from typing import Literal, TypeVar
from unittest import TestCase

from cwl_utils.parser.cwl_v1_2 import Directory as CwlDirectory
from cwl_utils.parser.cwl_v1_2 import File as CwlFile
from cwl_utils.parser.cwl_v1_2 import (
    InputArraySchema,
    InputEnumSchema,
    InputRecordSchema,
    OutputArraySchema,
    OutputEnumSchema,
    OutputRecordSchema,
    WorkflowInputParameter,
    WorkflowOutputParameter,
)
from gavicore.models import Schema
from pydantic import BaseModel, Field

from eozilla_eoap.procolike.eoap_process import (
    Directory,
    EoapProcess,
    File,
    _resolve_ogc_schema_from_cwl_utils,
    _resolve_to_pydantic_tuple,
    cwl_inputs_to_model_class,
)

CWL_MODELS = (
    (File, "File"),
    (Directory, "Directory"),
)

SIMPLE_TYPE_MAPPINGS = {
    # null -> this has no mapping as it's used as the "optional" marker in CWL
    "boolean": {
        "ogc_type": "boolean",
        "default_in": True,
        "default_out": True,
        "format": None,
    },
    "int": {
        "ogc_type": "integer",
        "default_in": 2147483647,
        "default_out": 2147483647,
        "format": None,
    },
    "long": {
        "ogc_type": "integer",
        "default_in": 9223372036854775807,
        "default_out": 9223372036854775807,
        "format": None,
    },
    "float": {
        "ogc_type": "number",
        "default_in": 3.402823e38,
        "default_out": 3.402823e38,
        "format": None,
    },
    "double": {
        "ogc_type": "number",
        "default_in": 1.797693e20,
        "default_out": 1.797693e20,
        "format": None,
    },
    "string": {
        "ogc_type": "string",
        "default_in": "hello, world",
        "default_out": "hello, world",
        "format": None,
    },
    "File": {
        "ogc_type": "string",
        "default_in": CwlFile(
            location="https://files.example.com/remote/path/to/some/file.txt"
        ),
        "default_out": "https://files.example.com/remote/path/to/some/file.txt",
        "format": "url",
    },
    "Directory": {
        "ogc_type": "string",
        "default_in": CwlDirectory(
            location="https://catalogs.example.com/remote/path/to/some/STAC/item/"
        ),
        "default_out": "https://catalogs.example.com/remote/path/to/some/STAC/item/",
        "format": "url",
    },
}

T = TypeVar("T", bound=BaseModel)


class EoapProcessTest(TestCase): ...


class ModelsTest(TestCase):
    def test_models_are_extensible(self):
        for model, class_name in CWL_MODELS:
            with self.subTest(model=model, class_name=class_name):
                model_dict = {
                    "class": class_name,
                    "path": "/some/imaginary/path",
                    "extra_attribute": "extra_value",
                }
                model_instance = model(**model_dict)
                self.assertEqual(
                    model_dict,
                    model_instance.model_dump(mode="python", exclude_unset=True),
                )

    def test_models_before_validator(self):
        for model, class_name in CWL_MODELS:
            with self.subTest(model=model, class_name=class_name):
                instance_with_validator = model(path="/some/imaginary/path")
                instance_without_validator = model(
                    class_=class_name, path="/some/imaginary/path"
                )
                self.assertEqual(instance_without_validator, instance_with_validator)


