"""Unit tests for WorkflowsClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ListApiResponse, ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.workflows import WorkflowsClient
from kibana.exceptions import BadRequestError, ConflictError, NotFoundError

WORKFLOW_YAML = """name: kbnpy-test-workflow
enabled: true
triggers:
  - type: manual
steps:
  - name: log_step
    type: console
    with:
      message: "hello"
"""


def _workflow_body(**overrides) -> dict:
    """Build a representative workflow response body (9.4.3 shape)."""
    body = {
        "id": "kbnpy-test-workflow",
        "name": "kbnpy-test-workflow",
        "description": "test workflow",
        "enabled": True,
        "yaml": WORKFLOW_YAML,
        "definition": {
            "name": "kbnpy-test-workflow",
            "enabled": True,
            "triggers": [{"type": "manual"}],
            "steps": [
                {
                    "name": "log_step",
                    "type": "console",
                    "with": {"message": "hello"},
                }
            ],
        },
        "valid": True,
        "createdAt": "2026-07-03T20:00:00.000Z",
        "createdBy": "elastic",
        "lastUpdatedAt": "2026-07-03T20:00:00.000Z",
        "lastUpdatedBy": "elastic",
    }
    body.update(overrides)
    return body


def _execution_body(**overrides) -> dict:
    """Build a representative workflow execution response body."""
    body = {
        "id": "bff7c3cb-e980-4480-a2ec-474f872dd6e8",
        "status": "completed",
        "workflowId": "kbnpy-test-workflow",
        "spaceId": "default",
        "isTestRun": False,
        "startedAt": "2026-07-03T20:03:37.900Z",
        "finishedAt": "2026-07-03T20:03:38.000Z",
        "duration": 100,
        "triggeredBy": "manual",
        "stepExecutions": [],
        "stepExecutionIds": [],
    }
    body.update(overrides)
    return body


def _mock_object_response(mock_transport, body=None, status=200):
    """Wire an ObjectApiResponse into the mock transport and return it."""
    response = ObjectApiResponse(
        body=body if body is not None else {},
        meta=Mock(status=status, headers={}),
    )
    mock_transport.perform_request.return_value = response
    return response


class TestWorkflowsClientInitialization:
    """Test WorkflowsClient initialization and wiring."""

    def test_workflows_client_initialization(self, mock_transport):
        """Test that WorkflowsClient can be initialized with a parent client."""
        client = Kibana(_transport=mock_transport)
        workflows_client = WorkflowsClient(client)
        assert workflows_client._client is client

    def test_workflows_property_returns_client(self, mock_transport):
        """Test that client.workflows returns a WorkflowsClient instance."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.workflows, WorkflowsClient)

    def test_workflows_property_caching(self, mock_transport):
        """Test that the workflows property returns the same instance."""
        client = Kibana(_transport=mock_transport)
        assert client.workflows is client.workflows


