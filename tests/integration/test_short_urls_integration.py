"""Integration tests for ShortUrlsClient against a live Kibana instance."""

import uuid

import pytest

from kibana.exceptions import NotFoundError

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

LOCATOR_ID = "LEGACY_SHORT_URL_LOCATOR"


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
def unique_slug():
    """Generate a unique, prefixed slug for testing."""
    return f"kbnpy-short-urls-{uuid.uuid4().hex[:12]}"


def _cleanup_short_url(client, short_url_id: str, space_id: str | None = None) -> None:
    """Delete a short URL, ignoring the case where it is already gone."""
    try:
        client.short_urls.delete(id=short_url_id, space_id=space_id)
    except NotFoundError:
        pass


class TestShortUrlsLifecycle:
    """Full lifecycle tests for the Short URLs API."""

    def test_create_get_resolve_delete(self, kibana_client, unique_slug):
        """Test the full short URL lifecycle with a custom slug."""
        created = kibana_client.short_urls.create(
            locator_id=LOCATOR_ID,
            params={"url": "/app/dashboards"},
            slug=unique_slug,
        )
        short_url_id = created.body["id"]
        try:
            assert created.meta.status == 200
            assert created.body["slug"] == unique_slug
            assert created.body["locator"]["id"] == LOCATOR_ID
            assert created.body["locator"]["state"] == {"url": "/app/dashboards"}

            # Get by ID
            fetched = kibana_client.short_urls.get(id=short_url_id)
            assert fetched.body["id"] == short_url_id
            assert fetched.body["slug"] == unique_slug

            # Resolve by slug
            resolved = kibana_client.short_urls.resolve(slug=unique_slug)
            assert resolved.body["id"] == short_url_id
            assert resolved.body["locator"]["state"] == {"url": "/app/dashboards"}
        finally:
            _cleanup_short_url(kibana_client, short_url_id)

        # After deletion the short URL must be gone
        with pytest.raises(NotFoundError):
            kibana_client.short_urls.get(id=short_url_id)
        with pytest.raises(NotFoundError):
            kibana_client.short_urls.resolve(slug=unique_slug)

    def test_create_with_generated_slug(self, kibana_client):
        """Test creating a short URL with a server-generated slug."""
        created = kibana_client.short_urls.create(
            locator_id=LOCATOR_ID,
            params={"url": "/app/discover"},
            human_readable_slug=True,
        )
        short_url_id = created.body["id"]
        try:
            slug = created.body["slug"]
            assert isinstance(slug, str) and len(slug) >= 3

            resolved = kibana_client.short_urls.resolve(slug=slug)
            assert resolved.body["id"] == short_url_id
        finally:
            _cleanup_short_url(kibana_client, short_url_id)

    def test_get_missing_short_url_raises_not_found(self, kibana_client):
        """Test that getting a nonexistent short URL raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.short_urls.get(id=f"kbnpy-short-urls-missing-{uuid.uuid4()}")

    def test_resolve_missing_slug_raises_not_found(self, kibana_client):
        """Test that resolving a nonexistent slug raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.short_urls.resolve(
                slug=f"kbnpy-short-urls-missing-{uuid.uuid4().hex[:8]}"
            )


class TestShortUrlsSpaceScoped:
    """Space-scoped tests for the Short URLs API."""

    def test_short_url_is_space_scoped(self, kibana_client, unique_slug):
        """Test that a short URL created in a space is not visible elsewhere."""
        space_id = f"kbnpy-short-urls-{uuid.uuid4().hex[:8]}"
        kibana_client.spaces.create(id=space_id, name=space_id)
        short_url_id = None
        try:
            created = kibana_client.short_urls.create(
                locator_id=LOCATOR_ID,
                params={"url": "/app/dashboards"},
                slug=unique_slug,
                space_id=space_id,
            )
            short_url_id = created.body["id"]

            # Visible in its own space
            resolved = kibana_client.short_urls.resolve(
                slug=unique_slug, space_id=space_id
            )
            assert resolved.body["id"] == short_url_id

            # Not visible in the default space
            with pytest.raises(NotFoundError):
                kibana_client.short_urls.resolve(slug=unique_slug)
        finally:
            if short_url_id is not None:
                _cleanup_short_url(kibana_client, short_url_id, space_id=space_id)
            kibana_client.spaces.delete(id=space_id)


class TestAsyncShortUrlsLifecycle:
    """Async round-trip test for the Short URLs API."""

    @pytest.mark.asyncio
    async def test_async_create_get_resolve_delete(
        self, async_kibana_client, unique_slug
    ):
        """Test the full short URL lifecycle with the async client."""
        created = await async_kibana_client.short_urls.create(
            locator_id=LOCATOR_ID,
            params={"url": "/app/dashboards"},
            slug=unique_slug,
        )
        short_url_id = created.body["id"]
        try:
            assert created.body["slug"] == unique_slug

            fetched = await async_kibana_client.short_urls.get(id=short_url_id)
            assert fetched.body["id"] == short_url_id

            resolved = await async_kibana_client.short_urls.resolve(slug=unique_slug)
            assert resolved.body["id"] == short_url_id
        finally:
            try:
                await async_kibana_client.short_urls.delete(id=short_url_id)
            except NotFoundError:
                pass

        with pytest.raises(NotFoundError):
            await async_kibana_client.short_urls.get(id=short_url_id)
