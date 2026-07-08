"""Integration tests for ApmClient against a live Kibana instance."""

import base64
import json
import os
import urllib.request
import uuid

import pytest

from kibana.exceptions import NotFoundError

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    get_integration_test_config,
    is_kibana_available,
)

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)

RESOURCE_PREFIX = "kbnpy-apm"

SOURCEMAP = {
    "version": 3,
    "file": "bundle.js",
    "sources": ["app.js"],
    "names": [],
    "mappings": "AAAA",
}


def _es_request(method: str, path: str, body: dict | None = None) -> dict:
    """Perform a minimal Elasticsearch request for test cleanup."""
    es_url = os.getenv("ES_URL") or os.getenv("ES_LOCAL_URL", "http://localhost:9200")
    _, basic_auth, _ = get_integration_test_config()
    request = urllib.request.Request(
        f"{es_url}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    if basic_auth:
        token = base64.b64encode(f"{basic_auth[0]}:{basic_auth[1]}".encode()).decode()
        request.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or b"{}")


def _delete_annotations_for_service(service_name: str) -> None:
    """Delete annotation documents created for a test service."""
    try:
        _es_request(
            "POST",
            "/observability-annotations/_delete_by_query?refresh=true",
            {"query": {"term": {"service.name": service_name}}},
        )
    except Exception:
        pass  # Index may not exist if annotation creation failed


def _invalidate_api_key(key_id: str) -> None:
    """Invalidate an API key created by the agent keys test."""
    try:
        _es_request("DELETE", "/_security/api_key", {"ids": [key_id]})
    except Exception:
        pass


def _cleanup_agent_configuration(client, name: str, environment: str) -> None:
    """Delete an agent configuration, ignoring the case where it is gone."""
    try:
        client.apm.delete_agent_configuration(
            service_name=name, service_environment=environment
        )
    except NotFoundError:
        pass


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
def unique_suffix():
    """Generate a unique suffix for test resource names."""
    return uuid.uuid4().hex[:12]


class TestApmAgentConfiguration:
    """Live tests for the agent configuration lifecycle."""

    def test_agent_configuration_lifecycle(self, kibana_client, unique_suffix):
        """Create, list, view, search, update and delete a configuration."""
        service_name = f"{RESOURCE_PREFIX}-cfg-{unique_suffix}"
        environment = "testing"
        try:
            # Create
            created = kibana_client.apm.create_or_update_agent_configuration(
                service_name=service_name,
                service_environment=environment,
                settings={"transaction_sample_rate": "0.3"},
                agent_name="nodejs",
            )
            assert created.meta.status == 200

            # List: our configuration must be present
            listed = kibana_client.apm.get_agent_configurations()
            services = [c["service"].get("name") for c in listed.body["configurations"]]
            assert service_name in services

            # View the single configuration
            viewed = kibana_client.apm.get_agent_configuration(
                name=service_name, environment=environment
            )
            assert viewed.body["service"] == {
                "name": service_name,
                "environment": environment,
            }
            assert viewed.body["settings"] == {"transaction_sample_rate": "0.3"}
            assert viewed.body["applied_by_agent"] is False
            etag = viewed.body["etag"]

            # Search (deprecated agent poll endpoint) returns the ES hit
            searched = kibana_client.apm.search_agent_configurations(
                service_name=service_name,
                service_environment=environment,
                etag=etag,
            )
            assert searched.body["_source"]["service"]["name"] == service_name
            assert searched.body["_source"]["settings"] == {
                "transaction_sample_rate": "0.3"
            }

            # Update with overwrite
            kibana_client.apm.create_or_update_agent_configuration(
                service_name=service_name,
                service_environment=environment,
                settings={"transaction_sample_rate": "0.7"},
                overwrite=True,
            )
            updated = kibana_client.apm.get_agent_configuration(
                name=service_name, environment=environment
            )
            assert updated.body["settings"] == {"transaction_sample_rate": "0.7"}

            # Delete
            deleted = kibana_client.apm.delete_agent_configuration(
                service_name=service_name, service_environment=environment
            )
            assert deleted.body["result"] == "deleted"
        finally:
            _cleanup_agent_configuration(kibana_client, service_name, environment)

        # After deletion the view endpoint returns 404
        with pytest.raises(NotFoundError):
            kibana_client.apm.get_agent_configuration(
                name=service_name, environment=environment
            )

    def test_get_environments(self, kibana_client, unique_suffix):
        """Environments lookup returns the all-environments option."""
        service_name = f"{RESOURCE_PREFIX}-env-{unique_suffix}"
        response = kibana_client.apm.get_environments(service_name=service_name)
        names = [env["name"] for env in response.body["environments"]]
        # A service without APM data still reports the "all" option
        assert "ALL_OPTION_VALUE" in names

    def test_get_agent_name_without_apm_data(self, kibana_client, unique_suffix):
        """A service with no ingested APM data yields an empty body."""
        service_name = f"{RESOURCE_PREFIX}-name-{unique_suffix}"
        response = kibana_client.apm.get_agent_name(service_name=service_name)
        assert response.meta.status == 200
        assert response.body.get("agentName") is None

    def test_space_scoped_route_accepted_live(self, kibana_client):
        """The live server accepts the /s/{space_id} route prefix."""
        response = kibana_client.apm.get_agent_configurations(space_id="default")
        assert response.meta.status == 200
        assert "configurations" in response.body


