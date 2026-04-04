"""
Comprehensive async example demonstrating AsyncKibana client features.

This example shows:
1. Async context manager usage
2. Multiple concurrent API calls
3. Error handling
4. Options pattern for per-request configuration
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent))

from examples.utils import (
    configure_example_telemetry,
    create_async_kibana_client,
    print_config_info,
    print_telemetry_info,
    setup_telemetry_cleanup,
    should_enable_telemetry,
)


async def fetch_status(client):
    """Fetch Kibana status."""
    import logging

    logger = logging.getLogger(__name__)

    print("\n📊 Fetching status...")
    logger.info(
        "Fetching Kibana status",
        extra={"operation": "fetch_status", "async_mode": True},
    )

    response = await client.perform_request("GET", "/api/status")
    status = response.body["status"]["overall"]["level"]
    version = response.body["version"]["number"]
    print(f"   ✓ Status: {status}, Version: {version}")

    logger.info(
        "Kibana status fetched successfully",
        extra={
            "kibana_status": status,
            "kibana_version": version,
            "operation": "fetch_status",
            "async_mode": True,
            "status": "success",
        },
    )

    return status, version


async def fetch_spaces(client):
    """Fetch Kibana spaces using proper client method."""
    import logging

    logger = logging.getLogger(__name__)

    print("\n🏢 Fetching spaces...")
    logger.info(
        "Fetching Kibana spaces",
        extra={"operation": "fetch_spaces", "async_mode": True},
    )

    response = await client.spaces.get_all()
    spaces = response.body
    print(f"   ✓ Found {len(spaces)} space(s)")
    for space in spaces[:3]:
        print(f"     - {space['name']} (id: {space['id']})")

    logger.info(
        "Kibana spaces fetched successfully",
        extra={
            "space_count": len(spaces),
            "operation": "fetch_spaces",
            "async_mode": True,
            "status": "success",
        },
    )

    return spaces


async def fetch_saved_objects(client):
    """Fetch saved objects using proper client method."""
    print("\n📦 Fetching saved objects...")
    response = await client.saved_objects.find(type="dashboard", per_page=5)
    objects = response.body
    total = objects.get("total", 0)
    print(f"   ✓ Found {total} dashboard(s)")
    for obj in objects.get("saved_objects", [])[:3]:
        title = obj.get("attributes", {}).get("title", "Untitled")
        print(f"     - {title}")
    return objects


async def main():
    """Main async function demonstrating AsyncKibana features."""
    print("=" * 80)
    print("Async Kibana Client - Comprehensive Example")
    print("=" * 80)
    print()

    # Print configuration information
    print_config_info()

    # Configure telemetry with async-compatible log forwarding
    import logging

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
                "Async comprehensive example started",
                extra={
                    "traces_enabled": traces_configured,
                    "logs_enabled": logs_configured,
                    "example": "async_comprehensive",
                    "async_mode": True,
                },
            )
    except Exception as e:
        print(f"⚠️  Telemetry configuration failed: {e}")
        print("   Continuing without telemetry...")
        logger.warning(
            f"Telemetry configuration failed: {e}",
            extra={
                "error_type": "telemetry_config_error",
                "example": "async_comprehensive",
                "async_mode": True,
            },
        )

    # Use async context manager
    async with create_async_kibana_client() as client:
        print("\n" + "=" * 80)
        print("Making Concurrent API Calls")
        print("=" * 80)

        try:
            # Execute multiple API calls concurrently
            await asyncio.gather(
                fetch_status(client), fetch_spaces(client), fetch_saved_objects(client)
            )

            print("\n" + "=" * 80)
            print("All API Calls Completed Successfully!")
            print("=" * 80)

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback

            traceback.print_exc()

        # Demonstrate options pattern
        print("\n" + "=" * 80)
        print("Using Options Pattern")
        print("=" * 80)

        try:
            # Create a new client with custom timeout
            custom_client = client.options(request_timeout=5.0)
            print("\n⚙️  Created client with custom timeout (5s)")

            await custom_client.perform_request("GET", "/api/status")
            print("   ✓ Request completed with custom timeout")

        except Exception as e:
            print(f"\n❌ Error with custom options: {e}")

    print("\n✓ Client closed automatically (async context manager)")
    print("\n" + "=" * 80)
    print("Example Complete!")
    print("=" * 80)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
