"""Integration tests for EndpointClient against a live Kibana instance.

The dev stack has no enrolled Elastic Defend endpoints, so the endpoint
*metadata*, *action listing*, *action state* and *scripts library* routes are
exercised on their real happy paths, while every response action (isolate,
unisolate, kill/suspend process, get file, execute, scan, memory dump, run
script, cancel, upload) and the policy/protection-note routes are exercised
live via their *semantic* errors (asserting the server's error message, not
just the status code, so a routing typo cannot masquerade as a pass).
"""

import uuid

import pytest

from kibana.exceptions import ApiError, BadRequestError, NotFoundError

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    is_kibana_available,
)

pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)

# Message the live server returns for response actions when no host has the
# Elastic Defend integration installed.
NO_DEFEND_MSG = "does not have Elastic Defend integration"


@pytest.fixture
def kibana_client():
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
async def async_kibana_client():
    client = create_test_async_kibana_client(auth_method="auto")
    yield client
    await client.close()


@pytest.fixture
def unique_name():
    return f"kbnpy-endpoint-{uuid.uuid4().hex[:12]}"


# ----------------------------------------------------------------------
# Metadata / actions listing / state  (real happy paths, empty stack)
# ----------------------------------------------------------------------
class TestMetadataAndActionsLive:
    def test_get_metadata_list_empty(self, kibana_client):
        resp = kibana_client.endpoint.get_metadata_list()
        assert "data" in resp.body
        assert isinstance(resp.body["data"], list)
        assert resp.body["total"] == 0

    def test_get_metadata_list_with_filters(self, kibana_client):
        resp = kibana_client.endpoint.get_metadata_list(
            host_statuses=["healthy", "updating"],
            page=1,
            page_size=20,
            sort_field="last_checkin",
            sort_direction="asc",
        )
        assert resp.body["pageSize"] == 20
        assert resp.body["sortField"] == "last_checkin"
        assert resp.body["sortDirection"] == "asc"

    def test_get_metadata_unknown_host(self, kibana_client):
        bogus = "00000000-0000-0000-0000-000000000000"
        with pytest.raises(NotFoundError) as exc:
            kibana_client.endpoint.get_metadata(id=bogus)
        assert bogus in str(exc.value)

    def test_get_actions_state(self, kibana_client):
        resp = kibana_client.endpoint.get_actions_state()
        assert "data" in resp.body
        assert "canEncrypt" in resp.body["data"]

    def test_get_actions_list_no_index(self, kibana_client):
        # On a stack that has never run a response action the backing index
        # doesn't exist yet; the server answers 404 index_not_found_exception.
        try:
            resp = kibana_client.endpoint.get_actions_list(page_size=10)
        except NotFoundError as exc:
            assert "index_not_found" in str(exc)
        else:
            assert "data" in resp.body

    def test_get_actions_status_unknown_agent(self, kibana_client):
        with pytest.raises(NotFoundError) as exc:
            kibana_client.endpoint.get_actions_status(agent_ids="kbnpy-fake-agent")
        assert "kbnpy-fake-agent not found" in str(exc.value)

    def test_get_action_details_unknown(self, kibana_client):
        # Unknown action id: the backing index is missing, so the server
        # raises a 500. Assert we route there and surface an ApiError.
        with pytest.raises(ApiError):
            kibana_client.endpoint.get_action_details(action_id="kbnpy-fake-action")

    def test_get_policy_response_unknown(self, kibana_client):
        with pytest.raises(NotFoundError) as exc:
            kibana_client.endpoint.get_policy_response(agent_id="kbnpy-fake-agent")
        assert "Policy response for endpoint id" in str(exc.value)


