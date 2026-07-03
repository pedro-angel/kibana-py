"""Integration tests for ConnectorsClient against a live Kibana stack.

Covers the full connector lifecycle with ``.server-log`` and ``.index``
connectors (including ``_execute``), the connector-types listing with
``feature_id`` filtering, the 9.4.0 OAuth callback endpoints, space-scoped
paths, and the deprecated ``client.actions`` alias.

Every resource created here is prefixed with ``kbnpy-connectors-`` and cleaned
up afterwards.
"""

import base64
import os
import urllib.error
import urllib.request
import uuid

import pytest
from elastic_transport import TextApiResponse

from kibana.exceptions import BadRequestError, NotFoundError

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    get_integration_test_config,
    is_kibana_available,
    safe_delete_connector,
)

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)

PREFIX = "kbnpy-connectors-"


def _delete_es_index(index: str) -> None:
    """Best-effort deletion of a throwaway Elasticsearch index."""
    es_url = os.getenv("ES_LOCAL_URL", "http://localhost:9200").rstrip("/")
    username = os.getenv("KIBANA_USERNAME", "elastic")
    password = os.getenv("ES_LOCAL_PASSWORD") or os.getenv("KIBANA_PASSWORD") or ""
    request = urllib.request.Request(f"{es_url}/{index}", method="DELETE")
    if password:
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        request.add_header("Authorization", f"Basic {token}")
    try:
        urllib.request.urlopen(request, timeout=10).close()
    except urllib.error.URLError, OSError:
        pass  # index may not exist; cleanup is best-effort


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
def created_connectors():
    """Track connectors created during tests for automatic cleanup."""
    connector_ids: list[str] = []
    yield connector_ids

    if connector_ids:
        client = create_test_kibana_client()
        try:
            for connector_id in connector_ids:
                try:
                    safe_delete_connector(client, connector_id)
                except Exception as e:  # pragma: no cover - cleanup best effort
                    print(f"Warning: failed to clean up connector {connector_id}: {e}")
        finally:
            client.close()


@pytest.fixture
def unique_name():
    """Generate a unique, namespaced connector name."""
    return f"{PREFIX}{uuid.uuid4().hex[:8]}"


class TestConnectorsClientConnectivity:
    """Basic connectivity, listing, and connector-type tests."""

    def test_connectors_client_exists(self, kibana_client):
        """Test that ConnectorsClient is accessible via the main client."""
        from kibana._sync.client.connectors import ConnectorsClient

        assert isinstance(kibana_client.connectors, ConnectorsClient)

    def test_list_connector_types(self, kibana_client):
        """Test listing available connector types and their structure."""
        response = kibana_client.connectors.list_types()

        assert response.meta.status == 200
        assert isinstance(response.body, list)
        assert len(response.body) > 0

        connector_type_ids = [ct["id"] for ct in response.body]
        assert ".server-log" in connector_type_ids
        assert ".index" in connector_type_ids

        server_log = next(ct for ct in response.body if ct["id"] == ".server-log")
        assert "name" in server_log
        assert isinstance(server_log["enabled"], bool)
        assert isinstance(server_log["enabled_in_config"], bool)
        assert "supported_feature_ids" in server_log

    def test_list_connector_types_with_feature_id(self, kibana_client):
        """Test the feature_id filter returns a strict subset supporting it."""
        all_types = kibana_client.connectors.list_types()
        alerting_types = kibana_client.connectors.list_types(feature_id="alerting")

        assert alerting_types.meta.status == 200
        all_ids = {ct["id"] for ct in all_types.body}
        alerting_ids = {ct["id"] for ct in alerting_types.body}
        assert alerting_ids <= all_ids
        assert 0 < len(alerting_ids) < len(all_ids)
        for connector_type in alerting_types.body:
            assert "alerting" in connector_type["supported_feature_ids"]

    def test_get_all_connectors(self, kibana_client):
        """Test getting all connectors returns a list."""
        response = kibana_client.connectors.get_all()

        assert response.meta.status == 200
        assert isinstance(response.body, list)


