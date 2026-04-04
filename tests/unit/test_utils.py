"""Unit tests for client utilities."""

from unittest.mock import Mock

from elastic_transport import ObjectApiResponse

from kibana._sync.client._base import BaseClient
from kibana._sync.client.utils import NamespaceClient, _quote


class TestNamespaceClient:
    """Test NamespaceClient base class."""

    def test_init_stores_client_reference(self):
        """Test that __init__ stores the parent client reference."""
        mock_client = Mock(spec=BaseClient)
        namespace_client = NamespaceClient(mock_client)

        assert namespace_client._client is mock_client

    def test_perform_request_delegates_to_parent_client(self):
        """Test that perform_request delegates to parent client."""
        mock_client = Mock(spec=BaseClient)
        mock_response = Mock(spec=ObjectApiResponse)
        mock_client.perform_request.return_value = mock_response

        namespace_client = NamespaceClient(mock_client)

        result = namespace_client.perform_request(
            method="GET",
            path="/api/test",
            params={"param1": "value1"},
            headers={"header1": "value1"},
            body={"key": "value"},
        )

        # Verify delegation
        mock_client.perform_request.assert_called_once_with(
            method="GET",
            path="/api/test",
            params={"param1": "value1"},
            headers={"header1": "value1"},
            body={"key": "value"},
        )
        assert result is mock_response

    def test_perform_request_with_minimal_params(self):
        """Test perform_request with only required parameters."""
        mock_client = Mock(spec=BaseClient)
        mock_response = Mock(spec=ObjectApiResponse)
        mock_client.perform_request.return_value = mock_response

        namespace_client = NamespaceClient(mock_client)

        result = namespace_client.perform_request(
            method="POST",
            path="/api/test",
        )

        mock_client.perform_request.assert_called_once_with(
            method="POST",
            path="/api/test",
            params=None,
            headers=None,
            body=None,
        )
        assert result is mock_response


class TestQuoteFunction:
    """Test _quote utility function."""

    def test_quote_simple_string(self):
        """Test quoting a simple string."""
        result = _quote("hello")
        assert result == "hello"

    def test_quote_string_with_spaces(self):
        """Test quoting string with spaces."""
        result = _quote("hello world")
        assert result == "hello%20world"

    def test_quote_string_with_special_chars(self):
        """Test quoting string with special characters."""
        result = _quote("user@example.com")
        assert result == "user%40example.com"

    def test_quote_with_safe_chars(self):
        """Test quoting with safe characters."""
        result = _quote("path/to/resource", safe="/")
        assert result == "path/to/resource"

    def test_quote_empty_string(self):
        """Test quoting empty string."""
        result = _quote("")
        assert result == ""

    def test_quote_converts_to_string(self):
        """Test that _quote converts input to string."""
        result = _quote(123)
        assert result == "123"
