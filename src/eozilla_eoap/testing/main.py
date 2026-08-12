from pathlib import Path

from eozilla_eoap.cwltool.runner import CwlToolRunner
from eozilla_eoap.procolike.local_eoap_registry import LocalEaopRegistry
from eozilla_eoap.service import LocalEoapService

SERVICE_BASE_DIR: Path = Path(__file__).parent.absolute()

service = LocalEoapService(
    title="Eozilla DRU API Server",
    description="Local DRU server implementing the OGC API - Processes Part 2.0 Draft standard, adhering to the EOAP BP guide",
    process_registry=LocalEaopRegistry(
        Path(SERVICE_BASE_DIR, "eoap-service", "registry")
    ),
    cwl_runner=CwlToolRunner(),
    persitency_directory=Path(SERVICE_BASE_DIR, "eoap-service", "runs"),
)
