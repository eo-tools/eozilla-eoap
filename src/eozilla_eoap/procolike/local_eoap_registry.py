from collections.abc import Mapping
from csv import DictReader, DictWriter
from pathlib import Path
from typing import Dict
from urllib.request import url2pathname

import yaml

from eozilla_eoap.interfaces.registry import Registry

from .eoap_process import EoapProcess


class LocalEaopRegistry(Mapping[str, EoapProcess], Registry):
    def __init__(self, path: Path):
        self.path: Path = Path(path)
        self.registry_mapping: Path = Path(path, "process-mapping.csv")
        self._eoaps: Dict[str, EoapProcess] = {}

    def __iter__(self):
        return iter(self._eoaps)

    def __getitem__(self, name: str) -> EoapProcess:
        return self._eoaps[name]

    def __len__(self) -> int:
        return len(self._eoaps)

    def configure(self) -> None:
        if not self.path.exists():
            self.path.mkdir(parents=True, exist_ok=True)

        if not self.registry_mapping.exists():
            with open(self.registry_mapping, "wt") as f:
                writer = DictWriter(f, fieldnames=["process-id", "process-path"])
                writer.writeheader()

        if not self._eoaps:
            self._rebuild_internal_mapping()

        return

    def create(
        self, contents: dict, entrypoint: str, ignore_existing: bool = False
    ) -> EoapProcess:
        new_eoap: EoapProcess = EoapProcess.create(self.path, contents, entrypoint)

        # after EoapProcess.create, id and entrypoint are identical
        # but using the id field seems a bit clearer
        cwl_path: Path = Path(url2pathname(new_eoap.source, require_scheme=True))

        # assume that all processes stored as files are also present in the internal mapping
        exisiting_process: EoapProcess = self._eoaps.get(new_eoap.description.id)
        process_exists: bool = exisiting_process is not None

        if process_exists and not exisiting_process.description.mutable:
            raise RuntimeError(f"{new_eoap.description.id} is immutable")
        if process_exists and not ignore_existing:
            raise KeyError(
                f"{new_eoap.description.id} already references an exisiting EOAP in the registry."
            )

        self._eoaps[new_eoap.description.id] = new_eoap

        with open(cwl_path, "wt") as cwl_document:
            yaml.safe_dump(contents, cwl_document)

        with open(self.registry_mapping, "a+t") as f:
            writer = DictWriter(f, fieldnames=["process-id", "process-path"])
            writer.writerow(
                {"process-id": new_eoap.description.id, "process-path": cwl_path}
            )

        return new_eoap

    def read(self, name: str) -> EoapProcess:
        return self._eoaps[name]

    def read_all(self) -> Dict[str, EoapProcess]:
        return self._eoaps

    def update(self, contents: dict, entrypoint: str) -> EoapProcess:
        return self.create(
            contents=contents, entrypoint=entrypoint, ignore_existing=True
        )

    def delete(self, name: str) -> None:
        cwl_path: Path = self.path / Path(name + ".cwl")

        if not cwl_path.exists() or name not in self._eoaps:
            raise KeyError(
                f"{cwl_path} does not reference an existing EOAP that can be deleted."
            )

        cwl_path.unlink()

        with open(self.registry_mapping, "r+t") as f:
            rows = list(DictReader(f))
            rows = [row for row in rows if row["process-id"] != name]

            f.seek(0)

            writer = DictWriter(f, fieldnames=["process-id", "process-path"])
            writer.writeheader()
            writer.writerows(rows)

            f.truncate()

        del self._eoaps[name]

        return

    def _rebuild_internal_mapping(self) -> None:
        """Rebuid internal _eoaps dictionary from persistent registry entries.

        In essence this translates to reading in CWL files and re-constructing
        a mapping of names to OGC Processes. In doing so, it's assumed that
        all present EOAPs were validated beforehand, either by being accepted
        by the server or because the service provided validated them.
        """
        with open(self.registry_mapping, "rt") as csvfile:
            reader = DictReader(csvfile)
            for row in reader:
                with open(row["process-path"], "rt") as f:
                    cwl = yaml.safe_load(f)

                eoap: EoapProcess = EoapProcess.create(
                    self.path, cwl, entrypoint=row["process-id"]
                )

                self._eoaps[eoap.description.id] = eoap

        return
