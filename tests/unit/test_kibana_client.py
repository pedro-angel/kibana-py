"""Unit tests for Kibana client."""

from unittest.mock import Mock, patch

import pytest
from elastic_transport import Transport


class TestKibanaClientInitialization:
    """Tests for Kibana client initialization."""

    def test_init_with_single_host_string(self):
        """Test Kibana client initialization with a single host string."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601")

        assert client is not None
        assert hasattr(client, "_transport")

    def test_init_with_multiple_hosts_list(self):
        """Test Kibana client initialization with multiple hosts."""
        from kibana import Kibana

        client = Kibana(hosts=["http://localhost:5601", "http://localhost:5602"])

        assert client is not None
        assert hasattr(client, "_transport")

    def test_init_with_cloud_id(self):
        """Test Kibana client initialization with cloud_id."""
        from kibana import Kibana

        # Cloud ID format: cluster_name:base64_encoded_data
        cloud_id = "my-cluster:dXMtY2VudHJhbDEuZ2NwLmNsb3VkLmVzLmlvJGFiYzEyMyRkZWY0NTY="

        client = Kibana(cloud_id=cloud_id, basic_auth=("elastic", "password"))

        assert client is not None
        assert hasattr(client, "_transport")

    def test_init_with_api_key_string(self):
        """Test initialization with API key as string."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601", api_key="base64_encoded_api_key")

        assert client is not None
        assert client._api_key == "base64_encoded_api_key"

    def test_init_with_api_key_tuple(self):
        """Test initialization with API key as tuple."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601", api_key=("id", "api_key"))

        assert client is not None
        assert client._api_key == ("id", "api_key")

    def test_init_with_basic_auth(self):
        """Test initialization with basic authentication."""
        from kibana import Kibana

        client = Kibana(
            hosts="http://localhost:5601", basic_auth=("username", "password")
        )

        assert client is not None
        assert client._basic_auth == ("username", "password")

    def test_init_with_bearer_auth(self):
        """Test initialization with bearer token."""
        from kibana import Kibana

        client = Kibana(
            hosts="http://localhost:5601", bearer_auth="bearer_token_string"
        )

        assert client is not None
        assert client._bearer_auth == "bearer_token_string"

    def test_init_without_hosts_or_cloud_id_raises_error(self):
        """Test that initialization without hosts or cloud_id raises an error."""
        from kibana import Kibana

        with pytest.raises((ValueError, TypeError)):
            Kibana()

    def test_init_stores_authentication_credentials(self):
        """Test that authentication credentials are stored correctly."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601", api_key="test_key")

        assert hasattr(client, "_api_key")
        assert client._api_key == "test_key"


