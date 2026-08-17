import copy
import itertools
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
        self.remove_staged_in_files()
        self.remove_staged_in_directories()
        self.remove_persistent_outputs()
        self.remove_temporary_outputs()

    def initialize(self):
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

    def stage_in(self):
        self.stage_in_files()
        self.stage_in_directories()

    def stage_in_files(self):
        # NOTE: This method has the side effect of updating the supplied instance model
        self.staged_in_files, self.process_instance_model = _iteratively_stage_in_files(
            self.process_instance_model,
            path_to_location=True,
        )

    def stage_in_directories(self):
        # NOTE: This method has the side effect of updating the supplied instance model
        self.staged_in_directories, self.process_instance_model = (
            _iteratively_stage_in_directories(
                self.process_instance_model,
                path_to_location=True,
            )
        )

    def rebuild_process_arguments(self) -> Dict[str, Any]:
        return self.process_instance_model.model_dump(
            mode="python", exclude_unset=False, exclude_none=True
        )

    def stage_out(self, workflow_results: Dict[str, Any]) -> Dict[str, Any]:
        transformed_results: Dict[str, Any] = copy.deepcopy(workflow_results)

        self.stage_out_logs()
        patched_results = self.stage_out_results(transformed_results)

        return patched_results

    def stage_out_logs(self):
        tmp_log_dir: Path = Path(self.temporary_output_directory, "log")
        per_log_dir: Path = Path(self.persistent_output_directory, "log")

        # NOTE: allow for already existing directories since the artifact manager creates
        #       the respective directories upfront.
        shutil.copytree(tmp_log_dir, per_log_dir, symlinks=False, dirs_exist_ok=True)

        self.staged_out_directories["logs"] = per_log_dir

    def stage_out_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
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

    def remove_staged_inputs(self):
        self.remove_staged_in_files()
        self.remove_staged_in_directories()

    def remove_staged_in_files(self):
        remaining_entries: Dict[str, List[Path]] = {}
        for arg in self.staged_in_files.keys():
            for _path in self.staged_in_files[arg]:
                if not _path.exists():
                    remaining_entries[arg] = _path
                    continue
                _path.unlink()
                shutil.rmtree(_path.parent)

        self.staged_in_files = remaining_entries

    def remove_staged_in_directories(self):
        remaining_entries: Dict[str, List[Path]] = {}
        for arg in self.staged_in_directories.keys():
            for _path in self.staged_in_directories[arg]:
                if not _path.exists():
                    remaining_entries[arg] = _path
                    continue
                shutil.rmtree(_path)

        self.staged_in_directories = remaining_entries

    def remove_temporary_outputs(self):
        if self.persistent_output_directory is not None and self.temporary_output_directory.exists():
            shutil.rmtree(self.temporary_output_directory)

    def remove_persistent_outputs(self):
        if self.persistent_output_directory is not None and self.persistent_output_directory.exists():
            shutil.rmtree(self.persistent_output_directory)


@dataclass
class WrappedHttpUrl:
    location: str


@dataclass
class WrappedFtpUrl:
    username: str | None
    password: str | None
    server: str
    path: str


def _string_to_url_class(url: str) -> WrappedHttpUrl | WrappedFtpUrl:
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
def _dispatch_singular_file_download(url) -> Path:
    raise TypeError(f"Download not implemented for {type(url)}")


@_dispatch_singular_file_download.register(WrappedHttpUrl)
def _(url: WrappedHttpUrl) -> Path:
    r = requests.get(url.location, stream=True, timeout=60)
    r.raise_for_status()

    server_side_name: str = r.headers.get("Content-Disposition")
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


# NOTE: we're only ever exposing a path, not a complete File model as defined by CWL
def _iteratively_stage_in_files(
    model: BaseModel, path_to_location: bool = False
) -> Tuple[Dict[str, List[Path]], type[BaseModel]]:
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
                                _string_to_url_class(x.path)
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
            f: File = model.__dict__.get(tag)
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
    return Path(catalog.get_self_href()).parent