class OgcSchemaResolvingTest(TestCase):
    def test_input_cwltypes_without_default(self):
        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type = WorkflowInputParameter(id="some-id", type_=key)

                # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
                nullable, unbounded, computed_schema = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type.type_,
                        format=cwl_type.format,
                        nullable=cwl_type.default is not None,
                    )
                )

                expected_schema = Schema(
                    type=value.get("ogc_type"),
                    contentMediaType=cwl_type.format,
                    nullable=False,
                    format=value.get("format"),
                )

                expected_dump = expected_schema.model_dump()
                computed_dump = computed_schema.model_dump()

                self.assertDictEqual(expected_dump, computed_dump)
                self.assertFalse(nullable)
                self.assertFalse(unbounded)

    def test_input_cwltypes_with_default(self):
        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type = WorkflowInputParameter(
                    id="some-id", type_=key, default=value.get("default_in")
                )

                # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
                nullable, unbounded, computed_schema = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type.type_,
                        default=cwl_type.default,
                        format=cwl_type.format,
                        nullable=cwl_type.default is not None,
                    )
                )

                expected_schema = Schema(
                    type=value.get("ogc_type"),
                    default=value.get("default_out"),
                    contentMediaType=cwl_type.format,
                    nullable=True,
                    format=value.get("format"),
                )

                expected_dump = expected_schema.model_dump()
                computed_dump = computed_schema.model_dump()

                self.assertDictEqual(expected_dump, computed_dump)
                self.assertTrue(nullable)
                self.assertFalse(unbounded)

    def test_input_optional_cwltypes_without_default(self):
        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type = WorkflowInputParameter(id="some-id", type_=["null", key])

                # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
                nullable, unbounded, computed_schema = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type.type_,
                        format=cwl_type.format,
                        nullable=cwl_type.default is not None,
                    )
                )

                expected_schema = Schema(
                    type=value.get("ogc_type"),
                    contentMediaType=cwl_type.format,
                    nullable=True,
                    format=value.get("format"),
                )

                expected_dump = expected_schema.model_dump()
                computed_dump = computed_schema.model_dump()

                self.assertDictEqual(expected_dump, computed_dump)
                self.assertTrue(nullable)
                self.assertFalse(unbounded)

    def test_input_optional_cwltypes_order_invariant(self):
        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type_1 = WorkflowInputParameter(id="some-id", type_=["null", key])
                cwl_type_2 = WorkflowInputParameter(id="some-id", type_=[key, "null"])

                # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
                nullable_1, unbounded_1, computed_schema_1 = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type_1.type_,
                        format=cwl_type_1.format,
                        nullable=cwl_type_1.default is not None,
                    )
                )
                nullable_2, unbounded_2, computed_schema_2 = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type_2.type_,
                        format=cwl_type_2.format,
                        nullable=cwl_type_2.default is not None,
                    )
                )

                computed_dump_1 = computed_schema_1.model_dump()
                computed_dump_2 = computed_schema_2.model_dump()

                self.assertDictEqual(computed_dump_1, computed_dump_2)
                self.assertTrue(nullable_1)
                self.assertFalse(unbounded_1)
                self.assertEqual(nullable_1, nullable_2)
                self.assertEqual(unbounded_1, unbounded_2)

    def test_input_array_of_cwltypes_without_default(self):
        self.maxDiff = None

        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type = WorkflowInputParameter(
                    id="some-id", type_=InputArraySchema(type_="array", items=key)
                )

                # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
                nullable, unbounded, computed_schema = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type.type_,
                        format=cwl_type.format,
                        nullable=cwl_type.default is not None,
                    )
                )

                expected_schema = Schema(
                    type="array",
                    nullable=False,
                    minItems=1,
                    items=Schema(
                        type=value.get("ogc_type"),
                        contentMediaType=cwl_type.format,
                        format=value.get("format"),
                    ),
                )

                expected_dump = expected_schema.model_dump()
                computed_dump = computed_schema.model_dump()

                self.assertDictEqual(expected_dump, computed_dump)
                self.assertFalse(nullable)
                self.assertTrue(unbounded)

    def test_input_array_of_cwltypes_with_default(self):
        self.maxDiff = None

        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type = WorkflowInputParameter(
                    id="some-id",
                    type_=InputArraySchema(type_="array", items=key),
                    default=[value.get("default_in")],
                )

                # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
                nullable, unbounded, computed_schema = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type.type_,
                        default=cwl_type.default,
                        format=cwl_type.format,
                        nullable=cwl_type.default is not None,
                    )
                )

                expected_schema = Schema(
                    type="array",
                    default=[value.get("default_out")],
                    nullable=True,
                    minItems=1,
                    items=Schema(
                        type=value.get("ogc_type"),
                        contentMediaType=cwl_type.format,
                        format=value.get("format"),
                    ),
                )

                expected_dump = expected_schema.model_dump()
                computed_dump = computed_schema.model_dump()

                self.assertDictEqual(expected_dump, computed_dump)
                self.assertTrue(nullable)
                self.assertTrue(unbounded)

    def test_input_optional_array_of_cwltypes_without_default(self):
        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type = WorkflowInputParameter(
                    id="some-id",
                    type_=["null", InputArraySchema(type_="array", items=key)],
                )

                nullable, unbounded, computed_schema = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type.type_,
                        default=cwl_type.default,
                        format=cwl_type.format,
                        nullable=cwl_type.default is not None,
                    )
                )

                expected_schema = Schema(
                    type="array",
                    nullable=True,
                    minItems=1,
                    items=Schema(
                        type=value.get("ogc_type"),
                        contentMediaType=cwl_type.format,
                        format=value.get("format"),
                    ),
                )

                expected_dump = expected_schema.model_dump()
                computed_dump = computed_schema.model_dump()

                self.assertDictEqual(expected_dump, computed_dump)
                self.assertTrue(nullable)
                self.assertTrue(unbounded)

    def test_input_optional_array_of_cwltypes_with_default(self):
        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type = WorkflowInputParameter(
                    id="some-id",
                    type_=["null", InputArraySchema(type_="array", items=key)],
                    default=[value.get("default_in")],
                )

                nullable, unbounded, computed_schema = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type.type_,
                        default=cwl_type.default,
                        format=cwl_type.format,
                        nullable=cwl_type.default is not None,
                    )
                )

                expected_schema = Schema(
                    type="array",
                    nullable=True,
                    minItems=1,
                    items=Schema(
                        type=value.get("ogc_type"),
                        contentMediaType=cwl_type.format,
                        format=value.get("format"),
                    ),
                    default=[value.get("default_out")],
                )

                expected_dump = expected_schema.model_dump()
                computed_dump = computed_schema.model_dump()

                self.assertDictEqual(expected_dump, computed_dump)
                self.assertTrue(nullable)
                self.assertTrue(unbounded)

    def test_input_array_of_enums_without_defaults(self):
        cwl_type = WorkflowInputParameter(
            id="some-id",
            type_=InputArraySchema(
                type_="array",
                items=InputEnumSchema(type_="enum", symbols=["sym-a", "sym-b"]),
            ),
        )

        # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
        nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
            cwl_type.type_,
            format=cwl_type.format,
            nullable=cwl_type.default is not None,
        )

        expected_schema = Schema(
            type="array",
            nullable=False,
            minItems=1,
            items=Schema(
                type="string",
                format=cwl_type.format,
                enum=["sym-a", "sym-b"],
            ),
        )

        expected_dump = expected_schema.model_dump()
        computed_dump = computed_schema.model_dump()

        self.assertDictEqual(expected_dump, computed_dump)
        self.assertFalse(nullable)
        self.assertTrue(unbounded)

    def test_input_array_of_enums_with_defaults(self):
        cwl_type = WorkflowInputParameter(
            id="some-id",
            type_=InputArraySchema(
                type_="array",
                items=InputEnumSchema(type_="enum", symbols=["sym-a", "sym-b"]),
            ),
            default=["sym-a"],
        )

        # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
        nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
            cwl_type.type_,
            default=cwl_type.default,
            format=cwl_type.format,
            nullable=cwl_type.default is not None,
        )

        expected_schema = Schema(
            type="array",
            default=["sym-a"],
            nullable=True,
            minItems=1,
            items=Schema(
                type="string",
                format=cwl_type.format,
                enum=["sym-a", "sym-b"],
            ),
        )

        expected_dump = expected_schema.model_dump()
        computed_dump = computed_schema.model_dump()

        self.assertDictEqual(expected_dump, computed_dump)
        self.assertTrue(nullable)
        self.assertTrue(unbounded)

    def test_input_optional_array_of_enums_without_default(self):
        cwl_type = WorkflowInputParameter(
            id="some-id",
            type_=[
                "null",
                InputArraySchema(
                    type_="array",
                    items=InputEnumSchema(type_="enum", symbols=["sym-a", "sym-b"]),
                ),
            ],
        )

        # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
        nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
            cwl_type.type_,
            format=cwl_type.format,
            nullable=cwl_type.default is not None,
        )

        expected_schema = Schema(
            type="array",
            nullable=True,
            minItems=1,
            items=Schema(
                type="string",
                format=cwl_type.format,
                enum=["sym-a", "sym-b"],
            ),
        )

        expected_dump = expected_schema.model_dump()
        computed_dump = computed_schema.model_dump()

        self.assertDictEqual(expected_dump, computed_dump)
        self.assertTrue(nullable)
        self.assertTrue(unbounded)

    def test_input_optional_array_of_enums_with_default(self):
        cwl_type = WorkflowInputParameter(
            id="some-id",
            type_=[
                "null",
                InputArraySchema(
                    type_="array",
                    items=InputEnumSchema(type_="enum", symbols=["sym-a", "sym-b"]),
                ),
            ],
            default=["sym-a"],
        )

        # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
        nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
            cwl_type.type_,
            default=cwl_type.default,
            format=cwl_type.format,
            nullable=cwl_type.default is not None,
        )

        expected_schema = Schema(
            type="array",
            default=["sym-a"],
            nullable=True,
            minItems=1,
            items=Schema(
                type="string",
                format=cwl_type.format,
                enum=["sym-a", "sym-b"],
            ),
        )

        expected_dump = expected_schema.model_dump()
        computed_dump = computed_schema.model_dump()

        self.assertDictEqual(expected_dump, computed_dump)
        self.assertTrue(nullable)
        self.assertTrue(unbounded)

    def test_input_enum_without_default(self):
        cwl_type = WorkflowInputParameter(
            id="some-id",
            type_=InputEnumSchema(type_="enum", symbols=["sym-a", "sym-b"]),
        )

        # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
        nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
            cwl_type.type_,
            default=cwl_type.default,
            format=cwl_type.format,
            nullable=cwl_type.default is not None,
        )

        expected_schema = Schema(
            type="string",
            default=cwl_type.default,
            nullable=cwl_type.default is not None,
            enum=["sym-a", "sym-b"],
        )

        expected_dump = expected_schema.model_dump()
        computed_dump = computed_schema.model_dump()

        self.assertDictEqual(expected_dump, computed_dump)
        self.assertFalse(nullable)
        self.assertFalse(unbounded)

    def test_input_enum_with_default(self):
        cwl_type = WorkflowInputParameter(
            id="some-id",
            type_=InputEnumSchema(type_="enum", symbols=["sym-a", "sym-b"]),
            default="sym-a",
        )

        # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
        nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
            cwl_type.type_,
            default=cwl_type.default,
            format=cwl_type.format,
            nullable=cwl_type.default is not None,
        )

        expected_schema = Schema(
            type="string",
            default=cwl_type.default,
            nullable=cwl_type.default is not None,
            enum=["sym-a", "sym-b"],
        )

        expected_dump = expected_schema.model_dump()
        computed_dump = computed_schema.model_dump()

        self.assertDictEqual(expected_dump, computed_dump)
        self.assertTrue(nullable)
        self.assertFalse(unbounded)

    def test_input_record_throws_error(self):
        with self.assertRaises(NotImplementedError):
            cwl_type = WorkflowInputParameter(
                id="some-id",
                type_=InputRecordSchema(type_="placeholder"),
            )

            # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
            nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
                cwl_type.type_,
                default=cwl_type.default,
                format=cwl_type.format,
                nullable=cwl_type.default is not None,
            )

    def test_input_array_of_records_throws_error(self):
        with self.assertRaises(NotImplementedError):
            cwl_type = WorkflowInputParameter(
                id="some-id",
                type_=InputArraySchema(
                    type_="array", items=InputRecordSchema(type_="placeholder")
                ),
            )

            # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
            nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
                cwl_type.type_,
                default=cwl_type.default,
                format=cwl_type.format,
                nullable=cwl_type.default is not None,
            )

    def test_input_record_of_records_throws_error(self):
        with self.assertRaises(NotImplementedError):
            cwl_type = WorkflowInputParameter(
                id="some-id",
                type_=InputRecordSchema(type_=InputRecordSchema(type_="placeholder")),
            )

            # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
            nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
                cwl_type.type_,
                default=cwl_type.default,
                format=cwl_type.format,
                nullable=cwl_type.default is not None,
            )

    def test_output_cwltypes(self):
        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type = WorkflowOutputParameter(id="some-id", type_=key)

                # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
                nullable, unbounded, computed_schema = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type.type_,
                        format=cwl_type.format,
                    )
                )

                expected_schema = Schema(
                    type=value.get("ogc_type"),
                    contentMediaType=cwl_type.format,
                    nullable=False,
                    format=value.get("format"),
                )

                expected_dump = expected_schema.model_dump()
                computed_dump = computed_schema.model_dump()

                self.assertDictEqual(expected_dump, computed_dump)
                self.assertFalse(nullable)
                self.assertFalse(unbounded)

    def test_output_optional_cwltypes(self):
        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type = WorkflowOutputParameter(id="some-id", type_=["null", key])

                # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
                nullable, unbounded, computed_schema = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type.type_,
                        format=cwl_type.format,
                    )
                )

                expected_schema = Schema(
                    type=value.get("ogc_type"),
                    contentMediaType=cwl_type.format,
                    nullable=True,
                    format=value.get("format"),
                )

                expected_dump = expected_schema.model_dump()
                computed_dump = computed_schema.model_dump()

                self.assertDictEqual(expected_dump, computed_dump)
                self.assertTrue(nullable)
                self.assertFalse(unbounded)

    def test_output_optional_cwltypes_order_invariant(self):
        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type_1 = WorkflowOutputParameter(id="some-id", type_=["null", key])
                cwl_type_2 = WorkflowOutputParameter(id="some-id", type_=[key, "null"])

                # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
                nullable_1, unbounded_1, computed_schema_1 = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type_1.type_,
                        format=cwl_type_1.format,
                    )
                )
                nullable_2, unbounded_2, computed_schema_2 = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type_2.type_,
                        format=cwl_type_2.format,
                        nullable=True,
                    )
                )

                computed_dump_1 = computed_schema_1.model_dump()
                computed_dump_2 = computed_schema_2.model_dump()

                self.assertDictEqual(computed_dump_1, computed_dump_2)
                self.assertTrue(nullable_1)
                self.assertFalse(unbounded_1)
                self.assertEqual(nullable_1, nullable_2)
                self.assertEqual(unbounded_1, unbounded_2)

    def test_output_array_of_cwltypes(self):
        self.maxDiff = None

        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type = WorkflowOutputParameter(
                    id="some-id", type_=OutputArraySchema(type_="array", items=key)
                )

                # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
                nullable, unbounded, computed_schema = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type.type_,
                        format=cwl_type.format,
                    )
                )

                expected_schema = Schema(
                    type="array",
                    nullable=False,
                    minItems=1,
                    items=Schema(
                        type=value.get("ogc_type"),
                        contentMediaType=cwl_type.format,
                        format=value.get("format"),
                    ),
                )

                expected_dump = expected_schema.model_dump()
                computed_dump = computed_schema.model_dump()

                self.assertDictEqual(expected_dump, computed_dump)
                self.assertFalse(nullable)
                self.assertTrue(unbounded)

    def test_output_optional_array_of_cwltypes(self):
        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type = WorkflowOutputParameter(
                    id="some-id",
                    type_=["null", OutputArraySchema(type_="array", items=key)],
                )

                nullable, unbounded, computed_schema = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type.type_,
                        format=cwl_type.format,
                    )
                )

                expected_schema = Schema(
                    type="array",
                    nullable=True,
                    minItems=1,
                    items=Schema(
                        type=value.get("ogc_type"),
                        contentMediaType=cwl_type.format,
                        format=value.get("format"),
                    ),
                )

                expected_dump = expected_schema.model_dump()
                computed_dump = computed_schema.model_dump()

                self.assertDictEqual(expected_dump, computed_dump)
                self.assertTrue(nullable)
                self.assertTrue(unbounded)

    def test_output_array_of_enums(self):
        cwl_type = WorkflowOutputParameter(
            id="some-id",
            type_=OutputArraySchema(
                type_="array",
                items=OutputEnumSchema(type_="enum", symbols=["sym-a", "sym-b"]),
            ),
        )

        # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
        nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
            cwl_type.type_,
            format=cwl_type.format,
        )

        expected_schema = Schema(
            type="array",
            nullable=False,
            minItems=1,
            items=Schema(
                type="string",
                format=cwl_type.format,
                enum=["sym-a", "sym-b"],
            ),
        )

        expected_dump = expected_schema.model_dump()
        computed_dump = computed_schema.model_dump()

        self.assertDictEqual(expected_dump, computed_dump)
        self.assertFalse(nullable)
        self.assertTrue(unbounded)

    def test_output_optional_array_of_enums(self):
        cwl_type = WorkflowOutputParameter(
            id="some-id",
            type_=[
                "null",
                OutputArraySchema(
                    type_="array",
                    items=OutputEnumSchema(type_="enum", symbols=["sym-a", "sym-b"]),
                ),
            ],
        )

        # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
        nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
            cwl_type.type_,
            format=cwl_type.format,
        )

        expected_schema = Schema(
            type="array",
            nullable=True,
            minItems=1,
            items=Schema(
                type="string",
                format=cwl_type.format,
                enum=["sym-a", "sym-b"],
            ),
        )

        expected_dump = expected_schema.model_dump()
        computed_dump = computed_schema.model_dump()

        self.assertDictEqual(expected_dump, computed_dump)
        self.assertTrue(nullable)
        self.assertTrue(unbounded)

    def test_output_enum(self):
        cwl_type = WorkflowOutputParameter(
            id="some-id",
            type_=OutputEnumSchema(type_="enum", symbols=["sym-a", "sym-b"]),
        )

        # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
        nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
            cwl_type.type_,
            format=cwl_type.format,
        )

        expected_schema = Schema(
            type="string",
            nullable=False,
            enum=["sym-a", "sym-b"],
        )

        expected_dump = expected_schema.model_dump()
        computed_dump = computed_schema.model_dump()

        self.assertDictEqual(expected_dump, computed_dump)
        self.assertFalse(nullable)
        self.assertFalse(unbounded)

    def test_output_optional_enum(self):
        cwl_type = WorkflowOutputParameter(
            id="some-id",
            type_=[
                "null",
                OutputEnumSchema(type_="enum", symbols=["sym-a", "sym-b"]),
            ],
        )

        # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
        nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
            cwl_type.type_,
            format=cwl_type.format,
        )

        expected_schema = Schema(
            type="string",
            nullable=True,
            enum=["sym-a", "sym-b"],
        )

        expected_dump = expected_schema.model_dump()
        computed_dump = computed_schema.model_dump()

        self.assertDictEqual(expected_dump, computed_dump)
        self.assertTrue(nullable)
        self.assertFalse(unbounded)

    def test_output_record_throws_error(self):
        with self.assertRaises(NotImplementedError):
            cwl_type = WorkflowOutputParameter(
                id="some-id",
                type_=OutputRecordSchema(type_="placeholder"),
            )

            # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
            nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
                cwl_type.type_,
                format=cwl_type.format,
            )

    def test_output_array_of_records_throws_error(self):
        with self.assertRaises(NotImplementedError):
            cwl_type = WorkflowOutputParameter(
                id="some-id",
                type_=OutputArraySchema(
                    type_="array", items=OutputRecordSchema(type_="placeholder")
                ),
            )

            # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
            nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
                cwl_type.type_,
                format=cwl_type.format,
            )

    def test_output_record_of_records_throws_error(self):
        with self.assertRaises(NotImplementedError):
            cwl_type = WorkflowOutputParameter(
                id="some-id",
                type_=OutputRecordSchema(type_=OutputRecordSchema(type_="placeholder")),
            )

            # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
            nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
                cwl_type.type_,
                format=cwl_type.format,
            )


