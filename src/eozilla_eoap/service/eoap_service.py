import json
import multiprocessing
import os
from concurrent.futures import CancelledError, Future, wait
from concurrent.futures.process import ProcessPoolExecutor
from concurrent.futures.thread import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import url2pathname
from uuid import uuid4

import fastapi
import yaml
from fastapi import Request, Response
from gavicore.dru_models import (
    CwlDescription,
    OgcApplicationPackage,
    OgcApplicationPackageProcessDescription,
)
from gavicore.dru_service import DruService
from gavicore.models import (
    JobInfo,
    JobList,
    JobResult,
    JobResults,
    JobStatus,
    ProcessDescription,
    ProcessList,
    ProcessRequest,
    ProcessSummary,
)
from gavicore.util.dynimp import import_value
from pydantic import ValidationError
from wraptile.exceptions import ServiceException
from wraptile.services.base import ServiceBase

from eozilla_eoap.interfaces.registry import Registry
from eozilla_eoap.interfaces.runner import Runner
from eozilla_eoap.procolike import (
    EntrypointNotFoundError,
    EoapProcess,
    NamespaceNotFoundError,
)
from eozilla_eoap.procolike.eoap_job import Job

from .eoap_acceptance import load_and_validate_from_body


class LocalEoapService(ServiceBase, DruService):
    SUPPORTED_MEDIA_TYPES: List[str] = [
        "application/cwl",
        "application/cwl+json",
        "application/cwl+yaml",
    ]

    def __init__(
        self,
        title: str,
        cwl_runner: Runner,
        persitency_directory: Path,
        description: Optional[str] = None,
        conforms_to: Optional[List[str]] = None,
        process_registry: Optional[Registry] = None,
    ):
        super().__init__(title=title, description=description, conforms_to=conforms_to)
        # TODO: Doesn't the executor become more of a "submitter" in my case?
        self.executor: Optional[ThreadPoolExecutor | ProcessPoolExecutor] = None
        self.cwl_runner: Runner = cwl_runner
        self.persitency_directory: Path = persitency_directory

        self.process_registry: Optional[Registry] = process_registry
        # (
        #     process_registry or LocalEaopRegistry(mkdtemp(), False)
        # )
        self.jobs: Dict[str, Job] = {}
        self.job_results: Dict[str, JobResult | None] = {}
        self.job_uses_processes: dict[str, bool] = {}
        self._executor_uses_processes = False
        self._executor_max_workers = 3
        self._executor_pid: int | None = None

    def configure(
        self, processes: Optional[bool] = None, max_workers: Optional[int] = None
    ):
        """Configure the local DRU/EOAP Service

        Args:
            processes: Whether to use processes instead of threads. Defaults to threads.
            max_workers: The maximum number of processes or threads. Defaults to 3.
        """
        self.process_registry.configure()

        num_workers: int = max_workers or 3
        use_processes = bool(processes)
        if self.executor is not None and self._executor_pid == os.getpid():
            self.executor.shutdown(wait=False, cancel_futures=True)
        self._executor_uses_processes = use_processes
        self._executor_max_workers = num_workers
        self._executor_pid = os.getpid()
        if use_processes:
            self.executor = ProcessPoolExecutor(
                max_workers=num_workers,
                mp_context=multiprocessing.get_context("spawn"),
            )
            self.logger.info(f"Using processes with max {num_workers} workers.")
        else:
            self.executor = ThreadPoolExecutor(max_workers=num_workers)
            self.logger.info(f"Using threads with max {num_workers} workers.")
        return

    async def get_processes(self, request: Request, **_kwargs) -> ProcessList:
        return ProcessList(
            processes=[
                ProcessSummary(
                    **p.description.model_dump(
                        mode="python", exclude={"inputs", "outputs"}
                    )
                )
                for p in self.process_registry.values()
            ],
            links=[self.get_self_link(request, "get_processes")],
        )

    async def get_process(self, process_id: str, *args, **kwargs) -> ProcessDescription:
        process: EoapProcess = self._get_process(process_id)

        if not process:
            raise ServiceException(404, detail=f"Job {process_id!r} does not exist")

        return process.description

    async def execute_process(
        self, process_id: str, process_request: ProcessRequest, *args, **kwargs
    ) -> JobInfo:
        eoap: EoapProcess = self._get_process(process_id)
        job_id: str = str(uuid4())

        try:
            job = Job.create(
                eoap,
                process_request,
                cwl_runner=self.cwl_runner,
                job_id=job_id,
                persistency_directory=self.persitency_directory,
            )
        except ValidationError as e:
            raise ServiceException(
                400,
                detail=f"Invalid parameterization for process {process_id!r}: {e}",
                exception=e,
            ) from e
        executor = self._ensure_executor()
        use_processes = isinstance(executor, ProcessPoolExecutor)
        if use_processes:
            if self.service_ref is None:
                raise ServiceException(
                    500,
                    detail=(
                        "Local process execution requires the service to be "
                        "loaded from an import reference."
                    ),
                )
        self.jobs[job_id] = job
        self.job_uses_processes[job_id] = use_processes
        if use_processes:
            assert self.service_ref is not None
            job.future = executor.submit(
                _run_imported_job,
                self.service_ref,
                process_id,
                process_request,
                self.cwl_runner,
                job_id,
            )
        else:
            job.future = executor.submit(job.run)

        job.future.add_done_callback(
            lambda future: self._update_job_from_future(
                job_id,
                future,
                use_processes=use_processes,
            )
        )

        return job.job_info

    async def get_jobs(self, request: fastapi.Request, **_kwargs) -> JobList:
        return JobList(
            jobs=[job.job_info for job in self.jobs.values()],
            links=[self.get_self_link(request, "get_jobs")],
        )

    async def get_job(self, job_id: str, *args, **kwargs) -> JobInfo:
        job = self._get_job(job_id, forbidden_status_codes={})
        return job.job_info

    async def dismiss_job(self, job_id: str, *args, **kwargs) -> JobInfo:
        # TODO: same question as in the original eozilla repository:
        #       how to correctly dismiss a (running) job and how to wait
        #       for its termination?!
        job = self._get_job(job_id, forbidden_status_codes={})
        if job.job_info.status in (JobStatus.accepted, JobStatus.running):
            job.cancel()
            if job.future is not None:
                job.future.cancel()
                _, not_done = wait([job.future])
                if not_done:
                    raise ServiceException(
                        status_code=500,
                        detail=f"Dismissal of {job_id} encountered an unexpected error.",
                    )
        elif job.job_info.status in (
            JobStatus.dismissed,
            JobStatus.successful,
            JobStatus.failed,
        ):
            del self.jobs[job_id].artifact_manager
            del self.jobs[job_id]
            self.job_results.pop(job_id, None)
            self.job_uses_processes.pop(job_id, None)
        return job.job_info

    async def get_job_results(self, job_id: str, *args, **kwargs) -> JobResults:
        job = self._get_job(
            job_id,
            forbidden_status_codes={
                JobStatus.accepted: "has not started yet",
                JobStatus.running: "is still running",
                JobStatus.dismissed: "has been cancelled",
                JobStatus.failed: "has failed",
            },
        )
        assert job.job_info.status == JobStatus.successful
        assert job.future is not None
        if job_id not in self.job_results:
            self.job_results[job_id] = self._get_job_result_from_future(
                job,
                job.future,
                use_processes=self.job_uses_processes.get(job_id, False),
            )
        job_results = self.job_results[job_id]
        assert job_results is not None
        return job_results

    async def deploy_process(
        self,
        request: Request,
        response: Response,
        w: str | None = None,
    ) -> Optional[ProcessSummary]:
        if request.headers.get("Content-Type") not in self.SUPPORTED_MEDIA_TYPES:
            raise ServiceException(
                status_code=415,
                # type="https://www.opengis.net/def/exceptions/ogcapi-processes-2/1.0/unsupported-media-type",
                detail=f"Unsupported media types. Accepting EOAPs as {', '.join(self.SUPPORTED_MEDIA_TYPES)}.",
            )

        eoap: dict = await load_and_validate_from_body(request, w=w)

        try:
            process: EoapProcess = self.process_registry.create(
                eoap, entrypoint=w, ignore_existing=False
            )
        except RuntimeError as e:
            raise ServiceException(
                status_code=403,
                type="https://www.opengis.net/def/exceptions/ogcapi-processes-2/1.0/immutable-process",
                detail=e.args,
            ) from e
        except KeyError:
            raise ServiceException(
                status_code=409,
                # type="https://www.opengis.net/def/exceptions/ogcapi-processes-2/1.0/duplicated-process",
                detail="Submitted process id already exists in registry.",
            ) from None
        except EntrypointNotFoundError:
            raise ServiceException(
                status_code=400,
                # type="https://www.opengis.net/def/exceptions/ogcapi-processes-2/1.0/workflow-not-found",
                detail=f"Workflow entrypoint {w} not found",
            ) from None
        except NamespaceNotFoundError:
            raise ServiceException(
                status_code=422,
                detail="Mailformed CWL document.",
            ) from None

        response.headers["location"] = f"/processes/{process.description.id}"

        return ProcessSummary(
            id=process.description.id,
            version=process.description.version,
            mutable=process.description.mutable,
            links=[self.get_self_link(request, "deploy_process")],
        )

    async def replace_process(
        self,
        process_id: str,
        request: Request,
        response: Response,
        w: str | None = None,
    ) -> Optional[ProcessSummary]:
        if request.headers.get("Content-Type") not in self.SUPPORTED_MEDIA_TYPES:
            raise ServiceException(
                status_code=415,
                type="https://www.opengis.net/def/exceptions/ogcapi-processes-2/1.0/unsupported-media-type",
                detail=f"Unsupported media types. Accepting EOAPs as {', '.join(self.SUPPORTED_MEDIA_TYPES)}.",
            )

        eoap: dict = await load_and_validate_from_body(request, w=w)

        try:
            process: EoapProcess = self.process_registry.update(
                eoap, entrypoint=w or process_id
            )
        except RuntimeError as e:
            raise ServiceException(
                status_code=403,
                type="https://www.opengis.net/def/exceptions/ogcapi-processes-2/1.0/immutable-process",
                detail=e.args,
            ) from e
        except EntrypointNotFoundError:
            raise ServiceException(
                status_code=400,
                # type="https://www.opengis.net/def/exceptions/ogcapi-processes-2/1.0/workflow-not-found",
                detail=f"Workflow entrypoint {w} not found",
            ) from None
        except NamespaceNotFoundError:
            raise ServiceException(
                status_code=422,
                detail="Mailformed CWL document.",
            ) from None

        response.headers["location"] = f"/processes/{process.description.id}"

        return ProcessSummary(
            id=process.description.id,
            version=process.description.version,
            mutable=process.description.mutable,
            links=[
                self.get_self_link(
                    request, "replace_process", processId=process_id, w=w
                )
            ],
        )

    async def undeploy_process(
        self,
        process_id: str,
        request: Request,
        response: Response,
    ) -> None:
        # NOTE: Mutability is checked in internal method
        eoap: EoapProcess = self._get_process(process_id)

        self.process_registry.delete(eoap.description.id)

        return

    async def get_formal_description(
        self,
        process_id: str,
        request: Request,
        response: Response,
    ) -> OgcApplicationPackage:
        # NOTE: Mutability is checked in internal method
        eoap: EoapProcess = self._get_process(process_id)

        with open(url2pathname(eoap.source, require_scheme=True), "rt") as f:
            cwl = yaml.safe_load(f)

        return OgcApplicationPackage(
            processDescription=OgcApplicationPackageProcessDescription(
                process=eoap.description
            ),
            executionUnit=CwlDescription(
                mediaType="application/cwl", value=json.dumps(cwl, indent=2)
            ),
        )

    def _ensure_executor(self) -> ThreadPoolExecutor | ProcessPoolExecutor:
        if self.executor is None:
            self.configure(
                processes=self._executor_uses_processes,
                max_workers=self._executor_max_workers,
            )
        elif self._executor_pid != os.getpid():
            self.logger.warning("Recreating local executor after process fork.")
            self.executor = None
            self.configure(
                processes=self._executor_uses_processes,
                max_workers=self._executor_max_workers,
            )
        assert self.executor is not None, "illegal state: no executor specified"
        return self.executor

    def _update_job_from_future(
        self,
        job_id: str,
        future: Future,
        *,
        use_processes: bool,
    ):
        job = self.jobs.get(job_id)
        if job is None:
            return
        try:
            self.job_results[job_id] = self._get_job_result_from_future(
                job, future, use_processes=use_processes
            )
        except CancelledError:
            if job.job_info.status in (JobStatus.accepted, JobStatus.running):
                job._finish_job(JobStatus.dismissed)
        except Exception as e:
            self.logger.exception(f"Execution of job {job_id!r} failed.")
            if job.job_info.status in (JobStatus.accepted, JobStatus.running):
                job._finish_job(JobStatus.failed, exception=e)

    @staticmethod
    def _get_job_result_from_future(
        job: Job,
        future: Future,
        *,
        use_processes: bool,
    ) -> JobResults | None:
        future_result = future.result()
        if use_processes:
            job_info, job_results = future_result
            job.job_info = job_info
            return job_results
        return future_result

    def _get_process(self, process_id: str) -> EoapProcess:
        try:
            process = self.process_registry.read(process_id)
        except KeyError:
            raise ServiceException(404, detail=f"Process {process_id!r} does not exist") from None
        else:
            if not process.description.mutable:
                raise ServiceException(
                    403,
                    type="https://www.opengis.net/def/exceptions/ogcapi-processes-2/1.0/immutable-process",
                    detail=f"Process {process_id!r} is immutable",
                ) from None
        return process

    def _get_job(
        self, job_id: str, forbidden_status_codes: dict[JobStatus, str]
    ) -> Job:

        job = self.jobs.get(job_id)
        if job is None:
            raise ServiceException(404, detail=f"Job {job_id!r} does not exist")
        message = forbidden_status_codes.get(job.job_info.status)
        if message:
            raise ServiceException(403, detail=f"Job {job_id!r} {message}")
        return job


def _run_imported_job(
    service_ref: str,
    process_id: str,
    process_request: ProcessRequest,
    backend: Runner,
    job_id: str,
) -> tuple[JobInfo, JobResults | None]:
    service = import_value(
        service_ref,
        type=LocalEoapService,
        name="service",
        example="path.to.module:service",
    )
    service.process_registry.configure()
    process = service.process_registry._eoaps.get(process_id)
    if process is None:
        raise RuntimeError(f"Process {process_id!r} does not exist")
    job = Job.create(process, process_request, backend, job_id=job_id, persistency_directory=service.persitency_directory)
    job_results = job.run()
    return job.job_info, job_results
