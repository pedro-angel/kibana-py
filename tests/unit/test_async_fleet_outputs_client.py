"""Unit tests for AsyncFleetOutputsClient."""

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client.fleet_outputs import AsyncFleetOutputsClient
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


class TestAsyncFleetOutputsClientInitialization:
    """Test AsyncFleetOutputsClient initialization and wiring."""

    @pytest.mark.asyncio
    async def test_client_initialization(self, mock_async_transport):
        """Test that AsyncFleetOutputsClient can be initialized with a parent."""
        client = AsyncKibana(_transport=mock_async_transport)
        fleet_outputs_client = AsyncFleetOutputsClient(client)
        assert fleet_outputs_client._client is client

    @pytest.mark.asyncio
    async def test_property_returns_fleet_outputs_client(self, mock_async_transport):
        """Test that client.fleet_outputs returns a AsyncFleetOutputsClient."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.fleet_outputs, AsyncFleetOutputsClient)

    @pytest.mark.asyncio
    async def test_property_caching(self, mock_async_transport):
        """Test that the fleet_outputs property returns the same instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert client.fleet_outputs is client.fleet_outputs


class TestAsyncOutputs:
    """Test the outputs methods."""

    @pytest.mark.asyncio
    async def test_get_outputs(self, mock_async_transport, mock_response):
        """Test listing outputs."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"items": [_output_item()], "page": 1, "perPage": 10000, "total": 1}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet_outputs.get_outputs()

        assert result.body["total"] == 1
        assert result.body["items"][0]["type"] == "elasticsearch"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/outputs"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    @pytest.mark.asyncio
    async def test_create_output_minimal(self, mock_async_transport, mock_response):
        """Test creating an Elasticsearch output with required params only."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"item": _output_item()}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet_outputs.create_output(
            name="kbnpy-output",
            type="elasticsearch",
            hosts=["http://localhost:9200"],
        )

        assert result.body["item"]["id"] == "output-1"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/outputs"
        assert call_kwargs["body"] == {
            "name": "kbnpy-output",
            "type": "elasticsearch",
            "hosts": ["http://localhost:9200"],
        }
        assert call_kwargs["headers"]["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_create_output_kafka_with_fields(
        self, mock_async_transport, mock_response
    ):
        """Test that type-specific properties in ``fields`` are merged."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"item": _output_item(type="kafka")}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.create_output(
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

        call_kwargs = mock_async_transport.perform_request.call_args[1]
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

    @pytest.mark.asyncio
    async def test_get_output(self, mock_async_transport, mock_response):
        """Test getting an output by ID with URL encoding."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"item": _output_item()}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet_outputs.get_output(output_id="output 1")

        assert result.body["item"]["name"] == "kbnpy-output"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/outputs/output%201"

    @pytest.mark.asyncio
    async def test_update_output_partial(self, mock_async_transport, mock_response):
        """Test that only provided properties are sent on update."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"item": _output_item(name="renamed")}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.update_output(output_id="output-1", name="renamed")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/fleet/outputs/output-1"
        assert call_kwargs["body"] == {"name": "renamed"}

    @pytest.mark.asyncio
    async def test_delete_output(self, mock_async_transport, mock_response):
        """Test deleting an output."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "output-1"}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet_outputs.delete_output(output_id="output-1")

        assert result.body["id"] == "output-1"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/fleet/outputs/output-1"

    @pytest.mark.asyncio
    async def test_get_output_health(self, mock_async_transport, mock_response):
        """Test getting the latest output health."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"state": "UNKNOWN", "message": "", "timestamp": ""}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet_outputs.get_output_health(output_id="output-1")

        assert result.body["state"] == "UNKNOWN"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/outputs/output-1/health"


class TestAsyncFleetServerHosts:
    """Test the Fleet Server hosts methods."""

    @pytest.mark.asyncio
    async def test_get_fleet_server_hosts(self, mock_async_transport, mock_response):
        """Test listing Fleet Server hosts."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"items": [], "page": 0, "perPage": 0, "total": 0}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet_outputs.get_fleet_server_hosts()

        assert result.body["items"] == []

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/fleet_server_hosts"

    @pytest.mark.asyncio
    async def test_create_fleet_server_host(self, mock_async_transport, mock_response):
        """Test creating a Fleet Server host."""
        mock_async_transport.perform_request.return_value = mock_response(
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

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet_outputs.create_fleet_server_host(
            name="kbnpy-fsh",
            host_urls=["https://fleet.example.com:8220"],
            is_default=False,
        )

        assert result.body["item"]["id"] == "fsh-1"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/fleet_server_hosts"
        assert call_kwargs["body"] == {
            "name": "kbnpy-fsh",
            "host_urls": ["https://fleet.example.com:8220"],
            "is_default": False,
        }

    @pytest.mark.asyncio
    async def test_get_fleet_server_host(self, mock_async_transport, mock_response):
        """Test getting a Fleet Server host by ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "fsh-1"}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.get_fleet_server_host(item_id="fsh-1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/fleet_server_hosts/fsh-1"

    @pytest.mark.asyncio
    async def test_update_fleet_server_host_partial(
        self, mock_async_transport, mock_response
    ):
        """Test that only provided properties are sent on update."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "fsh-1", "name": "renamed"}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.update_fleet_server_host(
            item_id="fsh-1", name="renamed"
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/fleet/fleet_server_hosts/fsh-1"
        assert call_kwargs["body"] == {"name": "renamed"}

    @pytest.mark.asyncio
    async def test_delete_fleet_server_host(self, mock_async_transport, mock_response):
        """Test deleting a Fleet Server host."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "fsh-1"}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.delete_fleet_server_host(item_id="fsh-1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/fleet/fleet_server_hosts/fsh-1"


class TestAsyncProxies:
    """Test the proxies methods."""

    @pytest.mark.asyncio
    async def test_get_proxies(self, mock_async_transport, mock_response):
        """Test listing proxies."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"items": [], "page": 1, "perPage": 10000, "total": 0}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.get_proxies()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/proxies"

    @pytest.mark.asyncio
    async def test_create_proxy(self, mock_async_transport, mock_response):
        """Test creating a proxy."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "item": {
                    "id": "proxy-1",
                    "name": "kbnpy-proxy",
                    "url": "https://proxy.example.com:3128",
                    "is_preconfigured": False,
                }
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet_outputs.create_proxy(
            name="kbnpy-proxy",
            url="https://proxy.example.com:3128",
            proxy_headers={"X-Forwarded-For": "kbnpy"},
        )

        assert result.body["item"]["id"] == "proxy-1"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/proxies"
        assert call_kwargs["body"] == {
            "name": "kbnpy-proxy",
            "url": "https://proxy.example.com:3128",
            "proxy_headers": {"X-Forwarded-For": "kbnpy"},
        }

    @pytest.mark.asyncio
    async def test_get_proxy(self, mock_async_transport, mock_response):
        """Test getting a proxy by ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "proxy-1"}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.get_proxy(item_id="proxy-1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/proxies/proxy-1"

    @pytest.mark.asyncio
    async def test_update_proxy_partial(self, mock_async_transport, mock_response):
        """Test that only provided properties are sent on update."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "proxy-1", "name": "renamed"}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.update_proxy(item_id="proxy-1", name="renamed")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/fleet/proxies/proxy-1"
        assert call_kwargs["body"] == {"name": "renamed"}

    @pytest.mark.asyncio
    async def test_delete_proxy(self, mock_async_transport, mock_response):
        """Test deleting a proxy."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "proxy-1"}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.delete_proxy(item_id="proxy-1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/fleet/proxies/proxy-1"


class TestAsyncAgentDownloadSources:
    """Test the agent binary download sources methods."""

    @pytest.mark.asyncio
    async def test_get_agent_download_sources(
        self, mock_async_transport, mock_response
    ):
        """Test listing agent binary download sources."""
        mock_async_transport.perform_request.return_value = mock_response(
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

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet_outputs.get_agent_download_sources()

        assert result.body["items"][0]["is_default"] is True

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/agent_download_sources"

    @pytest.mark.asyncio
    async def test_create_agent_download_source(
        self, mock_async_transport, mock_response
    ):
        """Test creating an agent binary download source."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "item": {
                    "id": "ads-1",
                    "name": "kbnpy-ads",
                    "host": "https://artifacts.example.com/downloads/",
                    "is_default": False,
                }
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet_outputs.create_agent_download_source(
            name="kbnpy-ads",
            host="https://artifacts.example.com/downloads/",
        )

        assert result.body["item"]["id"] == "ads-1"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/agent_download_sources"
        assert call_kwargs["body"] == {
            "name": "kbnpy-ads",
            "host": "https://artifacts.example.com/downloads/",
        }

    @pytest.mark.asyncio
    async def test_get_agent_download_source(self, mock_async_transport, mock_response):
        """Test getting an agent binary download source by ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "ads-1"}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.get_agent_download_source(source_id="ads-1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/agent_download_sources/ads-1"

    @pytest.mark.asyncio
    async def test_update_agent_download_source(
        self, mock_async_transport, mock_response
    ):
        """Test updating an agent binary download source (name+host required)."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "ads-1", "name": "renamed"}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.update_agent_download_source(
            source_id="ads-1",
            name="renamed",
            host="https://artifacts.example.com/downloads/",
            is_default=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/fleet/agent_download_sources/ads-1"
        assert call_kwargs["body"] == {
            "name": "renamed",
            "host": "https://artifacts.example.com/downloads/",
            "is_default": False,
        }

    @pytest.mark.asyncio
    async def test_delete_agent_download_source(
        self, mock_async_transport, mock_response
    ):
        """Test deleting an agent binary download source."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "ads-1"}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.delete_agent_download_source(source_id="ads-1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/fleet/agent_download_sources/ads-1"


class TestAsyncRemoteSyncedIntegrations:
    """Test the remote synced integrations methods."""

    @pytest.mark.asyncio
    async def test_get_remote_synced_integrations_status(
        self, mock_async_transport, mock_response
    ):
        """Test getting the local synced integrations status."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"error": "Follower index not found", "integrations": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet_outputs.get_remote_synced_integrations_status()

        assert result.body["integrations"] == []

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/remote_synced_integrations/status"

    @pytest.mark.asyncio
    async def test_get_remote_synced_integrations_remote_status(
        self, mock_async_transport, mock_response
    ):
        """Test getting the synced integrations status by output ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"integrations": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.get_remote_synced_integrations_remote_status(
            output_id="remote-1"
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert (
            call_kwargs["target"]
            == "/api/fleet/remote_synced_integrations/remote-1/remote_status"
        )


class TestAsyncCloudConnectors:
    """Test the cloud connectors methods."""

    @pytest.mark.asyncio
    async def test_get_cloud_connectors(self, mock_async_transport, mock_response):
        """Test listing cloud connectors with pagination params."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"items": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.get_cloud_connectors(
            page=1, per_page=5, kuery="cloudProvider: aws"
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/fleet/cloud_connectors" "?page=1&perPage=5&kuery=cloudProvider%3A+aws"
        )

    @pytest.mark.asyncio
    async def test_get_cloud_connectors_no_params(
        self, mock_async_transport, mock_response
    ):
        """Test listing cloud connectors without params."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"items": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.get_cloud_connectors()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/fleet/cloud_connectors"

    @pytest.mark.asyncio
    async def test_create_cloud_connector(self, mock_async_transport, mock_response):
        """Test creating a cloud connector with camelCase body keys."""
        mock_async_transport.perform_request.return_value = mock_response(
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
        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet_outputs.create_cloud_connector(
            name="arn:aws:iam::123456789012:role/kbnpy",
            cloud_provider="aws",
            vars=vars_,
            account_type="single-account",
        )

        assert result.body["item"]["id"] == "cc-1"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/cloud_connectors"
        assert call_kwargs["body"] == {
            "name": "arn:aws:iam::123456789012:role/kbnpy",
            "cloudProvider": "aws",
            "vars": vars_,
            "accountType": "single-account",
        }

    @pytest.mark.asyncio
    async def test_get_cloud_connector(self, mock_async_transport, mock_response):
        """Test getting a cloud connector by ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "cc-1"}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.get_cloud_connector(cloud_connector_id="cc-1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/cloud_connectors/cc-1"

    @pytest.mark.asyncio
    async def test_update_cloud_connector_partial(
        self, mock_async_transport, mock_response
    ):
        """Test that only provided properties are sent on update."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "cc-1", "name": "renamed"}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.update_cloud_connector(
            cloud_connector_id="cc-1", name="renamed"
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/fleet/cloud_connectors/cc-1"
        assert call_kwargs["body"] == {"name": "renamed"}

    @pytest.mark.asyncio
    async def test_delete_cloud_connector_with_force(
        self, mock_async_transport, mock_response
    ):
        """Test deleting a cloud connector with the force query param."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "cc-1"}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.delete_cloud_connector(
            cloud_connector_id="cc-1", force=True
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/fleet/cloud_connectors/cc-1?force=true"

    @pytest.mark.asyncio
    async def test_get_cloud_connector_usage(self, mock_async_transport, mock_response):
        """Test getting cloud connector usage with pagination."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"items": [], "total": 0, "page": 1, "perPage": 10}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet_outputs.get_cloud_connector_usage(
            cloud_connector_id="cc-1", page=1, per_page=10
        )

        assert result.body["total"] == 0

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert (
            call_kwargs["target"]
            == "/api/fleet/cloud_connectors/cc-1/usage?page=1&perPage=10"
        )


class TestAsyncSpaceScoping:
    """Test space-scoped path building."""

    @pytest.mark.asyncio
    async def test_get_outputs_space_scoped(self, mock_async_transport, mock_response):
        """Test that space_id builds a /s/<space>/api/... path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"items": [], "page": 1, "perPage": 10000, "total": 0}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.get_outputs(
            space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/fleet/outputs"

    @pytest.mark.asyncio
    async def test_create_proxy_space_scoped(self, mock_async_transport, mock_response):
        """Test that mutating methods honor space_id as well."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"item": {"id": "proxy-1"}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet_outputs.create_proxy(
            name="kbnpy-proxy",
            url="https://proxy.example.com:3128",
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/fleet/proxies"


class TestAsyncErrorHandling:
    """Test error mapping."""

    @pytest.mark.asyncio
    async def test_get_output_not_found(self, mock_async_transport, mock_response):
        """Test that a 404 response raises NotFoundError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Output missing-output not found",
            },
            status=404,
        )

        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(NotFoundError):
            await client.fleet_outputs.get_output(output_id="missing-output")

    @pytest.mark.asyncio
    async def test_get_cloud_connector_not_found_maps_to_bad_request(
        self, mock_async_transport, mock_response
    ):
        """Test the cloud connector API's 400-wrapped not-found errors."""
        mock_async_transport.perform_request.return_value = mock_response(
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

        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(BadRequestError):
            await client.fleet_outputs.get_cloud_connector(
                cloud_connector_id="missing-cc"
            )