# FIXME: this belongs to EoapProcess test class as the conversion is done by a class method
# construct classes manually AND their CWL format as dictionary; compare __pydantic_fields__ attributes


class ProcessModelNoDefaults(BaseModel):
    flag_value: bool
    int_value: int
    long_value: int
    float_value: float
    double_value: float
    string_value: str
    file_value: File
    directory_value: Directory
    array_int_value: list[int]
    array_file_value: list[File]
    array_array_file_value: list[list[File]]
    enum_value: Literal["value-1", "value-2"]


class ProcessModelsWithDefaults(BaseModel):
    flag_value: bool = Field(True)
    int_value: int = Field(42)
    long_value: int = Field(42_000_000)
    float_value: float = Field(3.141)
    double_value: float = Field(3.141e308)
    string_value: str = Field("Hello, World")
    file_value: File = Field(
        File(class_="File", path="https://example.com/some/remote/resource.txt")
    )
    directory_value: Directory = Field(
        Directory(class_="Directory", path="https://example.com/some/remote/resource/")
    )
    array_int_value: list[int] = Field([1, 2, 3])
    array_file_value: list[File] = Field(
        [
            File(class_="File", path="https://example.com/some/remote/resource.txt"),
        ]
    )
    array_array_file_value: list[list[File]] = Field(
        [
            [
                File(
                    class_="File", path="https://example.com/some/remote/resource.txt"
                ),
            ]
        ]
    )
    enum_value: Literal["value-1", "value-2"] = Field("value-1")


