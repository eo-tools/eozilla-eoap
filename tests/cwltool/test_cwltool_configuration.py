from unittest import TestCase

from pydantic import ValidationError

from eozilla_eoap.cwltool import RuntimeContextConfiguration


class RuntimeContextConfigurationTest(TestCase):
    def test_configuration_exposes_options(self):
        self.assertSetEqual(
            set(RuntimeContextConfiguration.model_fields.keys()),
            {
                "user_space_docker_command",
                "force_docker_pull",
                "rm_container",
                "singularity",
                "podman",
                "compute_checksum",
                "debug",
            },
        )

    def test_alias_serialization(self):
        self.assertSetEqual(
            set(RuntimeContextConfiguration().model_dump().keys()),
            {
                "user_space_docker_cmd",
                "force_docker_pull",
                "rm_container",
                "singularity",
                "podman",
                "compute_checksum",
                "debug",
            },
        )

    def test_no_duplicate_container_runtime(self):
        with self.assertRaises(ValidationError):
            RuntimeContextConfiguration(singularity=True, podman=True)
