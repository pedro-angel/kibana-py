"""Unit tests for the Alerting API client (Kibana 9.4.3 surface).

Covers every public method of ``AlertingClient``, ``RulesClient`` and
``BackfillClient``: exact method + target assertions, header injection,
query-parameter encoding (lists as repeated keys, dicts as JSON strings)
and body passthrough, plus 404 error mapping.
"""

import pytest

from kibana._sync.client import Kibana
from kibana._sync.client.alerting import (
    AlertingClient,
    BackfillClient,
    RulesClient,
)
from kibana.exceptions import NotFoundError


@pytest.fixture
def client(mock_transport, mock_response):
    """Kibana client whose transport returns a canned 200 response."""
    mock_transport.perform_request.return_value = mock_response(
        body={"id": "rule-123", "name": "test-rule"}
    )
    return Kibana(_transport=mock_transport)


def _call(mock_transport):
    """Extract (method, target, body, headers) of the last transport call."""
    kwargs = mock_transport.perform_request.call_args[1]
    return (
        kwargs["method"],
        kwargs["target"],
        kwargs.get("body"),
        kwargs.get("headers") or {},
    )


class TestRulesCreate:
    def test_create_minimal(self, client, mock_transport):
        client.alerting.rule.create(
            name="CPU Alert",
            consumer="alerts",
            rule_type_id=".index-threshold",
            schedule={"interval": "1m"},
            params={"threshold": [90]},
        )

        method, target, body, headers = _call(mock_transport)
        assert method == "POST"
        assert target == "/api/alerting/rule"
        assert body == {
            "name": "CPU Alert",
            "consumer": "alerts",
            "rule_type_id": ".index-threshold",
            "schedule": {"interval": "1m"},
            "params": {"threshold": [90]},
            "enabled": True,
        }
        assert headers["kbn-xsrf"] == "true"
        assert headers["content-type"] == "application/json"

    def test_create_with_custom_id(self, client, mock_transport):
        client.alerting.rule.create(
            name="Rule",
            consumer="alerts",
            rule_type_id=".es-query",
            schedule={"interval": "1m"},
            params={},
            id="my custom/id",
        )

        method, target, _, _ = _call(mock_transport)
        assert method == "POST"
        assert target == "/api/alerting/rule/my%20custom%2Fid"

    def test_create_with_all_options(self, client, mock_transport):
        client.alerting.rule.create(
            name="Full Rule",
            consumer="siem",
            rule_type_id=".index-threshold",
            schedule={"interval": "5m"},
            params={"index": ["logs-*"]},
            actions=[{"group": "default", "id": "act-1"}],
            tags=["prod"],
            notify_when="onActionGroupChange",
            enabled=False,
            throttle="10m",
            alert_delay={"active": 3},
            flapping={"look_back_window": 10, "status_change_threshold": 3},
            artifacts={"dashboards": [{"id": "dash-1"}]},
        )

        _, _, body, _ = _call(mock_transport)
        assert body["enabled"] is False
        assert body["actions"] == [{"group": "default", "id": "act-1"}]
        assert body["tags"] == ["prod"]
        assert body["notify_when"] == "onActionGroupChange"
        assert body["throttle"] == "10m"
        assert body["alert_delay"] == {"active": 3}
        assert body["flapping"] == {
            "look_back_window": 10,
            "status_change_threshold": 3,
        }
        assert body["artifacts"] == {"dashboards": [{"id": "dash-1"}]}

    def test_create_in_space(self, client, mock_transport):
        client.alerting.rule.create(
            name="Space Rule",
            consumer="alerts",
            rule_type_id=".es-query",
            schedule={"interval": "1m"},
            params={},
            space_id="marketing",
            validate_spaces=False,
        )

        _, target, _, _ = _call(mock_transport)
        assert target == "/s/marketing/api/alerting/rule"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"name": ""},
            {"consumer": ""},
            {"rule_type_id": ""},
            {"schedule": None},
            {"params": None},
        ],
    )
    def test_create_missing_required_raises(self, client, kwargs):
        defaults = dict(
            name="Rule",
            consumer="alerts",
            rule_type_id=".es-query",
            schedule={"interval": "1m"},
            params={},
        )
        defaults.update(kwargs)
        with pytest.raises(ValueError):
            client.alerting.rule.create(**defaults)