class ModelClassGenerationTest(TestCase):
    def test_process_model_without_defaults(self):
        self.maxDiff = None
        CwlInputsNoDefault = [
            WorkflowInputParameter(id="flag_value", type_="boolean"),
            WorkflowInputParameter(id="int_value", type_="int"),
            WorkflowInputParameter(id="long_value", type_="long"),
            WorkflowInputParameter(id="float_value", type_="float"),
            WorkflowInputParameter(id="double_value", type_="double"),
            WorkflowInputParameter(id="string_value", type_="string"),
            WorkflowInputParameter(id="file_value", type_="File"),
            WorkflowInputParameter(id="directory_value", type_="Directory"),
            WorkflowInputParameter(
                id="array_int_value", type_=InputArraySchema(type_="array", items="int")
            ),
            WorkflowInputParameter(
                id="array_file_value",
                type_=InputArraySchema(type_="array", items="File"),
            ),
            WorkflowInputParameter(
                id="array_array_file_value",
                type_=InputArraySchema(
                    type_="array", items=InputArraySchema(type_="array", items="File")
                ),
            ),
            WorkflowInputParameter(
                id="enum_value",
                type_=InputEnumSchema(type_="enum", symbols=["value-1", "value-2"]),
            ),
        ]

        DynamicProcessModel = cwl_inputs_to_model_class(CwlInputsNoDefault)

        static_fields = ProcessModelNoDefaults.__pydantic_fields__
        dynamic_fields = DynamicProcessModel.__pydantic_fields__

        self.assertEqual(static_fields.keys(), dynamic_fields.keys())

        # FieldInfo has no __eq__ or __hash__
        for k in static_fields.keys():
            with self.subTest(k=k):
                self.assertDictEqual(
                    static_fields[k].asdict(), dynamic_fields[k].asdict()
                )

    def test_process_model_with_defaults(self):
        self.maxDiff = None
        CwlInputsWithDefault = [
            WorkflowInputParameter(id="flag_value", type_="boolean", default=True),
            WorkflowInputParameter(id="int_value", type_="int", default=42),
            WorkflowInputParameter(id="long_value", type_="long", default=42_000_000),
            WorkflowInputParameter(id="float_value", type_="float", default=3.141),
            WorkflowInputParameter(
                id="double_value", type_="double", default=3.141e308
            ),
            WorkflowInputParameter(
                id="string_value", type_="string", default="Hello, World"
            ),
            WorkflowInputParameter(
                id="file_value",
                type_="File",
                default=CwlFile(path="https://example.com/some/remote/resource.txt"),
            ),
            WorkflowInputParameter(
                id="directory_value",
                type_="Directory",
                default=CwlDirectory(path="https://example.com/some/remote/resource/"),
            ),
            WorkflowInputParameter(
                id="array_int_value",
                type_=InputArraySchema(type_="array", items="int"),
                default=[1, 2, 3],
            ),
            WorkflowInputParameter(
                id="array_file_value",
                type_=InputArraySchema(type_="array", items="File"),
                default=[
                    CwlFile(path="https://example.com/some/remote/resource.txt"),
                ],
            ),
            WorkflowInputParameter(
                id="array_array_file_value",
                type_=InputArraySchema(
                    type_="array", items=InputArraySchema(type_="array", items="File")
                ),
                default=[
                    [
                        CwlFile(path="https://example.com/some/remote/resource.txt"),
                    ]
                ],
            ),
            WorkflowInputParameter(
                id="enum_value",
                type_=InputEnumSchema(type_="enum", symbols=["value-1", "value-2"]),
                default="value-1",
            ),
        ]

        DynamicProcessModel = cwl_inputs_to_model_class(CwlInputsWithDefault)

        static_fields = ProcessModelsWithDefaults.__pydantic_fields__
        dynamic_fields = DynamicProcessModel.__pydantic_fields__

        self.assertEqual(static_fields.keys(), dynamic_fields.keys())

        # FieldInfo has no __eq__ or __hash__
        for k in static_fields.keys():
            with self.subTest(k=k):
                self.assertDictEqual(
                    static_fields[k].asdict(), dynamic_fields[k].asdict()
                )


