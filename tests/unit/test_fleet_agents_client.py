"""Unit tests for FleetAgentsClient."""

import pytest

from kibana._sync.client import Kibana
from kibana._sync.client.fleet_agents import FleetAgentsClient
from kibana.exceptions import BadRequestError, NotFoundError


def _agent_body(**overrides):
    """Build a representative agent object."""
    agent = {
        "id": "agent-id-1",
        "type": "PERMANENT",
        "active": True,
        "enrolled_at": "2026-01-01T00:00:00.000Z",
        "local_metadata": {"host": {"hostname": "my-host"}},
        "packages": [],
        "effective_config": None,
        "status": "online",
        "policy_id": "agent-policy-id-1",
        "policy_revision": 1,
        "tags": ["production"],
    }
    agent.update(overrides)
    return agent


class TestFleetAgentsClientInitialization:
    """Test FleetAgentsClient initialization."""

    def test_fleet_agents_client_initialization(self, mock_transport):
        """Test that FleetAgentsClient can be initialized with a parent client."""
        client = Kibana(_transport=mock_transport)
        fleet_agents_client = FleetAgentsClient(client)
        assert fleet_agents_client._client is client

    def test_fleet_agents_property_returns_client(self, mock_transport):
        """Test that client.fleet_agents returns a FleetAgentsClient instance."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.fleet_agents, FleetAgentsClient)

    def test_fleet_agents_property_caching(self, mock_transport):
        """Test that the fleet_agents property returns the same instance."""
        client = Kibana(_transport=mock_transport)
        assert client.fleet_agents is client.fleet_agents


class TestFleetAgentsStatus:
    """Test agent status summary and incoming data methods."""

    def test_get_status(self, mock_transport, mock_response):
        """Test get_status without filters."""
        mock_transport.perform_request.return_value = mock_response(
            body={"results": {"online": 5, "error": 1, "offline": 2}}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.get_status()

        assert result.body["results"]["online"] == 5
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/agent_status"
        assert call_kwargs["headers"]["accept"] == "application/json"

    def test_get_status_with_filters(self, mock_transport, mock_response):
        """Test get_status query encoding (policyIds as repeated keys)."""
        mock_transport.perform_request.return_value = mock_response(
            body={"results": {"online": 0}}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.get_status(
            policy_id="p1", policy_ids=["p1", "p2"], kuery="status:online"
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/fleet/agent_status"
            "?policyId=p1&policyIds=p1&policyIds=p2&kuery=status%3Aonline"
        )

    def test_get_incoming_data(self, mock_transport, mock_response):
        """Test get_incoming_data with all query parameters."""
        mock_transport.perform_request.return_value = mock_response(
            body={"items": [{"a1": {"data": False}}], "dataPreview": []}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.get_incoming_data(
            agents_ids=["a1", "a2"],
            pkg_name="nginx",
            pkg_version="1.0.0",
            preview_data=True,
        )

        assert result.body["items"][0]["a1"]["data"] is False
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/fleet/agent_status/data"
            "?agentsIds=a1&agentsIds=a2&pkgName=nginx"
            "&pkgVersion=1.0.0&previewData=true"
        )


class TestFleetAgentsListAndCrud:
    """Test agent listing and per-agent CRUD methods."""

    def test_get_all_defaults(self, mock_transport, mock_response):
        """Test get_all without parameters."""
        mock_transport.perform_request.return_value = mock_response(
            body={"items": [_agent_body()], "total": 1, "page": 1, "perPage": 20}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.get_all()

        assert result.body["total"] == 1
        assert result.body["items"][0]["id"] == "agent-id-1"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/agents"

    def test_get_all_with_params(self, mock_transport, mock_response):
        """Test get_all query parameter encoding (camelCase, lowercase bools)."""
        mock_transport.perform_request.return_value = mock_response(
            body={"items": [], "total": 0, "page": 2, "perPage": 5}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.get_all(
            page=2,
            per_page=5,
            kuery='fleet-agents.tags : "prod"',
            show_agentless=False,
            show_inactive=True,
            with_metrics=True,
            show_upgradeable=False,
            get_status_summary=True,
            sort_field="enrolled_at",
            sort_order="desc",
            search_after="[123]",
            open_pit=True,
            pit_id="pit-1",
            pit_keep_alive="1m",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        target = call_kwargs["target"]
        assert target.startswith("/api/fleet/agents?")
        assert "page=2" in target
        assert "perPage=5" in target
        assert "kuery=fleet-agents.tags+%3A+%22prod%22" in target
        assert "showAgentless=false" in target
        assert "showInactive=true" in target
        assert "withMetrics=true" in target
        assert "showUpgradeable=false" in target
        assert "getStatusSummary=true" in target
        assert "sortField=enrolled_at" in target
        assert "sortOrder=desc" in target
        assert "searchAfter=%5B123%5D" in target
        assert "openPit=true" in target
        assert "pitId=pit-1" in target
        assert "pitKeepAlive=1m" in target

    def test_get_by_actions(self, mock_transport, mock_response):
        """Test get_by_actions body passthrough and header injection."""
        mock_transport.perform_request.return_value = mock_response(
            body={"items": ["agent-id-1"]}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.get_by_actions(action_ids=["act-1", "act-2"])

        assert result.body["items"] == ["agent-id-1"]
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agents"
        assert call_kwargs["body"] == {"actionIds": ["act-1", "act-2"]}
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs["headers"]["content-type"] == "application/json"

    def test_get(self, mock_transport, mock_response):
        """Test get with the withMetrics query parameter."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": _agent_body()}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.get(agent_id="agent-id-1", with_metrics=True)

        assert result.body["item"]["status"] == "online"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/agents/agent-id-1?withMetrics=true"

    def test_get_url_encodes_agent_id(self, mock_transport, mock_response):
        """Test that path parameters are URL-encoded."""
        mock_transport.perform_request.return_value = mock_response(body={"item": {}})

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.get(agent_id="agent/1 x")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/fleet/agents/agent%2F1%20x"

    def test_update(self, mock_transport, mock_response):
        """Test update body construction."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": _agent_body(tags=["production", "linux"])}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.update(
            agent_id="agent-id-1",
            tags=["production", "linux"],
            user_provided_metadata={"team": "sre"},
        )

        assert result.body["item"]["tags"] == ["production", "linux"]
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/fleet/agents/agent-id-1"
        assert call_kwargs["body"] == {
            "tags": ["production", "linux"],
            "user_provided_metadata": {"team": "sre"},
        }

    def test_delete(self, mock_transport, mock_response):
        """Test delete."""
        mock_transport.perform_request.return_value = mock_response(
            body={"action": "deleted"}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.delete(agent_id="agent-id-1")

        assert result.body["action"] == "deleted"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/fleet/agents/agent-id-1"


class TestFleetAgentsPerAgentOperations:
    """Test per-agent action methods."""

    def test_create_action(self, mock_transport, mock_response):
        """Test create_action wraps the action object."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "act-1", "type": "SETTINGS"}}
        )

        client = Kibana(_transport=mock_transport)
        action = {"type": "SETTINGS", "data": {"log_level": "debug"}}
        result = client.fleet_agents.create_action(agent_id="agent-id-1", action=action)

        assert result.body["item"]["type"] == "SETTINGS"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agents/agent-id-1/actions"
        assert call_kwargs["body"] == {"action": action}

    def test_get_effective_config(self, mock_transport, mock_response):
        """Test get_effective_config."""
        mock_transport.perform_request.return_value = mock_response(body={})

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.get_effective_config(agent_id="agent-id-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/agents/agent-id-1/effective_config"

    def test_migrate(self, mock_transport, mock_response):
        """Test migrate body construction."""
        mock_transport.perform_request.return_value = mock_response(
            body={"actionId": "act-1"}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.migrate(
            agent_id="agent-id-1",
            enrollment_token="token123",
            uri="https://fleet.example.com:8220",
            settings={"insecure": True},
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agents/agent-id-1/migrate"
        assert call_kwargs["body"] == {
            "enrollment_token": "token123",
            "uri": "https://fleet.example.com:8220",
            "settings": {"insecure": True},
        }

    def test_change_privilege_level(self, mock_transport, mock_response):
        """Test change_privilege_level body construction."""
        mock_transport.perform_request.return_value = mock_response(body={})

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.change_privilege_level(
            agent_id="agent-id-1",
            user_info={"username": "elastic-agent-user"},
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert (
            call_kwargs["target"]
            == "/api/fleet/agents/agent-id-1/privilege_level_change"
        )
        assert call_kwargs["body"] == {"user_info": {"username": "elastic-agent-user"}}

    def test_reassign(self, mock_transport, mock_response):
        """Test reassign body construction."""
        mock_transport.perform_request.return_value = mock_response(body={})

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.reassign(agent_id="agent-id-1", policy_id="policy-2")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agents/agent-id-1/reassign"
        assert call_kwargs["body"] == {"policy_id": "policy-2"}

    def test_request_diagnostics(self, mock_transport, mock_response):
        """Test request_diagnostics body construction."""
        mock_transport.perform_request.return_value = mock_response(
            body={"actionId": "act-1"}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.request_diagnostics(
            agent_id="agent-id-1", additional_metrics=["CPU"]
        )

        assert result.body["actionId"] == "act-1"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert (
            call_kwargs["target"] == "/api/fleet/agents/agent-id-1/request_diagnostics"
        )
        assert call_kwargs["body"] == {"additional_metrics": ["CPU"]}

    def test_rollback(self, mock_transport, mock_response):
        """Test rollback sends a POST without a body."""
        mock_transport.perform_request.return_value = mock_response(body={})

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.rollback(agent_id="agent-id-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agents/agent-id-1/rollback"
        assert "body" not in call_kwargs

    def test_unenroll(self, mock_transport, mock_response):
        """Test unenroll body construction."""
        mock_transport.perform_request.return_value = mock_response(body={})

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.unenroll(agent_id="agent-id-1", force=True, revoke=True)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agents/agent-id-1/unenroll"
        assert call_kwargs["body"] == {"force": True, "revoke": True}

    def test_upgrade(self, mock_transport, mock_response):
        """Test upgrade body construction."""
        mock_transport.perform_request.return_value = mock_response(body={})

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.upgrade(
            agent_id="agent-id-1",
            version="9.4.3",
            source_uri="https://artifacts.example.com",
            force=True,
            skip_rate_limit_check=True,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agents/agent-id-1/upgrade"
        assert call_kwargs["body"] == {
            "version": "9.4.3",
            "source_uri": "https://artifacts.example.com",
            "force": True,
            "skipRateLimitCheck": True,
        }

    def test_get_uploads(self, mock_transport, mock_response):
        """Test get_uploads."""
        mock_transport.perform_request.return_value = mock_response(body={"items": []})

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.get_uploads(agent_id="agent-id-1")

        assert result.body["items"] == []
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/agents/agent-id-1/uploads"


class TestFleetAgentsActions:
    """Test agent action bookkeeping methods."""

    def test_get_action_status(self, mock_transport, mock_response):
        """Test get_action_status query parameter encoding."""
        mock_transport.perform_request.return_value = mock_response(
            body={"items": [{"actionId": "act-1", "type": "UPGRADE"}]}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.get_action_status(
            page=0,
            per_page=10,
            date="2026-01-01T00:00:00.000Z",
            latest=100,
            error_size=3,
        )

        assert result.body["items"][0]["actionId"] == "act-1"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/fleet/agents/action_status"
            "?page=0&perPage=10&date=2026-01-01T00%3A00%3A00.000Z"
            "&latest=100&errorSize=3"
        )

    def test_cancel_action(self, mock_transport, mock_response):
        """Test cancel_action."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "cancel-1", "type": "CANCEL"}}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.cancel_action(action_id="act-1")

        assert result.body["item"]["type"] == "CANCEL"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agents/actions/act-1/cancel"
        assert "body" not in call_kwargs

    def test_get_available_versions(self, mock_transport, mock_response):
        """Test get_available_versions."""
        mock_transport.perform_request.return_value = mock_response(
            body={"items": ["9.4.3", "9.4.2"]}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.get_available_versions()

        assert "9.4.3" in result.body["items"]
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/agents/available_versions"


class TestFleetAgentsBulkOperations:
    """Test bulk agent operation methods."""

    def test_bulk_migrate(self, mock_transport, mock_response):
        """Test bulk_migrate body construction."""
        mock_transport.perform_request.return_value = mock_response(
            body={"actionId": "act-1"}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.bulk_migrate(
            agents=["a1", "a2"],
            enrollment_token="token123",
            uri="https://fleet.example.com:8220",
            settings={"insecure": True},
            batch_size=100,
        )

        assert result.body["actionId"] == "act-1"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agents/bulk_migrate"
        assert call_kwargs["body"] == {
            "agents": ["a1", "a2"],
            "enrollment_token": "token123",
            "uri": "https://fleet.example.com:8220",
            "settings": {"insecure": True},
            "batchSize": 100,
        }

    def test_bulk_change_privilege_level(self, mock_transport, mock_response):
        """Test bulk_change_privilege_level body construction."""
        mock_transport.perform_request.return_value = mock_response(
            body={"actionId": "act-1"}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.bulk_change_privilege_level(
            agents=["a1"], user_info={"username": "u"}, batch_size=50
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agents/bulk_privilege_level_change"
        assert call_kwargs["body"] == {
            "agents": ["a1"],
            "user_info": {"username": "u"},
            "batchSize": 50,
        }

    def test_bulk_reassign(self, mock_transport, mock_response):
        """Test bulk_reassign with a KQL string agent selector."""
        mock_transport.perform_request.return_value = mock_response(
            body={"actionId": "act-1"}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.bulk_reassign(
            agents='fleet-agents.status : "offline"',
            policy_id="policy-2",
            include_inactive=True,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agents/bulk_reassign"
        assert call_kwargs["body"] == {
            "agents": 'fleet-agents.status : "offline"',
            "policy_id": "policy-2",
            "includeInactive": True,
        }

    def test_bulk_request_diagnostics(self, mock_transport, mock_response):
        """Test bulk_request_diagnostics body construction."""
        mock_transport.perform_request.return_value = mock_response(
            body={"actionId": "act-1"}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.bulk_request_diagnostics(
            agents=["a1", "a2"], additional_metrics=["CPU"]
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/fleet/agents/bulk_request_diagnostics"
        assert call_kwargs["body"] == {
            "agents": ["a1", "a2"],
            "additional_metrics": ["CPU"],
        }

    def test_bulk_rollback(self, mock_transport, mock_response):
        """Test bulk_rollback body construction (returns actionIds list)."""
        mock_transport.perform_request.return_value = mock_response(
            body={"actionIds": ["act-1"]}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.bulk_rollback(
            agents=["a1"], include_inactive=False
        )

        assert result.body["actionIds"] == ["act-1"]
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/fleet/agents/bulk_rollback"
        assert call_kwargs["body"] == {"agents": ["a1"], "includeInactive": False}

    def test_bulk_unenroll(self, mock_transport, mock_response):
        """Test bulk_unenroll body construction."""
        mock_transport.perform_request.return_value = mock_response(
            body={"actionId": "act-1"}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.bulk_unenroll(
            agents=["a1", "a2"],
            force=True,
            revoke=True,
            batch_size=10,
            include_inactive=True,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/fleet/agents/bulk_unenroll"
        assert call_kwargs["body"] == {
            "agents": ["a1", "a2"],
            "force": True,
            "revoke": True,
            "batchSize": 10,
            "includeInactive": True,
        }

    def test_bulk_update_tags(self, mock_transport, mock_response):
        """Test bulk_update_tags body construction."""
        mock_transport.perform_request.return_value = mock_response(
            body={"actionId": "act-1"}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.bulk_update_tags(
            agents=["a1"],
            tags_to_add=["production"],
            tags_to_remove=["staging"],
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/fleet/agents/bulk_update_agent_tags"
        assert call_kwargs["body"] == {
            "agents": ["a1"],
            "tagsToAdd": ["production"],
            "tagsToRemove": ["staging"],
        }

    def test_bulk_upgrade(self, mock_transport, mock_response):
        """Test bulk_upgrade body construction."""
        mock_transport.perform_request.return_value = mock_response(
            body={"actionId": "act-1"}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.bulk_upgrade(
            agents=["a1", "a2"],
            version="9.4.3",
            source_uri="https://artifacts.example.com",
            rollout_duration_seconds=3600,
            start_time="2026-01-01T00:00:00.000Z",
            force=False,
            skip_rate_limit_check=True,
            batch_size=100,
            include_inactive=True,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/fleet/agents/bulk_upgrade"
        assert call_kwargs["body"] == {
            "agents": ["a1", "a2"],
            "version": "9.4.3",
            "source_uri": "https://artifacts.example.com",
            "rollout_duration_seconds": 3600,
            "start_time": "2026-01-01T00:00:00.000Z",
            "force": False,
            "skipRateLimitCheck": True,
            "batchSize": 100,
            "includeInactive": True,
        }


class TestFleetAgentsFiles:
    """Test uploaded file methods."""

    def test_get_file(self, mock_transport, mock_response):
        """Test get_file path construction with URL encoding."""
        mock_transport.perform_request.return_value = mock_response(body={})

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.get_file(file_id="file-1", file_name="diagnostics file.zip")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/fleet/agents/files/file-1/diagnostics%20file.zip"
        )

    def test_delete_file(self, mock_transport, mock_response):
        """Test delete_file."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "file-1", "deleted": True}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.delete_file(file_id="file-1")

        assert result.body["deleted"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/fleet/agents/files/file-1"


class TestFleetAgentsSetupAndTags:
    """Test setup and tags methods."""

    def test_get_setup_status(self, mock_transport, mock_response):
        """Test get_setup_status."""
        mock_transport.perform_request.return_value = mock_response(
            body={"isReady": False, "missing_requirements": ["fleet_server"]}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.get_setup_status()

        assert result.body["isReady"] is False
        assert result.body["missing_requirements"] == ["fleet_server"]
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/agents/setup"

    def test_initiate_setup(self, mock_transport, mock_response):
        """Test initiate_setup sends a POST without a body."""
        mock_transport.perform_request.return_value = mock_response(
            body={"isInitialized": True, "nonFatalErrors": []}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.initiate_setup()

        assert result.body["isInitialized"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agents/setup"
        assert "body" not in call_kwargs
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_get_tags(self, mock_transport, mock_response):
        """Test get_tags query parameter encoding."""
        mock_transport.perform_request.return_value = mock_response(
            body={"items": ["production", "linux"]}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_agents.get_tags(kuery="status:online", show_inactive=True)

        assert result.body["items"] == ["production", "linux"]
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/fleet/agents/tags?kuery=status%3Aonline&showInactive=true"
        )


class TestFleetAgentsSpaceScoping:
    """Test space-scoped path building."""

    def test_get_all_with_space_id(self, mock_transport, mock_response):
        """Test that space_id builds an /s/<space>/api/... path."""
        mock_transport.perform_request.return_value = mock_response(
            body={"items": [], "total": 0, "page": 1, "perPage": 20}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.get_all(space_id="marketing", validate_spaces=False)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/fleet/agents"

    def test_bulk_upgrade_with_space_id(self, mock_transport, mock_response):
        """Test that space_id scopes a mutating endpoint too."""
        mock_transport.perform_request.return_value = mock_response(
            body={"actionId": "act-1"}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_agents.bulk_upgrade(
            agents=["a1"],
            version="9.4.3",
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/fleet/agents/bulk_upgrade"


class TestFleetAgentsErrorHandling:
    """Test FleetAgentsClient error mapping."""

    def test_get_not_found_error(self, mock_transport, mock_response):
        """Test that a 404 response raises NotFoundError."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Agent agent-id-1 not found",
            },
            status=404,
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(NotFoundError, match="Agent agent-id-1 not found"):
            client.fleet_agents.get(agent_id="agent-id-1")

    def test_bulk_upgrade_bad_request_error(self, mock_transport, mock_response):
        """Test that a 400 response raises BadRequestError."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 400,
                "error": "Bad Request",
                "message": "[request body.version]: expected value of type [string]",
            },
            status=400,
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(BadRequestError):
            client.fleet_agents.bulk_upgrade(agents=["a1"], version="9.4.3")
