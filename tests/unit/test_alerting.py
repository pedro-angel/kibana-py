"""Unit tests for the Alerting (Rules) API client.

Tests cover parameter validation, path construction, space-scoping,
and request body building for all five RulesClient methods plus
the AlertingClient wrapper.
"""

from unittest.mock import MagicMock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._sync.client.alerting import AlertingClient, RulesClient

# ─── Helpers ───────────────────────────────────────────────────────────────────


def _mock_client():
    """Create a mock BaseClient that returns canned responses."""
    client = MagicMock()
    client.perform_request.return_value = ObjectApiResponse(
        body={"id": "rule-123", "name": "test-rule"},
        meta=MagicMock(),
    )
    return client


def _rules_client(**kwargs):
    """Build a RulesClient with validation disabled for unit tests."""
    client = _mock_client()
    return RulesClient(client, validate_spaces=False, **kwargs), client


def _last_call(mock):
    """Extract (method, path, body, params) from the last perform_request call."""
    kw = mock.perform_request.call_args.kwargs
    return (
        kw.get("method"),
        kw.get("path"),
        kw.get("body"),
        kw.get("params"),
    )


# ─── RulesClient.create ───────────────────────────────────────────────────────


class TestRulesCreate:
    """Tests for RulesClient.create."""

    def test_create_minimal(self):
        rules, mock = _rules_client()
        rules.create(
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

    def test_create_with_all_options(self):
        rules, mock = _rules_client()
        rules.create(
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

    def test_create_in_space(self):
        rules, mock = _rules_client()
        rules.create(
            name="Space Rule",
            consumer="alerts",
            rule_type_id=".threshold",
            schedule={"interval": "1m"},
            params={},
            space_id="marketing",
        )

        _, path, _, _ = _last_call(mock)
        assert path == "/s/marketing/api/alerting/rule"

    def test_create_missing_name_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="name"):
            rules.create(
                name="",
                consumer="alerts",
                rule_type_id=".threshold",
                schedule={"interval": "1m"},
                params={},
            )

    def test_create_missing_consumer_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="consumer"):
            rules.create(
                name="Rule",
                consumer="",
                rule_type_id=".threshold",
                schedule={"interval": "1m"},
                params={},
            )

    def test_create_missing_rule_type_id_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="rule_type_id"):
            rules.create(
                name="Rule",
                consumer="alerts",
                rule_type_id="",
                schedule={"interval": "1m"},
                params={},
            )

    def test_create_missing_schedule_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="schedule"):
            rules.create(
                name="Rule",
                consumer="alerts",
                rule_type_id=".threshold",
                schedule=None,  # type: ignore[arg-type]
                params={},
            )

    def test_create_missing_params_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="params"):
            rules.create(
                name="Rule",
                consumer="alerts",
                rule_type_id=".threshold",
                schedule={"interval": "1m"},
                params=None,  # type: ignore[arg-type]
            )


# ─── RulesClient.get ──────────────────────────────────────────────────────────


class TestRulesGet:
    """Tests for RulesClient.get."""

    def test_get_by_id(self):
        rules, mock = _rules_client()
        rules.get(id="rule-abc")

        method, path, _, _ = _last_call(mock)
        assert method == "GET"
        assert path == "/api/alerting/rule/rule-abc"

    def test_get_in_space(self):
        rules, mock = _rules_client()
        rules.get(id="rule-456", space_id="ops")

        _, path, _, _ = _last_call(mock)
        assert path == "/s/ops/api/alerting/rule/rule-456"

    def test_get_url_encodes_id(self):
        rules, mock = _rules_client()
        rules.get(id="rule with spaces")

        _, path, _, _ = _last_call(mock)
        assert "rule%20with%20spaces" in path

    def test_get_missing_id_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="id"):
            rules.get(id="")


# ─── RulesClient.update ───────────────────────────────────────────────────────


class TestRulesUpdate:
    """Tests for RulesClient.update."""

    def test_update_minimal(self):
        rules, mock = _rules_client()
        rules.update(
            id="rule-123",
            name="Updated Rule",
            schedule={"interval": "5m"},
            params={"threshold": 95},
        )

        method, path, body, _ = _last_call(mock)
        assert method == "PUT"
        assert path == "/api/alerting/rule/rule-123"
        assert body["name"] == "Updated Rule"

    def test_update_with_optional_fields(self):
        rules, mock = _rules_client()
        rules.update(
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

    def test_update_in_space(self):
        rules, mock = _rules_client()
        rules.update(
            id="rule-789",
            name="Rule",
            schedule={"interval": "1m"},
            params={},
            space_id="dev",
        )

        _, path, _, _ = _last_call(mock)
        assert path == "/s/dev/api/alerting/rule/rule-789"

    def test_update_missing_id_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="id"):
            rules.update(
                id="",
                name="Rule",
                schedule={"interval": "1m"},
                params={},
            )


# ─── RulesClient.delete ───────────────────────────────────────────────────────


class TestRulesDelete:
    """Tests for RulesClient.delete."""

    def test_delete_by_id(self):
        rules, mock = _rules_client()
        rules.delete(id="rule-del")

        method, path, _, _ = _last_call(mock)
        assert method == "DELETE"
        assert path == "/api/alerting/rule/rule-del"

    def test_delete_in_space(self):
        rules, mock = _rules_client()
        rules.delete(id="rule-del", space_id="staging")

        _, path, _, _ = _last_call(mock)
        assert path == "/s/staging/api/alerting/rule/rule-del"

    def test_delete_missing_id_raises(self):
        rules, _ = _rules_client()
        with pytest.raises(ValueError, match="id"):
            rules.delete(id="")


# ─── RulesClient.find ─────────────────────────────────────────────────────────


class TestRulesFind:
    """Tests for RulesClient.find."""

    def test_find_defaults(self):
        """A bare find() must send no query params at all.

        Kibana 9.4.3 rejects ``sort_order`` without ``sort_field`` (406), so
        no default query parameters may be sent; server defaults apply.
        """
        rules, mock = _rules_client()
        rules.find()

        method, path, _, params = _last_call(mock)
        assert method == "GET"
        assert path == "/api/alerting/rules/_find"
        assert not params

    def test_find_with_search(self):
        rules, mock = _rules_client()
        rules.find(search="cpu", page=2, per_page=50, sort_field="name")

        _, _, _, params = _last_call(mock)
        assert params["search"] == "cpu"
        assert params["page"] == 2
        assert params["per_page"] == 50
        assert params["sort_field"] == "name"

    def test_find_with_filter(self):
        rules, mock = _rules_client()
        rules.find(filter="alert.attributes.tags:production")

        _, _, _, params = _last_call(mock)
        assert params["filter"] == "alert.attributes.tags:production"

    def test_find_in_space(self):
        rules, mock = _rules_client()
        rules.find(space_id="analytics")

        _, path, _, _ = _last_call(mock)
        assert path == "/s/analytics/api/alerting/rules/_find"


# ─── AlertingClient ───────────────────────────────────────────────────────────


class TestAlertingClient:
    """Tests for the AlertingClient wrapper."""

    def test_rule_property(self):
        client = _mock_client()
        alerting = AlertingClient(client)

        assert isinstance(alerting.rule, RulesClient)

    def test_rule_property_caches_instance(self):
        client = _mock_client()
        alerting = AlertingClient(client)

        r1 = alerting.rule
        r2 = alerting.rule
        assert r1 is r2
