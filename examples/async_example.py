"""
Comprehensive async example demonstrating AsyncKibana client with all namespace clients.

This example shows:
1. Async context manager usage for automatic cleanup
2. Actions (connectors) management
3. Spaces management
4. Saved objects management
5. Status monitoring
6. Concurrent API operations
7. Error handling
"""

import asyncio
import sys
import uuid
from pathlib import Path

# Add parent directory to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent))

from examples.utils import (
    configure_example_telemetry,
    create_async_kibana_client,
    print_config_info,
    print_kept,
    print_telemetry_info,
    resource_prefix,
    setup_telemetry_cleanup,
    should_cleanup,
    should_enable_telemetry,
)
from kibana.exceptions import NotFoundError


async def demonstrate_actions(client):
    """Demonstrate async actions (connectors) operations."""
    import logging

    logger = logging.getLogger(__name__)

    print("\n" + "=" * 80)
    print("Actions (Connectors) Management")
    print("=" * 80)

    connector_id = None

    try:
        # List available connector types
        print("\n📋 Listing connector types...")
        logger.info(
            "Listing connector types",
            extra={"operation": "list_connector_types", "async_mode": True},
        )

        types_response = await client.actions.list_types()
        connector_types = types_response.body
        print(f"   ✓ Found {len(connector_types)} connector type(s)")
        for ct in connector_types[:5]:
            print(f"     - {ct['id']}: {ct['name']}")

        logger.info(
            "Connector types listed successfully",
            extra={
                "connector_type_count": len(connector_types),
                "operation": "list_connector_types",
                "async_mode": True,
                "status": "success",
            },
        )

        # Create a server-log connector with a stable ID (own scope): clear
        # only THIS example's own prior connector, then create fresh
        prefix = resource_prefix(__file__)
        connector_name = f"{prefix}-connector"
        stable_connector_id = f"{prefix}-conn"

        try:
            await client.actions.delete(id=stable_connector_id)
        except NotFoundError:
            pass

        logger.info(
            "Creating async server-log connector",
            extra={
                "connector_name": connector_name,
                "connector_type": ".server-log",
                "operation": "create_connector",
                "async_mode": True,
            },
        )

        create_response = await client.actions.create(
            id=stable_connector_id,
            name=connector_name,
            connector_type_id=".server-log",
            config={},
        )
        connector = create_response.body
        connector_id = connector["id"]
        print(f"   ✓ Created connector: {connector['name']} (ID: {connector_id})")

        logger.info(
            "Async connector created successfully",
            extra={
                "connector_id": connector_id,
                "connector_name": connector["name"],
                "connector_type": ".server-log",
                "operation": "create_connector",
                "async_mode": True,
                "status": "success",
            },
        )

        # Get the connector
        print(f"\n🔍 Retrieving connector {connector_id}...")
        get_response = await client.actions.get(id=connector_id)
        retrieved = get_response.body
        print(f"   ✓ Retrieved: {retrieved['name']}")

        # Execute the connector
        print("\n▶️  Executing connector...")
        logger.info(
            "Executing async connector",
            extra={
                "connector_id": connector_id,
                "operation": "execute_connector",
                "async_mode": True,
            },
        )

        execute_response = await client.actions.execute(
            id=connector_id,
            params={"message": "Test message from async example", "level": "info"},
        )
        result = execute_response.body
        print(f"   ✓ Execution status: {result['status']}")

        logger.info(
            "Async connector executed successfully",
            extra={
                "connector_id": connector_id,
                "execution_status": result["status"],
                "operation": "execute_connector",
                "async_mode": True,
                "status": "success",
            },
        )

        # Update the connector
        print("\n✏️  Updating connector...")
        new_name = f"{connector_name}-updated"
        update_response = await client.actions.update(id=connector_id, name=new_name)
        updated = update_response.body
        print(f"   ✓ Updated name: {updated['name']}")

        # List all connectors
        print("\n📋 Listing all connectors...")
        all_response = await client.actions.get_all()
        all_connectors = all_response.body
        print(f"   ✓ Total connectors: {len(all_connectors)}")

        # Cleanup
        if should_cleanup("\n🗑️  Delete the connector? (y/N): "):
            print("   Deleting connector...")
            try:
                await client.actions.delete(id=connector_id)
                print("   ✓ Connector deleted")
            except Exception:
                # Verify deletion
                try:
                    await client.actions.get(id=connector_id)
                    print("   ❌ Failed to delete connector")
                except NotFoundError:
                    print("   ✓ Connector deleted (confirmed)")
            connector_id = None
        else:
            print_kept([("connector", connector_id)])

    except Exception as e:
        print(f"\n❌ Error in actions demo: {e}")
        import traceback

        traceback.print_exc()

    return connector_id


