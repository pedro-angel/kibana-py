#!/usr/bin/env python3
"""
Actions Management Example

This example demonstrates comprehensive usage of the ActionsClient for managing
Kibana connectors (actions). It covers:

1. Listing available connector types
2. Creating different types of connectors
3. Retrieving connector information
4. Updating connector configuration
5. Executing connectors
6. Deleting connectors
7. Error handling

Run this example:
    python examples/actions_management.py
"""

from datetime import UTC, datetime

from utils import (
    configure_example_telemetry,
    create_kibana_client,
    print_config_info,
    print_telemetry_info,
    setup_telemetry_cleanup,
    should_cleanup,
    should_enable_telemetry,
)


def list_connector_types(client):
    """List all available connector types."""
    print("\n=== Available Connector Types ===")

    try:
        types_response = client.actions.list_types()
        types = types_response.body

        print(f"Found {len(types)} connector types:")
        for connector_type in types:
            type_id = connector_type.get("id", "unknown")
            name = connector_type.get("name", "Unknown")
            enabled = connector_type.get("enabled", False)
            status = "✓" if enabled else "✗"
            print(f"  {status} {type_id:20s} - {name}")

        return types
    except Exception as e:
        print(f"❌ Error listing connector types: {e}")
        return []


def list_existing_connectors(client):
    """List all existing connectors."""
    print("\n=== Existing Connectors ===")

    try:
        connectors_response = client.actions.get_all()
        connectors = connectors_response.body

        if not connectors:
            print("No connectors found")
            return []

        print(f"Found {len(connectors)} connectors:")
        for connector in connectors:
            conn_id = connector.get("id", "unknown")
            name = connector.get("name", "Unknown")
            type_id = connector.get("connector_type_id", "unknown")
            print(f"  - {name} ({type_id})")
            print(f"    ID: {conn_id}")

        return connectors
    except Exception as e:
        print(f"❌ Error listing connectors: {e}")
        return []


def create_index_connector(client):
    """Create an index connector for writing to Elasticsearch."""
    import logging

    logger = logging.getLogger(__name__)

    print("\n=== Creating Index Connector ===")

    try:
        logger.info(
            "Creating index connector",
            extra={
                "connector_type": ".index",
                "target_index": "kibana-connector-example",
                "operation": "create_connector",
            },
        )

        connector_response = client.actions.create(
            name="Example Index Connector",
            connector_type_id=".index",
            config={
                "index": "kibana-connector-example",
                "refresh": True,
                "executionTimeField": "@timestamp",
            },
        )

        connector = connector_response.body
        connector_id = connector["id"]
        print(f"✓ Created index connector: {connector_id}")
        print(f"  Name: {connector['name']}")
        print(f"  Type: {connector['connector_type_id']}")
        print(f"  Index: {connector['config']['index']}")

        logger.info(
            "Index connector created successfully",
            extra={
                "connector_id": connector_id,
                "connector_name": connector["name"],
                "target_index": connector["config"]["index"],
                "operation": "create_connector",
                "status": "success",
            },
        )

        return connector_id
    except Exception as e:
        print(f"❌ Error creating index connector: {e}")
        logger.error(
            f"Failed to create index connector: {e}",
            extra={
                "connector_type": ".index",
                "operation": "create_connector",
                "status": "error",
                "error_type": type(e).__name__,
            },
        )
        return None


def create_webhook_connector(client):
    """Create a webhook connector for HTTP requests."""
    print("\n=== Creating Webhook Connector ===")

    try:
        connector_response = client.actions.create(
            name="Example Webhook Connector",
            connector_type_id=".webhook",
            config={
                "url": "https://httpbin.org/post",
                "method": "post",
                "headers": {"Content-Type": "application/json"},
                "hasAuth": False,
            },
        )

        connector = connector_response.body
        connector_id = connector["id"]
        print(f"✓ Created webhook connector: {connector_id}")
        print(f"  Name: {connector['name']}")
        print(f"  Type: {connector['connector_type_id']}")
        print(f"  URL: {connector['config']['url']}")

        return connector_id
    except Exception as e:
        print(f"❌ Error creating webhook connector: {e}")
        return None