class TestApmAnnotations:
    """Live tests for service annotations."""

    def test_create_and_search_annotation(self, kibana_client, unique_suffix):
        """Create a deployment annotation and find it via search."""
        service_name = f"{RESOURCE_PREFIX}-svc-{unique_suffix}"
        try:
            created = kibana_client.apm.create_annotation(
                service_name=service_name,
                timestamp="2026-07-03T12:00:00.000Z",
                service_version="1.2.3",
                service_environment="testing",
                message="kbnpy deployment marker",
                tags=["kbnpy-apm-test"],
            )
            assert created.body["_index"] == "observability-annotations"
            source = created.body["_source"]
            assert source["service"]["name"] == service_name
            assert source["service"]["version"] == "1.2.3"
            assert source["annotation"]["type"] == "deployment"
            # The apm tag is always kept alongside custom tags
            assert "apm" in source["tags"]
            assert "kbnpy-apm-test" in source["tags"]

            found = kibana_client.apm.search_annotations(
                service_name=service_name,
                environment="testing",
                start="2026-07-01T00:00:00.000Z",
                end="2026-07-05T00:00:00.000Z",
            )
            annotations = found.body["annotations"]
            assert len(annotations) == 1
            assert annotations[0]["id"] == created.body["_id"]
            assert annotations[0]["text"] == "kbnpy deployment marker"
        finally:
            _delete_annotations_for_service(service_name)

    def test_search_annotations_empty_window(self, kibana_client, unique_suffix):
        """Searching a service with no annotations returns an empty list."""
        service_name = f"{RESOURCE_PREFIX}-none-{unique_suffix}"
        # Live 9.4.3 requires environment/start/end (spec marks them optional)
        found = kibana_client.apm.search_annotations(
            service_name=service_name,
            environment="ENVIRONMENT_ALL",
            start="2026-07-01T00:00:00.000Z",
            end="2026-07-02T00:00:00.000Z",
        )
        assert found.body["annotations"] == []


class TestApmSourcemaps:
    """Live tests for RUM source map upload, listing and deletion."""

    def test_sourcemap_upload_list_delete(self, kibana_client, unique_suffix):
        """Upload a tiny source map, find it in the list, then delete it."""
        service_name = f"{RESOURCE_PREFIX}-rum-{unique_suffix}"
        artifact_id = None
        try:
            uploaded = kibana_client.apm.upload_sourcemap(
                service_name=service_name,
                service_version="1.0.0",
                bundle_filepath="http://localhost/static/js/bundle.js",
                sourcemap=SOURCEMAP,
            )
            artifact_id = uploaded.body["id"]
            assert uploaded.body["type"] == "sourcemap"
            assert uploaded.body["identifier"] == f"{service_name}-1.0.0"
            assert artifact_id.startswith(f"apm:{service_name}-1.0.0-")

            # The uploaded artifact appears in the paginated list
            listed = kibana_client.apm.get_sourcemaps(page=1, per_page=100)
            ids = [artifact["id"] for artifact in listed.body["artifacts"]]
            assert artifact_id in ids

            deleted = kibana_client.apm.delete_sourcemap(id=artifact_id)
            assert deleted.meta.status == 200
            artifact_id = None

            # And it is gone afterwards
            listed = kibana_client.apm.get_sourcemaps(page=1, per_page=100)
            ids = [artifact["id"] for artifact in listed.body["artifacts"]]
            assert f"apm:{service_name}-1.0.0" not in [i.rsplit("-", 1)[0] for i in ids]
        finally:
            if artifact_id is not None:
                kibana_client.apm.delete_sourcemap(id=artifact_id)


