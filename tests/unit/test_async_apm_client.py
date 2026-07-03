"""Unit tests for AsyncApmClient."""

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client.apm import AsyncApmClient
from kibana.exceptions import (
    AuthorizationException,
    InvalidSpaceIdError,
    NotFoundError,
)

SOURCEMAP = {
    "version": 3,
    "file": "bundle.js",
    "sources": ["app.js"],
    "names": [],
    "mappings": "AAAA",
}


class TestAsyncApmClientInitialization:
    """Test AsyncApmClient initialization and wiring."""

    def test_apm_client_initialization(self, mock_async_transport):
        """Test that AsyncApmClient can be initialized with a parent client."""
        client = AsyncKibana(_transport=mock_async_transport)
        apm_client = AsyncApmClient(client)
        assert apm_client._client is client

    def test_apm_property_returns_apm_client(self, mock_async_transport):
        """Test that client.apm returns an AsyncApmClient instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.apm, AsyncApmClient)

    def test_apm_property_caching(self, mock_async_transport):
        """Test that the apm property returns the same instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert client.apm is client.apm


class TestAsyncApmAgentKeys:
    """Test AsyncApmClient.create_agent_key() method."""

    async def test_create_agent_key(self, mock_async_transport, mock_response):
        """Test agent key creation request encoding and response."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "agentKey": {
                    "id": "abc123",
                    "name": "my-key",
                    "api_key": "secret",
                    "encoded": "ZW5jb2RlZA==",
                }
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.apm.create_agent_key(
            name="my-key", privileges=["event:write", "config_agent:read"]
        )

        assert result.body["agentKey"]["name"] == "my-key"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/apm/agent_keys"
        assert call_kwargs["body"] == {
            "name": "my-key",
            "privileges": ["event:write", "config_agent:read"],
        }
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["accept"] == "application/json"

    async def test_create_agent_key_authorization_error(
        self, mock_async_transport, mock_response
    ):
        """Test that a 403 response raises AuthorizationException."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 403,
                "error": "Forbidden",
                "message": "Missing manage_own_api_key",
            },
            status=403,
        )

        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(AuthorizationException):
            await client.apm.create_agent_key(name="k", privileges=["event:write"])


class TestAsyncApmServerSchema:
    """Test AsyncApmClient.save_server_schema() method."""

    async def test_save_server_schema(self, mock_async_transport, mock_response):
        """Test schema save request encoding."""
        mock_async_transport.perform_request.return_value = mock_response(body={})

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.apm.save_server_schema(
            schema={"apm-server.host": "0.0.0.0:8200"}
        )

        assert result.body == {}

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/apm/fleet/apm_server_schema"
        assert call_kwargs["body"] == {"schema": {"apm-server.host": "0.0.0.0:8200"}}
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"


