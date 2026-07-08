"""Unit tests for AsyncEndpointClient (Security Endpoint Management API)."""

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._async.client import AsyncKibana
from kibana._async.client.endpoint import AsyncEndpointClient


def _resp(body=None, status=200):
    if body is None:
        body = {}
    return ObjectApiResponse(body=body, meta=Mock(status=status, headers={}))


def _call(mock_async_transport):
    mock_async_transport.perform_request.assert_called_once()
    return mock_async_transport.perform_request.call_args[1]


class TestAsyncEndpointClientInit:
    def test_init(self, mock_async_transport):
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.endpoint, AsyncEndpointClient)

    def test_property_caching(self, mock_async_transport):
        client = AsyncKibana(_transport=mock_async_transport)
        assert client.endpoint is client.endpoint


class TestAsyncMetadata:
    async def test_get_metadata_list(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": []})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.get_metadata_list(host_statuses=["healthy"])
        kw = _call(mock_async_transport)
        assert kw["method"] == "GET"
        assert kw["target"].startswith("/api/endpoint/metadata")
        assert "hostStatuses=healthy" in kw["target"]

    async def test_get_metadata(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"id": "e1"})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.get_metadata(id="e1")
        assert _call(mock_async_transport)["target"] == "/api/endpoint/metadata/e1"