class TestRulesGet:
    def test_get(self, client, mock_transport):
        client.alerting.rule.get(id="rule-abc")

        method, target, body, _ = _call(mock_transport)
        assert method == "GET"
        assert target == "/api/alerting/rule/rule-abc"
        assert body is None

    def test_get_url_encodes_id(self, client, mock_transport):
        client.alerting.rule.get(id="rule with spaces")

        _, target, _, _ = _call(mock_transport)
        assert target == "/api/alerting/rule/rule%20with%20spaces"

    def test_get_missing_id_raises(self, client):
        with pytest.raises(ValueError, match="id"):
            client.alerting.rule.get(id="")

    def test_get_not_found_maps_to_error(self, client, mock_transport, mock_response):
        mock_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Saved object [alert/nope] not found",
            },
            status=404,
        )
        with pytest.raises(NotFoundError):
            client.alerting.rule.get(id="nope")


class TestRulesUpdate:
    def test_update_minimal(self, client, mock_transport):
        client.alerting.rule.update(
            id="rule-123",
            name="Updated",
            schedule={"interval": "5m"},
        )

        method, target, body, _ = _call(mock_transport)
        assert method == "PUT"
        assert target == "/api/alerting/rule/rule-123"
        assert body == {"name": "Updated", "schedule": {"interval": "5m"}}

    def test_update_with_all_options(self, client, mock_transport):
        client.alerting.rule.update(
            id="rule-123",
            name="Rule",
            schedule={"interval": "1m"},
            params={"q": 1},
            actions=[{"id": "a1"}],
            tags=["urgent"],
            notify_when="onActiveAlert",
            throttle="5m",
            alert_delay={"active": 2},
            flapping={"look_back_window": 5, "status_change_threshold": 2},
            artifacts={"investigation_guide": {"blob": "x"}},
        )

        _, _, body, _ = _call(mock_transport)
        assert body["params"] == {"q": 1}
        assert body["alert_delay"] == {"active": 2}
        assert body["flapping"] == {
            "look_back_window": 5,
            "status_change_threshold": 2,
        }
        assert body["artifacts"] == {"investigation_guide": {"blob": "x"}}
        assert "enabled" not in body
        assert "rule_type_id" not in body

    def test_update_missing_id_raises(self, client):
        with pytest.raises(ValueError, match="id"):
            client.alerting.rule.update(id="", name="x", schedule={})


class TestRulesDelete:
    def test_delete(self, client, mock_transport):
        client.alerting.rule.delete(id="rule-del")

        method, target, _, headers = _call(mock_transport)
        assert method == "DELETE"
        assert target == "/api/alerting/rule/rule-del"
        assert headers["kbn-xsrf"] == "true"

    def test_delete_missing_id_raises(self, client):
        with pytest.raises(ValueError, match="id"):
            client.alerting.rule.delete(id="")


class TestRulesFind:
    def test_find_bare_sends_no_params(self, client, mock_transport):
        client.alerting.rule.find()

        method, target, _, _ = _call(mock_transport)
        assert method == "GET"
        assert target == "/api/alerting/rules/_find"
        assert "?" not in target

    def test_find_with_pagination_and_sort(self, client, mock_transport):
        client.alerting.rule.find(
            search="cpu", page=2, per_page=50, sort_field="name", sort_order="desc"
        )

        _, target, _, _ = _call(mock_transport)
        path, _, query = target.partition("?")
        assert path == "/api/alerting/rules/_find"
        assert "search=cpu" in query
        assert "page=2" in query
        assert "per_page=50" in query
        assert "sort_field=name" in query
        assert "sort_order=desc" in query

    def test_find_encodes_list_params_as_repeated_keys(self, client, mock_transport):
        client.alerting.rule.find(
            fields=["id", "name"],
            search_fields=["name", "tags"],
        )

        _, target, _, _ = _call(mock_transport)
        _, _, query = target.partition("?")
        assert "fields=id&fields=name" in query
        assert "search_fields=name&search_fields=tags" in query

    def test_find_encodes_filter_consumers_as_json_array(self, client, mock_transport):
        """Live 9.4.3 rejects a single repeated-key value for this param, so
        the client always sends it as a JSON array string."""
        client.alerting.rule.find(filter_consumers=["alerts"])

        _, target, _, _ = _call(mock_transport)
        _, _, query = target.partition("?")
        assert "filter_consumers=%5B%22alerts%22%5D" in query

    def test_find_encodes_has_reference_as_json(self, client, mock_transport):
        client.alerting.rule.find(has_reference={"type": "tag", "id": "tag-1"})

        _, target, _, _ = _call(mock_transport)
        _, _, query = target.partition("?")
        assert (
            "has_reference=%7B%22type%22%3A%22tag%22%2C%22id%22%3A%22tag-1%22%7D"
            in query
        )

    def test_find_with_filter_and_operator(self, client, mock_transport):
        client.alerting.rule.find(
            filter="alert.attributes.tags:production",
            default_search_operator="AND",
        )

        _, target, _, _ = _call(mock_transport)
        _, _, query = target.partition("?")
        assert "filter=alert.attributes.tags%3Aproduction" in query
        assert "default_search_operator=AND" in query

    def test_find_in_space(self, client, mock_transport):
        client.alerting.rule.find(space_id="analytics", validate_spaces=False)

        _, target, _, _ = _call(mock_transport)
        assert target == "/s/analytics/api/alerting/rules/_find"


