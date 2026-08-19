from unittest import TestCase

from eozilla_eoap.interfaces import Runner

RUNNER_EXPECTED_METHODS = ("run",)


class ProcsesInterfaceTest(TestCase):
    def test_interface_cannot_instantiate(self):
        with self.assertRaises(TypeError):
            Runner()

    def test_runner_abstract_methods(self):
        runner_abstract_methods: frozenset = Runner.__abstractmethods__

        for method in runner_abstract_methods:
            self.assertTrue(method in RUNNER_EXPECTED_METHODS)
