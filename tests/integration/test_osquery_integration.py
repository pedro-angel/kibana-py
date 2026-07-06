"""Integration tests for OsqueryClient against a live Kibana instance."""

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

UPTIME_QUERY = "select * from uptime;"


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


@pytest.fixture
def unique_suffix():
    """Generate a unique suffix for test resource names."""
    return uuid.uuid4().hex[:12]


def _cleanup_pack(client, pack_id: str, space_id: str | None = None) -> None:
    """Delete a pack, ignoring the case where it is already gone."""
    try:
        client.osquery.delete_pack(id=pack_id, space_id=space_id)
    except NotFoundError:
        pass


def _cleanup_saved_query(client, saved_query_id: str) -> None:
    """Delete a saved query, ignoring the case where it is already gone."""
    try:
        client.osquery.delete_saved_query(id=saved_query_id)
    except NotFoundError:
        pass


class TestOsqueryPacksLifecycle:
    """Full lifecycle tests for Osquery packs."""

    def test_pack_create_get_find_update_delete(self, kibana_client, unique_suffix):
        """Test the full pack lifecycle."""
        pack_name = f"kbnpy-osquery-pack-{unique_suffix}"
        created = kibana_client.osquery.create_pack(
            name=pack_name,
            description="kibana-py integration test pack",
            enabled=False,
            queries={"uptime": {"query": UPTIME_QUERY, "interval": 3600}},
        )
        pack_id = created.body["data"]["saved_object_id"]
        try:
            assert created.meta.status == 200
            assert created.body["data"]["name"] == pack_name
            assert created.body["data"]["enabled"] is False
            assert created.body["data"]["queries"]["uptime"]["query"] == UPTIME_QUERY

            # Get by ID
            fetched = kibana_client.osquery.get_pack(id=pack_id)
            assert fetched.body["data"]["name"] == pack_name
            assert fetched.body["data"]["queries"]["uptime"]["interval"] == 3600

            # Find (list) packs and locate ours. Live 9.4.3 returns
            # flattened items carrying saved_object_id (no id/attributes
            # wrapper as in the spec example).
            found = kibana_client.osquery.find_packs(
                page=1, page_size=100, sort="updated_at", sort_order="desc"
            )
            assert found.body["total"] >= 1
            ids = [item["saved_object_id"] for item in found.body["data"]]
            assert pack_id in ids

            # Update (the live server resets omitted fields, so send them all)
            updated = kibana_client.osquery.update_pack(
                id=pack_id,
                name=f"{pack_name}-updated",
                description="kibana-py integration test pack (updated)",
                enabled=False,
                queries={"uptime": {"query": UPTIME_QUERY, "interval": 600}},
            )
            # Live 9.4.3 quirk: when "enabled" is included in the update
            # body the response is the flattened pack (like create); without
            # it the raw saved object ("attributes" wrapper) is returned.
            assert updated.body["data"]["name"] == f"{pack_name}-updated"
            assert updated.body["data"]["queries"]["uptime"]["interval"] == 600

            refetched = kibana_client.osquery.get_pack(id=pack_id)
            assert refetched.body["data"]["name"] == f"{pack_name}-updated"
        finally:
            _cleanup_pack(kibana_client, pack_id)

        # After deletion the pack must be gone, with the semantic message
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.osquery.get_pack(id=pack_id)
        assert f"Pack {pack_id} not found" in str(exc_info.value)

    def test_get_missing_pack_raises_not_found(self, kibana_client):
        """Test that getting a nonexistent pack raises a semantic 404."""
        missing_id = f"kbnpy-osquery-missing-{uuid.uuid4()}"
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.osquery.get_pack(id=missing_id)
        assert f"Pack {missing_id} not found" in str(exc_info.value)


