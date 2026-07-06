"""Unit tests for FleetPoliciesClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ListApiResponse, ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.fleet_policies import FleetPoliciesClient
from kibana.exceptions import BadRequestError, NotFoundError


def _agent_policy_item(**overrides):
    """Build a representative agent policy body (Kibana 9.4.3 shape)."""
    item = {
        "id": "c9f83c10-5d0f-4a04-99c6-4baa5de4fc31",
        "version": "WzU1MCwyXQ==",
        "created_at": "2026-07-06T21:28:12.163Z",
        "space_ids": ["default"],
        "description": "test policy",
        "inactivity_timeout": 1209600,
        "schema_version": "1.1.1",
        "name": "kbnpy-fleet_policies-test",
        "namespace": "default",
        "status": "active",
        "is_managed": False,
        "revision": 1,
        "updated_at": "2026-07-06T21:28:12.163Z",
        "updated_by": "elastic",
        "is_protected": False,
    }
    item.update(overrides)
    return item


def _package_policy_item(**overrides):
    """Build a representative package policy body (Kibana 9.4.3 shape)."""
    item = {
        "id": "747e725b-02d0-4737-8c22-914e1568d054",
        "version": "WzU3NSwyXQ==",
        "name": "kbnpy-fleet_policies-pkg",
        "namespace": "",
        "package": {"name": "log", "title": "Custom Logs", "version": "2.4.4"},
        "enabled": True,
        "policy_id": "c9f83c10-5d0f-4a04-99c6-4baa5de4fc31",
        "policy_ids": ["c9f83c10-5d0f-4a04-99c6-4baa5de4fc31"],
        "inputs": {"logs-logfile": {"enabled": True, "streams": {}}},
        "revision": 1,
    }
    item.update(overrides)
    return item


def _object_response(body):
    """Wrap a dict body in an ObjectApiResponse with 200 metadata."""
    return ObjectApiResponse(body=body, meta=Mock(status=200, headers={}))


def _list_response(body):
    """Wrap a list body in a ListApiResponse with 200 metadata."""
    return ListApiResponse(body=body, meta=Mock(status=200, headers={}))


class TestFleetPoliciesClientInitialization:
    """Test FleetPoliciesClient initialization and wiring."""

    def test_fleet_policies_client_initialization(self, mock_transport):
        """Test that FleetPoliciesClient can be initialized with a parent."""
        client = Kibana(_transport=mock_transport)
        fleet_policies_client = FleetPoliciesClient(client)
        assert fleet_policies_client._client is client

    def test_fleet_policies_property_returns_client(self, mock_transport):
        """Test that client.fleet_policies returns a FleetPoliciesClient."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.fleet_policies, FleetPoliciesClient)

    def test_fleet_policies_property_caching(self, mock_transport):
        """Test that the fleet_policies property returns the same instance."""
        client = Kibana(_transport=mock_transport)
        assert client.fleet_policies is client.fleet_policies


