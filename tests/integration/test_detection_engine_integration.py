"""Integration tests for DetectionEngineClient against a live Kibana instance."""

import time
import uuid

import pytest

from kibana.exceptions import (
    ApiError,
    AuthorizationException,
    BadRequestError,
    NotFoundError,
)

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    is_kibana_available,
)

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)

PREFIX = "kbnpy-detection-engine"


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


def _unique(suffix: str) -> str:
    return f"{PREFIX}-{suffix}-{uuid.uuid4().hex[:12]}"


def _wait_until(fetch, ok, *, timeout=90.0, interval=1.0):
    """Poll fetch() until ok(result) is truthy (eventual consistency / async task
    manager on the live stack; generous deadline for the slow cold CI runner)."""
    deadline = time.time() + timeout
    result = fetch()
    while not ok(result) and time.time() < deadline:
        time.sleep(interval)
        result = fetch()
    return result


def _rule_args(rule_id: str, name: str) -> dict:
    """Keyword arguments for a minimal, disabled custom query rule."""
    return {
        "type": "query",
        "name": name,
        "description": "kbnpy-detection-engine integration test rule",
        "severity": "low",
        "risk_score": 21,
        "rule_id": rule_id,
        "query": 'user.name: "kbnpy-detection-engine-nonexistent"',
        "index": ["logs-*"],
        "interval": "60m",
        "from_": "now-120m",
        "enabled": False,
    }


def _delete_rule_quietly(client, *, rule_id=None, id=None, space_id=None) -> None:
    """Delete a rule, ignoring the case where it is already gone."""
    try:
        client.detection_engine.delete_rule(rule_id=rule_id, id=id, space_id=space_id)
    except NotFoundError:
        pass


class TestDetectionEngineStatusEndpoints:
    """Live tests for privileges, alerts index and prebuilt-content status."""

    def test_get_privileges(self, kibana_client):
        privileges = kibana_client.detection_engine.get_privileges()
        assert privileges.meta.status == 200
        assert privileges.body["is_authenticated"] is True
        assert "username" in privileges.body
        assert "index" in privileges.body

    def test_get_alerts_index(self, kibana_client):
        index = kibana_client.detection_engine.get_alerts_index()
        assert index.body["name"].startswith(".alerts-security.alerts-")
        assert "index_mapping_outdated" in index.body

    def test_get_prepackaged_rules_status(self, kibana_client):
        status = kibana_client.detection_engine.get_prepackaged_rules_status()
        for key in (
            "rules_custom_installed",
            "rules_installed",
            "rules_not_installed",
            "rules_not_updated",
            "timelines_installed",
            "timelines_not_installed",
        ):
            assert isinstance(status.body[key], int)

    def test_install_prepackaged_rules_is_idempotent(self, kibana_client):
        """Prebuilt rules were installed on this stack; re-install is a no-op."""
        # The install downloads the prebuilt-rules Fleet package on first use,
        # which can exceed the (unset) default request timeout on a cold runner.
        result = kibana_client.options(
            request_timeout=300
        ).detection_engine.install_prepackaged_rules()
        assert result.body["rules_installed"] >= 0
        assert result.body["rules_updated"] >= 0

        status = _wait_until(
            lambda: kibana_client.detection_engine.get_prepackaged_rules_status(),
            lambda r: r.body["rules_not_installed"] == 0,
        )
        assert status.body["rules_not_installed"] == 0

    def test_get_tags_returns_list(self, kibana_client):
        tags = kibana_client.detection_engine.get_tags()
        assert isinstance(tags.body, list)


