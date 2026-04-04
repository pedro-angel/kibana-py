#!/usr/bin/env python3
"""
Debug Spaces Example

This example helps you understand Kibana Spaces by:
1. Listing all available spaces
2. Showing detailed information about each space
3. Displaying space properties and configuration

This is useful for:
- Learning about the Spaces API structure
- Debugging space-related issues
- Understanding what spaces exist in your Kibana instance

Run this example:
    python examples/debug_spaces.py
"""

import json
import logging

from utils import (
    configure_example_telemetry,
    create_kibana_client,
    demonstrate_log_trace_correlation,
    demonstrate_structured_logging,
    print_config_info,
    print_telemetry_info,
    setup_telemetry_cleanup,
    should_enable_telemetry,
)

# Set up logger for this example
logger = logging.getLogger("kibana.examples.debug_spaces")


def main():
    # Print configuration information
    print_config_info()

    # Configure telemetry with enhanced log forwarding for debugging
    telemetry_enabled = should_enable_telemetry()
    traces_configured, logs_configured = configure_example_telemetry(
        enabled=telemetry_enabled,
        logs_enabled=telemetry_enabled,  # Enable logs when telemetry is enabled
    )
    print_telemetry_info()

    # Set up automatic telemetry cleanup
    setup_telemetry_cleanup()

    # Log example start with detailed context
    logger.info(
        "Starting debug spaces example",
        extra={
            "example": "debug_spaces",
            "traces_enabled": traces_configured,
            "logs_enabled": logs_configured,
        },
    )

    # Demonstrate structured logging capabilities
    if logs_configured:
        print("\n" + "=" * 60)
        print("LOG FORWARDING DEMONSTRATIONS")
        print("=" * 60)

        demonstrate_structured_logging()
        demonstrate_log_trace_correlation()

    # Initialize Kibana client with automatic configuration
    client = create_kibana_client()

    try:
        print("=" * 80)
        print("KIBANA SPACES DEBUG INFORMATION")
        print("=" * 80)

        # Create a span for the entire spaces debug operation
        try:
            from kibana.observability import create_span

            with create_span(
                "kibana_debug_spaces",
                attributes={
                    "operation.type": "debug",
                    "operation.name": "spaces_analysis",
                    "service.component": "debug_example",
                },
            ) as span:
                logger.info(
                    "Starting spaces debug analysis within trace span",
                    extra={
                        "operation": "spaces_debug_start",
                        "span_active": span is not None,
                    },
                )

                # Get all spaces
                print("\n📋 Fetching all spaces...")
                logger.info(
                    "Requesting all spaces",
                    extra={
                        "operation": "get_all_spaces",
                        "api_endpoint": "/api/spaces/space",
                    },
                )

                spaces_response = client.spaces.get_all()
                spaces = spaces_response.body  # Access the body attribute

                logger.info(
                    "Spaces retrieved successfully",
                    extra={
                        "operation": "get_all_spaces",
                        "spaces_count": len(spaces),
                        "api_endpoint": "/api/spaces/space",
                    },
                )

                if not spaces:
                    print("❌ No spaces found in Kibana")
                    logger.warning("No spaces found in Kibana instance")
                    return

                print(f"✓ Found {len(spaces)} space(s)\n")

                # Display each space
                for i, space in enumerate(spaces, 1):
                    space_id = space.get("id", "unknown")
                    space_name = space.get("name", "Unnamed")
                    disabled_features = space.get("disabledFeatures", [])

                    logger.info(
                        f"Processing space {i}",
                        extra={
                            "space_id": space_id,
                            "space_name": space_name,
                            "space_index": i,
                            "disabled_features_count": len(disabled_features),
                            "operation": "space_analysis",
                        },
                    )

                    # Log any disabled features as warnings
                    if disabled_features:
                        logger.warning(
                            f"Space {space_name} has disabled features",
                            extra={
                                "space_id": space_id,
                                "space_name": space_name,
                                "disabled_features": disabled_features,
                                "operation": "space_analysis",
                            },
                        )

                    print(f"\n{'=' * 80}")
                    print(f"SPACE {i}: {space_name}")
                    print(f"{'=' * 80}")

                    # Basic information
                    print("\n📌 Basic Information:")
                    print(f"   ID:          {space.get('id', 'N/A')}")
                    print(f"   Name:        {space.get('name', 'N/A')}")
                    print(f"   Description: {space.get('description', 'N/A')}")

                    # Visual properties
                    print("\n🎨 Visual Properties:")
                    print(f"   Color:    {space.get('color', 'N/A')}")
                    print(f"   Initials: {space.get('initials', 'N/A')}")

                    # Image URL (if present)
                    if space.get("imageUrl"):
                        print(f"   Image:    {space['imageUrl']}")

                    # Disabled features
                    print(f"\n🔒 Disabled Features ({len(disabled_features)}):")
                    if disabled_features:
                        for feature in disabled_features:
                            print(f"   - {feature}")
                    else:
                        print("   (All features enabled)")

                    # Access URL
                    if space_id:
                        if space_id == "default":
                            url = "http://localhost:5601/app/home"
                        else:
                            url = f"http://localhost:5601/s/{space_id}/app/home"
                        print("\n🔗 Access URL:")
                        print(f"   {url}")

                    # Full JSON (for debugging)
                    print("\n📄 Full JSON Response:")
                    print(json.dumps(space, indent=2))

                # Summary
                print(f"\n{'=' * 80}")
                print("SUMMARY")
                print(f"{'=' * 80}")
                print(f"Total spaces: {len(spaces)}")

                # Count spaces with disabled features
                spaces_with_disabled = sum(
                    1 for s in spaces if s.get("disabledFeatures", [])
                )
                print(f"Spaces with disabled features: {spaces_with_disabled}")

                # List all unique disabled features
                all_disabled = set()
                for space in spaces:
                    all_disabled.update(space.get("disabledFeatures", []))

                if all_disabled:
                    print("\nUnique disabled features across all spaces:")
                    for feature in sorted(all_disabled):
                        print(f"  - {feature}")

                # Log summary statistics
                logger.info(
                    "Spaces debug analysis completed",
                    extra={
                        "operation": "spaces_debug_complete",
                        "total_spaces": len(spaces),
                        "spaces_with_disabled_features": spaces_with_disabled,
                        "unique_disabled_features": list(all_disabled),
                        "status": "success",
                    },
                )

                print("\n✓ Debug information complete")

        except ImportError:
            # OpenTelemetry not available, continue without spans
            logger.info("OpenTelemetry not available, continuing without trace spans")

            # Get all spaces (without span)
            print("\n📋 Fetching all spaces...")
            logger.info(
                "Requesting all spaces",
                extra={
                    "operation": "get_all_spaces",
                    "api_endpoint": "/api/spaces/space",
                },
            )

            spaces_response = client.spaces.get_all()
            spaces = spaces_response.body

            if not spaces:
                print("❌ No spaces found in Kibana")
                logger.warning("No spaces found in Kibana instance")
                return

            print(f"✓ Found {len(spaces)} space(s)\n")
            # ... rest of the logic would be similar but without span context

        if logs_configured:
            print("\n📊 Check your APM server for detailed space analysis logs")
            print(
                "🔗 Logs should include trace IDs for correlation with this operation"
            )

    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(
            "Debug spaces example failed",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "example": "debug_spaces",
            },
        )
        import traceback

        traceback.print_exc()
    finally:
        logger.info("Debug spaces example completed")
        client.close()


if __name__ == "__main__":
    main()