class TestOsquerySavedQueriesLifecycle:
    """Full lifecycle tests for Osquery saved queries."""

    def test_saved_query_create_get_find_update_delete(
        self, kibana_client, unique_suffix
    ):
        """Test the full saved query lifecycle."""
        query_name = f"kbnpy_osquery_sq_{unique_suffix}"
        created = kibana_client.osquery.create_saved_query(
            id=query_name,
            query=UPTIME_QUERY,
            interval="60",
            description="kibana-py integration test saved query",
            ecs_mapping={"host.uptime": {"field": "total_seconds"}},
        )
        saved_object_id = created.body["data"]["saved_object_id"]
        try:
            assert created.meta.status == 200
            assert created.body["data"]["id"] == query_name
            assert created.body["data"]["query"] == UPTIME_QUERY
            assert created.body["data"]["interval"] == "60"

            # Get by saved object ID
            fetched = kibana_client.osquery.get_saved_query(id=saved_object_id)
            assert fetched.body["data"]["id"] == query_name
            assert fetched.body["data"]["ecs_mapping"] == {
                "host.uptime": {"field": "total_seconds"}
            }

            # Find (list) saved queries and locate ours. Live 9.4.3 returns
            # flattened items: "id" is the query name and "saved_object_id"
            # is the saved object ID (no id/attributes wrapper).
            found = kibana_client.osquery.find_saved_queries(
                page=1, page_size=100, sort="updated_at", sort_order="desc"
            )
            assert found.body["total"] >= 1
            ids = [item["saved_object_id"] for item in found.body["data"]]
            assert saved_object_id in ids

            # Update (the live server resets omitted fields, so send them all)
            updated = kibana_client.osquery.update_saved_query(
                id=saved_object_id,
                new_id=query_name,
                query=UPTIME_QUERY,
                interval="120",
                description="kibana-py integration test saved query (updated)",
            )
            # Live 9.4.3 quirk: interval must be SENT as a string, but after
            # an update the server stores and returns it as an integer.
            assert str(updated.body["data"]["interval"]) == "120"

            refetched = kibana_client.osquery.get_saved_query(id=saved_object_id)
            assert str(refetched.body["data"]["interval"]) == "120"
            assert (
                refetched.body["data"]["description"]
                == "kibana-py integration test saved query (updated)"
            )
        finally:
            _cleanup_saved_query(kibana_client, saved_object_id)

        # After deletion the saved query must be gone, with the semantic message
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.osquery.get_saved_query(id=saved_object_id)
        assert f"Saved query {saved_object_id} not found" in str(exc_info.value)

    def test_get_missing_saved_query_raises_not_found(self, kibana_client):
        """Test that getting a nonexistent saved query raises a semantic 404."""
        missing_id = f"kbnpy-osquery-missing-{uuid.uuid4()}"
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.osquery.get_saved_query(id=missing_id)
        assert f"Saved query {missing_id} not found" in str(exc_info.value)


class TestOsqueryLiveQueries:
    """Live query tests.

    The dev stack has no enrolled Elastic Agents (the ``.fleet-agents`` index
    has never been created), so creating a live query cannot be dispatched.
    These tests exercise every live-query route against the live server and
    assert the semantic server responses.
    """

    def test_find_live_queries(self, kibana_client):
        """Test listing live queries works live (empty result set is fine)."""
        result = kibana_client.osquery.find_live_queries(page=1, page_size=10)
        assert result.meta.status == 200
        assert "data" in result.body

    def test_find_live_queries_with_kuery(self, kibana_client):
        """Test that a kuery filter is accepted by the live server."""
        result = kibana_client.osquery.find_live_queries(
            kuery="user_id:elastic", page=1, page_size=10
        )
        assert result.meta.status == 200

    def test_create_live_query_records_server_behavior(self, kibana_client):
        """Test creating a live query with a fake agent ID list.

        On a stack where no agent has ever enrolled, Kibana 9.4.3 fails with
        a 500 ``index_not_found_exception`` for the missing ``.fleet-agents``
        index. If an agent index exists (agents were enrolled at some point),
        the server accepts the query and queues it instead.
        """
        fake_agent_id = "00000000-0000-0000-0000-000000000000"
        try:
            result = kibana_client.osquery.create_live_query(
                query=UPTIME_QUERY,
                agent_ids=[fake_agent_id],
            )
        except ApiError as exc:
            # No agent ever enrolled: semantic 500 from the osquery plugin
            assert exc.status_code == 500
            assert "no such index [.fleet-agents]" in str(exc)
        else:
            # Accepted and queued: the response carries the action metadata
            assert "action_id" in result.body["data"]

    def test_get_live_query_unknown_id_server_behavior(self, kibana_client):
        """Test details for an unknown live query ID.

        The live 9.4.3 server responds 500 "no elements in sequence" (not a
        404) for unknown live query IDs; asserting the message proves the
        request reached the osquery live-query route.
        """
        with pytest.raises(ApiError) as exc_info:
            kibana_client.osquery.get_live_query(id=str(uuid.uuid4()))
        assert exc_info.value.status_code == 500
        assert "no elements in sequence" in str(exc_info.value)

    def test_get_live_query_results_unknown_action_raises_not_found(
        self, kibana_client
    ):
        """Test results for an unknown action ID raise a semantic 404."""
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.osquery.get_live_query_results(
                id=str(uuid.uuid4()),
                action_id=str(uuid.uuid4()),
                page=1,
                page_size=10,
            )
        assert "Action not found" in str(exc_info.value)