async def demonstrate_spaces(client):
    """Demonstrate async spaces operations."""
    print("\n" + "=" * 80)
    print("Spaces Management")
    print("=" * 80)

    space_id = None

    try:
        # List all spaces
        print("\n📋 Listing all spaces...")
        all_response = await client.spaces.get_all()
        spaces = all_response.body
        print(f"   ✓ Found {len(spaces)} space(s)")
        for space in spaces[:3]:
            print(f"     - {space['name']} (id: {space['id']})")

        # Get default space
        print("\n🔍 Retrieving default space...")
        default_response = await client.spaces.get(id="default")
        default_space = default_response.body
        print(f"   ✓ Default space: {default_space['name']}")

        # Create a new space with a stable ID (own scope): clear only THIS
        # example's own prior space, then create fresh
        space_id = f"{resource_prefix(__file__)}-space"
        space_name = "Async Example Space"

        try:
            await client.spaces.delete(id=space_id)
        except NotFoundError:
            pass

        create_response = await client.spaces.create(
            id=space_id,
            name=space_name,
            description="Space created by async example",
            color="#FF6B6B",
            initials="AE",
        )
        space = create_response.body
        print(f"   ✓ Created space: {space['name']} (ID: {space_id})")

        # Get the space
        print(f"\n🔍 Retrieving space {space_id}...")
        get_response = await client.spaces.get(id=space_id)
        retrieved = get_response.body
        print(f"   ✓ Retrieved: {retrieved['name']}")
        print(f"     Color: {retrieved['color']}")
        print(f"     Initials: {retrieved['initials']}")

        # Update the space
        print("\n✏️  Updating space...")
        new_name = f"{space_name} (Updated)"
        update_response = await client.spaces.update(
            id=space_id, name=new_name, description="Updated by async example"
        )
        updated = update_response.body
        print(f"   ✓ Updated name: {updated['name']}")

        # Cleanup
        if should_cleanup("\n🗑️  Delete the space? (y/N): "):
            print("   Deleting space...")
            await client.spaces.delete(id=space_id)
            print("   ✓ Space deleted")
            space_id = None
        else:
            print_kept([("space", space_id)])

    except Exception as e:
        print(f"\n❌ Error in spaces demo: {e}")
        import traceback

        traceback.print_exc()

    return space_id


async def demonstrate_saved_objects(client):
    """Demonstrate async saved objects operations."""
    print("\n" + "=" * 80)
    print("Saved Objects Management")
    print("=" * 80)

    object_id = None

    try:
        # Create a saved object with a stable ID (own scope): clear only THIS
        # example's own prior saved object, then create fresh
        print("\n➕ Creating saved object...")
        object_id = f"{resource_prefix(__file__)}-obj"

        try:
            await client.saved_objects.delete(type="config", id=object_id)
        except NotFoundError:
            pass

        attributes = {
            "title": f"Async Example Config {uuid.uuid4().hex[:4]}",
            "buildNum": 99999,
        }
        create_response = await client.saved_objects.create(
            type="config", id=object_id, attributes=attributes
        )
        saved_object = create_response.body
        print(f"   ✓ Created: {saved_object['attributes']['title']}")
        print(f"     ID: {object_id}")
        print(f"     Type: {saved_object['type']}")

        # Get the saved object
        print(f"\n🔍 Retrieving saved object {object_id}...")
        get_response = await client.saved_objects.get(type="config", id=object_id)
        retrieved = get_response.body
        print(f"   ✓ Retrieved: {retrieved['attributes']['title']}")
        print(f"     Build number: {retrieved['attributes']['buildNum']}")

        # Update the saved object
        print("\n✏️  Updating saved object...")
        new_attributes = {
            "title": "Async Example Config (Updated)",
            "buildNum": 88888,
        }
        update_response = await client.saved_objects.update(
            type="config", id=object_id, attributes=new_attributes
        )
        updated = update_response.body
        print(f"   ✓ Updated title: {updated['attributes']['title']}")
        print(f"     New build number: {updated['attributes']['buildNum']}")

        # Cleanup
        if should_cleanup("\n🗑️  Delete the saved object? (y/N): "):
            print("   Deleting saved object...")
            await client.saved_objects.delete(type="config", id=object_id)
            print("   ✓ Saved object deleted")
            object_id = None
        else:
            print_kept([("saved object", object_id)])

    except Exception as e:
        print(f"\n❌ Error in saved objects demo: {e}")
        import traceback

        traceback.print_exc()

    return object_id


