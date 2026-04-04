"""Unit tests for BaseClient."""

from unittest.mock import patch

import pytest
from elastic_transport import HttpHeaders

from kibana.exceptions import (
    ApiError,
    AuthenticationException,
    AuthorizationException,
    BadRequestError,
    ConflictError,
    NotFoundError,
)


class TestBaseClientInitialization:
    """Tests for BaseClient initialization."""

    def test_init_with_transport(self, mock_transport):
        """Test BaseClient initialization with a Transport instance."""
        from kibana._sync.client._base import BaseClient

        client = BaseClient(_transport=mock_transport)

        assert client._transport is mock_transport
        assert isinstance(client._headers, HttpHeaders)


class TestPerformRequest:
    """Tests for BaseClient.perform_request() method."""

    def test_perform_request_calls_transport(self, mock_transport, mock_response):
        """Test that perform_request calls transport.perform_request."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"result": "success"}, status=200
        )

        client = BaseClient(_transport=mock_transport)
        response = client.perform_request("GET", "/api/status")

        mock_transport.perform_request.assert_called_once()
        assert response.body == {"result": "success"}

    def test_perform_request_with_params(self, mock_transport, mock_response):
        """Test perform_request with query parameters."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"items": []}, status=200
        )

        client = BaseClient(_transport=mock_transport)
        client.perform_request(
            "GET", "/api/saved_objects/_find", params={"type": "dashboard"}
        )

        call_args = mock_transport.perform_request.call_args
        # Params should be encoded in the target URL
        assert "target" in call_args[1]
        assert "type=dashboard" in call_args[1]["target"]

    def test_perform_request_with_body(self, mock_transport, mock_response):
        """Test perform_request with request body."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-id"}, status=200
        )

        client = BaseClient(_transport=mock_transport)
        body_data = {"attributes": {"title": "Test"}}
        client.perform_request("POST", "/api/saved_objects/dashboard", body=body_data)

        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["body"] == body_data

    def test_perform_request_with_headers(self, mock_transport, mock_response):
        """Test perform_request with custom headers."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(body={}, status=200)

        client = BaseClient(_transport=mock_transport)
        headers = {"X-Custom-Header": "value"}
        client.perform_request("GET", "/api/status", headers=headers)

        call_args = mock_transport.perform_request.call_args
        assert "headers" in call_args[1]

    def test_perform_request_processes_successful_response(
        self, mock_transport, mock_response
    ):
        """Test that successful responses are returned without raising exceptions."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"status": "green"}, status=200
        )

        client = BaseClient(_transport=mock_transport)
        response = client.perform_request("GET", "/api/status")

        assert response.body == {"status": "green"}
        assert response.meta.status == 200


class TestErrorResponseProcessing:
    """Tests for error response processing."""

    def test_400_raises_bad_request_error(self, mock_transport, mock_response):
        """Test that 400 status raises BadRequestError."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": "Invalid request"}, status=400
        )

        client = BaseClient(_transport=mock_transport)

        with pytest.raises(BadRequestError) as exc_info:
            client.perform_request("POST", "/api/saved_objects/dashboard")

        assert exc_info.value.status_code == 400
        assert exc_info.value.body == {"error": "Invalid request"}

    def test_401_raises_authentication_exception(self, mock_transport, mock_response):
        """Test that 401 status raises AuthenticationException."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": "Unauthorized"}, status=401
        )

        client = BaseClient(_transport=mock_transport)

        with pytest.raises(AuthenticationException) as exc_info:
            client.perform_request("GET", "/api/status")

        assert exc_info.value.status_code == 401

    def test_403_raises_authorization_exception(self, mock_transport, mock_response):
        """Test that 403 status raises AuthorizationException."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": "Forbidden"}, status=403
        )

        client = BaseClient(_transport=mock_transport)

        with pytest.raises(AuthorizationException) as exc_info:
            client.perform_request("GET", "/api/spaces/space")

        assert exc_info.value.status_code == 403

    def test_404_raises_not_found_error(self, mock_transport, mock_response):
        """Test that 404 status raises NotFoundError."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": "Not found"}, status=404
        )

        client = BaseClient(_transport=mock_transport)

        with pytest.raises(NotFoundError) as exc_info:
            client.perform_request("GET", "/api/saved_objects/dashboard/missing")

        assert exc_info.value.status_code == 404

    def test_409_raises_conflict_error(self, mock_transport, mock_response):
        """Test that 409 status raises ConflictError."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": "Conflict"}, status=409
        )

        client = BaseClient(_transport=mock_transport)

        with pytest.raises(ConflictError) as exc_info:
            client.perform_request("POST", "/api/saved_objects/dashboard")

        assert exc_info.value.status_code == 409

    def test_500_raises_generic_api_error(self, mock_transport, mock_response):
        """Test that unmapped status codes raise generic ApiError."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": "Internal server error"}, status=500
        )

        client = BaseClient(_transport=mock_transport)

        with pytest.raises(ApiError) as exc_info:
            client.perform_request("GET", "/api/status")

        assert exc_info.value.status_code == 500

    def test_error_includes_response_meta(self, mock_transport, mock_response):
        """Test that errors include response metadata."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": "Not found"}, status=404
        )

        client = BaseClient(_transport=mock_transport)

        with pytest.raises(NotFoundError) as exc_info:
            client.perform_request("GET", "/api/saved_objects/dashboard/missing")

        assert exc_info.value.meta is not None
        assert exc_info.value.meta.status == 404