class TestOsquerySpaceScoped:
    """Space-scoped tests for the Osquery API."""

    def test_pack_is_space_scoped(self, kibana_client, unique_suffix):
        """Test that a pack created in a space is not visible elsewhere."""
        space_id = f"kbnpy-osquery-{unique_suffix[:8]}"
        kibana_client.spaces.create(id=space_id, name=space_id)
        pack_id = None
        try:
            created = kibana_client.osquery.create_pack(
                name=f"kbnpy-osquery-space-pack-{unique_suffix}",
                queries={"uptime": {"query": UPTIME_QUERY, "interval": 3600}},
                space_id=space_id,
            )
            pack_id = created.body["data"]["saved_object_id"]

            # Visible in its own space
            fetched = kibana_client.osquery.get_pack(id=pack_id, space_id=space_id)
            assert (
                fetched.body["data"]["name"]
                == f"kbnpy-osquery-space-pack-{unique_suffix}"
            )

            # Not visible in the default space
            with pytest.raises(NotFoundError):
                kibana_client.osquery.get_pack(id=pack_id)
        finally:
            if pack_id is not None:
                _cleanup_pack(kibana_client, pack_id, space_id=space_id)
            kibana_client.spaces.delete(id=space_id)


class TestAsyncOsqueryLifecycle:
    """Async round-trip tests for the Osquery API."""

    @pytest.mark.asyncio
    async def test_async_saved_query_round_trip(
        self, async_kibana_client, unique_suffix
    ):
        """Test the full saved query lifecycle with the async client."""
        query_name = f"kbnpy_osquery_async_sq_{unique_suffix}"
        created = await async_kibana_client.osquery.create_saved_query(
            id=query_name,
            query=UPTIME_QUERY,
            interval="60",
            description="kibana-py async integration test saved query",
        )
        saved_object_id = created.body["data"]["saved_object_id"]
        try:
            assert created.body["data"]["id"] == query_name

            fetched = await async_kibana_client.osquery.get_saved_query(
                id=saved_object_id
            )
            assert fetched.body["data"]["query"] == UPTIME_QUERY

            updated = await async_kibana_client.osquery.update_saved_query(
                id=saved_object_id,
                new_id=query_name,
                query=UPTIME_QUERY,
                interval="300",
            )
            # Live 9.4.3 quirk: interval comes back as an integer on update.
            assert str(updated.body["data"]["interval"]) == "300"

            found = await async_kibana_client.osquery.find_saved_queries(
                page=1, page_size=100
            )
            ids = [item["saved_object_id"] for item in found.body["data"]]
            assert saved_object_id in ids
        finally:
            try:
                await async_kibana_client.osquery.delete_saved_query(id=saved_object_id)
            except NotFoundError:
                pass

        with pytest.raises(NotFoundError):
            await async_kibana_client.osquery.get_saved_query(id=saved_object_id)

    @pytest.mark.asyncio
    async def test_async_pack_round_trip(self, async_kibana_client, unique_suffix):
        """Test pack create/get/delete and live query listing with async."""
        pack_name = f"kbnpy-osquery-async-pack-{unique_suffix}"
        created = await async_kibana_client.osquery.create_pack(
            name=pack_name,
            queries={"uptime": {"query": UPTIME_QUERY, "interval": 3600}},
        )
        pack_id = created.body["data"]["saved_object_id"]
        try:
            fetched = await async_kibana_client.osquery.get_pack(id=pack_id)
            assert fetched.body["data"]["name"] == pack_name

            found = await async_kibana_client.osquery.find_packs(page_size=100)
            ids = [item["saved_object_id"] for item in found.body["data"]]
            assert pack_id in ids

            live = await async_kibana_client.osquery.find_live_queries(page_size=10)
            assert live.meta.status == 200
        finally:
            try:
                await async_kibana_client.osquery.delete_pack(id=pack_id)
            except NotFoundError:
                pass
