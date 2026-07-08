"""Unit tests for AsyncShortUrlsClient."""

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client.short_urls import AsyncShortUrlsClient
from kibana.exceptions import AuthorizationException, NotFoundError


def _short_url_body(**overrides):
    """Build a representative short URL response body."""
    body = {
        "id": "7f2f37bc-4b1e-467d-97cc-d64b0e20df6f",
        "locator": {
            "id": "LEGACY_SHORT_URL_LOCATOR",
            "version": "9.4.3",
            "state": {"url": "/app/dashboards"},
        },
        "accessCount": 0,
        "accessDate": 1783103966094,
        "createDate": 1783103966094,
        "slug": "0rRBq",
        "url": "",
    }
    body.update(overrides)
    return body


class TestAsyncShortUrlsClientInitialization:
    """Test AsyncShortUrlsClient initialization."""

    @pytest.mark.asyncio
    async def test_short_urls_client_initialization(self, mock_async_transport):
        """Test that AsyncShortUrlsClient can be initialized with a parent client."""
        client = AsyncKibana(_transport=mock_async_transport)
        short_urls_client = AsyncShortUrlsClient(client)
        assert short_urls_client._client is client

    @pytest.mark.asyncio
    async def test_short_urls_property_returns_client(self, mock_async_transport):
        """Test that client.short_urls returns an AsyncShortUrlsClient instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.short_urls, AsyncShortUrlsClient)

    @pytest.mark.asyncio
    async def test_short_urls_property_caching(self, mock_async_transport):
        """Test that the short_urls property returns the same instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert client.short_urls is client.short_urls


class TestAsyncShortUrlsClientCreate:
    """Test AsyncShortUrlsClient.create() method."""

    @pytest.mark.asyncio
    async def test_create_minimal(self, mock_async_transport, mock_response):
        """Test creating a short URL with only the required parameters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_short_url_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.short_urls.create(
            locator_id="LEGACY_SHORT_URL_LOCATOR",
            params={"url": "/app/dashboards"},
        )

        assert result.body["id"] == "7f2f37bc-4b1e-467d-97cc-d64b0e20df6f"
        assert result.body["slug"] == "0rRBq"

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/short_url"
        assert call_kwargs["body"] == {
            "locatorId": "LEGACY_SHORT_URL_LOCATOR",
            "params": {"url": "/app/dashboards"},
        }
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    @pytest.mark.asyncio
    async def test_create_with_custom_slug(self, mock_async_transport, mock_response):
        """Test creating a short URL with a custom slug."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_short_url_body(slug="my-dashboards")
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.short_urls.create(
            locator_id="LEGACY_SHORT_URL_LOCATOR",
            params={"url": "/app/dashboards"},
            slug="my-dashboards",
        )

        assert result.body["slug"] == "my-dashboards"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "locatorId": "LEGACY_SHORT_URL_LOCATOR",
            "params": {"url": "/app/dashboards"},
            "slug": "my-dashboards",
        }

    @pytest.mark.asyncio
    async def test_create_with_human_readable_slug(
        self, mock_async_transport, mock_response
    ):
        """Test creating a short URL requesting a human-readable slug."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_short_url_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.short_urls.create(
            locator_id="LEGACY_SHORT_URL_LOCATOR",
            params={"url": "/app/dashboards"},
            human_readable_slug=True,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"]["humanReadableSlug"] is True
        assert "slug" not in call_kwargs["body"]

    @pytest.mark.asyncio
    async def test_create_in_space(self, mock_async_transport, mock_response):
        """Test creating a short URL in a specific space."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_short_url_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.short_urls.create(
            locator_id="LEGACY_SHORT_URL_LOCATOR",
            params={"url": "/app/dashboards"},
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/short_url"


class TestAsyncShortUrlsClientGet:
    """Test AsyncShortUrlsClient.get() method."""

    @pytest.mark.asyncio
    async def test_get_success(self, mock_async_transport, mock_response):
        """Test getting a short URL by ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_short_url_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.short_urls.get(id="7f2f37bc-4b1e-467d-97cc-d64b0e20df6f")

        assert result.body["locator"]["id"] == "LEGACY_SHORT_URL_LOCATOR"

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert (
            call_kwargs["target"]
            == "/api/short_url/7f2f37bc-4b1e-467d-97cc-d64b0e20df6f"
        )
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_get_url_encodes_id(self, mock_async_transport, mock_response):
        """Test that the short URL ID is URL-encoded in the path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_short_url_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.short_urls.get(id="id with/special")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/short_url/id%20with%2Fspecial"

    @pytest.mark.asyncio
    async def test_get_in_space(self, mock_async_transport, mock_response):
        """Test getting a short URL from a specific space."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_short_url_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.short_urls.get(
            id="abc123", space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/short_url/abc123"


class TestAsyncShortUrlsClientResolve:
    """Test AsyncShortUrlsClient.resolve() method."""

    @pytest.mark.asyncio
    async def test_resolve_success(self, mock_async_transport, mock_response):
        """Test resolving a short URL by slug."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_short_url_body(slug="my-dashboards")
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.short_urls.resolve(slug="my-dashboards")

        assert result.body["slug"] == "my-dashboards"

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/short_url/_slug/my-dashboards"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    @pytest.mark.asyncio
    async def test_resolve_url_encodes_slug(self, mock_async_transport, mock_response):
        """Test that the slug is URL-encoded in the path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_short_url_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.short_urls.resolve(slug="a slug/x")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/short_url/_slug/a%20slug%2Fx"

    @pytest.mark.asyncio
    async def test_resolve_in_space(self, mock_async_transport, mock_response):
        """Test resolving a short URL in a specific space."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_short_url_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.short_urls.resolve(
            slug="my-slug", space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/short_url/_slug/my-slug"


class TestAsyncShortUrlsClientDelete:
    """Test AsyncShortUrlsClient.delete() method."""

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_async_transport, mock_response):
        """Test deleting a short URL by ID."""
        # Live Kibana 9.4.3 returns a JSON `null` body with HTTP 200
        mock_async_transport.perform_request.return_value = mock_response(body=None)

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.short_urls.delete(
            id="7f2f37bc-4b1e-467d-97cc-d64b0e20df6f"
        )

        assert not result.body

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert (
            call_kwargs["target"]
            == "/api/short_url/7f2f37bc-4b1e-467d-97cc-d64b0e20df6f"
        )
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_delete_in_space(self, mock_async_transport, mock_response):
        """Test deleting a short URL from a specific space."""
        mock_async_transport.perform_request.return_value = mock_response(body=None)

        client = AsyncKibana(_transport=mock_async_transport)
        await client.short_urls.delete(
            id="abc123", space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/short_url/abc123"


class TestAsyncShortUrlsClientErrorHandling:
    """Test AsyncShortUrlsClient error handling."""

    @pytest.mark.asyncio
    async def test_get_not_found_error(self, mock_async_transport, mock_response):
        """Test that a 404 response raises NotFoundError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Saved object [url/nope] not found",
            },
            status=404,
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(NotFoundError):
            await client.short_urls.get(id="nope")

    @pytest.mark.asyncio
    async def test_create_authorization_error(
        self, mock_async_transport, mock_response
    ):
        """Test that a 403 response raises AuthorizationException."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 403,
                "error": "Forbidden",
                "message": "Insufficient privileges",
            },
            status=403,
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(AuthorizationException):
            await client.short_urls.create(
                locator_id="LEGACY_SHORT_URL_LOCATOR",
                params={"url": "/app/dashboards"},
            )
