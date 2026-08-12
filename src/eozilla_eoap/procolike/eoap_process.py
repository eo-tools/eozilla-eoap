from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Tuple

from cwl_utils import errors, parser
from gavicore.models import (
    DescriptionType,
    InputDescription,
    OutputDescription,
    ProcessDescription,
    Schema,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FileUrl,
    create_model,
    model_validator,
)

from eozilla_eoap.interfaces import Process


@dataclass
class EoapProcess(Process):
    """
    An EOAP process comprises a process description and a link to
    executable code in form of a CWL document.

    Restriction:
        All directories are assumed to contain EO data. There's currently no way to
        stage directories containing non-EO data. While this severely limits generality
        of a compliant server, it is in line with requirement 18 ("The Platform SHALL map
        workflow input parameters of type “Directory” to a GeoJSON feature collection
        with STAC Items in the Process description.")

    Attributes:
        source: URI to CWL file, i.e. the OGC EOAP that this object describes.
        model_class: Pydantic model class for the arguments of `source`.
        description: Process description modeled after
            [OGC API - Processes - Part 1: Core](https://docs.ogc.org/is/18-062r2/18-062r2.html#toc37).
    """

    source: FileUrl | None
    entrypoint: str
    _model_class: type[BaseModel]
    _description: ProcessDescription

    @property
    def model_class(self) -> type[BaseModel]:
        return self._model_class

    @property
    def description(self) -> ProcessDescription:
        return self._description

    @classmethod
    def create(
        cls,
        future_source: Path,
        current_content: dict,
        entrypoint: str | None = None,
    ) -> "EoapProcess":
        id, version, title, description, keywords = cls._extract_process_metadata(
            current_content, entrypoint
        )

        if entrypoint and id != entrypoint:
            # Question to myself: how is this possible again?
            raise ValueError(
                "Specifying an entrypoint different to the id of the entrypoit is not allowed"
            )

        entrypoint = entrypoint or id

        input_description, output_description = cls._extract_cwl_argument_descriptions(
            current_content, entrypoint
        )

        model_class: type[BaseModel] = cls._generate_model_class(
            current_content, entrypoint
        )

        return EoapProcess(
            source=Path(future_source, id + ".cwl").as_uri(),
            entrypoint=entrypoint,
            _model_class=model_class,
            _description=ProcessDescription(
                id=id,
                version=version,
                mutable=True,
                title=title,
                description=description,
                inputs=input_description,
                outputs=output_description,
                keywords=keywords,
            ),
        )

    @classmethod
    def _extract_process_metadata(
        cls, cwl: dict, w: str | None = None
    ) -> Tuple[str, str, str, str]:
        process_entry_node = cls._find_entrypoint(cwl, w)

        # [`cwl_utils`] gobbles metadata, thus using raw dict is required
        namespaces: dict = cwl.get("$namespaces")
        schema_org_key: str = ""

        if namespaces is None:
            raise NamespaceNotFoundError("No namespaces specified")

        for k, v in namespaces.items():
            if v in ["https://schema.org", "https://schema.org/"]:
                schema_org_key = k
                break

        if not schema_org_key:
            raise NamespaceNotFoundError("schema.org namespace not found")

        return (
            process_entry_node.id.split("#", 1)[-1],
            cwl.get(schema_org_key + ":version"),
            process_entry_node.label,
            process_entry_node.doc,
            cwl.get(schema_org_key + ":keywords"),
        )

    @classmethod
    def _extract_cwl_argument_descriptions(
        cls,
        cwl: dict,
        entrypoint: str,
    ) -> Tuple[InputDescription, OutputDescription]:
        process_entry_node: dict = cls._find_entrypoint(cwl, entrypoint)

        inputs_ = cls._get_workflow_input(process_entry_node)
        ogc_conformant_inputs = {}
        for input_ in inputs_:
            assert input_.id, "Anonymous parameters not supported for workflow inputs"

            local_id_tag = input_.id.rsplit("/", 1)[-1]

            description: DescriptionType = DescriptionType(
                title=input_.label, description=input_.doc
            )

            t_ = input_.type_
            d_ = input_.default
            f_: str | None = input_.format

            optional, unbounded, schema = _resolve_ogc_schema_from_cwl_utils(
                t_, default=d_, format=f_, nullable=d_ is not None
            )

            ogc_conformant_inputs[local_id_tag] = InputDescription(
                **description.model_dump(),
                minOccurs=1 if not optional else 0,
                maxOccurs="unbounded" if unbounded else 1,
                schema=schema,
            )

        outputs_ = cls._get_workflow_ouput(process_entry_node)
        ogc_conformant_outputs = {}
        for output_ in outputs_:
            assert output_.id, "Anonymous parameters not supported for workflow outputs"

            local_id_tag = output_.id.rsplit("/", 1)[-1]

            description: DescriptionType = DescriptionType(
                title=output_.label, description=output_.doc
            )

            t_ = output_.type_
            f_: str | None = output_.format

            optional, unbounded, schema = _resolve_ogc_schema_from_cwl_utils(
                t_, default=None, format=f_
            )

            ogc_conformant_outputs[local_id_tag] = OutputDescription(
                **description.model_dump(), schema=schema
            )

        return ogc_conformant_inputs, ogc_conformant_outputs

    @classmethod
    def _generate_model_class(cls, cwl: dict, entrypoint: str) -> type[BaseModel]:
        process_entry_node: dict = cls._find_entrypoint(cwl, entrypoint)

        return cwl_inputs_to_model_class(process_entry_node.inputs)

    @classmethod
    def _find_entrypoint(cls, cwl_dict: dict, w: str | None = None):
        """Extract either the Workflow instance with the id tag given by `w` or,
        if the paramter is None, the first instance of a Workflow object.
        """
        if w is not None:
            try:
                loaded_cwl = parser.load_document(cwl_dict, id_=w)
            except errors.GraphTargetMissingException as e:
                raise EntrypointNotFoundError from e
            else:
                return loaded_cwl
        else:
            loaded_cwl = parser.load_document(cwl_dict, load_all=True)

            for cwl_node in loaded_cwl:
                if cwl_node.class_ == "Workflow":
                    return cwl_node

        raise EntrypointNotFoundError("No workflow entrypoint found.")

    @classmethod
    def _get_workflow_input(cls, cwl_node):
        return cwl_node.inputs

    @classmethod
    def _get_workflow_ouput(cls, cwl_node):
        return cwl_node.outputs


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
    secondary_files: list[File | Directory] | None = Field(None, alias="secondaryFiles")  # noqa: F821
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
    listing: list[File | Directory] | None = Field(None)  # noqa: F821

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
                    format="url",
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
                    format="url",
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
        normalized_symbols: List = [x.rsplit("/", 1)[-1] for x in cwl_type.symbols]
        return (
            nullable,
            False,
            Schema(
                type="string",
                nullable=nullable,
                enum=normalized_symbols,
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
            Schema(type="array", minItems=0 if nullable else 1, items=s),
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
            return (File, arg_default) if arg_default is not None else File
        elif arg_value == "Directory":
            # NOTE: dismissing `from_array` because defaults are attached to T not L<T> for files/directories
            return (Directory, arg_default) if arg_default is not None else Directory
        else:
            return (
                (FLAT_TYPE_MAPPING_TO_PYTHON[arg_value], arg_default)
                if arg_default is not None and not arg_from_array
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
            if arg_default is not None and not arg_from_array
            else Literal[*arg_value.symbols]
        )
    elif isinstance(arg_value, parser.InputArraySchema):
        t = _resolve_to_pydantic_tuple(
            arg_value.items, arg_default=arg_default, arg_from_array=True
        )

        return (
            (
                list[t],
                arg_default,
            )
            if arg_default is not None and not arg_from_array
            else list[t]
        )
    else:
        raise NotImplementedError(
            f"Schema conversion not implemented for {arg_value!r}"
        )


class EntrypointNotFoundError(ValueError):
    """Thin custom error to make it clearer what the error is."""


class NamespaceNotFoundError(ValueError):
    """Thin custom error to make it clearer what the error is."""
