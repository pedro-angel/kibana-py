"""
Simple async example demonstrating AsyncKibana client usage.

This example shows how to:
1. Create an AsyncKibana client
2. Make async API calls
3. Use async context manager for automatic cleanup
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


async def main():
    """Main async function demonstrating AsyncKibana usage."""
    print("=" * 80)
    print("Async Kibana Client - Simple Status Example")
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
                "Async simple status example started",
                extra={
                    "traces_enabled": traces_configured,
                    "logs_enabled": logs_configured,
                    "example": "async_simple_status",
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
                "example": "async_simple_status",
                "async_mode": True,
            },
        )

    # Use async context manager for automatic cleanup
    async with create_async_kibana_client() as client:
        print("\n" + "=" * 80)
        print("Fetching Kibana Status (async)")
        print("=" * 80)

        try:
            # Make async API call
            logger.info(
                "Fetching Kibana status",
                extra={"operation": "fetch_status", "async_mode": True},
            )

            response = await client.perform_request("GET", "/api/status")
            status_data = response.body

            print(f"\n✓ Status: {status_data['status']['overall']['level']}")
            print(f"✓ Version: {status_data['version']['number']}")
            print(f"✓ Build: {status_data['version']['build_number']}")

            logger.info(
                "Kibana status fetched successfully",
                extra={
                    "kibana_status": status_data["status"]["overall"]["level"],
                    "kibana_version": status_data["version"]["number"],
                    "build_number": status_data["version"]["build_number"],
                    "operation": "fetch_status",
                    "async_mode": True,
                    "status": "success",
                },
            )

            # Show some service statuses
            if "status" in status_data and "statuses" in status_data["status"]:
                print("\nService Statuses:")
                for service in status_data["status"]["statuses"][:5]:
                    print(f"  - {service['id']}: {service['state']}")

                logger.info(
                    "Service statuses retrieved",
                    extra={
                        "service_count": len(status_data["status"]["statuses"]),
                        "operation": "fetch_status",
                        "async_mode": True,
                    },
                )

        except Exception as e:
            print(f"\n❌ Error: {e}")
            logger.error(
                f"Failed to fetch Kibana status: {e}",
                extra={
                    "operation": "fetch_status",
                    "async_mode": True,
                    "status": "error",
                    "error_type": type(e).__name__,
                },
            )
            import traceback

            traceback.print_exc()

    print("\n✓ Client closed automatically (async context manager)")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