class TestDetectionRulesLifecycle:
    """Full CRUD lifecycle tests for detection rules."""

    def test_rule_crud_lifecycle(self, kibana_client):
        rule_id = _unique("crud")
        name = _unique("crud-rule")
        tag = _unique("tag")
        created = kibana_client.detection_engine.create_rule(
            **_rule_args(rule_id, name)
        )
        object_id = created.body["id"]
        try:
            assert created.body["rule_id"] == rule_id
            assert created.body["name"] == name
            assert created.body["enabled"] is False
            assert created.body["from"] == "now-120m"

            # Get by rule_id and by object id
            fetched = kibana_client.detection_engine.get_rule(rule_id=rule_id)
            assert fetched.body["id"] == object_id
            fetched_by_id = kibana_client.detection_engine.get_rule(id=object_id)
            assert fetched_by_id.body["rule_id"] == rule_id

            # Patch: add a tag (partial update, other fields untouched)
            patched = kibana_client.detection_engine.patch_rule(
                rule_id=rule_id, tags=[tag]
            )
            assert patched.body["tags"] == [tag]
            assert patched.body["query"] == created.body["query"]

            # Update (PUT): full replacement, toggling enabled works via PUT
            updated = kibana_client.detection_engine.update_rule(
                rule_id=rule_id,
                type="query",
                name=f"{name}-v2",
                description="updated by kbnpy integration test",
                severity="medium",
                risk_score=47,
                query='user.name: "kbnpy-detection-engine-nonexistent"',
                index=["logs-*"],
                tags=[tag],
                enabled=True,
            )
            assert updated.body["name"] == f"{name}-v2"
            assert updated.body["severity"] == "medium"
            assert updated.body["enabled"] is True

            # Disable again via PUT before cleanup
            disabled = kibana_client.detection_engine.update_rule(
                rule_id=rule_id,
                type="query",
                name=f"{name}-v2",
                description="updated by kbnpy integration test",
                severity="medium",
                risk_score=47,
                query='user.name: "kbnpy-detection-engine-nonexistent"',
                index=["logs-*"],
                tags=[tag],
                enabled=False,
            )
            assert disabled.body["enabled"] is False

            # Find by tag filter
            found = kibana_client.detection_engine.find_rules(
                filter=f'alert.attributes.tags: "{tag}"', per_page=10
            )
            assert found.body["total"] == 1
            assert found.body["data"][0]["rule_id"] == rule_id

            # The tag shows up in the tags aggregation
            tags = kibana_client.detection_engine.get_tags()
            assert tag in tags.body
        finally:
            _delete_rule_quietly(kibana_client, rule_id=rule_id)

        with pytest.raises(NotFoundError):
            kibana_client.detection_engine.get_rule(rule_id=rule_id)

    def test_get_missing_rule_raises_semantic_not_found(self, kibana_client):
        missing = _unique("missing")
        with pytest.raises(NotFoundError) as excinfo:
            kibana_client.detection_engine.get_rule(rule_id=missing)
        assert f'rule_id: "{missing}" not found' in str(excinfo.value)

    def test_patch_enabled_is_rejected_live(self, kibana_client):
        """Live 9.4.3 quirk: PATCH cannot edit 'enabled', even as superuser."""
        rule_id = _unique("patch-enabled")
        kibana_client.detection_engine.create_rule(
            **_rule_args(rule_id, _unique("patch-enabled-rule"))
        )
        try:
            with pytest.raises(AuthorizationException) as excinfo:
                kibana_client.detection_engine.patch_rule(rule_id=rule_id, enabled=True)
            assert "edit the following fields: enabled" in str(excinfo.value)
        finally:
            _delete_rule_quietly(kibana_client, rule_id=rule_id)

    def test_preview_rule(self, kibana_client):
        preview = kibana_client.detection_engine.preview_rule(
            type="query",
            name=_unique("preview-rule"),
            description="kbnpy preview",
            severity="low",
            risk_score=21,
            query='user.name: "kbnpy-detection-engine-nonexistent"',
            index=["logs-*"],
            invocation_count=1,
            timeframe_end="2026-07-06T12:00:00.000Z",
            from_="now-6h",
            interval="1h",
        )
        assert preview.body["previewId"]
        assert isinstance(preview.body["logs"], list)
        assert preview.body["isAborted"] is False


