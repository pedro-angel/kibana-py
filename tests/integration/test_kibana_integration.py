"""Integration tests for Kibana client."""

import pytest

from kibana import Kibana
from kibana.exceptions import AuthenticationException, NotFoundError

from .utils import (
    create_test_kibana_client,
    get_integration_test_config,
    is_kibana_available,
)

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
def kibana_client_basic_auth():
    """Create a Kibana client for testing with basic auth."""
    client = create_test_kibana_client(auth_method="basic")
    yield client
    client.close()


@pytest.fixture
def kibana_client_api_key():
    """Create a Kibana client for testing with API key."""
    client = create_test_kibana_client(auth_method="api_key")
    yield client
    client.close()


class TestKibanaConnection:
    """Tests for basic Kibana connectivity."""

    def test_client_initialization(self):
        """Test that client can be initialized."""
        client = create_test_kibana_client(auth_method="auto")
        assert client is not None
        client.close()

    def test_client_context_manager(self):
        """Test that client works as context manager."""
        kibana_url, basic_auth, api_key = get_integration_test_config()

        if api_key:
            with Kibana(kibana_url, api_key=api_key) as client:
                assert client is not None
        elif basic_auth:
            with Kibana(kibana_url, basic_auth=basic_auth) as client:
                assert client is not None
        else:
            with Kibana(kibana_url) as client:
                assert client is not None

    def test_get_status(self, kibana_client):
        """Test getting Kibana status."""
        response = kibana_client.perform_request("GET", "/api/status")

        assert response.meta.status == 200
        assert "status" in response.body
        assert "overall" in response.body["status"]

    def test_authentication_failure(self):
        """Test that invalid credentials raise AuthenticationException."""
        kibana_url, _, _ = get_integration_test_config()

        client = Kibana(
            kibana_url,
            basic_auth=("invalid", "credentials"),
        )

        # Use an endpoint that requires authentication
        # Spaces API requires authentication
        with pytest.raises(AuthenticationException):
            client.spaces.get_all()

        client.close()

    def test_multiple_hosts(self):
        """Test client initialization with multiple hosts."""
        kibana_url, basic_auth, api_key = get_integration_test_config()

        # Even though only one host is real, test that multiple hosts are accepted
        if api_key:
            client = Kibana(
                [kibana_url, "http://localhost:5602"],
                api_key=api_key,
            )
        elif basic_auth:
            client = Kibana(
                [kibana_url, "http://localhost:5602"],
                basic_auth=basic_auth,
            )
        else:
            client = Kibana([kibana_url, "http://localhost:5602"])

        # Should still connect to the first working host
        response = client.perform_request("GET", "/api/status")
        assert response.meta.status == 200
        client.close()


class TestKibanaAuthentication:
    """Tests for different authentication methods."""

    def test_basic_auth(self, kibana_client_basic_auth):
        """Test authentication with basic auth."""
        response = kibana_client_basic_auth.spaces.get_all()
        assert response.meta.status == 200

    def test_api_key_string(self, kibana_client_api_key):
        """Test authentication with API key as string."""
        response = kibana_client_api_key.spaces.get_all()
        assert response.meta.status == 200
        assert isinstance(response.body, list)

    def test_api_key_with_options(self):
        """Test that API key can be set via options()."""
        kibana_url, _, api_key = get_integration_test_config()

        if not api_key:
            pytest.skip("API key not available for this test")

        # Start with no auth
        client = Kibana(kibana_url)

        # Add API key via options
        client_with_auth = client.options(api_key=api_key)

        response = client_with_auth.spaces.get_all()
        assert response.meta.status == 200
        client.close()

    def test_switch_auth_methods(self):
        """Test switching between authentication methods using options()."""
        kibana_url, basic_auth, api_key = get_integration_test_config()

        if not (basic_auth and api_key):
            pytest.skip("Both basic auth and API key needed for this test")

        # Start with basic auth
        client = Kibana(kibana_url, basic_auth=basic_auth)

        response1 = client.spaces.get_all()
        assert response1.meta.status == 200

        # Switch to API key
        client_with_api_key = client.options(api_key=api_key)
        response2 = client_with_api_key.spaces.get_all()
        assert response2.meta.status == 200

        client.close()