class PydanticResolvingTest(TestCase):
    def test_boolean_without_default(self):
        self.assertEqual(bool, _resolve_to_pydantic_tuple("boolean"))

    def test_int_without_default(self):
        self.assertEqual(int, _resolve_to_pydantic_tuple("int"))

    def test_long_without_default(self):
        self.assertEqual(int, _resolve_to_pydantic_tuple("long"))

    def test_float_without_default(self):
        self.assertEqual(float, _resolve_to_pydantic_tuple("float"))

    def test_double_without_default(self):
        self.assertEqual(float, _resolve_to_pydantic_tuple("double"))

    def test_string_without_default(self):
        self.assertEqual(str, _resolve_to_pydantic_tuple("string"))

    def test_file_without_default(self):
        self.assertEqual(File, _resolve_to_pydantic_tuple("File"))

    def test_directory_without_default(self):
        self.assertEqual(Directory, _resolve_to_pydantic_tuple("Directory"))

    def test_list_boolean_without_default(self):
        self.assertEqual(
            list[bool],
            _resolve_to_pydantic_tuple(
                InputArraySchema(items="boolean", type_="array")
            ),
        )

    def test_list_int_without_default(self):
        self.assertEqual(
            list[int],
            _resolve_to_pydantic_tuple(InputArraySchema(items="int", type_="array")),
        )

    def test_list_long_without_default(self):
        self.assertEqual(
            list[int],
            _resolve_to_pydantic_tuple(InputArraySchema(items="long", type_="array")),
        )

    def test_list_float_without_default(self):
        self.assertEqual(
            list[float],
            _resolve_to_pydantic_tuple(InputArraySchema(items="float", type_="array")),
        )

    def test_list_double_without_default(self):
        self.assertEqual(
            list[float],
            _resolve_to_pydantic_tuple(InputArraySchema(items="double", type_="array")),
        )

    def test_list_string_without_default(self):
        self.assertEqual(
            list[str],
            _resolve_to_pydantic_tuple(InputArraySchema(items="string", type_="array")),
        )

    def test_list_file_without_default(self):
        self.assertEqual(
            list[File],
            _resolve_to_pydantic_tuple(InputArraySchema(items="File", type_="array")),
        )

    def test_list_directory_without_default(self):
        self.assertEqual(
            list[Directory],
            _resolve_to_pydantic_tuple(
                InputArraySchema(items="Directory", type_="array")
            ),
        )

    def test_list_list_boolean_without_default(self):
        self.assertEqual(
            list[list[bool]],
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="boolean", type_="array"),
                    type_="array",
                )
            ),
        )

    def test_list_list_int_without_default(self):
        self.assertEqual(
            list[list[int]],
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="int", type_="array"), type_="array"
                )
            ),
        )

    def test_list_list_long_without_default(self):
        self.assertEqual(
            list[list[int]],
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="long", type_="array"), type_="array"
                )
            ),
        )

    def test_list_list_float_without_default(self):
        self.assertEqual(
            list[list[float]],
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="float", type_="array"), type_="array"
                )
            ),
        )

    def test_list_list_double_without_default(self):
        self.assertEqual(
            list[list[float]],
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="double", type_="array"), type_="array"
                )
            ),
        )

    def test_list_list_string_without_default(self):
        self.assertEqual(
            list[list[str]],
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="string", type_="array"), type_="array"
                )
            ),
        )

    def test_list_list_file_without_default(self):
        self.assertEqual(
            list[list[File]],
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="File", type_="array"), type_="array"
                )
            ),
        )

    def test_list_list_directory_without_default(self):
        self.assertEqual(
            list[list[Directory]],
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="Directory", type_="array"),
                    type_="array",
                )
            ),
        )

    def test_boolean_with_default(self):
        self.assertEqual(
            (bool, False), _resolve_to_pydantic_tuple("boolean", arg_default=False)
        )

    def test_int_with_default(self):
        self.assertEqual((int, 42), _resolve_to_pydantic_tuple("int", arg_default=42))

    def test_long_with_default(self):
        self.assertEqual(
            (int, 42_000_000),
            _resolve_to_pydantic_tuple("long", arg_default=42_000_000),
        )

    def test_float_with_default(self):
        self.assertEqual(
            (float, 3.141), _resolve_to_pydantic_tuple("float", arg_default=3.141)
        )

    def test_double_with_default(self):
        self.assertEqual(
            (float, 3.141e20),
            _resolve_to_pydantic_tuple("double", arg_default=3.141e20),
        )

    def test_string_with_default(self):
        self.assertEqual(
            (str, "Hello, World"),
            _resolve_to_pydantic_tuple("string", arg_default="Hello, World"),
        )

    def test_file_with_default(self):
        self.assertEqual(
            (File, File(location="https://fileserver.example.com/path/to/file.txt")),
            _resolve_to_pydantic_tuple(
                "File",
                arg_default=CwlFile(
                    location="https://fileserver.example.com/path/to/file.txt"
                ),
            ),
        )

    def test_directory_with_default(self):
        self.assertEqual(
            (
                Directory,
                Directory(
                    location="https://directoryerver.example.com/path/to/directory"
                ),
            ),
            _resolve_to_pydantic_tuple(
                "Directory",
                arg_default=CwlDirectory(
                    location="https://directoryerver.example.com/path/to/directory"
                ),
            ),
        )

    def test_list_boolean_with_default(self):
        self.assertEqual(
            (
                list[bool],
                [
                    False,
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(items="boolean", type_="array"),
                arg_default=[
                    False,
                ],
            ),
        )

    def test_list_int_with_default(self):
        self.assertEqual(
            (
                list[int],
                [
                    42,
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(items="int", type_="array"),
                arg_default=[
                    42,
                ],
            ),
        )

    def test_list_long_with_default(self):
        self.assertEqual(
            (
                list[int],
                [
                    42_000_000,
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(items="long", type_="array"),
                arg_default=[
                    42_000_000,
                ],
            ),
        )

    def test_list_float_with_default(self):
        self.assertEqual(
            (
                list[float],
                [
                    3.141,
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(items="float", type_="array"),
                arg_default=[
                    3.141,
                ],
            ),
        )

    def test_list_double_with_default(self):
        self.assertEqual(
            (
                list[float],
                [
                    3.141e20,
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(items="double", type_="array"),
                arg_default=[
                    3.141e20,
                ],
            ),
        )

    def test_list_string_with_default(self):
        self.assertEqual(
            (
                list[str],
                [
                    "Hello, World",
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(items="string", type_="array"),
                arg_default=[
                    "Hello, World",
                ],
            ),
        )

    def test_list_file_with_default(self):
        self.assertEqual(
            (
                list[File],
                [
                    File(location="https://fileserver.example.com/path/to/file.txt"),
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items="File",
                    type_="array",
                ),
                arg_default=[
                    CwlFile(location="https://fileserver.example.com/path/to/file.txt"),
                ],
            ),
        )

    def test_list_directory_with_default(self):
        self.assertEqual(
            (
                list[Directory],
                [
                    Directory(
                        location="https://directoryerver.example.com/path/to/directory"
                    ),
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items="Directory",
                    type_="array",
                ),
                arg_default=[
                    CwlDirectory(
                        location="https://directoryerver.example.com/path/to/directory"
                    ),
                ],
            ),
        )

    def test_list_list_boolean_with_default(self):
        self.assertEqual(
            (
                list[list[bool]],
                [
                    [
                        False,
                    ],
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="boolean", type_="array"),
                    type_="array",
                ),
                arg_default=[
                    [
                        False,
                    ],
                ],
            ),
        )

    def test_list_list_int_with_default(self):
        self.assertEqual(
            (
                list[list[int]],
                [
                    [
                        42,
                    ],
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="int", type_="array"),
                    type_="array",
                ),
                arg_default=[
                    [
                        42,
                    ],
                ],
            ),
        )

    def test_list_list_long_with_default(self):
        self.assertEqual(
            (
                list[list[int]],
                [
                    [
                        42_000_000,
                    ],
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="long", type_="array"),
                    type_="array",
                ),
                arg_default=[
                    [
                        42_000_000,
                    ],
                ],
            ),
        )

    def test_list_list_float_with_default(self):
        self.assertEqual(
            (
                list[list[float]],
                [
                    [
                        3.141,
                    ],
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="float", type_="array"), type_="array"
                ),
                arg_default=[
                    [
                        3.141,
                    ],
                ],
            ),
        )

    def test_list_list_doule_with_default(self):
        self.assertEqual(
            (
                list[list[float]],
                [
                    [
                        3.141e20,
                    ],
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="double", type_="array"), type_="array"
                ),
                arg_default=[
                    [
                        3.141e20,
                    ],
                ],
            ),
        )

    def test_list_list_string_with_default(self):
        self.assertEqual(
            (
                list[list[str]],
                [
                    [
                        "Hello, World",
                    ],
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="string", type_="array"), type_="array"
                ),
                arg_default=[
                    [
                        "Hello, World",
                    ],
                ],
            ),
        )

    def test_list_list_file_with_default(self):
        self.assertEqual(
            (
                list[list[File]],
                [
                    [
                        File(
                            location="https://fileserver.example.com/path/to/file.txt"
                        ),
                    ],
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="File", type_="array"), type_="array"
                ),
                arg_default=[
                    [
                        CwlFile(
                            location="https://fileserver.example.com/path/to/file.txt"
                        ),
                    ],
                ],
            ),
        )

    def test_list_list_directory_with_default(self):
        self.assertEqual(
            (
                list[list[Directory]],
                [
                    [
                        Directory(
                            location="https://directoryerver.example.com/path/to/directory"
                        ),
                    ],
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="Directory", type_="array"),
                    type_="array",
                ),
                arg_default=[
                    [
                        CwlDirectory(
                            location="https://directoryerver.example.com/path/to/directory"
                        ),
                    ],
                ],
            ),
        )
