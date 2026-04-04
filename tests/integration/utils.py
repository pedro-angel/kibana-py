#!/usr/bin/env python3
"""
Utility functions for integration tests.
"""

import os
import sys
from pathlib import Path

# Add the project root to the path so we can import from examples
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from examples.utils import get_kibana_config


def get_integration_test_config() -> tuple[str, tuple[str, str] | None, str | None]:
    """
    Get Kibana configuration for integration tests.

    Uses the same automatic configuration as examples, with integration test
    environment variable overrides.

    :return: Tuple of (kibana_url, basic_auth, api_key)
    """
    # First try integration test specific environment variables
    kibana_url = os.getenv("KIBANA_URL")
    kibana_username = os.getenv("KIBANA_USERNAME")
    kibana_password = os.getenv("KIBANA_PASSWORD")
    api_key = os.getenv("KIBANA_API_KEY")

    # If not found, fall back to the same logic as examples
    if not kibana_url:
        kibana_url, basic_auth, api_key = get_kibana_config()

        # Override with integration test specific values if available
        if kibana_username and kibana_password:
            basic_auth = (kibana_username, kibana_password)

        return kibana_url, basic_auth, api_key

    # Build basic auth if we have username/password
    basic_auth = None
    if kibana_username and kibana_password:
        basic_auth = (kibana_username, kibana_password)

    return kibana_url, basic_auth, api_key


def create_test_kibana_client(auth_method: str = "auto"):
    """
    Create a Kibana client for integration tests with automatic configuration.

    :param auth_method: Authentication method to use ("auto", "basic", "api_key")
    :return: Configured Kibana client
    """
    from kibana import Kibana

    kibana_url, basic_auth, api_key = get_integration_test_config()

    if not kibana_url:
        raise ValueError(
            "KIBANA_URL not configured. Either set environment variables or "
            "start elastic-start-local stack."
        )

    # Choose authentication method
    if auth_method == "auto":
        # Prefer API key over basic auth
        if api_key:
            return Kibana(kibana_url, api_key=api_key)
        elif basic_auth:
            return Kibana(kibana_url, basic_auth=basic_auth)
        else:
            return Kibana(kibana_url)
    elif auth_method == "basic":
        if not basic_auth:
            raise ValueError("Basic auth credentials not available")
        return Kibana(kibana_url, basic_auth=basic_auth)
    elif auth_method == "api_key":
        if not api_key:
            raise ValueError("API key not available")
        return Kibana(kibana_url, api_key=api_key)
    else:
        raise ValueError(f"Unknown auth method: {auth_method}")


def is_kibana_available() -> bool:
    """
    Check if Kibana is available for integration tests.

    :return: True if Kibana is available, False otherwise
    """
    try:
        kibana_url, _, _ = get_integration_test_config()
        return kibana_url is not None
    except Exception:
        return False


def safe_delete_connector(client, connector_id: str) -> None:
    """
    Safely delete a connector, handling empty responses and errors.

    This is the same pattern used in examples for robust cleanup.

    :param client: Kibana client
    :param connector_id: ID of connector to delete
    """
    from kibana.exceptions import NotFoundError

    try:
        client.actions.delete(id=connector_id)
    except Exception:
        # DELETE may return empty response, verify deletion by trying to get
        try:
            client.actions.get(id=connector_id)
            # If get succeeds, deletion failed
            raise AssertionError(f"Connector {connector_id} was not deleted")
        except NotFoundError:
            # Expected - connector was deleted successfully
            pass


def print_test_config_info():
    """Print configuration information for integration tests."""
    kibana_url, basic_auth, api_key = get_integration_test_config()

    print("=== Integration Test Configuration ===")
    print(f"Kibana URL: {kibana_url}")

    if api_key:
        print(
            f"API Key: {api_key[:10]}..."
            if len(api_key) > 10
            else f"API Key: {api_key}"
        )
    elif basic_auth:
        print(f"Basic Auth: {basic_auth[0]} / {'*' * len(basic_auth[1])}")
    else:
        print("Authentication: None")

    # Check if local .env exists
    env_file = Path(__file__).parent.parent.parent / "elastic-start-local" / ".env"
    if env_file.exists():
        print(f"✅ Local .env file found: {env_file}")
    else:
        print(f"❌ Local .env file not found: {env_file}")

    # Check environment variables
    env_vars = ["KIBANA_URL", "KIBANA_USERNAME", "KIBANA_PASSWORD", "KIBANA_API_KEY"]
    set_vars = [var for var in env_vars if os.getenv(var)]
    if set_vars:
        print(f"Environment variables set: {', '.join(set_vars)}")
    else:
        print("No integration test environment variables set")

    print("=" * 40)
    print()


def create_test_async_kibana_client(auth_method: str = "auto"):
    """
    Create an AsyncKibana client for integration tests with automatic configuration.

    :param auth_method: Authentication method to use ("auto", "basic", "api_key")
    :return: Configured AsyncKibana client
    """
    from kibana import AsyncKibana

    kibana_url, basic_auth, api_key = get_integration_test_config()

    if not kibana_url:
        raise ValueError(
            "KIBANA_URL not configured. Either set environment variables or "
            "start elastic-start-local stack."
        )

    # Choose authentication method
    if auth_method == "auto":
        # Prefer API key over basic auth
        if api_key:
            return AsyncKibana(kibana_url, api_key=api_key)
        elif basic_auth:
            return AsyncKibana(kibana_url, basic_auth=basic_auth)
        else:
            return AsyncKibana(kibana_url)
    elif auth_method == "basic":
        if not basic_auth:
            raise ValueError("Basic auth credentials not available")
        return AsyncKibana(kibana_url, basic_auth=basic_auth)
    elif auth_method == "api_key":
        if not api_key:
            raise ValueError("API key not available")
        return AsyncKibana(kibana_url, api_key=api_key)
    else:
        raise ValueError(f"Unknown auth method: {auth_method}")


async def safe_delete_connector_async(client, connector_id: str) -> None:
    """
    Safely delete a connector asynchronously, handling empty responses and errors.

    This is the async version of safe_delete_connector.

    :param client: AsyncKibana client
    :param connector_id: ID of connector to delete
    """
    from kibana.exceptions import NotFoundError

    try:
        await client.actions.delete(id=connector_id)
    except Exception:
        # DELETE may return empty response, verify deletion by trying to get
        try:
            await client.actions.get(id=connector_id)
            # If get succeeds, deletion failed
            raise AssertionError(f"Connector {connector_id} was not deleted")
        except NotFoundError:
            # Expected - connector was deleted successfully
            pass


if __name__ == "__main__":
    # Test the configuration
    print_test_config_info()

    if is_kibana_available():
        print("✅ Kibana is available for integration tests")

        try:
            client = create_test_kibana_client()
            print("✅ Test Kibana client created successfully")
            client.close()
        except Exception as e:
            print(f"❌ Failed to create test Kibana client: {e}")
    else:
        print("❌ Kibana is not available for integration tests")
        print("   Set KIBANA_URL or start elastic-start-local stack")