async def demonstrate_status(client):
    """Demonstrate async status operations."""
    print("\n" + "=" * 80)
    print("Status Monitoring")
    print("=" * 80)

    try:
        # Get Kibana status
        print("\n📊 Fetching Kibana status...")
        status_response = await client.status.get_status()
        status = status_response.body

        print(f"   ✓ Overall status: {status['status']['overall']['level']}")
        print(f"   ✓ Version: {status['version']['number']}")
        print(f"   ✓ Build: {status['version']['build_number']}")

        # Get Kibana stats
        print("\n📈 Fetching Kibana stats...")
        await client.status.get_stats()
        print("   ✓ Stats retrieved successfully")

    except Exception as e:
        print(f"\n❌ Error in status demo: {e}")
        import traceback

        traceback.print_exc()


async def demonstrate_concurrent_operations(client):
    """Demonstrate concurrent async operations."""
    print("\n" + "=" * 80)
    print("Concurrent Operations")
    print("=" * 80)

    try:
        print("\n⚡ Executing multiple operations concurrently...")

        # Execute multiple operations at the same time
        results = await asyncio.gather(
            client.status.get_status(),
            client.spaces.get_all(),
            client.actions.list_types(),
            return_exceptions=True,
        )

        print(f"   ✓ All {len(results)} operations completed")

        # Check results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"     ❌ Operation {i+1} failed: {result}")
            else:
                print(f"     ✓ Operation {i+1} succeeded")

    except Exception as e:
        print(f"\n❌ Error in concurrent operations: {e}")
        import traceback

        traceback.print_exc()


async def demonstrate_options_pattern(client):
    """Demonstrate the options pattern for per-request configuration."""
    print("\n" + "=" * 80)
    print("Options Pattern")
    print("=" * 80)

    try:
        # Create a client with custom timeout
        print("\n⚙️  Creating client with custom timeout (60s)...")
        custom_client = client.options(request_timeout=60.0)

        # Make a request with the custom client
        print("   Making request with custom timeout...")
        await custom_client.status.get_status()
        print("   ✓ Request completed successfully")

        # Create a client with custom headers
        print("\n⚙️  Creating client with custom headers...")
        headers_client = client.options(headers={"X-Custom-Header": "async-example"})

        # Make a request with custom headers
        print("   Making request with custom headers...")
        await headers_client.status.get_status()
        print("   ✓ Request completed successfully")

    except Exception as e:
        print(f"\n❌ Error in options pattern demo: {e}")
        import traceback

        traceback.print_exc()


async def main():
    """Main async function demonstrating all AsyncKibana features."""
    print("=" * 80)
    print("AsyncKibana Client - Comprehensive Example")
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
                    "example": "async_example",
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
                "example": "async_example",
                "async_mode": True,
            },
        )

    # Use async context manager for automatic cleanup
    async with create_async_kibana_client() as client:
        print("\n✓ AsyncKibana client created (using async context manager)")

        # Demonstrate each namespace client
        await demonstrate_status(client)
        await demonstrate_actions(client)
        await demonstrate_spaces(client)
        await demonstrate_saved_objects(client)

        # Demonstrate advanced features
        await demonstrate_concurrent_operations(client)
        await demonstrate_options_pattern(client)

    print("\n✓ Client closed automatically (async context manager)")

    print("\n" + "=" * 80)
    print("Example Complete!")
    print("=" * 80)
    print()
    print("This example demonstrated:")
    print("  ✓ Async context manager usage")
    print("  ✓ Actions (connectors) management")
    print("  ✓ Spaces management")
    print("  ✓ Saved objects management")
    print("  ✓ Status monitoring")
    print("  ✓ Concurrent operations")
    print("  ✓ Options pattern")
    print()


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
