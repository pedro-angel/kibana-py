"""Integration tests for FleetOutputsClient against a live Kibana instance."""

import uuid

import pytest

from kibana.exceptions import BadRequestError, NotFoundError

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

PREFIX = "kbnpy-fleet_outputs"


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
def unique_name():
    """Generate a unique, prefixed resource name for testing."""
    return f"{PREFIX}-{uuid.uuid4().hex[:12]}"


def _cleanup_output(client, output_id: str) -> None:
    """Delete an output, ignoring the case where it is already gone."""
    try:
        client.fleet_outputs.delete_output(output_id=output_id)
    except NotFoundError:
        pass


class TestOutputsLifecycle:
    """Full lifecycle tests for the Fleet outputs API."""

    def test_elasticsearch_output_crud_and_health(self, kibana_client, unique_name):
        """Test create/list/get/update/health/delete for an ES output."""
        created = kibana_client.fleet_outputs.create_output(
            name=unique_name,
            type="elasticsearch",
            hosts=["http://localhost:9200"],
            is_default=False,
            is_default_monitoring=False,
        )
        output_id = created.body["item"]["id"]
        try:
            assert created.meta.status == 200
            assert created.body["item"]["name"] == unique_name
            assert created.body["item"]["type"] == "elasticsearch"
            assert created.body["item"]["is_default"] is False

            # List includes the new output (and the untouched default)
            listed = kibana_client.fleet_outputs.get_outputs()
            ids = [item["id"] for item in listed.body["items"]]
            assert output_id in ids
            assert "fleet-default-output" in ids

            # Get by ID
            fetched = kibana_client.fleet_outputs.get_output(output_id=output_id)
            assert fetched.body["item"]["hosts"] == ["http://localhost:9200"]

            # Partial update (rename only)
            updated = kibana_client.fleet_outputs.update_output(
                output_id=output_id, name=f"{unique_name}-renamed"
            )
            assert updated.body["item"]["name"] == f"{unique_name}-renamed"
            assert updated.body["item"]["hosts"] == ["http://localhost:9200"]

            # Health of a fresh output is reported as UNKNOWN
            health = kibana_client.fleet_outputs.get_output_health(output_id=output_id)
            assert health.body["state"] == "UNKNOWN"
        finally:
            _cleanup_output(kibana_client, output_id)

        with pytest.raises(NotFoundError):
            kibana_client.fleet_outputs.get_output(output_id=output_id)

    def test_kafka_output_with_type_specific_fields(self, kibana_client, unique_name):
        """Test creating a Kafka output using the ``fields`` passthrough."""
        created = kibana_client.fleet_outputs.create_output(
            name=unique_name,
            type="kafka",
            hosts=["kafka.example.com:9092"],
            fields={
                "auth_type": "user_pass",
                "username": "kbnpy",
                "password": "kbnpy-secret",
                "topic": f"{unique_name}-topic",
            },
        )
        output_id = created.body["item"]["id"]
        try:
            item = created.body["item"]
            assert item["type"] == "kafka"
            assert item["auth_type"] == "user_pass"
            assert item["topic"] == f"{unique_name}-topic"
            # Server-side Kafka defaults are applied
            assert item["compression"] == "gzip"
            assert item["required_acks"] == 1
        finally:
            _cleanup_output(kibana_client, output_id)

    def test_get_missing_output_semantic_not_found(self, kibana_client):
        """Test the server's 404 message for an unknown output ID."""
        missing_id = f"{PREFIX}-missing-{uuid.uuid4().hex[:8]}"
        with pytest.raises(NotFoundError) as excinfo:
            kibana_client.fleet_outputs.get_output(output_id=missing_id)
        assert f"Output {missing_id} not found" in str(excinfo.value)


class TestFleetServerHostsLifecycle:
    """Full lifecycle tests for the Fleet Server hosts API."""

    def test_fleet_server_host_crud(self, kibana_client, unique_name):
        """Test create/list/get/update/delete for a Fleet Server host."""
        created = kibana_client.fleet_outputs.create_fleet_server_host(
            name=unique_name,
            host_urls=["https://fleet.example.com:8220"],
            is_default=False,
        )
        item_id = created.body["item"]["id"]
        try:
            assert created.body["item"]["name"] == unique_name
            assert created.body["item"]["host_urls"] == [
                "https://fleet.example.com:8220"
            ]

            listed = kibana_client.fleet_outputs.get_fleet_server_hosts()
            assert item_id in [item["id"] for item in listed.body["items"]]

            fetched = kibana_client.fleet_outputs.get_fleet_server_host(item_id=item_id)
            assert fetched.body["item"]["id"] == item_id

            # Partial update (rename only) is accepted by the live server
            updated = kibana_client.fleet_outputs.update_fleet_server_host(
                item_id=item_id, name=f"{unique_name}-renamed"
            )
            assert updated.body["item"]["name"] == f"{unique_name}-renamed"
        finally:
            try:
                kibana_client.fleet_outputs.delete_fleet_server_host(item_id=item_id)
            except NotFoundError:
                pass

        with pytest.raises(NotFoundError) as excinfo:
            kibana_client.fleet_outputs.get_fleet_server_host(item_id=item_id)
        assert f"Fleet server {item_id} not found" in str(excinfo.value)


