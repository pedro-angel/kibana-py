#!/usr/bin/env python3
"""
Simple Index Connector Example

This example shows the minimal code needed to:
1. Create an index connector for "miconnectedindex"
2. Write a document to the index
3. Clean up the connector

Run this example:
    python examples/simple_index_connector.py
"""

import logging
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

# Set up logger for this example
logger = logging.getLogger("kibana.examples.simple_index_connector")


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
        "Starting simple index connector example",
        extra={
            "example": "simple_index_connector",
            "traces_enabled": traces_configured,
            "logs_enabled": logs_configured,
        },
    )

    # Initialize Kibana client with automatic configuration
    client = create_kibana_client()

    try:
        # 1. Create index connector
        print("Creating index connector...")
        logger.info(
            "Creating index connector",
            extra={
                "connector_type": ".index",
                "target_index": "miconnectedindex",
                "operation": "create",
            },
        )

        connector_response = client.actions.create(
            name="My Connected Index Connector",
            connector_type_id=".index",
            config={
                "index": "miconnectedindex",
                "refresh": True,
                "executionTimeField": "@timestamp",
            },
        )

        connector = connector_response.body  # Access the body attribute
        connector_id = connector["id"]

        logger.info(
            "Index connector created successfully",
            extra={
                "connector_id": connector_id,
                "connector_name": connector["name"],
                "connector_type": ".index",
                "target_index": "miconnectedindex",
                "operation": "create",
            },
        )

        print(f"✓ Created connector: {connector_id}")

        # 2. Write a document
        print("Writing document to index...")
        document = {
            "message": "Hello from Kibana connector!",
            "level": "INFO",
            "service": "example-app",
            "@timestamp": datetime.now(UTC).isoformat(),
        }

        logger.info(
            "Executing connector to write document",
            extra={
                "connector_id": connector_id,
                "document_count": 1,
                "operation": "execute",
            },
        )

        result_response = client.actions.execute(
            id=connector_id, params={"documents": [document]}
        )

        result = result_response.body  # Access the body attribute

        logger.info(
            "Document written successfully",
            extra={
                "connector_id": connector_id,
                "execution_status": result.get("status", "unknown"),
                "operation": "execute",
            },
        )

        print("✓ Document written successfully")
        print(f"  Status: {result.get('status', 'unknown')}")

        # 3. Verify connector exists
        logger.info(
            "Verifying connector exists",
            extra={"connector_id": connector_id, "operation": "verify"},
        )
        info_response = client.actions.get(id=connector_id)
        connector_info = info_response.body  # Access the body attribute
        print(f"✓ Connector verified: {connector_info['name']}")

        print("\n🎉 Success! Check your 'miconnectedindex' index in Elasticsearch.")
        print(f"   Connector ID: {connector_id}")
        print("   Kibana Dev Tools: http://localhost:5601/app/dev_tools#/console")
        print("   Try this query: GET miconnectedindex/_search")

        # Ask user about cleanup
        print(f"\nConnector '{connector_info['name']}' was created for this example.")
        if should_cleanup("Delete the connector? (y/N): "):
            print("Cleaning up...")
            logger.info(
                "Deleting connector",
                extra={"connector_id": connector_id, "operation": "delete"},
            )
            try:
                client.actions.delete(id=connector_id)
                print("✓ Connector deleted")
                logger.info(
                    "Connector deleted successfully",
                    extra={"connector_id": connector_id, "operation": "delete"},
                )
            except Exception as e:
                # Some DELETE operations return empty responses which can cause JSON parsing errors
                # Check if the connector was actually deleted
                try:
                    client.actions.get(id=connector_id)
                    print(f"❌ Failed to delete connector: {e}")
                    logger.error(
                        "Failed to delete connector",
                        extra={"connector_id": connector_id, "error": str(e)},
                    )
                except Exception:
                    # If get() fails, the connector was likely deleted successfully
                    print("✓ Connector deleted (confirmed)")
                    logger.info(
                        "Connector deletion confirmed",
                        extra={"connector_id": connector_id, "operation": "delete"},
                    )
        else:
            print(f"✓ Connector kept (ID: {connector_id})")
            logger.info(
                "Connector kept by user choice", extra={"connector_id": connector_id}
            )

    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(
            "Index connector example failed",
            extra={"error": str(e), "example": "simple_index_connector"},
        )
    finally:
        logger.info("Simple index connector example completed")
        client.close()


if __name__ == "__main__":
    main()