class TestAgentPoliciesList:
    """Test get_agent_policies()."""

    def test_get_agent_policies_minimal(self, mock_transport):
        """Test listing agent policies with no parameters."""
        mock_transport.perform_request.return_value = _object_response(
            {"items": [_agent_policy_item()], "total": 1, "page": 1, "perPage": 20}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.get_agent_policies()

        assert result.body["total"] == 1
        assert result.body["items"][0]["name"] == "kbnpy-fleet_policies-test"

        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/agent_policies"
        assert call_kwargs["headers"]["accept"] == "application/json"

    def test_get_agent_policies_param_encoding(self, mock_transport):
        """Test that all query parameters are encoded with spec names."""
        mock_transport.perform_request.return_value = _object_response(
            {"items": [], "total": 0, "page": 2, "perPage": 5}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_policies.get_agent_policies(
            page=2,
            per_page=5,
            sort_field="name",
            sort_order="asc",
            show_upgradeable=True,
            kuery='ingest-agent-policies.name:"test"',
            no_agent_count=False,
            with_agent_count=True,
            full=False,
            format="simplified",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        target = call_kwargs["target"]
        assert target.startswith("/api/fleet/agent_policies?")
        assert "page=2" in target
        assert "perPage=5" in target
        assert "sortField=name" in target
        assert "sortOrder=asc" in target
        assert "showUpgradeable=true" in target
        assert "noAgentCount=false" in target
        assert "withAgentCount=true" in target
        assert "full=false" in target
        assert "format=simplified" in target

    def test_get_agent_policies_in_space(self, mock_transport):
        """Test that space_id builds an /s/<space>/api path."""
        mock_transport.perform_request.return_value = _object_response(
            {"items": [], "total": 0, "page": 1, "perPage": 20}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_policies.get_agent_policies(
            space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/fleet/agent_policies"


class TestAgentPolicyCreate:
    """Test create_agent_policy()."""

    def test_create_agent_policy_minimal(self, mock_transport):
        """Test creating an agent policy with required fields only."""
        mock_transport.perform_request.return_value = _object_response(
            {"item": _agent_policy_item()}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.create_agent_policy(
            name="kbnpy-fleet_policies-test", namespace="default"
        )

        assert result.body["item"]["status"] == "active"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agent_policies"
        assert call_kwargs["body"] == {
            "name": "kbnpy-fleet_policies-test",
            "namespace": "default",
        }
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_create_agent_policy_full_body(self, mock_transport):
        """Test optional body fields, camelCase mapping and query flag."""
        mock_transport.perform_request.return_value = _object_response(
            {"item": _agent_policy_item()}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_policies.create_agent_policy(
            name="kbnpy-fleet_policies-test",
            namespace="default",
            description="described",
            bump_revision=True,
            monitoring_enabled=["logs", "metrics"],
            inactivity_timeout=600,
            is_protected=False,
            global_data_tags=[{"name": "team", "value": "obs"}],
            sys_monitoring=False,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/fleet/agent_policies?sys_monitoring=false"
        )
        body = call_kwargs["body"]
        assert body["bumpRevision"] is True
        assert "bump_revision" not in body
        assert body["monitoring_enabled"] == ["logs", "metrics"]
        assert body["inactivity_timeout"] == 600
        assert body["is_protected"] is False
        assert body["global_data_tags"] == [{"name": "team", "value": "obs"}]
        assert "force" not in body


class TestAgentPolicyBulkGet:
    """Test bulk_get_agent_policies()."""

    def test_bulk_get_agent_policies(self, mock_transport):
        """Test bulk get body construction and format query param."""
        mock_transport.perform_request.return_value = _object_response(
            {"items": [_agent_policy_item()]}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.bulk_get_agent_policies(
            ids=["id-1", "id-2"],
            full=True,
            ignore_missing=True,
            format="legacy",
        )

        assert len(result.body["items"]) == 1

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/fleet/agent_policies/_bulk_get?format=legacy"
        )
        assert call_kwargs["body"] == {
            "ids": ["id-1", "id-2"],
            "full": True,
            "ignoreMissing": True,
        }


class TestAgentPolicyGet:
    """Test get_agent_policy()."""

    def test_get_agent_policy(self, mock_transport):
        """Test getting a single agent policy."""
        mock_transport.perform_request.return_value = _object_response(
            {"item": _agent_policy_item()}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.get_agent_policy(
            agent_policy_id="c9f83c10-5d0f-4a04-99c6-4baa5de4fc31",
            format="simplified",
        )

        assert result.body["item"]["namespace"] == "default"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/fleet/agent_policies/c9f83c10-5d0f-4a04-99c6-4baa5de4fc31"
            "?format=simplified"
        )

    def test_get_agent_policy_url_encodes_id(self, mock_transport):
        """Test that the policy ID is URL-encoded in the path."""
        mock_transport.perform_request.return_value = _object_response(
            {"item": _agent_policy_item()}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_policies.get_agent_policy(agent_policy_id="policy id/1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/fleet/agent_policies/policy%20id%2F1"

    def test_get_agent_policy_not_found(self, mock_transport):
        """Test that a 404 response maps to NotFoundError."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Agent policy not found",
            },
            meta=Mock(status=404, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(NotFoundError):
            client.fleet_policies.get_agent_policy(agent_policy_id="missing")


class TestAgentPolicyUpdate:
    """Test update_agent_policy()."""

    def test_update_agent_policy(self, mock_transport):
        """Test updating an agent policy."""
        mock_transport.perform_request.return_value = _object_response(
            {"item": _agent_policy_item(revision=2)}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.update_agent_policy(
            agent_policy_id="policy-1",
            name="kbnpy-fleet_policies-test",
            namespace="default",
            description="updated",
            force=True,
        )

        assert result.body["item"]["revision"] == 2

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/fleet/agent_policies/policy-1"
        assert call_kwargs["body"] == {
            "name": "kbnpy-fleet_policies-test",
            "namespace": "default",
            "description": "updated",
            "force": True,
        }


class TestAgentPolicyAutoUpgradeStatus:
    """Test get_auto_upgrade_agents_status()."""

    def test_get_auto_upgrade_agents_status(self, mock_transport):
        """Test getting the auto-upgrade agents status."""
        mock_transport.perform_request.return_value = _object_response(
            {"currentVersions": [], "totalAgents": 0}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.get_auto_upgrade_agents_status(
            agent_policy_id="policy-1"
        )

        assert result.body["totalAgents"] == 0

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/fleet/agent_policies/policy-1/auto_upgrade_agents_status"
        )


class TestAgentPolicyCopy:
    """Test copy_agent_policy()."""

    def test_copy_agent_policy(self, mock_transport):
        """Test copying an agent policy."""
        mock_transport.perform_request.return_value = _object_response(
            {"item": _agent_policy_item(id="copy-id", name="copied")}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.copy_agent_policy(
            agent_policy_id="policy-1",
            name="copied",
            description="a copy",
            format="legacy",
        )

        assert result.body["item"]["id"] == "copy-id"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/fleet/agent_policies/policy-1/copy?format=legacy"
        )
        assert call_kwargs["body"] == {"name": "copied", "description": "a copy"}


class TestAgentPolicyDownload:
    """Test download_agent_policy()."""

    def test_download_agent_policy(self, mock_transport):
        """Test downloading the YAML document with query params."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body="id: policy-1\noutputs:\n  default:\n    type: elasticsearch\n",
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.download_agent_policy(
            agent_policy_id="policy-1",
            download=True,
            standalone=True,
            kubernetes=False,
            revision=3,
        )

        assert result.body.startswith("id: policy-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        target = call_kwargs["target"]
        assert target.startswith("/api/fleet/agent_policies/policy-1/download?")
        assert "download=true" in target
        assert "standalone=true" in target
        assert "kubernetes=false" in target
        assert "revision=3" in target
        assert call_kwargs["headers"]["accept"] == "text/x-yaml, application/json"


class TestAgentPolicyFull:
    """Test get_full_agent_policy()."""

    def test_get_full_agent_policy(self, mock_transport):
        """Test getting the full compiled agent policy."""
        mock_transport.perform_request.return_value = _object_response(
            {"item": {"id": "policy-1", "outputs": {"default": {}}, "inputs": []}}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.get_full_agent_policy(
            agent_policy_id="policy-1", standalone=False
        )

        assert "outputs" in result.body["item"]

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/fleet/agent_policies/policy-1/full?standalone=false"
        )


class TestAgentPolicyOutputs:
    """Test get_agent_policy_outputs() and get_agent_policies_outputs()."""

    def test_get_agent_policy_outputs(self, mock_transport):
        """Test getting outputs for a single agent policy."""
        mock_transport.perform_request.return_value = _object_response(
            {
                "item": {
                    "monitoring": {"output": {"id": "fleet-default-output"}},
                    "data": {
                        "output": {"id": "fleet-default-output"},
                        "integrations": [],
                    },
                }
            }
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.get_agent_policy_outputs(
            agent_policy_id="policy-1"
        )

        assert result.body["item"]["data"]["output"]["id"] == "fleet-default-output"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/agent_policies/policy-1/outputs"

    def test_get_agent_policies_outputs(self, mock_transport):
        """Test getting outputs for multiple agent policies."""
        mock_transport.perform_request.return_value = _object_response(
            {"items": [{"agentPolicyId": "policy-1"}]}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.get_agent_policies_outputs(ids=["policy-1"])

        assert result.body["items"][0]["agentPolicyId"] == "policy-1"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agent_policies/outputs"
        assert call_kwargs["body"] == {"ids": ["policy-1"]}


class TestAgentPolicyDelete:
    """Test delete_agent_policy()."""

    def test_delete_agent_policy(self, mock_transport):
        """Test deleting an agent policy via the POST delete endpoint."""
        mock_transport.perform_request.return_value = _object_response(
            {"id": "policy-1", "name": "kbnpy-fleet_policies-test"}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.delete_agent_policy(
            agent_policy_id="policy-1", force=True
        )

        assert result.body["id"] == "policy-1"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agent_policies/delete"
        assert call_kwargs["body"] == {"agentPolicyId": "policy-1", "force": True}


class TestAgentlessPolicies:
    """Test create_agentless_policy() and delete_agentless_policy()."""

    def test_create_agentless_policy(self, mock_transport):
        """Test creating an agentless policy."""
        mock_transport.perform_request.return_value = _object_response(
            {"item": _package_policy_item()}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.create_agentless_policy(
            name="kbnpy-fleet_policies-agentless",
            package={"name": "cspm", "version": "1.0.0"},
            description="agentless test",
            vars={"setting": "value"},
            format="simplified",
        )

        assert "item" in result.body

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/fleet/agentless_policies?format=simplified"
        )
        assert call_kwargs["body"] == {
            "name": "kbnpy-fleet_policies-agentless",
            "package": {"name": "cspm", "version": "1.0.0"},
            "description": "agentless test",
            "vars": {"setting": "value"},
        }

    def test_create_agentless_policy_bad_request(self, mock_transport):
        """Test that the self-managed 400 rejection maps to BadRequestError."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 400,
                "error": "Bad Request",
                "message": (
                    "supports_agentless is only allowed in serverless and cloud "
                    "environments that support the agentless feature"
                ),
            },
            meta=Mock(status=400, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(BadRequestError, match="agentless feature"):
            client.fleet_policies.create_agentless_policy(
                name="kbnpy-fleet_policies-agentless",
                package={"name": "cspm", "version": "1.0.0"},
            )

    def test_delete_agentless_policy(self, mock_transport):
        """Test deleting an agentless policy with the force flag."""
        mock_transport.perform_request.return_value = _object_response(
            {"id": "agentless-1"}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.delete_agentless_policy(
            policy_id="agentless-1", force=True
        )

        assert result.body["id"] == "agentless-1"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == (
            "/api/fleet/agentless_policies/agentless-1?force=true"
        )


class TestPackagePoliciesList:
    """Test get_package_policies()."""

    def test_get_package_policies_minimal(self, mock_transport):
        """Test listing package policies with no parameters."""
        mock_transport.perform_request.return_value = _object_response(
            {"items": [_package_policy_item()], "total": 1, "page": 1, "perPage": 20}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.get_package_policies()

        assert result.body["total"] == 1

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/package_policies"

    def test_get_package_policies_param_encoding(self, mock_transport):
        """Test that all query parameters are encoded with spec names."""
        mock_transport.perform_request.return_value = _object_response(
            {"items": [], "total": 0, "page": 1, "perPage": 10}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_policies.get_package_policies(
            page=1,
            per_page=10,
            sort_field="name",
            sort_order="desc",
            show_upgradeable=False,
            kuery='ingest-package-policies.package.name:"log"',
            format="legacy",
            with_agent_count=True,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        target = call_kwargs["target"]
        assert target.startswith("/api/fleet/package_policies?")
        assert "perPage=10" in target
        assert "sortField=name" in target
        assert "sortOrder=desc" in target
        assert "showUpgradeable=false" in target
        assert "format=legacy" in target
        assert "withAgentCount=true" in target


class TestPackagePolicyCreate:
    """Test create_package_policy()."""

    def test_create_package_policy_simplified(self, mock_transport):
        """Test creating a package policy with simplified (dict) inputs."""
        mock_transport.perform_request.return_value = _object_response(
            {"item": _package_policy_item()}
        )

        inputs = {
            "logs-logfile": {
                "enabled": True,
                "streams": {
                    "log.logs": {
                        "enabled": True,
                        "vars": {"paths": ["/var/log/app.log"]},
                    }
                },
            }
        }

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.create_package_policy(
            name="kbnpy-fleet_policies-pkg",
            package={"name": "log", "version": "2.4.4"},
            policy_ids=["policy-1"],
            inputs=inputs,
        )

        assert result.body["item"]["package"]["name"] == "log"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/package_policies"
        assert call_kwargs["body"] == {
            "name": "kbnpy-fleet_policies-pkg",
            "package": {"name": "log", "version": "2.4.4"},
            "policy_ids": ["policy-1"],
            "inputs": inputs,
        }

    def test_create_package_policy_classic_body_mapping(self, mock_transport):
        """Test classic (list) inputs and the spaceIds camelCase mapping."""
        mock_transport.perform_request.return_value = _object_response(
            {"item": _package_policy_item()}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_policies.create_package_policy(
            name="kbnpy-fleet_policies-pkg",
            package={"name": "log", "version": "2.4.4"},
            policy_ids=["policy-1"],
            inputs=[{"type": "logfile", "enabled": True, "streams": []}],
            space_ids=["default"],
            enabled=True,
            force=True,
            format="legacy",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/fleet/package_policies?format=legacy"
        body = call_kwargs["body"]
        assert body["inputs"] == [{"type": "logfile", "enabled": True, "streams": []}]
        assert body["spaceIds"] == ["default"]
        assert "space_ids" not in body
        assert body["enabled"] is True
        assert body["force"] is True


class TestPackagePolicyBulkGet:
    """Test bulk_get_package_policies()."""

    def test_bulk_get_package_policies(self, mock_transport):
        """Test bulk get body construction and ignoreMissing mapping."""
        mock_transport.perform_request.return_value = _object_response(
            {"items": [_package_policy_item()]}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.bulk_get_package_policies(
            ids=["pkg-1"], ignore_missing=True, format="simplified"
        )

        assert len(result.body["items"]) == 1

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/fleet/package_policies/_bulk_get?format=simplified"
        )
        assert call_kwargs["body"] == {"ids": ["pkg-1"], "ignoreMissing": True}


class TestPackagePolicyGet:
    """Test get_package_policy()."""

    def test_get_package_policy(self, mock_transport):
        """Test getting a single package policy."""
        mock_transport.perform_request.return_value = _object_response(
            {"item": _package_policy_item()}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.get_package_policy(
            package_policy_id="pkg-1", format="simplified"
        )

        assert result.body["item"]["enabled"] is True

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/fleet/package_policies/pkg-1?format=simplified"
        )

    def test_get_package_policy_url_encodes_id(self, mock_transport):
        """Test that the package policy ID is URL-encoded in the path."""
        mock_transport.perform_request.return_value = _object_response(
            {"item": _package_policy_item()}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_policies.get_package_policy(package_policy_id="pkg id/1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/fleet/package_policies/pkg%20id%2F1"


class TestPackagePolicyUpdate:
    """Test update_package_policy()."""

    def test_update_package_policy(self, mock_transport):
        """Test updating a package policy."""
        mock_transport.perform_request.return_value = _object_response(
            {"item": _package_policy_item(revision=2)}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.update_package_policy(
            package_policy_id="pkg-1",
            package={"name": "log", "version": "2.4.4"},
            name="kbnpy-fleet_policies-pkg",
            description="updated",
            version="WzU3NSwyXQ==",
        )

        assert result.body["item"]["revision"] == 2

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/fleet/package_policies/pkg-1"
        assert call_kwargs["body"] == {
            "package": {"name": "log", "version": "2.4.4"},
            "name": "kbnpy-fleet_policies-pkg",
            "description": "updated",
            "version": "WzU3NSwyXQ==",
        }


class TestPackagePolicyDelete:
    """Test delete_package_policy() and bulk_delete_package_policies()."""

    def test_delete_package_policy(self, mock_transport):
        """Test deleting a single package policy with the force flag."""
        mock_transport.perform_request.return_value = _object_response({"id": "pkg-1"})

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.delete_package_policy(
            package_policy_id="pkg-1", force=True
        )

        assert result.body["id"] == "pkg-1"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == ("/api/fleet/package_policies/pkg-1?force=true")

    def test_bulk_delete_package_policies(self, mock_transport):
        """Test bulk deleting package policies (list response body)."""
        mock_transport.perform_request.return_value = _list_response(
            [{"id": "pkg-1", "name": "kbnpy-fleet_policies-pkg", "success": True}]
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.bulk_delete_package_policies(
            package_policy_ids=["pkg-1"], force=True
        )

        assert result.body[0]["success"] is True

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/package_policies/delete"
        assert call_kwargs["body"] == {
            "packagePolicyIds": ["pkg-1"],
            "force": True,
        }


class TestPackagePolicyUpgrade:
    """Test upgrade_package_policies() and upgrade_package_policies_dry_run()."""

    def test_upgrade_package_policies(self, mock_transport):
        """Test upgrading package policies (list response body)."""
        mock_transport.perform_request.return_value = _list_response(
            [{"id": "pkg-1", "name": "kbnpy-fleet_policies-pkg", "success": True}]
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.upgrade_package_policies(
            package_policy_ids=["pkg-1"]
        )

        assert result.body[0]["success"] is True

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/package_policies/upgrade"
        assert call_kwargs["body"] == {"packagePolicyIds": ["pkg-1"]}

    def test_upgrade_package_policies_dry_run(self, mock_transport):
        """Test dry-running a package policy upgrade with a pinned version."""
        mock_transport.perform_request.return_value = _list_response(
            [
                {
                    "name": "kbnpy-fleet_policies-pkg",
                    "diff": [{"id": "pkg-1"}, {"id": "pkg-1"}],
                    "hasErrors": False,
                }
            ]
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_policies.upgrade_package_policies_dry_run(
            package_policy_ids=["pkg-1"], package_version="2.4.4"
        )

        assert result.body[0]["hasErrors"] is False

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/package_policies/upgrade/dryrun"
        assert call_kwargs["body"] == {
            "packagePolicyIds": ["pkg-1"],
            "packageVersion": "2.4.4",
        }
