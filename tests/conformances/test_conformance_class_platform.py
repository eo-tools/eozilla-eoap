import os
from pathlib import Path
from typing import Dict
from unittest import TestCase

import pystac
import pytest
import yaml
from fastapi import Response
from fastapi.testclient import TestClient
from gavicore.models import (
    InputDescription,
    OutputDescription,
    ProcessDescription,
    Schema,
)
from gavicore.util.testing import set_env
from wraptile.main import app
from wraptile.provider import ServiceProvider


def check_asset_existance(key: str, asset: pystac.Asset) -> Dict[str, pystac.Asset]:
    assert Path(asset.href).exists(), f"{asset.href} does not exist"
    return {key: asset}


def check_item_existance(item: pystac.Item) -> pystac.Item:
    assert Path(item.get_self_href()).exists(), f"{item.get_self_href()} does not exist"
    return item


class ConformanceClassPlatformTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.static_resources_path: Path = Path(
            Path(__file__).parent.parent, "resources", "cwls"
        )

        cls.restore_env = set_env(EOZILLA_SERVICE="eozilla_eoap.testing.main:service")

        # NOTE: need to touch service provider to trigger dependency injection
        ServiceProvider.get_instance()

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        response: Response = cls.client.get("/processes")
        processes = response.json()["processes"]

        for proc in processes:
            id_ = proc["id"]
            cls.client.delete(f"/processes/{id_}")

        cls.restore_env()

    def test_abstract_test_10(self):
        response: Response = self.client.get("/processes")
        self.assertEqual(response.status_code, 200)

        response_body: Dict = response.json()
        self.assertEqual(len(response_body["processes"]), 0)

        with open(
            Path(self.static_resources_path, "conglomerate_of_arguments.cwl"), "r"
        ) as f:
            response = self.client.post(
                "/processes",
                content=f.read(),
                headers={"Content-Type": "application/cwl"},
            )

            # NOTE: is it okay to read in the file here as well?
            f.seek(0)

            in_memory_eoap = yaml.safe_load(f)

        self.assertEqual(response.status_code, 201)

        response = self.client.get("/processes")
        self.assertEqual(response.status_code, 200)

        response_body = response.json()
        self.assertEqual(len(response_body["processes"]), 1)

        # NOTE: A more comprehensive test suite for type conversions can be found in tests/procolike/test_eoap_process.py
        response = self.client.get("/processes/platform/package")
        self.assertEqual(response.status_code, 200)

        response_body = response.json()
        process_description: ProcessDescription = ProcessDescription.model_validate(
            response_body["processDescription"]["process"]
        )

        # Check table 2 based on req/plt/api
        self.assertEqual(
            process_description.id, in_memory_eoap.get("$graph")[0].get("id")
        )
        self.assertEqual(
            process_description.title, in_memory_eoap.get("$graph")[0].get("label")
        )
        self.assertEqual(
            process_description.description, in_memory_eoap.get("$graph")[0].get("doc")
        )
        self.assertEqual(process_description.keywords, in_memory_eoap.get("s:keyword"))
        self.assertEqual(process_description.version, in_memory_eoap.get("s:version"))

        expected_inputs: Dict[str, InputDescription] = {
            "boolean_input": InputDescription(
                title="Placeholder label for the input",
                description="Placeholder doc-string for the input",
                maxOccurs=1,
                schema=Schema(type="boolean", nullable=False),
            ),
            "int_input": InputDescription(
                title="Placeholder label for the input",
                description="Placeholder doc-string for the input",
                maxOccurs=1,
                schema=Schema(
                    type="integer",
                    nullable=False,
                ),
            ),
            "long_input": InputDescription(
                title="Placeholder label for the input",
                description="Placeholder doc-string for the input",
                maxOccurs=1,
                schema=Schema(
                    type="integer",
                    nullable=False,
                ),
            ),
            "float_input": InputDescription(
                title="Placeholder label for the input",
                description="Placeholder doc-string for the input",
                maxOccurs=1,
                schema=Schema(type="number", nullable=False),
            ),
            "double_input": InputDescription(
                title="Placeholder label for the input",
                description="Placeholder doc-string for the input",
                maxOccurs=1,
                schema=Schema(type="number", nullable=False),
            ),
            "string_input": InputDescription(
                title="Placeholder label for the input",
                description="Placeholder doc-string for the input",
                maxOccurs=1,
                schema=Schema(type="string", nullable=False),
            ),
            "enum_input": InputDescription(
                title="Placeholder label for the input",
                description="Placeholder doc-string for the input",
                maxOccurs=1,
                schema=Schema(
                    type="string", nullable=False, enum=["option 1", "option 2"]
                ),
            ),
            "file_input": InputDescription(
                title="Placeholder label for the input",
                description="Placeholder doc-string for the input",
                maxOccurs=1,
                schema=Schema(type="string", nullable=False, format="url"),
            ),
            "directory_input": InputDescription(
                title="Placeholder label for the input",
                description="Placeholder doc-string for the input",
                maxOccurs=1,
                schema=Schema(type="string", nullable=False, format="url"),
            ),
            "optional_int_input": InputDescription(
                title="Placeholder label for the input",
                description="Placeholder doc-string for the input",
                minOccurs=0,
                maxOccurs=1,
                schema=Schema(
                    type="integer",
                    nullable=True,
                ),
            ),
            "array_enum_input": InputDescription(
                title="Placeholder label for the input",
                description="Placeholder doc-string for the input",
                minOccurs=1,
                maxOccurs="unbounded",
                schema=Schema(
                    type="array",
                    nullable=False,
                    minItems=1,
                    items=Schema(
                        type="string", nullable=False, enum=["option 1", "option 2"]
                    ),
                ),
            ),
        }

        expected_outputs: Dict[str, OutputDescription] = {
            "boolean_output": OutputDescription(
                title="Placeholder label for the output",
                description="Placeholder doc-string for the output",
                schema=Schema(type="boolean", nullable=False),
            ),
            "int_output": OutputDescription(
                title="Placeholder label for the output",
                description="Placeholder doc-string for the output",
                schema=Schema(
                    type="integer",
                    nullable=False,
                ),
            ),
            "long_output": OutputDescription(
                title="Placeholder label for the output",
                description="Placeholder doc-string for the output",
                schema=Schema(
                    type="integer",
                    nullable=False,
                ),
            ),
            "float_output": OutputDescription(
                title="Placeholder label for the output",
                description="Placeholder doc-string for the output",
                schema=Schema(type="number", nullable=False),
            ),
            "double_output": OutputDescription(
                title="Placeholder label for the output",
                description="Placeholder doc-string for the output",
                schema=Schema(type="number", nullable=False),
            ),
            "string_output": OutputDescription(
                title="Placeholder label for the output",
                description="Placeholder doc-string for the output",
                schema=Schema(type="string", nullable=False),
            ),
            "enum_output": OutputDescription(
                title="Placeholder label for the output",
                description="Placeholder doc-string for the output",
                schema=Schema(
                    type="string", nullable=False, enum=["option 1", "option 2"]
                ),
            ),
            "file_output": OutputDescription(
                title="Placeholder label for the output",
                description="Placeholder doc-string for the output",
                schema=Schema(type="string", nullable=False, format="url"),
            ),
            "directory_output": OutputDescription(
                title="Placeholder label for the output",
                description="Placeholder doc-string for the output",
                schema=Schema(type="string", nullable=False, format="url"),
            ),
            "optional_int_output": OutputDescription(
                title="Placeholder label for the output",
                description="Placeholder doc-string for the output",
                schema=Schema(
                    type="integer",
                    nullable=True,
                ),
            ),
            "array_enum_output": OutputDescription(
                title="Placeholder label for the output",
                description="Placeholder doc-string for the output",
                schema=Schema(
                    type="array",
                    nullable=False,
                    minItems=1,
                    items=Schema(
                        type="string", nullable=False, enum=["option 1", "option 2"]
                    ),
                ),
            ),
        }

        self.assertDictEqual(process_description.inputs, expected_inputs)
        self.assertDictEqual(process_description.outputs, expected_outputs)


class ConformanceClassPlatformStagedOutputsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.static_resources_path: Path = Path(
            Path(__file__).parent.parent, "resources", "cwls"
        )

        cls.restore_env = set_env(EOZILLA_SERVICE="eozilla_eoap.testing.main:service")

        # NOTE: need to touch service provider to trigger dependency injection
        ServiceProvider.get_instance()

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        response: Response = cls.client.get("/processes")
        processes = response.json()["processes"]

        for proc in processes:
            id_ = proc["id"]
            cls.client.delete(f"/processes/{id_}")

        cls.restore_env()

    def setUp(self):
        with open(Path(self.static_resources_path, "platform-stac-out.cwl"), "r") as f:
            self.client.post(
                "/processes",
                content=f.read(),
                headers={"Content-Type": "application/cwl"},
            )

    def test_abstract_test_13(self):
        response: Response = self.client.post(
            "/processes/platform-stac-out/execution", json={}
        )
        self.assertEqual(response.status_code, 201)

        response_body = response.json()
        job_id: str = response_body.get("jobID")

        while True:
            response = self.client.get(f"/jobs/{job_id}")
            self.assertEqual(response.status_code, 200)

            response_body = response.json()

            if response_body.get("status") == "successful":
                break
            elif response_body.get("status") == "running":
                continue
            else:
                raise AssertionError

        response = self.client.get(f"/jobs/{job_id}/results")
        self.assertEqual(response.status_code, 200)

        response_body = response.json()
        output_catalog = response_body.get("stac_output")
        self.assertIsNotNone(output_catalog)

        self.assertTrue(Path(output_catalog).exists())

        catalog: pystac.Catalog = pystac.Catalog.from_file(output_catalog)
        catalog.make_all_asset_hrefs_absolute()
        _ = catalog.map_items(check_item_existance)
        _ = catalog.map_assets(check_asset_existance)

        self.client.delete(f"/jobs/{job_id}")