@singledispatch
def _dispatch_stac_resolving(stac_obj) -> Catalog:
    raise NotImplementedError("Generic STAC resoving to local catalog not implemented.")


@_dispatch_stac_resolving.register(Catalog)
def _(stac_obj: Catalog) -> Catalog:
    raise RuntimeWarning(
        "Using a catlog seems unreasonable, may be deprecated in the future."
    )

    out_dir = TemporaryDirectory(prefix="cwl-input-staging-", delete=False).name

    catalog: Catalog = stac_obj.full_copy()
    catalog.set_self_href(out_dir)
    catalog.normalize_hrefs(str(out_dir))
    catalog.save()

    return catalog


@_dispatch_stac_resolving.register(ItemCollection)
def _(stac_obj: ItemCollection) -> Catalog:
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


def _load_local_stac_from_cwl_output(path: str) -> ItemCollection | Catalog | Item:
    # NOTE: The best practive guide assumes a process generates a STAC catalog
    #       that is named "catalog.json"
    validated_url: FileUrl = FileUrl(path + "/catalog.json")
    parsed_path: str = url2pathname(str(validated_url), require_scheme=True)

    try:
        generic_stac_obj: STACObject = STACObject.from_file(parsed_path)
    except pystac.errors.STACTypeError:
        return ItemCollection.from_file(parsed_path)
    else:
        if generic_stac_obj.STAC_OBJECT_TYPE == "Catalog":
            return Catalog.from_dict(generic_stac_obj.to_dict())
        elif generic_stac_obj.STAC_OBJECT_TYPE == "Feature":
            return Item.from_dict(generic_stac_obj.to_dict())
        else:
            raise ValueError(
                f"Supplied STAC type ('{generic_stac_obj.STAC_OBJECT_TYPE}') not supported."
            ) from None