class TestConnectorsClientServerLogLifecycle:
    """Full lifecycle tests with a .server-log connector."""

    def test_create_without_config(
        self, kibana_client, created_connectors, unique_name
    ):
        """Test creating a .server-log connector without passing config."""
        response = kibana_client.connectors.create(
            name=unique_name, connector_type_id=".server-log"
        )
        connector = response.body
        created_connectors.append(connector["id"])

        assert connector["name"] == unique_name
        assert connector["connector_type_id"] == ".server-log"
        assert connector["config"] == {}
        assert "secrets" not in connector

    def test_full_lifecycle(self, kibana_client, unique_name):
        """Test create -> get -> get_all -> update -> execute -> delete."""
        # 1. Create
        created = kibana_client.connectors.create(
            name=unique_name, connector_type_id=".server-log"
        ).body
        connector_id = created["id"]

        try:
            # 2. Get
            fetched = kibana_client.connectors.get(id=connector_id).body
            assert fetched["id"] == connector_id
            assert fetched["name"] == unique_name

            # 3. Get all contains it
            all_connectors = kibana_client.connectors.get_all().body
            assert any(c["id"] == connector_id for c in all_connectors)

            # 4. Update (full-replace PUT; name is mandatory)
            new_name = f"{unique_name}-updated"
            updated = kibana_client.connectors.update(
                id=connector_id, name=new_name
            ).body
            assert updated["name"] == new_name

            # 5. Execute
            result = kibana_client.connectors.execute(
                id=connector_id,
                params={"message": f"{PREFIX}integration log", "level": "info"},
            ).body
            assert result["status"] == "ok"
            assert result["connector_id"] == connector_id
        finally:
            # 6. Delete
            response = kibana_client.connectors.delete(id=connector_id)
            assert response.meta.status in (200, 204)

        # 7. Verify deletion
        with pytest.raises(NotFoundError):
            kibana_client.connectors.get(id=connector_id)

    def test_create_with_caller_specified_id(self, kibana_client, created_connectors):
        """Test POST /api/actions/connector/{id} with a fixed connector ID."""
        connector_id = f"{PREFIX}{uuid.uuid4().hex[:12]}"  # <= 36 chars

        response = kibana_client.connectors.create(
            id=connector_id,
            name=f"{connector_id}-name",
            connector_type_id=".server-log",
        )
        created_connectors.append(connector_id)

        assert response.body["id"] == connector_id

        fetched = kibana_client.connectors.get(id=connector_id).body
        assert fetched["id"] == connector_id


class TestConnectorsClientIndexLifecycle:
    """Full lifecycle tests with an .index connector (backed by a tiny ES index)."""

    def test_index_connector_lifecycle(self, kibana_client, created_connectors):
        """Test create/execute/update semantics of an .index connector."""
        suffix = uuid.uuid4().hex[:8]
        index_name = f"{PREFIX}idx-{suffix}"
        connector_name = f"{PREFIX}index-{suffix}"

        try:
            # Create with required config
            created = kibana_client.connectors.create(
                name=connector_name,
                connector_type_id=".index",
                config={"index": index_name, "refresh": True},
            ).body
            connector_id = created["id"]
            created_connectors.append(connector_id)
            assert created["config"]["index"] == index_name

            # Execute writes a document
            result = kibana_client.connectors.execute(
                id=connector_id,
                params={"documents": [{"message": "kbnpy connectors test"}]},
            ).body
            assert result["status"] == "ok"

            # update() without config is a full replacement -> the required
            # 'index' config field is reset to {} and Kibana rejects it.
            with pytest.raises(BadRequestError):
                kibana_client.connectors.update(
                    id=connector_id, name=f"{connector_name}-renamed"
                )

            # update() with the full config succeeds
            updated = kibana_client.connectors.update(
                id=connector_id,
                name=f"{connector_name}-renamed",
                config={"index": index_name, "refresh": False},
            ).body
            assert updated["name"] == f"{connector_name}-renamed"
            assert updated["config"]["refresh"] is False
        finally:
            _delete_es_index(index_name)