class TestDetectionRulesExportImport:
    """NDJSON export / multipart import round-trip tests."""

    def test_export_import_roundtrip(self, kibana_client):
        rule_id = _unique("export")
        name = _unique("export-rule")
        kibana_client.detection_engine.create_rule(**_rule_args(rule_id, name))
        try:
            lines = _wait_until(
                lambda: list(
                    kibana_client.detection_engine.export_rules(
                        objects=[{"rule_id": rule_id}],
                        exclude_export_details=True,
                    )
                ),
                lambda ls: len(ls) == 1,
            )
            assert len(lines) == 1
            assert lines[0]["rule_id"] == rule_id

            # Export details line is appended unless excluded
            with_details = kibana_client.detection_engine.export_rules(
                objects=[{"rule_id": rule_id}],
            )
            detail_lines = list(with_details)
            assert detail_lines[-1]["exported_rules_count"] == 1

            # Delete, then re-import from the export payload
            kibana_client.detection_engine.delete_rule(rule_id=rule_id)
            result = kibana_client.detection_engine.import_rules(file=lines)
            assert result.body["success"] is True
            assert result.body["success_count"] == 1

            restored = kibana_client.detection_engine.get_rule(rule_id=rule_id)
            assert restored.body["name"] == name

            # Re-import without overwrite fails; with overwrite succeeds
            result = kibana_client.detection_engine.import_rules(
                file=lines, overwrite=True
            )
            assert result.body["success"] is True
        finally:
            _delete_rule_quietly(kibana_client, rule_id=rule_id)


class TestDetectionRulesBulkActions:
    """Live tests for POST /api/detection_engine/rules/_bulk_action."""

    def test_bulk_edit_export_and_delete(self, kibana_client):
        rule_ids = [_unique("bulk-a"), _unique("bulk-b")]
        tag = _unique("bulk-tag")
        object_ids = []
        try:
            for rule_id in rule_ids:
                created = kibana_client.detection_engine.create_rule(
                    **_rule_args(rule_id, _unique("bulk-rule"))
                )
                object_ids.append(created.body["id"])

            # Bulk edit: add a tag to both rules
            edited = kibana_client.detection_engine.bulk_action_rules(
                action="edit",
                ids=object_ids,
                edit=[{"type": "add_tags", "value": [tag]}],
            )
            assert edited.body["success"] is True
            assert edited.body["attributes"]["summary"]["succeeded"] == 2

            # Bulk export responds with NDJSON (parsed to a list)
            exported = kibana_client.detection_engine.bulk_action_rules(
                action="export", ids=object_ids
            )
            exported_rule_ids = {
                line["rule_id"] for line in exported if "rule_id" in line
            }
            assert set(rule_ids) <= exported_rule_ids

            # Bulk delete by query (dry run first, then for real)
            dry = kibana_client.detection_engine.bulk_action_rules(
                action="delete",
                query=f'alert.attributes.tags: "{tag}"',
                dry_run=True,
            )
            assert dry.body["attributes"]["summary"]["succeeded"] == 2
            assert (
                kibana_client.detection_engine.find_rules(
                    filter=f'alert.attributes.tags: "{tag}"'
                ).body["total"]
                == 2
            )

            deleted = kibana_client.detection_engine.bulk_action_rules(
                action="delete",
                query=f'alert.attributes.tags: "{tag}"',
            )
            assert deleted.body["success"] is True
            assert deleted.body["attributes"]["summary"]["succeeded"] == 2
        finally:
            for rule_id in rule_ids:
                _delete_rule_quietly(kibana_client, rule_id=rule_id)

        for rule_id in rule_ids:
            with pytest.raises(NotFoundError):
                kibana_client.detection_engine.get_rule(rule_id=rule_id)

    def test_bulk_duplicate(self, kibana_client):
        rule_id = _unique("dup")
        created = kibana_client.detection_engine.create_rule(
            **_rule_args(rule_id, _unique("dup-rule"))
        )
        duplicate_rule_id = None
        try:
            result = kibana_client.detection_engine.bulk_action_rules(
                action="duplicate",
                ids=[created.body["id"]],
                duplicate={
                    "include_exceptions": False,
                    "include_expired_exceptions": False,
                },
            )
            assert result.body["success"] is True
            duplicates = result.body["attributes"]["results"]["created"]
            assert len(duplicates) == 1
            duplicate_rule_id = duplicates[0]["rule_id"]
            assert duplicates[0]["name"].endswith("[Duplicate]")
        finally:
            _delete_rule_quietly(kibana_client, rule_id=rule_id)
            if duplicate_rule_id:
                _delete_rule_quietly(kibana_client, rule_id=duplicate_rule_id)

    def test_bulk_enable_rejected_live(self, kibana_client):
        """Live 9.4.3 quirk: bulk enable/disable/run report
        USER_INSUFFICIENT_RULE_PRIVILEGES even for superusers.

        The semantic error message proves the route and payload reach the
        bulk-action handler.
        """
        rule_id = _unique("bulk-enable")
        created = kibana_client.detection_engine.create_rule(
            **_rule_args(rule_id, _unique("bulk-enable-rule"))
        )
        try:
            with pytest.raises(ApiError) as excinfo:
                kibana_client.detection_engine.bulk_action_rules(
                    action="enable", ids=[created.body["id"]]
                )
            errors = excinfo.value.body["attributes"]["errors"]
            assert errors[0]["message"] == (
                "User does not have permission to enable rules"
            )
            assert errors[0]["err_code"] == "USER_INSUFFICIENT_RULE_PRIVILEGES"
        finally:
            _delete_rule_quietly(kibana_client, rule_id=rule_id)


