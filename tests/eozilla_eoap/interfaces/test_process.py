from unittest import TestCase

from eozilla_eoap.interfaces import Process

PROCESS_EXPECTED_METHODS = (
    "create",
    "model_class",
    "description",
)


class ProcsesInterfaceTest(TestCase):
    def test_interface_cannot_instantiate(self):
        with self.assertRaises(TypeError):
            Process()

    def test_process_abstract_methods(self):
        process_abstract_methods: frozenset = Process.__abstractmethods__

        for method in process_abstract_methods:
            self.assertTrue(method in PROCESS_EXPECTED_METHODS)
