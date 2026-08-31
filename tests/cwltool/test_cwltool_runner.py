import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest import TestCase
from unittest.mock import Mock, mock_open, patch

from cwltool.errors import WorkflowException
from cwltool.executors import SingleJobExecutor
from procodile.job import JobCancelledException, NullJobContext

from eozilla_eoap.cwltool import CallbackExecutor, CwltoolLogger, CwlToolRunner
from eozilla_eoap.procolike.eoap_job import EoapProcess, Job


class CwlLoggerTest(TestCase):
    def test_logger_has_file_handle(self):
        with NamedTemporaryFile() as tf:
            lgr = CwltoolLogger(tf.name)
            self.assertIsInstance(lgr.handler, logging.FileHandler)

    def test_logger_has_only_file_handle(self):
        self.skipTest("pytest inserts its own log handler, so this test fails.")
        with NamedTemporaryFile() as tf, CwltoolLogger(tf.name) as lgr:
            self.assertEqual(len(lgr.handlers), 1)
            self.assertIsInstance(lgr.handlers[0], logging.FileHandler)

    def test_logger_logs_to_file(self):
        with (
            NamedTemporaryFile(mode="w+t") as tf,
            CwltoolLogger(tf.name) as lgr,
            self.assertLogs("cwltool") as cm,
        ):
            lgr.info("Interesting information")
            lgr.warning("Important warning")
            lgr.error("Threatening error")

        self.assertEqual(
            cm.output,
            [
                "INFO:cwltool:Interesting information",
                "WARNING:cwltool:Important warning",
                "ERROR:cwltool:Threatening error",
            ],
        )


class ExecutorTest(TestCase):
    @patch("eozilla_eoap.cwltool.runner.SingleJobExecutor", spec=SingleJobExecutor)
    def test_init_with_job_context(self, mocked_single_job_executor):
        context = Mock(spec=Job)

        executor = CallbackExecutor(context)

        self.assertIs(executor.context, context)

    @patch("eozilla_eoap.cwltool.runner.SingleJobExecutor", spec=SingleJobExecutor)
    def test_init_without_job_context(self, mocked_single_job_executor):
        executor = CallbackExecutor()

        self.assertIsInstance(executor.context, NullJobContext)

    # NOTE: This class probably warrants more tests but I'm lost on what
    #       to test and how to implement them; using mocked and patched
    #       objects will be necessary but I fear that this results in
    #       some form of "circular" testing where I "test" the behavior
    #       of mocks instead of the wrapper executor


ECHO_WORKFLOW_DEFINITION = {
    "$graph": [
        {
            "class": "Workflow",
            "cwlVersion": "v1.2",
            "label": "Echo User Input to File",
            "doc": "The echo EOAP is a simple process that simply echos the user's input to a files and returns it. By registering the accompanying CWL workflow, the process will be available at `/processes/echo-workflow`.",
            "id": "echo-workflow",
            "inputs": {
                "message": {
                    "label": "message to echo",
                    "doc": "some very length description of what this argument does",
                    "type": "string",
                    "default": "Hello World",
                }
            },
            "outputs": {
                "hello_out": {"outputSource": "echo/hello_out", "type": "File"}
            },
            "steps": {
                "echo": {
                    "in": {"message": "message"},
                    "out": ["hello_out"],
                    "run": "#echo-tool",
                }
            },
        },
        {
            "baseCommand": ["echo"],
            "class": "CommandLineTool",
            "id": "#echo-tool",
            "inputs": {"message": {"inputBinding": {"position": 1}, "type": "string"}},
            "label": "Echo Tool",
            "outputs": {
                "hello_out": {"outputBinding": {"glob": "hello.txt"}, "type": "File"}
            },
            "requirements": {"DockerRequirement": {"dockerPull": "alpine:3.22"}},
            "stdout": "hello.txt",
        },
    ],
    "$namespaces": {"s": "https://schema.org/"},
    "cwlVersion": "v1.2",
    "s:version": "0.0.1",
}


