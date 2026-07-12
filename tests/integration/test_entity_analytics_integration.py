"""Integration tests for EntityAnalyticsClient against a live Kibana instance."""

import time
import uuid

import pytest

from kibana.exceptions import ApiError, NotFoundError

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

PREFIX = "kbnpy-entity-analytics"


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
    """Generate a unique, prefixed resource name."""
    return f"{PREFIX}-{suffix}-{uuid.uuid4().hex[:8]}"


def _wait_for_entity_store_status(
    client, expected: str, timeout: float = 300.0, interval: float = 5.0
) -> dict:
    """Poll the entity store status until it reaches ``expected``."""
    deadline = time.monotonic() + timeout
    body = client.entity_analytics.get_entity_store_status().body
    while body["status"] != expected:
        if time.monotonic() > deadline:
            raise AssertionError(
                f"Entity store did not reach status {expected!r} within "
                f"{timeout}s (last status: {body['status']!r}, "
                f"engines: {body.get('engines')!r})"
            )
        time.sleep(interval)
        body = client.entity_analytics.get_entity_store_status().body
    return body


class TestAssetCriticality:
    """Live tests for the (deprecated but functional) asset criticality API."""

    def test_asset_criticality_lifecycle(self, kibana_client):
        """Test create -> get -> find -> delete for one criticality record."""
        host_name = _unique("host")
        try:
            created = kibana_client.entity_analytics.create_asset_criticality(
                id_field="host.name",
                id_value=host_name,
                criticality_level="high_impact",
                refresh="wait_for",
            )
            assert created.meta.status == 200
            assert created.body["criticality_level"] == "high_impact"
            assert created.body["asset"]["criticality"] == "high_impact"

            fetched = kibana_client.entity_analytics.get_asset_criticality(
                id_field="host.name", id_value=host_name
            )
            assert fetched.body["id_value"] == host_name

            found = kibana_client.entity_analytics.find_asset_criticality(
                kuery=f"id_value: {host_name}",
                sort_field="@timestamp",
                sort_direction="desc",
                per_page=10,
            )
            assert found.body["total"] == 1
            assert found.body["records"][0]["id_value"] == host_name
        finally:
            deleted = kibana_client.entity_analytics.delete_asset_criticality(
                id_field="host.name", id_value=host_name, refresh="wait_for"
            )

        assert deleted.body["deleted"] is True
        with pytest.raises(NotFoundError):
            kibana_client.entity_analytics.get_asset_criticality(
                id_field="host.name", id_value=host_name
            )

    def test_bulk_upsert_asset_criticality(self, kibana_client):
        """Test bulk upserting and cleaning up criticality records."""
        host_name = _unique("bulk-host")
        user_name = _unique("bulk-user")
        try:
            result = kibana_client.entity_analytics.bulk_upsert_asset_criticality(
                records=[
                    {
                        "id_field": "host.name",
                        "id_value": host_name,
                        "criticality_level": "medium_impact",
                    },
                    {
                        "id_field": "user.name",
                        "id_value": user_name,
                        "criticality_level": "low_impact",
                    },
                ]
            )
            assert result.body["errors"] == []
            assert result.body["stats"] == {
                "successful": 2,
                "failed": 0,
                "total": 2,
            }
        finally:
            for id_field, id_value in [
                ("host.name", host_name),
                ("user.name", user_name),
            ]:
                kibana_client.entity_analytics.delete_asset_criticality(
                    id_field=id_field, id_value=id_value, refresh="wait_for"
                )


class TestRiskEngine:
    """Live tests for the risk engine routes.

    On this stack Entity Store V2 is enabled, which unregisters the legacy
    public risk engine routes: Kibana answers a plain 404 "Not Found" (the
    internal risk engine routes answer 400 "This API is not available when
    Entity Store V2 is enabled"). These tests pin down that live behavior.
    """

    def test_schedule_risk_engine_now_route_unregistered(self, kibana_client):
        """Test that schedule_now raises NotFoundError on this stack."""
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.entity_analytics.schedule_risk_engine_now()
        assert "Not Found" in str(exc_info.value)

    def test_configure_risk_engine_saved_object_route_unregistered(self, kibana_client):
        """Test that saved-object configure raises NotFoundError on this stack."""
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.entity_analytics.configure_risk_engine_saved_object(
                exclude_alert_statuses=["closed"]
            )
        assert "Not Found" in str(exc_info.value)

    # NOTE: cleanup_risk_engine (DELETE /api/risk_score/engine/
    # dangerously_delete_data) is intentionally NOT exercised live: the brief
    # forbids calling it without having initialized the risk engine in this
    # test run, and the route is unregistered on this stack anyway (the
    # request shape is fully unit-tested).


