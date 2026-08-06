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


async def load_and_validate_from_body(request: Request, w: str) -> dict:
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
    cwl_object = parser.load_document(content, load_all=True)

    eoap_requirements_passed = [
        check_eoap_requirement_07(cwl_object)
        or print("test_eoap_requirement_07 failed"),
        check_eoap_requirement_08(cwl_object)
        or print("test_eoap_requirement_08 failed"),
        check_eoap_requirement_09(cwl_object)
        or print("test_eoap_requirement_09 failed"),
        check_eoap_requirement_10(cwl_object)
        or print("test_eoap_requirement_10 failed"),
        check_eoap_requirement_11(content) or print("test_eoap_requirement_11 failed"),
        check_eoap_requirement_12(cwl_object)
        or print("test_eoap_requirement_12 failed"),
        check_eoap_requirement_13(cwl_object)
        or print("test_eoap_requirement_13 failed"),
        check_eoap_requirement_14(cwl_object)
        or print("test_eoap_requirement_14 failed"),
    ]

    return all(eoap_requirements_passed)


def check_eoap_requirement_07(cwl_object: list) -> bool:
    return any(map(lambda x: x.class_ == "Workflow", cwl_object)) and any(
        map(lambda x: x.class_ == "CommandLineTool", cwl_object)
    )


def check_eoap_requirement_08(cwl_object: list) -> bool:
    clis: List[
        parser.cwl_v1_0.CommandLineTool
        | parser.cwl_v1_1.CommandLineTool
        | parser.cwl_v1_2.CommandLineTool
    ] = filter(lambda x: x.class_ == "CommandLineTool", cwl_object)
    all_have_ids = all(map(lambda x: x.id, clis))
    all_have_base_command = all(map(lambda x: x.baseCommand, clis))
    all_have_inputs = all(map(lambda x: x.inputs, clis))
    all_have_requirements = all(map(lambda x: x.requirements, clis))

    all_have_docker_requirement = True
    requirements: List[parser.ProcessRequirement] = map(lambda x: x.requriements, clis)
    for req in requirements:
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
    workflows: List[
        parser.cwl_v1_0.Workflow | parser.cwl_v1_1.Workflow | parser.cwl_v1_2.Workflow
    ] = filter(lambda x: x.class_ == "Workflow", cwl_object)
    return all(map(lambda x: x.id and x.label and x.doc, workflows))


def check_eoap_requirement_10(cwl_object: list) -> bool:
    workflows: List[
        parser.cwl_v1_0.Workflow | parser.cwl_v1_1.Workflow | parser.cwl_v1_2.Workflow
    ] = filter(lambda x: x.class_ == "Workflow", cwl_object)

    workflow_inputs: List[List[parser.WorkflowInputParameter]] = map(
        lambda x: x.inputs, workflows
    )
    for workflow_input in chain(*workflow_inputs):
        if not (workflow_input.id and workflow_input.label and workflow_input.doc):
            return False

    return True


def check_eoap_requirement_11(cwl_object: dict) -> bool:
    """req/app-pck/metadata

    The Application Package CWL Workclass classes SHALL
    include additional metadata as defined in Table 1.
    {
      I.e., does a version tag exist?! This cannot be
      checked by using the parsed cwl_util input beacause
      the library discards top-level objects and only exposed
      workflows, *-tools, steps etc.
    }
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


def check_eoap_requirement_12(cwl_object: list) -> bool:
    """req/app-pck-stage-in/clt-stac

    All input parameters of the CWL ComandLineTool
    that require the staging of EO products SHALL
    be of type Directory.

    Note:
        This cannot be checked beforehand.

    Returns:
        bool: True in all cases
    """
    return True


def check_eoap_requirement_13(cwl_object: list) -> bool:
    """req/app-pck-stage-in/wf-stac

    Input parameters of the CWL Workflow that require
    the staging of EO products SHALL be of type Directory.

    Note:
        This cannot be checked beforehand.

    Returns:
        bool: True in all cases
    """
    return True


def check_eoap_requirement_14(cwl_object: list) -> bool:
    """req/app-pck-stage-out/output-stac

    The outputs field of the CommandLineTool that requires
    the stage-out of EO products SHALL retrieve all
    the files produced in the working directory.

    Note:
        This cannot be checked beforehand.

    Returns:
        bool: True in all cases
    """
    return True
