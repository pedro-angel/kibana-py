"""Integration tests for FleetAgentsClient against a live Kibana instance.

The dev stack has no enrolled Elastic Agents (and no Fleet Server), so:

- listing/status/action-bookkeeping endpoints are exercised live end-to-end,
- bulk operations are exercised live (the server creates real actions even
  when the selected agents do not exist; the actions then fail
  asynchronously, which is fine for API-contract testing),
- per-agent operations are exercised live via their semantic errors
  (the server's "Agent <id> not found" 404s prove routing and validation).
"""

import asyncio
import time
import uuid

import pytest

from kibana.exceptions import ApiError, BadRequestError, NotFoundError

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    is_kibana_available,
)

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)

PREFIX = "kbnpy-fleet-agents"


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
async def async_kibana_client():
    """Create an AsyncKibana client for testing with automatic configuration."""
    client = create_test_async_kibana_client(auth_method="auto")
    yield client
    await client.close()


@pytest.fixture
def fake_agent_id():
    """A unique agent ID that is guaranteed not to be enrolled."""
    return f"{PREFIX}-missing-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def agent_policy(kibana_client):
    """Create a throwaway agent policy (raw request) and delete it afterwards."""
    policy_name = f"{PREFIX}-policy-{uuid.uuid4().hex[:12]}"
    created = kibana_client.perform_request(
        "POST",
        "/api/fleet/agent_policies",
        params={"sys_monitoring": False},
        body={
            "name": policy_name,
            "namespace": "default",
            "description": "kibana-py fleet_agents integration test policy",
        },
    )
    policy_id = created.body["item"]["id"]
    yield policy_id
    kibana_client.perform_request(
        "POST",
        "/api/fleet/agent_policies/delete",
        body={"agentPolicyId": policy_id},
    )


class TestFleetAgentsReadEndpoints:
    """Live tests for the read-only Fleet agents endpoints."""

    def test_get_status(self, kibana_client):
        """Test the agent status summary endpoint."""
        result = kibana_client.fleet_agents.get_status()
        assert result.meta.status == 200
        results = result.body["results"]
        for key in ("online", "error", "offline", "updating", "all", "active"):
            assert isinstance(results[key], int)

    def test_get_status_with_policy_filter(self, kibana_client):
        """Test the agent status summary filtered by policy IDs."""
        result = kibana_client.fleet_agents.get_status(
            policy_ids=[f"{PREFIX}-no-such-policy"]
        )
        assert result.body["results"]["all"] == 0

    def test_get_incoming_data(self, kibana_client, fake_agent_id):
        """Test the incoming data endpoint reports no data for unknown agents."""
        result = kibana_client.fleet_agents.get_incoming_data(
            agents_ids=[fake_agent_id]
        )
        assert result.body["dataPreview"] == []
        assert result.body["items"] == [{fake_agent_id: {"data": False}}]

    def test_get_all(self, kibana_client):
        """Test listing agents with pagination info."""
        result = kibana_client.fleet_agents.get_all(per_page=5)
        assert isinstance(result.body["items"], list)
        assert isinstance(result.body["total"], int)
        assert result.body["page"] == 1
        assert result.body["perPage"] == 5

    def test_get_all_with_status_summary_and_kuery(self, kibana_client):
        """Test listing agents with a KQL filter and a status summary."""
        result = kibana_client.fleet_agents.get_all(
            kuery=f'fleet-agents.tags : "{PREFIX}-no-such-tag"',
            show_inactive=True,
            get_status_summary=True,
        )
        assert result.body["items"] == []
        assert "statusSummary" in result.body
        assert isinstance(result.body["statusSummary"], dict)

    def test_get_tags(self, kibana_client):
        """Test listing distinct agent tags."""
        result = kibana_client.fleet_agents.get_tags(show_inactive=True)
        assert isinstance(result.body["items"], list)

    def test_get_available_versions(self, kibana_client):
        """Test listing available agent versions."""
        result = kibana_client.fleet_agents.get_available_versions()
        versions = result.body["items"]
        assert isinstance(versions, list) and versions
        assert any(v.startswith("9.4") for v in versions)

    def test_get_setup_status(self, kibana_client):
        """Test the agent setup info endpoint."""
        result = kibana_client.fleet_agents.get_setup_status()
        assert isinstance(result.body["isReady"], bool)
        assert isinstance(result.body["missing_requirements"], list)

    def test_initiate_setup(self, kibana_client):
        """Test that initiating Fleet setup is idempotent."""
        result = kibana_client.fleet_agents.initiate_setup()
        assert result.body["isInitialized"] is True
        assert isinstance(result.body["nonFatalErrors"], list)

    def test_get_action_status(self, kibana_client):
        """Test listing agent action statuses."""
        result = kibana_client.fleet_agents.get_action_status(per_page=10)
        assert isinstance(result.body["items"], list)

    def test_get_uploads_for_unknown_agent(self, kibana_client, fake_agent_id):
        """Test that uploads for an unknown agent are an empty list (live 200)."""
        result = kibana_client.fleet_agents.get_uploads(agent_id=fake_agent_id)
        assert result.body["items"] == []