class TestPrivilegeMonitoring:
    """Live tests for the Privilege Monitoring Engine and monitored users."""

    def test_monitoring_privileges_check(self, kibana_client):
        """Test the privileges check endpoint."""
        result = kibana_client.entity_analytics.get_monitoring_privileges()
        assert result.meta.status == 200
        assert "has_all_required" in result.body
        assert "elasticsearch" in result.body["privileges"]

    @pytest.mark.flaky  # context-dependent: fails in full-suite runs, passes in isolation; see #39
    def test_monitoring_engine_and_users_lifecycle(self, kibana_client):
        """Test the full privilege monitoring lifecycle.

        init -> health -> create/list/update user -> CSV upload ->
        schedule_now -> disable -> delete (with data).
        """
        ea = kibana_client.entity_analytics
        user_name = _unique("privuser")
        csv_user_1 = _unique("csvuser1")
        csv_user_2 = _unique("csvuser2")
        try:
            init = ea.init_monitoring_engine()
            assert init.body["status"] == "started"

            health = ea.get_monitoring_health()
            assert health.body["status"] == "started"

            created = ea.create_monitored_user(name=user_name)
            user_id = created.body["id"]
            assert created.body["user"]["name"] == user_name
            assert created.body["user"]["is_privileged"] is True
            assert created.body["labels"]["sources"] == ["api"]

            listed = ea.list_monitored_users(kql=f"user.name: {user_name}")
            assert [u["id"] for u in listed.body] == [user_id]

            renamed = f"{user_name}-renamed"
            updated = ea.update_monitored_user(
                id=user_id,
                doc={"user": {"name": renamed, "is_privileged": True}},
            )
            assert updated.body["user"]["name"] == renamed

            csv_result = ea.upload_monitored_users_csv(
                file=f"{csv_user_1}\n{csv_user_2}\n"
            )
            assert csv_result.body["errors"] == []
            assert csv_result.body["stats"]["uploaded"] == 2
            assert csv_result.body["stats"]["failedOperations"] == 0

            scheduled = ea.schedule_monitoring_engine_now()
            assert scheduled.body["success"] is True

            deleted_user = ea.delete_monitored_user(id=user_id)
            assert deleted_user.body["acknowledged"] is True

            disabled = ea.disable_monitoring_engine()
            assert disabled.body["status"] == "disabled"
            assert ea.get_monitoring_health().body["status"] == "disabled"
        finally:
            # Always remove the engine and its data (including CSV users)
            result = ea.delete_monitoring_engine(data=True)
            assert result.body["deleted"] is True

        assert ea.get_monitoring_health().body["status"] == "not_installed"


class TestPrivilegedAccessDetection:
    """Live tests for the privileged access detection (PAD) package."""

    def test_install_pad_package_and_get_status(self, kibana_client):
        """Test installing the PAD package (idempotent) and reading status."""
        result = kibana_client.entity_analytics.install_pad_package()
        # First run: "Successfully installed privileged access detection
        # package."; subsequent runs: "Privileged access detection package
        # was already installed."
        assert "installed" in result.body["message"]
        assert "privileged access detection package" in result.body["message"].lower()

        status = kibana_client.entity_analytics.get_pad_status()
        assert status.body["package_installation_status"] == "complete"
        assert "ml_module_setup_status" in status.body
        assert "jobs" in status.body


