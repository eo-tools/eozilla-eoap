import io
import json
import logging
import tempfile
from itertools import chain
from typing import List

import yaml
from cwl_utils import parser
from cwltool.main import main as validator
from fastapi import Request
from wraptile.exceptions import ServiceException

ALLOWED_ENCODING = (
    "application/cwl",
    "application/cwl+json",
    "application/cwl+yaml",
)


async def load_and_validate_from_body(request: Request, w: str | None) -> dict:
    """Load and Validate a CWL Document from HTTP Body

    Args:
        request (Request): fastapi request object.
        w (str | None): Optional fastapi query paramter specifying workflow entrypoint.

    Raises:
        RuntimeError: Content body is not in YAML or JSON format or malformed;
            CWL couldn't be loaded.
        ServiceException: CWL document doesn't adhere to CWL specification or
            fails EOAP validation.

    Returns:
        dict: Loaded (but not parsed) CWL body.
    """
    content_header: str = request.headers.get("Content-Type")

    body: bytes = await request.body()

    loaded_cwl: dict | None = _load_from_bytes(body, content_header)

    if not loaded_cwl:
        raise RuntimeError()

    if not _is_valid_as_cwl(loaded_cwl):
        raise ServiceException(status_code=422, detail="Not a valid cwl")

    if not _is_valid_as_eoap(loaded_cwl, w):
        raise ServiceException(status_code=422, detail="Not a valid eoap")

    return loaded_cwl


def _load_from_bytes(contents: bytes, format_hint: str) -> dict | None:
    """Load a Dictionary from Bytes

    Args:
        contents (bytes): Bytes object
        format_hint (str): Hint specifying whether contents is YAML or JSON-encoded.

    Returns:
        dict | None: Loaded dictionary or None, if object could not be loaded
            by Python's YAML/JSON-decoders.
    """
    if format_hint == "application/cwl+json":
        try:
            return json.loads(contents)
        except json.JSONDecodeError:
            return None
    elif format_hint == "application/cwl+yaml":
        try:
            return yaml.safe_load(contents)
        except yaml.YAMLError:
            return None

    return _load_from_bytes(contents, "application/cwl+json") or _load_from_bytes(
        contents, "application/cwl+yaml"
    )


def _is_valid_as_cwl(content: dict) -> bool:
    """Validate a Dictionary against CWL's specification

    Validation of CWL is more complex than simply checking
    the structure of the supplied document, e.g. because identifiers
    must be resolved and arguments checked for their type
    compatibility.

    Thus, the validation is delegated to `cwltool`, the reference
    implementation developed alongside the CWL standard. However,
    they don't offer a clean API to validate a CWL document. Thus,
    this function hooks into their _CLI interface_ which operates
    on a temporary file.

    Notes:
        - All CWL nodes are checked, i.e. the entire document not
          just a single (entrypoint) node
        - Any warnings etc. are gobbled

    Args:
        content (dict): In-memory representation of CWL document
            to check.

    Returns:
        bool: True if CWL is valid, False otherwise.
    """
    with tempfile.NamedTemporaryFile("w+t") as temporary_cwl_file:
        yaml.safe_dump(content, temporary_cwl_file)

        # make sure all contents are written to disk
        temporary_cwl_file.flush()

        logging.disable()

        result = validator(
            ["--validate", "--strict", temporary_cwl_file.name],
            stdout=io.StringIO(),  # I do not care about whatever cwltool has to say about it
            stderr=io.StringIO(),  # I do not care about whatever cwltool has to say about it
        )

        logging.disable(0)

    return not bool(result)


def _is_valid_as_eoap(content: dict, w: str | None = None) -> bool:
    """Validate an EOAP against OGC's Requirements

    The OGC Best Practice Guideline for EOAPs defines several
    additional requiremtens, next to being a valid CWL document,
    for a submitted process to be accepted. These can be found online
    in the respective document:

    Not all requirements can be checked without executing the EOAP,
    which is why only a subset of requirement tests is performed.

    Args:
        content (dict): In-memory representation of valid CWL document
        w (str | None, optional): Optional workflow entrypoint. Defaults to None.

    Returns:
        bool: True if EOAP is valid, False otherwise.
    """
    cwl_object = parser.load_document(content, load_all=True)

    eoap_requirements_passed = [
        check_eoap_requirement_07(cwl_object),
        check_eoap_requirement_08(cwl_object),
        check_eoap_requirement_09(cwl_object),
        check_eoap_requirement_10(cwl_object),
        check_eoap_requirement_11(content),
    ]

    return all(eoap_requirements_passed)