class TestFleetAgentsActionLifecycle:
    """Live round trip: create a bulk action, look it up, and cancel it."""

    def test_bulk_action_get_by_actions_and_cancel(self, kibana_client, fake_agent_id):
        """Test bulk_request_diagnostics -> action_status -> get_by_actions -> cancel.

        bulk_request_diagnostics is used because it persists a real action
        document even when the selected agents do not exist (unlike
        bulk_update_tags, whose actionId is not persisted when no agents
        match).
        """
        # Create a real agent action targeting a nonexistent agent; the server
        # queues the action and reports its progress via action_status.
        created = kibana_client.fleet_agents.bulk_request_diagnostics(
            agents=[fake_agent_id],
        )
        action_id = created.body["actionId"]
        assert isinstance(action_id, str) and action_id

        # The action must eventually show up in the action status list.
        deadline = time.time() + 30
        seen_ids: list[str] = []
        while time.time() < deadline:
            statuses = kibana_client.fleet_agents.get_action_status(per_page=100)
            seen_ids = [item["actionId"] for item in statuses.body["items"]]
            if action_id in seen_ids:
                break
            time.sleep(1)
        assert action_id in seen_ids

        # Look up agents associated with the action (none exist -> empty).
        by_actions = kibana_client.fleet_agents.get_by_actions(action_ids=[action_id])
        assert by_actions.body["items"] == []

        # Cancel the action; the server responds with a CANCEL action item.
        cancelled = kibana_client.fleet_agents.cancel_action(action_id=action_id)
        assert cancelled.body["item"]["type"] == "CANCEL"
        assert cancelled.body["item"]["id"]


class TestFleetAgentsBulkOperations:
    """Live tests for the bulk agent operations.

    No agents are enrolled, so each bulk call selects nonexistent agents:
    the server still creates and returns a real action (which later fails
    asynchronously for the unknown agents).
    """

    def test_bulk_unenroll(self, kibana_client, fake_agent_id):
        """Test bulk_unenroll returns an actionId."""
        result = kibana_client.fleet_agents.bulk_unenroll(
            agents=[fake_agent_id], revoke=True, include_inactive=True
        )
        assert isinstance(result.body["actionId"], str)

    def test_bulk_upgrade(self, kibana_client, fake_agent_id):
        """Test bulk_upgrade returns an actionId."""
        result = kibana_client.fleet_agents.bulk_upgrade(
            agents=[fake_agent_id], version="9.4.3", skip_rate_limit_check=True
        )
        assert isinstance(result.body["actionId"], str)

    def test_bulk_request_diagnostics(self, kibana_client, fake_agent_id):
        """Test bulk_request_diagnostics returns an actionId."""
        result = kibana_client.fleet_agents.bulk_request_diagnostics(
            agents=[fake_agent_id], additional_metrics=["CPU"]
        )
        assert isinstance(result.body["actionId"], str)

    def test_bulk_migrate(self, kibana_client, fake_agent_id):
        """Test bulk_migrate returns an actionId."""
        result = kibana_client.fleet_agents.bulk_migrate(
            agents=[fake_agent_id],
            enrollment_token=f"{PREFIX}-token",
            uri="https://fleet.example.com:8220",
        )
        assert isinstance(result.body["actionId"], str)

    def test_bulk_change_privilege_level(self, kibana_client, fake_agent_id):
        """Test bulk_change_privilege_level returns an actionId."""
        result = kibana_client.fleet_agents.bulk_change_privilege_level(
            agents=[fake_agent_id]
        )
        assert isinstance(result.body["actionId"], str)

    def test_bulk_update_tags(self, kibana_client, fake_agent_id):
        """Test bulk_update_tags returns an actionId.

        Note: when none of the selected agents exist the returned actionId
        is not persisted (it will not appear in action_status), but the 200
        response proves routing and payload validation.
        """
        result = kibana_client.fleet_agents.bulk_update_tags(
            agents=[fake_agent_id],
            tags_to_add=[f"{PREFIX}-tag"],
            tags_to_remove=[f"{PREFIX}-old-tag"],
        )
        assert isinstance(result.body["actionId"], str)

    def test_bulk_rollback(self, kibana_client, fake_agent_id):
        """Test bulk_rollback returns a list of actionIds (live shape)."""
        result = kibana_client.fleet_agents.bulk_rollback(agents=[fake_agent_id])
        assert isinstance(result.body["actionIds"], list)
        assert result.body["actionIds"]

    def test_bulk_reassign_unknown_policy(self, kibana_client, fake_agent_id):
        """Test bulk_reassign rejects an unknown target policy (semantic 404)."""
        with pytest.raises(NotFoundError, match="Agent policy not found"):
            kibana_client.fleet_agents.bulk_reassign(
                agents=[fake_agent_id],
                policy_id=f"{PREFIX}-no-such-policy",
            )

    def test_bulk_reassign_real_policy_no_agents(
        self, kibana_client, fake_agent_id, agent_policy
    ):
        """Test bulk_reassign with a real policy but no matching agents.

        The policy lookup succeeds; the server then rejects the call because
        none of the selected agents can be reassigned (semantic 400).
        """
        with pytest.raises(BadRequestError, match="No agents to reassign"):
            kibana_client.fleet_agents.bulk_reassign(
                agents=[fake_agent_id],
                policy_id=agent_policy,
            )


