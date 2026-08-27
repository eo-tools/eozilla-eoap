from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from gavicore.models import JobResults, JobStatus, ProcessRequest
from procodile.job import JobCancelledException

from eozilla_eoap.interfaces import Runner
from eozilla_eoap.procolike import EoapProcess, Job

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


class JobTest(TestCase):
    def setUp(self):
        self.proc = EoapProcess.create("/non/existing/dir", ECHO_WORKFLOW_DEFINITION)

        am_patcher = patch(
            "eozilla_eoap.procolike.eoap_job.LocalArtifactManager", autospec=True
        )
        self.addCleanup(am_patcher.stop)
        # this corresponds to the class itself, can be used, e.g., to check whether constructor was called
        self.mock_artifcat_manager_class = am_patcher.start()
        # this corresponds to a class instance, can be used, e.g., to check whether a method was called
        self.mock_artifcat_manager = self.mock_artifcat_manager_class.return_value

        # NOTE: since only the interface is mocked, these attributes are never defind and
        #       must be set explicitly!
        self.artifact_base = Path("/some/path")
        self.mock_artifcat_manager.persistent_output_directory = Path(
            "/persistent/output"
        )
        self.mock_artifcat_manager.temporary_output_directory = Path("/tmp/output")  # noqa: S108

        # since at no point in all of this, an acutal runner is instantiated, we can mock instead of path
        # additionally, we can mock the interface instead of an implementation
        self.mock_runner = Mock(spec=Runner)

    def tearDown(self):
        del self.proc

    def test_job_constructor(self):
        job = Job.create(
            process=self.proc,
            request=ProcessRequest(inputs={"message": "שלום עולם"}),
            cwl_runner=self.mock_runner,
            job_id="static-job-id-01",
            persistency_directory=self.artifact_base,
        )

        self.assertEqual("echo-workflow", job.job_info.processID)
        self.assertEqual("static-job-id-01", job.job_info.jobID)
        self.assertIsNone(job.job_info.progress)

        self.mock_artifcat_manager_class.assert_called_once()
        self.mock_artifcat_manager_class.assert_called_with(
            self.artifact_base,
            "static-job-id-01",
            self.proc.model_class.model_validate({"message": "שלום עולם"}),
        )

    def test_job_constructor_default_arg(self):
        job = Job.create(
            process=self.proc,
            request=ProcessRequest(),
            cwl_runner=self.mock_runner,
            job_id="static-job-id-01",
            persistency_directory=self.artifact_base,
        )

        self.assertEqual("echo-workflow", job.job_info.processID)
        self.assertEqual("static-job-id-01", job.job_info.jobID)
        self.assertIsNone(job.job_info.progress)

        self.mock_artifcat_manager_class.assert_called_once()
        self.mock_artifcat_manager_class.assert_called_with(
            self.artifact_base,
            "static-job-id-01",
            self.proc.model_class.model_validate({}),
        )

    def test_run_success(self):
        self.mock_runner.run.return_value = {"hello_out": "שלום עולם"}
        self.mock_artifcat_manager.stage_out.return_value = {"hello_out": "שלום עולם"}

        job = Job.create(
            process=self.proc,
            request=ProcessRequest(inputs={"message": "שלום עולם"}),
            cwl_runner=self.mock_runner,
            job_id="static-job-id-01",
            persistency_directory=self.artifact_base,
        )

        job_results = job.run()

        self.mock_artifcat_manager.initialize.assert_called_once()
        self.mock_artifcat_manager.stage_in.assert_called_once()
        self.mock_artifcat_manager.rebuild_process_arguments.assert_called_once()
        self.mock_artifcat_manager.stage_out.assert_called_once()
        self.mock_artifcat_manager.remove_staged_inputs.assert_called_once()
        self.mock_artifcat_manager.remove_temporary_outputs.assert_called_once()

        self.mock_runner.run.assert_called_once()
        self.assertEqual(job_results, JobResults({"hello_out": "שלום עולם"}))

        self.assertEqual(JobStatus.successful, job.job_info.status)
        self.assertIsNone(job.job_info.progress)
        self.assertIsNone(job.job_info.message)

    def test_run_success_with_defaults(self):
        # this is wrong as the return value is actual CWL object!
        # FUCK: I also need to patch intialization and stage_in!
        self.mock_runner.run.return_value = {"hello_out": "Hello World"}
        self.mock_artifcat_manager.stage_out.return_value = {"hello_out": "Hello World"}

        job = Job.create(
            process=self.proc,
            request=ProcessRequest(),
            cwl_runner=self.mock_runner,
            job_id="static-job-id-01",
            persistency_directory=self.artifact_base,
        )

        job_results = job.run()

        self.mock_artifcat_manager.initialize.assert_called_once()
        self.mock_artifcat_manager.stage_in.assert_called_once()
        self.mock_artifcat_manager.rebuild_process_arguments.assert_called_once()
        self.mock_artifcat_manager.stage_out.assert_called_once()
        self.mock_artifcat_manager.remove_staged_inputs.assert_called_once()
        self.mock_artifcat_manager.remove_temporary_outputs.assert_called_once()

        self.mock_runner.run.assert_called_once()
        self.assertEqual(job_results, JobResults({"hello_out": "Hello World"}))

        self.assertEqual(JobStatus.successful, job.job_info.status)
        self.assertIsNone(job.job_info.progress)
        self.assertIsNone(job.job_info.message)

    def test_run_exception(self):
        self.mock_runner.run.side_effect = Exception

        job = Job.create(
            process=self.proc,
            request=ProcessRequest(),
            cwl_runner=self.mock_runner,
            job_id="static-job-id-01",
            persistency_directory=self.artifact_base,
        )

        job_results = job.run()

        self.mock_artifcat_manager.initialize.assert_called_once()
        self.mock_artifcat_manager.stage_in.assert_called_once()
        self.mock_artifcat_manager.rebuild_process_arguments.assert_called_once()
        self.mock_artifcat_manager.stage_out.assert_not_called()
        self.mock_artifcat_manager.remove_staged_inputs.assert_called_once()
        self.mock_artifcat_manager.remove_temporary_outputs.assert_called_once()

        self.mock_runner.run.assert_called_once()
        self.assertIsNone(job_results)

        self.assertEqual(JobStatus.failed, job.job_info.status)
        self.assertIsNone(job.job_info.progress)
        self.assertEqual(job.job_info.message, "")

    def test_run_failed(self):
        self.mock_runner.run.side_effect = JobCancelledException

        job = Job.create(
            process=self.proc,
            request=ProcessRequest(),
            cwl_runner=self.mock_runner,
            job_id="static-job-id-01",
            persistency_directory=self.artifact_base,
        )

        job_results = job.run()

        self.mock_artifcat_manager.initialize.assert_called_once()
        self.mock_artifcat_manager.stage_in.assert_called_once()
        self.mock_artifcat_manager.rebuild_process_arguments.assert_called_once()
        self.mock_artifcat_manager.stage_out.assert_not_called()
        self.mock_artifcat_manager.remove_staged_inputs.assert_called_once()
        self.mock_artifcat_manager.remove_temporary_outputs.assert_called_once()

        self.mock_runner.run.assert_called_once()
        self.assertIsNone(job_results)

        self.assertEqual(JobStatus.dismissed, job.job_info.status)
        self.assertIsNone(job.job_info.progress)
        self.assertIsNone(job.job_info.message)
