"""Unit tests for AsyncEntityAnalyticsClient."""

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client.entity_analytics import AsyncEntityAnalyticsClient
from kibana.exceptions import NotFoundError


def _asset_criticality_body(**overrides):
    """Build a representative asset criticality record response body."""
    body = {
        "id_field": "host.name",
        "id_value": "my-host",
        "criticality_level": "high_impact",
        "@timestamp": "2026-07-06T21:52:20.422Z",
        "asset": {"criticality": "high_impact"},
        "host": {
            "name": "my-host",
            "asset": {"criticality": "high_impact"},
        },
    }
    body.update(overrides)
    return body


def _watchlist_body(**overrides):
    """Build a representative watchlist response body."""
    body = {
        "id": "b8b48d31-3026-45c0-aa8a-b8ed7f86ade8",
        "name": "High Risk Vendors",
        "description": "High risk vendor watchlist",
        "riskModifier": 1.5,
        "managed": False,
        "entitySourceIds": [],
        "entityCount": 0,
        "createdAt": "2026-07-06T21:54:20.835Z",
        "updatedAt": "2026-07-06T21:54:20.835Z",
    }
    body.update(overrides)
    return body


class TestAsyncEntityAnalyticsClientInitialization:
    """Test AsyncEntityAnalyticsClient initialization and wiring."""

    async def test_client_initialization(self, mock_async_transport):
        """Test that AsyncEntityAnalyticsClient can be initialized with a parent."""
        client = AsyncKibana(_transport=mock_async_transport)
        ea_client = AsyncEntityAnalyticsClient(client)
        assert ea_client._client is client

    async def test_entity_analytics_property_returns_client(self, mock_async_transport):
        """Test that client.entity_analytics returns an AsyncEntityAnalyticsClient."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.entity_analytics, AsyncEntityAnalyticsClient)

    async def test_entity_analytics_property_caching(self, mock_async_transport):
        """Test that the entity_analytics property returns the same instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert client.entity_analytics is client.entity_analytics