def create_server_log_connector(client):
    """Create a server log connector for logging."""
    print("\n=== Creating Server Log Connector ===")

    try:
        connector_response = client.actions.create(
            name="Example Server Log Connector",
            connector_type_id=".server-log",
            config={},  # Server log connector has no configuration
        )

        connector = connector_response.body
        connector_id = connector["id"]
        print(f"✓ Created server log connector: {connector_id}")
        print(f"  Name: {connector['name']}")
        print(f"  Type: {connector['connector_type_id']}")

        return connector_id
    except Exception as e:
        print(f"❌ Error creating server log connector: {e}")
        return None


def get_connector_info(client, connector_id):
    """Get detailed information about a connector."""
    print(f"\n=== Getting Connector Info: {connector_id} ===")

    try:
        connector_response = client.actions.get(id=connector_id)
        connector = connector_response.body

        print("✓ Retrieved connector information:")
        print(f"  ID: {connector['id']}")
        print(f"  Name: {connector['name']}")
        print(f"  Type: {connector['connector_type_id']}")
        print(f"  Is Preconfigured: {connector.get('is_preconfigured', False)}")
        print(f"  Is Deprecated: {connector.get('is_deprecated', False)}")
        print(f"  Is Missing Secrets: {connector.get('is_missing_secrets', False)}")

        if "config" in connector:
            print("  Configuration:")
            for key, value in connector["config"].items():
                print(f"    {key}: {value}")

        return connector
    except Exception as e:
        print(f"❌ Error getting connector info: {e}")
        return None


def update_connector(client, connector_id):
    """Update a connector's configuration."""
    print(f"\n=== Updating Connector: {connector_id} ===")

    try:
        # Get current connector to preserve config
        current = client.actions.get(id=connector_id).body

        # Update the connector name (must provide config as well)
        updated_response = client.actions.update(
            id=connector_id,
            name="Updated Example Connector",
            config=current.get("config", {}),
        )

        updated = updated_response.body
        print("✓ Updated connector:")
        print(f"  New Name: {updated['name']}")

        return updated
    except Exception as e:
        print(f"❌ Error updating connector: {e}")
        print("  Note: Some connector types may not support updates")
        return None


def execute_index_connector(client, connector_id):
    """Execute an index connector to write documents."""
    import logging

    logger = logging.getLogger(__name__)

    print(f"\n=== Executing Index Connector: {connector_id} ===")

    try:
        # Prepare documents to write
        documents = [
            {
                "message": "First example document",
                "level": "INFO",
                "service": "example-app",
                "@timestamp": datetime.now(UTC).isoformat(),
            },
            {
                "message": "Second example document",
                "level": "DEBUG",
                "service": "example-app",
                "@timestamp": datetime.now(UTC).isoformat(),
            },
        ]

        logger.info(
            "Executing index connector",
            extra={
                "connector_id": connector_id,
                "document_count": len(documents),
                "operation": "execute_connector",
            },
        )

        # Execute the connector
        result_response = client.actions.execute(
            id=connector_id, params={"documents": documents}
        )

        result = result_response.body
        print("✓ Connector executed successfully")
        print(f"  Status: {result.get('status', 'unknown')}")
        print(f"  Documents written: {len(documents)}")

        logger.info(
            "Index connector executed successfully",
            extra={
                "connector_id": connector_id,
                "document_count": len(documents),
                "execution_status": result.get("status", "unknown"),
                "operation": "execute_connector",
                "status": "success",
            },
        )

        return result
    except Exception as e:
        print(f"❌ Error executing connector: {e}")
        logger.error(
            f"Failed to execute index connector: {e}",
            extra={
                "connector_id": connector_id,
                "operation": "execute_connector",
                "status": "error",
                "error_type": type(e).__name__,
            },
        )
        return None


def execute_webhook_connector(client, connector_id):
    """Execute a webhook connector to send HTTP request."""
    print(f"\n=== Executing Webhook Connector: {connector_id} ===")

    try:
        # Prepare webhook payload
        payload = {
            "message": "Hello from Kibana connector!",
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "kibana-py-example",
        }

        # Execute the connector
        result_response = client.actions.execute(
            id=connector_id, params={"body": str(payload)}
        )

        result = result_response.body
        print("✓ Webhook executed successfully")
        print(f"  Status: {result.get('status', 'unknown')}")

        return result
    except Exception as e:
        print(f"❌ Error executing webhook: {e}")
        return None


