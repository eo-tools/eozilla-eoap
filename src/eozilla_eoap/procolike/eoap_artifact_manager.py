import itertools
import shutil
from dataclasses import dataclass
from ftplib import FTP
from functools import singledispatch
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Literal, NewType, Tuple, Union, get_args, get_origin
from urllib.parse import unquote

import requests
from pydantic import AnyUrl, BaseModel

from eozilla_eoap.procolike.eoap_process import File


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
    """
    def __init__(self, base: Path, job_id: str, process_instance_model: BaseModel):
        self.base: Path = base
        self.job_id: str = job_id
        self.process_instance_model: BaseModel = process_instance_model
        self.persistent_output_directory: Path | None = (
            None  # NOTE: Runner only uses this, out and log directory should be created by artifact manager
        )
        self.resolved_files: Dict[str, List[Path]] = {}

    def __del__(self):
        self.remove_staged_files()
        self.remove_staged_directories()
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

    def resolve_remote_inputs(self): ...  # stage both files and directories

    def resolve_remote_files(self):
        self.resolved_files, self.process_instance_model = _iteratively_resolve_files(
            self.process_instance_model,
            path_to_location=True,
        )

    def resolve_remote_directories(self): ...

    def rebuild_process_arguments(self) -> Dict[str, Any]:
        return self.process_instance_model.model_dump(
            mode="python", exclude_unset=False, exclude_none=True
        )

    def remove_staged_inputs(self):
        self.remove_staged_files()

    def remove_staged_files(self):
        for _path in itertools.chain.from_iterable(self.resolved_files.values()):
            if not _path.exists():
                continue
            _path.unlink()
            shutil.rmtree(_path.parent)

    def remove_staged_directories(self): ...


@dataclass
class HttpUrl:
    location: str


@dataclass
class FtpUrl:
    username: str | None
    password: str | None
    server: str
    path: str


def _string_to_url_class(url: str) -> HttpUrl | FtpUrl:
    any_url: AnyUrl = AnyUrl(url)
    if any_url.scheme in ["http", "https"]:
        return HttpUrl(url)
    elif any_url.scheme in [
        "ftp",
    ]:
        user: str = unquote(any_url.username) if any_url.username else ""
        password: str = unquote(any_url.password) if any_url.password else ""
        return FtpUrl(user, password, any_url.host, unquote(any_url.path))
    else:
        raise NotImplementedError(f"No support for URLs with scheme {any_url.scheme}")


@singledispatch
def _dispatch_singular_file_download(url) -> Path:
    raise TypeError(f"Download not implemented for {type(url)}")


@_dispatch_singular_file_download.register(HttpUrl)
def _(url: HttpUrl) -> Path:
    r = requests.get(url.location, stream=True, timeout=60)
    r.raise_for_status()

    server_side_name: str = r.headers.get("Content-Disposition")
    url_derived_name: str = url.location.rsplit("/", 1).pop()
    out_name = server_side_name or url_derived_name

    out_dir = TemporaryDirectory(prefix="cwl-input-staging", delete=False).name

    full_out_path = Path(out_dir, out_name)

    with open(full_out_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024):
            f.write(chunk)
    r.close()

    return full_out_path


@_dispatch_singular_file_download.register(FtpUrl)
def _(url: FtpUrl) -> Path:
    out_name = url.path.rsplit("/", 1).pop()

    out_dir = TemporaryDirectory(prefix="cwl-input-staging", delete=False).name

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