class TestAsyncAssetCriticality:
    """Test the asset criticality methods."""

    async def test_create_asset_criticality(self, mock_async_transport, mock_response):
        """Test upserting an asset criticality record."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_asset_criticality_body()
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.create_asset_criticality(
            id_field="host.name",
            id_value="my-host",
            criticality_level="high_impact",
            refresh="wait_for",
        )

        assert result.body["criticality_level"] == "high_impact"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/asset_criticality"
        assert call_kwargs["body"] == {
            "id_field": "host.name",
            "id_value": "my-host",
            "criticality_level": "high_impact",
            "refresh": "wait_for",
        }
        # Mutating call: kbn-xsrf and JSON content-type injected by base client
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs["headers"]["content-type"] == "application/json"

    async def test_create_asset_criticality_without_refresh(
        self, mock_async_transport, mock_response
    ):
        """Test that refresh is omitted from the body when not provided."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_asset_criticality_body()
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.create_asset_criticality(
            id_field="host.name",
            id_value="my-host",
            criticality_level="high_impact",
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert "refresh" not in call_kwargs["body"]

    async def test_get_asset_criticality(self, mock_async_transport, mock_response):
        """Test getting an asset criticality record with encoded params."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_asset_criticality_body()
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.get_asset_criticality(
            id_field="host.name", id_value="my host"
        )

        assert result.body["id_field"] == "host.name"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/asset_criticality?id_field=host.name&id_value=my+host"
        )

    async def test_delete_asset_criticality(self, mock_async_transport, mock_response):
        """Test deleting an asset criticality record."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"deleted": True, "record": _asset_criticality_body()}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.delete_asset_criticality(
            id_field="host.name", id_value="my-host", refresh="wait_for"
        )

        assert result.body["deleted"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == (
            "/api/asset_criticality"
            "?id_field=host.name&id_value=my-host&refresh=wait_for"
        )

    async def test_bulk_upsert_asset_criticality(
        self, mock_async_transport, mock_response
    ):
        """Test bulk upserting asset criticality records."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "errors": [],
                "stats": {"successful": 2, "failed": 0, "total": 2},
            }
        )
        client = AsyncKibana(_transport=mock_async_transport)

        records = [
            {
                "id_field": "host.name",
                "id_value": "host-1",
                "criticality_level": "high_impact",
            },
            {
                "id_field": "user.name",
                "id_value": "user-1",
                "criticality_level": "unassigned",
            },
        ]
        result = await client.entity_analytics.bulk_upsert_asset_criticality(
            records=records
        )

        assert result.body["stats"]["successful"] == 2
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/asset_criticality/bulk"
        assert call_kwargs["body"] == {"records": records}

    async def test_find_asset_criticality(self, mock_async_transport, mock_response):
        """Test listing asset criticality records with all query params."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"records": [], "total": 0, "page": 1, "per_page": 10}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.find_asset_criticality(
            sort_field="@timestamp",
            sort_direction="desc",
            page=2,
            per_page=50,
            kuery="criticality_level: high_impact",
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/asset_criticality/list?sort_field=%40timestamp"
            "&sort_direction=desc&page=2&per_page=50"
            "&kuery=criticality_level%3A+high_impact"
        )

    async def test_find_asset_criticality_no_params(
        self, mock_async_transport, mock_response
    ):
        """Test that no query string is added when no filters are given."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"records": [], "total": 0, "page": 1, "per_page": 10}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.find_asset_criticality()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/asset_criticality/list"


class TestAsyncRiskEngine:
    """Test the risk engine methods."""

    async def test_schedule_risk_engine_now(self, mock_async_transport, mock_response):
        """Test scheduling an immediate risk engine run."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"success": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.schedule_risk_engine_now()

        assert result.body["success"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/risk_score/engine/schedule_now"
        assert "body" not in call_kwargs

    async def test_configure_risk_engine_saved_object(
        self, mock_async_transport, mock_response
    ):
        """Test configuring the risk engine saved object."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"risk_engine_saved_object_configured": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.configure_risk_engine_saved_object(
            enable_reset_to_zero=True,
            exclude_alert_statuses=["closed"],
            exclude_alert_tags=["False Positive"],
            filters=[{"entity_types": ["host"], "filter": "host.name: web-*"}],
            page_size=1000,
            range={"start": "now-30d", "end": "now"},
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["target"] == (
            "/api/risk_score/engine/saved_object/configure"
        )
        assert call_kwargs["body"] == {
            "enable_reset_to_zero": True,
            "exclude_alert_statuses": ["closed"],
            "exclude_alert_tags": ["False Positive"],
            "filters": [{"entity_types": ["host"], "filter": "host.name: web-*"}],
            "page_size": 1000,
            "range": {"start": "now-30d", "end": "now"},
        }

    async def test_cleanup_risk_engine(self, mock_async_transport, mock_response):
        """Test the risk engine cleanup (dangerously delete data) call."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"risk_engine_cleanup": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.cleanup_risk_engine()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == (
            "/api/risk_score/engine/dangerously_delete_data"
        )