class TestKibanaSpaces:
    """Tests for Kibana Spaces API."""

    def test_get_default_space(self, kibana_client):
        """Test getting the default space."""
        response = kibana_client.spaces.get(id="default")

        assert response.meta.status == 200
        assert response.body["id"] == "default"
        assert "name" in response.body

    def test_list_spaces(self, kibana_client):
        """Test listing all spaces."""
        response = kibana_client.spaces.get_all()

        assert response.meta.status == 200
        assert isinstance(response.body, list)
        assert len(response.body) > 0

        # Default space should exist
        space_ids = [space["id"] for space in response.body]
        assert "default" in space_ids

    def test_get_nonexistent_space(self, kibana_client):
        """Test that getting a non-existent space raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.perform_request(
                "GET", "/api/spaces/space/nonexistent-space-12345"
            )


class TestKibanaSavedObjects:
    """Tests for Kibana Saved Objects API."""

    def test_find_saved_objects(self, kibana_client):
        """Test finding saved objects."""
        response = kibana_client.saved_objects.find(type="config", per_page=1)

        assert response.meta.status == 200
        assert "saved_objects" in response.body
        assert "total" in response.body


class TestKibanaOptions:
    """Tests for client options() method."""

    def test_options_with_custom_headers(self, kibana_client):
        """Test that options() allows per-request headers."""
        client_with_headers = kibana_client.options(
            headers={"X-Custom-Header": "test-value"}
        )

        # Should still be able to make requests
        response = client_with_headers.perform_request("GET", "/api/status")
        assert response.meta.status == 200

    def test_options_with_timeout(self, kibana_client):
        """Test that options() allows per-request timeout."""
        client_with_timeout = kibana_client.options(request_timeout=30.0)

        # Should still be able to make requests
        response = client_with_timeout.perform_request("GET", "/api/status")
        assert response.meta.status == 200

    def test_options_creates_new_instance(self, kibana_client):
        """Test that options() creates a new client instance."""
        new_client = kibana_client.options(request_timeout=30.0)

        assert new_client is not kibana_client
        assert isinstance(new_client, Kibana)


class TestKibanaErrorHandling:
    """Tests for error handling."""

    def test_invalid_endpoint_raises_not_found(self, kibana_client):
        """Test that invalid endpoints raise NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.perform_request("GET", "/api/nonexistent/endpoint/12345")

    def test_error_includes_response_body(self, kibana_client):
        """Test that errors include response body for debugging."""
        try:
            kibana_client.perform_request("GET", "/api/nonexistent/endpoint")
        except NotFoundError as e:
            assert e.body is not None
            assert e.meta is not None
            assert e.status_code == 404


