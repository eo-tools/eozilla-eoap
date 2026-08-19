from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Tuple, get_origin

from cwl_utils import errors, parser
from gavicore.models import (
    DataType,
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
    create_model,
    field_validator,
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
        entrypoint: Workflow entrypoint to use, also used as process Id.

    Properties:
        model_class: Pydantic model class for the arguments of `source`.
        description: Process description modeled after
            [OGC API - Processes - Part 1: Core](https://docs.ogc.org/is/18-062r2/18-062r2.html#toc37).
    """

    source: str
    entrypoint: str
    _model_class: type[BaseModel]
    _description: ProcessDescription

    @property
    def model_class(self) -> type[BaseModel]:
        """Getter of `model_class` property

        Returns:
            type[BaseModel]: Process model instance.
        """
        return self._model_class

    @property
    def description(self) -> ProcessDescription:
        """Getter of `description` property

        Returns:
            ProcessDescription: OGC-compliant process description.
        """
        return self._description

    @classmethod
    def create(
        cls,
        future_source: Path,
        current_content: dict,
        entrypoint: str | None = None,
    ) -> "EoapProcess":
        """Public Constructor for EoapProcess

        Args:
            future_source (Path): Base directory where the serialized content of
                the encapsulated CWL document will be stored.
            current_content (dict): In-memory representation
            entrypoint (str | None, optional): Optional workflow entrypoint specified
                by the user. Defaults to None.

        Raises:
            ValueError: The user supplied an entrypoint that was not found in the
                workflow definition.

        Returns:
            EoapProcess: New instance of created EoapProcess.
        """
        id, version, title, description, keywords = cls._extract_process_metadata(
            current_content, entrypoint
        )

        if entrypoint and id != entrypoint:
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
    ) -> Tuple[str, str, str, str, List[str]]:
        """Extract Set of CWL Workflow Metadata

        Args:
            cwl (dict): In-memory, non-parsed representation of CWL document.
            w (str | None, optional): Optional, user-supplied workflow entrypoint. Defaults to None.

        Raises:
            NamespaceNotFoundError: Namesspaces attribute is missing entirely or
                the schema.org namespace is missing from it.

        Returns:
            Tuple[str, str, str, str]: Tuple of (1) workflow id, i.e. the workflow entrypoint name,
                (2) version tag, (3) workflow title, (4) workflow description and
                (5) workflow keywords.
        """
        process_entry_node = cls._find_entrypoint(cwl, w)

        # [`cwl_utils`] gobbles metadata, thus using raw dict is required
        namespaces: Dict | None = cwl.get("$namespaces")
        schema_org_key: str = ""

        if namespaces is None or type(namespaces) is not dict:
            raise NamespaceNotFoundError("No namespaces specified")

        for k, v in namespaces.items():
            if v in ["https://schema.org", "https://schema.org/"]:
                schema_org_key = k
                break

        if not schema_org_key:
            raise NamespaceNotFoundError("schema.org namespace not found")

        ret_tuple = (
            process_entry_node.id.split("#", 1)[-1],
            cwl.get(schema_org_key + ":version"),
            process_entry_node.label,
            process_entry_node.doc,
            cwl.get(schema_org_key + ":keywords"),
        )

        return ret_tuple

    @classmethod
    def _extract_cwl_argument_descriptions(
        cls,
        cwl: dict,
        entrypoint: str,
    ) -> Tuple[Dict[str, InputDescription], Dict[str, OutputDescription]]:
        """Convert CWL Workflow Inputs and Outputs to OGC-compliant Descriptions

        Iterate over all input descriptions of the workflow entrypoint and
        convert them to an OGC-compliant schema that is presented to a client
        querying input and output definitions of a deployed OGC Process.

        Every CWL argument definition is recursively resolved to a base
        type (boolean, int, float, string, File, Directory), array or enums.
        Optional values are marked by setting the `minOccurs` field to zero.
        Default values are preserved and set accordingly.

        Note that `File` and `Directory` argument are converted to string inputs
        that must point to remote resources.

        Important:
            Record types are currently not supported there's no clear way how
            they should be mapped to OGC-compliant input and output descriptions.

        Args:
            cwl (dict): In-memory representation of CWL document.
            entrypoint (str): Resolved entrypoint of the workflow.

        Raises:
            AssertionError: Input or output argument has no unique Id specified.

        Returns:
            Tuple[InputDescription, OutputDescription]: Tuple of (1) OGC-compliant
                process input description and (2) OGC-compliant process output
                description.
        """
        process_entry_node: parser.Workflow = cls._find_entrypoint(cwl, entrypoint)

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

            description: DescriptionType = DescriptionType(  # type: ignore[no-redef]
                title=output_.label, description=output_.doc
            )

            t_ = output_.type_
            f_: str | None = output_.format  # type: ignore[no-redef]

            optional, unbounded, schema = _resolve_ogc_schema_from_cwl_utils(
                t_, default=None, format=f_
            )

            ogc_conformant_outputs[local_id_tag] = OutputDescription(
                **description.model_dump(), schema=schema
            )

        return ogc_conformant_inputs, ogc_conformant_outputs

    @classmethod
    def _generate_model_class(cls, cwl: dict, entrypoint: str) -> type[BaseModel]:
        """Generate pydantic Model Class for Workflow/Process Inputs

        The generated pydantic model can be used to validated user inputs
        upon execution requests. Note that contrary to the conversion from
        CWL to OGC input/output descriptions, complete data models for
        `File` and `Directory` are incorporated.

        Args:
            cwl (dict): In-memory representation of CWL Workflow.
            entrypoint (str): Workflow entrypoint.

        Returns:
            type[BaseModel]: Dynamically created process model.
        """
        process_entry_node: parser.Workflow = cls._find_entrypoint(cwl, entrypoint)

        return cwl_inputs_to_model_class(process_entry_node.inputs)

    @classmethod
    def _find_entrypoint(cls, cwl_dict: dict, w: str | None = None) -> parser.Workflow:
        """Extract Workflow Entrypoint

        Extract either the Workflow instance with the id tag given by `w` or,
        if the paramter is None, the first instance of a Workflow object.

        Args:
            cwl_dict (dict): In-memory representation of CWL Workflow.
            w (str | None, optional): Optional, user-supplied workflow entrypoint.
                Defaults to None.

        Raises:
            EntrypointNotFoundError: Raised if user-supplied entrypoint does not exist.

        Returns:
            Dict: Workflow node to representing entrypoint of process.
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
    def _get_workflow_input(cls, cwl_node: Dict) -> Dict:
        """Extract Input Attribute of Node

        Args:
            cwl_node (Dict): A CWL node.

        Returns:
            Dict: Input definitions of supplied CWL node.
        """
        return cwl_node.inputs

    @classmethod
    def _get_workflow_ouput(cls, cwl_node: Dict) -> Dict:
        """Extract Output Attribute of Node

        Args:
            cwl_node (Dict): A CWL node.

        Returns:
            Dict: Output definitions of supplied CWL node.
        """
        return cwl_node.outputs


FLAT_TYPE_MAPPING_TO_OGC = {
    "boolean": "boolean",
    "int": "integer",
    "long": "integer",
    "float": "number",
    "double": "number",
    "string": "string",
}


class File(BaseModel):
    """Pydanic model of a CWL file"""

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
        """Before-validator for Improved User-Friendliness

        To hide the underlying pydantic model when a process takes
        in a File argument, this model validator allowes the user to
        pass in only the file path that is converted to a minimal
        set of mandatory fields needed to pass model validation.

        Args:
            data (Any): Input data

        Returns:
            Any: Possibly modified input data.
        """
        if isinstance(data, str):
            return {"class": "File", "path": data}

        if isinstance(data, list):
            return [{"class": "File", "path": x} for x in data]

        return data


class Directory(BaseModel):
    """Pydanic model of a CWL directory"""

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
        """Before-validator for Improved User-Friendliness

        To hide the underlying pydantic model when a process takes
        in a Directory argument, this model validator allowes the
        user to pass in only the "directory" path (STAC Object)
        that is converted to a minimal set of mandatory fields
        needed to pass model validation.

        Args:
            data (Any): Input data

        Returns:
            Any: Possibly modified input data.
        """
        if isinstance(data, str):
            return {"class": "Directory", "path": data}

        if isinstance(data, list):
            return [{"class": "Directory", "path": x} for x in data]

        return data


def _recursively_extract_special_defaults_to_ogc(arg_default):
    if isinstance(arg_default, parser.File) or isinstance(
        arg_default, parser.Directory
    ):
        return arg_default.location or arg_default.path
    elif isinstance(arg_default, list):
        return [_recursively_extract_special_defaults_to_ogc(i) for i in arg_default]
    else:
        return arg_default


def _resolve_ogc_schema_from_cwl_utils(
    cwl_type: str
    | list
    | parser.InputArraySchema
    | parser.OutputArraySchema
    | parser.InputEnumSchema
    | parser.OutputEnumSchema
    | parser.InputRecordSchema
    | parser.OutputRecordSchema,
    *,
    default: Any | None = None,
    format: str | None = None,
    nullable: bool = False,
) -> Tuple[bool, bool, Schema]:
    """Resolve CWL Arguments to OGC Schema

    Every CWL argument definition is recursively resolved to a base
    type (boolean, int, float, string, File, Directory), that may be
    encapsulated in arrays or enums. Optional values are marked by
    setting the `minOccurs` field to zero, arrays by marking a parameter
    as "unbounded". Default values are preserved and set accordingly.

    Note that `File` and `Directory` argument are converted to string inputs
    that must point to remote resources.

    Important:
        Record types are currently not supported there's no clear way how
        they should be mapped to OGC-compliant input and output descriptions.

    Args:
        cwl_type (str | list | parser.InputArraySchema | parser.OutputArraySchema | parser.InputEnumSchema | parser.OutputEnumSchema | parser.OutputRecordSchema | parser.OutputRecordSchema): Type field of workflow input/output item.
        default (Any | None, optional): Optional default value. Defaults to None.
        format (str | None, optional): Optional format string. Defaults to None.
        nullable (bool, optional): Boolean indicating if parameter can be null.
            Defaults to False.

    Raises:
        NotImplementedError: Raised when encountering CWL type whose conversion
            is not possible or implemented.

    Returns:
        Tuple[bool, bool, Schema]: Tuple consisting of (1) boolean indicating if
            argument can be null, (2) boolean indicating if an argument is
            unbounded, i.e. an array and (3) the corresponding OGC Schema.
    """
    nullable = nullable or (default is not None)  # don't trust user input
    if isinstance(cwl_type, str):
        if cwl_type == "File":
            return (
                nullable,
                False,
                Schema(
                    type=DataType("string"),
                    nullable=nullable,
                    default=_recursively_extract_special_defaults_to_ogc(default),
                    contentMediaType=format,
                    format="url",
                ),
            )
        elif cwl_type == "Directory":
            return (
                nullable,
                False,
                Schema(
                    type=DataType("string"),
                    nullable=nullable,
                    default=_recursively_extract_special_defaults_to_ogc(default),
                    contentMediaType=format,
                    format="url",
                ),
            )
        else:
            return (
                nullable,
                False,
                Schema(
                    type=DataType(FLAT_TYPE_MAPPING_TO_OGC[cwl_type]),
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
                type=DataType("string"),
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
            nullable=False,
            default=None,
            format=format,
        )
        return (
            nullable,
            True,
            Schema(
                type=DataType("array"),
                minItems=1,
                items=s,
                default=_recursively_extract_special_defaults_to_ogc(default),
                nullable=nullable,
            ),
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


def at_least_one_element_in_list(v: Any) -> Any:
    # OGC defines lists as containers with at least one element
    if not isinstance(v, list):
        return v
    if len(v) == 0:
        raise AssertionError
    return [at_least_one_element_in_list(item) for item in v]


def cwl_inputs_to_model_class(
    inputs: list[parser.WorkflowInputParameter],
) -> type[BaseModel]:
    """Generate a pydantic Model from a Workflow#s Input Arguments

    The generated pydantic model can be used to validate the user-provided
    arguments upon process execution request.

    Args:
        inputs (list[parser.WorkflowInputParameter]): List of input arguments.

    Returns:
        type[BaseModel]: Pydantic model
    """
    arguments: Dict[str, Any] = {}
    validators: Dict[str, Callable] = {}

    if isinstance(inputs, list):
        for input_ in inputs:
            n_ = input_.id.rsplit("/", 1)[-1]
            t_ = input_.type_
            d_ = input_.default

            resolved = _resolve_to_pydantic_tuple(t_, d_)
            arguments[n_] = resolved

            is_tuple = type(resolved) is tuple
            python_type_definition = arguments[n_][0] if is_tuple else arguments[n_]
            if get_origin(python_type_definition) is list:
                validators[n_ + "_validator"] = field_validator(n_)(
                    at_least_one_element_in_list
                )

    model_class: type[BaseModel] = create_model(
        "ProcessInputs",
        **arguments,
        __validators__=validators,
    )

    return model_class


def _recursively_extract_special_defaults_to_pydantic(arg_default):
    if isinstance(arg_default, parser.File):
        _vars = vars(arg_default)
        # removing cwl_utils-internal fields
        del _vars["extension_fields"]
        del _vars["loadingOptions"]
        return File(**_vars)
    elif isinstance(arg_default, parser.Directory):
        _vars = vars(arg_default)
        # removing cwl_utils-internal fields
        del _vars["extension_fields"]
        del _vars["loadingOptions"]
        return Directory(**_vars)
    elif isinstance(arg_default, list):
        return [
            _recursively_extract_special_defaults_to_pydantic(i) for i in arg_default
        ]
    else:
        return arg_default


def _resolve_to_pydantic_tuple(
    arg_value: str
    | list
    | parser.InputArraySchema
    | parser.InputEnumSchema
    | parser.InputRecordSchema,
    arg_default: Any = None,
    *,
    arg_from_array: bool = False,
) -> Tuple[type, type] | type:
    """Resolve CWL Type Definition to Python's Types

    Every CWL argument definition is recursively resolved to a base
    type (boolean, int, float, string, File, Directory), that may be
    encapsulated in arrays or enums. The deduced type is converted into
    a type Python can represent.

    Args:
        arg_value (str | list | parser.InputArraySchema | parser.InputEnumSchema | parser.InputRecordSchema): Type field of workflow input item.
        arg_default (Any, optional): Optional default value. Defaults to None.
        arg_from_array (bool, optional): Boolean indicating whether type was deduced from array. Defaults to False.

    Raises:
        NotImplementedError: Raised when encountering CWL type whose conversion
            is not possible or implemented.

    Returns:
        Tuple[type, type] | type: Tuple of converted argument type and its default value or just the converted argument type.
    """
    # NOTE: `cwltool` drops default values at T[][] and seemingly breaks
    #       with deeper nested lists using the shorthand notation.
    #       Entirely possible that I encounter the same problem because
    #       I rely on cwl_util's parsing as well.
    # NOTE: My understanding of the `location` and `path` parameters is:
    #       one the two must be given (ignoring that file contents can
    #       be given inlined!) and the location takes precedence over
    #       the path attribute
    if isinstance(arg_value, str):
        if arg_value == "File":
            return (
                (File, _recursively_extract_special_defaults_to_pydantic(arg_default))
                if arg_default is not None and not arg_from_array
                else File
            )
        elif arg_value == "Directory":
            return (
                (
                    Directory,
                    _recursively_extract_special_defaults_to_pydantic(arg_default),
                )
                if arg_default is not None and not arg_from_array
                else Directory
            )
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

        resolved_opt_value = _resolve_to_pydantic_tuple(
            content, arg_default=arg_default, arg_from_array=False
        )

        if type(resolved_opt_value) is type:
            # something like a: int | None = None
            return (resolved_opt_value | None, None)
        else:
            # someting like a: int | None = 1
            return (resolved_opt_value[0] | None, resolved_opt_value[1])
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

        # on the top-most invocation, where the default argument is set,
        # special types such as File and Directory must be handled specially
        # to extract the `location` or `path` values used to set the default
        # value; this means, we need to recurse twice on the same parameter:
        # once for the type conversion and once for the default value
        # conversion/extraction
        return (
            (
                list[t],
                _recursively_extract_special_defaults_to_pydantic(arg_default),
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