class TestWorkflowsClientCrud:
    """Test workflow CRUD methods."""

    def test_create(self, mock_transport):
        """Test creating a workflow with a custom ID."""
        _mock_object_response(mock_transport, _workflow_body())

        client = Kibana(_transport=mock_transport)
        result = client.workflows.create(yaml=WORKFLOW_YAML, id="kbnpy-test-workflow")

        assert result.body["id"] == "kbnpy-test-workflow"
        assert result.body["valid"] is True

        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/workflows/workflow"
        assert call_kwargs["body"] == {
            "yaml": WORKFLOW_YAML,
            "id": "kbnpy-test-workflow",
        }
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_create_without_id(self, mock_transport):
        """Test that the optional id is omitted from the body when not given."""
        _mock_object_response(mock_transport, _workflow_body())

        client = Kibana(_transport=mock_transport)
        client.workflows.create(yaml=WORKFLOW_YAML)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {"yaml": WORKFLOW_YAML}

    def test_create_in_space(self, mock_transport):
        """Test creating a workflow in a specific space."""
        _mock_object_response(mock_transport, _workflow_body())

        client = Kibana(_transport=mock_transport)
        client.workflows.create(
            yaml=WORKFLOW_YAML, space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/workflows/workflow"

    def test_get(self, mock_transport):
        """Test getting a workflow by ID."""
        _mock_object_response(mock_transport, _workflow_body())

        client = Kibana(_transport=mock_transport)
        result = client.workflows.get(id="kbnpy-test-workflow")

        assert result.body["name"] == "kbnpy-test-workflow"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/workflows/workflow/kbnpy-test-workflow"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    def test_get_url_encodes_id(self, mock_transport):
        """Test that the workflow ID is URL-encoded in the path."""
        _mock_object_response(mock_transport, _workflow_body())

        client = Kibana(_transport=mock_transport)
        client.workflows.get(id="my workflow/1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/workflows/workflow/my%20workflow%2F1"

    def test_update(self, mock_transport):
        """Test partially updating a workflow."""
        _mock_object_response(
            mock_transport,
            {
                "id": "kbnpy-test-workflow",
                "enabled": False,
                "valid": True,
                "validationErrors": [],
                "lastUpdatedAt": "2026-07-03T20:10:00.000Z",
                "lastUpdatedBy": "elastic",
            },
        )

        client = Kibana(_transport=mock_transport)
        result = client.workflows.update(
            id="kbnpy-test-workflow",
            name="renamed",
            description="new description",
            enabled=False,
            tags=["kbnpy", "test"],
        )

        assert result.body["enabled"] is False

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/workflows/workflow/kbnpy-test-workflow"
        assert call_kwargs["body"] == {
            "name": "renamed",
            "description": "new description",
            "enabled": False,
            "tags": ["kbnpy", "test"],
        }

    def test_update_with_yaml(self, mock_transport):
        """Test replacing a workflow definition via yaml."""
        _mock_object_response(mock_transport, {"id": "kbnpy-test-workflow"})

        client = Kibana(_transport=mock_transport)
        client.workflows.update(id="kbnpy-test-workflow", yaml=WORKFLOW_YAML)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {"yaml": WORKFLOW_YAML}

    def test_delete(self, mock_transport):
        """Test deleting a workflow with the force flag."""
        _mock_object_response(mock_transport, {})

        client = Kibana(_transport=mock_transport)
        client.workflows.delete(id="kbnpy-test-workflow", force=True)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert (
            call_kwargs["target"]
            == "/api/workflows/workflow/kbnpy-test-workflow?force=true"
        )

    def test_clone(self, mock_transport):
        """Test cloning a workflow."""
        _mock_object_response(
            mock_transport, _workflow_body(id="kbnpy-test-workflow-copy")
        )

        client = Kibana(_transport=mock_transport)
        result = client.workflows.clone(id="kbnpy-test-workflow")

        assert result.body["id"] == "kbnpy-test-workflow-copy"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert (
            call_kwargs["target"] == "/api/workflows/workflow/kbnpy-test-workflow/clone"
        )


class TestWorkflowsClientSearchAndBulk:
    """Test search, bulk and lookup methods."""

    def test_get_all(self, mock_transport):
        """Test searching workflows with filters and pagination."""
        _mock_object_response(
            mock_transport,
            {"results": [_workflow_body()], "total": 1, "page": 1, "size": 5},
        )

        client = Kibana(_transport=mock_transport)
        result = client.workflows.get_all(
            query="kbnpy",
            size=5,
            page=1,
            enabled=[True, False],
            created_by=["elastic"],
            tags=["a", "b"],
        )

        assert result.body["total"] == 1

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/workflows?query=kbnpy&size=5&page=1"
            "&enabled=true&enabled=false&createdBy=elastic&tags=a&tags=b"
        )

    def test_get_all_no_params(self, mock_transport):
        """Test that no query string is added when no filters are given."""
        _mock_object_response(
            mock_transport, {"results": [], "total": 0, "page": 1, "size": 20}
        )

        client = Kibana(_transport=mock_transport)
        client.workflows.get_all()

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/workflows"

    def test_bulk_create(self, mock_transport):
        """Test bulk creating workflows with overwrite."""
        _mock_object_response(mock_transport, {"created": [_workflow_body()]})

        client = Kibana(_transport=mock_transport)
        workflows = [{"id": "kbnpy-test-workflow", "yaml": WORKFLOW_YAML}]
        result = client.workflows.bulk_create(workflows=workflows, overwrite=True)

        assert len(result.body["created"]) == 1

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/workflows?overwrite=true"
        assert call_kwargs["body"] == {"workflows": workflows}

    def test_bulk_delete(self, mock_transport):
        """Test bulk deleting workflows by IDs."""
        _mock_object_response(
            mock_transport, {"total": 2, "deleted": 2, "failures": []}
        )

        client = Kibana(_transport=mock_transport)
        result = client.workflows.bulk_delete(ids=["wf-1", "wf-2"], force=True)

        assert result.body["deleted"] == 2

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/workflows?force=true"
        assert call_kwargs["body"] == {"ids": ["wf-1", "wf-2"]}

    def test_mget(self, mock_transport):
        """Test multi-getting workflows by IDs (body is a JSON array)."""
        mock_transport.perform_request.return_value = ListApiResponse(
            body=[{"id": "wf-1", "name": "wf-1"}],
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.workflows.mget(ids=["wf-1"], source=["id", "name"])

        assert isinstance(result.body, list)
        assert result.body[0]["id"] == "wf-1"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/workflows/mget"
        assert call_kwargs["body"] == {"ids": ["wf-1"], "source": ["id", "name"]}

    def test_export(self, mock_transport):
        """Test exporting workflows as normalized YAML entries."""
        _mock_object_response(
            mock_transport,
            {
                "entries": [{"id": "wf-1", "yaml": WORKFLOW_YAML}],
                "manifest": {"exportedCount": 1, "version": "1"},
            },
        )

        client = Kibana(_transport=mock_transport)
        result = client.workflows.export(ids=["wf-1"])

        assert result.body["manifest"]["exportedCount"] == 1

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/workflows/export"
        assert call_kwargs["body"] == {"ids": ["wf-1"]}


class TestWorkflowsClientMetadata:
    """Test aggs, connectors, schema and stats methods."""

    def test_get_aggs(self, mock_transport):
        """Test aggregating workflow field values."""
        _mock_object_response(
            mock_transport,
            {"tags": [{"key": "kbnpy", "doc_count": 1}], "createdBy": []},
        )

        client = Kibana(_transport=mock_transport)
        result = client.workflows.get_aggs(fields=["tags", "createdBy"])

        assert result.body["tags"][0]["key"] == "kbnpy"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert (
            call_kwargs["target"] == "/api/workflows/aggs?fields=tags&fields=createdBy"
        )

    def test_get_connectors(self, mock_transport):
        """Test listing available connectors."""
        _mock_object_response(
            mock_transport,
            {
                "connectorTypes": {
                    ".email": {
                        "actionTypeId": ".email",
                        "displayName": "Email",
                        "instances": [],
                        "enabled": True,
                    }
                }
            },
        )

        client = Kibana(_transport=mock_transport)
        result = client.workflows.get_connectors()

        assert ".email" in result.body["connectorTypes"]

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/workflows/connectors"

    def test_get_schema(self, mock_transport):
        """Test retrieving the workflow JSON schema."""
        _mock_object_response(
            mock_transport,
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
                "definitions": {},
            },
        )

        client = Kibana(_transport=mock_transport)
        result = client.workflows.get_schema(loose=False)

        assert result.body["$schema"] == "http://json-schema.org/draft-07/schema#"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/workflows/schema?loose=false"

    def test_get_stats(self, mock_transport):
        """Test retrieving workflow statistics."""
        _mock_object_response(
            mock_transport,
            {"workflows": {"enabled": 1, "disabled": 0}, "executions": []},
        )

        client = Kibana(_transport=mock_transport)
        result = client.workflows.get_stats()

        assert result.body["workflows"]["enabled"] == 1

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/workflows/stats"


class TestWorkflowsClientRunAndTest:
    """Test run, test and test_step methods."""

    def test_run(self, mock_transport):
        """Test running a workflow with inputs and metadata."""
        _mock_object_response(mock_transport, {"workflowExecutionId": "exec-1"})

        client = Kibana(_transport=mock_transport)
        result = client.workflows.run(
            id="kbnpy-test-workflow", inputs={"k": "v"}, metadata={"m": 1}
        )

        assert result.body["workflowExecutionId"] == "exec-1"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert (
            call_kwargs["target"] == "/api/workflows/workflow/kbnpy-test-workflow/run"
        )
        assert call_kwargs["body"] == {"inputs": {"k": "v"}, "metadata": {"m": 1}}

    def test_test_with_workflow_id(self, mock_transport):
        """Test starting a test run of an existing workflow."""
        _mock_object_response(mock_transport, {"workflowExecutionId": "exec-2"})

        client = Kibana(_transport=mock_transport)
        result = client.workflows.test(workflow_id="kbnpy-test-workflow", inputs={})

        assert result.body["workflowExecutionId"] == "exec-2"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/workflows/test"
        assert call_kwargs["body"] == {
            "inputs": {},
            "workflowId": "kbnpy-test-workflow",
        }

    def test_test_with_yaml(self, mock_transport):
        """Test starting a test run of an ad-hoc YAML definition."""
        _mock_object_response(mock_transport, {"workflowExecutionId": "exec-3"})

        client = Kibana(_transport=mock_transport)
        client.workflows.test(workflow_yaml=WORKFLOW_YAML, inputs={"a": 1})

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "inputs": {"a": 1},
            "workflowYaml": WORKFLOW_YAML,
        }

    def test_test_step(self, mock_transport):
        """Test starting a single-step test run."""
        _mock_object_response(mock_transport, {"workflowExecutionId": "exec-4"})

        client = Kibana(_transport=mock_transport)
        result = client.workflows.test_step(
            step_id="log_step",
            context_override={"x": 1},
            workflow_yaml=WORKFLOW_YAML,
            workflow_id="kbnpy-test-workflow",
            execution_context={"y": 2},
        )

        assert result.body["workflowExecutionId"] == "exec-4"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/workflows/step/test"
        assert call_kwargs["body"] == {
            "stepId": "log_step",
            "contextOverride": {"x": 1},
            "workflowYaml": WORKFLOW_YAML,
            "workflowId": "kbnpy-test-workflow",
            "executionContext": {"y": 2},
        }