class TestWatchlists:
    """Live tests for the watchlists API (Technical Preview)."""

    def test_watchlist_lifecycle(self, kibana_client):
        """Test create -> get -> list -> update -> unassign -> delete."""
        ea = kibana_client.entity_analytics
        name = _unique("watchlist")
        created = ea.create_watchlist(
            name=name,
            risk_modifier=1.2,
            description="kbnpy integration test watchlist",
        )
        watchlist_id = created.body["id"]
        try:
            assert created.body["name"] == name
            assert created.body["riskModifier"] == 1.2
            assert created.body["managed"] is False

            fetched = ea.get_watchlist(id=watchlist_id)
            assert fetched.body["id"] == watchlist_id
            assert fetched.body["entityCount"] == 0

            listed = ea.list_watchlists()
            assert watchlist_id in [w["id"] for w in listed.body]

            updated = ea.update_watchlist(
                id=watchlist_id,
                name=name,
                risk_modifier=1.7,
                description="updated by kbnpy",
            )
            assert updated.body["riskModifier"] == 1.7
            assert updated.body["description"] == "updated by kbnpy"

            # Unassigning entities that were never assigned reports not_found
            # per item (works even without the Entity Store installed).
            unassigned = ea.unassign_watchlist_entities(
                watchlist_id=watchlist_id,
                euids=[f"host:{PREFIX}-missing"],
            )
            assert unassigned.body["total"] == 1
            assert unassigned.body["not_found"] == 1
            assert unassigned.body["items"][0]["status"] == "not_found"
        finally:
            deleted = ea.delete_watchlist(id=watchlist_id)
            assert deleted.body["deleted"] is True

        # Live quirk: Kibana 9.4.3 answers 500 "Watchlist config ... not
        # found" (not 404) for a missing watchlist ID.
        with pytest.raises(ApiError) as exc_info:
            ea.get_watchlist(id=watchlist_id)
        assert exc_info.value.status_code == 500
        assert "not found" in str(exc_info.value)


class TestEntityStore:
    """Live tests for the Entity Store: install, use and uninstall.

    A single lifecycle test keeps installation/uninstallation atomic so the
    shared stack is always left clean, even on assertion failure.
    """

    def test_entity_store_full_lifecycle(self, kibana_client):
        """Test install -> status poll -> entity CRUD/resolution -> uninstall."""
        ea = kibana_client.entity_analytics
        host_1 = _unique("store-host1")
        host_2 = _unique("store-host2")
        euid_1 = f"host:{host_1}"
        euid_2 = f"host:{host_2}"
        watchlist_id = None
        try:
            install = ea.install_entity_store(entity_types=["host"], log_extraction={})
            assert install.body["ok"] is True

            # Poll until the store reports running (generous timeout)
            body = _wait_for_entity_store_status(kibana_client, "running")
            assert [e["type"] for e in body["engines"]] == ["host"]
            assert body["engines"][0]["status"] == "started"

            # Component-level status
            with_components = ea.get_entity_store_status(include_components=True)
            components = with_components.body["engines"][0]["components"]
            assert len(components) > 0
            assert {"resource", "installed"} <= set(components[0].keys())

            # Update the store-level log extraction configuration
            updated = ea.update_entity_store(log_extraction={"frequency": "2m"})
            assert updated.body["ok"] is True

            # Create / update / bulk-update entities. Note: bulk update does
            # NOT upsert missing documents (even with force=True) -- it
            # reports a per-item 404 document_missing_exception -- so both
            # entities are created explicitly first.
            for host_name in (host_1, host_2):
                assert (
                    ea.create_entity(
                        entity_type="host", document={"host": {"name": host_name}}
                    ).body["ok"]
                    is True
                )
            assert (
                ea.update_entity(
                    entity_type="host",
                    document={
                        "host": {"name": host_1},
                        "labels": {"kbnpy": "yes"},
                    },
                    force=True,
                ).body["ok"]
                is True
            )
            bulk = ea.bulk_update_entities(
                entities=[
                    {
                        "type": "host",
                        "doc": {
                            "host": {"name": host_2},
                            "labels": {"kbnpy": "bulk"},
                        },
                    },
                ],
                force=True,
            )
            assert bulk.body["ok"] is True
            assert bulk.body["errors"] == []

            # Listing hits the (transform-fed) latest index; entities written
            # via the CRUD APIs are not materialized into it by the transform
            # on 9.4.3, so only assert the documented response shape.
            entities = ea.list_entities(entity_types=["host"], per_page=10)
            assert entities.meta.status == 200
            assert {"records", "total", "page", "per_page"} <= set(entities.body.keys())

            # Entity resolution: group / link / unlink
            group = ea.get_entity_resolution_group(entity_id=euid_1)
            assert group.body["target"]["entity"]["id"] == euid_1
            assert group.body["group_size"] >= 1

            linked = ea.link_entities(entity_ids=[euid_2], target_id=euid_1)
            assert linked.body["linked"] == [euid_2]
            assert linked.body["target_id"] == euid_1

            unlinked = ea.unlink_entities(entity_ids=[euid_2])
            assert unlinked.body["unlinked"] == [euid_2]

            # Watchlist entity assignment requires the Entity Store indices,
            # so exercise it here with a throwaway watchlist. Live quirk:
            # entities created through the CRUD APIs are never materialized
            # into the latest index by the transform, and assigning one makes
            # Kibana 9.4.3 fail schema validation on the stripped record with
            # a 500 "Unexpected entity store record".
            watchlist = ea.create_watchlist(
                name=_unique("store-watchlist"), risk_modifier=1.0
            )
            watchlist_id = watchlist.body["id"]
            with pytest.raises(ApiError) as exc_info:
                ea.assign_watchlist_entities(watchlist_id=watchlist_id, euids=[euid_1])
            assert exc_info.value.status_code == 500
            assert "Unexpected entity store record" in str(exc_info.value)

            # CSV rows are parsed and matched against the latest index; the
            # CRUD-created entity is not there, so the row is "unmatched".
            csv_result = ea.upload_watchlist_csv(
                watchlist_id=watchlist_id,
                file=f"type,name\nhost,{host_1}\n",
            )
            assert csv_result.body["total"] == 1
            assert csv_result.body["items"][0]["status"] in {
                "unmatched",
                "success",
            }

            # Delete one entity document
            assert ea.delete_entity(entity_id=euid_2).body["deleted"] is True

            # Stop and restart the engines
            assert ea.stop_entity_store().body["ok"] is True
            status = ea.get_entity_store_status().body
            assert status["status"] == "stopped"

            assert ea.start_entity_store(entity_types=["host"]).body["ok"] is True
            status = ea.get_entity_store_status().body
            assert status["status"] == "running"
        finally:
            if watchlist_id is not None:
                try:
                    ea.delete_watchlist(id=watchlist_id)
                except NotFoundError:
                    pass
            # Guaranteed uninstall, no matter what happened above
            uninstall = ea.uninstall_entity_store()
            assert uninstall.body["ok"] is True
            _wait_for_entity_store_status(kibana_client, "not_installed")


