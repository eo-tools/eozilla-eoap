from typing import Literal, Tuple

from cwl_utils import parser
from gavicore.models import Schema
from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

FLAT_TYPE_MAPPING_TO_OGC = {
    "boolean": "boolean",
    "int": "integer",
    "long": "integer",
    "float": "number",
    "double": "number",
    "string": "string",
}


# NOTE: Taken from cwl2/models module from mr. propper repo
class File(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        use_enum_values=True,
        serialize_by_alias=True,
    )

    class_: Literal["File"] = Field("File", alias="class")
    location: str | None = None
    path: str | None = None
    basename: str | None = None
    dirname: str | None = None
    nameroot: str | None = None
    nameext: str | None = None
    checksum: str | None = None
    size: int | None = None
    secondary_files: list[File | Directory] | None = Field(None, alias="secondaryFiles")
    format: str | None = None
    contents: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_minimal_file(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"class": "File", "path": data}

        if isinstance(data, list):
            return [{"class": "File", "path": x} for x in data]

        return data


# NOTE: Taken from cwl2/models module from mr. propper repo
class Directory(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        use_enum_values=True,
        serialize_by_alias=True,
    )

    class_: Literal["Directory"] = Field("Directory", alias="class")
    location: str | None = None
    path: str | None = None
    basename: str | None = None
    listing: list[File | Directory] | None = Field(None)

    @model_validator(mode="before")
    @classmethod
    def normalize_minimal_directory(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"class": "Directory", "path": data}

        if isinstance(data, list):
            return [{"class": "Directory", "path": x} for x in data]

        return data


def _resolve_ogc_schema_from_cwl_utils(
    cwl_type,
    *,
    default: Any | None = None,
    format: str | None = None,
    nullable: bool = False,
) -> Tuple[bool, bool, Schema]:
    if isinstance(cwl_type, str):
        if cwl_type == "File":
            return (
                nullable,
                False,
                Schema(
                    type="string",
                    nullable=nullable,
                    default=default,
                    contentMediaType=format,
                ),
            )
        elif cwl_type == "Directory":
            return (
                nullable,
                False,
                Schema(
                    type="string",
                    nullable=nullable,
                    default=default,
                    contentMediaType=format,
                    format="uri",
                ),
            )
        else:
            return (
                nullable,
                False,
                Schema(
                    type=FLAT_TYPE_MAPPING_TO_OGC[cwl_type],
                    nullable=nullable,
                    default=default,
                ),
            )
    elif isinstance(cwl_type, list):
        assert cwl_type[0] == "null" or cwl_type[1] == "null", (
            "Python list that doesn't represent an optional argument"
        )

        content = cwl_type[0] if cwl_type[1] == "null" else cwl_type[1]

        _, u, s = _resolve_ogc_schema_from_cwl_utils(
            content, nullable=True, default=default, format=format
        )
        return True, u, s
    elif isinstance(cwl_type, parser.InputEnumSchema) or isinstance(
        cwl_type, parser.OutputEnumSchema
    ):
        return (
            nullable,
            False,
            Schema(
                type="string",
                nullable=nullable,
                enum=cwl_type.symbols,
                default=default,
            ),
        )
    elif isinstance(cwl_type, parser.InputArraySchema) or isinstance(
        cwl_type, parser.OutputArraySchema
    ):
        _, _, s = _resolve_ogc_schema_from_cwl_utils(
            cwl_type.items,
            nullable=nullable,
            default=default,
            format=format,
        )
        return (
            nullable,
            True,
            Schema(type="array", minItems=o if nullable else 1, items=s),
        )
    else:
        raise NotImplementedError(f"Schema conversion not implemented for {cwl_type!r}")


FLAT_TYPE_MAPPING_TO_PYTHON = {
    "boolean": bool,
    "int": int,
    "long": int,
    "float": float,
    "double": float,
    "string": str,
}


def cwl_inputs_to_model_class(
    inputs: list[parser.WorkflowInputParameter],
) -> type[BaseModel]:
    arguments: Dict[str, Any] = {}

    if isinstance(inputs, list):
        for input_ in inputs:
            n_ = input_.id.rsplit("/", 1)[-1]
            t_ = input_.type_
            d_ = input_.default

            arguments[n_] = _resolve_to_pydantic_tuple(t_, d_)

    model_class: type[BaseModel] = create_model(
        "ProcessInputs",
        **arguments,
    )

    return model_class


def _resolve_to_pydantic_tuple(
    arg_value, arg_default: Any = None, *, arg_from_array: bool = False
) -> Tuple[type, type] | type:
    if isinstance(arg_value, str):
        if arg_value == "File":
            # NOTE: dismissing `from_array` because defaults are attached to T not L<T> for files/directories
            return (File, arg_default) if arg_default else File
        elif arg_value == "Directory":
            # NOTE: dismissing `from_array` because defaults are attached to T not L<T> for files/directories
            return (Directory, arg_default) if arg_default else Directory
        else:
            return (
                (FLAT_TYPE_MAPPING_TO_PYTHON[arg_value], arg_default)
                if arg_default and not arg_from_array
                else FLAT_TYPE_MAPPING_TO_PYTHON[arg_value]
            )
    elif isinstance(arg_value, list):
        assert arg_value[0] == "null" or arg_value[1] == "null", (
            "Python list that doesn't represent an optional argument"
        )

        content = arg_value[0] if arg_value[1] == "null" else arg_value[1]

        return _resolve_to_pydantic_tuple(
            content, arg_default=arg_default, arg_from_array=False
        )
    elif isinstance(arg_value, parser.InputEnumSchema):
        return (
            (Literal[*arg_value.symbols], arg_default)
            if arg_default and not arg_from_array
            else Literal[*arg_value.symbols]
        )
    elif isinstance(arg_value, parser.InputArraySchema):
        t = _resolve_to_pydantic_tuple(
            arg_value.items, arg_default=arg_default, arg_from_array=True
        )

        return (
            (
                list[t],
                [
                    arg_default
                ],  # TODO: shouldn't the default itself be able to contain a list??!
            )
            if arg_default
            else list[t]
        )
    else:
        raise NotImplementedError(
            f"Schema conversion not implemented for {arg_value!r}"
        )
