#!/usr/bin/env python3
"""
Debug Saved Objects Example

This example helps you understand Kibana Saved Objects by:
1. Creating a test saved object
2. Showing detailed information about the object
3. Demonstrating update and delete operations
4. Displaying saved object structure

This is useful for:
- Learning about the Saved Objects API structure
- Debugging saved object-related issues
- Understanding saved object attributes and metadata

Run this example:
    python examples/debug_saved_objects.py
"""

import json
import logging
import uuid

from utils import (
    configure_example_telemetry,
    create_kibana_client,
    demonstrate_log_trace_correlation,
    demonstrate_structured_logging,
    print_config_info,
    print_telemetry_info,
    setup_telemetry_cleanup,
    should_cleanup,
    should_enable_telemetry,
)

# Set up logger for this example
logger = logging.getLogger("kibana.examples.debug_saved_objects")


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

    # Generate unique ID for test object
    test_id = f"debug-test-{uuid.uuid4().hex[:8]}"

    # Log example start with detailed context
    logger.info(
        "Starting debug saved objects example",
        extra={
            "example": "debug_saved_objects",
            "test_object_id": test_id,
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
        print("KIBANA SAVED OBJECTS DEBUG INFORMATION")
        print("=" * 80)

        # Create a span for the entire saved objects debug operation
        try:
            from kibana.observability import create_span

            with create_span(
                "kibana_debug_saved_objects",
                attributes={
                    "operation.type": "debug",
                    "operation.name": "saved_objects_lifecycle",
                    "service.component": "debug_example",
                    "saved_object.type": "visualization",
                    "saved_object.id": test_id,
                },
            ) as span:
                logger.info(
                    "Starting saved objects debug lifecycle within trace span",
                    extra={
                        "operation": "saved_objects_debug_start",
                        "test_object_id": test_id,
                        "span_active": span is not None,
                    },
                )

                # 1. Create a test visualization
                print("\n📝 Creating test visualization...")
                logger.info(
                    "Creating test visualization",
                    extra={
                        "operation": "create_saved_object",
                        "object_type": "visualization",
                        "object_id": test_id,
                        "api_endpoint": "/api/saved_objects/visualization",
                    },
                )

                client.saved_objects.create(
                    type="visualization",
                    attributes={
                        "title": "Debug Test Visualization",
                        "visState": json.dumps({"type": "line"}),
                        "uiStateJSON": "{}",
                        "description": "Test visualization for debugging",
                        "version": 1,
                        "kibanaSavedObjectMeta": {
                            "searchSourceJSON": json.dumps({"query": "", "filter": []})
                        },
                    },
                    id=test_id,
                )

        except Exception:
            pass

        # 2. Retrieve the object
        print(f"\n{'=' * 80}")
        print("RETRIEVING SAVED OBJECT")
        print(f"{'=' * 80}")
        get_response = client.saved_objects.get(
            type="visualization",
            id=test_id,
        )
        retrieved = get_response.body

        print("\n📌 Basic Information:")
        print(f"   ID:      {retrieved['id']}")
        print(f"   Type:    {retrieved['type']}")
        print(f"   Version: {retrieved.get('version', 'N/A')}")

        print("\n📋 Attributes:")
        for key, value in retrieved.get("attributes", {}).items():
            if isinstance(value, str) and len(value) > 100:
                print(f"   {key}: {value[:100]}... (truncated)")
            else:
                print(f"   {key}: {value}")

        print("\n🔗 References:")
        references = retrieved.get("references", [])
        if references:
            for ref in references:
                print(
                    f"   - Type: {ref.get('type')}, ID: {ref.get('id')}, Name: {ref.get('name')}"
                )
        else:
            print("   (No references)")

        print("\n📊 Metadata:")
        if "updated_at" in retrieved:
            print(f"   Updated: {retrieved['updated_at']}")
        if "created_at" in retrieved:
            print(f"   Created: {retrieved['created_at']}")
        if "namespaces" in retrieved:
            print(f"   Namespaces: {retrieved['namespaces']}")

        # 3. Update the object
        print(f"\n{'=' * 80}")
        print("UPDATING SAVED OBJECT")
        print(f"{'=' * 80}")
        update_response = client.saved_objects.update(
            type="visualization",
            id=test_id,
            attributes={
                "title": "Debug Test Visualization (Updated)",
                "visState": json.dumps({"type": "line"}),
                "uiStateJSON": "{}",
                "description": "Updated test visualization",
                "version": 1,
                "kibanaSavedObjectMeta": {
                    "searchSourceJSON": json.dumps({"query": "", "filter": []})
                },
            },
        )
        updated = update_response.body

        print("✓ Updated saved object")
        print(f"   Old version: {retrieved.get('version', 'N/A')}")
        print(f"   New version: {updated.get('version', 'N/A')}")
        print(f"   Old title: {retrieved['attributes']['title']}")
        print(f"   New title: {updated['attributes']['title']}")

        # 4. Demonstrate version conflict
        print(f"\n{'=' * 80}")
        print("DEMONSTRATING VERSION CONFLICT")
        print(f"{'=' * 80}")
        print("Attempting to update with old version...")
        try:
            client.saved_objects.update(
                type="visualization",
                id=test_id,
                attributes={
                    "title": "This should fail",
                    "visState": "{}",
                    "uiStateJSON": "{}",
                    "description": "",
                    "version": 1,
                    "kibanaSavedObjectMeta": {"searchSourceJSON": "{}"},
                },
                version=retrieved.get("version"),  # Old version
            )
            print("❌ Update succeeded (unexpected)")
        except Exception as e:
            print(f"✓ Update failed as expected: {type(e).__name__}")
            print("   This demonstrates optimistic concurrency control")

        # Ask user about cleanup
        print(f"\n{'=' * 80}")
        print("CLEANUP")
        print(f"{'=' * 80}")
        if should_cleanup("Delete the test visualization? (y/N): "):
            print("Deleting...")
            try:
                client.saved_objects.delete(type="visualization", id=test_id)
                print("✓ Test visualization deleted")
            except Exception as e:
                # Check if actually deleted
                try:
                    client.saved_objects.get(type="visualization", id=test_id)
                    print(f"❌ Failed to delete: {e}")
                except Exception:
                    print("✓ Test visualization deleted (confirmed)")
        else:
            print(f"✓ Test visualization kept (ID: {test_id})")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()
