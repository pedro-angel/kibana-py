"""Integration tests for the Synthetics API clients.

These tests run against a live Kibana instance. The stack is shared with
other test runs, so every resource created here is prefixed with
``kbnpy-synthetics-`` plus a per-run unique suffix, and is always deleted
afterwards (fixture finalizers or try/finally).

Private locations need a Fleet agent policy: the module-scoped fixture
creates a dedicated throwaway policy through the Fleet API, backs a private
location with it, and force-deletes both when the module finishes. No
Elastic Agent is enrolled, so monitors are fully manageable via CRUD but
never actually execute.
"""

import uuid

import pytest

from kibana.exceptions import BadRequestError, NotFoundError

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

# Unique per-run namespace for every resource created by this module.
NS = f"kbnpy-synthetics-{uuid.uuid4().hex[:8]}"


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


@pytest.fixture(scope="module")
def module_client():
    """Module-scoped client used by the shared private-location fixture."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture(scope="module")
def private_location(module_client):
    """Create a private location backed by a throwaway Fleet agent policy.

    Yields the created private location body. On teardown it deletes any
    leftover monitors tagged with this run's namespace, the private
    location, and finally force-deletes the agent policy (synthetics
    attaches managed package policies to it, so ``force`` is required).
    """
    policy = module_client.perform_request(
        "POST",
        "/api/fleet/agent_policies",
        body={
            "name": f"{NS}-policy",
            "namespace": "default",
            "description": "kibana-py synthetics integration tests",
        },
    )
    policy_id = policy.body["item"]["id"]
    location = None
    try:
        location = module_client.synthetics.create_private_location(
            label=f"{NS}-loc",
            agent_policy_id=policy_id,
            tags=[NS],
        ).body
        yield location
    finally:
        # Delete any monitors this run may have leaked before removing the
        # location (a location with assigned monitors cannot be deleted).
        try:
            leftovers = module_client.synthetics.get_monitors(tags=[NS]).body
            ids = [m["config_id"] for m in leftovers.get("monitors", [])]
            if ids:
                module_client.synthetics.bulk_delete_monitors(ids=ids)
        except Exception:
            pass
        if location is not None:
            try:
                module_client.synthetics.delete_private_location(id=location["id"])
            except Exception:
                pass
        module_client.perform_request(
            "POST",
            "/api/fleet/agent_policies/delete",
            body={"agentPolicyId": policy_id, "force": True},
        )


@pytest.fixture
def http_monitor(kibana_client, private_location):
    """Create an HTTP monitor on the private location; always delete it."""
    monitor = kibana_client.synthetics.create_monitor(
        type="http",
        name=f"{NS}-monitor-{uuid.uuid4().hex[:6]}",
        url="https://example.com",
        private_locations=[private_location["label"]],
        schedule={"number": "10", "unit": "m"},
        tags=[NS],
    ).body
    yield monitor
    try:
        kibana_client.synthetics.delete_monitor(id=monitor["config_id"])
    except NotFoundError:
        pass


class TestSyntheticsClientExists:
    """Basic wiring tests."""

    def test_synthetics_client_exists(self, kibana_client):
        """Test that SyntheticsClient is accessible via the main client."""
        assert hasattr(kibana_client, "synthetics")
        assert kibana_client.synthetics is not None


class TestSyntheticsMonitorsLive:
    """Live tests for the monitor endpoints."""

    def test_monitor_lifecycle(self, kibana_client, private_location):
        """Test create -> get -> update -> delete for an HTTP monitor."""
        name = f"{NS}-lifecycle"
        created = kibana_client.synthetics.create_monitor(
            type="http",
            name=name,
            url="https://example.com",
            private_locations=[private_location["label"]],
            schedule={"number": "10", "unit": "m"},
            tags=[NS, "lifecycle"],
        )
        monitor_id = created.body["config_id"]
        try:
            assert created.meta.status == 200
            assert created.body["name"] == name
            assert created.body["type"] == "http"
            assert created.body["enabled"] is True
            location_ids = [loc["id"] for loc in created.body["locations"]]
            assert private_location["id"] in location_ids

            fetched = kibana_client.synthetics.get_monitor(id=monitor_id)
            assert fetched.body["config_id"] == monitor_id
            assert fetched.body["url"] == "https://example.com"

            # Partial update: only the provided fields change
            updated = kibana_client.synthetics.update_monitor(
                id=monitor_id,
                name=f"{name}-renamed",
                enabled=False,
            )
            assert updated.body["name"] == f"{name}-renamed"
            assert updated.body["enabled"] is False
            assert updated.body["url"] == "https://example.com"
            assert updated.body["revision"] > created.body["revision"]
        finally:
            result = kibana_client.synthetics.delete_monitor(id=monitor_id)
            assert result.body[0] == {"id": monitor_id, "deleted": True}

        with pytest.raises(NotFoundError):
            kibana_client.synthetics.get_monitor(id=monitor_id)

    def test_get_monitors_filtering_and_pagination(self, kibana_client, http_monitor):
        """Test listing monitors filtered by tags, type, and query."""
        listed = kibana_client.synthetics.get_monitors(
            tags=[NS],
            monitor_types=["http"],
            query=http_monitor["name"],
            page=1,
            per_page=5,
            sort_field="name.keyword",
            sort_order="asc",
        )

        assert listed.meta.status == 200
        assert listed.body["perPage"] == 5
        names = [m["name"] for m in listed.body["monitors"]]
        assert http_monitor["name"] in names

    def test_bulk_delete_monitors(self, kibana_client, private_location):
        """Test bulk-deleting monitors, including an unknown ID."""
        created = kibana_client.synthetics.create_monitor(
            type="http",
            name=f"{NS}-bulk",
            url="https://example.com",
            private_locations=[private_location["label"]],
            tags=[NS],
        )
        monitor_id = created.body["config_id"]

        try:
            result = kibana_client.synthetics.bulk_delete_monitors(
                ids=[monitor_id, "kbnpy-does-not-exist"]
            )
        except Exception:
            kibana_client.synthetics.delete_monitor(id=monitor_id)
            raise

        assert result.meta.status == 200
        by_id = {item["id"]: item for item in result.body["result"]}
        assert by_id[monitor_id]["deleted"] is True
        assert by_id["kbnpy-does-not-exist"]["deleted"] is False
        assert "error" in by_id["kbnpy-does-not-exist"]

    def test_test_monitor_on_demand_run(self, kibana_client, http_monitor):
        """Test triggering an on-demand test run returns a testRunId."""
        run = kibana_client.synthetics.test_monitor(
            monitor_id=http_monitor["config_id"]
        )

        assert run.meta.status == 200
        assert isinstance(run.body["testRunId"], str)
        assert run.body["testRunId"]

    def test_create_monitor_without_location_is_rejected(self, kibana_client):
        """Test the live validation error when no location is provided."""
        with pytest.raises(BadRequestError, match="At least one location"):
            kibana_client.synthetics.create_monitor(
                type="http",
                name=f"{NS}-no-location",
                url="https://example.com",
            )

    def test_get_monitor_not_found(self, kibana_client):
        """Test that an unknown monitor ID maps to NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.synthetics.get_monitor(id="kbnpy-does-not-exist")