class TestAsyncActions:
    async def test_get_actions_list(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": []})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.get_actions_list(commands=["isolate"])
        kw = _call(mock_async_transport)
        assert kw["method"] == "GET"
        assert "commands=isolate" in kw["target"]

    async def test_get_actions_status(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.get_actions_status(agent_ids="a1")
        assert (
            _call(mock_async_transport)["target"]
            == "/api/endpoint/action_status?agent_ids=a1"
        )

    async def test_get_action_details(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.get_action_details(action_id="act-1")
        assert _call(mock_async_transport)["target"] == "/api/endpoint/action/act-1"

    async def test_get_actions_state(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp(
            {"data": {"canEncrypt": True}}
        )
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.get_actions_state()
        assert _call(mock_async_transport)["target"] == "/api/endpoint/action/state"

    async def test_get_action_file_info(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.get_action_file_info(action_id="act-1", file_id="f1")
        assert (
            _call(mock_async_transport)["target"]
            == "/api/endpoint/action/act-1/file/f1"
        )

    async def test_download_action_file(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.download_action_file(action_id="act-1", file_id="f1")
        kw = _call(mock_async_transport)
        assert kw["target"] == "/api/endpoint/action/act-1/file/f1/download"
        assert kw["headers"]["accept"] == "application/octet-stream"


class TestAsyncResponseActions:
    async def test_isolate(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.isolate(endpoint_ids=["e1"], comment="q")
        kw = _call(mock_async_transport)
        assert kw["method"] == "POST"
        assert kw["target"] == "/api/endpoint/action/isolate"
        assert kw["body"] == {"endpoint_ids": ["e1"], "comment": "q"}

    async def test_unisolate(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.unisolate(endpoint_ids=["e1"])
        assert _call(mock_async_transport)["target"] == "/api/endpoint/action/unisolate"

    async def test_kill_process(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.kill_process(endpoint_ids=["e1"], parameters={"pid": 1})
        kw = _call(mock_async_transport)
        assert kw["target"] == "/api/endpoint/action/kill_process"
        assert kw["body"]["parameters"] == {"pid": 1}

    async def test_suspend_process(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.suspend_process(
            endpoint_ids=["e1"], parameters={"pid": 1}
        )
        assert (
            _call(mock_async_transport)["target"]
            == "/api/endpoint/action/suspend_process"
        )

    async def test_get_running_processes(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.get_running_processes(endpoint_ids=["e1"])
        assert (
            _call(mock_async_transport)["target"]
            == "/api/endpoint/action/running_procs"
        )

    async def test_get_file(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.get_file(endpoint_ids=["e1"], parameters={"path": "/x"})
        assert _call(mock_async_transport)["target"] == "/api/endpoint/action/get_file"

    async def test_execute(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.execute(endpoint_ids=["e1"], parameters={"command": "ls"})
        assert _call(mock_async_transport)["target"] == "/api/endpoint/action/execute"

    async def test_scan(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.scan(endpoint_ids=["e1"], parameters={"path": "/x"})
        assert _call(mock_async_transport)["target"] == "/api/endpoint/action/scan"

    async def test_generate_memory_dump(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.generate_memory_dump(
            endpoint_ids=["e1"], parameters={"type": "kernel"}
        )
        assert (
            _call(mock_async_transport)["target"] == "/api/endpoint/action/memory_dump"
        )

    async def test_run_script(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.run_script(
            endpoint_ids=["e1"], parameters={"scriptId": "s1"}
        )
        assert (
            _call(mock_async_transport)["target"] == "/api/endpoint/action/run_script"
        )

    async def test_cancel(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.cancel(endpoint_ids=["e1"], parameters={"id": "act-1"})
        assert _call(mock_async_transport)["target"] == "/api/endpoint/action/cancel"

    async def test_upload(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.upload(endpoint_ids=["e1"], file=b"abc", filename="f.sh")
        kw = _call(mock_async_transport)
        assert kw["target"] == "/api/endpoint/action/upload"
        assert kw["headers"]["content-type"].startswith("multipart/form-data")
        assert b'name="file"; filename="f.sh"' in kw["body"]
        assert b"abc" in kw["body"]


class TestAsyncPolicyAndNote:
    async def test_get_policy_response(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.get_policy_response(agent_id="a1")
        assert (
            _call(mock_async_transport)["target"]
            == "/api/endpoint/policy_response?agentId=a1"
        )

    async def test_get_protection_updates_note(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.get_protection_updates_note(package_policy_id="pp1")
        assert (
            _call(mock_async_transport)["target"]
            == "/api/endpoint/protection_updates_note/pp1"
        )

    async def test_create_update_note(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.create_update_protection_updates_note(
            package_policy_id="pp1", note="hi"
        )
        kw = _call(mock_async_transport)
        assert kw["method"] == "POST"
        assert kw["body"] == {"note": "hi"}


class TestAsyncScriptsLibrary:
    async def test_get_scripts(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": []})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.get_scripts(page_size=50)
        kw = _call(mock_async_transport)
        assert kw["target"].startswith("/api/endpoint/scripts_library")
        assert "pageSize=50" in kw["target"]

    async def test_get_script(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.get_script(script_id="s1")
        assert (
            _call(mock_async_transport)["target"] == "/api/endpoint/scripts_library/s1"
        )

    async def test_create_script(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.create_script(
            name="s",
            platform=["linux"],
            file_type="script",
            file=b"echo hi",
            filename="s.sh",
        )
        kw = _call(mock_async_transport)
        assert kw["method"] == "POST"
        assert kw["target"] == "/api/endpoint/scripts_library"
        assert b'name="platform"' in kw["body"] and b'["linux"]' in kw["body"]

    async def test_update_script(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": {}})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.update_script(script_id="s1", description="d")
        kw = _call(mock_async_transport)
        assert kw["method"] == "PATCH"
        assert b'name="file"' not in kw["body"]

    async def test_delete_script(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.delete_script(script_id="s1")
        kw = _call(mock_async_transport)
        assert kw["method"] == "DELETE"
        assert kw["target"] == "/api/endpoint/scripts_library/s1"

    async def test_download_script(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.download_script(script_id="s1")
        kw = _call(mock_async_transport)
        assert kw["target"] == "/api/endpoint/scripts_library/s1/download"


class TestAsyncSpaceScopingAndErrors:
    async def test_space_scoped(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _resp({"data": []})
        client = AsyncKibana(_transport=mock_async_transport)
        await client.endpoint.get_metadata_list(
            space_id="marketing", validate_spaces=False
        )
        assert (
            _call(mock_async_transport)["target"]
            == "/s/marketing/api/endpoint/metadata"
        )

    async def test_not_found(self, mock_async_transport):
        from kibana.exceptions import NotFoundError

        mock_async_transport.perform_request.return_value = _resp(
            {"statusCode": 404, "error": "Not Found", "message": "not found"},
            status=404,
        )
        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(NotFoundError):
            await client.endpoint.get_metadata(id="missing")
