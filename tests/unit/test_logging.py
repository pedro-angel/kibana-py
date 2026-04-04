"""Unit tests for logging functionality."""

import logging
from unittest.mock import MagicMock

import pytest
from elastic_transport import ApiResponseMeta, ObjectApiResponse

from kibana._sync.client._base import BaseClient, _redact_sensitive_headers
from kibana._utils import deprecated, warn_deprecated


class TestSensitiveDataRedaction:
    """Test sensitive data redaction in headers."""

    def test_redact_authorization_header_api_key(self):
        """Test redaction of API key authorization header."""
        headers = {"authorization": "ApiKey dGVzdDp0ZXN0"}
        redacted = _redact_sensitive_headers(headers)
        assert redacted["authorization"] == "ApiKey [REDACTED]"

    def test_redact_authorization_header_basic(self):
        """Test redaction of basic auth authorization header."""
        headers = {"authorization": "Basic dXNlcjpwYXNz"}
        redacted = _redact_sensitive_headers(headers)
        assert redacted["authorization"] == "Basic [REDACTED]"

    def test_redact_authorization_header_bearer(self):
        """Test redaction of bearer token authorization header."""
        headers = {"authorization": "Bearer secret-token"}
        redacted = _redact_sensitive_headers(headers)
        assert redacted["authorization"] == "Bearer [REDACTED]"

    def test_redact_api_key_header(self):
        """Test redaction of x-api-key header."""
        headers = {"x-api-key": "secret-key"}
        redacted = _redact_sensitive_headers(headers)
        assert redacted["x-api-key"] == "[REDACTED]"

    def test_redact_case_insensitive(self):
        """Test that redaction is case-insensitive."""
        headers = {
            "Authorization": "ApiKey test",
            "X-API-Key": "secret",
            "API-KEY": "another-secret",
        }
        redacted = _redact_sensitive_headers(headers)
        assert redacted["Authorization"] == "ApiKey [REDACTED]"
        assert redacted["X-API-Key"] == "[REDACTED]"
        assert redacted["API-KEY"] == "[REDACTED]"

    def test_preserve_non_sensitive_headers(self):
        """Test that non-sensitive headers are preserved."""
        headers = {
            "content-type": "application/json",
            "kbn-xsrf": "true",
            "x-custom-header": "value",
        }
        redacted = _redact_sensitive_headers(headers)
        assert redacted == headers

    def test_mixed_headers(self):
        """Test redaction with mixed sensitive and non-sensitive headers."""
        headers = {
            "authorization": "Bearer token",
            "content-type": "application/json",
            "x-api-key": "secret",
            "kbn-xsrf": "true",
        }
        redacted = _redact_sensitive_headers(headers)
        assert redacted["authorization"] == "Bearer [REDACTED]"
        assert redacted["content-type"] == "application/json"
        assert redacted["x-api-key"] == "[REDACTED]"
        assert redacted["kbn-xsrf"] == "true"