def _wolfgang_beltracchi(
    key: str, value: Asset, source_trunk: str, destination_trunk: str
) -> Dict[str, Asset]:
    """Copy STAC Asset to new trunk

    The source trunk refers to the base directory of the catalog, i.e. when /path/to/old/catalog.json is the full
    path to the catalog source, `source_trunk` is /path/to/old and `destination_trunk` is a new absolute path
    under which the copied catalog is placed, i.e. /new/path/old/catalog.json.
    Thus, the encapsulating directory is preserved!

    Args:
        key (str): _description_
        value (Asset): _description_
        source_trunk (str): _description_
        destination_trunk (str): _description_

    Returns:
        Dict[str, Asset]: _description_
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
    """_summary_

    Note:
        Nothing from a self-contained STAC catalog can be outside of `Path(stac_obj.get_self_href()).parent`.

    Args:
        stac_obj (Catalog): _description_
        local_catalog_path (Path): Base directory to which outputs are staged.

    Returns:
        Catalog: _description_
    """
    self_source_trunk: Path = Path(stac_obj.get_self_href()).parent

    self_destination_trunk = Path(local_catalog_path, self_source_trunk.name)
    self_destination_trunk.mkdir(parents=True, exist_ok=False)

    local_beltracchi: Callable[[str, Asset], Dict[str, Asset]] = partial(
        _wolfgang_beltracchi,
        source_trunk=str(self_source_trunk),
        destination_trunk=str(self_destination_trunk),
    )

    stac_obj.make_all_asset_hrefs_absolute()

    catalog: Catalog = stac_obj.map_assets(local_beltracchi)

    catalog.set_self_href(self_destination_trunk)

    catalog.normalize_hrefs(str(self_destination_trunk))

    catalog.make_all_asset_hrefs_relative()

    _ = [item.set_root(catalog) for item in catalog.get_all_items()]

    catalog.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)

    return catalog


# NOTE: we're only ever exposing a path, not a complete Directory model as defined by CWL
# NOTE: single-file-stac is deprecated since Dec, 22 2022!
# It's not quite clear to me what the replacement format should be tbh.
# Pystac in its current form isn't even able to identify single-file-stac (was able to hold
# Item and Collection). Thus, the only solution would be to support collections,
# catalogs and item collections;
# ItemCollection according to pystac's documentation is closest to GeoJSON FeatureCollections
# but can only hold Item-objects
# I understand section '9.4.  Data Flow Management' in the sense that the platform should download
# the data needed either upfront or lazily. I don't really get why because the program itself
# must be able to read STAC itself anyway, but whatever
def _iteratively_stage_in_directories(
    model: BaseModel, path_to_location: bool = False
) -> Tuple[Dict[str, List[Path]], type[BaseModel]]:
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
            d: File = model.__dict__.get(tag)
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
    staged_out_files: Dict[str, List[Path]] = {}
    patched_result_dict: Dict[str, Any] = {}

    for result_tag, result_value in results.items():
        if type(result_value) is list:
            patched_sublist = []
            staged_out_sublist = []
            for item in result_value:
                if type(item) is not dict:
                    patched_sublist.append(item)
                    continue

                class_: str | None = item.get("class")
                if class_ is None or class_ != "File":
                    patched_sublist.append(item)
                    continue

                f: File = File.model_validate(item)
                src_path: str = url2pathname(f.location, require_scheme=True)
                dst_path: str = Path(dst_base, Path(src_path).name)

                shutil.copyfile(src_path, dst_path)

                patched_sublist.append(pathname2url(dst_path, add_scheme=True))
                staged_out_files.append(dst_path)

            patched_result_dict[result_tag] = patched_sublist
            staged_out_files[result_tag] = staged_out_sublist
        elif type(result_value) is dict:
            class_: str | None = result_value.get("class")
            if class_ is None or class_ != "File":
                patched_result_dict[result_tag] = result_value
                continue

            f: File = File.model_validate(result_value)
            src_path: str = url2pathname(f.location, require_scheme=True)
            dst_path: str = Path(dst_base, Path(src_path).name)

            shutil.copyfile(src_path, dst_path)

            patched_result_dict[result_tag] = pathname2url(dst_path, add_scheme=True)
            staged_out_files[result_tag] = dst_path
        else:
            patched_result_dict[result_tag] = result_value

    return staged_out_files, patched_result_dict


def _iteratively_stage_out_directories(
    results: Dict[str, Any], dst_base: Path
) -> Tuple[Dict[str, List[Path]], Dict[str, Any]]:
    staged_out_directories: Dict[str, List[Path]] = {}
    patched_result_dict: Dict[str, Any] = {}

    for result_tag, result_value in results.items():
        if type(result_value) is list:
            patched_sublist = []
            staged_out_sublist = []
            for item in result_value:
                if type(item) is not dict:
                    patched_sublist.append(item)
                    continue

                class_: str | None = item.get("class")
                if class_ is None or class_ != "Directory":
                    patched_sublist.append(item)
                    continue

                d: Directory = Directory.model_validate(item)

                old_catalog: Catalog = _load_local_stac_from_cwl_output(d.location)

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
            class_: str | None = result_value.get("class")
            if class_ is None or class_ != "Directory":
                patched_result_dict[result_tag] = result_value
                continue

            d: Directory = Directory.model_validate(result_value)

            old_catalog: Catalog = _load_local_stac_from_cwl_output(d.location)

            new_catalog: Catalog = _copy_local_stac_catalog_to_new_trunk(
                old_catalog, dst_base
            )

            patched_result_dict[result_tag] = new_catalog.get_self_href()
            staged_out_directories[result_tag] = [
                _get_local_catalog_base_directory(new_catalog)
            ]
        else:
            patched_result_dict[result_tag] = result_value

    return staged_out_directories, patched_result_dict