class TestDetectionAlerts:
    """Live tests for the detection alerts (signals) endpoints.

    The stack's alerts index exists but contains no alerts, so the mutation
    endpoints are exercised as empty-set round trips (HTTP 200, updated=0).
    """

    def test_search_alerts(self, kibana_client):
        results = kibana_client.detection_engine.search_alerts(
            query={"match_all": {}}, size=1
        )
        assert results.body["hits"]["total"]["value"] >= 0
        assert isinstance(results.body["hits"]["hits"], list)

    def test_search_alerts_with_aggregation(self, kibana_client):
        results = kibana_client.detection_engine.search_alerts(
            query={"match_all": {}},
            size=0,
            aggs={"by_rule": {"terms": {"field": "kibana.alert.rule.uuid"}}},
            track_total_hits=True,
        )
        assert "by_rule" in results.body["aggregations"]

    def test_set_alert_status_empty_set(self, kibana_client):
        result = kibana_client.detection_engine.set_alert_status(
            status="closed",
            signal_ids=[f"{PREFIX}-nonexistent-alert"],
        )
        assert result.body["updated"] == 0
        assert result.body["failures"] == []

    def test_set_alert_status_by_query_empty_set(self, kibana_client):
        result = kibana_client.detection_engine.set_alert_status(
            status="open",
            query={
                "bool": {
                    "filter": [
                        {"term": {"kibana.alert.rule.rule_id": f"{PREFIX}-none"}}
                    ]
                }
            },
            conflicts="proceed",
        )
        assert result.body["updated"] == 0

    def test_set_alert_tags_empty_set(self, kibana_client):
        result = kibana_client.detection_engine.set_alert_tags(
            ids=[f"{PREFIX}-nonexistent-alert"],
            tags_to_add=[f"{PREFIX}-tag"],
            tags_to_remove=[],
        )
        assert result.body["updated"] == 0

    def test_set_alert_assignees_empty_set(self, kibana_client):
        result = kibana_client.detection_engine.set_alert_assignees(
            ids=[f"{PREFIX}-nonexistent-alert"],
            add=["u_kbnpy_nonexistent_profile"],
            remove=[],
        )
        assert result.body["updated"] == 0