class TestConnectorsClientSpaceScoped:
    """Space-scoped path tests (using the always-present default space)."""

    def test_get_all_in_default_space(self, kibana_client):
        """Test that /s/default/... paths work for connectors."""
        response = kibana_client.connectors.get_all(space_id="default")

        assert response.meta.status == 200
        assert isinstance(response.body, list)

    def test_crud_in_default_space(
        self, kibana_client, created_connectors, unique_name
    ):
        """Test connector create/get in an explicit space scope."""
        created = kibana_client.connectors.create(
            name=unique_name,
            connector_type_id=".server-log",
            space_id="default",
        ).body
        created_connectors.append(created["id"])

        fetched = kibana_client.connectors.get(
            id=created["id"], space_id="default"
        ).body
        assert fetched["name"] == unique_name

        # The default space is the same as the unscoped path
        unscoped = kibana_client.connectors.get(id=created["id"]).body
        assert unscoped["id"] == fetched["id"]

    def test_list_types_in_default_space(self, kibana_client):
        """Test that connector types can be listed in a space scope."""
        response = kibana_client.connectors.list_types(
            space_id="default", feature_id="alerting"
        )

        assert response.meta.status == 200
        assert len(response.body) > 0


class TestConnectorsClientOAuth:
    """Tests for the 9.4.0 OAuth callback endpoints."""

    def test_oauth_callback_returns_completion_page(self, kibana_client):
        """Test that the OAuth callback returns the HTML completion page."""
        response = kibana_client.connectors.oauth_callback()

        assert response.meta.status == 200
        assert isinstance(response, TextApiResponse)
        assert "html" in response.body.lower()

    def test_oauth_callback_with_provider_error(self, kibana_client):
        """Test the OAuth callback with provider error query parameters."""
        response = kibana_client.connectors.oauth_callback(
            error="access_denied",
            error_description="kbnpy integration test",
            state="kbnpy-connectors-state",
        )

        assert response.meta.status == 200

    def test_get_oauth_callback_script(self, kibana_client):
        """Test that the OAuth callback script endpoint returns JavaScript."""
        response = kibana_client.connectors.get_oauth_callback_script()

        assert response.meta.status == 200
        assert isinstance(response, TextApiResponse)
        assert "oauth_flow_completed" in response.body


class TestConnectorsClientErrorHandling:
    """Error handling against the live server."""

    def test_get_nonexistent_connector(self, kibana_client):
        """Test that getting a non-existent connector raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.connectors.get(id=f"{PREFIX}nonexistent")

        assert exc_info.value.status_code == 404

    def test_update_nonexistent_connector(self, kibana_client):
        """Test that updating a non-existent connector raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.connectors.update(
                id=f"{PREFIX}nonexistent", name="Updated Name"
            )

    def test_delete_nonexistent_connector(self, kibana_client):
        """Test that deleting a non-existent connector raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.connectors.delete(id=f"{PREFIX}nonexistent")

    def test_execute_nonexistent_connector(self, kibana_client):
        """Test that executing a non-existent connector raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.connectors.execute(
                id=f"{PREFIX}nonexistent", params={"message": "test"}
            )

    def test_create_connector_with_invalid_type(self, kibana_client, unique_name):
        """Test that an invalid connector type raises BadRequestError."""
        with pytest.raises(BadRequestError) as exc_info:
            kibana_client.connectors.create(
                name=unique_name, connector_type_id=".kbnpy-nonexistent-type"
            )

        assert exc_info.value.status_code == 400

    def test_create_connector_with_invalid_config(self, kibana_client, unique_name):
        """Test that a missing required config field raises BadRequestError."""
        with pytest.raises(BadRequestError) as exc_info:
            kibana_client.connectors.create(
                name=unique_name,
                connector_type_id=".index",
                config={},  # missing required 'index' field
            )

        assert exc_info.value.status_code == 400