class TestOptionsMethod:
    """Tests for BaseClient.options() method."""

    def test_options_creates_new_instance(self, mock_transport):
        """Test that options() creates a new client instance."""
        from kibana._sync.client._base import BaseClient

        client = BaseClient(_transport=mock_transport)
        new_client = client.options(request_timeout=30)

        assert new_client is not client
        assert isinstance(new_client, BaseClient)

    def test_options_with_api_key_string(self, mock_transport):
        """Test options() stores API key string on new client."""
        from kibana._sync.client._base import BaseClient

        client = BaseClient(_transport=mock_transport)
        new_client = client.options(api_key="test_api_key")

        assert new_client is not client
        assert new_client._api_key == "test_api_key"

    def test_options_with_api_key_tuple(self, mock_transport):
        """Test options() stores API key tuple on new client."""
        from kibana._sync.client._base import BaseClient

        client = BaseClient(_transport=mock_transport)
        new_client = client.options(api_key=("id", "key"))

        assert new_client is not client
        assert new_client._api_key == ("id", "key")

    def test_options_with_basic_auth(self, mock_transport):
        """Test options() stores basic auth credentials on new client."""
        from kibana._sync.client._base import BaseClient

        client = BaseClient(_transport=mock_transport)
        new_client = client.options(basic_auth=("username", "password"))

        assert new_client is not client
        assert new_client._basic_auth == ("username", "password")

    def test_options_with_bearer_auth(self, mock_transport):
        """Test options() stores bearer token on new client."""
        from kibana._sync.client._base import BaseClient

        client = BaseClient(_transport=mock_transport)
        new_client = client.options(bearer_auth="bearer_token")

        assert new_client is not client
        assert new_client._bearer_auth == "bearer_token"

    def test_options_with_headers(self, mock_transport):
        """Test options() stores custom headers on new client."""
        from kibana._sync.client._base import BaseClient

        client = BaseClient(_transport=mock_transport)
        new_client = client.options(headers={"X-Custom": "value"})

        assert new_client is not client
        assert new_client._custom_headers == {"X-Custom": "value"}

    def test_options_with_request_timeout(self, mock_transport):
        """Test options() stores request timeout on new client."""
        from kibana._sync.client._base import BaseClient

        client = BaseClient(_transport=mock_transport)
        new_client = client.options(request_timeout=60.0)

        assert new_client is not client
        assert new_client._request_timeout == 60.0

    def test_options_preserves_transport(self, mock_transport):
        """Test that options() preserves the transport instance."""
        from kibana._sync.client._base import BaseClient

        client = BaseClient(_transport=mock_transport)
        new_client = client.options(request_timeout=30)

        # Both should reference the same transport
        assert new_client._transport is mock_transport


class TestAuthenticationHeaderResolution:
    """Tests for authentication header resolution."""

    def test_resolve_auth_headers_with_api_key_string(self):
        """Test resolving auth headers with API key as string."""
        from kibana._sync.client._base import resolve_auth_headers

        headers = resolve_auth_headers(api_key="test_api_key_string")

        assert "authorization" in headers
        assert headers["authorization"].startswith("ApiKey ")

    def test_resolve_auth_headers_with_api_key_tuple(self):
        """Test resolving auth headers with API key as tuple."""
        from kibana._sync.client._base import resolve_auth_headers

        headers = resolve_auth_headers(api_key=("id", "key"))

        assert "authorization" in headers
        assert headers["authorization"].startswith("ApiKey ")

    def test_resolve_auth_headers_with_basic_auth(self):
        """Test resolving auth headers with basic authentication."""
        from kibana._sync.client._base import resolve_auth_headers

        headers = resolve_auth_headers(basic_auth=("username", "password"))

        assert "authorization" in headers
        assert headers["authorization"].startswith("Basic ")

    def test_resolve_auth_headers_with_bearer_auth(self):
        """Test resolving auth headers with bearer token."""
        from kibana._sync.client._base import resolve_auth_headers

        headers = resolve_auth_headers(bearer_auth="test_token")

        assert "authorization" in headers
        assert headers["authorization"] == "Bearer test_token"

    def test_resolve_auth_headers_returns_empty_when_no_auth(self):
        """Test that resolve_auth_headers returns empty dict when no auth provided."""
        from kibana._sync.client._base import resolve_auth_headers

        headers = resolve_auth_headers()

        assert headers == {}

    def test_resolve_auth_headers_api_key_takes_precedence_over_basic(self):
        """Test that API key takes precedence over basic auth."""
        from kibana._sync.client._base import resolve_auth_headers

        headers = resolve_auth_headers(api_key="test_key", basic_auth=("user", "pass"))

        assert headers["authorization"].startswith("ApiKey ")

    def test_resolve_auth_headers_api_key_takes_precedence_over_bearer(self):
        """Test that API key takes precedence over bearer auth."""
        from kibana._sync.client._base import resolve_auth_headers

        headers = resolve_auth_headers(api_key="test_key", bearer_auth="token")

        assert headers["authorization"].startswith("ApiKey ")

    def test_resolve_auth_headers_basic_takes_precedence_over_bearer(self):
        """Test that basic auth takes precedence over bearer auth."""
        from kibana._sync.client._base import resolve_auth_headers

        headers = resolve_auth_headers(basic_auth=("user", "pass"), bearer_auth="token")

        assert headers["authorization"].startswith("Basic ")