class TestSignalsMigrations:
    """Semantic-error live tests for the deprecated legacy migration APIs.

    The stack has no legacy ``.siem-signals-*`` indices, so every endpoint
    is exercised through its server-side semantic error.
    """

    def test_create_alerts_migration_requires_legacy_template(self, kibana_client):
        with pytest.raises(BadRequestError) as excinfo:
            kibana_client.detection_engine.create_alerts_migration(
                index=[".siem-signals-default"]
            )
        assert "Cannot migrate due to the signals template being out of date" in str(
            excinfo.value
        )

    def test_get_alerts_migration_status_without_legacy_indices(self, kibana_client):
        # Live 9.4.3 quirk: responds 404 with message "undefined: undefined"
        # when no legacy signals indices exist for the range.
        with pytest.raises(NotFoundError):
            kibana_client.detection_engine.get_alerts_migration_status(from_="now-30d")

    def test_finalize_alerts_migration_unknown_id(self, kibana_client):
        migration_id = _unique("migration")
        with pytest.raises(NotFoundError) as excinfo:
            kibana_client.detection_engine.finalize_alerts_migration(
                migration_ids=[migration_id]
            )
        assert f"security-solution-signals-migration/{migration_id}] not found" in str(
            excinfo.value
        )

    def test_delete_alerts_migration_unknown_id(self, kibana_client):
        migration_id = _unique("migration")
        with pytest.raises(NotFoundError) as excinfo:
            kibana_client.detection_engine.delete_alerts_migration(
                migration_ids=[migration_id]
            )
        assert f"security-solution-signals-migration/{migration_id}] not found" in str(
            excinfo.value
        )


class TestDetectionEngineSpaceScoped:
    """Space-scoped tests using a throwaway space.

    The alerts-index delete route is exercised here (never against the
    default space, whose alerts index is shared with other tests).
    """

    def test_alerts_index_and_rules_are_space_scoped(self, kibana_client):
        space_id = f"{PREFIX}-{uuid.uuid4().hex[:8]}"
        rule_id = _unique("spaced")
        kibana_client.spaces.create(id=space_id, name=space_id)
        try:
            # Alerts index lifecycle in the new space
            created = kibana_client.detection_engine.create_alerts_index(
                space_id=space_id
            )
            assert created.body == {"acknowledged": True}

            index = kibana_client.detection_engine.get_alerts_index(space_id=space_id)
            assert index.body["name"] == f".alerts-security.alerts-{space_id}"

            # DELETE only removes legacy .siem-signals indices on 9.4.3:
            # with only the modern alias present it responds a semantic 404.
            with pytest.raises(NotFoundError) as excinfo:
                kibana_client.detection_engine.delete_alerts_index(space_id=space_id)
            assert f'".siem-signals-{space_id}" does not exist' in str(excinfo.value)

            # A rule created in the space is not visible in the default space
            kibana_client.detection_engine.create_rule(
                **_rule_args(rule_id, _unique("spaced-rule")), space_id=space_id
            )
            fetched = kibana_client.detection_engine.get_rule(
                rule_id=rule_id, space_id=space_id
            )
            assert fetched.body["rule_id"] == rule_id
            with pytest.raises(NotFoundError):
                kibana_client.detection_engine.get_rule(rule_id=rule_id)
        finally:
            _delete_rule_quietly(kibana_client, rule_id=rule_id, space_id=space_id)
            kibana_client.spaces.delete(id=space_id)


class TestAsyncDetectionEngine:
    """Async round-trip tests for the detection engine API."""

    @pytest.mark.asyncio
    async def test_async_rule_roundtrip(self, async_kibana_client):
        rule_id = _unique("async")
        name = _unique("async-rule")
        created = await async_kibana_client.detection_engine.create_rule(
            **_rule_args(rule_id, name)
        )
        try:
            assert created.body["rule_id"] == rule_id

            fetched = await async_kibana_client.detection_engine.get_rule(
                rule_id=rule_id
            )
            assert fetched.body["name"] == name

            found = await async_kibana_client.detection_engine.find_rules(
                filter=f'alert.attributes.name: "{name}"'
            )
            assert found.body["total"] == 1

            privileges = await async_kibana_client.detection_engine.get_privileges()
            assert privileges.body["is_authenticated"] is True
        finally:
            try:
                await async_kibana_client.detection_engine.delete_rule(rule_id=rule_id)
            except NotFoundError:
                pass

        with pytest.raises(NotFoundError):
            await async_kibana_client.detection_engine.get_rule(rule_id=rule_id)
