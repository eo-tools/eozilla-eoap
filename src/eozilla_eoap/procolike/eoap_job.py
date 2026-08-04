#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# TODO: An abstraction of the executor would be nice as well but maybe this is better suited to be used in `eoap_service.py`? At least in the
#       real eozilla repo, this is where the job is acually submitted and I agree that submission of a job shouldn't really be the responsibility
#       of the job to submit itself to another entity

import datetime
import inspect
import traceback
import uuid
import warnings
from abc import ABC, abstractmethod
from concurrent.futures import Future
from typing import Any, Optional

import pydantic
from gavicore.models import (
    JobInfo,
    JobResults,
    JobStatus,
    ProcessRequest,
    Subscriber,
)
from procodile.reporter import CallbackReporter

from eozilla_eoap.interfaces.runner import Runner

from .eoap_artifact_manager import LocalArtifactManager
from .eoap_process import EoapProcess


class JobCancelledException(Exception):
    """Raised if a job's cancellation has been requested."""


class JobContext(ABC):
    """
    Report process progress and check for task cancellation.

    A process function can retrieve the current job context

    1. via [JobContext.get()][procolike.JobContext.get] from
       within a process function, or
    2. as a function argument of type [JobContext][procolike.JobContext].
    """

    @classmethod
    def get(cls) -> "JobContext":
        """
        Get the current job context.

        Returns the current job context that can be used by
        process functions to report job progress in percent
        or via messages and to check whether cancellation
        has been requested.
        This function is intended to be called from within
        a process function executed as a job. If called as a usual
        Python function (without a job serving as context), the
        returned context will have no-op methods only.

        Returns:
            An instance of the current job context.
        """
        frame = inspect.currentframe()
        try:
            while frame:
                job_context = frame.f_locals.get("__job_context__")
                if isinstance(job_context, JobContext):
                    return job_context
                frame = frame.f_back
        finally:
            # Always free alive frame-references
            del frame
        # noinspection PyUnreachableCode
        warnings.warn(
            "cannot determine current job context; using non-functional dummy",
            stacklevel=2,
        )
        return NullJobContext()

    @abstractmethod
    def report_progress(
        self,
        progress: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        """Report task progress.

        Args:
            progress: Progress in percent.
            message: Detail progress message.

        Raises:
            JobCancellationException: if an attempt has been made
                to cancel this job.
        """

    @abstractmethod
    def is_cancelled(self) -> bool:
        """Test whether an attempt has been made to cancel this job.
        It may still be running though.

        Returns:
            `True` if so, `False` otherwise.
        """

    @abstractmethod
    def check_cancelled(self) -> None:
        """Raise a `JobCancellationException`, if
        an attempt has been made to cancel this job.
        """


class Job(JobContext):
    # TODO: I would say the job still belongs to the "platform", thus the job context
    #       would be appropriate to be responsible for stage-in and stage-out of data
    #       even though this isn't really needed in my case
    """
    Represents an execution of a CWL.

    Args:
        process: The process that created this job.
        job_id: A job identifier.
        eoap_args: The user CWL's keyword arguments.
            A keyword must be a valid Python identifier or a
            sequence of Python identifiers separated by the dot
            (`.`) character.
        subscriber: Optional subscriber URIs.
    """

    @classmethod
    def create(
        cls,
        process: EoapProcess,
        request: ProcessRequest,
        cwl_runner: Runner,
        job_id: str,
        persistency_directory: Path,
    ) -> "Job":
        """
        Create a new job for the given process and process request.

        Args:
            process: The process.
            request: The process request.
                Names of request inputs must be valid Python identifiers or
                sequences of Python identifiers separated by the dot
                (`.`) character. The latter is used to set nested input objects.
            job_id: Optional job identifier.
                If omitted, a unique identifier will be generated (UUID4).


        Returns:
            A new job instance.

        Raises:
            pydantic.ValidationError: if an input value is not valid
                with respect to its process input description.
        """

        input_params = request.inputs or {}

        model_instance: pydantic.BaseModel = process.model_class.model_validate(
            input_params, extra="forbid"
        )

        eoap_args = model_instance.model_dump(
            mode="python", exclude_unset=False, exclude_none=True
        )

        artifact_manager: LocalArtifactManager = LocalArtifactManager(
            persistency_directory, job_id, model_instance
        )

        return Job(
            process=process,
            job_id=job_id,
            eoap_args=eoap_args,
            cwl_runner=cwl_runner,
            subscriber=request.subscriber,
            artifact_manager=artifact_manager,
        )

    def __init__(
        self,
        *,
        process: EoapProcess,
        job_id: str,
        eoap_args: dict[str, Any],
        cwl_runner: Runner,
        subscriber: Optional[Subscriber] = None,
        artifact_manager: Optional[LocalArtifactmanager] = None,
    ):
        """Internal constructor.
        Use `Job.create() instead.`
        """
        self.process = process
        # noinspection PyTypeChecker
        self.job_info = JobInfo(  # noqa [call-arg]
            jobID=job_id,
            processID=process.description.id,
            status=JobStatus.accepted,
            created=self._now(),
        )
        self.eoap_args = eoap_args
        self.cancelled = False
        self.future: Optional[Future] = None
        self.subscriber = subscriber
        self._reporter: CallbackReporter | None = None
        self.cwl_runner = cwl_runner
        self.artifact_manager = artifact_manager

    @property
    def reporter(self) -> CallbackReporter:
        if self._reporter is None:
            self._reporter = CallbackReporter()
        return self._reporter

    def report_progress(
        self, progress: Optional[int] = None, message: Optional[str] = None
    ):
        self.check_cancelled()
        # noinspection PyTypeChecker
        self.job_info.updated = self._now()
        if progress is not None:
            self.job_info.progress = progress
        if message is not None:
            self.job_info.message = message
        self._maybe_notify_in_progress()

    def is_cancelled(self) -> bool:
        return self.cancelled

    def check_cancelled(self):
        if self.cancelled:
            raise JobCancelledException

    def cancel(self):
        """Request job cancellation.
        Note, actual cancellation will happen
        only from within the user function.
        """
        self.cancelled = True

    def run(self) -> JobResults | None:
        """Run this job."""

        # Make the job (context) findable by get_job_context()
        # through the local variable __job_context__
        ctx = __job_context__ = self  # noqa: F841

        function_kwargs: dict[str, Any] = dict(getattr(self, "function_kwargs", {}))

        # use "inputs arg", if needed
        inputs_arg = getattr(self.process, "inputs_arg", None)
        if inputs_arg:
            function_kwargs.pop(inputs_arg, None)
            function_kwargs = {inputs_arg: self.process.model_class(**function_kwargs)}

        # inject job context, if needed
        ctx_arg = getattr(self.process, "job_ctx_arg", None)
        if ctx_arg:
            function_kwargs.pop(ctx_arg, None)
            function_kwargs = {ctx_arg: ctx, **function_kwargs}

        self._start_job()
        try:
            self.artifact_manager.initialize()
            self.artifact_manager.stage_in()
            self.eoap_args = self.artifact_manager.rebuild_process_arguments()
            self.check_cancelled()
            # TODO: Is it possible/desirable to dispatch run method (self.cwl_runner.run)
            #       on Process vs. EoapProcess? Could possibly allow multiple "things"
            #       to co-exist
            results = self.cwl_runner.run(
                self.job_info.jobID,
                context=ctx,
                process=self.process,
                process_arguments=self.eoap_args,
                persistent_output_directory=self.artifact_manager.persistent_output_directory,
            )
            self._finish_job(JobStatus.successful)
            # TODO: Similarly to the LocalEOAPService method `get_job_results`,
            #       this would be responsible for stage-out/directory creation.
            #       It doesn't seem like I need a new model; JobResults should be generic
            #       enough.
            #       Same as with the OGC Process: This is only a representation of the
            #       outputs as far as I'm concerned as the actual output lives on disk.
            # Maybe not alternatively but additionally: Can the process results
            #       be modeled via the pydantic class describing the output? Not sure on
            #       that one...
            job_results = self._get_job_results(results)
            self._maybe_notify_success(job_results)
            return job_results
        except JobCancelledException:
            self._finish_job(JobStatus.dismissed)
            self._maybe_notify_failed()
        except Exception as e:
            self._finish_job(JobStatus.failed, exception=e)
            self._maybe_notify_failed()
        finally:
            self.artifact_manager.remove_staged_inputs()
        return None

    def _get_job_results(self, function_result: Any) -> JobResults:
        assert self.job_info.status == JobStatus.successful
        assert self.job_info.processID is not None

        # Outputs are already validated and normalized by
        # `ExecutionContext.normalize_outputs()`.
        if isinstance(function_result, dict):
            return JobResults(**function_result)

        outputs = self.process.description.outputs or {}
        output_count = len(outputs)
        return JobResults(
            **{
                output_name: (
                    function_result if output_count == 1 else function_result[i]
                )
                for i, output_name in enumerate(outputs.keys())
            }
        )

    def _start_job(self):
        # noinspection PyTypeChecker
        self.job_info.started = self._now()
        self.job_info.status = JobStatus.running

    def _finish_job(self, job_status: JobStatus, exception: Optional[Exception] = None):
        # noinspection PyTypeChecker
        self.job_info.finished = self._now()
        self.job_info.status = job_status
        if exception is not None:
            self.job_info.message = f"{exception}"
            self.job_info.traceback = traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )

    def _maybe_notify_success(self, job_results: JobResults):
        if self.subscriber is not None and self.subscriber.successUri is not None:
            url = str(self.subscriber.successUri)
            data = job_results.model_dump(mode="json", by_alias=True)
            self.reporter.report(url, data)

    def _maybe_notify_failed(self):
        if self.subscriber is not None:
            self._maybe_notify_current_job_info(self.subscriber.failedUri)

    def _maybe_notify_in_progress(self):
        if self.subscriber is not None:
            self._maybe_notify_current_job_info(self.subscriber.inProgressUri)

    def _maybe_notify_current_job_info(self, url: pydantic.AnyUrl | None):
        if url is not None:
            data = self.job_info.model_dump(
                mode="json",
                by_alias=True,
                exclude_none=True,
                exclude_unset=True,
            )
            self.reporter.report(str(url), data)

    @staticmethod
    def _now() -> datetime.datetime:
        # noinspection PyTypeChecker
        return datetime.datetime.now(tz=datetime.timezone.utc)


class NullJobContext(JobContext):
    """A job context used if a real one could not be provided."""

    def report_progress(
        self, progress: Optional[int] = None, message: Optional[str] = None
    ) -> None:
        """Does nothing."""

    def is_cancelled(self) -> bool:
        """Returns `False`."""
        return False

    def check_cancelled(self) -> None:
        """Does nothing."""
