"""Unit tests for the async Alerting (Rules) API client.

Tests cover parameter validation, path construction, space-scoping,
and request body building for all five AsyncRulesClient methods plus
the AsyncAlertingClient wrapper.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._async.client.alerting import AsyncAlertingClient, AsyncRulesClient

# ─── Helpers ───────────────────────────────────────────────────────────────────


def _mock_client():
    """Create a mock AsyncBaseClient that returns canned responses."""
    client = MagicMock()
    client.perform_request = AsyncMock(
        return_value=ObjectApiResponse(
            body={"id": "rule-123", "name": "test-rule"},
            meta=MagicMock(),
        )
    )
    return client


def _rules_client(**kwargs):
    """Build an AsyncRulesClient with validation disabled for unit tests."""
    client = _mock_client()
    return AsyncRulesClient(client, validate_spaces=False, **kwargs), client


def _last_call(mock):
    """Extract (method, path, body, params) from the last perform_request call."""
    kw = mock.perform_request.call_args.kwargs
    return (
        kw.get("method"),
        kw.get("path"),
        kw.get("body"),
        kw.get("params"),
    )


# ─── AsyncRulesClient.create ─────────────────────────────────────────────────


class TestAsyncRulesCreate:
    """Tests for AsyncRulesClient.create."""

    @pytest.mark.asyncio
    async def test_create_minimal(self):
        rules, mock = _rules_client()
        await rules.create(
            name="CPU Alert",
            consumer="alerts",
            rule_type_id=".threshold",
            schedule={"interval": "1m"},
            params={"threshold": 90},
        )

        method, path, body, _ = _last_call(mock)
        assert method == "POST"
        assert path == "/api/alerting/rule"
        assert body["name"] == "CPU Alert"
        assert body["consumer"] == "alerts"
        assert body["rule_type_id"] == ".threshold"
        assert body["schedule"] == {"interval": "1m"}
        assert body["params"] == {"threshold": 90}
        assert body["enabled"] is True

    @pytest.mark.asyncio
    async def test_create_with_all_options(self):
        rules, mock = _rules_client()
        await rules.create(
            name="Full Rule",
            consumer="siem",
            rule_type_id=".index-threshold",
            schedule={"interval": "5m"},
            params={"index": "logs-*"},
            actions=[{"group": "default", "id": "act-1"}],
            tags=["prod", "critical"],
            notify_when="onActionGroupChange",
            enabled=False,
            throttle="10m",
        )

        _, _, body, _ = _last_call(mock)
        assert body["enabled"] is False
        assert body["actions"] == [{"group": "default", "id": "act-1"}]
        assert body["tags"] == ["prod", "critical"]
        assert body["notify_when"] == "onActionGroupChange"
        assert body["throttle"] == "10m"

    @pytest.mark.asyncio
    async def test_create_in_space(self):
        rules, mock = _rules_client()
        await rules.create(
            name="Space Rule",
            consumer="alerts",
            rule_type_id=".threshold",
            schedule={"interval": "1m"},
            params={},
            space_id="marketing",
        )

        _, path, _, _ = _last_call(mock)
        assert path == "/s/marketing/api/alerting/rule"

    @pytest.mark.asyncio
    async def test_create_missing_name_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="name"):
            await rules.create(
                name="",
                consumer="alerts",
                rule_type_id=".threshold",
                schedule={"interval": "1m"},
                params={},
            )

    @pytest.mark.asyncio
    async def test_create_missing_consumer_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="consumer"):
            await rules.create(
                name="Rule",
                consumer="",
                rule_type_id=".threshold",
                schedule={"interval": "1m"},
                params={},
            )

    @pytest.mark.asyncio
    async def test_create_missing_rule_type_id_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="rule_type_id"):
            await rules.create(
                name="Rule",
                consumer="alerts",
                rule_type_id="",
                schedule={"interval": "1m"},
                params={},
            )

    @pytest.mark.asyncio
    async def test_create_missing_schedule_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="schedule"):
            await rules.create(
                name="Rule",
                consumer="alerts",
                rule_type_id=".threshold",
                schedule=None,  # type: ignore[arg-type]
                params={},
            )

    @pytest.mark.asyncio
    async def test_create_missing_params_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="params"):
            await rules.create(
                name="Rule",
                consumer="alerts",
                rule_type_id=".threshold",
                schedule={"interval": "1m"},
                params=None,  # type: ignore[arg-type]
            )


# ─── AsyncRulesClient.get ────────────────────────────────────────────────────


class TestAsyncRulesGet:
    """Tests for AsyncRulesClient.get."""

    @pytest.mark.asyncio
    async def test_get_by_id(self):
        rules, mock = _rules_client()
        await rules.get(id="rule-abc")

        method, path, _, _ = _last_call(mock)
        assert method == "GET"
        assert path == "/api/alerting/rule/rule-abc"

    @pytest.mark.asyncio
    async def test_get_in_space(self):
        rules, mock = _rules_client()
        await rules.get(id="rule-456", space_id="ops")

        _, path, _, _ = _last_call(mock)
        assert path == "/s/ops/api/alerting/rule/rule-456"

    @pytest.mark.asyncio
    async def test_get_url_encodes_id(self):
        rules, mock = _rules_client()
        await rules.get(id="rule with spaces")

        _, path, _, _ = _last_call(mock)
        assert "rule%20with%20spaces" in path

    @pytest.mark.asyncio
    async def test_get_missing_id_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="id"):
            await rules.get(id="")


# ─── AsyncRulesClient.update ─────────────────────────────────────────────────


class TestAsyncRulesUpdate:
    """Tests for AsyncRulesClient.update."""

    @pytest.mark.asyncio
    async def test_update_minimal(self):
        rules, mock = _rules_client()
        await rules.update(
            id="rule-123",
            name="Updated Rule",
            schedule={"interval": "5m"},
            params={"threshold": 95},
        )

        method, path, body, _ = _last_call(mock)
        assert method == "PUT"
        assert path == "/api/alerting/rule/rule-123"
        assert body["name"] == "Updated Rule"

    @pytest.mark.asyncio
    async def test_update_with_optional_fields(self):
        rules, mock = _rules_client()
        await rules.update(
            id="rule-123",
            name="Rule",
            schedule={"interval": "1m"},
            params={},
            actions=[{"id": "a1"}],
            tags=["urgent"],
            notify_when="onActiveAlert",
            throttle="5m",
        )

        _, _, body, _ = _last_call(mock)
        assert body["actions"] == [{"id": "a1"}]
        assert body["tags"] == ["urgent"]
        assert "enabled" not in body

    @pytest.mark.asyncio
    async def test_update_in_space(self):
        rules, mock = _rules_client()
        await rules.update(
            id="rule-789",
            name="Rule",
            schedule={"interval": "1m"},
            params={},
            space_id="dev",
        )

        _, path, _, _ = _last_call(mock)
        assert path == "/s/dev/api/alerting/rule/rule-789"

    @pytest.mark.asyncio
    async def test_update_missing_id_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="id"):
            await rules.update(
                id="",
                name="Rule",
                schedule={"interval": "1m"},
                params={},
            )


# ─── AsyncRulesClient.delete ─────────────────────────────────────────────────


class TestAsyncRulesDelete:
    """Tests for AsyncRulesClient.delete."""

    @pytest.mark.asyncio
    async def test_delete_by_id(self):
        rules, mock = _rules_client()
        await rules.delete(id="rule-del")

        method, path, _, _ = _last_call(mock)
        assert method == "DELETE"
        assert path == "/api/alerting/rule/rule-del"

    @pytest.mark.asyncio
    async def test_delete_in_space(self):
        rules, mock = _rules_client()
        await rules.delete(id="rule-del", space_id="staging")

        _, path, _, _ = _last_call(mock)
        assert path == "/s/staging/api/alerting/rule/rule-del"

    @pytest.mark.asyncio
    async def test_delete_missing_id_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="id"):
            await rules.delete(id="")


# ─── AsyncRulesClient.find ───────────────────────────────────────────────────


class TestAsyncRulesFind:
    """Tests for AsyncRulesClient.find."""

    @pytest.mark.asyncio
    async def test_find_defaults(self):
        rules, mock = _rules_client()
        await rules.find()

        method, path, _, params = _last_call(mock)
        assert method == "GET"
        assert path == "/api/alerting/rules/_find"
        assert params["page"] == 1
        assert params["per_page"] == 20
        assert params["sort_order"] == "asc"

    @pytest.mark.asyncio
    async def test_find_with_search(self):
        rules, mock = _rules_client()
        await rules.find(search="cpu", page=2, per_page=50, sort_field="name")

        _, _, _, params = _last_call(mock)
        assert params["search"] == "cpu"
        assert params["page"] == 2
        assert params["per_page"] == 50
        assert params["sort_field"] == "name"

    @pytest.mark.asyncio
    async def test_find_with_filter(self):
        rules, mock = _rules_client()
        await rules.find(filter="alert.attributes.tags:production")

        _, _, _, params = _last_call(mock)
        assert params["filter"] == "alert.attributes.tags:production"

    @pytest.mark.asyncio
    async def test_find_in_space(self):
        rules, mock = _rules_client()
        await rules.find(space_id="analytics")

        _, path, _, _ = _last_call(mock)
        assert path == "/s/analytics/api/alerting/rules/_find"


# ─── AsyncAlertingClient ─────────────────────────────────────────────────────


class TestAsyncAlertingClient:
    """Tests for the AsyncAlertingClient wrapper."""

    def test_rule_property(self):
        client = _mock_client()
        alerting = AsyncAlertingClient(client)

        assert isinstance(alerting.rule, AsyncRulesClient)

    def test_rule_property_caches_instance(self):
        client = _mock_client()
        alerting = AsyncAlertingClient(client)

        r1 = alerting.rule
        r2 = alerting.rule
        assert r1 is r2