class TestSyntheticsParamsLive:
    """Live tests for the global parameter endpoints."""

    def test_param_lifecycle(self, kibana_client):
        """Test create -> get -> list -> update -> delete for a parameter."""
        created = kibana_client.synthetics.create_param(
            key=f"{NS}-key",
            value="initial-value",
            description="kibana-py integration test",
            tags=[NS],
        )
        param_id = created.body["id"]
        try:
            assert created.meta.status == 200
            assert created.body["key"] == f"{NS}-key"

            fetched = kibana_client.synthetics.get_param(id=param_id)
            assert fetched.body["id"] == param_id
            assert fetched.body["description"] == "kibana-py integration test"
            assert fetched.body["tags"] == [NS]

            listed = kibana_client.synthetics.get_params()
            assert param_id in [p["id"] for p in listed.body]

            updated = kibana_client.synthetics.update_param(
                id=param_id,
                value="rotated-value",
                description="rotated",
            )
            assert updated.body["description"] == "rotated"
            # Untouched fields are preserved
            assert updated.body["key"] == f"{NS}-key"
            # Live discrepancy: the PUT response echoes the PREVIOUS stored
            # value (encrypted field), even though the new value is applied.
            assert updated.body["value"] == "initial-value"

            # A follow-up update's response proves the new value was stored.
            reread = kibana_client.synthetics.update_param(
                id=param_id, description="rotated-again"
            )
            assert reread.body["value"] == "rotated-value"
        finally:
            result = kibana_client.synthetics.delete_param(id=param_id)
            assert result.body[0] == {"id": param_id, "deleted": True}

        with pytest.raises(NotFoundError):
            kibana_client.synthetics.update_param(id=param_id, value="x")

    def test_bulk_create_and_bulk_delete_params(self, kibana_client):
        """Test creating and deleting several parameters in one request."""
        created = kibana_client.synthetics.bulk_create_params(
            parameters=[
                {"key": f"{NS}-bulk-1", "value": "v1", "tags": [NS]},
                {"key": f"{NS}-bulk-2", "value": "v2", "tags": [NS]},
            ]
        )
        ids = [p["id"] for p in created.body]
        try:
            assert created.meta.status == 200
            assert len(ids) == 2
            keys = {p["key"] for p in created.body}
            assert keys == {f"{NS}-bulk-1", f"{NS}-bulk-2"}
        finally:
            result = kibana_client.synthetics.bulk_delete_params(ids=ids)
            assert {item["id"]: item["deleted"] for item in result.body} == {
                ids[0]: True,
                ids[1]: True,
            }


