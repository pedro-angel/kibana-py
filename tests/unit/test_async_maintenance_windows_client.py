"""Unit tests for AsyncMaintenanceWindowsClient."""

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client.maintenance_windows import AsyncMaintenanceWindowsClient
from kibana.exceptions import AuthorizationException, NotFoundError

MW_ID = "d0b13fd9-25a8-4f1c-9c33-a44b18d24ce2"

SCHEDULE = {
    "custom": {
        "start": "2030-01-01T00:00:00.000Z",
        "duration": "2h",
        "timezone": "UTC",
        "recurring": {"every": "1w", "onWeekDay": ["MO"]},
    }
}

SCOPE = {"alerting": {"query": {"kql": 'tags: "maintenance"'}}}


def _maintenance_window_body(**overrides):
    """Build a representative maintenance window response body."""
    body = {
        "id": MW_ID,
        "title": "kbnpy-mw-example",
        "enabled": True,
        "schedule": SCHEDULE,
        "scope": SCOPE,
        "created_by": "elastic",
        "updated_by": "elastic",
        "created_at": "2026-07-03T18:49:55.595Z",
        "updated_at": "2026-07-03T18:49:55.595Z",
        "status": "upcoming",
    }
    body.update(overrides)
    return body


class TestAsyncMaintenanceWindowsClientInitialization:
    """Test AsyncMaintenanceWindowsClient initialization."""

    @pytest.mark.asyncio
    async def test_maintenance_windows_client_initialization(
        self, mock_async_transport
    ):
        """Test that AsyncMaintenanceWindowsClient can be initialized with a parent client."""
        client = AsyncKibana(_transport=mock_async_transport)
        maintenance_windows_client = AsyncMaintenanceWindowsClient(client)
        assert maintenance_windows_client._client is client

    @pytest.mark.asyncio
    async def test_maintenance_windows_property_returns_client(
        self, mock_async_transport
    ):
        """Test that client.maintenance_windows returns an AsyncMaintenanceWindowsClient."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.maintenance_windows, AsyncMaintenanceWindowsClient)

    @pytest.mark.asyncio
    async def test_maintenance_windows_property_caching(self, mock_async_transport):
        """Test that the maintenance_windows property returns the same instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert client.maintenance_windows is client.maintenance_windows


class TestAsyncMaintenanceWindowsClientCreate:
    """Test AsyncMaintenanceWindowsClient.create() method."""

    @pytest.mark.asyncio
    async def test_create_minimal(self, mock_async_transport, mock_response):
        """Test creating a maintenance window with only the required parameters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_maintenance_window_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.maintenance_windows.create(
            title="kbnpy-mw-example",
            schedule=SCHEDULE,
        )

        assert result.body["id"] == MW_ID
        assert result.body["status"] == "upcoming"

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/maintenance_window"
        assert call_kwargs["body"] == {
            "title": "kbnpy-mw-example",
            "schedule": SCHEDULE,
        }
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    @pytest.mark.asyncio
    async def test_create_with_all_parameters(
        self, mock_async_transport, mock_response
    ):
        """Test creating a maintenance window with enabled flag and scope."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_maintenance_window_body(enabled=False, status="disabled")
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.maintenance_windows.create(
            title="kbnpy-mw-example",
            schedule=SCHEDULE,
            enabled=False,
            scope=SCOPE,
        )

        assert result.body["enabled"] is False

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "title": "kbnpy-mw-example",
            "schedule": SCHEDULE,
            "enabled": False,
            "scope": SCOPE,
        }

    @pytest.mark.asyncio
    async def test_create_in_space(self, mock_async_transport, mock_response):
        """Test creating a maintenance window in a specific space."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_maintenance_window_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.maintenance_windows.create(
            title="kbnpy-mw-example",
            schedule=SCHEDULE,
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/maintenance_window"


class TestAsyncMaintenanceWindowsClientGet:
    """Test AsyncMaintenanceWindowsClient.get() method."""

    @pytest.mark.asyncio
    async def test_get_success(self, mock_async_transport, mock_response):
        """Test getting a maintenance window by ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_maintenance_window_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.maintenance_windows.get(id=MW_ID)

        assert result.body["title"] == "kbnpy-mw-example"

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == f"/api/maintenance_window/{MW_ID}"
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_get_url_encodes_id(self, mock_async_transport, mock_response):
        """Test that the maintenance window ID is URL-encoded in the path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_maintenance_window_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.maintenance_windows.get(id="id with/special")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/maintenance_window/id%20with%2Fspecial"

    @pytest.mark.asyncio
    async def test_get_in_space(self, mock_async_transport, mock_response):
        """Test getting a maintenance window from a specific space."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_maintenance_window_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.maintenance_windows.get(
            id="abc123", space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/maintenance_window/abc123"