class RunnerTest(TestCase):
    def setUp(self):
        factory_patcher = patch("eozilla_eoap.cwltool.runner.Factory", autospec=True)
        self.addCleanup(factory_patcher.stop)
        self.mock_factory_class = factory_patcher.start()
        self.mock_factory = self.mock_factory_class.return_value

        callback_executor_patcher = patch(
            "eozilla_eoap.cwltool.runner.CallbackExecutor", autospec=True
        )
        self.addCleanup(callback_executor_patcher.stop)
        self.mock_callback_executor_class = callback_executor_patcher.start()
        self.mock_callback_executor = self.mock_callback_executor_class.return_value

        runtime_context_patcher = patch(
            "eozilla_eoap.cwltool.runner.RuntimeContext", autospec=True
        )
        self.addCleanup(runtime_context_patcher.stop)
        self.mock_runtime_context_class = runtime_context_patcher.start()
        self.mock_runtime_context = self.mock_runtime_context_class.return_value

        logger_patcher = patch(
            "eozilla_eoap.cwltool.runner.CwltoolLogger", autospec=True
        )
        self.addCleanup(logger_patcher.stop)
        self.mock_logger_class = logger_patcher.start()
        self.mock_logger = self.mock_logger_class.return_value

        self.runner = CwlToolRunner()

        self.job = Mock(spec=Job)

    @patch("builtins.open", new_callable=mock_open)
    def test_run_success(self, mocked_open):
        process = Mock(spec=EoapProcess)
        process.source = "file://some/path/to/workflow/source"
        process.description.id = "echo-workflow"
        process_id = "file://some/path/to/workflow/source#echo-workflow"

        expected_result = {
            "hello_out": {
                "class": "File",
                "path": "/tmp/hello.txt",  # noqa: S108
            }
        }

        process_callable = Mock()
        process_callable.return_value = expected_result
        self.mock_factory.make.return_value = process_callable

        temporary_output_directory = Path("/tmp/output")  # noqa: S108
        process_arguments = {"message": "Hello World"}

        result = self.runner.run(
            "job-1",
            process=process,
            process_arguments=process_arguments,
            temporary_output_directory=temporary_output_directory,
            context=self.job,
        )

        self.mock_logger_class.assert_called_once_with(
            str(Path(temporary_output_directory, "log", "run.log"))
        )
        self.mock_logger.__enter__.assert_called_once()
        self.mock_logger.__exit__.assert_called_once()

        self.mock_callback_executor_class.assert_called_once()

        self.mock_runtime_context_class.assert_called_once_with(
            {
                "outdir": str(Path(temporary_output_directory, "out")),
                "strict_memory_limit": False,
                "strict_cpu_limit": True,
            }
        )

        self.mock_factory_class.assert_called_once_with(
            executor=self.mock_callback_executor,
            runtime_context=self.mock_runtime_context,
        )

        self.mock_factory.make.assert_called_once_with(process_id)
        process_callable.assert_called_once_with(**process_arguments)

        self.assertEqual(result, expected_result)

    @patch("builtins.open", new_callable=mock_open)
    def test_run_cancelled(self, mocked_open):
        process = Mock(spec=EoapProcess)
        process.source = "file://some/path/to/workflow/source"
        process.description.id = "echo-workflow"
        process_id = "file://some/path/to/workflow/source#echo-workflow"

        expected_result = {
            "hello_out": {
                "class": "File",
                "path": "/tmp/hello.txt",  # noqa: S108
            }
        }

        process_callable = Mock()
        process_callable.return_value = expected_result
        process_callable.side_effect = WorkflowException
        self.mock_factory.make.return_value = process_callable

        self.job.is_cancelled.return_value = True

        temporary_output_directory = Path("/tmp/output")  # noqa: S108
        process_arguments = {"message": "Hello World"}

        with self.assertRaises(JobCancelledException):
            _ = self.runner.run(
                "job-1",
                process=process,
                process_arguments=process_arguments,
                temporary_output_directory=temporary_output_directory,
                context=self.job,
            )

        self.mock_logger_class.assert_called_once_with(
            str(Path(temporary_output_directory, "log", "run.log"))
        )
        self.mock_logger.__enter__.assert_called_once()
        self.mock_logger.__exit__.assert_called_once()

        self.mock_callback_executor_class.assert_called_once()

        self.mock_runtime_context_class.assert_called_once_with(
            {
                "outdir": str(Path(temporary_output_directory, "out")),
                "strict_memory_limit": False,
                "strict_cpu_limit": True,
            }
        )

        self.mock_factory_class.assert_called_once_with(
            executor=self.mock_callback_executor,
            runtime_context=self.mock_runtime_context,
        )

        self.mock_factory.make.assert_called_once_with(process_id)
        process_callable.assert_called_once_with(**process_arguments)

    @patch("builtins.open", new_callable=mock_open)
    def test_run_workflowexception_not_cancelled(self, mocked_open):
        process = Mock(spec=EoapProcess)
        process.source = "file://some/path/to/workflow/source"
        process.description.id = "echo-workflow"
        process_id = "file://some/path/to/workflow/source#echo-workflow"

        expected_result = {
            "hello_out": {
                "class": "File",
                "path": "/tmp/hello.txt",  # noqa: S108
            }
        }

        process_callable = Mock()
        process_callable.return_value = expected_result
        process_callable.side_effect = WorkflowException
        self.mock_factory.make.return_value = process_callable

        self.job.is_cancelled.return_value = False

        temporary_output_directory = Path("/tmp/output")  # noqa: S108
        process_arguments = {"message": "Hello World"}

        with self.assertRaises(Exception):  # noqa: B017
            _ = self.runner.run(
                "job-1",
                process=process,
                process_arguments=process_arguments,
                temporary_output_directory=temporary_output_directory,
                context=self.job,
            )

        self.mock_logger_class.assert_called_once_with(
            str(Path(temporary_output_directory, "log", "run.log"))
        )
        self.mock_logger.__enter__.assert_called_once()
        self.mock_logger.__exit__.assert_called_once()

        self.mock_callback_executor_class.assert_called_once()

        self.mock_runtime_context_class.assert_called_once_with(
            {
                "outdir": str(Path(temporary_output_directory, "out")),
                "strict_memory_limit": False,
                "strict_cpu_limit": True,
            }
        )

        self.mock_factory_class.assert_called_once_with(
            executor=self.mock_callback_executor,
            runtime_context=self.mock_runtime_context,
        )

        self.mock_factory.make.assert_called_once_with(process_id)
        process_callable.assert_called_once_with(**process_arguments)

    @patch("builtins.open", new_callable=mock_open)
    def test_run_failure(self, mocked_open):
        process = Mock(spec=EoapProcess)
        process.source = "file://some/path/to/workflow/source"
        process.description.id = "echo-workflow"
        process_id = "file://some/path/to/workflow/source#echo-workflow"

        expected_result = {
            "hello_out": {
                "class": "File",
                "path": "/tmp/hello.txt",  # noqa: S108
            }
        }

        process_callable = Mock()
        process_callable.return_value = expected_result
        process_callable.side_effect = Exception
        self.mock_factory.make.return_value = process_callable

        temporary_output_directory = Path("/tmp/output")  # noqa: S108
        process_arguments = {"message": "Hello World"}

        with self.assertRaises(Exception):  # noqa: B017
            _ = self.runner.run(
                "job-1",
                process=process,
                process_arguments=process_arguments,
                temporary_output_directory=temporary_output_directory,
                context=self.job,
            )

        self.mock_logger_class.assert_called_once_with(
            str(Path(temporary_output_directory, "log", "run.log"))
        )
        self.mock_logger.__enter__.assert_called_once()
        self.mock_logger.__exit__.assert_called_once()

        self.mock_callback_executor_class.assert_called_once()

        self.mock_runtime_context_class.assert_called_once_with(
            {
                "outdir": str(Path(temporary_output_directory, "out")),
                "strict_memory_limit": False,
                "strict_cpu_limit": True,
            }
        )

        self.mock_factory_class.assert_called_once_with(
            executor=self.mock_callback_executor,
            runtime_context=self.mock_runtime_context,
        )

        self.mock_factory.make.assert_called_once_with(process_id)
        process_callable.assert_called_once_with(**process_arguments)

    @patch("builtins.open", new_callable=mock_open)
    def test_factory_failure(self, mocked_open):
        process = Mock(spec=EoapProcess)
        process.source = "file://some/path/to/workflow/source"
        process.description.id = "echo-workflow"
        process_id = "file://some/path/to/workflow/source#echo-workflow"

        expected_result = {
            "hello_out": {
                "class": "File",
                "path": "/tmp/hello.txt",  # noqa: S108
            }
        }

        process_callable = Mock()
        process_callable.return_value = expected_result
        self.mock_factory.make.return_value = process_callable
        self.mock_factory.make.side_effect = WorkflowException

        temporary_output_directory = Path("/tmp/output")  # noqa: S108
        process_arguments = {"message": "Hello World"}

        with self.assertRaises(WorkflowException):
            _ = self.runner.run(
                "job-1",
                process=process,
                process_arguments=process_arguments,
                temporary_output_directory=temporary_output_directory,
                context=self.job,
            )

        self.mock_logger_class.assert_called_once_with(
            str(Path(temporary_output_directory, "log", "run.log"))
        )
        self.mock_logger.__enter__.assert_called_once()
        self.mock_logger.__exit__.assert_called_once()

        self.mock_callback_executor_class.assert_called_once()

        self.mock_runtime_context_class.assert_called_once_with(
            {
                "outdir": str(Path(temporary_output_directory, "out")),
                "strict_memory_limit": False,
                "strict_cpu_limit": True,
            }
        )

        self.mock_factory_class.assert_called_once_with(
            executor=self.mock_callback_executor,
            runtime_context=self.mock_runtime_context,
        )

        self.mock_factory.make.assert_called_once_with(process_id)
        process_callable.assert_not_called()

    @patch("eozilla_eoap.cwltool.runner.NullJobContext", spec=NullJobContext)
    @patch("builtins.open", new_callable=mock_open)
    def test_nullcontext_on_run_success(self, mocked_open, mocked_null_context):
        process = Mock(spec=EoapProcess)
        process.source = "file://some/path/to/workflow/source"
        process.description.id = "echo-workflow"
        process_id = "file://some/path/to/workflow/source#echo-workflow"

        expected_result = {
            "hello_out": {
                "class": "File",
                "path": "/tmp/hello.txt",  # noqa: S108
            }
        }

        process_callable = Mock()
        process_callable.return_value = expected_result
        self.mock_factory.make.return_value = process_callable

        temporary_output_directory = Path("/tmp/output")  # noqa: S108
        process_arguments = {"message": "Hello World"}

        result = self.runner.run(
            "job-1",
            process=process,
            process_arguments=process_arguments,
            temporary_output_directory=temporary_output_directory,
            context=None,
        )

        mocked_null_context.assert_called_once()

        self.mock_logger_class.assert_called_once_with(
            str(Path(temporary_output_directory, "log", "run.log"))
        )
        self.mock_logger.__enter__.assert_called_once()
        self.mock_logger.__exit__.assert_called_once()

        self.mock_callback_executor_class.assert_called_once_with(
            mocked_null_context.return_value
        )

        self.mock_runtime_context_class.assert_called_once_with(
            {
                "outdir": str(Path(temporary_output_directory, "out")),
                "strict_memory_limit": False,
                "strict_cpu_limit": True,
            }
        )

        self.mock_factory_class.assert_called_once_with(
            executor=self.mock_callback_executor,
            runtime_context=self.mock_runtime_context,
        )

        self.mock_factory.make.assert_called_once_with(process_id)
        process_callable.assert_called_once_with(**process_arguments)

        self.assertEqual(result, expected_result)

    @patch("eozilla_eoap.cwltool.runner.NullJobContext", spec=NullJobContext)
    @patch("builtins.open", new_callable=mock_open)
    def test_nullcontext_on_run_failure(self, mocked_open, mocked_null_context):
        process = Mock(spec=EoapProcess)
        process.source = "file://some/path/to/workflow/source"
        process.description.id = "echo-workflow"
        process_id = "file://some/path/to/workflow/source#echo-workflow"

        expected_result = {
            "hello_out": {
                "class": "File",
                "path": "/tmp/hello.txt",  # noqa: S108
            }
        }

        process_callable = Mock()
        process_callable.return_value = expected_result
        process_callable.side_effect = JobCancelledException
        self.mock_factory.make.return_value = process_callable

        temporary_output_directory = Path("/tmp/output")  # noqa: S108
        process_arguments = {"message": "Hello World"}

        # NullJobContext cannot be cancelled; thus a JobCancelledException is not raised
        with self.assertRaises(Exception):  # noqa: B017
            _ = self.runner.run(
                "job-1",
                process=process,
                process_arguments=process_arguments,
                temporary_output_directory=temporary_output_directory,
                context=None,
            )

        mocked_null_context.assert_called_once()

        self.mock_logger_class.assert_called_once_with(
            str(Path(temporary_output_directory, "log", "run.log"))
        )
        self.mock_logger.__enter__.assert_called_once()
        self.mock_logger.__exit__.assert_called_once()

        self.mock_callback_executor_class.assert_called_once_with(
            mocked_null_context.return_value
        )

        self.mock_runtime_context_class.assert_called_once_with(
            {
                "outdir": str(Path(temporary_output_directory, "out")),
                "strict_memory_limit": False,
                "strict_cpu_limit": True,
            }
        )

        self.mock_factory_class.assert_called_once_with(
            executor=self.mock_callback_executor,
            runtime_context=self.mock_runtime_context,
        )

        self.mock_factory.make.assert_called_once_with(process_id)
        process_callable.assert_called_once_with(**process_arguments)