class TestAsyncApmAnnotations:
    """Test annotation create/search methods."""

    async def test_create_annotation_full_body(
        self, mock_async_transport, mock_response
    ):
        """Test annotation creation with all fields."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"_id": "an1", "_index": "observability-annotations"}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.apm.create_annotation(
            service_name="opbeans-java",
            timestamp="2026-07-03T00:00:00.000Z",
            service_version="1.2.3",
            service_environment="production",
            message="Deployed 1.2.3",
            tags=["kbnpy"],
        )

        assert result.body["_id"] == "an1"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/apm/services/opbeans-java/annotation"
        assert call_kwargs["body"] == {
            "@timestamp": "2026-07-03T00:00:00.000Z",
            "service": {"version": "1.2.3", "environment": "production"},
            "message": "Deployed 1.2.3",
            "tags": ["kbnpy"],
        }
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    async def test_create_annotation_minimal_body(
        self, mock_async_transport, mock_response
    ):
        """Optional fields must not be sent when omitted."""
        mock_async_transport.perform_request.return_value = mock_response(body={})

        client = AsyncKibana(_transport=mock_async_transport)
        await client.apm.create_annotation(
            service_name="svc",
            timestamp="2026-07-03T00:00:00.000Z",
            service_version="1.0.0",
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "@timestamp": "2026-07-03T00:00:00.000Z",
            "service": {"version": "1.0.0"},
        }

    async def test_create_annotation_url_encodes_service_name(
        self, mock_async_transport, mock_response
    ):
        """Service names are URL-encoded in the path."""
        mock_async_transport.perform_request.return_value = mock_response(body={})

        client = AsyncKibana(_transport=mock_async_transport)
        await client.apm.create_annotation(
            service_name="my svc/1",
            timestamp="2026-07-03T00:00:00.000Z",
            service_version="1.0.0",
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/apm/services/my%20svc%2F1/annotation"

    async def test_search_annotations_with_params(
        self, mock_async_transport, mock_response
    ):
        """Test annotation search query parameter encoding."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"annotations": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.apm.search_annotations(
            service_name="opbeans-java",
            environment="production",
            start="2026-07-01T00:00:00.000Z",
            end="2026-07-04T00:00:00.000Z",
        )

        assert result.body["annotations"] == []

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/apm/services/opbeans-java/annotation/search"
            "?environment=production"
            "&start=2026-07-01T00%3A00%3A00.000Z"
            "&end=2026-07-04T00%3A00%3A00.000Z"
        )
        assert call_kwargs["headers"] == {"accept": "application/json"}

    async def test_search_annotations_without_params(
        self, mock_async_transport, mock_response
    ):
        """No query string is sent when all optional params are omitted."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"annotations": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.apm.search_annotations(service_name="svc")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/apm/services/svc/annotation/search"


class TestAsyncApmAgentConfiguration:
    """Test agent configuration methods."""

    async def test_get_agent_configurations(self, mock_async_transport, mock_response):
        """Test listing all agent configurations."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"configurations": [{"service": {}, "settings": {}}]}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.apm.get_agent_configurations()

        assert len(result.body["configurations"]) == 1

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/apm/settings/agent-configuration"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    async def test_create_or_update_agent_configuration_full(
        self, mock_async_transport, mock_response
    ):
        """Test upsert with all fields and the overwrite query param."""
        mock_async_transport.perform_request.return_value = mock_response(body={})

        client = AsyncKibana(_transport=mock_async_transport)
        await client.apm.create_or_update_agent_configuration(
            service_name="opbeans-node",
            service_environment="production",
            settings={"transaction_sample_rate": "0.5"},
            agent_name="nodejs",
            overwrite=True,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == (
            "/api/apm/settings/agent-configuration?overwrite=true"
        )
        assert call_kwargs["body"] == {
            "service": {"name": "opbeans-node", "environment": "production"},
            "settings": {"transaction_sample_rate": "0.5"},
            "agent_name": "nodejs",
        }
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs["headers"]["content-type"] == "application/json"

    async def test_create_or_update_agent_configuration_all_services(
        self, mock_async_transport, mock_response
    ):
        """Omitting service name/environment targets all services."""
        mock_async_transport.perform_request.return_value = mock_response(body={})

        client = AsyncKibana(_transport=mock_async_transport)
        await client.apm.create_or_update_agent_configuration(
            settings={"transaction_sample_rate": "1"}
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/apm/settings/agent-configuration"
        assert call_kwargs["body"] == {
            "service": {},
            "settings": {"transaction_sample_rate": "1"},
        }

    async def test_delete_agent_configuration(
        self, mock_async_transport, mock_response
    ):
        """Test delete sends the service selector as the request body."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"result": "deleted"}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.apm.delete_agent_configuration(
            service_name="opbeans-node", service_environment="production"
        )

        assert result.body["result"] == "deleted"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/apm/settings/agent-configuration"
        assert call_kwargs["body"] == {
            "service": {"name": "opbeans-node", "environment": "production"}
        }
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    async def test_get_agent_configuration(self, mock_async_transport, mock_response):
        """Test single configuration lookup via the view endpoint."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "c1", "settings": {"transaction_sample_rate": "0.5"}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.apm.get_agent_configuration(
            name="opbeans-node", environment="production"
        )

        assert result.body["id"] == "c1"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/apm/settings/agent-configuration/view"
            "?name=opbeans-node&environment=production"
        )

    async def test_get_agent_configuration_not_found(
        self, mock_async_transport, mock_response
    ):
        """Test that a 404 response raises NotFoundError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Configuration not found",
            },
            status=404,
        )

        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(NotFoundError):
            await client.apm.get_agent_configuration(name="missing", environment="dev")

    async def test_search_agent_configurations(
        self, mock_async_transport, mock_response
    ):
        """Test the deprecated search endpoint body encoding."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"_id": "c1", "_source": {"settings": {}}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.apm.search_agent_configurations(
            service_name="opbeans-node",
            service_environment="production",
            etag="0bc3b5eb",
            mark_as_applied_by_agent=True,
            error="agent failed to apply",
        )

        assert result.body["_id"] == "c1"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/apm/settings/agent-configuration/search"
        assert call_kwargs["body"] == {
            "service": {"name": "opbeans-node", "environment": "production"},
            "etag": "0bc3b5eb",
            "mark_as_applied_by_agent": True,
            "error": "agent failed to apply",
        }

    async def test_get_environments(self, mock_async_transport, mock_response):
        """Test environments lookup with serviceName param."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"environments": [{"name": "production", "alreadyConfigured": True}]}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.apm.get_environments(service_name="opbeans-node")

        assert result.body["environments"][0]["name"] == "production"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/apm/settings/agent-configuration/environments"
            "?serviceName=opbeans-node"
        )

    async def test_get_environments_without_service(
        self, mock_async_transport, mock_response
    ):
        """serviceName is optional for the environments endpoint."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"environments": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.apm.get_environments()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/apm/settings/agent-configuration/environments"
        )

    async def test_get_agent_name(self, mock_async_transport, mock_response):
        """Test agent name lookup for a service."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"agentName": "nodejs"}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.apm.get_agent_name(service_name="opbeans-node")

        assert result.body["agentName"] == "nodejs"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/apm/settings/agent-configuration/agent_name"
            "?serviceName=opbeans-node"
        )


class TestAsyncApmSourcemaps:
    """Test source map methods."""

    async def test_get_sourcemaps_with_pagination(
        self, mock_async_transport, mock_response
    ):
        """Test source map listing with page/perPage params."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"artifacts": [], "total": 0}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.apm.get_sourcemaps(page=2, per_page=25)

        assert result.body["total"] == 0

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/apm/sourcemaps?page=2&perPage=25"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    async def test_get_sourcemaps_without_params(
        self, mock_async_transport, mock_response
    ):
        """No query string is sent when pagination params are omitted."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"artifacts": [], "total": 0}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.apm.get_sourcemaps()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/apm/sourcemaps"

    async def test_upload_sourcemap_multipart(
        self, mock_async_transport, mock_response
    ):
        """Test multipart body construction for source map upload."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "apm:svc-1.0.0-abc"}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.apm.upload_sourcemap(
            service_name="svc",
            service_version="1.0.0",
            bundle_filepath="http://localhost/bundle.js",
            sourcemap=SOURCEMAP,
        )

        assert result.body["id"] == "apm:svc-1.0.0-abc"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/apm/sourcemaps"

        content_type = call_kwargs["headers"]["content-type"]
        assert content_type.startswith("multipart/form-data; boundary=")
        boundary = content_type.split("boundary=", 1)[1]

        body = call_kwargs["body"]
        assert isinstance(body, bytes)
        assert body.startswith(f"--{boundary}\r\n".encode())
        assert body.endswith(f"--{boundary}--\r\n".encode())
        assert b'name="service_name"\r\n\r\nsvc\r\n' in body
        assert b'name="service_version"\r\n\r\n1.0.0\r\n' in body
        assert b'name="bundle_filepath"\r\n\r\nhttp://localhost/bundle.js\r\n' in body
        assert b'name="sourcemap"; filename="bundle.js.map"' in body
        # Kibana JSON-parses application/json parts; the file part must be
        # sent as application/octet-stream to arrive as a Buffer.
        assert b"Content-Type: application/octet-stream\r\n" in body
        assert b'"mappings": "AAAA"' in body
        # CSRF header still present for the POST
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    async def test_upload_sourcemap_accepts_string_content(
        self, mock_async_transport, mock_response
    ):
        """A pre-serialized source map string is passed through unchanged."""
        mock_async_transport.perform_request.return_value = mock_response(body={})

        client = AsyncKibana(_transport=mock_async_transport)
        await client.apm.upload_sourcemap(
            service_name="svc",
            service_version="1.0.0",
            bundle_filepath="http://localhost/bundle.js",
            sourcemap='{"version":3,"mappings":"AAAA"}',
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert b'{"version":3,"mappings":"AAAA"}' in call_kwargs["body"]

    async def test_delete_sourcemap_url_encodes_id(
        self, mock_async_transport, mock_response
    ):
        """Artifact IDs (which contain colons) are URL-encoded in the path."""
        mock_async_transport.perform_request.return_value = mock_response(body={})

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.apm.delete_sourcemap(id="apm:svc-1.0.0-abc")

        assert result.body == {}

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/apm/sourcemaps/apm%3Asvc-1.0.0-abc"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert "body" not in call_kwargs


class TestAsyncApmSpaceScoping:
    """Every async APM method must honor the /s/{space_id} route prefix."""

    SPACE_CALLS = [
        (
            "create_agent_key",
            {"name": "k", "privileges": ["event:write"]},
            "/s/marketing/api/apm/agent_keys",
        ),
        (
            "save_server_schema",
            {"schema": {"apm-server.host": "0.0.0.0:8200"}},
            "/s/marketing/api/apm/fleet/apm_server_schema",
        ),
        (
            "create_annotation",
            {
                "service_name": "svc",
                "timestamp": "2026-07-03T00:00:00.000Z",
                "service_version": "1.0.0",
            },
            "/s/marketing/api/apm/services/svc/annotation",
        ),
        (
            "search_annotations",
            {"service_name": "svc"},
            "/s/marketing/api/apm/services/svc/annotation/search",
        ),
        (
            "get_agent_configurations",
            {},
            "/s/marketing/api/apm/settings/agent-configuration",
        ),
        (
            "create_or_update_agent_configuration",
            {"settings": {"transaction_sample_rate": "1"}},
            "/s/marketing/api/apm/settings/agent-configuration",
        ),
        (
            "delete_agent_configuration",
            {"service_name": "svc"},
            "/s/marketing/api/apm/settings/agent-configuration",
        ),
        (
            "get_agent_configuration",
            {"name": "svc"},
            "/s/marketing/api/apm/settings/agent-configuration/view?name=svc",
        ),
        (
            "search_agent_configurations",
            {"service_name": "svc"},
            "/s/marketing/api/apm/settings/agent-configuration/search",
        ),
        (
            "get_environments",
            {},
            "/s/marketing/api/apm/settings/agent-configuration/environments",
        ),
        (
            "get_agent_name",
            {"service_name": "svc"},
            "/s/marketing/api/apm/settings/agent-configuration/agent_name"
            "?serviceName=svc",
        ),
        ("get_sourcemaps", {}, "/s/marketing/api/apm/sourcemaps"),
        (
            "upload_sourcemap",
            {
                "service_name": "svc",
                "service_version": "1.0.0",
                "bundle_filepath": "http://localhost/bundle.js",
                "sourcemap": SOURCEMAP,
            },
            "/s/marketing/api/apm/sourcemaps",
        ),
        (
            "delete_sourcemap",
            {"id": "apm:svc-1.0.0-abc"},
            "/s/marketing/api/apm/sourcemaps/apm%3Asvc-1.0.0-abc",
        ),
    ]

    @pytest.mark.parametrize("method,kwargs,expected_target", SPACE_CALLS)
    async def test_space_id_prefixes_path(
        self, mock_async_transport, mock_response, method, kwargs, expected_target
    ):
        """An explicit space_id routes the request through /s/{space_id}."""
        mock_async_transport.perform_request.return_value = mock_response(body={})

        client = AsyncKibana(_transport=mock_async_transport)
        await getattr(client.apm, method)(
            **kwargs, space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == expected_target

    async def test_space_scoped_client_inherits_default_space(
        self, mock_async_transport, mock_response
    ):
        """client.space(...).apm must inherit the space context."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"configurations": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        scoped = await client.space("marketing", validate=False)
        await scoped.apm.get_agent_configurations()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/s/marketing/api/apm/settings/agent-configuration"
        )

    async def test_explicit_space_id_overrides_default(
        self, mock_async_transport, mock_response
    ):
        """A per-call space_id wins over the client default space."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"configurations": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        apm_client = AsyncApmClient(
            client, default_space_id="sales", validate_spaces=False
        )
        await apm_client.get_agent_configurations(space_id="marketing")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/s/marketing/api/apm/settings/agent-configuration"
        )

    async def test_invalid_space_id_raises_before_request(self, mock_async_transport):
        """Malformed space IDs are rejected without hitting the server."""
        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(InvalidSpaceIdError):
            await client.apm.get_agent_configurations(
                space_id="Bad Space!", validate_spaces=False
            )
        mock_async_transport.perform_request.assert_not_called()
