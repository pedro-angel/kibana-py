"""Unit tests for AsyncFleetClient."""

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client.fleet import AsyncFleetClient
from kibana.exceptions import (
    AuthorizationException,
    BadRequestError,
    NotFoundError,
)


def _settings_body(**overrides):
    """Build a representative GET/PUT /api/fleet/settings response body."""
    item = {
        "id": "fleet-default-settings",
        "version": "WzUsMV0=",
        "prerelease_integrations_enabled": False,
        "use_space_awareness_migration_status": "success",
        "preconfigured_fields": [],
        "ilm_migration_status": {
            "logs": "success",
            "metrics": "success",
            "synthetics": "success",
        },
        "integration_knowledge_enabled": True,
    }
    item.update(overrides)
    return {"item": item}


def _space_settings_body(prefixes=None):
    """Build a representative /api/fleet/space_settings response body."""
    return {"item": {"allowed_namespace_prefixes": prefixes or []}}


class TestAsyncFleetClientInitialization:
    """Test AsyncFleetClient initialization."""

    @pytest.mark.asyncio
    async def test_fleet_client_initialization(self, mock_async_transport):
        """Test that AsyncFleetClient can be initialized with a parent client."""
        client = AsyncKibana(_transport=mock_async_transport)
        fleet_client = AsyncFleetClient(client)
        assert fleet_client._client is client

    @pytest.mark.asyncio
    async def test_fleet_property_returns_fleet_client(self, mock_async_transport):
        """Test that client.fleet returns an AsyncFleetClient instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.fleet, AsyncFleetClient)

    @pytest.mark.asyncio
    async def test_fleet_property_caching(self, mock_async_transport):
        """Test that the fleet property returns the same instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert client.fleet is client.fleet


class TestAsyncFleetClientSetup:
    """Test AsyncFleetClient.setup() method."""

    @pytest.mark.asyncio
    async def test_setup_success(self, mock_async_transport, mock_response):
        """Test initiating Fleet setup."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"isInitialized": True, "nonFatalErrors": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet.setup()

        assert result.body["isInitialized"] is True
        assert result.body["nonFatalErrors"] == []

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/setup"
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_setup_in_space(self, mock_async_transport, mock_response):
        """Test that setup builds a space-scoped path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"isInitialized": True, "nonFatalErrors": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet.setup(space_id="marketing", validate_spaces=False)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/fleet/setup"


class TestAsyncFleetClientGetSettings:
    """Test AsyncFleetClient.get_settings() method."""

    @pytest.mark.asyncio
    async def test_get_settings_success(self, mock_async_transport, mock_response):
        """Test getting the global Fleet settings."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_settings_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet.get_settings()

        assert result.body["item"]["id"] == "fleet-default-settings"
        assert result.body["item"]["prerelease_integrations_enabled"] is False

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/settings"
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_get_settings_in_space(self, mock_async_transport, mock_response):
        """Test that get_settings builds a space-scoped path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_settings_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet.get_settings(space_id="marketing", validate_spaces=False)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/fleet/settings"