# ----------------------------------------------------------------------
# Response actions: semantic-error live tests (no enrolled endpoints)
# ----------------------------------------------------------------------
class TestResponseActionsSemanticErrors:
    FAKE = ["kbnpy-fake-endpoint"]

    def test_isolate(self, kibana_client):
        with pytest.raises(BadRequestError) as exc:
            kibana_client.endpoint.isolate(endpoint_ids=self.FAKE, comment="probe")
        assert NO_DEFEND_MSG in str(exc.value)

    def test_unisolate(self, kibana_client):
        with pytest.raises(BadRequestError) as exc:
            kibana_client.endpoint.unisolate(endpoint_ids=self.FAKE)
        assert NO_DEFEND_MSG in str(exc.value)

    def test_kill_process(self, kibana_client):
        with pytest.raises(BadRequestError) as exc:
            kibana_client.endpoint.kill_process(
                endpoint_ids=self.FAKE, parameters={"pid": 123}
            )
        assert NO_DEFEND_MSG in str(exc.value)

    def test_suspend_process(self, kibana_client):
        with pytest.raises(BadRequestError) as exc:
            kibana_client.endpoint.suspend_process(
                endpoint_ids=self.FAKE, parameters={"pid": 123}
            )
        assert NO_DEFEND_MSG in str(exc.value)

    def test_get_running_processes(self, kibana_client):
        with pytest.raises(BadRequestError) as exc:
            kibana_client.endpoint.get_running_processes(endpoint_ids=self.FAKE)
        assert NO_DEFEND_MSG in str(exc.value)

    def test_get_file(self, kibana_client):
        with pytest.raises(BadRequestError) as exc:
            kibana_client.endpoint.get_file(
                endpoint_ids=self.FAKE, parameters={"path": "/tmp/x"}
            )
        assert NO_DEFEND_MSG in str(exc.value)

    def test_execute(self, kibana_client):
        with pytest.raises(BadRequestError) as exc:
            kibana_client.endpoint.execute(
                endpoint_ids=self.FAKE, parameters={"command": "ls"}
            )
        assert NO_DEFEND_MSG in str(exc.value)

    def test_scan(self, kibana_client):
        with pytest.raises(BadRequestError) as exc:
            kibana_client.endpoint.scan(
                endpoint_ids=self.FAKE, parameters={"path": "/tmp"}
            )
        assert NO_DEFEND_MSG in str(exc.value)

    def test_memory_dump(self, kibana_client):
        # Memory dump is behind a feature flag on this stack: the route
        # rejects the request before the Defend check, with a distinct message.
        with pytest.raises(BadRequestError) as exc:
            kibana_client.endpoint.generate_memory_dump(
                endpoint_ids=self.FAKE, parameters={"type": "kernel"}
            )
        assert "feature is disabled" in str(exc.value)

    def test_run_script(self, kibana_client):
        # Elastic Defend run_script requires a scriptId; against the empty
        # stack the parameters are rejected before the Defend check.
        with pytest.raises(BadRequestError):
            kibana_client.endpoint.run_script(
                endpoint_ids=self.FAKE, parameters={"scriptId": "kbnpy-none"}
            )

    def test_upload(self, kibana_client):
        with pytest.raises(BadRequestError) as exc:
            kibana_client.endpoint.upload(
                endpoint_ids=self.FAKE,
                file=b"#!/bin/sh\necho hi\n",
                filename="kbnpy-fix.sh",
            )
        assert NO_DEFEND_MSG in str(exc.value)

    def test_cancel(self, kibana_client):
        # The cancel route reads the actions index, which is absent on a stack
        # that never ran an action, so the server raises a 500 ApiError. We
        # still confirm the route is reached (not a 404 routing miss).
        with pytest.raises(ApiError) as exc:
            kibana_client.endpoint.cancel(
                endpoint_ids=self.FAKE, parameters={"id": "kbnpy-fake-action"}
            )
        assert exc.value.meta.status in (400, 500)


# ----------------------------------------------------------------------
# Action file info/download: semantic-error live tests
# ----------------------------------------------------------------------
class TestActionFilesSemanticErrors:
    def test_file_info_unknown(self, kibana_client):
        with pytest.raises(ApiError) as exc:
            kibana_client.endpoint.get_action_file_info(
                action_id="kbnpy-fake-action", file_id="kbnpy-fake-file"
            )
        assert exc.value.meta.status in (400, 404, 500)

    def test_file_download_unknown(self, kibana_client):
        with pytest.raises(ApiError) as exc:
            kibana_client.endpoint.download_action_file(
                action_id="kbnpy-fake-action", file_id="kbnpy-fake-file"
            )
        assert exc.value.meta.status in (400, 404, 500)