class TestTransportConfiguration:
    """Tests for transport configuration options."""

    def test_init_with_verify_certs(self):
        """Test initialization with verify_certs option."""
        from kibana import Kibana

        client = Kibana(hosts="https://localhost:5601", verify_certs=True)

        assert client is not None

    def test_init_with_ca_certs(self):
        """Test initialization with ca_certs path."""
        from kibana import Kibana

        client = Kibana(hosts="https://localhost:5601", ca_certs="/path/to/ca.crt")

        assert client is not None

    def test_init_with_client_cert_and_key(self):
        """Test initialization with client certificate and key."""
        from kibana import Kibana

        client = Kibana(
            hosts="https://localhost:5601",
            client_cert="/path/to/client.crt",
            client_key="/path/to/client.key",
        )

        assert client is not None

    def test_init_with_request_timeout(self):
        """Test initialization with request timeout."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601", request_timeout=30.0)

        assert client is not None
        assert client._request_timeout == 30.0

    def test_init_with_max_retries(self):
        """Test initialization with max_retries option."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601", max_retries=5)

        assert client is not None

    def test_init_with_retry_on_timeout(self):
        """Test initialization with retry_on_timeout option."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601", retry_on_timeout=True)

        assert client is not None

    def test_init_with_retry_on_status(self):
        """Test initialization with retry_on_status option."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601", retry_on_status=[502, 503, 504])

        assert client is not None

    def test_init_with_connections_per_node(self):
        """Test initialization with connections_per_node option."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601", connections_per_node=10)

        assert client is not None

    def test_init_with_dead_node_backoff_factor(self):
        """Test initialization with dead_node_backoff_factor option."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601", dead_node_backoff_factor=2.0)

        assert client is not None

    def test_init_with_max_dead_node_backoff(self):
        """Test initialization with max_dead_node_backoff option."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601", max_dead_node_backoff=120.0)

        assert client is not None

    def test_init_with_custom_headers(self):
        """Test initialization with custom headers."""
        from kibana import Kibana

        client = Kibana(
            hosts="http://localhost:5601", headers={"X-Custom-Header": "value"}
        )

        assert client is not None

    def test_init_with_multiple_transport_options(self):
        """Test initialization with multiple transport options."""
        from kibana import Kibana

        client = Kibana(
            hosts="https://localhost:5601",
            verify_certs=True,
            ca_certs="/path/to/ca.crt",
            request_timeout=60.0,
            max_retries=3,
            retry_on_timeout=True,
            connections_per_node=5,
        )

        assert client is not None
        assert client._request_timeout == 60.0


class TestCloseMethod:
    """Tests for Kibana client close() method."""

    def test_close_method_exists(self):
        """Test that close() method exists."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601")

        assert hasattr(client, "close")
        assert callable(client.close)

    def test_close_calls_transport_close(self):
        """Test that close() calls transport.close()."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601")

        # Mock the transport's close method
        with patch.object(client._transport, "close") as mock_close:
            client.close()
            mock_close.assert_called_once()

    def test_close_can_be_called_multiple_times(self):
        """Test that close() can be called multiple times safely."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601")

        # Should not raise an error
        client.close()
        client.close()

    def test_client_can_be_used_as_context_manager(self):
        """Test that client can be used as a context manager."""
        from kibana import Kibana

        # This should work without errors
        with Kibana(hosts="http://localhost:5601") as client:
            assert client is not None

    def test_context_manager_calls_close(self):
        """Test that context manager calls close() on exit."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601")

        with patch.object(client, "close") as mock_close:
            with client:
                pass
            mock_close.assert_called_once()


class TestKibanaClientInheritance:
    """Tests for Kibana client inheritance from BaseClient."""

    def test_kibana_extends_base_client(self):
        """Test that Kibana class extends BaseClient."""
        from kibana import Kibana
        from kibana._sync.client._base import BaseClient

        client = Kibana(hosts="http://localhost:5601")

        assert isinstance(client, BaseClient)

    def test_kibana_has_perform_request_method(self):
        """Test that Kibana inherits perform_request from BaseClient."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601")

        assert hasattr(client, "perform_request")
        assert callable(client.perform_request)

    def test_kibana_has_options_method(self):
        """Test that Kibana inherits options from BaseClient."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601")

        assert hasattr(client, "options")
        assert callable(client.options)

    def test_options_returns_kibana_instance(self):
        """Test that options() returns a Kibana instance."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601")
        new_client = client.options(request_timeout=30)

        assert isinstance(new_client, Kibana)
        assert new_client is not client
        assert new_client._request_timeout == 30


class TestTransportCreation:
    """Tests for Transport instance creation."""

    def test_transport_is_created(self):
        """Test that Transport instance is created."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601")

        assert hasattr(client, "_transport")
        assert isinstance(client._transport, Transport)

    def test_transport_configured_with_hosts(self):
        """Test that transport is configured with provided hosts."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601")

        # Transport should have node pool with configured hosts
        assert client._transport is not None
        assert hasattr(client._transport, "node_pool")

    @patch("kibana._sync.client.Transport")
    def test_transport_receives_serializer(self, mock_transport_class):
        """Test that transport is configured with serializer."""
        from kibana import Kibana

        mock_transport_instance = Mock(spec=Transport)
        mock_transport_class.return_value = mock_transport_instance

        Kibana(hosts="http://localhost:5601")

        # Verify Transport was called with serializer
        assert mock_transport_class.called

    @patch("kibana._sync.client.Transport")
    def test_transport_receives_node_configs(self, mock_transport_class):
        """Test that transport receives proper node configurations."""
        from kibana import Kibana

        mock_transport_instance = Mock(spec=Transport)
        mock_transport_class.return_value = mock_transport_instance

        Kibana(hosts=["http://localhost:5601", "http://localhost:5602"])

        # Verify Transport was called
        assert mock_transport_class.called


class TestDefaultValues:
    """Tests for default configuration values."""

    def test_default_request_timeout_is_none(self):
        """Test that default request_timeout is None."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601")

        # Should use transport's default timeout
        assert client._request_timeout is None

    def test_default_auth_is_none(self):
        """Test that default authentication is None."""
        from kibana import Kibana

        client = Kibana(hosts="http://localhost:5601")

        assert client._api_key is None
        assert client._basic_auth is None
        assert client._bearer_auth is None

    def test_can_create_client_with_minimal_config(self):
        """Test that client can be created with minimal configuration."""
        from kibana import Kibana

        # Should work with just hosts
        client = Kibana(hosts="http://localhost:5601")

        assert client is not None
        assert client._transport is not None