class TestSyntheticsPrivateLocationsLive:
    """Live tests for the private location endpoints."""

    def test_get_private_locations(self, kibana_client, private_location):
        """Test that the fixture location appears in the list response."""
        listed = kibana_client.synthetics.get_private_locations()

        assert listed.meta.status == 200
        by_id = {loc["id"]: loc for loc in listed.body}
        assert private_location["id"] in by_id
        assert by_id[private_location["id"]]["isServiceManaged"] is False

    def test_get_private_location_by_id(self, kibana_client, private_location):
        """Test getting a private location by ID."""
        fetched = kibana_client.synthetics.get_private_location(
            id=private_location["id"]
        )

        assert fetched.body["id"] == private_location["id"]
        assert fetched.body["agentPolicyId"] == private_location["agentPolicyId"]

    def test_update_private_location_label(self, kibana_client, private_location):
        """Test renaming a private location; then restore the label."""
        original_label = private_location["label"]
        try:
            updated = kibana_client.synthetics.update_private_location(
                id=private_location["id"],
                label=f"{original_label}-renamed",
            )
            assert updated.body["label"] == f"{original_label}-renamed"
        finally:
            restored = kibana_client.synthetics.update_private_location(
                id=private_location["id"],
                label=original_label,
            )
            assert restored.body["label"] == original_label

    def test_delete_unknown_private_location_is_bad_request(self, kibana_client):
        """Live discrepancy: deleting an unknown location returns 400, not 404."""
        with pytest.raises(BadRequestError, match="does not exist"):
            kibana_client.synthetics.delete_private_location(id="kbnpy-does-not-exist")

    def test_create_private_location_unknown_policy_is_rejected(self, kibana_client):
        """Test the validation error for a nonexistent agent policy."""
        with pytest.raises(BadRequestError, match="not found in space"):
            kibana_client.synthetics.create_private_location(
                label=f"{NS}-bogus",
                agent_policy_id="kbnpy-does-not-exist",
            )


class TestAsyncSyntheticsLive:
    """Live tests for AsyncSyntheticsClient."""

    async def test_async_param_roundtrip(self, async_kibana_client):
        """Test an async create -> get -> delete parameter round-trip."""
        created = await async_kibana_client.synthetics.create_param(
            key=f"{NS}-async-key",
            value="async-value",
            tags=[NS],
        )
        param_id = created.body["id"]
        try:
            assert created.meta.status == 200

            fetched = await async_kibana_client.synthetics.get_param(id=param_id)
            assert fetched.body["key"] == f"{NS}-async-key"
        finally:
            result = await async_kibana_client.synthetics.delete_param(id=param_id)
            assert result.body[0] == {"id": param_id, "deleted": True}

    async def test_async_monitor_roundtrip(self, async_kibana_client, private_location):
        """Test an async create -> list -> delete monitor round-trip."""
        created = await async_kibana_client.synthetics.create_monitor(
            type="http",
            name=f"{NS}-async-monitor",
            url="https://example.com",
            private_locations=[private_location["label"]],
            tags=[NS],
        )
        monitor_id = created.body["config_id"]
        try:
            listed = await async_kibana_client.synthetics.get_monitors(
                tags=[NS], query=f"{NS}-async-monitor"
            )
            names = [m["name"] for m in listed.body["monitors"]]
            assert f"{NS}-async-monitor" in names
        finally:
            result = await async_kibana_client.synthetics.delete_monitor(id=monitor_id)
            assert result.body[0] == {"id": monitor_id, "deleted": True}

    async def test_async_get_private_locations(
        self, async_kibana_client, private_location
    ):
        """Test listing private locations asynchronously."""
        listed = await async_kibana_client.synthetics.get_private_locations()

        assert listed.meta.status == 200
        assert private_location["id"] in [loc["id"] for loc in listed.body]
