#!/usr/bin/env python3
"""
Simple Space Example

This example shows the minimal code needed to:
1. Create a Kibana space
2. Verify the space exists
3. Clean up the space

Run this example:
    python examples/simple_space.py
"""

import logging

from utils import (
    configure_example_telemetry,
    create_kibana_client,
    print_config_info,
    print_telemetry_info,
    setup_telemetry_cleanup,
    should_cleanup,
    should_enable_telemetry,
)

# Set up logger for this example
logger = logging.getLogger("kibana.examples.simple_space")


def main():
    # Print configuration information
    print_config_info()

    # Configure telemetry with log forwarding
    telemetry_enabled = should_enable_telemetry()
    traces_configured, logs_configured = configure_example_telemetry(
        enabled=telemetry_enabled,
        logs_enabled=telemetry_enabled,  # Enable logs when telemetry is enabled
    )
    print_telemetry_info()

    # Set up automatic telemetry cleanup
    setup_telemetry_cleanup()

    # Log example start
    logger.info(
        "Starting simple space example",
        extra={
            "example": "simple_space",
            "traces_enabled": traces_configured,
            "logs_enabled": logs_configured,
        },
    )

    # Initialize Kibana client with automatic configuration
    client = create_kibana_client()

    try:
        # 1. Create a space
        print("Creating space...")
        logger.info(
            "Creating Kibana space",
            extra={"space_id": "my-team-space", "operation": "create"},
        )

        space_response = client.spaces.create(
            id="my-team-space",
            name="My Team Space",
            description="A space for my team's dashboards and visualizations",
        )

        space = space_response.body  # Access the body attribute
        space_id = space["id"]

        logger.info(
            "Space created successfully",
            extra={
                "space_id": space_id,
                "space_name": space["name"],
                "operation": "create",
            },
        )

        print(f"✓ Created space: {space_id}")
        print(f"  Name: {space['name']}")
        print(f"  Description: {space.get('description', 'N/A')}")

        # 2. Verify space exists
        logger.info(
            "Verifying space exists",
            extra={"space_id": space_id, "operation": "verify"},
        )
        info_response = client.spaces.get(id=space_id)
        space_info = info_response.body  # Access the body attribute
        print(f"✓ Space verified: {space_info['name']}")

        print("\n🎉 Success! Your space is ready to use.")
        print(f"   Space ID: {space_id}")
        print(f"   Access it at: http://localhost:5601/s/{space_id}/app/home")

        # Ask user about cleanup
        print(f"\nSpace '{space_info['name']}' was created for this example.")
        if should_cleanup("Delete the space? (y/N): "):
            print("Cleaning up...")
            logger.info(
                "Deleting space", extra={"space_id": space_id, "operation": "delete"}
            )
            try:
                client.spaces.delete(id=space_id)
                print("✓ Space deleted")
                logger.info(
                    "Space deleted successfully",
                    extra={"space_id": space_id, "operation": "delete"},
                )
            except Exception as e:
                # Some DELETE operations return empty responses
                # Check if the space was actually deleted
                try:
                    client.spaces.get(id=space_id)
                    print(f"❌ Failed to delete space: {e}")
                    logger.error(
                        "Failed to delete space",
                        extra={"space_id": space_id, "error": str(e)},
                    )
                except Exception:
                    # If get() fails, the space was likely deleted successfully
                    print("✓ Space deleted (confirmed)")
                    logger.info(
                        "Space deletion confirmed",
                        extra={"space_id": space_id, "operation": "delete"},
                    )
        else:
            print(f"✓ Space kept (ID: {space_id})")
            logger.info("Space kept by user choice", extra={"space_id": space_id})

    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(
            "Space example failed", extra={"error": str(e), "example": "simple_space"}
        )
    finally:
        logger.info("Simple space example completed")
        client.close()


if __name__ == "__main__":
    main()