class TestProxiesLifecycle:
    """Full lifecycle tests for the Fleet proxies API."""

    def test_proxy_crud(self, kibana_client, unique_name):
        """Test create/list/get/update/delete for a Fleet proxy."""
        created = kibana_client.fleet_outputs.create_proxy(
            name=unique_name,
            url="https://proxy.example.com:3128",
            proxy_headers={"X-Kbnpy": "fleet-outputs"},
        )
        item_id = created.body["item"]["id"]
        try:
            assert created.body["item"]["name"] == unique_name
            assert created.body["item"]["url"] == "https://proxy.example.com:3128"

            listed = kibana_client.fleet_outputs.get_proxies()
            assert item_id in [item["id"] for item in listed.body["items"]]

            fetched = kibana_client.fleet_outputs.get_proxy(item_id=item_id)
            assert fetched.body["item"]["id"] == item_id

            updated = kibana_client.fleet_outputs.update_proxy(
                item_id=item_id, name=f"{unique_name}-renamed"
            )
            assert updated.body["item"]["name"] == f"{unique_name}-renamed"
        finally:
            try:
                kibana_client.fleet_outputs.delete_proxy(item_id=item_id)
            except NotFoundError:
                pass

        with pytest.raises(NotFoundError) as excinfo:
            kibana_client.fleet_outputs.get_proxy(item_id=item_id)
        assert f"Fleet proxy {item_id} not found" in str(excinfo.value)


class TestAgentDownloadSourcesLifecycle:
    """Full lifecycle tests for the agent binary download sources API."""

    def test_agent_download_source_crud(self, kibana_client, unique_name):
        """Test create/list/get/update/delete for a download source."""
        created = kibana_client.fleet_outputs.create_agent_download_source(
            name=unique_name,
            host="https://artifacts.example.com/downloads/",
        )
        source_id = created.body["item"]["id"]
        try:
            assert created.body["item"]["name"] == unique_name
            assert created.body["item"]["is_default"] is False

            listed = kibana_client.fleet_outputs.get_agent_download_sources()
            ids = [item["id"] for item in listed.body["items"]]
            assert source_id in ids
            # The preinstalled default source is untouched
            assert "fleet-default-download-source" in ids

            fetched = kibana_client.fleet_outputs.get_agent_download_source(
                source_id=source_id
            )
            assert fetched.body["item"]["id"] == source_id

            # name and host are required by the API on every update
            updated = kibana_client.fleet_outputs.update_agent_download_source(
                source_id=source_id,
                name=f"{unique_name}-renamed",
                host="https://artifacts.example.com/downloads/",
            )
            assert updated.body["item"]["name"] == f"{unique_name}-renamed"
        finally:
            try:
                kibana_client.fleet_outputs.delete_agent_download_source(
                    source_id=source_id
                )
            except NotFoundError:
                pass

        with pytest.raises(NotFoundError) as excinfo:
            kibana_client.fleet_outputs.get_agent_download_source(source_id=source_id)
        assert f"Agent binary source {source_id} not found" in str(excinfo.value)


class TestRemoteSyncedIntegrations:
    """Tests for the remote synced integrations status APIs."""

    def test_get_status(self, kibana_client):
        """Test the local synced integrations status endpoint."""
        status = kibana_client.fleet_outputs.get_remote_synced_integrations_status()
        assert status.meta.status == 200
        assert "integrations" in status.body
        assert isinstance(status.body["integrations"], list)

    def test_remote_status_requires_sync_enabled(self, kibana_client, unique_name):
        """Test the per-output remote status against a real remote ES output.

        Without a reachable remote cluster and ``sync_integrations`` enabled
        the server rejects the call with a semantic 400, which proves the
        route is wired correctly.
        """
        created = kibana_client.fleet_outputs.create_output(
            name=unique_name,
            type="remote_elasticsearch",
            hosts=["https://remote.example.com:9200"],
            secrets={"service_token": "kbnpy-fleet-outputs-token"},
        )
        output_id = created.body["item"]["id"]
        try:
            with pytest.raises(BadRequestError) as excinfo:
                kibana_client.fleet_outputs.get_remote_synced_integrations_remote_status(
                    output_id=output_id
                )
            assert "Synced integrations not enabled" in str(excinfo.value)
        finally:
            _cleanup_output(kibana_client, output_id)

    def test_remote_status_rejects_non_remote_output(self, kibana_client):
        """Test the per-output remote status against a non-remote output."""
        with pytest.raises(BadRequestError) as excinfo:
            kibana_client.fleet_outputs.get_remote_synced_integrations_remote_status(
                output_id="fleet-default-output"
            )
        assert "is not a remote elasticsearch output" in str(excinfo.value)


