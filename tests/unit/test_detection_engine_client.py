"""Unit tests for DetectionEngineClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.detection_engine import DetectionEngineClient


def _rule_body() -> dict:
    """A trimmed Kibana 9.4.3 detection-rule response body."""
    return {
        "id": "07f4242f-bc60-443d-a3d1-6b81611509ba",
        "rule_id": "kbnpy-rule",
        "name": "kbnpy rule",
        "description": "test",
        "type": "query",
        "query": "user.name: kbnpy",
        "language": "kuery",
        "severity": "low",
        "risk_score": 21,
        "enabled": False,
        "interval": "5m",
        "from": "now-6m",
        "to": "now",
        "tags": [],
        "immutable": False,
        "rule_source": {"type": "internal"},
        "version": 1,
        "revision": 0,
    }


def _update_by_query_body() -> dict:
    """Kibana 9.4.3 signals status/tags/assignees response body."""
    return {
        "took": 1,
        "timed_out": False,
        "total": 0,
        "updated": 0,
        "deleted": 0,
        "batches": 0,
        "version_conflicts": 0,
        "noops": 0,
        "retries": {"bulk": 0, "search": 0},
        "throttled_millis": 0,
        "requests_per_second": -1,
        "throttled_until_millis": 0,
        "failures": [],
    }


@pytest.fixture
def client_and_transport(mock_transport):
    """A Kibana client wired to a mock transport returning 200 {}."""
    mock_transport.perform_request.return_value = ObjectApiResponse(
        body={},
        meta=Mock(status=200, headers={}),
    )
    return Kibana(_transport=mock_transport), mock_transport


def _call_kwargs(transport):
    return transport.perform_request.call_args[1]


class TestDetectionEngineClientInitialization:
    """Test DetectionEngineClient initialization and wiring."""

    def test_initialization(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        detection_engine_client = DetectionEngineClient(client)
        assert detection_engine_client._client is client

    def test_property_returns_detection_engine_client(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.detection_engine, DetectionEngineClient)

    def test_property_caching(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        assert client.detection_engine is client.detection_engine


class TestPrivilegesAndIndex:
    """Tests for privileges and alerts-index methods."""

    def test_get_privileges(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.get_privileges()

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/detection_engine/privileges"
        assert kwargs["headers"] == {"accept": "application/json"}

    def test_create_alerts_index(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.create_alerts_index()

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/detection_engine/index"

    def test_get_alerts_index(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.get_alerts_index()

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/detection_engine/index"

    def test_delete_alerts_index(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.delete_alerts_index()

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "DELETE"
        assert kwargs["target"] == "/api/detection_engine/index"

    def test_get_alerts_index_space_scoped(self, client_and_transport):
        """space_id must build a /s/<space>/api/... target."""
        client, transport = client_and_transport
        client.detection_engine.get_alerts_index(
            space_id="secops", validate_spaces=False
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["target"] == "/s/secops/api/detection_engine/index"


class TestRulesCrud:
    """Tests for rule create/get/update/patch/delete/find."""

    def test_create_rule_body(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.create_rule(
            type="query",
            name="kbnpy rule",
            description="test",
            severity="low",
            risk_score=21,
            rule_id="kbnpy-rule",
            query="user.name: kbnpy",
            index=["logs-*"],
            interval="10m",
            from_="now-20m",
            enabled=False,
            tags=["kbnpy"],
            fields={"max_signals": 50},
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/detection_engine/rules"
        assert kwargs["body"] == {
            "type": "query",
            "name": "kbnpy rule",
            "description": "test",
            "severity": "low",
            "risk_score": 21,
            "rule_id": "kbnpy-rule",
            "query": "user.name: kbnpy",
            "index": ["logs-*"],
            "interval": "10m",
            "from": "now-20m",
            "enabled": False,
            "tags": ["kbnpy"],
            "max_signals": 50,
        }

    def test_create_rule_threat_match_fields(self, client_and_transport):
        """Type-specific threat_match fields are passed through."""
        client, transport = client_and_transport
        client.detection_engine.create_rule(
            type="threat_match",
            name="kbnpy ti rule",
            description="test",
            severity="low",
            risk_score=21,
            query="*:*",
            threat_index=["ti-*"],
            threat_query="*:*",
            threat_mapping=[
                {
                    "entries": [
                        {
                            "field": "host.name",
                            "type": "mapping",
                            "value": "host.name",
                        }
                    ]
                }
            ],
        )

        body = _call_kwargs(transport)["body"]
        assert body["threat_index"] == ["ti-*"]
        assert body["threat_query"] == "*:*"
        assert body["threat_mapping"][0]["entries"][0]["field"] == "host.name"

    def test_get_rule_by_id(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.get_rule(id="07f4242f")

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/detection_engine/rules?id=07f4242f"

    def test_get_rule_by_rule_id(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.get_rule(rule_id="kbnpy-rule")

        kwargs = _call_kwargs(transport)
        assert kwargs["target"] == "/api/detection_engine/rules?rule_id=kbnpy-rule"

    def test_get_rule_requires_exactly_one_selector(self, client_and_transport):
        client, _ = client_and_transport
        with pytest.raises(ValueError):
            client.detection_engine.get_rule()
        with pytest.raises(ValueError):
            client.detection_engine.get_rule(id="a", rule_id="b")

    def test_update_rule(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.update_rule(
            rule_id="kbnpy-rule",
            type="query",
            name="kbnpy rule v2",
            description="updated",
            severity="medium",
            risk_score=47,
            query="user.name: kbnpy",
            enabled=True,
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "PUT"
        assert kwargs["target"] == "/api/detection_engine/rules"
        assert kwargs["body"]["rule_id"] == "kbnpy-rule"
        assert kwargs["body"]["name"] == "kbnpy rule v2"
        assert kwargs["body"]["enabled"] is True
        assert "id" not in kwargs["body"]

    def test_update_rule_requires_selector(self, client_and_transport):
        client, _ = client_and_transport
        with pytest.raises(ValueError):
            client.detection_engine.update_rule(
                type="query",
                name="n",
                description="d",
                severity="low",
                risk_score=21,
            )

    def test_patch_rule(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.patch_rule(
            id="07f4242f",
            tags=["kbnpy", "triage"],
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "PATCH"
        assert kwargs["target"] == "/api/detection_engine/rules"
        assert kwargs["body"] == {"id": "07f4242f", "tags": ["kbnpy", "triage"]}

    def test_patch_rule_requires_selector(self, client_and_transport):
        client, _ = client_and_transport
        with pytest.raises(ValueError):
            client.detection_engine.patch_rule(tags=["x"])

    def test_delete_rule_by_rule_id(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.delete_rule(rule_id="kbnpy-rule")

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "DELETE"
        assert kwargs["target"] == "/api/detection_engine/rules?rule_id=kbnpy-rule"

    def test_delete_rule_requires_exactly_one_selector(self, client_and_transport):
        client, _ = client_and_transport
        with pytest.raises(ValueError):
            client.detection_engine.delete_rule()
        with pytest.raises(ValueError):
            client.detection_engine.delete_rule(id="a", rule_id="b")

    def test_find_rules_param_encoding(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.find_rules(
            filter="alert.attributes.name:kbnpy",
            sort_field="name",
            sort_order="asc",
            page=2,
            per_page=5,
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == (
            "/api/detection_engine/rules/_find"
            "?filter=alert.attributes.name%3Akbnpy"
            "&sort_field=name&sort_order=asc&page=2&per_page=5"
        )

    def test_find_rules_list_params_repeat(self, client_and_transport):
        """Array query params are encoded as repeated keys."""
        client, transport = client_and_transport
        client.detection_engine.find_rules(
            fields=["name", "enabled"],
            gap_fill_statuses=["unfilled", "error"],
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["target"] == (
            "/api/detection_engine/rules/_find"
            "?fields=name&fields=enabled"
            "&gap_fill_statuses=unfilled&gap_fill_statuses=error"
        )

    def test_find_rules_no_params(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.find_rules()

        kwargs = _call_kwargs(transport)
        assert kwargs["target"] == "/api/detection_engine/rules/_find"

    def test_find_rules_space_scoped(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.find_rules(
            per_page=1, space_id="secops", validate_spaces=False
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["target"] == (
            "/s/secops/api/detection_engine/rules/_find?per_page=1"
        )


class TestRulesBulkExportImport:
    """Tests for bulk actions, export/import, prepackaged and preview."""

    def test_bulk_action_rules_edit(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.bulk_action_rules(
            action="edit",
            ids=["id-1", "id-2"],
            edit=[{"type": "add_tags", "value": ["kbnpy"]}],
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/detection_engine/rules/_bulk_action"
        assert kwargs["body"] == {
            "action": "edit",
            "ids": ["id-1", "id-2"],
            "edit": [{"type": "add_tags", "value": ["kbnpy"]}],
        }

    def test_bulk_action_rules_dry_run_query_param(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.bulk_action_rules(
            action="delete",
            query='alert.attributes.tags: "kbnpy"',
            dry_run=True,
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["target"] == (
            "/api/detection_engine/rules/_bulk_action?dry_run=true"
        )
        assert kwargs["body"] == {
            "action": "delete",
            "query": 'alert.attributes.tags: "kbnpy"',
        }

    def test_bulk_action_rules_run_window(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.bulk_action_rules(
            action="run",
            ids=["id-1"],
            run={
                "start_date": "2026-07-05T00:00:00.000Z",
                "end_date": "2026-07-05T01:00:00.000Z",
            },
        )

        body = _call_kwargs(transport)["body"]
        assert body["action"] == "run"
        assert body["run"]["start_date"] == "2026-07-05T00:00:00.000Z"

    def test_export_rules(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.export_rules(
            objects=[{"rule_id": "kbnpy-rule"}],
            exclude_export_details=True,
            file_name="kbnpy.ndjson",
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == (
            "/api/detection_engine/rules/_export"
            "?exclude_export_details=true&file_name=kbnpy.ndjson"
        )
        assert kwargs["headers"]["accept"] == "application/ndjson"
        assert kwargs["body"] == {"objects": [{"rule_id": "kbnpy-rule"}]}

    def test_export_rules_all_sends_no_body(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.export_rules()

        kwargs = _call_kwargs(transport)
        assert kwargs["target"] == "/api/detection_engine/rules/_export"
        assert "body" not in kwargs

    def test_import_rules_multipart(self, client_and_transport):
        client, transport = client_and_transport
        rule = {"rule_id": "kbnpy-rule", "name": "kbnpy rule", "type": "query"}
        client.detection_engine.import_rules(
            file=[rule],
            overwrite=True,
            overwrite_exceptions=False,
            as_new_list=True,
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == (
            "/api/detection_engine/rules/_import"
            "?overwrite=true&overwrite_exceptions=false&as_new_list=true"
        )
        content_type = kwargs["headers"]["content-type"]
        assert content_type.startswith("multipart/form-data; boundary=")
        boundary = content_type.split("boundary=", 1)[1]
        body = kwargs["body"]
        assert isinstance(body, bytes)
        assert f"--{boundary}\r\n".encode() in body
        assert b'name="file"; filename="import.ndjson"' in body
        assert b'"rule_id": "kbnpy-rule"' in body
        assert f"--{boundary}--\r\n".encode() in body

    def test_import_rules_accepts_raw_bytes(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.import_rules(file=b'{"rule_id":"kbnpy-rule"}\n')

        body = _call_kwargs(transport)["body"]
        assert b'{"rule_id":"kbnpy-rule"}' in body

    def test_import_rules_empty_file_raises(self, client_and_transport):
        client, _ = client_and_transport
        with pytest.raises(ValueError):
            client.detection_engine.import_rules(file=b"")

    def test_get_prepackaged_rules_status(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.get_prepackaged_rules_status()

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == ("/api/detection_engine/rules/prepackaged/_status")

    def test_install_prepackaged_rules(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.install_prepackaged_rules()

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "PUT"
        assert kwargs["target"] == "/api/detection_engine/rules/prepackaged"

    def test_preview_rule(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.preview_rule(
            type="query",
            name="kbnpy preview",
            description="test",
            severity="low",
            risk_score=21,
            query="user.name: kbnpy",
            index=["logs-*"],
            invocation_count=2,
            timeframe_end="2026-07-06T12:00:00.000Z",
            enable_logged_requests=True,
            from_="now-6h",
            interval="1h",
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == (
            "/api/detection_engine/rules/preview?enable_logged_requests=true"
        )
        body = kwargs["body"]
        assert body["invocationCount"] == 2
        assert body["timeframeEnd"] == "2026-07-06T12:00:00.000Z"
        assert body["from"] == "now-6h"
        assert "invocation_count" not in body

    def test_get_tags(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.get_tags()

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/detection_engine/tags"


class TestSignals:
    """Tests for the detection alerts (signals) methods."""

    def test_search_alerts_body(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.search_alerts(
            query={"match_all": {}},
            aggs={"by_rule": {"terms": {"field": "kibana.alert.rule.uuid"}}},
            size=5,
            sort={"@timestamp": {"order": "desc"}},
            source=False,
            track_total_hits=True,
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/detection_engine/signals/search"
        assert kwargs["body"] == {
            "query": {"match_all": {}},
            "aggs": {"by_rule": {"terms": {"field": "kibana.alert.rule.uuid"}}},
            "size": 5,
            "sort": {"@timestamp": {"order": "desc"}},
            "_source": False,
            "track_total_hits": True,
        }

    def test_set_alert_status_by_ids(self, mock_transport):
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=_update_by_query_body(),
            meta=Mock(status=200, headers={}),
        )
        client = Kibana(_transport=mock_transport)
        result = client.detection_engine.set_alert_status(
            status="closed",
            signal_ids=["alert-1"],
            reason="false_positive",
        )

        assert result.body["updated"] == 0
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/detection_engine/signals/status"
        assert kwargs["body"] == {
            "status": "closed",
            "signal_ids": ["alert-1"],
            "reason": "false_positive",
        }

    def test_set_alert_status_by_query(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.set_alert_status(
            status="open",
            query={"bool": {"filter": [{"match_all": {}}]}},
            conflicts="proceed",
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["body"] == {
            "status": "open",
            "query": {"bool": {"filter": [{"match_all": {}}]}},
            "conflicts": "proceed",
        }

    def test_set_alert_status_requires_exactly_one_selector(self, client_and_transport):
        client, _ = client_and_transport
        with pytest.raises(ValueError):
            client.detection_engine.set_alert_status(status="open")
        with pytest.raises(ValueError):
            client.detection_engine.set_alert_status(
                status="open", signal_ids=["a"], query={"match_all": {}}
            )

    def test_set_alert_tags(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.set_alert_tags(
            ids=["alert-1"],
            tags_to_add=["triage"],
            tags_to_remove=["stale"],
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/detection_engine/signals/tags"
        assert kwargs["body"] == {
            "ids": ["alert-1"],
            "tags": {"tags_to_add": ["triage"], "tags_to_remove": ["stale"]},
        }

    def test_set_alert_assignees(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.set_alert_assignees(
            ids=["alert-1"],
            add=["u_profile_1"],
            remove=[],
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/detection_engine/signals/assignees"
        assert kwargs["body"] == {
            "ids": ["alert-1"],
            "assignees": {"add": ["u_profile_1"], "remove": []},
        }


class TestSignalsMigrations:
    """Tests for the deprecated legacy signals migration methods."""

    def test_create_alerts_migration(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.create_alerts_migration(
            index=[".siem-signals-default-000001"],
            requests_per_second=10,
            size=100,
            slices=2,
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/detection_engine/signals/migration"
        assert kwargs["body"] == {
            "index": [".siem-signals-default-000001"],
            "requests_per_second": 10,
            "size": 100,
            "slices": 2,
        }

    def test_get_alerts_migration_status(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.get_alerts_migration_status(from_="now-30d")

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == (
            "/api/detection_engine/signals/migration_status?from=now-30d"
        )

    def test_finalize_alerts_migration(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.finalize_alerts_migration(
            migration_ids=["mig-1", "mig-2"]
        )

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == ("/api/detection_engine/signals/finalize_migration")
        assert kwargs["body"] == {"migration_ids": ["mig-1", "mig-2"]}

    def test_delete_alerts_migration(self, client_and_transport):
        client, transport = client_and_transport
        client.detection_engine.delete_alerts_migration(migration_ids=["mig-1"])

        kwargs = _call_kwargs(transport)
        assert kwargs["method"] == "DELETE"
        assert kwargs["target"] == "/api/detection_engine/signals/migration"
        assert kwargs["body"] == {"migration_ids": ["mig-1"]}


class TestErrorHandling:
    """Test error mapping for the detection engine namespace."""

    def test_get_rule_not_found_error(self, mock_transport):
        from kibana.exceptions import NotFoundError

        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "message": 'rule_id: "missing" not found',
                "status_code": 404,
            },
            meta=Mock(status=404, headers={}),
        )
        client = Kibana(_transport=mock_transport)

        with pytest.raises(NotFoundError):
            client.detection_engine.get_rule(rule_id="missing")

    def test_create_rule_conflict_error(self, mock_transport):
        from kibana.exceptions import ConflictError

        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "message": 'rule_id: "kbnpy-rule" already exists',
                "status_code": 409,
            },
            meta=Mock(status=409, headers={}),
        )
        client = Kibana(_transport=mock_transport)

        with pytest.raises(ConflictError):
            client.detection_engine.create_rule(
                type="query",
                name="kbnpy rule",
                description="test",
                severity="low",
                risk_score=21,
                rule_id="kbnpy-rule",
                query="*:*",
            )

    def test_create_rule_returns_rule_body(self, mock_transport):
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=_rule_body(),
            meta=Mock(status=200, headers={}),
        )
        client = Kibana(_transport=mock_transport)
        result = client.detection_engine.create_rule(
            type="query",
            name="kbnpy rule",
            description="test",
            severity="low",
            risk_score=21,
            rule_id="kbnpy-rule",
            query="user.name: kbnpy",
        )

        assert result.body["id"] == "07f4242f-bc60-443d-a3d1-6b81611509ba"
        assert result.body["rule_id"] == "kbnpy-rule"
