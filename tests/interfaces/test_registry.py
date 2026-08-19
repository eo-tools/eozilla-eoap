from unittest import TestCase

from eozilla_eoap.interfaces import Registry

REGISTRY_EXPECTED_METHODS = (
    "configure",
    "create",
    "read",
    "read_all",
    "update",
    "delete",
)


class RegistryInterfaceTest(TestCase):
    def test_interface_cannot_instantiate(self):
        with self.assertRaises(TypeError):
            Registry()

    def test_registry_abstract_methods(self):
        registry_abstract_methods: frozenset = Registry.__abstractmethods__

        for method in registry_abstract_methods:
            if str(method).startswith("__"):
                continue # skip magick methods from Mapping
            self.assertTrue(method in REGISTRY_EXPECTED_METHODS)
