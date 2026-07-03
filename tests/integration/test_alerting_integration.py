"""Integration tests for the Alerting API client against a live Kibana 9.4.3.

Exercises rule CRUD and lifecycle (enable/disable/mute/snooze/API key),
find with 9.4.3 query params, framework health / rule types, and the
backfill endpoints, using an ``.es-query`` rule over a tiny throwaway
Elasticsearch index. All created resources are prefixed ``kbnpy-alerting-``
and cleaned up.
"""

import base64
import json
import os
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta

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

ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")


def _es_request(method: str, path: str, body: dict | None = None) -> None:
    """Perform a raw request against Elasticsearch with basic auth."""
    _, basic_auth, _ = get_integration_test_config()
    if basic_auth is None:
        basic_auth = ("elastic", "kibana-py-es-dev")
    token = base64.b64encode(f"{basic_auth[0]}:{basic_auth[1]}".encode()).decode()
    request = urllib.request.Request(
        f"{ES_URL}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        response.read()


@pytest.fixture(scope="module")
def es_index():
    """Create a tiny throwaway ES index backing the .es-query rules."""
    index = f"kbnpy-alerting-idx-{uuid.uuid4().hex[:8]}"
    _es_request(
        "PUT",
        f"/{index}",
        {"mappings": {"properties": {"@timestamp": {"type": "date"}}}},
    )
    _es_request(
        "POST",
        f"/{index}/_doc?refresh=true",
        {"@timestamp": "2026-01-01T00:00:00.000Z"},
    )
    yield index
    try:
        _es_request("DELETE", f"/{index}")
    except Exception:
        pass


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
def created_rules(kibana_client):
    """Track rules created during tests for automatic cleanup."""
    rule_ids: list[str] = []
    yield rule_ids
    for rule_id in rule_ids:
        try:
            kibana_client.alerting.rule.delete(id=rule_id)
        except Exception:
            pass


def _es_query_rule_params(index: str) -> dict:
    """Params for a minimal .es-query rule over the given index."""
    return {
        "searchType": "esQuery",
        "esQuery": '{"query":{"match_all":{}}}',
        "index": [index],
        "timeField": "@timestamp",
        "size": 1,
        "threshold": [0],
        "thresholdComparator": ">",
        "timeWindowSize": 5,
        "timeWindowUnit": "m",
    }


def _create_rule(kibana_client, created_rules, es_index, **overrides):
    """Create a disabled kbnpy-prefixed .es-query rule and track it."""
    rule_id = f"kbnpy-alerting-rule-{uuid.uuid4().hex[:8]}"
    kwargs = dict(
        id=rule_id,
        name=f"{rule_id} name",
        consumer="alerts",
        rule_type_id=".es-query",
        schedule={"interval": "1m"},
        params=_es_query_rule_params(es_index),
        enabled=False,
        tags=["kbnpy-alerting"],
    )
    kwargs.update(overrides)
    response = kibana_client.alerting.rule.create(**kwargs)
    created_rules.append(response.body["id"])
    return response


class TestAlertingFramework:
    """Framework-level endpoints."""

    def test_health(self, kibana_client):
        response = kibana_client.alerting.health()
        assert response.meta.status == 200
        body = response.body
        assert "is_sufficiently_secure" in body
        assert "has_permanent_encryption_key" in body
        assert "alerting_framework_health" in body
        assert "execution_health" in body["alerting_framework_health"]

    def test_rule_types(self, kibana_client):
        response = kibana_client.alerting.rule_types()
        assert response.meta.status == 200
        types = response.body
        assert isinstance(types, list)
        ids = [t["id"] for t in types]
        assert ".es-query" in ids
        assert ".index-threshold" in ids


class TestRuleCrud:
    """Rule create/get/update/delete/find round-trips."""

    def test_create_with_custom_id_get_update_delete(
        self, kibana_client, created_rules, es_index
    ):
        response = _create_rule(
            kibana_client,
            created_rules,
            es_index,
            alert_delay={"active": 2},
        )
        rule = response.body
        rule_id = rule["id"]
        assert rule_id.startswith("kbnpy-alerting-rule-")
        assert rule["enabled"] is False
        assert rule["alert_delay"] == {"active": 2}

        # Get
        got = kibana_client.alerting.rule.get(id=rule_id)
        assert got.body["id"] == rule_id
        assert got.body["rule_type_id"] == ".es-query"

        # Update (name + params + alert_delay)
        updated = kibana_client.alerting.rule.update(
            id=rule_id,
            name=f"{rule_id} renamed",
            schedule={"interval": "2m"},
            params=_es_query_rule_params(es_index),
            tags=["kbnpy-alerting", "updated"],
            alert_delay={"active": 3},
        )
        assert updated.body["name"] == f"{rule_id} renamed"
        assert updated.body["schedule"] == {"interval": "2m"}
        assert updated.body["alert_delay"] == {"active": 3}

        # Delete and verify
        kibana_client.alerting.rule.delete(id=rule_id)
        created_rules.remove(rule_id)
        with pytest.raises(NotFoundError):
            kibana_client.alerting.rule.get(id=rule_id)

    def test_find_bare_no_arguments(self, kibana_client):
        """Regression: a bare find() must not send sort_order (406 in 9.4.3)."""
        response = kibana_client.alerting.rule.find()
        assert response.meta.status == 200
        body = response.body
        assert "total" in body
        assert "data" in body

    def test_find_with_query_params(self, kibana_client, created_rules, es_index):
        response = _create_rule(kibana_client, created_rules, es_index)
        rule_id = response.body["id"]
        rule_name = response.body["name"]

        # search + sort + fields (repeated keys) + search_fields + operator
        found = kibana_client.alerting.rule.find(
            search=rule_name,
            search_fields=["name"],
            default_search_operator="AND",
            sort_field="name",
            sort_order="asc",
            fields=["id", "name"],
            per_page=100,
        )
        assert found.body["total"] >= 1
        match = [r for r in found.body["data"] if r["id"] == rule_id]
        assert match, f"rule {rule_id} not in find results"
        # fields projection applied (only requested attributes + defaults)
        assert match[0]["name"] == rule_name
        assert "schedule" not in match[0]

        # filter + filter_consumers
        filtered = kibana_client.alerting.rule.find(
            filter="alert.attributes.tags:kbnpy-alerting",
            filter_consumers=["alerts"],
            per_page=100,
        )
        assert rule_id in [r["id"] for r in filtered.body["data"]]

        # has_reference (JSON-object query param): no rule references this
        # saved object, so the result must be empty but the call valid.
        refs = kibana_client.alerting.rule.find(
            has_reference={"type": "tag", "id": "kbnpy-alerting-nonexistent"},
        )
        assert refs.meta.status == 200
        assert refs.body["total"] == 0


class TestRuleLifecycle:
    """Enable/disable, mute/unmute, snooze/unsnooze, API key rotation."""

    def test_full_lifecycle(self, kibana_client, created_rules, es_index):
        response = _create_rule(kibana_client, created_rules, es_index)
        rule_id = response.body["id"]

        # Enable
        kibana_client.alerting.rule.enable(id=rule_id)
        assert kibana_client.alerting.rule.get(id=rule_id).body["enabled"] is True

        # Mute all / unmute all
        kibana_client.alerting.rule.mute_all(id=rule_id)
        assert kibana_client.alerting.rule.get(id=rule_id).body["mute_all"] is True
        kibana_client.alerting.rule.unmute_all(id=rule_id)
        assert kibana_client.alerting.rule.get(id=rule_id).body["mute_all"] is False

        # Snooze / unsnooze
        snoozed = kibana_client.alerting.rule.snooze(
            id=rule_id,
            schedule={
                "custom": {
                    "duration": "1h",
                    "start": "2027-01-01T00:00:00.000Z",
                }
            },
        )
        schedule_id = snoozed.body["schedule"]["id"]
        assert schedule_id
        kibana_client.alerting.rule.unsnooze(rule_id=rule_id, schedule_id=schedule_id)

        # Update API key
        kibana_client.alerting.rule.update_api_key(id=rule_id)

        # Disable with untrack body
        kibana_client.alerting.rule.disable(id=rule_id, untrack=True)
        assert kibana_client.alerting.rule.get(id=rule_id).body["enabled"] is False

    def test_mute_and_unmute_alert(self, kibana_client, created_rules, es_index):
        """Exercise the per-alert mute/unmute endpoints.

        Live 9.4.3 behavior: muting requires the alert instance to exist
        (404 otherwise), while unmuting an unknown alert succeeds (204).
        """
        response = _create_rule(kibana_client, created_rules, es_index)
        rule_id = response.body["id"]

        with pytest.raises(NotFoundError, match="does not exist"):
            kibana_client.alerting.rule.mute_alert(
                rule_id=rule_id, alert_id="kbnpy-alerting-nonexistent-alert"
            )

        # validate_alerts_existence=False mutes an alert that has not fired.
        muted = kibana_client.alerting.rule.mute_alert(
            rule_id=rule_id,
            alert_id="kbnpy-alerting-nonexistent-alert",
            validate_alerts_existence=False,
        )
        assert muted.meta.status == 204

        unmuted = kibana_client.alerting.rule.unmute_alert(
            rule_id=rule_id, alert_id="kbnpy-alerting-nonexistent-alert"
        )
        assert unmuted.meta.status == 204


class TestBackfill:
    """Backfill endpoints.

    Live 9.4.3 note: backfills are only supported for specific rule types
    (e.g. detection rules); scheduling one for an ``.es-query`` rule returns
    HTTP 200 with a per-item error, which still exercises the endpoint.
    """

    def test_schedule_reports_unsupported_rule_type(
        self, kibana_client, created_rules, es_index
    ):
        response = _create_rule(kibana_client, created_rules, es_index)
        rule_id = response.body["id"]
        kibana_client.alerting.rule.enable(id=rule_id)

        # Backfills cannot look back more than 90 days: use yesterday.
        now = datetime.now(UTC)
        fmt = "%Y-%m-%dT%H:%M:%S.000Z"
        scheduled = kibana_client.alerting.backfill.schedule(
            backfills=[
                {
                    "rule_id": rule_id,
                    "ranges": [
                        {
                            "start": (now - timedelta(days=1)).strftime(fmt),
                            "end": (now - timedelta(hours=23)).strftime(fmt),
                        }
                    ],
                }
            ]
        )
        assert scheduled.meta.status == 200
        results = scheduled.body
        assert isinstance(results, list) and len(results) == 1
        assert "error" in results[0]
        assert "not supported" in results[0]["error"]["message"]

        kibana_client.alerting.rule.disable(id=rule_id)

    def test_find_get_delete(self, kibana_client):
        found = kibana_client.alerting.backfill.find(
            page=1, per_page=5, sort_field="createdAt", sort_order="desc"
        )
        assert found.meta.status == 200
        assert "data" in found.body
        assert "total" in found.body

        with pytest.raises(NotFoundError):
            kibana_client.alerting.backfill.get(id="kbnpy-alerting-no-such-backfill")

        with pytest.raises(NotFoundError):
            kibana_client.alerting.backfill.delete(id="kbnpy-alerting-no-such-backfill")


class TestAsyncAlerting:
    """Async client round-trip against the live stack."""

    async def test_async_rule_round_trip(self, es_index):
        client = create_test_async_kibana_client(auth_method="auto")
        rule_id = f"kbnpy-alerting-async-{uuid.uuid4().hex[:8]}"
        try:
            health = await client.alerting.health()
            assert "alerting_framework_health" in health.body

            types = await client.alerting.rule_types()
            assert ".es-query" in [t["id"] for t in types.body]

            created = await client.alerting.rule.create(
                id=rule_id,
                name=f"{rule_id} name",
                consumer="alerts",
                rule_type_id=".es-query",
                schedule={"interval": "1m"},
                params=_es_query_rule_params(es_index),
                enabled=False,
                tags=["kbnpy-alerting"],
            )
            assert created.body["id"] == rule_id

            got = await client.alerting.rule.get(id=rule_id)
            assert got.body["name"] == f"{rule_id} name"

            found = await client.alerting.rule.find(
                search=rule_id, search_fields=["name"], per_page=100
            )
            assert rule_id in [r["id"] for r in found.body["data"]]

            backfills = await client.alerting.backfill.find(per_page=1)
            assert "data" in backfills.body
        finally:
            try:
                await client.alerting.rule.delete(id=rule_id)
            except Exception:
                pass
            await client.close()

        with pytest.raises(NotFoundError):
            sync_client = create_test_kibana_client(auth_method="auto")
            try:
                sync_client.alerting.rule.get(id=rule_id)
            finally:
                sync_client.close()