class TestRuleLifecycle:
    def test_enable(self, client, mock_transport):
        client.alerting.rule.enable(id="r1")

        method, target, body, headers = _call(mock_transport)
        assert (method, target) == ("POST", "/api/alerting/rule/r1/_enable")
        assert body is None
        assert headers["kbn-xsrf"] == "true"

    def test_disable_without_body(self, client, mock_transport):
        client.alerting.rule.disable(id="r1")

        method, target, body, _ = _call(mock_transport)
        assert (method, target) == ("POST", "/api/alerting/rule/r1/_disable")
        assert body is None

    def test_disable_with_untrack(self, client, mock_transport):
        client.alerting.rule.disable(id="r1", untrack=True)

        _, _, body, _ = _call(mock_transport)
        assert body == {"untrack": True}

    def test_mute_all(self, client, mock_transport):
        client.alerting.rule.mute_all(id="r1")

        method, target, _, _ = _call(mock_transport)
        assert (method, target) == ("POST", "/api/alerting/rule/r1/_mute_all")

    def test_unmute_all(self, client, mock_transport):
        client.alerting.rule.unmute_all(id="r1")

        method, target, _, _ = _call(mock_transport)
        assert (method, target) == ("POST", "/api/alerting/rule/r1/_unmute_all")

    def test_update_api_key(self, client, mock_transport):
        client.alerting.rule.update_api_key(id="r1")

        method, target, _, _ = _call(mock_transport)
        assert (method, target) == ("POST", "/api/alerting/rule/r1/_update_api_key")

    @pytest.mark.parametrize(
        "method_name",
        ["enable", "disable", "mute_all", "unmute_all", "update_api_key"],
    )
    def test_lifecycle_missing_id_raises(self, client, method_name):
        with pytest.raises(ValueError, match="id"):
            getattr(client.alerting.rule, method_name)(id="")


class TestSnooze:
    def test_snooze(self, client, mock_transport):
        schedule = {"custom": {"duration": "1h", "start": "2026-01-01T00:00:00.000Z"}}
        client.alerting.rule.snooze(id="r1", schedule=schedule)

        method, target, body, _ = _call(mock_transport)
        assert (method, target) == ("POST", "/api/alerting/rule/r1/snooze_schedule")
        assert body == {"schedule": schedule}

    def test_snooze_missing_schedule_raises(self, client):
        with pytest.raises(ValueError, match="schedule"):
            client.alerting.rule.snooze(id="r1", schedule=None)  # type: ignore[arg-type]

    def test_unsnooze(self, client, mock_transport):
        client.alerting.rule.unsnooze(rule_id="r1", schedule_id="sched-1")

        method, target, _, _ = _call(mock_transport)
        assert (method, target) == (
            "DELETE",
            "/api/alerting/rule/r1/snooze_schedule/sched-1",
        )

    def test_unsnooze_missing_schedule_id_raises(self, client):
        with pytest.raises(ValueError, match="schedule_id"):
            client.alerting.rule.unsnooze(rule_id="r1", schedule_id="")