class TestWorkflowsClientExecutions:
    """Test execution-related methods."""

    def test_get_executions(self, mock_transport):
        """Test listing workflow executions with filters."""
        _mock_object_response(
            mock_transport,
            {"results": [_execution_body()], "total": 1, "page": 1, "size": 10},
        )

        client = Kibana(_transport=mock_transport)
        result = client.workflows.get_executions(
            workflow_id="kbnpy-test-workflow",
            statuses=["completed", "failed"],
            execution_types=["production"],
            executed_by=["elastic"],
            omit_step_runs=True,
            page=1,
            size=10,
        )

        assert result.body["total"] == 1

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/workflows/workflow/kbnpy-test-workflow/executions"
            "?statuses=completed&statuses=failed&executionTypes=production"
            "&executedBy=elastic&omitStepRuns=true&page=1&size=10"
        )

    def test_get_step_executions(self, mock_transport):
        """Test listing step executions across the runs of a workflow."""
        _mock_object_response(
            mock_transport,
            {
                "results": [
                    {"id": "step-exec-1", "stepId": "log_step", "status": "completed"}
                ],
                "total": 1,
                "page": 1,
                "size": 10,
            },
        )

        client = Kibana(_transport=mock_transport)
        result = client.workflows.get_step_executions(
            workflow_id="kbnpy-test-workflow",
            step_id="log_step",
            include_input=True,
            include_output=False,
            page=1,
            size=10,
        )

        assert result.body["results"][0]["stepId"] == "log_step"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/workflows/workflow/kbnpy-test-workflow/executions/steps"
            "?stepId=log_step&includeInput=true&includeOutput=false&page=1&size=10"
        )

    def test_cancel_all_executions(self, mock_transport):
        """Test cancelling all active executions of a workflow."""
        _mock_object_response(mock_transport, {})

        client = Kibana(_transport=mock_transport)
        client.workflows.cancel_all_executions(workflow_id="kbnpy-test-workflow")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/workflows/workflow/kbnpy-test-workflow/executions/cancel"
        )

    def test_get_execution(self, mock_transport):
        """Test getting a single execution with input/output flags."""
        _mock_object_response(mock_transport, _execution_body())

        client = Kibana(_transport=mock_transport)
        result = client.workflows.get_execution(
            execution_id="exec-1", include_input=True, include_output=True
        )

        assert result.body["status"] == "completed"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/workflows/executions/exec-1?includeInput=true&includeOutput=true"
        )

    def test_cancel_execution(self, mock_transport):
        """Test cancelling a single execution."""
        _mock_object_response(mock_transport, {})

        client = Kibana(_transport=mock_transport)
        client.workflows.cancel_execution(execution_id="exec-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/workflows/executions/exec-1/cancel"

    def test_resume_execution(self, mock_transport):
        """Test resuming an execution that waits for input."""
        _mock_object_response(mock_transport, {})

        client = Kibana(_transport=mock_transport)
        client.workflows.resume_execution(
            execution_id="exec-1", input={"approved": True}
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/workflows/executions/exec-1/resume"
        assert call_kwargs["body"] == {"input": {"approved": True}}

    def test_get_execution_children(self, mock_transport):
        """Test listing child executions (body is a JSON array)."""
        mock_transport.perform_request.return_value = ListApiResponse(
            body=[],
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.workflows.get_execution_children(execution_id="exec-1")

        assert isinstance(result.body, list)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/workflows/executions/exec-1/children"

    def test_get_execution_logs(self, mock_transport):
        """Test retrieving execution logs with sort and pagination."""
        _mock_object_response(
            mock_transport,
            {
                "logs": [
                    {
                        "timestamp": "2026-07-03T20:03:37.914Z",
                        "level": "info",
                        "message": "hello",
                    }
                ],
                "total": 1,
                "page": 1,
                "size": 50,
            },
        )

        client = Kibana(_transport=mock_transport)
        result = client.workflows.get_execution_logs(
            execution_id="exec-1",
            step_execution_id="step-exec-1",
            size=50,
            page=1,
            sort_field="timestamp",
            sort_order="asc",
        )

        assert result.body["logs"][0]["message"] == "hello"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/workflows/executions/exec-1/logs"
            "?stepExecutionId=step-exec-1&size=50&page=1"
            "&sortField=timestamp&sortOrder=asc"
        )

    def test_get_step_execution(self, mock_transport):
        """Test getting a single step execution."""
        _mock_object_response(
            mock_transport,
            {"id": "step-exec-1", "stepId": "log_step", "status": "completed"},
        )

        client = Kibana(_transport=mock_transport)
        result = client.workflows.get_step_execution(
            execution_id="exec-1", step_execution_id="step-exec-1"
        )

        assert result.body["stepId"] == "log_step"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/workflows/executions/exec-1/step/step-exec-1"
        )


class TestWorkflowsClientErrorHandling:
    """Test error mapping for the workflows namespace."""

    def test_get_not_found_error(self, mock_transport):
        """Test that a 404 response raises NotFoundError."""
        _mock_object_response(
            mock_transport,
            {
                "statusCode": 404,
                "error": "Not Found",
                "message": "Workflow not found",
            },
            status=404,
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(NotFoundError):
            client.workflows.get(id="missing-workflow")

    def test_create_bad_request_error(self, mock_transport):
        """Test that a 400 response raises BadRequestError."""
        _mock_object_response(
            mock_transport,
            {
                "statusCode": 400,
                "error": "Bad Request",
                "message": "Invalid workflow yaml",
            },
            status=400,
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(BadRequestError):
            client.workflows.create(yaml="not: [valid")

    def test_resume_conflict_error(self, mock_transport):
        """Test that a 409 response raises ConflictError."""
        _mock_object_response(
            mock_transport,
            {
                "statusCode": 409,
                "error": "Conflict",
                "message": (
                    'Workflow execution "exec-1" is in status "completed" '
                    'but expected "waiting_for_input".'
                ),
            },
            status=409,
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(ConflictError):
            client.workflows.resume_execution(execution_id="exec-1", input={})