class TestAsyncFleetClientUpdateSettings:
    """Test AsyncFleetClient.update_settings() method."""

    @pytest.mark.asyncio
    async def test_update_settings_single_field(
        self, mock_async_transport, mock_response
    ):
        """Test updating a single Fleet setting sends only that field."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_settings_body(prerelease_integrations_enabled=True)
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet.update_settings(
            prerelease_integrations_enabled=True
        )

        assert result.body["item"]["prerelease_integrations_enabled"] is True

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/fleet/settings"
        assert call_kwargs["body"] == {"prerelease_integrations_enabled": True}
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    @pytest.mark.asyncio
    async def test_update_settings_all_fields(
        self, mock_async_transport, mock_response
    ):
        """Test that every documented settings field is passed through."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_settings_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet.update_settings(
            additional_yaml_config="foo: bar",
            delete_unenrolled_agents={"enabled": True, "is_preconfigured": False},
            has_seen_add_data_notice=True,
            integration_knowledge_enabled=False,
            kibana_ca_sha256="abc123",
            kibana_urls=["https://kibana.example.com:5601"],
            prerelease_integrations_enabled=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "additional_yaml_config": "foo: bar",
            "delete_unenrolled_agents": {
                "enabled": True,
                "is_preconfigured": False,
            },
            "has_seen_add_data_notice": True,
            "integration_knowledge_enabled": False,
            "kibana_ca_sha256": "abc123",
            "kibana_urls": ["https://kibana.example.com:5601"],
            "prerelease_integrations_enabled": False,
        }

    @pytest.mark.asyncio
    async def test_update_settings_omits_unset_fields(
        self, mock_async_transport, mock_response
    ):
        """Test that None fields are not sent in the body."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_settings_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet.update_settings(integration_knowledge_enabled=True)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {"integration_knowledge_enabled": True}

    @pytest.mark.asyncio
    async def test_update_settings_in_space(self, mock_async_transport, mock_response):
        """Test that update_settings builds a space-scoped path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_settings_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet.update_settings(
            prerelease_integrations_enabled=True,
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/fleet/settings"


class TestAsyncFleetClientGetSpaceSettings:
    """Test AsyncFleetClient.get_space_settings() method."""

    @pytest.mark.asyncio
    async def test_get_space_settings_success(
        self, mock_async_transport, mock_response
    ):
        """Test getting the Fleet space settings."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_space_settings_body(["teama", "teamb"])
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet.get_space_settings()

        assert result.body["item"]["allowed_namespace_prefixes"] == [
            "teama",
            "teamb",
        ]

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/space_settings"
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_get_space_settings_in_space(
        self, mock_async_transport, mock_response
    ):
        """Test that get_space_settings builds a space-scoped path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_space_settings_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet.get_space_settings(
            space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/fleet/space_settings"


class TestAsyncFleetClientUpdateSpaceSettings:
    """Test AsyncFleetClient.update_space_settings() method."""

    @pytest.mark.asyncio
    async def test_update_space_settings_success(
        self, mock_async_transport, mock_response
    ):
        """Test updating the Fleet space settings."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_space_settings_body(["teama"])
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet.update_space_settings(
            allowed_namespace_prefixes=["teama"]
        )

        assert result.body["item"]["allowed_namespace_prefixes"] == ["teama"]

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/fleet/space_settings"
        assert call_kwargs["body"] == {"allowed_namespace_prefixes": ["teama"]}
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    @pytest.mark.asyncio
    async def test_update_space_settings_empty_list_is_sent(
        self, mock_async_transport, mock_response
    ):
        """Test that an explicit empty prefix list is sent (clears prefixes)."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_space_settings_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet.update_space_settings(allowed_namespace_prefixes=[])

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {"allowed_namespace_prefixes": []}

    @pytest.mark.asyncio
    async def test_update_space_settings_in_space(
        self, mock_async_transport, mock_response
    ):
        """Test that update_space_settings builds a space-scoped path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_space_settings_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet.update_space_settings(
            allowed_namespace_prefixes=["teama"],
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/fleet/space_settings"


class TestAsyncFleetClientHealthCheck:
    """Test AsyncFleetClient.health_check() method."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_async_transport, mock_response):
        """Test checking Fleet Server health by host ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"name": "fleet-server-1", "status": "ONLINE"}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet.health_check(id="fleet-server-host-id-1")

        assert result.body["status"] == "ONLINE"
        assert result.body["name"] == "fleet-server-1"

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/health_check"
        assert call_kwargs["body"] == {"id": "fleet-server-host-id-1"}
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    @pytest.mark.asyncio
    async def test_health_check_in_space(self, mock_async_transport, mock_response):
        """Test that health_check builds a space-scoped path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"host_id": "abc", "status": "OFFLINE"}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet.health_check(
            id="abc", space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/fleet/health_check"


class TestAsyncFleetClientCheckPermissions:
    """Test AsyncFleetClient.check_permissions() method."""

    @pytest.mark.asyncio
    async def test_check_permissions_success(self, mock_async_transport, mock_response):
        """Test checking Fleet permissions without options."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"success": True}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet.check_permissions()

        assert result.body["success"] is True

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/check-permissions"
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_check_permissions_fleet_server_setup_param(
        self, mock_async_transport, mock_response
    ):
        """Test that fleet_server_setup=True is encoded as a query param."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"success": True}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet.check_permissions(fleet_server_setup=True)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == "/api/fleet/check-permissions?fleetServerSetup=true"
        )

    @pytest.mark.asyncio
    async def test_check_permissions_missing_privileges(
        self, mock_async_transport, mock_response
    ):
        """Test the response body when the user is missing privileges."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"success": False, "error": "MISSING_PRIVILEGES"}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.fleet.check_permissions()

        assert result.body["success"] is False
        assert result.body["error"] == "MISSING_PRIVILEGES"

    @pytest.mark.asyncio
    async def test_check_permissions_in_space(
        self, mock_async_transport, mock_response
    ):
        """Test that check_permissions builds a space-scoped path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"success": True}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.fleet.check_permissions(
            space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/fleet/check-permissions"


class TestAsyncFleetClientErrorHandling:
    """Test AsyncFleetClient error handling."""

    @pytest.mark.asyncio
    async def test_health_check_not_found_error(
        self, mock_async_transport, mock_response
    ):
        """Test that a 404 response raises NotFoundError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "The requested host id nope does not exist.",
            },
            status=404,
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(NotFoundError):
            await client.fleet.health_check(id="nope")

    @pytest.mark.asyncio
    async def test_update_space_settings_bad_request_error(
        self, mock_async_transport, mock_response
    ):
        """Test that a 400 response raises BadRequestError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 400,
                "error": "Bad Request",
                "message": (
                    "[request body.allowed_namespace_prefixes.0]: " "Must not contain -"
                ),
            },
            status=400,
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(BadRequestError):
            await client.fleet.update_space_settings(
                allowed_namespace_prefixes=["kbnpy-fleet"]
            )

    @pytest.mark.asyncio
    async def test_update_settings_authorization_error(
        self, mock_async_transport, mock_response
    ):
        """Test that a 403 response raises AuthorizationException."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 403,
                "error": "Forbidden",
                "message": "Insufficient privileges",
            },
            status=403,
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(AuthorizationException):
            await client.fleet.update_settings(prerelease_integrations_enabled=True)
