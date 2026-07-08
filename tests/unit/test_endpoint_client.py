"""Unit tests for EndpointClient (Security Endpoint Management API)."""

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.endpoint import EndpointClient


def _resp(body=None, status=200):
    """Build a mock ObjectApiResponse."""
    if body is None:
        body = {}
    return ObjectApiResponse(body=body, meta=Mock(status=status, headers={}))


def _call(mock_transport):
    """Return the kwargs of the single perform_request call."""
    mock_transport.perform_request.assert_called_once()
    return mock_transport.perform_request.call_args[1]


class TestEndpointClientInit:
    def test_init(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.endpoint, EndpointClient)

    def test_property_caching(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        assert client.endpoint is client.endpoint


class TestMetadata:
    def test_get_metadata_list_minimal(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": [], "total": 0})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_metadata_list()
        kw = _call(mock_transport)
        assert kw["method"] == "GET"
        assert kw["target"] == "/api/endpoint/metadata"
        assert kw["headers"]["accept"] == "application/json"

    def test_get_metadata_list_params(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": []})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_metadata_list(
            host_statuses=["healthy", "updating"],
            page=1,
            page_size=50,
            kuery="host.name:*",
            sort_field="last_checkin",
            sort_direction="asc",
        )
        target = _call(mock_transport)["target"]
        assert "hostStatuses=healthy" in target
        assert "hostStatuses=updating" in target
        assert "pageSize=50" in target
        assert "sortField=last_checkin" in target
        assert "sortDirection=asc" in target
        assert "kuery=host.name" in target

    def test_get_metadata(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"id": "abc"})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_metadata(id="host id/1")
        kw = _call(mock_transport)
        assert kw["method"] == "GET"
        assert kw["target"] == "/api/endpoint/metadata/host%20id%2F1"


class TestActionsListingStatus:
    def test_get_actions_list_minimal(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": []})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_actions_list()
        kw = _call(mock_transport)
        assert kw["method"] == "GET"
        assert kw["target"] == "/api/endpoint/action"

    def test_get_actions_list_params(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": []})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_actions_list(
            page=2,
            page_size=20,
            commands=["isolate", "unisolate"],
            agent_ids=["a1", "a2"],
            user_ids="elastic",
            start_date="2026-01-01T00:00:00.000Z",
            end_date="2026-12-31T00:00:00.000Z",
            agent_types="endpoint",
            with_outputs=["act-1"],
            types=["manual"],
        )
        target = _call(mock_transport)["target"]
        assert "page=2" in target
        assert "commands=isolate" in target and "commands=unisolate" in target
        assert "agentIds=a1" in target and "agentIds=a2" in target
        assert "userIds=elastic" in target
        assert "agentTypes=endpoint" in target
        assert "withOutputs=act-1" in target
        assert "types=manual" in target

    def test_get_actions_status_list(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_actions_status(agent_ids=["a1", "a2"])
        kw = _call(mock_transport)
        assert kw["method"] == "GET"
        assert kw["target"].startswith("/api/endpoint/action_status?")
        assert "agent_ids=a1" in kw["target"] and "agent_ids=a2" in kw["target"]

    def test_get_actions_status_single(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_actions_status(agent_ids="a1")
        assert (
            _call(mock_transport)["target"]
            == "/api/endpoint/action_status?agent_ids=a1"
        )

    def test_get_action_details(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_action_details(action_id="act-1")
        assert _call(mock_transport)["target"] == "/api/endpoint/action/act-1"

    def test_get_actions_state(self, mock_transport):
        mock_transport.perform_request.return_value = _resp(
            {"data": {"canEncrypt": True}}
        )
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_actions_state()
        assert _call(mock_transport)["target"] == "/api/endpoint/action/state"

    def test_get_action_file_info(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_action_file_info(action_id="act-1", file_id="file-1")
        assert (
            _call(mock_transport)["target"] == "/api/endpoint/action/act-1/file/file-1"
        )

    def test_download_action_file(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({})
        client = Kibana(_transport=mock_transport)
        client.endpoint.download_action_file(action_id="act-1", file_id="file-1")
        kw = _call(mock_transport)
        assert kw["target"] == "/api/endpoint/action/act-1/file/file-1/download"
        assert kw["headers"]["accept"] == "application/octet-stream"


class TestResponseActions:
    def test_isolate(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.isolate(
            endpoint_ids=["e1"], comment="quarantine", case_ids=["c1"]
        )
        kw = _call(mock_transport)
        assert kw["method"] == "POST"
        assert kw["target"] == "/api/endpoint/action/isolate"
        assert kw["body"] == {
            "endpoint_ids": ["e1"],
            "case_ids": ["c1"],
            "comment": "quarantine",
        }

    def test_unisolate(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.unisolate(endpoint_ids=["e1"], agent_type="endpoint")
        kw = _call(mock_transport)
        assert kw["target"] == "/api/endpoint/action/unisolate"
        assert kw["body"] == {"endpoint_ids": ["e1"], "agent_type": "endpoint"}

    def test_kill_process(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.kill_process(endpoint_ids=["e1"], parameters={"pid": 123})
        kw = _call(mock_transport)
        assert kw["target"] == "/api/endpoint/action/kill_process"
        assert kw["body"] == {"endpoint_ids": ["e1"], "parameters": {"pid": 123}}

    def test_suspend_process(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.suspend_process(
            endpoint_ids=["e1"], parameters={"entity_id": "x"}
        )
        kw = _call(mock_transport)
        assert kw["target"] == "/api/endpoint/action/suspend_process"
        assert kw["body"]["parameters"] == {"entity_id": "x"}

    def test_get_running_processes(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_running_processes(endpoint_ids=["e1"])
        kw = _call(mock_transport)
        assert kw["target"] == "/api/endpoint/action/running_procs"
        assert kw["body"] == {"endpoint_ids": ["e1"]}

    def test_get_file(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_file(endpoint_ids=["e1"], parameters={"path": "/etc/x"})
        kw = _call(mock_transport)
        assert kw["target"] == "/api/endpoint/action/get_file"
        assert kw["body"]["parameters"] == {"path": "/etc/x"}

    def test_execute(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.execute(
            endpoint_ids=["e1"], parameters={"command": "ls", "timeout": 600}
        )
        kw = _call(mock_transport)
        assert kw["target"] == "/api/endpoint/action/execute"
        assert kw["body"]["parameters"] == {"command": "ls", "timeout": 600}

    def test_scan(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.scan(endpoint_ids=["e1"], parameters={"path": "/opt"})
        kw = _call(mock_transport)
        assert kw["target"] == "/api/endpoint/action/scan"
        assert kw["body"]["parameters"] == {"path": "/opt"}

    def test_generate_memory_dump(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.generate_memory_dump(
            endpoint_ids=["e1"], parameters={"type": "kernel"}
        )
        kw = _call(mock_transport)
        assert kw["target"] == "/api/endpoint/action/memory_dump"
        assert kw["body"]["parameters"] == {"type": "kernel"}

    def test_run_script(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.run_script(endpoint_ids=["e1"], parameters={"scriptId": "s1"})
        kw = _call(mock_transport)
        assert kw["target"] == "/api/endpoint/action/run_script"
        assert kw["body"]["parameters"] == {"scriptId": "s1"}

    def test_cancel(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.cancel(endpoint_ids=["e1"], parameters={"id": "act-1"})
        kw = _call(mock_transport)
        assert kw["target"] == "/api/endpoint/action/cancel"
        assert kw["body"]["parameters"] == {"id": "act-1"}

    def test_upload_multipart(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.upload(
            endpoint_ids=["e1"],
            file=b"payload-bytes",
            filename="fix.sh",
            parameters={"overwrite": True},
        )
        kw = _call(mock_transport)
        assert kw["method"] == "POST"
        assert kw["target"] == "/api/endpoint/action/upload"
        assert kw["headers"]["content-type"].startswith(
            "multipart/form-data; boundary="
        )
        body = kw["body"]
        assert isinstance(body, bytes)
        assert b'name="endpoint_ids"' in body
        assert b'["e1"]' in body
        assert b'name="parameters"' in body
        assert b'{"overwrite": true}' in body
        assert b'name="file"; filename="fix.sh"' in body
        assert b"payload-bytes" in body


class TestPolicyResponse:
    def test_get_policy_response(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"policy_response": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_policy_response(agent_id="agent-1")
        kw = _call(mock_transport)
        assert kw["method"] == "GET"
        assert kw["target"] == "/api/endpoint/policy_response?agentId=agent-1"


class TestProtectionUpdatesNote:
    def test_get_note(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"note": "x"})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_protection_updates_note(package_policy_id="pp1")
        kw = _call(mock_transport)
        assert kw["method"] == "GET"
        assert kw["target"] == "/api/endpoint/protection_updates_note/pp1"

    def test_create_update_note(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"note": "hi"})
        client = Kibana(_transport=mock_transport)
        client.endpoint.create_update_protection_updates_note(
            package_policy_id="pp1", note="hi"
        )
        kw = _call(mock_transport)
        assert kw["method"] == "POST"
        assert kw["target"] == "/api/endpoint/protection_updates_note/pp1"
        assert kw["body"] == {"note": "hi"}


class TestScriptsLibrary:
    def test_get_scripts(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": []})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_scripts(
            page=1, page_size=50, sort_field="name", sort_direction="desc", kuery="a:b"
        )
        kw = _call(mock_transport)
        assert kw["method"] == "GET"
        assert kw["target"].startswith("/api/endpoint/scripts_library?")
        assert "pageSize=50" in kw["target"]
        assert "sortField=name" in kw["target"]

    def test_get_script(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_script(script_id="s1")
        assert _call(mock_transport)["target"] == "/api/endpoint/scripts_library/s1"

    def test_create_script_multipart(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {"id": "s1"}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.create_script(
            name="collect",
            platform=["linux", "macos"],
            file_type="script",
            file=b"#!/bin/sh\necho hi\n",
            filename="collect.sh",
            requires_input=True,
            tags=["threatHunting"],
        )
        kw = _call(mock_transport)
        assert kw["method"] == "POST"
        assert kw["target"] == "/api/endpoint/scripts_library"
        ct = kw["headers"]["content-type"]
        assert ct.startswith("multipart/form-data; boundary=")
        body = kw["body"]
        assert b'name="name"' in body and b"collect" in body
        assert b'name="platform"' in body and b'["linux", "macos"]' in body
        assert b'name="fileType"' in body
        assert b'name="requiresInput"' in body and b"true" in body
        assert b'name="tags"' in body and b'["threatHunting"]' in body
        assert b'name="file"; filename="collect.sh"' in body
        assert b"echo hi" in body

    def test_update_script_metadata_only(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.update_script(script_id="s1", description="new")
        kw = _call(mock_transport)
        assert kw["method"] == "PATCH"
        assert kw["target"] == "/api/endpoint/scripts_library/s1"
        body = kw["body"]
        assert b'name="description"' in body and b"new" in body
        # No file part when file is not provided
        assert b'name="file"' not in body

    def test_update_script_with_file(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.update_script(
            script_id="s1", file=b"new-bytes", filename="u.sh", name="renamed"
        )
        body = _call(mock_transport)["body"]
        assert b'name="name"' in body and b"renamed" in body
        assert b'name="file"; filename="u.sh"' in body
        assert b"new-bytes" in body

    def test_delete_script(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({})
        client = Kibana(_transport=mock_transport)
        client.endpoint.delete_script(script_id="s1")
        kw = _call(mock_transport)
        assert kw["method"] == "DELETE"
        assert kw["target"] == "/api/endpoint/scripts_library/s1"

    def test_download_script(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({})
        client = Kibana(_transport=mock_transport)
        client.endpoint.download_script(script_id="s1")
        kw = _call(mock_transport)
        assert kw["target"] == "/api/endpoint/scripts_library/s1/download"
        assert kw["headers"]["accept"] == "application/octet-stream"


class TestSpaceScoping:
    def test_space_scoped_path(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": []})
        client = Kibana(_transport=mock_transport)
        client.endpoint.get_metadata_list(space_id="marketing", validate_spaces=False)
        assert _call(mock_transport)["target"] == "/s/marketing/api/endpoint/metadata"

    def test_space_scoped_post(self, mock_transport):
        mock_transport.perform_request.return_value = _resp({"data": {}})
        client = Kibana(_transport=mock_transport)
        client.endpoint.isolate(
            endpoint_ids=["e1"], space_id="team-a", validate_spaces=False
        )
        assert (
            _call(mock_transport)["target"] == "/s/team-a/api/endpoint/action/isolate"
        )


class TestErrorMapping:
    def test_not_found(self, mock_transport):
        from kibana.exceptions import NotFoundError

        mock_transport.perform_request.return_value = _resp(
            {"statusCode": 404, "error": "Not Found", "message": "not found"},
            status=404,
        )
        client = Kibana(_transport=mock_transport)
        with pytest.raises(NotFoundError):
            client.endpoint.get_metadata(id="missing")

    def test_bad_request(self, mock_transport):
        from kibana.exceptions import BadRequestError

        mock_transport.perform_request.return_value = _resp(
            {
                "statusCode": 400,
                "error": "Bad Request",
                "message": "The host does not have Elastic Defend integration installed",
            },
            status=400,
        )
        client = Kibana(_transport=mock_transport)
        with pytest.raises(BadRequestError):
            client.endpoint.isolate(endpoint_ids=["e1"])
