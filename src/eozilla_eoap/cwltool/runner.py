import logging
import threading
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from cwl_utils.types import CWLObjectType
from cwltool.context import RuntimeContext
from cwltool.errors import WorkflowException
from cwltool.executors import SingleJobExecutor
from cwltool.factory import Factory, Callable as CwlCallable
from cwltool.process import Process
from cwltool.utils import JobsGeneratorType, JobsType, OutputCallbackType
from procodile.job import JobCancelledException, NullJobContext

from eozilla_eoap.interfaces import Runner
from eozilla_eoap.procolike import (
    EoapProcess,
    Job,
)


class CwltoolLogger:
    """Manipulate cwltool's logger to log to File

    Store logs from CWL execution to a file for examination.
    The class implements the context manager interface and
    is not expected to be used standalone.

    Notes:
        All other handler previously contained by cwltools's
        logger are removed.
    """

    def __init__(self, filename: str):
        self.handler = logging.FileHandler(filename)

    def __enter__(self):
        logger = logging.getLogger("cwltool")

        logger.propagate = False
        for h in logging.getLogger("cwltool").handlers:
            logger.removeHandler(h)
            h.close()

        logger.addHandler(self.handler)
        return logger

    def __exit__(self, *args):
        logger = logging.getLogger("cwltool")
        logger.removeHandler(self.handler)
        self.handler.close()


class CallbackExecutor(SingleJobExecutor):
    """A CWL Executor with Callback Injected Between job Steps

    The CallbackExecutor extends the [`SingleJobExecutor`](cwltool.executors.SingleJobExecutor)
    such that before and after each job step (e.g. execution of a command line tool), a
    [`JobContext`](eozilla_eoap.procolile.eoap_job.Jobcontext) is checked for a cancellation condition. If no
    [`JobContext`](eozilla_eoap.procolile.eoap_job.Jobcontext) is specified a default
    `NullJobContext` is used.
    """

    def __init__(self, context: Optional[Job] = None) -> None:
        self.context: Job | NullJobContext = (
            NullJobContext() if not context else context
        )
        super().__init__()

    def __call__(
        self,
        process: Process,
        job_order_object: CWLObjectType,
        runtime_context: RuntimeContext,
    ) -> tuple[CWLObjectType | None, str]:
        """Custom Call Implementation for Executor

        The goal is to register a callback that is executed after each job (-step).
        The `self.process.job` method returns an iterator over all job (-steps) that
        need to be executed for a successful workflow/command line tool execution.

        By intercepting the *base call*, we can wrap/alter the generator
        responsible for producing job steps. The __call__ method returns the result of
        the `execute` method which does some additional pre-processing before executing
        job (-steps) and finalizing outputs.

        To do so it's necessary to wrap the process.job object (that returns an
        iterator) such, that each generated job object is wrapped by `_wrap_run`.

        Args:
            process (Process): Generator container for new jobs
            job_order_object (CWLObjectType): Resolved job orders
            runtime_context (RuntimeContext): Runtime context for execution

        Returns:
            tuple[CWLObjectType | None, str]: Result from base/super class implementation

        Yields:
            JobsGeneratorType: Next job item to execue
        """
        # original_job is a bound method,
        # i.e. storing a pointer to the original process.job
        original_job = process.job

        def job(
            job_order: CWLObjectType,
            output_callbacks: OutputCallbackType,
            runtimeContext: RuntimeContext,
        ) -> JobsGeneratorType:
            """Job Generator

            This function wraps the original/default job generator, yielding
            the original job object wrapped in a custom `_wrap_run` function.

            Notes:
                This method is called for all instances of a "job" which are
                not exclusive to command line jobs; thus it may preferable,
                if the overwritten `run` method does not raise immediate errors
                or have side-effects on the first invocation.

            Args:
                job_order (CWLObjectType): Resolved job orders.
                output_callbacks (OutputCallbackType): Callback executed on job return.
                runtimeContext (RuntimeContext): Runtime context for execution.

            Yields:
                Iterator[JobsGeneratorType]: Next job step.
            """
            for job in original_job(job_order, output_callbacks, runtimeContext):
                self._wrap_run(job)  # mutating object inside + passing by reference
                # re-yield result
                yield job

        # within the stack frame(?) of the newly registered `wrapped_job` function, we still
        # have access to the original process.job object because of Python's lexcial scoping
        # rules
        process.job = job

        return super().__call__(
            process,
            job_order_object,
            runtime_context,
        )

    def _wrap_run(self, job: JobsType):
        # bound method, i.e. storing a pointer to the original process.job
        original = job.run

        def run(
            runtime_context: RuntimeContext,
            tmpdir_lock: Union[threading.Lock, None] = None,
        ) -> None:
            """Custom Thin wrapper around the run method of CWL job by shadowing
            original method look-up (through setting an attribute with the same name)

            The Executor builds the runtime context which is then passed
            to the run method.
            Here, `original` refers to the original (super class) method.

            Args:
                runtime_context (RuntiWormeContext): Runtime context for a single job (-step)
                    execution.
                tmpdir_lock (Union[threading.Lock, None]): Lock to serialize access
                    to local temporary directory.
            """
            self.context.check_cancelled()
            # call non-local, original, run method
            return original(runtime_context, tmpdir_lock)

        # overwrite *public* run method called by Exectuor
        # within the stack frame(?) of the newly registered `wrapped_job` function, we still
        # have access to the original process.job object because of Python's lexcial scoping
        # rules
        job.run = run


