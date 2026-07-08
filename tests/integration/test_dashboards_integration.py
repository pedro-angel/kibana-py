"""Integration tests for the Dashboards API (tech preview, added in 9.4.0).

Runs against a live Kibana stack. Every resource created here is prefixed
``kbnpy-dashboards-`` and cleaned up via fixtures/finalizers.
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

PREFIX = "kbnpy-dashboards"


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
def created_dashboards(kibana_client):
    """Track (dashboard_id, space_id) pairs created during tests for cleanup."""
    entries: list[tuple[str, str | None]] = []
    yield entries

    for dashboard_id, space_id in entries:
        try:
            kibana_client.dashboards.delete(
                id=dashboard_id, space_id=space_id, validate_spaces=False
            )
        except NotFoundError:
            pass  # Already deleted by the test itself
        except Exception as e:  # pragma: no cover - cleanup best effort
            print(f"Warning: failed to clean up dashboard {dashboard_id}: {e}")


@pytest.fixture
def unique_suffix():
    """Unique suffix so parallel runs never collide."""
    return uuid.uuid4().hex[:8]


class TestDashboardsCrudLifecycle:
    """Full CRUD round-trip with a rich dashboard payload."""

    def test_create_read_update_delete_roundtrip(
        self, kibana_client, created_dashboards, unique_suffix
    ):
        title = f"{PREFIX}-crud-{unique_suffix}"
        tag_a = f"{PREFIX}-tag-a-{unique_suffix}"
        tag_b = f"{PREFIX}-tag-b-{unique_suffix}"
        markdown_panel = {
            "type": "markdown",
            "grid": {"x": 0, "y": 0, "w": 24, "h": 15},
            "config": {
                "title": "Notes",
                "content": "# kibana-py integration test\nCreated by kibana-py.",
                "settings": {"open_links_in_new_tab": True},
            },
        }

        # --- create ---
        created = kibana_client.dashboards.create(
            title=title,
            description="kibana-py dashboards integration test",
            panels=[markdown_panel],
            tags=[tag_a, tag_b],
            time_range={"from": "now-7d", "to": "now"},
            options={"hide_panel_titles": True},
        )
        dashboard_id = created.body["id"]
        created_dashboards.append((dashboard_id, None))

        assert created.meta.status in (200, 201)
        assert created.body["data"]["title"] == title
        assert "meta" in created.body

        # --- read back field-by-field ---
        fetched = kibana_client.dashboards.get(id=dashboard_id)
        data = fetched.body["data"]
        assert fetched.body["id"] == dashboard_id
        assert data["title"] == title
        assert data["description"] == "kibana-py dashboards integration test"
        assert sorted(data["tags"]) == sorted([tag_a, tag_b])
        assert data["time_range"]["from"] == "now-7d"
        assert data["time_range"]["to"] == "now"
        assert data["options"]["hide_panel_titles"] is True
        assert len(data["panels"]) == 1
        panel = data["panels"][0]
        assert panel["type"] == "markdown"
        assert panel["grid"] == {"x": 0, "y": 0, "w": 24, "h": 15}
        assert panel["config"]["content"] == (
            "# kibana-py integration test\nCreated by kibana-py."
        )
        assert panel["config"]["settings"]["open_links_in_new_tab"] is True
        meta = fetched.body["meta"]
        assert meta["managed"] is False
        assert "created_at" in meta
        assert "updated_at" in meta

        # --- update (upsert on an existing id) ---
        updated = kibana_client.dashboards.update(
            id=dashboard_id,
            title=f"{title}-updated",
            description="updated by kibana-py",
            tags=[tag_a],
            time_range={"from": "now-24h", "to": "now"},
        )
        assert updated.meta.status == 200
        assert updated.body["data"]["title"] == f"{title}-updated"

        refetched = kibana_client.dashboards.get(id=dashboard_id)
        data = refetched.body["data"]
        assert data["title"] == f"{title}-updated"
        assert data["description"] == "updated by kibana-py"
        assert data["tags"] == [tag_a]
        assert data["time_range"]["from"] == "now-24h"
        # PUT replaces the whole data object: panels were omitted, so gone
        assert data["panels"] == []

        # --- delete ---
        deleted = kibana_client.dashboards.delete(id=dashboard_id)
        assert deleted.meta.status == 204

        with pytest.raises(NotFoundError):
            kibana_client.dashboards.get(id=dashboard_id)

    def test_update_upserts_with_custom_id(
        self, kibana_client, created_dashboards, unique_suffix
    ):
        """PUT with a fresh id creates the dashboard (201) — the custom-id path."""
        custom_id = f"{PREFIX}-custom-{unique_suffix}"
        created_dashboards.append((custom_id, None))

        response = kibana_client.dashboards.update(
            id=custom_id, title=f"{PREFIX}-upsert-{unique_suffix}"
        )
        assert response.meta.status == 201
        assert response.body["id"] == custom_id

        fetched = kibana_client.dashboards.get(id=custom_id)
        assert fetched.body["id"] == custom_id

    def test_create_rejects_id_in_body(self, kibana_client):
        """The live server rejects an ``id`` property in the POST body.

        The client never sends one (there is no ``id`` kwarg on create), so
        verify the raw API contract that motivates that design.
        """
        with pytest.raises(BadRequestError, match="id"):
            kibana_client.perform_request(
                "POST",
                "/api/dashboards",
                body={"id": f"{PREFIX}-rejected", "title": f"{PREFIX}-rejected"},
            )


class TestDashboardsSearch:
    """GET /api/dashboards with query/tags filters and pagination."""

    @pytest.fixture
    def searchable_dashboards(self, kibana_client, created_dashboards, unique_suffix):
        """Create three dashboards with distinct tags for search tests."""
        marker = f"{PREFIX}-search-{unique_suffix}"
        tag_wanted = f"{PREFIX}-wanted-{unique_suffix}"
        tag_other = f"{PREFIX}-other-{unique_suffix}"

        ids = []
        for index, tag in enumerate([tag_wanted, tag_wanted, tag_other]):
            response = kibana_client.dashboards.create(
                title=f"{marker}-{index}",
                tags=[tag],
            )
            dashboard_id = response.body["id"]
            ids.append(dashboard_id)
            created_dashboards.append((dashboard_id, None))
        return {
            "marker": marker,
            "ids": ids,
            "tag_wanted": tag_wanted,
            "tag_other": tag_other,
        }

    def test_search_with_query_filter(self, kibana_client, searchable_dashboards):
        marker = searchable_dashboards["marker"]

        results = kibana_client.dashboards.get_all(query=f"{marker}*")

        assert results.body["total"] == 3
        found_ids = {item["id"] for item in results.body["dashboards"]}
        assert found_ids == set(searchable_dashboards["ids"])
        for item in results.body["dashboards"]:
            assert item["data"]["title"].startswith(marker)

    def test_search_with_tags_filter(self, kibana_client, searchable_dashboards):
        results = kibana_client.dashboards.get_all(
            tags=[searchable_dashboards["tag_wanted"]]
        )

        assert results.body["total"] == 2
        found_ids = {item["id"] for item in results.body["dashboards"]}
        assert found_ids == set(searchable_dashboards["ids"][:2])

    def test_search_with_excluded_tags_filter(
        self, kibana_client, searchable_dashboards
    ):
        marker = searchable_dashboards["marker"]

        results = kibana_client.dashboards.get_all(
            query=f"{marker}*",
            excluded_tags=[searchable_dashboards["tag_wanted"]],
        )

        assert results.body["total"] == 1
        assert results.body["dashboards"][0]["id"] == searchable_dashboards["ids"][2]

    def test_search_pagination(self, kibana_client, searchable_dashboards):
        marker = searchable_dashboards["marker"]

        page1 = kibana_client.dashboards.get_all(query=f"{marker}*", per_page=2, page=1)
        page2 = kibana_client.dashboards.get_all(query=f"{marker}*", per_page=2, page=2)

        assert page1.body["page"] == 1
        assert page2.body["page"] == 2
        assert page1.body["total"] == 3
        assert page2.body["total"] == 3
        assert len(page1.body["dashboards"]) == 2
        assert len(page2.body["dashboards"]) == 1

        page1_ids = {item["id"] for item in page1.body["dashboards"]}
        page2_ids = {item["id"] for item in page2.body["dashboards"]}
        assert page1_ids.isdisjoint(page2_ids)
        assert page1_ids | page2_ids == set(searchable_dashboards["ids"])


class TestDashboardsSpaceScoped:
    """Dashboards live inside spaces: round-trip in a dedicated space."""

    @pytest.fixture
    def test_space(self, kibana_client, unique_suffix):
        """Create a dedicated space and delete it (and its contents) afterwards."""
        space_id = f"{PREFIX}-space-{unique_suffix}"
        kibana_client.spaces.create(
            id=space_id, name=f"kibana-py dashboards test {unique_suffix}"
        )
        yield space_id
        try:
            kibana_client.spaces.delete(id=space_id)
        except Exception as e:  # pragma: no cover - cleanup best effort
            print(f"Warning: failed to delete space {space_id}: {e}")

    def test_space_scoped_roundtrip(
        self, kibana_client, created_dashboards, test_space, unique_suffix
    ):
        title = f"{PREFIX}-spaced-{unique_suffix}"

        created = kibana_client.dashboards.create(
            title=title,
            space_id=test_space,
        )
        dashboard_id = created.body["id"]
        created_dashboards.append((dashboard_id, test_space))

        # Visible inside the space
        fetched = kibana_client.dashboards.get(id=dashboard_id, space_id=test_space)
        assert fetched.body["data"]["title"] == title

        results = kibana_client.dashboards.get_all(
            query=f"{title}*", space_id=test_space
        )
        assert results.body["total"] == 1
        assert results.body["dashboards"][0]["id"] == dashboard_id

        # Not visible in the default space
        with pytest.raises(NotFoundError):
            kibana_client.dashboards.get(id=dashboard_id)
        default_results = kibana_client.dashboards.get_all(query=f"{title}*")
        assert default_results.body["total"] == 0

        # Delete inside the space
        kibana_client.dashboards.delete(id=dashboard_id, space_id=test_space)
        with pytest.raises(NotFoundError):
            kibana_client.dashboards.get(id=dashboard_id, space_id=test_space)


class TestAsyncDashboardsIntegration:
    """Async client round-trip against the live stack."""

    async def test_async_crud_roundtrip(self, unique_suffix):
        client = create_test_async_kibana_client(auth_method="auto")
        title = f"{PREFIX}-async-{unique_suffix}"
        dashboard_id = None
        try:
            created = await client.dashboards.create(
                title=title,
                description="async round-trip",
                tags=[f"{PREFIX}-async-tag-{unique_suffix}"],
                panels=[
                    {
                        "type": "markdown",
                        "grid": {"x": 0, "y": 0, "w": 48, "h": 6},
                        "config": {
                            "content": "async markdown",
                            "settings": {},
                        },
                    }
                ],
            )
            dashboard_id = created.body["id"]
            assert created.body["data"]["title"] == title

            fetched = await client.dashboards.get(id=dashboard_id)
            assert fetched.body["data"]["description"] == "async round-trip"
            assert fetched.body["data"]["panels"][0]["type"] == "markdown"
            assert (
                fetched.body["data"]["panels"][0]["config"]["content"]
                == "async markdown"
            )

            updated = await client.dashboards.update(
                id=dashboard_id, title=f"{title}-updated"
            )
            assert updated.body["data"]["title"] == f"{title}-updated"

            results = await client.dashboards.get_all(query=f"{title}*")
            assert results.body["total"] == 1
            assert results.body["dashboards"][0]["id"] == dashboard_id

            deleted = await client.dashboards.delete(id=dashboard_id)
            assert deleted.meta.status == 204
            dashboard_id = None
        finally:
            if dashboard_id is not None:
                try:
                    await client.dashboards.delete(id=dashboard_id)
                except Exception:
                    pass
            await client.close()