class TestApmAgentKeys:
    """Live tests for APM agent key creation."""

    def test_create_agent_key(self, unique_suffix):
        """Create an agent key and receive its credentials once.

        Uses basic auth explicitly: Elasticsearch rejects creating (derived)
        API keys when the caller itself is authenticated with an API key,
        and the shared test config may provide one.
        """
        key_name = f"{RESOURCE_PREFIX}-key-{unique_suffix}"
        key_id = None
        basic_client = create_test_kibana_client(auth_method="basic")
        try:
            response = basic_client.apm.create_agent_key(
                name=key_name,
                privileges=["event:write", "config_agent:read"],
            )
            agent_key = response.body["agentKey"]
            key_id = agent_key["id"]
            assert agent_key["name"] == key_name
            assert agent_key["api_key"]
            # encoded is base64(id:api_key), usable as an Authorization header
            decoded = base64.b64decode(agent_key["encoded"]).decode()
            assert decoded == f"{key_id}:{agent_key['api_key']}"
        finally:
            basic_client.close()
            if key_id is not None:
                _invalidate_api_key(key_id)


class TestApmServerSchema:
    """Live tests for the deprecated APM Server schema endpoint."""

    def test_save_server_schema(self, kibana_client):
        """Save an APM Server schema and clean up the saved object."""
        try:
            response = kibana_client.apm.save_server_schema(
                schema={"apm-server.host": "0.0.0.0:8200"}
            )
            assert response.meta.status == 200
            assert response.body == {}
        finally:
            # The endpoint stores a single global apm-server-schema saved
            # object; remove it to leave the shared stack unchanged.
            try:
                kibana_client.saved_objects.delete(
                    type="apm-server-schema", id="apm-server-schema"
                )
            except NotFoundError:
                pass


class TestAsyncApmIntegration:
    """Async round-trip tests against the live stack."""

    async def test_async_agent_configuration_round_trip(
        self, async_kibana_client, unique_suffix
    ):
        """Create, view and delete an agent configuration asynchronously."""
        service_name = f"{RESOURCE_PREFIX}-async-{unique_suffix}"
        environment = "testing"
        try:
            created = (
                await async_kibana_client.apm.create_or_update_agent_configuration(
                    service_name=service_name,
                    service_environment=environment,
                    settings={"transaction_sample_rate": "0.1"},
                )
            )
            assert created.meta.status == 200

            viewed = await async_kibana_client.apm.get_agent_configuration(
                name=service_name, environment=environment
            )
            assert viewed.body["settings"] == {"transaction_sample_rate": "0.1"}

            environments = await async_kibana_client.apm.get_environments(
                service_name=service_name
            )
            assert (
                any(
                    env["alreadyConfigured"]
                    for env in environments.body["environments"]
                    if env["name"] == "testing"
                )
                or environments.body["environments"]
            )
        finally:
            try:
                await async_kibana_client.apm.delete_agent_configuration(
                    service_name=service_name, service_environment=environment
                )
            except NotFoundError:
                pass

    async def test_async_search_annotations(self, async_kibana_client, unique_suffix):
        """Annotation search works through the async client."""
        service_name = f"{RESOURCE_PREFIX}-anone-{unique_suffix}"
        # Live 9.4.3 requires environment/start/end (spec marks them optional)
        found = await async_kibana_client.apm.search_annotations(
            service_name=service_name,
            environment="ENVIRONMENT_ALL",
            start="2026-07-01T00:00:00.000Z",
            end="2026-07-02T00:00:00.000Z",
        )
        assert found.body["annotations"] == []
