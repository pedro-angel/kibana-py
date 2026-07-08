"""Unit tests for FleetOutputsClient."""

import pytest

from kibana._sync.client import Kibana
from kibana._sync.client.fleet_outputs import FleetOutputsClient
from kibana.exceptions import BadRequestError, NotFoundError


def _output_item(**overrides):
    """Build a representative Fleet output response item."""
    item = {
        "id": "output-1",
        "name": "kbnpy-output",
        "type": "elasticsearch",
        "hosts": ["http://localhost:9200"],
        "is_default": False,
        "is_default_monitoring": False,
        "preset": "balanced",
    }
    item.update(overrides)
    return item


class TestFleetOutputsClientInitialization:
    """Test FleetOutputsClient initialization and wiring."""

    def test_client_initialization(self, mock_transport):
        """Test that FleetOutputsClient can be initialized with a parent."""
        client = Kibana(_transport=mock_transport)
        fleet_outputs_client = FleetOutputsClient(client)
        assert fleet_outputs_client._client is client

    def test_property_returns_fleet_outputs_client(self, mock_transport):
        """Test that client.fleet_outputs returns a FleetOutputsClient."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.fleet_outputs, FleetOutputsClient)

    def test_property_caching(self, mock_transport):
        """Test that the fleet_outputs property returns the same instance."""
        client = Kibana(_transport=mock_transport)
        assert client.fleet_outputs is client.fleet_outputs


class TestOutputs:
    """Test the outputs methods."""

    def test_get_outputs(self, mock_transport, mock_response):
        """Test listing outputs."""
        mock_transport.perform_request.return_value = mock_response(
            body={"items": [_output_item()], "page": 1, "perPage": 10000, "total": 1}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_outputs.get_outputs()

        assert result.body["total"] == 1
        assert result.body["items"][0]["type"] == "elasticsearch"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/outputs"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    def test_create_output_minimal(self, mock_transport, mock_response):
        """Test creating an Elasticsearch output with required params only."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": _output_item()}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_outputs.create_output(
            name="kbnpy-output",
            type="elasticsearch",
            hosts=["http://localhost:9200"],
        )

        assert result.body["item"]["id"] == "output-1"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/outputs"
        assert call_kwargs["body"] == {
            "name": "kbnpy-output",
            "type": "elasticsearch",
            "hosts": ["http://localhost:9200"],
        }
        assert call_kwargs["headers"]["content-type"] == "application/json"

    def test_create_output_kafka_with_fields(self, mock_transport, mock_response):
        """Test that type-specific properties in ``fields`` are merged."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": _output_item(type="kafka")}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.create_output(
            name="kbnpy-kafka",
            type="kafka",
            hosts=["kafka.example.com:9092"],
            is_default=False,
            config_yaml="key: value",
            fields={
                "auth_type": "user_pass",
                "username": "fleet",
                "password": "secret",
                "topic": "agent-events",
            },
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "name": "kbnpy-kafka",
            "type": "kafka",
            "hosts": ["kafka.example.com:9092"],
            "is_default": False,
            "config_yaml": "key: value",
            "auth_type": "user_pass",
            "username": "fleet",
            "password": "secret",
            "topic": "agent-events",
        }

    def test_get_output(self, mock_transport, mock_response):
        """Test getting an output by ID with URL encoding."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": _output_item()}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_outputs.get_output(output_id="output 1")

        assert result.body["item"]["name"] == "kbnpy-output"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/outputs/output%201"

    def test_update_output_partial(self, mock_transport, mock_response):
        """Test that only provided properties are sent on update."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": _output_item(name="renamed")}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.update_output(output_id="output-1", name="renamed")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/fleet/outputs/output-1"
        assert call_kwargs["body"] == {"name": "renamed"}

    def test_delete_output(self, mock_transport, mock_response):
        """Test deleting an output."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "output-1"}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_outputs.delete_output(output_id="output-1")

        assert result.body["id"] == "output-1"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/fleet/outputs/output-1"

    def test_get_output_health(self, mock_transport, mock_response):
        """Test getting the latest output health."""
        mock_transport.perform_request.return_value = mock_response(
            body={"state": "UNKNOWN", "message": "", "timestamp": ""}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_outputs.get_output_health(output_id="output-1")

        assert result.body["state"] == "UNKNOWN"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/outputs/output-1/health"


class TestFleetServerHosts:
    """Test the Fleet Server hosts methods."""

    def test_get_fleet_server_hosts(self, mock_transport, mock_response):
        """Test listing Fleet Server hosts."""
        mock_transport.perform_request.return_value = mock_response(
            body={"items": [], "page": 0, "perPage": 0, "total": 0}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_outputs.get_fleet_server_hosts()

        assert result.body["items"] == []

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/fleet_server_hosts"

    def test_create_fleet_server_host(self, mock_transport, mock_response):
        """Test creating a Fleet Server host."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "item": {
                    "id": "fsh-1",
                    "name": "kbnpy-fsh",
                    "host_urls": ["https://fleet.example.com:8220"],
                    "is_default": False,
                    "is_preconfigured": False,
                }
            }
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_outputs.create_fleet_server_host(
            name="kbnpy-fsh",
            host_urls=["https://fleet.example.com:8220"],
            is_default=False,
        )

        assert result.body["item"]["id"] == "fsh-1"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/fleet_server_hosts"
        assert call_kwargs["body"] == {
            "name": "kbnpy-fsh",
            "host_urls": ["https://fleet.example.com:8220"],
            "is_default": False,
        }

    def test_get_fleet_server_host(self, mock_transport, mock_response):
        """Test getting a Fleet Server host by ID."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "fsh-1"}}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.get_fleet_server_host(item_id="fsh-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/fleet_server_hosts/fsh-1"

    def test_update_fleet_server_host_partial(self, mock_transport, mock_response):
        """Test that only provided properties are sent on update."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "fsh-1", "name": "renamed"}}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.update_fleet_server_host(item_id="fsh-1", name="renamed")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/fleet/fleet_server_hosts/fsh-1"
        assert call_kwargs["body"] == {"name": "renamed"}

    def test_delete_fleet_server_host(self, mock_transport, mock_response):
        """Test deleting a Fleet Server host."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "fsh-1"}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.delete_fleet_server_host(item_id="fsh-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/fleet/fleet_server_hosts/fsh-1"


class TestProxies:
    """Test the proxies methods."""

    def test_get_proxies(self, mock_transport, mock_response):
        """Test listing proxies."""
        mock_transport.perform_request.return_value = mock_response(
            body={"items": [], "page": 1, "perPage": 10000, "total": 0}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.get_proxies()

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/proxies"

    def test_create_proxy(self, mock_transport, mock_response):
        """Test creating a proxy."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "item": {
                    "id": "proxy-1",
                    "name": "kbnpy-proxy",
                    "url": "https://proxy.example.com:3128",
                    "is_preconfigured": False,
                }
            }
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_outputs.create_proxy(
            name="kbnpy-proxy",
            url="https://proxy.example.com:3128",
            proxy_headers={"X-Forwarded-For": "kbnpy"},
        )

        assert result.body["item"]["id"] == "proxy-1"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/proxies"
        assert call_kwargs["body"] == {
            "name": "kbnpy-proxy",
            "url": "https://proxy.example.com:3128",
            "proxy_headers": {"X-Forwarded-For": "kbnpy"},
        }

    def test_get_proxy(self, mock_transport, mock_response):
        """Test getting a proxy by ID."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "proxy-1"}}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.get_proxy(item_id="proxy-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/proxies/proxy-1"

    def test_update_proxy_partial(self, mock_transport, mock_response):
        """Test that only provided properties are sent on update."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "proxy-1", "name": "renamed"}}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.update_proxy(item_id="proxy-1", name="renamed")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/fleet/proxies/proxy-1"
        assert call_kwargs["body"] == {"name": "renamed"}

    def test_delete_proxy(self, mock_transport, mock_response):
        """Test deleting a proxy."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "proxy-1"}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.delete_proxy(item_id="proxy-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/fleet/proxies/proxy-1"


class TestAgentDownloadSources:
    """Test the agent binary download sources methods."""

    def test_get_agent_download_sources(self, mock_transport, mock_response):
        """Test listing agent binary download sources."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "items": [
                    {
                        "id": "fleet-default-download-source",
                        "name": "Elastic Artifacts",
                        "is_default": True,
                        "host": "https://artifacts.elastic.co/downloads/",
                    }
                ],
                "page": 1,
                "perPage": 10000,
                "total": 1,
            }
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_outputs.get_agent_download_sources()

        assert result.body["items"][0]["is_default"] is True

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/agent_download_sources"

    def test_create_agent_download_source(self, mock_transport, mock_response):
        """Test creating an agent binary download source."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "item": {
                    "id": "ads-1",
                    "name": "kbnpy-ads",
                    "host": "https://artifacts.example.com/downloads/",
                    "is_default": False,
                }
            }
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_outputs.create_agent_download_source(
            name="kbnpy-ads",
            host="https://artifacts.example.com/downloads/",
        )

        assert result.body["item"]["id"] == "ads-1"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agent_download_sources"
        assert call_kwargs["body"] == {
            "name": "kbnpy-ads",
            "host": "https://artifacts.example.com/downloads/",
        }

    def test_get_agent_download_source(self, mock_transport, mock_response):
        """Test getting an agent binary download source by ID."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "ads-1"}}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.get_agent_download_source(source_id="ads-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/agent_download_sources/ads-1"

    def test_update_agent_download_source(self, mock_transport, mock_response):
        """Test updating an agent binary download source (name+host required)."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "ads-1", "name": "renamed"}}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.update_agent_download_source(
            source_id="ads-1",
            name="renamed",
            host="https://artifacts.example.com/downloads/",
            is_default=False,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/fleet/agent_download_sources/ads-1"
        assert call_kwargs["body"] == {
            "name": "renamed",
            "host": "https://artifacts.example.com/downloads/",
            "is_default": False,
        }

    def test_delete_agent_download_source(self, mock_transport, mock_response):
        """Test deleting an agent binary download source."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "ads-1"}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.delete_agent_download_source(source_id="ads-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/fleet/agent_download_sources/ads-1"


class TestRemoteSyncedIntegrations:
    """Test the remote synced integrations methods."""

    def test_get_remote_synced_integrations_status(self, mock_transport, mock_response):
        """Test getting the local synced integrations status."""
        mock_transport.perform_request.return_value = mock_response(
            body={"error": "Follower index not found", "integrations": []}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_outputs.get_remote_synced_integrations_status()

        assert result.body["integrations"] == []

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/remote_synced_integrations/status"

    def test_get_remote_synced_integrations_remote_status(
        self, mock_transport, mock_response
    ):
        """Test getting the synced integrations status by output ID."""
        mock_transport.perform_request.return_value = mock_response(
            body={"integrations": []}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.get_remote_synced_integrations_remote_status(
            output_id="remote-1"
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert (
            call_kwargs["target"]
            == "/api/fleet/remote_synced_integrations/remote-1/remote_status"
        )


class TestCloudConnectors:
    """Test the cloud connectors methods."""

    def test_get_cloud_connectors(self, mock_transport, mock_response):
        """Test listing cloud connectors with pagination params."""
        mock_transport.perform_request.return_value = mock_response(body={"items": []})

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.get_cloud_connectors(
            page=1, per_page=5, kuery="cloudProvider: aws"
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/fleet/cloud_connectors" "?page=1&perPage=5&kuery=cloudProvider%3A+aws"
        )

    def test_get_cloud_connectors_no_params(self, mock_transport, mock_response):
        """Test listing cloud connectors without params."""
        mock_transport.perform_request.return_value = mock_response(body={"items": []})

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.get_cloud_connectors()

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/fleet/cloud_connectors"

    def test_create_cloud_connector(self, mock_transport, mock_response):
        """Test creating a cloud connector with camelCase body keys."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "cc-1", "cloudProvider": "aws"}}
        )

        vars_ = {
            "role_arn": {
                "value": "arn:aws:iam::123456789012:role/kbnpy",
                "type": "text",
            },
            "external_id": {
                "value": {"id": "AbCdEfGhIjKlMnOpQrSt", "isSecretRef": True},
                "type": "password",
            },
        }
        client = Kibana(_transport=mock_transport)
        result = client.fleet_outputs.create_cloud_connector(
            name="arn:aws:iam::123456789012:role/kbnpy",
            cloud_provider="aws",
            vars=vars_,
            account_type="single-account",
        )

        assert result.body["item"]["id"] == "cc-1"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/cloud_connectors"
        assert call_kwargs["body"] == {
            "name": "arn:aws:iam::123456789012:role/kbnpy",
            "cloudProvider": "aws",
            "vars": vars_,
            "accountType": "single-account",
        }

    def test_get_cloud_connector(self, mock_transport, mock_response):
        """Test getting a cloud connector by ID."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "cc-1"}}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.get_cloud_connector(cloud_connector_id="cc-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/cloud_connectors/cc-1"

    def test_update_cloud_connector_partial(self, mock_transport, mock_response):
        """Test that only provided properties are sent on update."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "cc-1", "name": "renamed"}}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.update_cloud_connector(
            cloud_connector_id="cc-1", name="renamed"
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/fleet/cloud_connectors/cc-1"
        assert call_kwargs["body"] == {"name": "renamed"}

    def test_delete_cloud_connector_with_force(self, mock_transport, mock_response):
        """Test deleting a cloud connector with the force query param."""
        mock_transport.perform_request.return_value = mock_response(body={"id": "cc-1"})

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.delete_cloud_connector(
            cloud_connector_id="cc-1", force=True
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/fleet/cloud_connectors/cc-1?force=true"

    def test_get_cloud_connector_usage(self, mock_transport, mock_response):
        """Test getting cloud connector usage with pagination."""
        mock_transport.perform_request.return_value = mock_response(
            body={"items": [], "total": 0, "page": 1, "perPage": 10}
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_outputs.get_cloud_connector_usage(
            cloud_connector_id="cc-1", page=1, per_page=10
        )

        assert result.body["total"] == 0

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert (
            call_kwargs["target"]
            == "/api/fleet/cloud_connectors/cc-1/usage?page=1&perPage=10"
        )


class TestSpaceScoping:
    """Test space-scoped path building."""

    def test_get_outputs_space_scoped(self, mock_transport, mock_response):
        """Test that space_id builds a /s/<space>/api/... path."""
        mock_transport.perform_request.return_value = mock_response(
            body={"items": [], "page": 1, "perPage": 10000, "total": 0}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.get_outputs(space_id="marketing", validate_spaces=False)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/fleet/outputs"

    def test_create_proxy_space_scoped(self, mock_transport, mock_response):
        """Test that mutating methods honor space_id as well."""
        mock_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "proxy-1"}}
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_outputs.create_proxy(
            name="kbnpy-proxy",
            url="https://proxy.example.com:3128",
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/fleet/proxies"


class TestErrorHandling:
    """Test error mapping."""

    def test_get_output_not_found(self, mock_transport, mock_response):
        """Test that a 404 response raises NotFoundError."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Output missing-output not found",
            },
            status=404,
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(NotFoundError):
            client.fleet_outputs.get_output(output_id="missing-output")

    def test_get_cloud_connector_not_found_maps_to_bad_request(
        self, mock_transport, mock_response
    ):
        """Test the cloud connector API's 400-wrapped not-found errors."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 400,
                "error": "Bad Request",
                "message": (
                    "Error getting cloud connectors in Fleet, Failed to get "
                    "cloud connector: Saved object "
                    "[fleet-cloud-connector/missing-cc] not found"
                ),
            },
            status=400,
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(BadRequestError):
            client.fleet_outputs.get_cloud_connector(cloud_connector_id="missing-cc")
