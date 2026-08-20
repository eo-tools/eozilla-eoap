import copy
import shutil
from dataclasses import dataclass
from ftplib import FTP
from functools import partial, singledispatch
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Dict, List, Tuple, Union, get_args, get_origin
from urllib.parse import unquote
from urllib.request import pathname2url, url2pathname

import pystac
import requests
from pydantic import AnyUrl, BaseModel, FileUrl, HttpUrl
from pystac import STACObject
from pystac.asset import Asset
from pystac.catalog import Catalog
from pystac.item import Item
from pystac.item_collection import ItemCollection

from eozilla_eoap.procolike.eoap_process import Directory, File


class LocalArtifactManager:
    """Resolving remote input files and manage output directories

    The LocalArtifactManager is responsible for:
        - create the runs directory and it's subdirectory for a given Job
        - resolve remote files to local ones, i.e. download them
        - patch the instance model created based off of process
          arguments to point to local files instead of URLs
        - regenerate dictonary to be used as input for workflow execution
        - remove previously downloaded input files after workflow execution,
          both in case of successful and failed runs
        - cleanup output files and directories, either explicitly or when deleting
          an instance

    While this is tightly coupled to job execution and delegation of
    actual execution to a CWL runner, it's not really the responsibility
    of either 'classes' and thus factored out.

    Notes:
        - Rationale for downloading files: "At job submission, the inputs passed
            as references (as HTTP link, S3 link, etc.) must be fetched and made
            available for processing by executing the CWL document." While this
            could also mean, transparently mapping the file and not actually
            downloading it eagerly, this is to much for the current state of
            the implementation.
        - Rationale for not downloding assets in Directories: "For the data
            stage-in, the Platform creates a local STAC Catalog with a STAC Item
            whose Assets have an accessible href (either local or remote e.g. COG)
            as the input files manifest for the application."
    """

    def __init__(self, base: Path, job_id: str, process_instance_model: BaseModel):
        """Constructor for LocalArtifactManager

        Args:
            base (Path): Base directory where persistent output is stored
            job_id (str): Unique job Id
            process_instance_model (BaseModel): Process instance model, i.e. validated inputs
        """
        self.base: Path = base
        self.job_id: str = job_id
        self.process_instance_model: BaseModel = process_instance_model
        self.persistent_output_directory: Path | None = None
        self.temporary_output_directory: Path | None = None
        self.staged_in_files: Dict[str, List[Path]] = {}
        self.staged_in_directories: Dict[str, List[Path]] = {}
        self.staged_out_files: Dict[str, List[Path]] = {}
        self.staged_out_directories: Dict[str, List[Path]] = {}

    def __del__(self):
        """Destructor for LocalArtifactManager

        The destructor cleans up all staged-in files and STAC catalogs
        as well all staged-out files and STAC catalogs.
        """
        self.remove_staged_in_files()
        self.remove_staged_in_directories()
        self.remove_persistent_outputs()
        self.remove_temporary_outputs()

    def initialize(self) -> None:
        """Initialize Temporary and Persistent Output Directories.

        Creates empty directories for temporary and persistent outputs
        of a given job execution together with the respective
        log and out subdirectories.

        Raises:
            FileExistsError: Directories already exist, hinting at duplicate
                job Ids.
        """
        self.persistent_output_directory = Path(self.base, self.job_id)
        self.persistent_output_directory.mkdir(parents=True, exist_ok=False)
        Path(self.persistent_output_directory, "out").mkdir(
            parents=False, exist_ok=False
        )
        Path(self.persistent_output_directory, "log").mkdir(
            parents=False, exist_ok=False
        )
        self.temporary_output_directory = Path(
            TemporaryDirectory(prefix="cwl-temporary-output-", delete=False).name
        )
        Path(self.temporary_output_directory, "out").mkdir(
            parents=False, exist_ok=False
        )
        Path(self.temporary_output_directory, "log").mkdir(
            parents=False, exist_ok=False
        )

    def stage_in(self) -> None:
        """Stage-in `File` and `Directory` arguments"""
        self.stage_in_files()
        self.stage_in_directories()

    def stage_in_files(self) -> None:
        """Stage-In `File` Arguments

        Notes:
            This method has the side effect of updating the supplied process
            instance model.
        """
        # NOTE: This method has the side effect of updating the supplied instance model
        self.staged_in_files, self.process_instance_model = _iteratively_stage_in_files(
            self.process_instance_model,
            path_to_location=True,
        )

    def stage_in_directories(self) -> None:
        """Stage-In `Directory` Arguments

        Notes:
            This method has the side effect of updating the supplied process
            instance model.
        """
        # NOTE: This method has the side effect of updating the supplied instance model
        self.staged_in_directories, self.process_instance_model = (
            _iteratively_stage_in_directories(
                self.process_instance_model,
                path_to_location=True,
            )
        )

    def rebuild_process_arguments(self) -> Dict[str, Any]:
        """Regenerate Process Argument Dictonary

        After staging-in `File` and `Directory` arguments and updating the
        respective model fields, the original argument dictonary must be
        regenerated to point to the resolved, now local, entities.

        Returns:
            Dict[str, Any]: Regenerated process argument dictionary.
        """
        return self.process_instance_model.model_dump(
            mode="python", exclude_unset=False, exclude_none=True
        )

    def stage_out(self, workflow_results: Dict[str, Any]) -> Dict[str, Any]:
        """Stage-Out Logs and Results of Workflow/Process execution.

        Notes:
            - The `workflow_results` input argument is copied, changes are
              not visible on the original value.

        Args:
            workflow_results (Dict[str, Any]): Workflow/Process results returned by executor.

        Returns:
            Dict[str, Any]: Patched results dictionary.
        """
        transformed_results: Dict[str, Any] = copy.deepcopy(workflow_results)

        self.stage_out_logs()
        patched_results = self.stage_out_results(transformed_results)

        return patched_results

    def stage_out_logs(self) -> None:
        """Stage-Out Log Files by Copying entire Filesystem Trees

        Notes:
            Here, pre-existing directories are allowed since the
            artifact manager already created the directories upon
            initialization.
        """
        if not (self.temporary_output_directory and self.persistent_output_directory):
            raise RuntimeError

        tmp_log_dir: Path = Path(self.temporary_output_directory, "log")
        per_log_dir: Path = Path(self.persistent_output_directory, "log")

        shutil.copytree(tmp_log_dir, per_log_dir, symlinks=False, dirs_exist_ok=True)

        self.staged_out_directories["logs"] = [
            per_log_dir,
        ]

    def stage_out_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Stage-out `File` and `Directory` Workflow Results.

        The results of a workflow/process execution are checked for entries
        of type `File` or `Directory`. These are staged-out to a persistent
        directory and the respective type models are replaced by a string
        value pointing to the result.

        Notes:
            - The `workflow_results` input argument is copied, changes are
              not visible on the original value.
            - For STAC catalogs, only the `catalog.json` is returned which
              is sufficient to discover all related output data.

        Args:
            results (Dict[str, Any]): Workflow/Process results returned by executor.

        Returns:
            Dict[str, Any]: Patched results dictionary.
        """
        if not (self.temporary_output_directory and self.persistent_output_directory):
            raise RuntimeError

        # QUESTION: Work with result dict or with files found in file system?
        tmp_out_dir: Path = Path(self.temporary_output_directory, "out")
        per_out_dir: Path = Path(self.persistent_output_directory, "out")

        staged_out_files, results = _iteratively_stage_out_files(
            results, src_base=tmp_out_dir, dst_base=per_out_dir
        )
        self.staged_out_files.update(staged_out_files)

        staged_out_directories, results = _iteratively_stage_out_directories(
            results, dst_base=per_out_dir
        )
        self.staged_out_directories.update(staged_out_directories)

        return results

    def remove_staged_inputs(self) -> None:
        """Remove Staged-In `Files` and `Directories`"""
        self.remove_staged_in_files()
        self.remove_staged_in_directories()

    def remove_staged_in_files(self) -> None:
        """Remove Staged-In `Files`.

        Iterate over all previously staged-in files, deleting them
        and the temporary directory they were placed in.
        """
        remaining_entries: Dict[str, List[Path]] = {}
        for arg in self.staged_in_files.keys():
            for _path in self.staged_in_files[arg]:
                if not _path.exists():
                    remaining_entries[arg] = [
                        _path,
                    ]
                    continue
                _path.unlink()
                shutil.rmtree(_path.parent)

        self.staged_in_files = remaining_entries

    def remove_staged_in_directories(self) -> None:
        """Remove Staged-In `Directories`.

        Iterate over all previously staged-in STAC catalogs,
        unlinking the entire temporary directory they were placed in.
        """
        remaining_entries: Dict[str, List[Path]] = {}
        for arg in self.staged_in_directories.keys():
            for _path in self.staged_in_directories[arg]:
                if not _path.exists():
                    remaining_entries[arg] = [
                        _path,
                    ]
                    continue
                shutil.rmtree(_path)

        self.staged_in_directories = remaining_entries

    def remove_temporary_outputs(self) -> None:
        if (
            self.temporary_output_directory is not None
            and self.temporary_output_directory.exists()
        ):
            shutil.rmtree(self.temporary_output_directory)

    def remove_persistent_outputs(self) -> None:
        if (
            self.persistent_output_directory is not None
            and self.persistent_output_directory.exists()
        ):
            shutil.rmtree(self.persistent_output_directory)


@dataclass
class WrappedHttpUrl:
    location: str


@dataclass
class WrappedFtpUrl:
    username: str
    password: str
    server: str
    path: str


def _string_to_url_class(url: str) -> WrappedHttpUrl | WrappedFtpUrl:
    """Convert an URL to a known URL Type

    The supplied URL is validated using pydantic's `AnyUrl` model and
    converted to a known URL type for downloading.

    Args:
        url (str): URL supplied by the user in process execution request
            for arguments of type `File`.

    Raises:
        NotImplementedError: Supplied URL's scheme is not implemented for
            remote data access.

    Returns:
        WrappedHttpUrl | WrappedFtpUrl: Instance of URL type.
    """
    any_url: AnyUrl = AnyUrl(url)
    if any_url.scheme in ["http", "https"]:
        return WrappedHttpUrl(url)
    elif any_url.scheme in [
        "ftp",
    ]:
        user: str = unquote(any_url.username) if any_url.username else ""
        password: str = unquote(any_url.password) if any_url.password else ""
        return WrappedFtpUrl(user, password, any_url.host, unquote(any_url.path))
    else:
        raise NotImplementedError(f"No support for URLs with scheme {any_url.scheme}")


@singledispatch
def _dispatch_singular_file_download(url: AnyUrl) -> Path:
    """Generic Function for Remote File Download

    Args:
        url (AnyUrl): Previously converted URL.

    Raises:
        TypeError: Raised in case not-implemented URL type is supplied.

    Returns:
        Path: Local path of downloaded file.
    """
    raise TypeError(f"Download not implemented for {type(url)}")


@_dispatch_singular_file_download.register(WrappedHttpUrl)
def _(url: WrappedHttpUrl) -> Path:
    """Download Remote File via HTTP(S)

    Files accessible via HTTP(S) are downloaded stored in a
    temporary directory. The file name is taken either from the
    "Content-Disposition" header field or the last fragment of
    the supplied URL.

    Notes:
        - A connection timeout of 60 seconds is set when connecting
          to the remote server

    Args:
        url (WrappedHttpUrl): Perviously converted/validated URL.

    Returns:
        Path: Local path of downloaded file.
    """
    r = requests.get(url.location, stream=True, timeout=60)
    r.raise_for_status()

    server_side_name: str | None = r.headers.get("Content-Disposition")
    url_derived_name: str = url.location.rsplit("/", 1).pop()
    out_name = server_side_name or url_derived_name

    out_dir = TemporaryDirectory(prefix="cwl-input-staging-", delete=False).name

    full_out_path = Path(out_dir, out_name)

    with open(full_out_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024):
            f.write(chunk)
    r.close()

    return full_out_path


@_dispatch_singular_file_download.register(WrappedFtpUrl)
def _(url: WrappedFtpUrl) -> Path:
    """Download Remote File via FTP

    Files accessible via FTP are downloaded stored in a
    temporary directory. The file name is taken from the
    last fragment of the supplied URL.

    Warnings:
        - FTP is an insecure protocol and should probably not be
          used in production

    Notes:
        - No connection timeout is set

    Args:
        url (WrappedHttpUrl): Perviously converted/validated URL.

    Returns:
        Path: Local path of downloaded file.
    """
    out_name = url.path.rsplit("/", 1).pop()

    out_dir = TemporaryDirectory(prefix="cwl-input-staging-", delete=False).name

    full_out_path = Path(out_dir, out_name)

    with FTP(url.server) as ftp:  # noqa: S321
        if url.username:
            ftp.login(url.username, url.password)
        else:
            ftp.login()

        with open(full_out_path, "wb") as f:
            ftp.retrbinary(f"RETR {url.path}", f.write)

    return full_out_path


def _iteratively_stage_in_files(
    model: BaseModel, path_to_location: bool = False
) -> Tuple[Dict[str, List[Path]], BaseModel]:
    """Iteratively Stage-In `File` Arguments

    Iterate over all fields of the process model instance and download
    remote file resources. Other arguments are left untouched.

    Since an OGC compliant server does not expose the entire `File` model
    defined by the CWL standard, resolving them becomes easier as we do not
    need to concern ourselves with additional (secondary) files. Optional
    files, list of files and optional list of files are all handled.

    Args:
        model (BaseModel): Process instance model
        path_to_location (bool, optional): Remap the path attribute of the `File`
            model to `location`. Defaults to False.

    Raises:
        AssertionError: Unexpected code path.

    Returns:
        Tuple[Dict[str, List[Path]], type[BaseModel]]: Tuple of (1) argument name and list of
            local file paths pointing to downloaded files and (2) updated process instance model.
    """
    return_mapping: Dict[str, List[Path]] = {}

    for tag, val in model.__class__.model_fields.items():
        annotation = val.annotation

        # separate type annotation
        #   origin is whatever wraps the type, e.g. a Union, List...
        #   args is the type that was wrapped, e.g. for Optional[str] -> (str, NoneType)
        origin = get_origin(annotation)
        args = get_args(annotation)

        if origin in (Union, list):
            for arg in args:
                if (
                    isinstance(arg, type)
                    and issubclass(arg, BaseModel)
                    and not issubclass(arg, File)
                ):
                    raise AssertionError(
                        "This path should not be possible in case of EOAPs"
                    )
                if not (isinstance(arg, type) and issubclass(arg, File)):
                    continue

                potential_file: File | List[File] | None = model.__dict__.get(tag)
                if not potential_file:
                    continue

                if isinstance(potential_file, list):
                    return_mapping[tag] = [
                        Path(
                            _dispatch_singular_file_download(
                                _string_to_url_class(
                                    x.path
                                )  # FIXME: here and elsewhere: it's not guarantueed that the path variable is set; how do I guard against that?
                            )
                        )
                        for x in potential_file
                    ]

                    for f_model, p in zip(
                        potential_file, return_mapping[tag], strict=True
                    ):
                        f_model.path = str(p)

                        if path_to_location:
                            f_model.location = f_model.path
                            f_model.path = None

                else:
                    return_mapping[tag] = [
                        Path(
                            _dispatch_singular_file_download(
                                _string_to_url_class(potential_file.path)
                            )
                        ),
                    ]

                    potential_file.path = str(return_mapping[tag][0])

                    if path_to_location:
                        potential_file.location = potential_file.path
                        potential_file.path = None
        elif issubclass(annotation, File):
            f: File = model.__dict__[tag]
            return_mapping[tag] = [
                Path(
                    _dispatch_singular_file_download(_string_to_url_class(f.path)),
                )
            ]

            f.path = str(return_mapping[tag][0])

            if path_to_location:
                f.location = f.path
                f.path = None
        else:
            continue

    model = model.model_validate(model)

    return return_mapping, model


def _get_local_catalog_base_directory(catalog: Catalog) -> Path:
    """Get the Parent Directory of a STAC Catalog

    Args:
        catalog (Catalog): STAC Catalog

    Returns:
        Path: Parent directory of input STAC catalog
    """
    self_ref: str | None = catalog.get_self_href()
    if not self_ref:
        raise RuntimeError

    return Path(self_ref).parent


@singledispatch
def _dispatch_stac_resolving(stac_obj: pystac.STACObject) -> Catalog:
    """Generic Function for Remote STAC Download

    Args:
        stac_obj (pystac.STACObject): In-memory representation of STAC object.

    Raises:
        NotImplementedError: Raised in case not-implemented STAC type is supplied.

    Returns:
        Catalog: Local path of of resolved and downloaded STAC Catalog.
    """
    raise NotImplementedError("Generic STAC resoving to local catalog not implemented.")


@_dispatch_stac_resolving.register(Catalog)
def _(stac_obj: Catalog) -> Catalog:
    """Generate Self-Contained STAC Catalog in Temporary Directory

    Stage-in a STAC Catalog by generating a self-contained STAC
    Catalog in the local file system. All items/children are saved under the same
    directory but no actual data is downloaded.

    Args:
        stac_obj (Catalog): In-memory representation of STAC Catalog.

    Raises:
        RuntimeWarning: Always Raised since stage-in of an entire STAC Catalog
            seems unreasonable.

    Returns:
        Catalog: Local path to staged-in STAC Catalog.
    """
    raise RuntimeWarning("Using a catlog seems unreasonable, disallowed.")

    out_dir = TemporaryDirectory(prefix="cwl-input-staging-", delete=False).name

    catalog: Catalog = stac_obj.full_copy()
    catalog.set_self_href(out_dir)
    catalog.normalize_hrefs(str(out_dir))
    catalog.save()

    return catalog


@_dispatch_stac_resolving.register(ItemCollection)
def _(stac_obj: ItemCollection) -> Catalog:
    """Generate Self-Contained STAC Catalog in Temporary Directory

    Stage-in a STAC ItemCollection by generating a self-contained STAC
    Catalog in the local file system. All items are saved under the same
    directory but no actual data is downloaded.

    Args:
        stac_obj (ItemCollection): In-memory representation of STAC ItemCollection.

    Raises:
        ValueError: Raised if input ItemCollection doesn't hold any items.

    Returns:
        Catalog: Local path to staged-in STAC Catalog.
    """
    if len(stac_obj.items) == 0:
        raise ValueError("Empty ItemCollection")

    out_dir = TemporaryDirectory(prefix="cwl-input-staging-", delete=False).name

    catalog: Catalog = Catalog(
        id=stac_obj.items[0].collection_id or "eoap-input-catalog",
        description="STAC Catalog of EOAP inputs.",
        catalog_type=pystac.CatalogType.SELF_CONTAINED,
        stac_extensions=stac_obj[0].stac_extensions,
    )
    catalog.set_self_href(out_dir)
    catalog.add_items(stac_obj.items)
    catalog.normalize_hrefs(str(out_dir))
    catalog.save()

    return catalog


@_dispatch_stac_resolving.register(Item)
def _(stac_obj: Item) -> Catalog:
    """Generate Self-Contained STAC Catalog in Temporary Directory

    Stage-in a STAC Item by generating a self-contained STAC
    Catalog in the local file system. The item is saved under the same
    directory but no actual data is downloaded.

    Args:
        stac_obj (Item): In-memory representation of STAC Item.

    Returns:
        Catalog: Local path to staged-in STAC Catalog.
    """
    out_dir = TemporaryDirectory(prefix="cwl-input-staging", delete=False).name

    catalog: Catalog = Catalog(
        id=stac_obj.collection_id or "eoap-input-catalog",
        description="STAC Catalog of EOAP inputs.",
        catalog_type=pystac.CatalogType.SELF_CONTAINED,
        stac_extensions=stac_obj.stac_extensions,
    )
    catalog.set_self_href(out_dir)
    catalog.add_item(stac_obj)
    catalog.normalize_hrefs(str(out_dir))
    catalog.save()

    return catalog


def _load_remote_stac_from_http_url(path: str) -> ItemCollection | Catalog | Item:
    """Read STAC Object from Remote Location.

    Args:
        path (str): URL pointing to a remote STAC Object.

    Raises:
        ValidationError: Raised in case the supplied URL does not match
            pydantic's HttpUrl-scheme.
        ValueError: Raised in case the supplied URL does not point to
            a STAC ItemCollection, STAC Catalog or STAC Item.

    Returns:
        ItemCollection | Catalog | Item: In-memory representation of STAC object.
    """
    validated_url: HttpUrl = HttpUrl(path)

    try:
        generic_stac_obj: STACObject = STACObject.from_file(str(validated_url))
    except pystac.errors.STACTypeError:
        return ItemCollection.from_file(str(validated_url))
    else:
        if generic_stac_obj.STAC_OBJECT_TYPE == "Catalog":
            return Catalog.from_dict(generic_stac_obj.to_dict())
        elif generic_stac_obj.STAC_OBJECT_TYPE == "Feature":
            return Item.from_dict(generic_stac_obj.to_dict())
        else:
            raise ValueError(
                f"Supplied STAC type ('{generic_stac_obj.STAC_OBJECT_TYPE}') not supported."
            ) from None


def _load_local_stac_from_cwl_output(path: str) -> Catalog:
    """Read STAC Object from Local Location.

    Notes:
        - The OGC Best Practice Guidelines state that a output STAC Catalog must
          be named "catalog.json"

    Args:
        path (str): Path pointing to a local STAC Object.

    Raises:
        ValidationError: Raised in case the supplied URL does not match
            pydantic's FileUrl-scheme.
        RuntimeError: Raied in case there's no file called 'catalog.json'.
        ValueError: Raised in case the supplied URL does not point to
            a STAC Catalog.

    Returns:
        ItemCollection | Catalog | Item: In-memory representation of STAC object.
    """
    validated_url: FileUrl = FileUrl(path + "/catalog.json")
    parsed_path: str = url2pathname(str(validated_url), require_scheme=True)

    if not Path(parsed_path).exists():
        raise RuntimeError(
            f"{parsed_path} does not point to an existing STAC Catalog, outputs must be named 'catalog.json'."
        )

    try:
        generic_stac_obj: STACObject = STACObject.from_file(parsed_path)
    except pystac.errors.STACTypeError as e:
        raise ValueError("EO Output must be a STAC Catalog.") from e
    else:
        if generic_stac_obj.STAC_OBJECT_TYPE != "Catalog":
            raise ValueError("EO Output must be a STAC Catalog.") from e

        return Catalog.from_dict(generic_stac_obj.to_dict())


def _wolfgang_beltracchi(
    key: str, value: Asset, source_trunk: str, destination_trunk: str
) -> Dict[str, Asset]:
    """Copy STAC Asset to new trunk

    The source trunk refers to the base directory of the catalog, i.e. when /path/to/old/catalog.json is the full
    path to the catalog source, `source_trunk` is /path/to/old and `destination_trunk` is a new absolute path
    under which the copied catalog is placed, i.e. /new/path/old/catalog.json.
    Thus, the encapsulating directory is preserved!

    Args:
        key (str): Asset key (name) in containing STAC object.
        value (Asset): STAC Asset
        source_trunk (str): Path to root of root STAC object containing the asset to copy.
        destination_trunk (str): Path to new root of root STAC object containing the copied asset.

    Returns:
        Dict[str, Asset]: Mapping of asset key (name) in new STAC object to new Asset instance with copied data.
    """
    # check if asset href is a local absolute path, if not simply return
    asset_path: Path = Path(value.href)
    if not (asset_path.is_absolute() and asset_path.exists()):
        return {key: value}

    new_location: str = value.href.replace(source_trunk, destination_trunk)

    Path(new_location).parent.mkdir(parents=True, exist_ok=True)

    new_asset: Asset = value.copy(new_location)

    return {key: new_asset}


def _copy_local_stac_catalog_to_new_trunk(
    stac_obj: Catalog, local_catalog_path: Path
) -> Catalog:
    """Copy a STAC Catalog to new Trunk

    Copy an entire STAC Catalog to a new location while retaining the orignal parent
    directory name of the catalog. All assets, including the actual data pointed to, are
    copied to the new location. The new STAC Catalog is self-contained.

    Raises:
        FileExistsError: The output directory pointed inferred in `local_catalog_path`
            already exists.

    Note:
        Nothing from a self-contained STAC catalog can be outside of `Path(stac_obj.get_self_href()).parent`.

    Args:
        stac_obj (Catalog): In-memory STAC Catalog object to be copied.
        local_catalog_path (Path): Base directory to which outputs are staged.

    Returns:
        Catalog: Copied STAC Catalog poining to new location.
    """
    self_ref: str | None = stac_obj.get_self_href()
    if not self_ref:
        raise RuntimeError

    self_source_trunk: Path = Path(self_ref).parent

    self_destination_trunk = Path(local_catalog_path, self_source_trunk.name)
    self_destination_trunk.mkdir(parents=True, exist_ok=False)

    local_beltracchi: Callable[[str, Asset], Dict[str, Asset]] = partial(
        _wolfgang_beltracchi,
        source_trunk=str(self_source_trunk),
        destination_trunk=str(self_destination_trunk),
    )

    stac_obj.make_all_asset_hrefs_absolute()

    catalog: Catalog = stac_obj.map_assets(local_beltracchi)

    catalog.set_self_href(str(self_destination_trunk))

    catalog.normalize_hrefs(str(self_destination_trunk))

    catalog.make_all_asset_hrefs_relative()

    _ = [item.set_root(catalog) for item in catalog.get_all_items()]  # type: ignore[func-returns-value]

    catalog.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)

    return catalog


def _iteratively_stage_in_directories(
    model: BaseModel, path_to_location: bool = False
) -> Tuple[Dict[str, List[Path]], BaseModel]:
    """Iteratively Stage-In `Directory` Arguments

    Iterate over all fields of the process model instance and download/
    stage-in remote STAC object inputs. Other arguments are left untouched.

    Since an OGC compliant server does not expose the entire `Directory` model
    defined by the CWL standard, resolving them becomes easier as we do not
    need to concern ourselves with additional listings defined. Optional
    STAC inputs, list of STAC inputs and optional list of STAC inputs are
    all handled.

    Args:
        model (BaseModel): Process instance model
        path_to_location (bool, optional): Remap the path attribute of the `Directory`
            model to `location`. Defaults to False.

    Raises:
        AssertionError: Unexpected code path.

    Returns:
        Tuple[Dict[str, List[Path]], type[BaseModel]]: Tuple of (1) argument name and list of
            local file paths pointing to base directory of staged-in STAC Catalogs
            and (2) updated process instance model.
    """
    return_mapping: Dict[str, List[Path]] = {}

    for tag, val in model.__class__.model_fields.items():
        annotation = val.annotation

        # separate type annotation
        #   origin is whatever wraps the type, e.g. a Union, List...
        #   args is the type that was wrapped, e.g. for Optional[str] -> (str, NoneType)
        origin = get_origin(annotation)
        args = get_args(annotation)

        if origin in (Union, list):
            for arg in args:
                if (
                    isinstance(arg, type)
                    and issubclass(arg, BaseModel)
                    and not issubclass(arg, Directory)
                ):
                    raise AssertionError(
                        "This path should not be possible in case of EOAPs"
                    )
                if not (isinstance(arg, type) and issubclass(arg, Directory)):
                    continue

                potential_directory: Directory | List[Directory] | None = (
                    model.__dict__.get(tag)
                )
                if not potential_directory:
                    continue

                if isinstance(potential_directory, list):
                    return_mapping[tag] = [
                        _get_local_catalog_base_directory(
                            _dispatch_stac_resolving(
                                _load_remote_stac_from_http_url(x.path)
                            )
                        )
                        for x in potential_directory
                    ]

                    for d_model, p in zip(
                        potential_directory, return_mapping[tag], strict=True
                    ):
                        d_model.path = str(p)

                        if path_to_location:
                            d_model.location = d_model.path
                            d_model.path = None

                else:
                    return_mapping[tag] = [
                        _get_local_catalog_base_directory(
                            _dispatch_stac_resolving(
                                _load_remote_stac_from_http_url(
                                    potential_directory.path
                                )
                            )
                        ),
                    ]

                    potential_directory.path = str(return_mapping[tag][0])

                    if path_to_location:
                        potential_directory.location = potential_directory.path
                        potential_directory.path = None
        elif issubclass(annotation, Directory):
            d: File = model.__dict__[tag]
            return_mapping[tag] = [
                _get_local_catalog_base_directory(
                    _dispatch_stac_resolving(_load_remote_stac_from_http_url(d.path))
                ),
            ]

            d.path = str(return_mapping[tag][0])

            if path_to_location:
                d.location = d.path
                d.path = None
        else:
            continue

    model = model.model_validate(model)

    return return_mapping, model


def _iteratively_stage_out_files(
    results: Dict[str, Any], src_base: Path, dst_base: Path
) -> Tuple[Dict[str, List[Path]], Dict[str, Any]]:
    """Iteratively Stage-Out all `File` Values

    Iterate over all fields of the workflow/process return
    dictionary and stage-out all entries of type `File`
    to a persistent directory. Other arguments are left untouched

    The updated dictionary fields are converted from CWL's
    `File` model to local path URLs.

    Args:
        results (Dict[str, Any]): Workflow/Process results as dictionary.
        src_base (Path): Temporary output directory base managed by an
            instance of `LocalArtifactManager`.
        dst_base (Path): Persistent output directory base managed by an
            instance of `LocalArtifactManager`.

    Returns:
        Tuple[Dict[str, List[Path]], Dict[str, Any]]: Tuple of (1) argument name and list of
            local file paths pointing to staged-out files and (2) updated return value dictionary.
    """
    staged_out_files: Dict[str, List[Path]] = {}
    patched_result_dict: Dict[str, Any] = {}

    for result_tag, result_value in results.items():
        if type(result_value) is list:
            patched_sublist: List[Any] = []
            staged_out_sublist: List[Path] = []
            for item in result_value:
                if type(item) is not dict:
                    patched_sublist.append(item)
                    continue

                class_: str | None = item.get("class")
                if class_ is None or class_ != "File":
                    patched_sublist.append(item)
                    continue

                # cwltool populates all fields, so none accessed here is "None"
                f: File = File.model_validate(item)
                src_path: str = url2pathname(f.location, require_scheme=True)  # type: ignore[arg-type]
                dst_path: str = str(Path(dst_base, Path(src_path).name))

                shutil.copyfile(src_path, dst_path)

                patched_sublist.append(pathname2url(dst_path, add_scheme=True))
                staged_out_sublist.append(Path(dst_path))

            patched_result_dict[result_tag] = patched_sublist
            staged_out_files[result_tag] = staged_out_sublist
        elif type(result_value) is dict:
            class_: str | None = result_value.get("class")  # type: ignore[no-redef]
            if class_ is None or class_ != "File":
                patched_result_dict[result_tag] = result_value
                continue

            f: File = File.model_validate(result_value)  # type: ignore[no-redef]
            src_path: str = url2pathname(f.location, require_scheme=True)  # type: ignore[no-redef, arg-type]
            dst_path: str = Path(dst_base, Path(src_path).name)  # type: ignore[no-redef]

            shutil.copyfile(src_path, dst_path)

            patched_result_dict[result_tag] = pathname2url(dst_path, add_scheme=True)
            staged_out_files[result_tag] = [
                Path(dst_path),
            ]
        else:
            patched_result_dict[result_tag] = result_value

    return staged_out_files, patched_result_dict


def _iteratively_stage_out_directories(
    results: Dict[str, Any], dst_base: Path
) -> Tuple[Dict[str, List[Path]], Dict[str, Any]]:
    """Iteratively Stage-Out all `Directory` Values

    Iterate over all fields of the workflow/process return
    dictionary and stage-out all entries of type `Directory`
    to a persistent directory. Other arguments are left untouched

    The updated dictionary fields are converted from CWL's
    `Directory` model to local path URLs pointing to a "catalog.json".
    In contrast to stage-out of files, the STAC Catalog itself can provide
    the path to the "temporary output location", including any possibly
    existing parent directories which are preserved.

    Args:
        results (Dict[str, Any]): Workflow/Process results as dictionary.
        dst_base (Path): Persistent output directory base managed by an
            instance of `LocalArtifactManager`.

    Returns:
        Tuple[Dict[str, List[Path]], Dict[str, Any]]: Tuple of (1) argument name and list of
            local file paths pointing to staged-out files and (2) updated return value dictionary.
    """
    staged_out_directories: Dict[str, List[Path]] = {}
    patched_result_dict: Dict[str, Any] = {}

    for result_tag, result_value in results.items():
        if type(result_value) is list:
            patched_sublist: List[Any] = []
            staged_out_sublist: List[Path] = []
            for item in result_value:
                if type(item) is not dict:
                    patched_sublist.append(item)
                    continue

                class_: str | None = item.get("class")
                if class_ is None or class_ != "Directory":
                    patched_sublist.append(item)
                    continue

                # cwltool populates all fields, so none accessed here is "None"
                d: Directory = Directory.model_validate(item)

                old_catalog: ItemCollection | Catalog | Item = (
                    _load_local_stac_from_cwl_output(d.location)
                )

                if not isinstance(old_catalog, Catalog):
                    raise RuntimeError

                new_catalog: Catalog = _copy_local_stac_catalog_to_new_trunk(
                    old_catalog, dst_base
                )

                patched_sublist.append(new_catalog.get_self_href())
                staged_out_sublist.append(
                    _get_local_catalog_base_directory(new_catalog)
                )

            patched_result_dict[result_tag] = patched_sublist
            staged_out_directories[result_tag] = staged_out_sublist
        elif type(result_value) is dict:
            class_: str | None = result_value.get("class")  # type: ignore[no-redef]
            if class_ is None or class_ != "Directory":
                patched_result_dict[result_tag] = result_value
                continue

            d: Directory = Directory.model_validate(result_value)  # type: ignore[no-redef]

            old_catalog: ItemCollection | Catalog | Item = (  # type: ignore[no-redef]
                _load_local_stac_from_cwl_output(d.location)
            )

            if not isinstance(old_catalog, Catalog):
                raise RuntimeError

            new_catalog: Catalog = _copy_local_stac_catalog_to_new_trunk(  # type: ignore[no-redef]
                old_catalog, dst_base
            )

            patched_result_dict[result_tag] = new_catalog.get_self_href()
            staged_out_directories[result_tag] = [
                _get_local_catalog_base_directory(new_catalog),
            ]
        else:
            patched_result_dict[result_tag] = result_value

    return staged_out_directories, patched_result_dict
