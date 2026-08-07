from typing import List
from unittest import TestCase
from unittest.mock import Mock

import yaml
from cwl_utils.parser import cwl_v1_2

from eozilla_eoap.service.eoap_acceptance import (
    _is_valid_as_cwl,
    _is_valid_as_eoap,
    _load_from_bytes,
    check_eoap_requirement_07,
    check_eoap_requirement_08,
    check_eoap_requirement_09,
    check_eoap_requirement_10,
    check_eoap_requirement_11,
    load_and_validate_from_body,
)


class EoapAcceptanceTest(TestCase):
    def test_error_on_empty_body(self):
        # load_and_validate_form-body
        self.fail("`test_error_on_empty_body` is not implemented")

    def test_error_on_invalid_cwl(self):
        # load_and_validate_form-body
        self.fail("`test_error_on_invalid_cwl` is not implemented")

    def test_error_on_invalid_eoap(self):
        # load_and_validate_form-body
        self.fail("`test_error_on_invalid_eoap` is not implemented")

    def test_correctly_load_from_json(self):
        # load_and_validate_form-body
        self.fail("`test_correctly_load_from_json` is not implemented")

    def test_correctly_load_from_yaml(self):
        # load_and_validate_form-body
        self.fail("`test_correctly_load_from_yaml` is not implemented")

    def test_none_on_invalid_input(self):
        # _load_from_bytes
        self.fail("`test_none_on_invalid_input` is not implemented")

    def test_can_load_json(self):
        # _load_from_bytes
        self.fail("`test_can_load_json` is not implemented")

    def test_can_load_yaml(self):
        # _load_from_bytes
        self.fail("`test_can_load_yaml` is not implemented")

    def test_can_load_wrong_hint(self):
        # _load_from_bytes
        self.fail("`test_can_load_wrong_hint` is not implemented")

    def test_invalid_cwl_is_false(self):
        # TODO: Clarify if validation should be mocked or whether actually testing validity
        #       is preferred/correct/required
        self.fail("`test_invalid_cwl_is_false` is not implemented")

    def test_valid_cwl_is_true(self):
        # TODO: Clarify if validation should be mocked or whether actually testing validity
        #       is preferred/correct/required
        self.fail("`test_valid_cwl_is_true` is not implemented")

    def test_invalid_eoap_is_false(self):
        self.fail("`test_invalid_eoap_is_false` is not implemented")

    def test_valid_eoap_is_true(self):
        self.fail("`test_valid_eoap_is_true` is not implemented")

    # Requirement 7: req/app-pck/cwl
    # NOTE: The checks don't actually incorporate testing for validity of supplied CWL;
    #       this is one in `is_valid_cwl`
    def test_req_07_missing_workflow(self):
        cwl_objects: List[cwl_v1_2.Workflow | cwl_v1_2.CommandLineTool] = [
            cwl_v1_2.CommandLineTool(
                id="cli-1",
                baseCommand="command-1",
                inputs=[
                    cwl_v1_2.CommandInputParameter(id="cli-input-1", type_="string")
                ],
                requirements=[cwl_v1_2.DockerRequirement()],
                outputs=[
                    cwl_v1_2.CommandOutputParameter(id="cli-output-1", type_="string")
                ],
            ),
        ]

        self.assertFalse(check_eoap_requirement_07(cwl_objects))

    def test_req_07_missing_cli(self):
        cwl_objects: List[cwl_v1_2.Workflow | cwl_v1_2.CommandLineTool] = [
            cwl_v1_2.Workflow(
                id="workflow-1",
                label="label-1",
                doc="doc-1",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(id="wf-input-1", type_="string")
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-1", type_="string")
                ],
                steps=[],
            ),
        ]

        self.assertFalse(check_eoap_requirement_07(cwl_objects))

    def test_req_07_valid_intput(self):
        cwl_objects: List[cwl_v1_2.Workflow | cwl_v1_2.CommandLineTool] = [
            cwl_v1_2.Workflow(
                id="workflow-1",
                label="label-1",
                doc="doc-1",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(id="wf-input-1", type_="string")
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-1", type_="string")
                ],
                steps=[],
            ),
            cwl_v1_2.CommandLineTool(
                id="cli-1",
                baseCommand="command-1",
                inputs=[
                    cwl_v1_2.CommandInputParameter(id="cli-input-1", type_="string")
                ],
                requirements=[cwl_v1_2.DockerRequirement()],
                outputs=[
                    cwl_v1_2.CommandOutputParameter(id="cli-output-1", type_="string")
                ],
            ),
        ]

        self.assertTrue(check_eoap_requirement_07(cwl_objects))

    # Requirement 8: req/app-pck/clt
    def test_req_08_missing_base_command(self):
        cwl_objects: List[cwl_v1_2.CommandLineTool] = [
            cwl_v1_2.CommandLineTool(
                id="cli-1",
                inputs=[cwl_v1_2.CommandInputParameter(id="input-1", type_="string")],
                requirements=[],
                outputs=[
                    cwl_v1_2.CommandOutputParameter(id="output-1", type_="string")
                ],
            )
        ]

        self.assertFalse(check_eoap_requirement_08(cwl_objects))

    def test_req_08_missing_requirements(self):
        cwl_objects: List[cwl_v1_2.CommandLineTool] = [
            cwl_v1_2.CommandLineTool(
                id="cli-1",
                baseCommand="command-1",
                inputs=[cwl_v1_2.CommandInputParameter(id="input-1", type_="string")],
                outputs=[
                    cwl_v1_2.CommandOutputParameter(id="output-1", type_="string")
                ],
            )
        ]

        self.assertFalse(check_eoap_requirement_08(cwl_objects))

    def test_req_08_missing_docker_requirement(self):
        cwl_objects: List[cwl_v1_2.CommandLineTool] = [
            cwl_v1_2.CommandLineTool(
                id="cli-1",
                baseCommand="command-1",
                inputs=[cwl_v1_2.CommandInputParameter(id="input-1", type_="string")],
                requirements=[],
                outputs=[
                    cwl_v1_2.CommandOutputParameter(id="output-1", type_="string")
                ],
            )
        ]

        self.assertFalse(check_eoap_requirement_08(cwl_objects))

    def test_req_08_complete_command_line_tool(self):
        cwl_objects: List[cwl_v1_2.CommandLineTool] = [
            cwl_v1_2.CommandLineTool(
                id="cli-1",
                baseCommand="command-1",
                inputs=[cwl_v1_2.CommandInputParameter(id="input-1", type_="string")],
                requirements=[cwl_v1_2.DockerRequirement()],
                outputs=[
                    cwl_v1_2.CommandOutputParameter(id="output-1", type_="string")
                ],
            )
        ]

        self.assertTrue(check_eoap_requirement_08(cwl_objects))

    def test_req_08_list_contains_only_valid(self):
        cwl_objects: List[cwl_v1_2.CommandLineTool] = [
            cwl_v1_2.CommandLineTool(
                id="cli-1",
                baseCommand="command-1",
                inputs=[cwl_v1_2.CommandInputParameter(id="input-1", type_="string")],
                requirements=[cwl_v1_2.DockerRequirement()],
                outputs=[
                    cwl_v1_2.CommandOutputParameter(id="output-1", type_="string")
                ],
            ),
            cwl_v1_2.CommandLineTool(
                id="cli-2",
                baseCommand="command-2",
                inputs=[cwl_v1_2.CommandInputParameter(id="input-2", type_="string")],
                requirements=[cwl_v1_2.DockerRequirement()],
                outputs=[
                    cwl_v1_2.CommandOutputParameter(id="output-2", type_="string")
                ],
            ),
        ]

        self.assertTrue(check_eoap_requirement_08(cwl_objects))

    def test_req_08_list_contains_one_invalid(self):
        cwl_objects: List[cwl_v1_2.CommandLineTool] = [
            cwl_v1_2.CommandLineTool(
                id="cli-1",
                baseCommand="command-1",
                inputs=[cwl_v1_2.CommandInputParameter(id="input-1", type_="string")],
                requirements=[cwl_v1_2.DockerRequirement()],
                outputs=[
                    cwl_v1_2.CommandOutputParameter(id="output-1", type_="string")
                ],
            ),
            cwl_v1_2.CommandLineTool(
                id="cli-2",
                inputs=[cwl_v1_2.CommandInputParameter(id="input-2", type_="string")],
                outputs=[
                    cwl_v1_2.CommandOutputParameter(id="output-2", type_="string")
                ],
            ),
        ]

        self.assertFalse(check_eoap_requirement_08(cwl_objects))

    # Requirement 09: req/app-pck/wf
    def test_req_09_missing_label(self):
        cwl_objects: List[cwl_v1_2.Workflow] = [
            cwl_v1_2.Workflow(
                id="workflow-1",
                doc="doc-1",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(id="wf-input-1", type_="string")
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-1", type_="string")
                ],
                steps=[],
            ),
        ]

        self.assertFalse(check_eoap_requirement_09(cwl_objects))

    def test_req_09_missing_doc(self):
        cwl_objects: List[cwl_v1_2.Workflow] = [
            cwl_v1_2.Workflow(
                id="workflow-1",
                label="label-1",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(id="wf-input-1", type_="string")
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-1", type_="string")
                ],
                steps=[],
            ),
        ]

        self.assertFalse(check_eoap_requirement_09(cwl_objects))

    def test_req_09_complete_input_fields(self):
        cwl_objects: List[cwl_v1_2.Workflow] = [
            cwl_v1_2.Workflow(
                id="workflow-1",
                label="label-1",
                doc="doc-1",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(id="wf-input-1", type_="string")
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-1", type_="string")
                ],
                steps=[],
            ),
        ]

        self.assertTrue(check_eoap_requirement_09(cwl_objects))

    def test_req_09_list_contains_only_valid(self):
        cwl_objects: List[cwl_v1_2.Workflow] = [
            cwl_v1_2.Workflow(
                id="workflow-1",
                label="label-1",
                doc="doc-1",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(id="wf-input-1", type_="string")
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-1", type_="string")
                ],
                steps=[],
            ),
            cwl_v1_2.Workflow(
                id="workflow-2",
                label="label-2",
                doc="doc-2",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(id="wf-input-2", type_="string")
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-2", type_="string")
                ],
                steps=[],
            ),
        ]

        self.assertTrue(check_eoap_requirement_09(cwl_objects))

    def test_req_09_list_contains_one_invalid(self):
        cwl_objects: List[cwl_v1_2.Workflow] = [
            cwl_v1_2.Workflow(
                id="workflow-1",
                label="label-1",
                doc="doc-1",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(id="wf-input-1", type_="string")
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-1", type_="string")
                ],
                steps=[],
            ),
            cwl_v1_2.Workflow(
                id="workflow-2",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(id="wf-input-2", type_="string")
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-2", type_="string")
                ],
                steps=[],
            ),
        ]

        self.assertFalse(check_eoap_requirement_09(cwl_objects))

    # Requirement 10: req/app-pck/wf-inputs
    def test_req_10_missing_label(self):
        cwl_objects: List[cwl_v1_2.Workflow] = [
            cwl_v1_2.Workflow(
                id="workflow-1",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(id="input-1", type_="string"),
                    cwl_v1_2.WorkflowInputParameter(id="input-2", type_="string"),
                    cwl_v1_2.WorkflowInputParameter(id="input-3", type_="string"),
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-1", type_="string")
                ],
                steps=[],
            ),
        ]

        self.assertFalse(check_eoap_requirement_10(cwl_objects))

    def test_req_10_missing_doc(self):
        cwl_objects: List[cwl_v1_2.Workflow] = [
            cwl_v1_2.Workflow(
                id="workflow-1",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(id="input-1", type_="string"),
                    cwl_v1_2.WorkflowInputParameter(id="input-2", type_="string"),
                    cwl_v1_2.WorkflowInputParameter(id="input-3", type_="string"),
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-1", type_="string")
                ],
                steps=[],
            ),
        ]

        self.assertFalse(check_eoap_requirement_10(cwl_objects))

    def test_req_10_complete_input_fields(self):
        cwl_objects: List[cwl_v1_2.Workflow] = [
            cwl_v1_2.Workflow(
                id="workflow-1",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(
                        id="input-1", type_="string", label="label-1", doc="doc-1"
                    ),
                    cwl_v1_2.WorkflowInputParameter(
                        id="input-2", type_="string", label="label-2", doc="doc-2"
                    ),
                    cwl_v1_2.WorkflowInputParameter(
                        id="input-3", type_="string", label="label-3", doc="doc-3"
                    ),
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-1", type_="string")
                ],
                steps=[],
            ),
        ]

        self.assertTrue(check_eoap_requirement_10(cwl_objects))

    def test_req_10_list_contains_only_valid(self):
        cwl_objects: List[cwl_v1_2.Workflow] = [
            cwl_v1_2.Workflow(
                id="workflow-1",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(
                        id="input-1", type_="string", label="label-1", doc="doc-1"
                    ),
                    cwl_v1_2.WorkflowInputParameter(
                        id="input-2", type_="string", label="label-2", doc="doc-2"
                    ),
                    cwl_v1_2.WorkflowInputParameter(
                        id="input-3", type_="string", label="label-3", doc="doc-3"
                    ),
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-1", type_="string")
                ],
                steps=[],
            ),
            cwl_v1_2.Workflow(
                id="workflow-2",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(
                        id="input-4", type_="string", label="label-4", doc="doc-4"
                    ),
                    cwl_v1_2.WorkflowInputParameter(
                        id="input-5", type_="string", label="label-5", doc="doc-5"
                    ),
                    cwl_v1_2.WorkflowInputParameter(
                        id="input-6", type_="string", label="label-6", doc="doc-6"
                    ),
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-2", type_="string")
                ],
                steps=[],
            ),
        ]

        self.assertTrue(check_eoap_requirement_10(cwl_objects))

    def test_req_10_list_contains_one_invalid(self):
        cwl_objects: List[cwl_v1_2.Workflow] = [
            cwl_v1_2.Workflow(
                id="workflow-1",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(
                        id="input-1", type_="string", label="label-1", doc="doc-1"
                    ),
                    cwl_v1_2.WorkflowInputParameter(
                        id="input-2", type_="string", label="label-2", doc="doc-2"
                    ),
                    cwl_v1_2.WorkflowInputParameter(
                        id="input-3", type_="string", label="label-3", doc="doc-3"
                    ),
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-1", type_="string")
                ],
                steps=[],
            ),
            cwl_v1_2.Workflow(
                id="workflow-2",
                inputs=[
                    cwl_v1_2.WorkflowInputParameter(id="input-4", type_="string"),
                    cwl_v1_2.WorkflowInputParameter(id="input-5", type_="string"),
                    cwl_v1_2.WorkflowInputParameter(id="input-6", type_="string"),
                ],
                outputs=[
                    cwl_v1_2.WorkflowOutputParameter(id="wf-output-2", type_="string")
                ],
                steps=[],
            ),
        ]

        self.assertFalse(check_eoap_requirement_10(cwl_objects))

    # Requirement 11: req/app-pck/metadata
    def test_req_11_does_not_accept_list(self):
        self.assertFalse(check_eoap_requirement_11([]))

    def test_req_11_does_not_accept_set(self):
        self.assertFalse(check_eoap_requirement_11({}))

    def test_req_11_does_not_accept_int(self):
        self.assertFalse(check_eoap_requirement_11(1))

    def test_req_11_does_not_accept_float(self):
        self.assertFalse(check_eoap_requirement_11(3.141))

    def test_req_11_does_not_accept_bool(self):
        self.assertFalse(check_eoap_requirement_11(True))

    def test_req_11_does_not_accept_string(self):
        self.assertFalse(check_eoap_requirement_11(""))

    def test_req_11_does_not_accept_none(self):
        self.assertFalse(check_eoap_requirement_11(None))

    def test_req_11_does_not_accept_object(self):
        self.assertFalse(check_eoap_requirement_11(object))

    def test_req_11_missing_namespaces(self):
        test_input: dict = {"some_key": "some_value", "another_key": 1}

        self.assertFalse(check_eoap_requirement_11(test_input))

    def test_namespaces_is_dict(self):
        test_input: dict = {"some_key": "some_value", "$namespaces": 1}

        self.assertFalse(check_eoap_requirement_11(test_input))

    def test_req_11_missing_schema_org(self):
        test_input: dict = {
            "some_key": "some_value",
            "$namespaces": {"s": "another_value"},
        }

        self.assertFalse(check_eoap_requirement_11(test_input))

    def test_req_11_missing_version_tag(self):
        test_input: dict = {
            "some_key": "some_value",
            "$namespaces": {"s": "https://schema.org"},
        }

        self.assertFalse(check_eoap_requirement_11(test_input))

    def test_req_11_present_version_tag(self):
        test_input: dict = {
            "some_key": "some_value",
            "$namespaces": {"s": "https://schema.org"},
            "s:version": "1.0.0",
        }

        self.assertTrue(check_eoap_requirement_11(test_input))

    def test_req_11_schema_org_trailing_slash(self):
        test_input: dict = {
            "some_key": "some_value",
            "$namespaces": {"s": "https://schema.org/"},
            "s:version": "1.0.0",
        }

        self.assertTrue(check_eoap_requirement_11(test_input))