def check_eoap_requirement_07(cwl_object: list) -> bool:
    """Test req/app-pck/cwl

    The Application Package SHALL be a valid CWL document with
    a "Workflow" class and one or more "CommandLineTool" classes.

    Args:
        cwl_object (list): List of CWL nodes.

    Returns:
        bool: True if requirement was passed.
    """
    return any(map(lambda x: x.class_ == "Workflow", cwl_object)) and any(
        map(lambda x: x.class_ == "CommandLineTool", cwl_object)
    )


def check_eoap_requirement_08(cwl_object: list) -> bool:
    """Test req/app-pck/clt

    The Application Package CWL CommandLineTool classes SHALL
    contain the following elements:
    - Identifier ("id")
    - Command line name ("baseCommand")
    - Input parameters ("inputs")
    - Environment requirements ("requirements")
    - Docker information ("DockerRequirement")

    Args:
        cwl_object (list): List of CWL nodes.

    Returns:
        bool: True if requirement was passed.
    """
    clis: List[
        parser.cwl_v1_0.CommandLineTool
        | parser.cwl_v1_1.CommandLineTool
        | parser.cwl_v1_2.CommandLineTool
    ] = list(filter(lambda x: x.class_ == "CommandLineTool", cwl_object))
    all_have_ids = all(map(lambda x: x.id, clis))
    all_have_base_command = all(map(lambda x: x.baseCommand, clis))
    all_have_inputs = all(map(lambda x: x.inputs, clis))
    all_have_requirements = all(map(lambda x: x.requirements is not None, clis))

    all_have_docker_requirement = True
    requirements: List[parser.ProcessRequirement] = map(lambda x: x.requirements, clis)
    for req in requirements:
        if req is None: return False
        all_have_docker_requirement = all_have_docker_requirement and any(
            map(lambda x: isinstance(x, parser.DockerRequirement), req)
        )

    return (
        all_have_ids
        and all_have_base_command
        and all_have_inputs
        and all_have_requirements
        and all_have_docker_requirement
    )


def check_eoap_requirement_09(cwl_object: list) -> bool:
    """req/app-pck/wf

    The Application Package CWL Workflow class SHALL contain
    the following elements:
    - Identifier ("id")
    - Title ("label")
    - Abstract ("doc")

    Args:
        cwl_object (list): List of CWL nodes.

    Returns:
        bool: True if requirement was passed.
    """
    workflows: List[
        parser.cwl_v1_0.Workflow | parser.cwl_v1_1.Workflow | parser.cwl_v1_2.Workflow
    ] = list(filter(lambda x: x.class_ == "Workflow", cwl_object))
    return all(map(lambda x: x.id and x.label and x.doc, workflows))


def check_eoap_requirement_10(cwl_object: list) -> bool:
    """Test req/app-pck/wf-inputs

    The Application Package CWL Workflow class "inputs" fields
    SHALL contain the following elements:
    - Identifier ("id")
    - Title ("label")
    - Abstract ("doc")

    Args:
        cwl_object (list): List of CWL nodes.

    Returns:
        bool: True if requirement was passed.
    """
    workflows: List[
        parser.cwl_v1_0.Workflow | parser.cwl_v1_1.Workflow | parser.cwl_v1_2.Workflow
    ] = list(filter(lambda x: x.class_ == "Workflow", cwl_object))

    workflow_inputs: List[List[parser.WorkflowInputParameter]] = map(
        lambda x: x.inputs, workflows
    )
    for workflow_input in chain(*workflow_inputs):
        if not (workflow_input.id and workflow_input.label and workflow_input.doc):
            return False

    return True


def check_eoap_requirement_11(cwl_object: dict) -> bool:
    """Test req/app-pck/metadata

    The Application Package CWL Workclass classes SHALL
    include additional metadata as defined in Table 1.

    I.e., does a version tag exist? This cannot be
    checked by using the parsed cwl_util input beacause
    the library discards top-level objects and only exposed
    workflows, *-tools, steps etc.

    Args:
        cwl_object (list): List of CWL nodes.

    Returns:
        bool: True if requirement was passed.
    """
    if not isinstance(cwl_object, dict):
        return False

    namespaces: dict = cwl_object.get("$namespaces")

    if namespaces is None or type(namespaces) is not dict:
        return False

    schema_org_key: str = ""

    for k, v in namespaces.items():
        if v in ["https://schema.org", "https://schema.org/"]:
            schema_org_key = k
            break

    if not schema_org_key:
        return False

    return cwl_object.get(schema_org_key + ":version") is not None