class TestAsyncMonitoringEngine:
    """Test the Privilege Monitoring Engine methods."""

    async def test_init_monitoring_engine(self, mock_async_transport, mock_response):
        """Test initializing the monitoring engine."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"status": "started"}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.init_monitoring_engine()

        assert result.body["status"] == "started"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == ("/api/entity_analytics/monitoring/engine/init")

    async def test_disable_monitoring_engine(self, mock_async_transport, mock_response):
        """Test disabling the monitoring engine."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"status": "disabled"}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.disable_monitoring_engine()

        assert result.body["status"] == "disabled"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/entity_analytics/monitoring/engine/disable"
        )

    async def test_schedule_monitoring_engine_now(
        self, mock_async_transport, mock_response
    ):
        """Test scheduling an immediate monitoring engine run."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"success": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.schedule_monitoring_engine_now()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/entity_analytics/monitoring/engine/schedule_now"
        )

    async def test_delete_monitoring_engine_with_data(
        self, mock_async_transport, mock_response
    ):
        """Test deleting the monitoring engine with data=True encoding."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"deleted": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.delete_monitoring_engine(data=True)

        assert result.body["deleted"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == (
            "/api/entity_analytics/monitoring/engine/delete?data=true"
        )

    async def test_delete_monitoring_engine_default(
        self, mock_async_transport, mock_response
    ):
        """Test deleting the monitoring engine without the data param."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"deleted": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.delete_monitoring_engine()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/entity_analytics/monitoring/engine/delete"
        )

    async def test_get_monitoring_health(self, mock_async_transport, mock_response):
        """Test the monitoring engine health check."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "status": "started",
                "users": {"current_count": 0, "max_allowed": 10000},
            }
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.get_monitoring_health()

        assert result.body["status"] == "started"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/entity_analytics/monitoring/privileges/health"
        )
        assert call_kwargs["headers"] == {"accept": "application/json"}

    async def test_get_monitoring_privileges(self, mock_async_transport, mock_response):
        """Test the monitoring privileges check."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"privileges": {"elasticsearch": {}}, "has_all_required": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.get_monitoring_privileges()

        assert result.body["has_all_required"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/entity_analytics/monitoring/privileges/privileges"
        )


class TestAsyncMonitoredUsers:
    """Test the monitored (privileged) users methods."""

    async def test_create_monitored_user(self, mock_async_transport, mock_response):
        """Test creating a monitored user."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "id": "OflsOZ8BiXLbCmmNbJ9J",
                "user": {"name": "admin-user", "is_privileged": True},
                "labels": {"sources": ["api"]},
            }
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.create_monitored_user(name="admin-user")

        assert result.body["user"]["is_privileged"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/entity_analytics/monitoring/users"
        assert call_kwargs["body"] == {"user": {"name": "admin-user"}}

    async def test_create_monitored_user_with_labels(
        self, mock_async_transport, mock_response
    ):
        """Test creating a monitored user with monitoring labels."""
        mock_async_transport.perform_request.return_value = mock_response(body={})
        client = AsyncKibana(_transport=mock_async_transport)

        labels = [{"field": "team", "value": "ops", "source": "api"}]
        await client.entity_analytics.create_monitored_user(
            name="admin-user", monitoring_labels=labels
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "user": {"name": "admin-user"},
            "entity_analytics_monitoring": {"labels": labels},
        }

    async def test_update_monitored_user(self, mock_async_transport, mock_response):
        """Test updating a monitored user with a path-encoded ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "abc/123", "user": {"name": "renamed"}}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        doc = {"user": {"name": "renamed", "is_privileged": True}}
        await client.entity_analytics.update_monitored_user(id="abc/123", doc=doc)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == (
            "/api/entity_analytics/monitoring/users/abc%2F123"
        )
        assert call_kwargs["body"] == doc

    async def test_delete_monitored_user(self, mock_async_transport, mock_response):
        """Test deleting a monitored user."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"acknowledged": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.delete_monitored_user(id="user-doc-id")

        assert result.body["acknowledged"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == (
            "/api/entity_analytics/monitoring/users/user-doc-id"
        )

    async def test_list_monitored_users(self, mock_async_transport, mock_response):
        """Test listing monitored users with a KQL filter."""
        mock_async_transport.perform_request.return_value = mock_response(body=[])
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.list_monitored_users(kql="user.name: admin*")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/entity_analytics/monitoring/users/list" "?kql=user.name%3A+admin%2A"
        )

    async def test_upload_monitored_users_csv(
        self, mock_async_transport, mock_response
    ):
        """Test the monitored users CSV multipart upload."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "errors": [],
                "stats": {
                    "failedOperations": 0,
                    "successfulOperations": 2,
                    "uploaded": 2,
                    "totalOperations": 2,
                },
            }
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.upload_monitored_users_csv(
            file="admin-1\nadmin-2\n"
        )

        assert result.body["stats"]["uploaded"] == 2
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == ("/api/entity_analytics/monitoring/users/_csv")
        assert call_kwargs["headers"]["content-type"].startswith(
            "multipart/form-data; boundary="
        )
        assert b'name="file"; filename="users.csv"' in call_kwargs["body"]
        assert b"admin-1\nadmin-2\n" in call_kwargs["body"]

    async def test_upload_monitored_users_csv_empty_raises(self, mock_async_transport):
        """Test that an empty CSV payload raises ValueError."""
        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(ValueError, match="'file' is required"):
            await client.entity_analytics.upload_monitored_users_csv(file="")


class TestAsyncPrivilegedAccessDetection:
    """Test the privileged access detection (PAD) package methods."""

    async def test_install_pad_package(self, mock_async_transport, mock_response):
        """Test installing the PAD package."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "message": (
                    "Successfully installed privileged access detection package."
                )
            }
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.install_pad_package()

        assert "Successfully installed" in result.body["message"]
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/entity_analytics/privileged_user_monitoring/pad/install"
        )

    async def test_get_pad_status(self, mock_async_transport, mock_response):
        """Test getting the PAD package status."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "package_installation_status": "complete",
                "ml_module_setup_status": "incomplete",
                "jobs": [],
            }
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.get_pad_status()

        assert result.body["package_installation_status"] == "complete"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/entity_analytics/privileged_user_monitoring/pad/status"
        )


class TestAsyncWatchlists:
    """Test the watchlists methods."""

    async def test_create_watchlist(self, mock_async_transport, mock_response):
        """Test creating a watchlist with entity sources."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_watchlist_body()
        )
        client = AsyncKibana(_transport=mock_async_transport)

        sources = [
            {
                "type": "index",
                "name": "My User Index Source",
                "indexPattern": "my-sync-index",
                "identifierField": "user.name",
                "enabled": True,
            }
        ]
        result = await client.entity_analytics.create_watchlist(
            name="High Risk Vendors",
            risk_modifier=1.5,
            description="High risk vendor watchlist",
            managed=False,
            entity_sources=sources,
        )

        assert result.body["id"] == "b8b48d31-3026-45c0-aa8a-b8ed7f86ade8"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/entity_analytics/watchlists"
        assert call_kwargs["body"] == {
            "name": "High Risk Vendors",
            "riskModifier": 1.5,
            "description": "High risk vendor watchlist",
            "managed": False,
            "entitySources": sources,
        }

    async def test_list_watchlists(self, mock_async_transport, mock_response):
        """Test listing watchlists."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=[_watchlist_body()]
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.list_watchlists()

        assert result.body[0]["name"] == "High Risk Vendors"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/entity_analytics/watchlists/list"

    async def test_get_watchlist(self, mock_async_transport, mock_response):
        """Test getting a watchlist by ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_watchlist_body()
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.get_watchlist(
            id="b8b48d31-3026-45c0-aa8a-b8ed7f86ade8"
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/entity_analytics/watchlists/b8b48d31-3026-45c0-aa8a-b8ed7f86ade8"
        )

    async def test_update_watchlist(self, mock_async_transport, mock_response):
        """Test updating a watchlist."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_watchlist_body(riskModifier=1.8)
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.update_watchlist(
            id="wl-1",
            name="High Risk Vendors",
            risk_modifier=1.8,
            description="Updated",
        )

        assert result.body["riskModifier"] == 1.8
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/entity_analytics/watchlists/wl-1"
        assert call_kwargs["body"] == {
            "name": "High Risk Vendors",
            "riskModifier": 1.8,
            "description": "Updated",
        }

    async def test_delete_watchlist(self, mock_async_transport, mock_response):
        """Test deleting a watchlist (live-supported, not in the 9.4.3 spec)."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"deleted": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.delete_watchlist(id="wl-1")

        assert result.body["deleted"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/entity_analytics/watchlists/wl-1"

    async def test_upload_watchlist_csv(self, mock_async_transport, mock_response):
        """Test the watchlist CSV multipart upload."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "total": 1,
                "successful": 1,
                "failed": 0,
                "unmatched": 0,
                "items": [],
            }
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.upload_watchlist_csv(
            watchlist_id="wl-1",
            file="type,name\nuser,alice\n",
        )

        assert result.body["successful"] == 1
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/entity_analytics/watchlists/wl-1/csv_upload"
        )
        assert call_kwargs["headers"]["content-type"].startswith(
            "multipart/form-data; boundary="
        )
        assert b'filename="watchlist.csv"' in call_kwargs["body"]
        assert b"type,name\nuser,alice\n" in call_kwargs["body"]

    async def test_upload_watchlist_csv_empty_raises(self, mock_async_transport):
        """Test that an empty watchlist CSV payload raises ValueError."""
        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(ValueError, match="'file' is required"):
            await client.entity_analytics.upload_watchlist_csv(
                watchlist_id="wl-1", file=""
            )

    async def test_assign_watchlist_entities(self, mock_async_transport, mock_response):
        """Test assigning entities to a watchlist."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "successful": 1,
                "failed": 0,
                "not_found": 0,
                "total": 1,
                "items": [],
            }
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.assign_watchlist_entities(
            watchlist_id="wl-1", euids=["host:web-01"]
        )

        assert result.body["successful"] == 1
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/entity_analytics/watchlists/wl-1/entities/assign"
        )
        assert call_kwargs["body"] == {"euids": ["host:web-01"]}

    async def test_unassign_watchlist_entities(
        self, mock_async_transport, mock_response
    ):
        """Test unassigning entities from a watchlist."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "successful": 1,
                "failed": 0,
                "not_found": 0,
                "total": 1,
                "items": [],
            }
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.unassign_watchlist_entities(
            watchlist_id="wl-1", euids=["host:web-01"]
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/entity_analytics/watchlists/wl-1/entities/unassign"
        )
        assert call_kwargs["body"] == {"euids": ["host:web-01"]}


class TestAsyncEntityStore:
    """Test the Entity Store methods."""

    async def test_install_entity_store(self, mock_async_transport, mock_response):
        """Test installing the Entity Store."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"ok": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.install_entity_store(
            entity_types=["host"],
            log_extraction={"frequency": "5m", "lookbackPeriod": "12h"},
            history_snapshot={"frequency": "24h"},
        )

        assert result.body["ok"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/security/entity_store/install"
        assert call_kwargs["body"] == {
            "entityTypes": ["host"],
            "logExtraction": {"frequency": "5m", "lookbackPeriod": "12h"},
            "historySnapshot": {"frequency": "24h"},
        }

    async def test_install_entity_store_defaults(
        self, mock_async_transport, mock_response
    ):
        """Test that install sends an empty body when no options are given."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"ok": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.install_entity_store()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {}

    async def test_uninstall_entity_store(self, mock_async_transport, mock_response):
        """Test uninstalling the Entity Store for specific types."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"ok": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.uninstall_entity_store(entity_types=["host"])

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/security/entity_store/uninstall"
        assert call_kwargs["body"] == {"entityTypes": ["host"]}

    async def test_update_entity_store(self, mock_async_transport, mock_response):
        """Test updating the Entity Store log extraction settings."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"ok": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.update_entity_store(
            log_extraction={"frequency": "10m"}
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/security/entity_store"
        assert call_kwargs["body"] == {"logExtraction": {"frequency": "10m"}}

    async def test_get_entity_store_status(self, mock_async_transport, mock_response):
        """Test getting the Entity Store status with components."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"status": "running", "engines": [{"type": "host"}]}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.get_entity_store_status(
            include_components=True
        )

        assert result.body["status"] == "running"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/security/entity_store/status?include_components=true"
        )

    async def test_start_entity_store(self, mock_async_transport, mock_response):
        """Test starting Entity Store engines."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"ok": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.start_entity_store(entity_types=["host", "user"])

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/security/entity_store/start"
        assert call_kwargs["body"] == {"entityTypes": ["host", "user"]}

    async def test_stop_entity_store(self, mock_async_transport, mock_response):
        """Test stopping Entity Store engines."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"ok": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.stop_entity_store()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/security/entity_store/stop"
        assert call_kwargs["body"] == {}

    async def test_list_entities(self, mock_async_transport, mock_response):
        """Test listing entities with paging, sorting and type filters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"records": [], "total": 0, "page": 1, "per_page": 100}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.list_entities(
            entity_types=["host", "user"],
            sort_field="entity.name",
            sort_order="asc",
            page=1,
            per_page=100,
            filter='host.name: "web-01"',
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        target = call_kwargs["target"]
        assert target.startswith("/api/security/entity_store/entities?")
        assert "filter=host.name%3A+%22web-01%22" in target
        assert "sort_field=entity.name" in target
        assert "sort_order=asc" in target
        assert "page=1" in target
        assert "per_page=100" in target
        # list params are encoded as repeated keys
        assert "entity_types=host" in target
        assert "entity_types=user" in target

    async def test_list_entities_camel_case_params(
        self, mock_async_transport, mock_response
    ):
        """Test that search_after and filter_query map to camelCase params."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"records": [], "total": 0}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.list_entities(
            size=10,
            search_after="cursor123",
            filter_query='{"term":{}}',
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        target = call_kwargs["target"]
        assert "size=10" in target
        assert "searchAfter=cursor123" in target
        assert "filterQuery=%7B%22term%22%3A%7B%7D%7D" in target

    async def test_create_entity(self, mock_async_transport, mock_response):
        """Test creating an entity."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"ok": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        document = {"host": {"name": "web-01"}}
        result = await client.entity_analytics.create_entity(
            entity_type="host", document=document
        )

        assert result.body["ok"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/security/entity_store/entities/host"
        assert call_kwargs["body"] == document

    async def test_update_entity_with_force(self, mock_async_transport, mock_response):
        """Test updating an entity with the force flag."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"ok": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        document = {"host": {"name": "web-01"}, "labels": {"env": "prod"}}
        await client.entity_analytics.update_entity(
            entity_type="host", document=document, force=True
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == (
            "/api/security/entity_store/entities/host?force=true"
        )
        assert call_kwargs["body"] == document

    async def test_bulk_update_entities(self, mock_async_transport, mock_response):
        """Test bulk updating entities."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"ok": True, "errors": []}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        entities = [{"type": "host", "doc": {"host": {"name": "web-01"}}}]
        result = await client.entity_analytics.bulk_update_entities(
            entities=entities, force=True
        )

        assert result.body["errors"] == []
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == (
            "/api/security/entity_store/entities/bulk?force=true"
        )
        assert call_kwargs["body"] == {"entities": entities}

    async def test_delete_entity(self, mock_async_transport, mock_response):
        """Test deleting an entity by EUID (DELETE with a JSON body)."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"deleted": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.delete_entity(entity_id="host:web-01")

        assert result.body["deleted"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/security/entity_store/entities/"
        assert call_kwargs["body"] == {"entityId": "host:web-01"}

    async def test_get_entity_resolution_group(
        self, mock_async_transport, mock_response
    ):
        """Test getting an entity's resolution group."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"target": {}, "aliases": [], "group_size": 1}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.get_entity_resolution_group(
            entity_id="host:web-01"
        )

        assert result.body["group_size"] == 1
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/security/entity_store/resolution/group?entity_id=host%3Aweb-01"
        )

    async def test_link_entities(self, mock_async_transport, mock_response):
        """Test linking entities to a target entity."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "linked": ["host:web-01.internal"],
                "skipped": [],
                "target_id": "host:web-01",
            }
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.link_entities(
            entity_ids=["host:web-01.internal"], target_id="host:web-01"
        )

        assert result.body["linked"] == ["host:web-01.internal"]
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/security/entity_store/resolution/link"
        assert call_kwargs["body"] == {
            "entity_ids": ["host:web-01.internal"],
            "target_id": "host:web-01",
        }

    async def test_unlink_entities(self, mock_async_transport, mock_response):
        """Test unlinking entities from their resolution group."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"unlinked": ["host:web-01.internal"], "skipped": []}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.entity_analytics.unlink_entities(
            entity_ids=["host:web-01.internal"]
        )

        assert result.body["unlinked"] == ["host:web-01.internal"]
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == ("/api/security/entity_store/resolution/unlink")
        assert call_kwargs["body"] == {"entity_ids": ["host:web-01.internal"]}


class TestAsyncEntityAnalyticsSpaceScoping:
    """Test space-scoped path building."""

    async def test_space_scoped_path(self, mock_async_transport, mock_response):
        """Test that space_id builds an /s/<space>/api/... path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"status": "not_installed", "engines": []}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.get_entity_store_status(
            space_id="security-team", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/s/security-team/api/security/entity_store/status"
        )

    async def test_space_scoped_path_with_params(
        self, mock_async_transport, mock_response
    ):
        """Test space scoping combined with query parameters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"records": [], "total": 0}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.entity_analytics.find_asset_criticality(
            per_page=5, space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/s/marketing/api/asset_criticality/list?per_page=5"
        )


class TestAsyncEntityAnalyticsErrorHandling:
    """Test AsyncEntityAnalyticsClient error mapping."""

    async def test_get_asset_criticality_not_found(
        self, mock_async_transport, mock_response
    ):
        """Test 404 responses raise NotFoundError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"statusCode": 404, "error": "Not Found", "message": "Not Found"},
            status=404,
        )
        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(NotFoundError):
            await client.entity_analytics.get_asset_criticality(
                id_field="host.name", id_value="missing-host"
            )