class TestRequestResponseLogging:
    """Test request and response logging."""

    @pytest.fixture
    def mock_transport(self):
        """Create a mock transport."""
        transport = MagicMock()
        transport.perform_request.return_value = ObjectApiResponse(
            body={"id": "test-id", "result": "success"},
            meta=ApiResponseMeta(
                status=200,
                headers={},
                http_version="1.1",
                duration=0.1,
                node=None,
            ),
        )
        return transport

    @pytest.fixture
    def client(self, mock_transport):
        """Create a test client."""
        client = BaseClient(_transport=mock_transport)
        client._api_key = "test-key"
        return client

    def test_debug_logging_request(self, client, mock_transport, caplog):
        """Test that request details are logged at DEBUG level."""
        with caplog.at_level(logging.DEBUG, logger="kibana"):
            client.perform_request("GET", "/api/test")

        # Check that request was logged
        assert any("Making GET request" in record.message for record in caplog.records)
        assert any("/api/test" in record.message for record in caplog.records)

    def test_debug_logging_redacts_auth_headers(self, client, mock_transport, caplog):
        """Test that auth headers are redacted in logs."""
        with caplog.at_level(logging.DEBUG, logger="kibana"):
            client.perform_request("GET", "/api/test")

        # Check that authorization header is redacted
        log_messages = " ".join(record.message for record in caplog.records)
        assert "[REDACTED]" in log_messages
        assert "test-key" not in log_messages

    def test_debug_logging_request_body(self, client, mock_transport, caplog):
        """Test that request body is logged at DEBUG level."""
        body = {"name": "test", "value": 123}

        with caplog.at_level(logging.DEBUG, logger="kibana"):
            client.perform_request("POST", "/api/test", body=body)

        # Check that body was logged
        assert any("Request body:" in record.message for record in caplog.records)
        assert any("test" in record.message for record in caplog.records)

    def test_debug_logging_response(self, client, mock_transport, caplog):
        """Test that response is logged at DEBUG level."""
        with caplog.at_level(logging.DEBUG, logger="kibana"):
            client.perform_request("GET", "/api/test")

        # Check that response was logged
        assert any(
            "Request completed successfully" in record.message
            for record in caplog.records
        )
        assert any("Response body:" in record.message for record in caplog.records)

    def test_debug_logging_truncates_large_response(
        self, client, mock_transport, caplog
    ):
        """Test that large responses are truncated in logs."""
        # Create a large response
        large_body = {"data": "x" * 1000}
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=large_body,
            meta=ApiResponseMeta(
                status=200,
                headers={},
                http_version="1.1",
                duration=0.1,
                node=None,
            ),
        )

        with caplog.at_level(logging.DEBUG, logger="kibana"):
            client.perform_request("GET", "/api/test")

        # Check that response was truncated
        assert any("[truncated]" in record.message for record in caplog.records)

    def test_no_debug_logging_when_disabled(self, client, mock_transport, caplog):
        """Test that DEBUG logs are not generated when logging level is higher."""
        with caplog.at_level(logging.INFO, logger="kibana"):
            client.perform_request("GET", "/api/test")

        # Check that no DEBUG messages were logged
        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert len(debug_records) == 0

    def test_error_logging(self, client, mock_transport, caplog):
        """Test that errors are logged appropriately."""
        # Make the transport return an error
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"error": {"message": "Not found"}},
            meta=ApiResponseMeta(
                status=404,
                headers={},
                http_version="1.1",
                duration=0.1,
                node=None,
            ),
        )

        with caplog.at_level(logging.DEBUG, logger="kibana"):
            with pytest.raises(Exception):
                client.perform_request("GET", "/api/test")

        # Check that error was logged
        assert any("Request failed" in record.message for record in caplog.records)
        assert any("404" in record.message for record in caplog.records)


class TestDeprecationWarnings:
    """Test deprecation warning functionality."""

    def test_warn_deprecated(self):
        """Test basic deprecation warning."""
        with pytest.warns(DeprecationWarning, match="This is deprecated"):
            warn_deprecated("This is deprecated")

    def test_warn_deprecated_custom_category(self):
        """Test deprecation warning with custom category."""
        with pytest.warns(FutureWarning, match="Future change"):
            warn_deprecated("Future change", category=FutureWarning)

    def test_deprecated_decorator(self):
        """Test deprecated decorator on function."""

        @deprecated("Old function is deprecated")
        def old_function():
            return "result"

        with pytest.warns(DeprecationWarning, match="old_function is deprecated"):
            result = old_function()

        assert result == "result"

    def test_deprecated_decorator_with_version(self):
        """Test deprecated decorator with version."""

        @deprecated("Old function", version="1.0.0")
        def old_function():
            return "result"

        with pytest.warns(
            DeprecationWarning, match="since version 1.0.0.*Old function"
        ):
            old_function()

    def test_deprecated_decorator_with_alternative(self):
        """Test deprecated decorator with alternative."""

        @deprecated("Old function", alternative="new_function()")
        def old_function():
            return "result"

        with pytest.warns(
            DeprecationWarning, match="Old function.*Use new_function\\(\\) instead"
        ):
            old_function()

    def test_deprecated_decorator_preserves_metadata(self):
        """Test that deprecated decorator preserves function metadata."""

        @deprecated("Deprecated")
        def documented_function():
            """This is a docstring."""
            return "result"

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is a docstring."

    def test_deprecated_decorator_with_args(self):
        """Test deprecated decorator on function with arguments."""

        @deprecated("Old function")
        def old_function(x, y):
            return x + y

        with pytest.warns(DeprecationWarning):
            result = old_function(1, 2)

        assert result == 3