class TestKibanaHTTPMethods:
    """Tests for different HTTP methods."""

    def test_get_request(self, kibana_client):
        """Test GET request."""
        response = kibana_client.perform_request("GET", "/api/status")
        assert response.meta.status == 200

    def test_post_request_with_body(self, kibana_client):
        """Test POST request with body."""
        # Create a saved object
        body = {
            "attributes": {
                "title": "Test Dashboard",
                "description": "Integration test dashboard",
            }
        }

        response = kibana_client.perform_request(
            "POST", "/api/saved_objects/dashboard", body=body
        )

        assert response.meta.status == 200
        assert "id" in response.body

        # Clean up - delete the created object
        object_id = response.body["id"]
        kibana_client.perform_request(
            "DELETE", f"/api/saved_objects/dashboard/{object_id}"
        )

    def test_put_request(self, kibana_client):
        """Test PUT request."""
        # First create an object
        body = {
            "attributes": {
                "title": "Test Dashboard for PUT",
                "description": "Will be updated",
            }
        }

        create_response = kibana_client.perform_request(
            "POST", "/api/saved_objects/dashboard", body=body
        )
        object_id = create_response.body["id"]

        # Update it with PUT
        update_body = {
            "attributes": {
                "title": "Updated Dashboard",
                "description": "Updated via PUT",
            }
        }

        update_response = kibana_client.perform_request(
            "PUT", f"/api/saved_objects/dashboard/{object_id}", body=update_body
        )

        assert update_response.meta.status == 200
        assert update_response.body["attributes"]["title"] == "Updated Dashboard"

        # Clean up
        kibana_client.perform_request(
            "DELETE", f"/api/saved_objects/dashboard/{object_id}"
        )

    def test_delete_request(self, kibana_client):
        """Test DELETE request."""
        # Create an object to delete
        body = {
            "attributes": {
                "title": "Test Dashboard to Delete",
                "description": "Will be deleted",
            }
        }

        create_response = kibana_client.perform_request(
            "POST", "/api/saved_objects/dashboard", body=body
        )
        object_id = create_response.body["id"]

        # Delete it
        delete_response = kibana_client.perform_request(
            "DELETE", f"/api/saved_objects/dashboard/{object_id}"
        )

        assert delete_response.meta.status == 200

        # Verify it's gone
        with pytest.raises(NotFoundError):
            kibana_client.perform_request(
                "GET", f"/api/saved_objects/dashboard/{object_id}"
            )


class TestKibanaQueryParameters:
    """Tests for query parameter handling."""

    def test_single_query_parameter(self, kibana_client):
        """Test request with single query parameter."""
        response = kibana_client.perform_request(
            "GET", "/api/saved_objects/_find", params={"type": "dashboard"}
        )

        assert response.meta.status == 200
        assert "saved_objects" in response.body

    def test_multiple_query_parameters(self, kibana_client):
        """Test request with multiple query parameters."""
        response = kibana_client.perform_request(
            "GET",
            "/api/saved_objects/_find",
            params={"type": "dashboard", "per_page": 5, "page": 1},
        )

        assert response.meta.status == 200
        assert "saved_objects" in response.body
        assert response.body["per_page"] == 5

    def test_query_parameters_with_special_characters(self, kibana_client):
        """Test query parameters with special characters are properly encoded."""
        response = kibana_client.perform_request(
            "GET",
            "/api/saved_objects/_find",
            params={"type": "dashboard", "search": "test & demo"},
        )

        assert response.meta.status == 200


class TestKibanaResponseMetadata:
    """Tests for response metadata."""

    def test_response_has_meta(self, kibana_client):
        """Test that responses include metadata."""
        response = kibana_client.perform_request("GET", "/api/status")

        assert hasattr(response, "meta")
        assert hasattr(response.meta, "status")
        assert hasattr(response.meta, "headers")

    def test_response_has_body(self, kibana_client):
        """Test that responses include body."""
        response = kibana_client.perform_request("GET", "/api/status")

        assert hasattr(response, "body")
        assert isinstance(response.body, dict)

    def test_response_status_code(self, kibana_client):
        """Test that response status code is accessible."""
        response = kibana_client.perform_request("GET", "/api/status")

        assert response.meta.status == 200


class TestKibanaClientReuse:
    """Tests for client reusability."""

    def test_client_can_make_multiple_requests(self, kibana_client):
        """Test that client can be reused for multiple requests."""
        response1 = kibana_client.perform_request("GET", "/api/status")
        assert response1.meta.status == 200

        response2 = kibana_client.spaces.get_all()
        assert response2.meta.status == 200

        response3 = kibana_client.saved_objects.find(type="config", per_page=1)
        assert response3.meta.status == 200

    def test_options_client_is_independent(self, kibana_client):
        """Test that options() creates independent client instances."""
        # Create a client with custom timeout
        client_with_timeout = kibana_client.options(request_timeout=60.0)

        # Both should work independently
        response1 = kibana_client.perform_request("GET", "/api/status")
        response2 = client_with_timeout.perform_request("GET", "/api/status")

        assert response1.meta.status == 200
        assert response2.meta.status == 200