class TestAsyncMaintenanceWindowsClientFind:
    """Test AsyncMaintenanceWindowsClient.find() method."""

    @pytest.mark.asyncio
    async def test_find_without_filters(self, mock_async_transport, mock_response):
        """Test searching maintenance windows without any filters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "page": 1,
                "per_page": 10,
                "total": 1,
                "maintenanceWindows": [_maintenance_window_body()],
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.maintenance_windows.find()

        assert result.body["total"] == 1
        assert result.body["maintenanceWindows"][0]["id"] == MW_ID

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/maintenance_window/_find"
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_find_with_all_filters(self, mock_async_transport, mock_response):
        """Test that all find filters are encoded as query parameters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "page": 2,
                "per_page": 5,
                "total": 0,
                "maintenanceWindows": [],
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.maintenance_windows.find(
            title="kbnpy-mw-example",
            created_by="elastic",
            status=["running", "upcoming"],
            page=2,
            per_page=5,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/maintenance_window/_find"
            "?title=kbnpy-mw-example&created_by=elastic"
            "&status=running&status=upcoming&page=2&per_page=5"
        )

    @pytest.mark.asyncio
    async def test_find_with_single_status_string(
        self, mock_async_transport, mock_response
    ):
        """Test that a single status string is passed as one query parameter."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "page": 1,
                "per_page": 10,
                "total": 0,
                "maintenanceWindows": [],
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.maintenance_windows.find(status="archived")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/maintenance_window/_find?status=archived"

    @pytest.mark.asyncio
    async def test_find_in_space(self, mock_async_transport, mock_response):
        """Test searching maintenance windows in a specific space."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "page": 1,
                "per_page": 10,
                "total": 0,
                "maintenanceWindows": [],
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.maintenance_windows.find(
            space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/maintenance_window/_find"


class TestAsyncMaintenanceWindowsClientUpdate:
    """Test AsyncMaintenanceWindowsClient.update() method."""

    @pytest.mark.asyncio
    async def test_update_partial(self, mock_async_transport, mock_response):
        """Test that only the provided fields are sent in the PATCH body."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_maintenance_window_body(enabled=False, status="disabled")
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.maintenance_windows.update(id=MW_ID, enabled=False)

        assert result.body["status"] == "disabled"

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["target"] == f"/api/maintenance_window/{MW_ID}"
        assert call_kwargs["body"] == {"enabled": False}
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    @pytest.mark.asyncio
    async def test_update_all_fields(self, mock_async_transport, mock_response):
        """Test updating every updatable field of a maintenance window."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_maintenance_window_body(title="kbnpy-mw-renamed")
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.maintenance_windows.update(
            id=MW_ID,
            title="kbnpy-mw-renamed",
            enabled=True,
            schedule=SCHEDULE,
            scope=SCOPE,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "title": "kbnpy-mw-renamed",
            "enabled": True,
            "schedule": SCHEDULE,
            "scope": SCOPE,
        }

    @pytest.mark.asyncio
    async def test_update_url_encodes_id(self, mock_async_transport, mock_response):
        """Test that the maintenance window ID is URL-encoded in the path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_maintenance_window_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.maintenance_windows.update(id="id with/special", title="x")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/maintenance_window/id%20with%2Fspecial"

    @pytest.mark.asyncio
    async def test_update_in_space(self, mock_async_transport, mock_response):
        """Test updating a maintenance window in a specific space."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_maintenance_window_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.maintenance_windows.update(
            id="abc123",
            title="kbnpy-mw-renamed",
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/maintenance_window/abc123"


class TestAsyncMaintenanceWindowsClientDelete:
    """Test AsyncMaintenanceWindowsClient.delete() method."""

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_async_transport, mock_response):
        """Test deleting a maintenance window by ID."""
        # Live Kibana 9.4.3 returns an empty body with HTTP 204
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=204
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.maintenance_windows.delete(id=MW_ID)

        assert not result.body

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == f"/api/maintenance_window/{MW_ID}"
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_delete_in_space(self, mock_async_transport, mock_response):
        """Test deleting a maintenance window from a specific space."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=204
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.maintenance_windows.delete(
            id="abc123", space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/maintenance_window/abc123"


class TestAsyncMaintenanceWindowsClientArchive:
    """Test AsyncMaintenanceWindowsClient.archive() and unarchive() methods."""

    @pytest.mark.asyncio
    async def test_archive_success(self, mock_async_transport, mock_response):
        """Test archiving a maintenance window."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_maintenance_window_body(status="archived")
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.maintenance_windows.archive(id=MW_ID)

        assert result.body["status"] == "archived"

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == f"/api/maintenance_window/{MW_ID}/_archive"
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_archive_in_space(self, mock_async_transport, mock_response):
        """Test archiving a maintenance window in a specific space."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_maintenance_window_body(status="archived")
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.maintenance_windows.archive(
            id="abc123", space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == "/s/marketing/api/maintenance_window/abc123/_archive"
        )

    @pytest.mark.asyncio
    async def test_unarchive_success(self, mock_async_transport, mock_response):
        """Test unarchiving a maintenance window."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_maintenance_window_body(status="upcoming")
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.maintenance_windows.unarchive(id=MW_ID)

        assert result.body["status"] == "upcoming"

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == f"/api/maintenance_window/{MW_ID}/_unarchive"
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_unarchive_in_space(self, mock_async_transport, mock_response):
        """Test unarchiving a maintenance window in a specific space."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_maintenance_window_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.maintenance_windows.unarchive(
            id="abc123", space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == "/s/marketing/api/maintenance_window/abc123/_unarchive"
        )


class TestAsyncMaintenanceWindowsClientErrorHandling:
    """Test AsyncMaintenanceWindowsClient error handling."""

    @pytest.mark.asyncio
    async def test_get_not_found_error(self, mock_async_transport, mock_response):
        """Test that a 404 response raises NotFoundError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Failed to get maintenance window by id: nope",
            },
            status=404,
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(NotFoundError):
            await client.maintenance_windows.get(id="nope")

    @pytest.mark.asyncio
    async def test_create_authorization_error(
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
            await client.maintenance_windows.create(
                title="kbnpy-mw-example",
                schedule=SCHEDULE,
            )
