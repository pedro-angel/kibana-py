"""Unit tests for ShortUrlsClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.short_urls import ShortUrlsClient
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


class TestShortUrlsClientInitialization:
    """Test ShortUrlsClient initialization."""

    def test_short_urls_client_initialization(self, mock_transport):
        """Test that ShortUrlsClient can be initialized with a parent client."""
        client = Kibana(_transport=mock_transport)
        short_urls_client = ShortUrlsClient(client)
        assert short_urls_client._client is client

    def test_short_urls_property_returns_client(self, mock_transport):
        """Test that client.short_urls returns a ShortUrlsClient instance."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.short_urls, ShortUrlsClient)

    def test_short_urls_property_caching(self, mock_transport):
        """Test that the short_urls property returns the same instance."""
        client = Kibana(_transport=mock_transport)
        assert client.short_urls is client.short_urls


class TestShortUrlsClientCreate:
    """Test ShortUrlsClient.create() method."""

    def test_create_minimal(self, mock_transport):
        """Test creating a short URL with only the required parameters."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=_short_url_body(),
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.short_urls.create(
            locator_id="LEGACY_SHORT_URL_LOCATOR",
            params={"url": "/app/dashboards"},
        )

        assert result.body["id"] == "7f2f37bc-4b1e-467d-97cc-d64b0e20df6f"
        assert result.body["slug"] == "0rRBq"

        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/short_url"
        assert call_kwargs["body"] == {
            "locatorId": "LEGACY_SHORT_URL_LOCATOR",
            "params": {"url": "/app/dashboards"},
        }
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_create_with_custom_slug(self, mock_transport):
        """Test creating a short URL with a custom slug."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=_short_url_body(slug="my-dashboards"),
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.short_urls.create(
            locator_id="LEGACY_SHORT_URL_LOCATOR",
            params={"url": "/app/dashboards"},
            slug="my-dashboards",
        )

        assert result.body["slug"] == "my-dashboards"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "locatorId": "LEGACY_SHORT_URL_LOCATOR",
            "params": {"url": "/app/dashboards"},
            "slug": "my-dashboards",
        }

    def test_create_with_human_readable_slug(self, mock_transport):
        """Test creating a short URL requesting a human-readable slug."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=_short_url_body(),
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.short_urls.create(
            locator_id="LEGACY_SHORT_URL_LOCATOR",
            params={"url": "/app/dashboards"},
            human_readable_slug=True,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"]["humanReadableSlug"] is True
        assert "slug" not in call_kwargs["body"]

    def test_create_in_space(self, mock_transport):
        """Test creating a short URL in a specific space."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=_short_url_body(),
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.short_urls.create(
            locator_id="LEGACY_SHORT_URL_LOCATOR",
            params={"url": "/app/dashboards"},
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/short_url"


class TestShortUrlsClientGet:
    """Test ShortUrlsClient.get() method."""

    def test_get_success(self, mock_transport):
        """Test getting a short URL by ID."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=_short_url_body(),
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.short_urls.get(id="7f2f37bc-4b1e-467d-97cc-d64b0e20df6f")

        assert result.body["locator"]["id"] == "LEGACY_SHORT_URL_LOCATOR"

        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert (
            call_kwargs["target"]
            == "/api/short_url/7f2f37bc-4b1e-467d-97cc-d64b0e20df6f"
        )
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert call_kwargs.get("body") is None

    def test_get_url_encodes_id(self, mock_transport):
        """Test that the short URL ID is URL-encoded in the path."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=_short_url_body(),
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.short_urls.get(id="id with/special")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/short_url/id%20with%2Fspecial"

    def test_get_in_space(self, mock_transport):
        """Test getting a short URL from a specific space."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=_short_url_body(),
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.short_urls.get(id="abc123", space_id="marketing", validate_spaces=False)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/short_url/abc123"


class TestShortUrlsClientResolve:
    """Test ShortUrlsClient.resolve() method."""

    def test_resolve_success(self, mock_transport):
        """Test resolving a short URL by slug."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=_short_url_body(slug="my-dashboards"),
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.short_urls.resolve(slug="my-dashboards")

        assert result.body["slug"] == "my-dashboards"

        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/short_url/_slug/my-dashboards"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    def test_resolve_url_encodes_slug(self, mock_transport):
        """Test that the slug is URL-encoded in the path."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=_short_url_body(),
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.short_urls.resolve(slug="a slug/x")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/short_url/_slug/a%20slug%2Fx"

    def test_resolve_in_space(self, mock_transport):
        """Test resolving a short URL in a specific space."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=_short_url_body(),
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.short_urls.resolve(
            slug="my-slug", space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/short_url/_slug/my-slug"


class TestShortUrlsClientDelete:
    """Test ShortUrlsClient.delete() method."""

    def test_delete_success(self, mock_transport):
        """Test deleting a short URL by ID."""
        # Live Kibana 9.4.3 returns a JSON `null` body with HTTP 200
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=None,
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.short_urls.delete(id="7f2f37bc-4b1e-467d-97cc-d64b0e20df6f")

        assert not result.body

        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert (
            call_kwargs["target"]
            == "/api/short_url/7f2f37bc-4b1e-467d-97cc-d64b0e20df6f"
        )
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs.get("body") is None

    def test_delete_in_space(self, mock_transport):
        """Test deleting a short URL from a specific space."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=None,
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.short_urls.delete(
            id="abc123", space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/short_url/abc123"


class TestShortUrlsClientErrorHandling:
    """Test ShortUrlsClient error handling."""

    def test_get_not_found_error(self, mock_transport):
        """Test that a 404 response raises NotFoundError."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Saved object [url/nope] not found",
            },
            meta=Mock(status=404, headers={}),
        )

        client = Kibana(_transport=mock_transport)

        with pytest.raises(NotFoundError):
            client.short_urls.get(id="nope")

    def test_create_authorization_error(self, mock_transport):
        """Test that a 403 response raises AuthorizationException."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 403,
                "error": "Forbidden",
                "message": "Insufficient privileges",
            },
            meta=Mock(status=403, headers={}),
        )

        client = Kibana(_transport=mock_transport)

        with pytest.raises(AuthorizationException):
            client.short_urls.create(
                locator_id="LEGACY_SHORT_URL_LOCATOR",
                params={"url": "/app/dashboards"},
            )