class TestConnectorsClientWithOptions:
    """Tests for ConnectorsClient with per-request client options."""

    def test_connectors_with_custom_timeout(self, kibana_client):
        """Test that ConnectorsClient works with custom timeout options."""
        client_with_timeout = kibana_client.options(request_timeout=60.0)
        response = client_with_timeout.connectors.list_types()
        assert response.meta.status == 200

    def test_connectors_with_custom_headers(self, kibana_client):
        """Test that ConnectorsClient works with custom headers."""
        client_with_headers = kibana_client.options(
            headers={"X-Kbnpy-Connectors": "test-value"}
        )
        response = client_with_headers.connectors.list_types()
        assert response.meta.status == 200

    def test_connectors_with_api_key_auth(self, kibana_client):
        """Test that ConnectorsClient works when switching to API key auth."""
        _, _, api_key = get_integration_test_config()
        if not api_key:
            pytest.skip("API key not available for authentication switching test")

        client_with_api_key = kibana_client.options(api_key=api_key)
        response = client_with_api_key.connectors.list_types()
        assert response.meta.status == 200


class TestActionsAliasLive:
    """Live tests for the deprecated client.actions alias."""

    def test_actions_is_connectors_subclass_instance(self, kibana_client):
        """Test the alias class relationship on a real client."""
        from kibana._sync.client.actions import ActionsClient
        from kibana._sync.client.connectors import ConnectorsClient

        assert issubclass(ActionsClient, ConnectorsClient)
        assert isinstance(kibana_client.actions, ConnectorsClient)

    def test_actions_alias_round_trip(
        self, kibana_client, created_connectors, unique_name
    ):
        """Test that client.actions still performs a full round trip."""
        types = kibana_client.actions.list_types()
        assert types.meta.status == 200

        created = kibana_client.actions.create(
            name=unique_name, connector_type_id=".server-log"
        ).body
        created_connectors.append(created["id"])

        fetched = kibana_client.actions.get(id=created["id"]).body
        assert fetched["name"] == unique_name


class TestAsyncConnectorsIntegration:
    """Async round-trip tests against the live stack."""

    async def test_async_full_lifecycle(self):
        """Test async create -> get -> update -> execute -> delete."""
        client = create_test_async_kibana_client(auth_method="auto")
        name = f"{PREFIX}async-{uuid.uuid4().hex[:8]}"
        connector_id = None
        try:
            created = (
                await client.connectors.create(
                    name=name, connector_type_id=".server-log"
                )
            ).body
            connector_id = created["id"]
            assert created["name"] == name

            fetched = (await client.connectors.get(id=connector_id)).body
            assert fetched["id"] == connector_id

            updated = (
                await client.connectors.update(id=connector_id, name=f"{name}-upd")
            ).body
            assert updated["name"] == f"{name}-upd"

            result = (
                await client.connectors.execute(
                    id=connector_id,
                    params={"message": f"{PREFIX}async log", "level": "info"},
                )
            ).body
            assert result["status"] == "ok"
        finally:
            if connector_id is not None:
                try:
                    await client.connectors.delete(id=connector_id)
                except NotFoundError:
                    pass
            await client.close()

    async def test_async_list_types_and_oauth_script(self):
        """Test async list_types with feature filter and the OAuth script."""
        client = create_test_async_kibana_client(auth_method="auto")
        try:
            types = await client.connectors.list_types(feature_id="alerting")
            assert types.meta.status == 200
            assert len(types.body) > 0

            script = await client.connectors.get_oauth_callback_script()
            assert script.meta.status == 200
            assert isinstance(script, TextApiResponse)
            assert "oauth_flow_completed" in script.body

            callback = await client.connectors.oauth_callback(
                error="access_denied", error_description="kbnpy async test"
            )
            assert callback.meta.status == 200

            # Deprecated async alias still works
            alias_types = await client.actions.list_types()
            assert alias_types.meta.status == 200
        finally:
            await client.close()
