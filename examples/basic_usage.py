#!/usr/bin/env python3
"""
Basic Usage Example

This example demonstrates the fundamental patterns for using the Kibana Python client:
1. Client initialization with different authentication methods
2. Making basic API calls
3. Handling responses
4. Proper resource cleanup

Run this example:
    python examples/basic_usage.py
"""

import os

from utils import create_kibana_client, get_kibana_config, print_config_info


def example_basic_initialization():
    """Example 1: Basic client initialization."""
    print("\n=== Example 1: Basic Initialization ===")

    from kibana import Kibana

    # Simple initialization with URL only
    client = Kibana("http://localhost:5601")
    print("✓ Client created with URL only")
    client.close()

    # With basic authentication (use env vars — never hardcode credentials)
    client = Kibana(
        "http://localhost:5601",
        basic_auth=(
            os.getenv("KIBANA_USERNAME", "elastic"),
            os.getenv("KIBANA_PASSWORD", "changeme"),
        ),
    )
    print("✓ Client created with basic auth")
    client.close()

    # With API key
    client = Kibana("http://localhost:5601", api_key="your_api_key")
    print("✓ Client created with API key")
    client.close()

    # With bearer token
    client = Kibana("http://localhost:5601", bearer_auth="your_bearer_token")
    print("✓ Client created with bearer token")
    client.close()


def example_context_manager():
    """Example 2: Using context manager for automatic cleanup."""
    print("\n=== Example 2: Context Manager ===")

    from kibana import Kibana

    kibana_url, basic_auth, api_key = get_kibana_config()

    # Context manager automatically closes the client
    with Kibana(kibana_url, basic_auth=basic_auth) as client:
        # List connector types to verify connection
        types = client.actions.list_types()
        print(f"✓ Connected to Kibana - found {len(types.body)} connector types")
        print("✓ Client will be automatically closed")


def example_response_handling():
    """Example 3: Handling API responses."""
    print("\n=== Example 3: Response Handling ===")

    client = create_kibana_client()

    try:
        # List connector types
        response = client.actions.list_types()

        # Response is an ObjectApiResponse object
        print(f"Response type: {type(response)}")

        # Access the response body
        body = response.body
        print(f"✓ Response body type: {type(body)}")

        # Extract specific fields
        print(f"  Found {len(body)} connector types")
        if body:
            first_type = body[0]
            print(f"  First type ID: {first_type.get('id', 'unknown')}")
            print(f"  First type name: {first_type.get('name', 'unknown')}")

        # Access response metadata
        print(f"  HTTP Status: {response.meta.status}")
        print(f"  HTTP Version: {response.meta.http_version}")

    finally:
        client.close()


def example_per_request_options():
    """Example 4: Per-request configuration with options()."""
    print("\n=== Example 4: Per-Request Options ===")

    client = create_kibana_client()

    try:
        # Set a longer timeout for a specific request
        print("Making request with 60s timeout...")
        response = client.options(request_timeout=60).actions.list_types()
        print(f"✓ Request completed: found {len(response.body)} connector types")

        # Add custom headers for a specific request
        print("Making request with custom headers...")
        response = client.options(
            headers={"X-Custom-Header": "example-value"}
        ).actions.list_types()
        print("✓ Request completed with custom headers")

        # Chain multiple options
        print("Making request with multiple options...")
        response = client.options(
            request_timeout=30, headers={"X-Request-ID": "12345"}
        ).actions.list_types()
        print("✓ Request completed with multiple options")

    finally:
        client.close()


def example_connection_configuration():
    """Example 5: Advanced connection configuration."""
    print("\n=== Example 5: Connection Configuration ===")

    from kibana import Kibana

    kibana_url, basic_auth, api_key = get_kibana_config()

    # Create client with advanced configuration
    client = Kibana(
        hosts=[kibana_url],
        basic_auth=basic_auth,
        # Timeout settings
        request_timeout=30.0,
        # Retry configuration
        max_retries=3,
        retry_on_timeout=True,
        retry_on_status=[502, 503, 504],
        # Connection pooling
        connections_per_node=10,
    )

    print("✓ Client created with advanced configuration")
    print("  Request timeout: 30.0s")
    print("  Max retries: 3")
    print("  Connections per node: 10")

    try:
        # Test the connection
        types = client.actions.list_types()
        print(f"✓ Connection successful: found {len(types.body)} connector types")
    finally:
        client.close()


def example_multiple_hosts():
    """Example 6: Connecting to multiple Kibana nodes."""
    print("\n=== Example 6: Multiple Hosts ===")

    from kibana import Kibana

    # Connect to multiple Kibana nodes for high availability
    client = Kibana(
        hosts=[
            "http://kibana-node-1:5601",
            "http://kibana-node-2:5601",
            "http://kibana-node-3:5601",
        ],
        basic_auth=(
            os.getenv("KIBANA_USERNAME", "elastic"),
            os.getenv("KIBANA_PASSWORD", "changeme"),
        ),
    )

    print("✓ Client configured with multiple hosts")
    print("  The client will automatically load balance across nodes")
    print("  Failed nodes will be temporarily skipped")

    client.close()


def main():
    """Run all examples."""
    print("=" * 60)
    print("Kibana Python Client - Basic Usage Examples")
    print("=" * 60)

    # Print configuration info
    print_config_info()

    # Configure telemetry with production-ready error handling
    import logging

    from utils import (
        configure_example_telemetry,
        print_telemetry_info,
        setup_telemetry_cleanup,
        should_enable_telemetry,
    )

    logger = logging.getLogger(__name__)

    try:
        telemetry_enabled = should_enable_telemetry()
        traces_configured, logs_configured = configure_example_telemetry(
            enabled=telemetry_enabled,
            logs_enabled=telemetry_enabled,  # Enable log forwarding when telemetry is enabled
        )
        print_telemetry_info()

        # Set up automatic telemetry cleanup
        setup_telemetry_cleanup()

        if traces_configured or logs_configured:
            logger.info(
                "Basic usage example started",
                extra={
                    "traces_enabled": traces_configured,
                    "logs_enabled": logs_configured,
                    "example": "basic_usage",
                },
            )
    except Exception as e:
        logger.warning(
            f"Telemetry configuration failed: {e}",
            extra={"error_type": "telemetry_config_error", "example": "basic_usage"},
        )
        print("⚠️  Continuing without telemetry...")

    # Run examples
    example_basic_initialization()
    example_context_manager()
    example_response_handling()
    example_per_request_options()
    example_connection_configuration()
    example_multiple_hosts()

    print("\n" + "=" * 60)
    print("✅ All examples completed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("  - Check examples/actions_management.py for connector examples")
    print("  - Check examples/error_handling.py for exception handling")
    print("  - Read the documentation for more advanced features")


if __name__ == "__main__":
    main()