class CwlToolRunner(Runner):
    """Implementation of the interfaces mandated by [`Runner`][eozilla_eoap.interfaces.Runner]."""

    def run(
        self,
        job_id: str,
        *,
        process: EoapProcess,
        process_arguments: Dict[str, Any],
        # only passing in a temporary directory decouples the CWL implementation
        # from other parts of the software
        temporary_output_directory: Path,
        context: Optional[Job] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Dispatch a execution request to cwltool.

        The `run` method is responsible for various steps necessary before
        actual execution of a process can occurr:

        - Paths under which to store generated logs and outputs are set up,
          though not created as the Runner is not responsible for *external*
          data management.
        - cwltool's runtime context is prepared.
        - The workflow implementation and the corresponding entrypoint are
          loaded from a CWL document.
        - The workflow is executed locally and its results are passed up to
          the calling context.

        Args:
            job_id (str): Unique job Id (currently unused).
            process (EoapProcess): In-memory representation of an OGC
                Process that can be used to access the source and entrypoint
                of a CWL file.
            process_arguments (Dict[str, Any]): Validated user-supplied
                arguments for the process. Note, that any staging of data
                must already been applied before passing the execution request
                to this runner.
            temporary_output_directory (Path): Absolute file path to a directory
                where logs and outputs are stored. Note, that from cwltool's
                perspective, this might as well be a persistent/final
                output directory.
            context (Optional[Job], optional): Optional job context used to check
                for cancellation requests between job steps. Defaults to None.

        Raises:
            JobCancelledException: The user requested early cancellation of the
                process. Only raised when the `context` argument is non-null.
            Exception: Raised in case of general execution exceptions.

        Returns:
            Dict[str, Any]: Workflow results to be passed back to caller.
        """
        # NOTE: The process arguments have already been validated when the owning job
        #       object was created
        out_dir: Path = Path(temporary_output_directory, "out")
        log_dir: Path = Path(temporary_output_directory, "log")

        context = context or NullJobContext()

        with (
            CwltoolLogger(str(Path(log_dir, "run.log"))),
            open(Path(log_dir, "stdout"), "wt") as proc_stdout,
            open(Path(log_dir, "stderr"), "wt") as proc_stderr,
            redirect_stdout(proc_stdout),
            redirect_stderr(proc_stderr),
        ):
            runtime_context: RuntimeContext = RuntimeContext(
                {
                    "outdir": str(out_dir),
                    # NOTE: Setting strict memory limit to false to allow processes to simply not specify resource
                    #       requirements and still function when using more than one Gb of RAM.
                    #       Relevant section in https://cwltool.readthedocs.io/_/downloads/en/stable/pdf/ is
                    #       on page 24
                    "strict_memory_limit": False,
                    "strict_cpu_limit": True,
                }
            )

            factory: Factory = Factory(
                executor=CallbackExecutor(context),
                runtime_context=runtime_context,
            )

            workflow: CwlCallable = factory.make(
                process.source + "#" + process.description.id
            )

            try:
                workflow_result: Any = workflow(**process_arguments)
            except WorkflowException as e:
                # cwltool wraps any unknown error into WorkflowException,
                # this is why I need to check the context explicitly
                if context.is_cancelled():
                    raise JobCancelledException from e
                else:
                    raise e
            except Exception as e:
                raise

        return workflow_result