class TestFleetAgentsPerAgentSemanticErrors:
    """Live semantic-error tests for per-agent operations.

    No agents are enrolled on the stack, so the happy path cannot run; each
    test asserts the server's specific "Agent <id> not found" message, which
    proves the route and payload were accepted and validated.
    """

    def test_get_unknown_agent(self, kibana_client, fake_agent_id):
        """Test get raises a semantic 404."""
        with pytest.raises(NotFoundError, match=f"Agent {fake_agent_id} not found"):
            kibana_client.fleet_agents.get(agent_id=fake_agent_id)

    def test_update_unknown_agent(self, kibana_client, fake_agent_id):
        """Test update raises a semantic 404."""
        with pytest.raises(NotFoundError, match=f"Agent {fake_agent_id} not found"):
            kibana_client.fleet_agents.update(
                agent_id=fake_agent_id, tags=[f"{PREFIX}-tag"]
            )

    def test_delete_unknown_agent(self, kibana_client, fake_agent_id):
        """Test delete raises a semantic 404."""
        with pytest.raises(NotFoundError, match=f"Agent {fake_agent_id} not found"):
            kibana_client.fleet_agents.delete(agent_id=fake_agent_id)

    def test_create_action_unknown_agent(self, kibana_client, fake_agent_id):
        """Test create_action raises a semantic 404."""
        with pytest.raises(NotFoundError, match=f"Agent {fake_agent_id} not found"):
            kibana_client.fleet_agents.create_action(
                agent_id=fake_agent_id,
                action={"type": "SETTINGS", "data": {"log_level": "info"}},
            )

    def test_migrate_unknown_agent(self, kibana_client, fake_agent_id):
        """Test migrate raises a semantic 404."""
        with pytest.raises(NotFoundError, match=f"Agent {fake_agent_id} not found"):
            kibana_client.fleet_agents.migrate(
                agent_id=fake_agent_id,
                enrollment_token=f"{PREFIX}-token",
                uri="https://fleet.example.com:8220",
            )

    def test_change_privilege_level_unknown_agent(self, kibana_client, fake_agent_id):
        """Test change_privilege_level raises a semantic 404."""
        with pytest.raises(NotFoundError, match=f"Agent {fake_agent_id} not found"):
            kibana_client.fleet_agents.change_privilege_level(agent_id=fake_agent_id)

    def test_reassign_unknown_policy(self, kibana_client, fake_agent_id):
        """Test reassign validates the target policy first (semantic 404)."""
        with pytest.raises(
            NotFoundError, match=f"Agent policy not found: {PREFIX}-no-such-policy"
        ):
            kibana_client.fleet_agents.reassign(
                agent_id=fake_agent_id,
                policy_id=f"{PREFIX}-no-such-policy",
            )

    def test_reassign_real_policy_unknown_agent(
        self, kibana_client, fake_agent_id, agent_policy
    ):
        """Test reassign with a real policy raises the agent-not-found 404."""
        with pytest.raises(NotFoundError, match=f"Agent {fake_agent_id} not found"):
            kibana_client.fleet_agents.reassign(
                agent_id=fake_agent_id, policy_id=agent_policy
            )

    def test_request_diagnostics_unknown_agent(self, kibana_client, fake_agent_id):
        """Test request_diagnostics raises a semantic 404."""
        with pytest.raises(NotFoundError, match=f"Agent {fake_agent_id} not found"):
            kibana_client.fleet_agents.request_diagnostics(agent_id=fake_agent_id)

    def test_rollback_unknown_agent(self, kibana_client, fake_agent_id):
        """Test rollback raises a semantic 404."""
        with pytest.raises(NotFoundError, match=f"Agent {fake_agent_id} not found"):
            kibana_client.fleet_agents.rollback(agent_id=fake_agent_id)

    def test_unenroll_unknown_agent(self, kibana_client, fake_agent_id):
        """Test unenroll raises a semantic 404."""
        with pytest.raises(NotFoundError, match=f"Agent {fake_agent_id} not found"):
            kibana_client.fleet_agents.unenroll(agent_id=fake_agent_id)

    def test_upgrade_unknown_agent(self, kibana_client, fake_agent_id):
        """Test upgrade raises a semantic 404."""
        with pytest.raises(NotFoundError, match=f"Agent {fake_agent_id} not found"):
            kibana_client.fleet_agents.upgrade(agent_id=fake_agent_id, version="9.4.3")

    def test_get_effective_config_unknown_agent(self, kibana_client, fake_agent_id):
        """Test get_effective_config raises a 404.

        Without any enrolled agent the backing ``.fleet-agents`` index does
        not exist, so the live server 404s with an index_not_found message
        (once an agent has enrolled it would be "Agent <id> not found").
        """
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.fleet_agents.get_effective_config(agent_id=fake_agent_id)
        message = str(exc_info.value)
        assert "no such index" in message or "not found" in message.lower()

    def test_delete_file_unknown_file(self, kibana_client):
        """Test delete_file raises a 404 for a file that does not exist.

        Without any uploaded agent file the backing file-data index does not
        exist, so the live server 404s with an index_not_found message.
        """
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.fleet_agents.delete_file(file_id=f"{PREFIX}-no-such-file")
        message = str(exc_info.value)
        assert "no such index" in message or "not found" in message.lower()

    def test_get_file_unknown_file(self, kibana_client):
        """Test get_file errors for a file that does not exist.

        Spec/live discrepancy: the 9.4.3 spec documents only 200/400 for
        this endpoint, but the live server responds with a 500
        index_not_found error when no agent file was ever uploaded.
        """
        with pytest.raises(ApiError) as exc_info:
            kibana_client.fleet_agents.get_file(
                file_id=f"{PREFIX}-no-such-file",
                file_name="diagnostics.zip",
            )
        assert exc_info.value.status_code in (404, 500)
        assert "index_not_found" in str(exc_info.value) or "not found" in str(
            exc_info.value
        )


