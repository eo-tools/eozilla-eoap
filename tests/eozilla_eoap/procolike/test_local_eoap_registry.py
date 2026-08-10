from tempfile import TemporaryDirectory
from unittest import TestCase
from pathlib import Path
from shutil import rmtree
import yaml
from urllib.request import url2pathname

from eozilla_eoap.procolike import EoapProcess, LocalEaopRegistry

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

ECHO_WORKFLOW_DEFINITION_HIGH_VERSION = {
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
    "s:version": "100.0.0",
}

CAT_WORKFLOW_DEFINITION = {
    "$graph": [
        {
            "class": "Workflow",
            "cwlVersion": "v1.2",
            "label": "Cat User Input from File to stdout",
            "doc": "The cat EOAP is a simple process that cat the contents of a user-supplied file to stdout . By registering the accompanying CWL workflow, the process will be available at `/processes/cat-workflow`.",
            "id": "cat-workflow",
            "inputs": {
                "file": {
                    "label": "File to cat",
                    "doc": "some very length description of what this argument does",
                    "type": "File",
                }
            },
            "outputs": {
                "cat_out": {
                    "outputSource": "cat/cat_out",
                    "type": {"type": "array", "items": "string"},
                }
            },
            "steps": {
                "cat": {"in": {"file": "file"}, "out": ["cat_out"], "run": "#cat-tool"}
            },
        },
        {
            "baseCommand": ["cat"],
            "class": "CommandLineTool",
            "id": "#cat-tool",
            "inputs": {"file": {"inputBinding": {"position": 1}, "type": "File"}},
            "label": "Cat Tool",
            "outputs": {
                "cat_out": {
                    "outputBinding": {
                        "glob": "cat.txt",
                        "loadContents": True,
                        "outputEval": "$(self[0].contents.split('\\n'))",
                    },
                    "type": {"type": "array", "items": "string"},
                }
            },
            "requirements": {
                "DockerRequirement": {"dockerPull": "alpine:3.22"},
                "InlineJavascriptRequirement": {},
            },
            "stdout": "cat.txt",
        },
    ],
    "$namespaces": {"s": "https://schema.org/"},
    "cwlVersion": "v1.2",
    "s:version": "0.0.1",
}


class LocalEaopRegistryTest(TestCase):
    def setUp(self):
        self.temporary_path = Path(TemporaryDirectory(prefix="pytest-fixture-", delete=False).name)
        self.registry = LocalEaopRegistry(self.temporary_path)
        # TODO: doesn't this somehow *invalidate* the test for the registry, if I access
        #       one of its methods while also testing the registry's functionality?
        self.registry.configure()
        self.registry.create(ECHO_WORKFLOW_DEFINITION, None, ignore_existing=False)

    def tearDown(self):
        rmtree(self.temporary_path)

    def test_len_and_contains(self):
        self.assertEqual(len(self.registry), 1)
        self.assertIn("echo-workflow", self.registry)
        self.assertNotIn("missing", self.registry)

    def test_getitem_retuns_process(self):
        proc = self.registry["echo-workflow"]

        self.assertIsInstance(proc, EoapProcess)
        self.assertEqual(proc.description.id, "echo-workflow")

    def test_get_method(self):
        proc = self.registry.get("echo-workflow")
        missing = self.registry.get("missing")

        self.assertIsInstance(proc, EoapProcess)
        self.assertIsNone(missing)

    def test_iteration_yields_keys(self):
        keys = list(self.registry)
        self.assertEqual(keys, ["echo-workflow"])

    def test_values_yields_processes(self):
        values = list(self.registry.values())

        self.assertEqual(len(values), 1)
        self.assertIsInstance(values[0], EoapProcess)

    def test_items_yield_id_and_process(self):
        items = list(self.registry.items())

        self.assertEqual(len(items), 1)

        proc_id, proc = items[0]

        self.assertEqual(proc_id, "echo-workflow")
        self.assertIsInstance(proc, EoapProcess)

    def test_process_creation(self):
        proc = self.registry.create(CAT_WORKFLOW_DEFINITION, None, False)

        self.assertIsInstance(proc, EoapProcess)
        self.assertEqual(proc.description.id, "cat-workflow")
        self.assertEqual(proc.entrypoint, "cat-workflow")
        self.assertEqual(len(self.registry), 2)
        self.assertEqual(len(list(self.temporary_path.glob("*.cwl"))), 2)

    def test_process_creation_refuses_duplicate(self): ...

    def test_process_read(self):
        proc = self.registry.read("echo-workflow")

        self.assertIsInstance(proc, EoapProcess)
    
    def test_process_read_missing(self):
        with self.assertRaises(KeyError):
            self.registry.read("missing")

    def test_process_read_all(self):
        processes = self.registry.read_all()

        self.assertIsInstance(processes, dict)
        self.assertEqual(len(processes), 1)

        proc_id, proc = list(processes.items())[0]
        self.assertEqual(proc_id, "echo-workflow")
        self.assertIsInstance(proc, EoapProcess)

    def test_process_replacement(self):
        self.registry.update(ECHO_WORKFLOW_DEFINITION_HIGH_VERSION, None)

        proc = self.registry.get("echo-workflow")

        with open(url2pathname(proc.source, require_scheme=True), "rt") as f:
            d = yaml.safe_load(f)

        self.assertIsInstance(proc, EoapProcess)
        self.assertDictEqual(d, ECHO_WORKFLOW_DEFINITION_HIGH_VERSION)

    def test_process_deletion(self):
        self.registry.delete("echo-workflow")
        self.assertEqual(len(self.registry), 0)
        self.assertNotIn("echo-workflow", self.registry)

    def test_registry_rebuilding(self):
        new_registry = LocalEaopRegistry(self.temporary_path)
        new_registry.configure()

        self.assertEqual(len(new_registry), 1)
        self.assertIn("echo-workflow", new_registry)
        self.assertNotIn("missing", new_registry)

        proc = new_registry.get("echo-workflow")

        self.assertEqual(proc.description.id, "echo-workflow")
        self.assertEqual(proc.entrypoint, "echo-workflow")
        self.assertIsInstance(proc, EoapProcess)