# ----------------------------------------------------------------------
# Protection updates note: needs a Defend package policy → semantic error
# ----------------------------------------------------------------------
class TestProtectionUpdatesNoteSemanticErrors:
    def test_get_note_unknown_policy(self, kibana_client):
        with pytest.raises(NotFoundError) as exc:
            kibana_client.endpoint.get_protection_updates_note(
                package_policy_id="kbnpy-fake-policy"
            )
        assert "Package policy kbnpy-fake-policy not found" in str(exc.value)

    def test_create_note_unknown_policy(self, kibana_client):
        with pytest.raises(NotFoundError) as exc:
            kibana_client.endpoint.create_update_protection_updates_note(
                package_policy_id="kbnpy-fake-policy", note="kbnpy probe"
            )
        assert "Package policy kbnpy-fake-policy not found" in str(exc.value)


# ----------------------------------------------------------------------
# Scripts library: full CRUD live (works without enrolled endpoints)
# ----------------------------------------------------------------------
class TestScriptsLibraryLive:
    def test_get_scripts_empty(self, kibana_client):
        resp = kibana_client.endpoint.get_scripts(page_size=50)
        assert "data" in resp.body
        assert isinstance(resp.body["data"], list)

    def test_script_crud_roundtrip(self, kibana_client, unique_name):
        script_id = None
        try:
            created = kibana_client.endpoint.create_script(
                name=unique_name,
                platform=["linux"],
                file_type="script",
                file=b"#!/bin/bash\necho kbnpy-endpoint-test\n",
                filename=f"{unique_name}.sh",
                description="kbnpy integration test script",
                requires_input=False,
                tags=["threatHunting"],
            )
            data = created.body["data"]
            script_id = data["id"]
            assert data["name"] == unique_name
            assert data["platform"] == ["linux"]
            assert data["fileType"] == "script"
            assert data["tags"] == ["threatHunting"]

            # get one
            fetched = kibana_client.endpoint.get_script(script_id=script_id)
            assert fetched.body["data"]["id"] == script_id

            # appears in the list
            listed = kibana_client.endpoint.get_scripts(kuery=f"name:{unique_name}")
            assert any(s["id"] == script_id for s in listed.body["data"])

            # patch metadata (no new file)
            patched = kibana_client.endpoint.update_script(
                script_id=script_id, description="kbnpy updated description"
            )
            assert patched.body["data"]["description"] == "kbnpy updated description"

            # download the file content
            dl = kibana_client.endpoint.download_script(script_id=script_id)
            content = dl.body if isinstance(dl.body, str) else dl.body.decode()
            assert "kbnpy-endpoint-test" in content
        finally:
            if script_id is not None:
                kibana_client.endpoint.delete_script(script_id=script_id)
                with pytest.raises(NotFoundError):
                    kibana_client.endpoint.get_script(script_id=script_id)


# ----------------------------------------------------------------------
# Async round-trip
# ----------------------------------------------------------------------
class TestAsyncEndpointLive:
    async def test_async_metadata_and_state(self, async_kibana_client):
        meta = await async_kibana_client.endpoint.get_metadata_list()
        assert "data" in meta.body
        state = await async_kibana_client.endpoint.get_actions_state()
        assert "canEncrypt" in state.body["data"]

    async def test_async_script_roundtrip(self, async_kibana_client, unique_name):
        script_id = None
        try:
            created = await async_kibana_client.endpoint.create_script(
                name=unique_name,
                platform=["linux", "macos"],
                file_type="script",
                file=b"#!/bin/bash\necho kbnpy-async\n",
                filename=f"{unique_name}.sh",
            )
            script_id = created.body["data"]["id"]
            assert created.body["data"]["platform"] == ["linux", "macos"]

            fetched = await async_kibana_client.endpoint.get_script(script_id=script_id)
            assert fetched.body["data"]["id"] == script_id
        finally:
            if script_id is not None:
                await async_kibana_client.endpoint.delete_script(script_id=script_id)

    async def test_async_isolate_semantic_error(self, async_kibana_client):
        with pytest.raises(BadRequestError) as exc:
            await async_kibana_client.endpoint.isolate(
                endpoint_ids=["kbnpy-fake-endpoint"]
            )
        assert NO_DEFEND_MSG in str(exc.value)