class TestFleetAgentsSpaceScoped:
    """Space-scoped live tests for the Fleet agents API."""

    def test_fleet_agents_in_custom_space(self, kibana_client):
        """Test that Fleet agents endpoints work under an /s/<space> prefix."""
        space_id = f"{PREFIX}-{uuid.uuid4().hex[:8]}"
        kibana_client.spaces.create(id=space_id, name=space_id)
        try:
            agents = kibana_client.fleet_agents.get_all(space_id=space_id)
            assert agents.body["items"] == []

            status = kibana_client.fleet_agents.get_status(space_id=space_id)
            assert "results" in status.body

            tags = kibana_client.fleet_agents.get_tags(space_id=space_id)
            assert isinstance(tags.body["items"], list)
        finally:
            kibana_client.spaces.delete(id=space_id)


class TestAsyncFleetAgents:
    """Async round-trip tests for the Fleet agents API."""

    @pytest.mark.asyncio
    async def test_async_action_round_trip(self, async_kibana_client, fake_agent_id):
        """Test list + bulk action + cancel + semantic 404 with the async client."""
        agents = await async_kibana_client.fleet_agents.get_all(per_page=1)
        assert isinstance(agents.body["items"], list)

        versions = await async_kibana_client.fleet_agents.get_available_versions()
        assert versions.body["items"]

        created = await async_kibana_client.fleet_agents.bulk_request_diagnostics(
            agents=[fake_agent_id],
        )
        action_id = created.body["actionId"]
        assert isinstance(action_id, str) and action_id

        # The action document may take a moment to become searchable.
        cancelled = None
        for _ in range(10):
            try:
                cancelled = await async_kibana_client.fleet_agents.cancel_action(
                    action_id=action_id
                )
                break
            except NotFoundError:
                await asyncio.sleep(1)
        assert cancelled is not None, f"action {action_id} never became cancellable"
        assert cancelled.body["item"]["type"] == "CANCEL"

        with pytest.raises(NotFoundError, match=f"Agent {fake_agent_id} not found"):
            await async_kibana_client.fleet_agents.get(agent_id=fake_agent_id)