class TestLogging:
    """Tests for logging functionality."""

    @patch("kibana._sync.client._base.logger")
    def test_perform_request_logs_debug(
        self, mock_logger, mock_transport, mock_response
    ):
        """Test that perform_request logs at DEBUG level."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"result": "success"}, status=200
        )

        client = BaseClient(_transport=mock_transport)
        client.perform_request("GET", "/api/status")

        # Verify debug logging was called
        assert mock_logger.debug.called

    @patch("kibana._sync.client._base.logger")
    def test_error_response_logs_at_debug_level(
        self, mock_logger, mock_transport, mock_response
    ):
        """Test that error responses are logged at DEBUG level."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": "Not found"}, status=404
        )

        client = BaseClient(_transport=mock_transport)

        with pytest.raises(NotFoundError):
            client.perform_request("GET", "/api/saved_objects/dashboard/missing")

        assert mock_logger.debug.called


class TestExtractErrorMessage:
    """Tests for BaseClient._extract_error_message()."""

    def _extract(self, body):
        from unittest.mock import Mock

        from kibana._sync.client._base import BaseClient

        client = BaseClient(_transport=Mock())
        return client._extract_error_message(body)

    def test_error_as_string(self):
        """Test extraction when 'error' is a plain string."""
        assert self._extract({"error": "Something failed"}) == "Something failed"

    def test_error_as_dict_with_message(self):
        """Test extraction from error.message nested structure."""
        body = {"error": {"message": "Detailed error", "code": 500}}
        assert self._extract(body) == "Detailed error"

    def test_error_as_dict_with_reason(self):
        """Test extraction from error.reason when message is absent."""
        body = {"error": {"reason": "Some reason", "type": "exception"}}
        assert self._extract(body) == "Some reason"

    def test_error_as_dict_without_message_or_reason(self):
        """Test fallback when error dict has neither message nor reason."""
        body = {"error": {"code": 500}}
        result = self._extract(body)
        assert result.startswith("API error occurred:")

    def test_message_field_directly(self):
        """Test extraction from top-level 'message' field."""
        assert self._extract({"message": "Top-level message"}) == "Top-level message"

    def test_non_dict_body(self):
        """Test fallback for non-dict body."""
        result = self._extract("plain string error")
        assert result == "API error occurred: plain string error"

    def test_empty_dict_body(self):
        """Test fallback for empty dict."""
        result = self._extract({})
        assert result == "API error occurred: {}"

    def test_error_field_takes_precedence_over_message(self):
        """Test that 'error' field is checked before 'message' field."""
        body = {"error": "Error wins", "message": "Message loses"}
        assert self._extract(body) == "Error wins"


class TestUnmappedStatusCodes:
    """Tests for HTTP status codes not in HTTP_EXCEPTIONS."""

    def test_429_raises_api_error(self, mock_transport, mock_response):
        """Test that 429 Too Many Requests raises generic ApiError."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": "Too many requests"}, status=429
        )

        client = BaseClient(_transport=mock_transport)

        with pytest.raises(ApiError) as exc_info:
            client.perform_request("GET", "/api/status")

        assert exc_info.value.status_code == 429
        assert not isinstance(exc_info.value, BadRequestError | NotFoundError)

    def test_502_raises_api_error(self, mock_transport, mock_response):
        """Test that 502 Bad Gateway raises generic ApiError."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": "Bad gateway"}, status=502
        )

        client = BaseClient(_transport=mock_transport)

        with pytest.raises(ApiError) as exc_info:
            client.perform_request("GET", "/api/status")

        assert exc_info.value.status_code == 502

    def test_503_raises_api_error(self, mock_transport, mock_response):
        """Test that 503 Service Unavailable raises generic ApiError."""
        from kibana._sync.client._base import BaseClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": "Service unavailable"}, status=503
        )

        client = BaseClient(_transport=mock_transport)

        with pytest.raises(ApiError) as exc_info:
            client.perform_request("GET", "/api/status")

        assert exc_info.value.status_code == 503