def execute_server_log_connector(client, connector_id):
    """Execute a server log connector to write logs."""
    print(f"\n=== Executing Server Log Connector: {connector_id} ===")

    try:
        # Execute the connector with log message
        result_response = client.actions.execute(
            id=connector_id,
            params={"message": "Example log message from kibana-py", "level": "info"},
        )

        result = result_response.body
        print("✓ Server log executed successfully")
        print(f"  Status: {result.get('status', 'unknown')}")

        return result
    except Exception as e:
        print(f"❌ Error executing server log: {e}")
        return None


def delete_connector(client, connector_id):
    """Delete a connector."""
    print(f"\n=== Deleting Connector: {connector_id} ===")

    try:
        client.actions.delete(id=connector_id)
        print("✓ Connector deleted")

        # Verify deletion
        try:
            client.actions.get(id=connector_id)
            print("⚠️  Warning: Connector still exists after deletion")
        except Exception:
            print("✓ Deletion confirmed")

    except Exception as e:
        # Some DELETE operations return empty responses
        # Check if the connector was actually deleted
        try:
            client.actions.get(id=connector_id)
            print(f"❌ Failed to delete connector: {e}")
        except Exception:
            print("✓ Connector deleted (confirmed)")


def cleanup_connectors(client, connector_ids):
    """Clean up created connectors."""
    if not connector_ids:
        return

    print("\n=== Cleanup ===")
    print(f"Created {len(connector_ids)} connectors during this example.")

    if should_cleanup("Delete all created connectors? (y/N): "):
        print("Cleaning up...")
        for connector_id in connector_ids:
            try:
                delete_connector(client, connector_id)
            except Exception as e:
                print(f"❌ Error deleting {connector_id}: {e}")
    else:
        print("✓ Connectors kept:")
        for connector_id in connector_ids:
            print(f"  - {connector_id}")


def main():
    """Run the complete actions management example."""
    print("=" * 70)
    print("Kibana Python Client - Actions Management Example")
    print("=" * 70)

    # Print configuration info
    print_config_info()

    # Configure telemetry with production-ready error handling
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
                "Actions management example started",
                extra={
                    "traces_enabled": traces_configured,
                    "logs_enabled": logs_configured,
                    "example": "actions_management",
                },
            )
    except Exception as e:
        print(f"⚠️  Telemetry configuration failed: {e}")
        print("   Continuing without telemetry...")
        logger.warning(
            f"Telemetry configuration failed: {e}",
            extra={
                "error_type": "telemetry_config_error",
                "example": "actions_management",
            },
        )

    # Initialize client
    client = create_kibana_client()
    created_connector_ids = []

    try:
        # List available connector types
        list_connector_types(client)

        # List existing connectors
        list_existing_connectors(client)

        # Create different types of connectors
        index_connector_id = create_index_connector(client)
        if index_connector_id:
            created_connector_ids.append(index_connector_id)

        webhook_connector_id = create_webhook_connector(client)
        if webhook_connector_id:
            created_connector_ids.append(webhook_connector_id)

        server_log_connector_id = create_server_log_connector(client)
        if server_log_connector_id:
            created_connector_ids.append(server_log_connector_id)

        # Get detailed info about the first connector
        if index_connector_id:
            get_connector_info(client, index_connector_id)

        # Update a connector
        if index_connector_id:
            update_connector(client, index_connector_id)

        # Execute connectors
        if index_connector_id:
            execute_index_connector(client, index_connector_id)

        if webhook_connector_id:
            execute_webhook_connector(client, webhook_connector_id)

        if server_log_connector_id:
            execute_server_log_connector(client, server_log_connector_id)

        # Summary
        print("\n" + "=" * 70)
        print("✅ Actions Management Example Completed!")
        print("=" * 70)
        print(f"\nCreated {len(created_connector_ids)} connectors:")
        for connector_id in created_connector_ids:
            print(f"  - {connector_id}")

        print("\nYou can view these connectors in Kibana:")
        print("  Stack Management → Connectors")
        print(
            "  URL: http://localhost:5601/app/management/insightsAndAlerting/connectors"
        )

        # Cleanup
        cleanup_connectors(client, created_connector_ids)

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()
