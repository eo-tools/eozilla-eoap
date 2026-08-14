from pathlib import Path
from shutil import rmtree
from tempfile import TemporaryDirectory
from unittest import TestCase
from urllib.request import url2pathname

import yaml

from eozilla_eoap.procolike import EoapProcess, LocalEaopRegistry


class LocalEaopRegistryTest(TestCase):
    @classmethod
    def setUpClass(cls):
        static_resources_path: Path = Path(
            Path(__file__).parent.parent, "resources", "cwls"
        )

        with open(Path(static_resources_path, "primes-workflow.cwl"), "rt") as f:
            cls.primes_workflow_definition = yaml.safe_load(f)

        with open(Path(static_resources_path, "echo-workflow.cwl"), "rt") as f:
            cls.echo_workflow_definition = yaml.safe_load(f)

        cls.echo_workflow_definition_high_version = cls.echo_workflow_definition.copy()
        cls.echo_workflow_definition_high_version["s:version"] = "100.0.0"

    def setUp(self):
        self.temporary_path = Path(
            TemporaryDirectory(prefix="pytest-fixture-", delete=False).name
        )
        self.registry = LocalEaopRegistry(self.temporary_path)
        # TODO: doesn't this somehow *invalidate* the test for the registry, if I access
        #       one of its methods while also testing the registry's functionality?
        self.registry.configure()
        self.registry.create(self.echo_workflow_definition, None, ignore_existing=False)

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
        proc = self.registry.create(self.primes_workflow_definition, None, False)

        self.assertIsInstance(proc, EoapProcess)
        self.assertEqual(proc.description.id, "primes-workflow")
        self.assertEqual(proc.entrypoint, "primes-workflow")
        self.assertEqual(len(self.registry), 2)
        self.assertEqual(len(list(self.temporary_path.glob("*.cwl"))), 2)

    def test_process_creation_refuses_duplicate(self):
        with self.assertRaises(KeyError):
            self.registry.create(
                self.echo_workflow_definition, None, ignore_existing=False
            )

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
        self.registry.update(self.echo_workflow_definition_high_version, None)

        proc = self.registry.get("echo-workflow")

        with open(url2pathname(proc.source, require_scheme=True), "rt") as f:
            d = yaml.safe_load(f)

        self.assertIsInstance(proc, EoapProcess)
        self.assertDictEqual(d, self.echo_workflow_definition_high_version)

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