class TestMuteAlert:
    def test_mute_alert(self, client, mock_transport):
        client.alerting.rule.mute_alert(rule_id="r1", alert_id="server 1")

        method, target, _, _ = _call(mock_transport)
        assert (method, target) == (
            "POST",
            "/api/alerting/rule/r1/alert/server%201/_mute",
        )

    def test_unmute_alert(self, client, mock_transport):
        client.alerting.rule.unmute_alert(rule_id="r1", alert_id="server-1")

        method, target, _, _ = _call(mock_transport)
        assert (method, target) == (
            "POST",
            "/api/alerting/rule/r1/alert/server-1/_unmute",
        )

    def test_mute_alert_validate_alerts_existence(self, client, mock_transport):
        client.alerting.rule.mute_alert(
            rule_id="r1", alert_id="server-1", validate_alerts_existence=False
        )

        method, target, _, _ = _call(mock_transport)
        assert method == "POST"
        assert target == (
            "/api/alerting/rule/r1/alert/server-1/_mute"
            "?validate_alerts_existence=false"
        )

    def test_mute_alert_missing_alert_id_raises(self, client):
        with pytest.raises(ValueError, match="alert_id"):
            client.alerting.rule.mute_alert(rule_id="r1", alert_id="")


class TestBackfill:
    def test_schedule_sends_list_body(self, client, mock_transport):
        backfills = [
            {
                "rule_id": "r1",
                "ranges": [
                    {
                        "start": "2026-01-01T00:00:00.000Z",
                        "end": "2026-01-01T12:00:00.000Z",
                    }
                ],
                "run_actions": False,
            }
        ]
        client.alerting.backfill.schedule(backfills=backfills)

        method, target, body, _ = _call(mock_transport)
        assert (method, target) == ("POST", "/api/alerting/rules/backfill/_schedule")
        assert body == backfills

    def test_schedule_missing_backfills_raises(self, client):
        with pytest.raises(ValueError, match="backfills"):
            client.alerting.backfill.schedule(backfills=[])

    def test_find_bare(self, client, mock_transport):
        client.alerting.backfill.find()

        method, target, body, _ = _call(mock_transport)
        assert (method, target) == ("POST", "/api/alerting/rules/backfill/_find")
        assert body is None

    def test_find_with_params(self, client, mock_transport):
        client.alerting.backfill.find(
            rule_ids="r1,r2",
            start="2026-01-01T00:00:00.000Z",
            end="2026-01-02T00:00:00.000Z",
            page=1,
            per_page=5,
            sort_field="createdAt",
            sort_order="desc",
            initiator="user",
        )

        _, target, _, _ = _call(mock_transport)
        path, _, query = target.partition("?")
        assert path == "/api/alerting/rules/backfill/_find"
        assert "rule_ids=r1%2Cr2" in query
        assert "start=2026-01-01T00%3A00%3A00.000Z" in query
        assert "end=2026-01-02T00%3A00%3A00.000Z" in query
        assert "sort_field=createdAt" in query
        assert "sort_order=desc" in query
        assert "initiator=user" in query

    def test_get(self, client, mock_transport):
        client.alerting.backfill.get(id="bf-1")

        method, target, _, _ = _call(mock_transport)
        assert (method, target) == ("GET", "/api/alerting/rules/backfill/bf-1")

    def test_delete(self, client, mock_transport):
        client.alerting.backfill.delete(id="bf-1")

        method, target, _, _ = _call(mock_transport)
        assert (method, target) == ("DELETE", "/api/alerting/rules/backfill/bf-1")

    @pytest.mark.parametrize("method_name", ["get", "delete"])
    def test_missing_id_raises(self, client, method_name):
        with pytest.raises(ValueError, match="id"):
            getattr(client.alerting.backfill, method_name)(id="")


class TestAlertingClientTopLevel:
    def test_health(self, client, mock_transport):
        client.alerting.health()

        method, target, _, _ = _call(mock_transport)
        assert (method, target) == ("GET", "/api/alerting/_health")

    def test_health_in_space(self, client, mock_transport):
        client.alerting.health(space_id="ops", validate_spaces=False)

        _, target, _, _ = _call(mock_transport)
        assert target == "/s/ops/api/alerting/_health"

    def test_rule_types(self, client, mock_transport):
        client.alerting.rule_types()

        method, target, _, _ = _call(mock_transport)
        assert (method, target) == ("GET", "/api/alerting/rule_types")

    def test_sub_client_properties(self, client):
        alerting = client.alerting
        assert isinstance(alerting, AlertingClient)
        assert isinstance(alerting.rule, RulesClient)
        assert isinstance(alerting.backfill, BackfillClient)
        assert alerting.rule is alerting.rule
        assert alerting.backfill is alerting.backfill
