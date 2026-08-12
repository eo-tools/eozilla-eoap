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
        "example_value": True,
        "format": None,
    },
    "int": {
        "ogc_type": "integer",
        "example_value": 2147483647,
        "format": None,
    },
    "long": {
        "ogc_type": "integer",
        "example_value": 9223372036854775807,
        "format": None,
    },
    "float": {
        "ogc_type": "number",
        "example_value": 3.402823e38,
        "format": None,
    },
    "double": {
        "ogc_type": "number",
        "example_value": 1.797693e308,
        "format": None,
    },
    "string": {
        "ogc_type": "string",
        "example_value": "hello, world",
        "format": None,
    },
    "File": {
        "ogc_type": "string",
        "example_value": "https://files.example.com/remote/path/to/some/file.txt",
        "format": "url",
    },
    "Directory": {
        "ogc_type": "string",
        "example_value": "https://catalogs.example.com/remote/path/to/some/STAC/item/",
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
        self.maxDiff = None

        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type = WorkflowInputParameter(id="some-id", type_=key)

                # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
                nullable, unbounded, computed_schema = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type.type_,
                        default=cwl_type.default,
                        format=cwl_type.format,
                        nullable=False,
                    )
                )

                expected_schema = Schema(
                    type=value.get("ogc_type"),
                    default=cwl_type.default,
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
        self.maxDiff = None

        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type = WorkflowInputParameter(
                    id="some-id", type_=key, default=value.get("example_value")
                )

                # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
                nullable, unbounded, computed_schema = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type.type_,
                        default=cwl_type.default,
                        format=cwl_type.format,
                        nullable=False,
                    )
                )

                expected_schema = Schema(
                    type=value.get("ogc_type"),
                    default=cwl_type.default,
                    contentMediaType=cwl_type.format,
                    nullable=False,
                    format=value.get("format"),
                )

                expected_dump = expected_schema.model_dump()
                computed_dump = computed_schema.model_dump()

                self.assertDictEqual(expected_dump, computed_dump)
                self.assertTrue(nullable)
                self.assertFalse(unbounded)

    def test_input_optional_cwltypes_without_default(self):
        self.fail("discussion regarding optional values and presence of defaults")
        self.maxDiff = None

        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type = WorkflowInputParameter(id="some-id", type_=["null", key])

                # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
                nullable, unbounded, computed_schema = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type.type_,
                        default=cwl_type.default,
                        format=cwl_type.format,
                        nullable=True,
                    )
                )

                expected_schema = Schema(
                    type=value.get("ogc_type"),
                    default=cwl_type.default,
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
        # FIXME: discussion regarding optional values and presence of defaults
        self.maxDiff = None

        for key, value in SIMPLE_TYPE_MAPPINGS.items():
            with self.subTest(key=key, vlaue=value):
                cwl_type_1 = WorkflowInputParameter(id="some-id", type_=["null", key])
                cwl_type_2 = WorkflowInputParameter(id="some-id", type_=[key, "null"])

                # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
                nullable_1, unbounded_1, computed_schema_1 = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type_1.type_,
                        default=cwl_type_1.default,
                        format=cwl_type_1.format,
                        nullable=True,
                    )
                )
                nullable_2, unbounded_2, computed_schema_2 = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type_2.type_,
                        default=cwl_type_2.default,
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

    def test_input_nullable_cwltypes_must_have_defaults(self):
        self.fail("`test_input_nullable_cwltypes_must_have_defaults` not implemented")

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
                        default=cwl_type.default,
                        format=cwl_type.format,
                        nullable=False,
                    )
                )

                expected_schema = Schema(
                    type="array",
                    default=cwl_type.default,  # FIXME: for File and Directory, the default is attached to the items, not the array!
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
                    default=value.get("example_value"),
                )

                # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
                nullable, unbounded, computed_schema = (
                    _resolve_ogc_schema_from_cwl_utils(
                        cwl_type.type_,
                        default=cwl_type.default,
                        format=cwl_type.format,
                        nullable=False,
                    )
                )

                expected_schema = Schema(
                    type="array",
                    default=cwl_type.default,  # FIXME: for File and Directory, the default is attached to the items, not the array!
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
            default=cwl_type.default,
            format=cwl_type.format,
            nullable=False,
        )

        expected_schema = Schema(
            type="array",
            default=cwl_type.default,
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
            default="sym-a",
        )

        # TODO: the format parameter is somewhat useless I suppose?! Or it should be set at all times!
        nullable, unbounded, computed_schema = _resolve_ogc_schema_from_cwl_utils(
            cwl_type.type_,
            default=cwl_type.default,
            format=cwl_type.format,
            nullable=False,
        )

        expected_schema = Schema(
            type="array",
            default=cwl_type.default,
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
            nullable=False,
        )

        expected_schema = Schema(
            type="string",
            default=cwl_type.default,
            nullable=False,
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
            nullable=False,
        )

        expected_schema = Schema(
            type="string",
            default=cwl_type.default,
            nullable=False,
            enum=["sym-a", "sym-b"],
        )

        expected_dump = expected_schema.model_dump()
        computed_dump = computed_schema.model_dump()

        self.assertDictEqual(expected_dump, computed_dump)
        self.assertFalse(nullable)
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
                nullable=False,
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
                nullable=False,
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
                nullable=False,
            )

    # Inputs
    ## test plain CWLTypes: null, boolean, int, long, float, double, string, File, Directory ✔
    ##   -> testing of forwarding of format field should also be tested
    ## test optional plain CWLTypes: boolean, int, long, float, double, string, File, Directory ✔
    ##   -> should also include that it doesn't matter whether it's ['null', T] or [T, 'null'] ✔
    ##   -> do I test whether optional 'null' fails or succeeds?
    ##   -> nullable must have default
    ## test array of plain CWLTypes: null, boolean, int, long, float, double, string, File, Directory ✔
    ## test input array of plain CWLTypes, enums
    ## test optional array of plain CWLTypes, enums
    ## test nested array
    ## test input enum
    ## test optional enum
    ## test everything above with default values!

    ## test unsupported record ✔
    ## test optional unsupported record ✔
    ## test nested unsupported record ✔

    # Outputs
    ## test plain CWLTypes: null, boolean, int, long, float, double, string, File, Directory
    ## test optional plain CWLTypes: null, boolean, int, long, float, double, string, File, Directory
    ##   -> should also include that it doesn't matter whether it's ['null', T] or [T, 'null']
    ##   -> do I test whether optional 'null' fails or succeeds?
    ## test array of plain CWLTypes: null, boolean, int, long, float, double, string, File, Directory
    ## test input array of plain CWLTypes, enums
    ## test optional array of plain CWLTypes, enums
    ## test nested array
    ## test input enum
    ## test optional enum
    ## test nested enum <- is this even possible? I don't think so
    ## test everything above with default values!

    ## test unsupported record
    ## test optional unsupported record
    ## test nested unsupported record <- is this even possible?

    # NOTE: Fix tests for input paramter and then simply copy, replace, paste for output stuff; probably easier than fixing things in two places


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
    enum_value: Literal["value-1", "value-2"]