class TestCloudConnectorsLifecycle:
    """Full lifecycle tests for the Fleet cloud connectors API."""

    def test_cloud_connector_crud_and_usage(self, kibana_client):
        """Test create/list/get/update/usage/delete for a cloud connector."""
        role_arn = f"arn:aws:iam::123456789012:role/{PREFIX}-{uuid.uuid4().hex[:8]}"
        vars_ = {
            "role_arn": {"value": role_arn, "type": "text"},
            "external_id": {
                # The external ID must be a 20-char secret reference
                "value": {"id": uuid.uuid4().hex[:20], "isSecretRef": True},
                "type": "password",
            },
        }
        created = kibana_client.fleet_outputs.create_cloud_connector(
            name=role_arn,
            cloud_provider="aws",
            vars=vars_,
        )
        connector_id = created.body["item"]["id"]
        try:
            assert created.body["item"]["cloudProvider"] == "aws"
            assert created.body["item"]["packagePolicyCount"] == 0

            listed = kibana_client.fleet_outputs.get_cloud_connectors(
                page=1, per_page=100
            )
            assert connector_id in [item["id"] for item in listed.body["items"]]

            fetched = kibana_client.fleet_outputs.get_cloud_connector(
                cloud_connector_id=connector_id
            )
            assert fetched.body["item"]["name"] == role_arn

            updated = kibana_client.fleet_outputs.update_cloud_connector(
                cloud_connector_id=connector_id, name=f"{role_arn}-renamed"
            )
            assert updated.body["item"]["name"] == f"{role_arn}-renamed"

            usage = kibana_client.fleet_outputs.get_cloud_connector_usage(
                cloud_connector_id=connector_id, page=1, per_page=10
            )
            assert usage.body["total"] == 0
            assert usage.body["items"] == []
        finally:
            try:
                kibana_client.fleet_outputs.delete_cloud_connector(
                    cloud_connector_id=connector_id, force=True
                )
            except BadRequestError:
                pass

        # The cloud connector API wraps not-found errors in 400 responses
        with pytest.raises(BadRequestError) as excinfo:
            kibana_client.fleet_outputs.get_cloud_connector(
                cloud_connector_id=connector_id
            )
        assert "not found" in str(excinfo.value)

    def test_create_cloud_connector_rejects_plain_external_id(self, kibana_client):
        """Test the server's semantic validation of cloud connector vars."""
        role_arn = f"arn:aws:iam::123456789012:role/{PREFIX}-{uuid.uuid4().hex[:8]}"
        with pytest.raises(BadRequestError) as excinfo:
            kibana_client.fleet_outputs.create_cloud_connector(
                name=role_arn,
                cloud_provider="aws",
                vars={
                    "role_arn": {"value": role_arn, "type": "text"},
                    "external_id": {
                        "value": {"id": uuid.uuid4().hex[:20], "isSecretRef": False},
                        "type": "password",
                    },
                },
            )
        assert "External ID secret reference is not valid" in str(excinfo.value)


class TestAsyncFleetOutputsLifecycle:
    """Async round-trip test for the Fleet outputs API."""

    @pytest.mark.asyncio
    async def test_async_output_crud(self, async_kibana_client, unique_name):
        """Test the full output lifecycle with the async client."""
        created = await async_kibana_client.fleet_outputs.create_output(
            name=unique_name,
            type="elasticsearch",
            hosts=["http://localhost:9200"],
        )
        output_id = created.body["item"]["id"]
        try:
            assert created.body["item"]["name"] == unique_name

            fetched = await async_kibana_client.fleet_outputs.get_output(
                output_id=output_id
            )
            assert fetched.body["item"]["id"] == output_id

            updated = await async_kibana_client.fleet_outputs.update_output(
                output_id=output_id, name=f"{unique_name}-renamed"
            )
            assert updated.body["item"]["name"] == f"{unique_name}-renamed"

            health = await async_kibana_client.fleet_outputs.get_output_health(
                output_id=output_id
            )
            assert health.body["state"] == "UNKNOWN"

            status = await (
                async_kibana_client.fleet_outputs.get_remote_synced_integrations_status()
            )
            assert "integrations" in status.body
        finally:
            try:
                await async_kibana_client.fleet_outputs.delete_output(
                    output_id=output_id
                )
            except NotFoundError:
                pass

        with pytest.raises(NotFoundError):
            await async_kibana_client.fleet_outputs.get_output(output_id=output_id)
