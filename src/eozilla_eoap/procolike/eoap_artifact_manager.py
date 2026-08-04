import itertools
import shutil
from dataclasses import dataclass
from ftplib import FTP
from functools import singledispatch
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Tuple, Union, get_args, get_origin
from urllib.parse import unquote

import pystac
import requests
from pydantic import AnyUrl, BaseModel, HttpUrl
from pystac import STACObject
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
        self.persistent_output_directory: Path | None = (
            None  # NOTE: Runner only uses this, out and log directory should be created by artifact manager
        )
        self.staged_in_files: Dict[str, List[Path]] = {}
        self.staged_in_directories: Dict[str, List[Path]] = {}

    def __del__(self):
        self.remove_staged_in_files()
        self.remove_staged_in_directories()
        if self.persistent_output_directory.exists():
            shutil.rmtree(self.persistent_output_directory)

    def initialize(self):
        self.persistent_output_directory = Path(self.base, self.job_id)
        self.persistent_output_directory.mkdir(parents=True, exist_ok=False)
        Path(self.persistent_output_directory, "out").mkdir(
            parents=False, exist_ok=False
        )
        Path(self.persistent_output_directory, "log").mkdir(
            parents=False, exist_ok=False
        )

    def stage_in(self):
        self.stage_in_files()
        self.stage_in_directories()

    def stage_in_files(self):
        # NOTE: This method has the side effect of updating the supplied instance model
        self.staged_in_files, self.process_instance_model = _iteratively_resolve_files(
            self.process_instance_model,
            path_to_location=True,
        )

    def stage_in_directories(self):
        # NOTE: This method has the side effect of updating the supplied instance model
        self.staged_in_directories, self.process_instance_model = (
            _iteratively_resolve_directories(
                self.process_instance_model,
                path_to_location=True,
            )
        )

    def rebuild_process_arguments(self) -> Dict[str, Any]:
        return self.process_instance_model.model_dump(
            mode="python", exclude_unset=False, exclude_none=True
        )

    def remove_staged_inputs(self):
        self.remove_staged_in_files()
        self.remove_staged_in_directories()

    def remove_staged_in_files(self):
        for _path in itertools.chain.from_iterable(self.staged_in_files.values()):
            if not _path.exists():
                continue
            _path.unlink()
            shutil.rmtree(_path.parent)

    def remove_staged_in_directories(self):
        for _path in itertools.chain.from_iterable(self.staged_in_directories.values()):
            if not _path.exists():
                continue
            shutil.rmtree(_path)


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

    with FTP(url.server) as ftp:
        if url.username:
            ftp.login(url.username, url.password)
        else:
            ftp.login()

        with open(full_out_path, "wb") as f:
            ftp.retrbinary(f"RETR {url.path}", f.write)

    return full_out_path


# NOTE: we're only ever exposing a path, not a complete File model as defined by CWL
def _iteratively_resolve_files(
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
                        _dispatch_singular_file_download(_string_to_url_class(x.path))
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
                        _dispatch_singular_file_download(
                            _string_to_url_class(potential_file.path)
                        ),
                    ]

                    potential_file.path = str(return_mapping[tag][0])

                    if path_to_location:
                        potential_file.location = potential_file.path
                        potential_file.path = None
        elif issubclass(annotation, File):
            f: File = model.__dict__.get(tag)
            return_mapping[tag] = [
                _dispatch_singular_file_download(_string_to_url_class(f.path)),
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


def _load_stac(path: str) -> ItemCollection | Catalog | Item:
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
def _iteratively_resolve_directories(
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
                            _dispatch_stac_resolving(_load_stac(x.path))
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
                                _load_stac(potential_directory.path)
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
                    _dispatch_stac_resolving(_load_stac(d.path))
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