class ProcessModelsWithDefaults(BaseModel):
    flag_value: bool = Field(True)
    int_value: int = Field(42)
    long_value: int = Field(42000000000000000000)
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
    enum_value: Literal["value-1", "value-2"] = Field("value-1")


class ModelClassGenerationTest(TestCase):
    def test_process_model_without_defaults(self):
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
                id="enum_value",
                type_=InputEnumSchema(type_="enum", symbols=["value-1", "value-2"]),
            ),
        ]

        DynamicProcessModel = cwl_inputs_to_model_class(CwlInputsNoDefault)

        self.assertDictEqual(
            ProcessModelNoDefaults.__pydantic_fields__,
            DynamicProcessModel.__pydantic_fields__,
        )

    def test_process_model_with_defaults(self):
        self.maxDiff = None
        CwlInputsWithDefault = [
            WorkflowInputParameter(id="flag_value", type_="boolean", default=True),
            WorkflowInputParameter(id="int_value", type_="int", default=42),
            WorkflowInputParameter(
                id="long_value", type_="long", default=42000000000000000000
            ),
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
                id="enum_value",
                type_=InputEnumSchema(type_="enum", symbols=["value-1", "value-2"]),
                default="value-1",
            ),
        ]

        DynamicProcessModel = cwl_inputs_to_model_class(CwlInputsWithDefault)

        self.assertDictEqual(
            ProcessModelsWithDefaults.__pydantic_fields__,
            DynamicProcessModel.__pydantic_fields__,
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
            (File, "https://fileserver.example.com/path/to/file.txt"),
            _resolve_to_pydantic_tuple(
                "File", arg_default="https://fileserver.example.com/path/to/file.txt"
            ),
        )

    def test_directory_with_default(self):
        self.assertEqual(
            (Directory, "https://directoryerver.example.com/path/to/directory"),
            _resolve_to_pydantic_tuple(
                "Directory",
                arg_default="https://directoryerver.example.com/path/to/directory",
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
                    "https://fileserver.example.com/path/to/file.txt",
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items="File",
                    type_="array",
                ),
                arg_default=[
                    "https://fileserver.example.com/path/to/file.txt",
                ],
            ),
        )

    def test_list_directory_with_default(self):
        self.assertEqual(
            (
                list[Directory],
                [
                    "https://directoryerver.example.com/path/to/directory",
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items="Directory",
                    type_="array",
                ),
                arg_default=[
                    "https://directoryerver.example.com/path/to/directory",
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
                        "https://fileserver.example.com/path/to/file.txt",
                    ],
                ],
            ),
            _resolve_to_pydantic_tuple(
                InputArraySchema(
                    items=InputArraySchema(items="File", type_="array"), type_="array"
                ),
                arg_default=[
                    [
                        "https://fileserver.example.com/path/to/file.txt",
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
                        "https://directoryerver.example.com/path/to/directory",
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
                        "https://directoryerver.example.com/path/to/directory",
                    ],
                ],
            ),
        )