class TestAsyncEntityAnalytics:
    """Async round-trip tests for the Entity Analytics API."""

    async def test_async_asset_criticality_round_trip(self, async_kibana_client):
        """Test the asset criticality lifecycle with the async client."""
        ea = async_kibana_client.entity_analytics
        host_name = _unique("async-host")
        try:
            created = await ea.create_asset_criticality(
                id_field="host.name",
                id_value=host_name,
                criticality_level="extreme_impact",
                refresh="wait_for",
            )
            assert created.body["criticality_level"] == "extreme_impact"

            fetched = await ea.get_asset_criticality(
                id_field="host.name", id_value=host_name
            )
            assert fetched.body["id_value"] == host_name

            found = await ea.find_asset_criticality(kuery=f"id_value: {host_name}")
            assert found.body["total"] == 1
        finally:
            deleted = await ea.delete_asset_criticality(
                id_field="host.name", id_value=host_name, refresh="wait_for"
            )
        assert deleted.body["deleted"] is True

    async def test_async_watchlist_round_trip(self, async_kibana_client):
        """Test watchlist create/get/delete with the async client."""
        ea = async_kibana_client.entity_analytics
        name = _unique("async-watchlist")
        created = await ea.create_watchlist(name=name, risk_modifier=0.9)
        watchlist_id = created.body["id"]
        try:
            fetched = await ea.get_watchlist(id=watchlist_id)
            assert fetched.body["name"] == name
        finally:
            deleted = await ea.delete_watchlist(id=watchlist_id)
            assert deleted.body["deleted"] is True

    async def test_async_entity_store_status(self, async_kibana_client):
        """Test reading the entity store status with the async client."""
        status = await async_kibana_client.entity_analytics.get_entity_store_status()
        assert status.meta.status == 200
        assert "status" in status.body
        assert "engines" in status.body
