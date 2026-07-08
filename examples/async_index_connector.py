#!/usr/bin/env python3
"""
Async Index Connector Example

This example demonstrates the async Kibana client API:
1. Create an index connector for "miconnectedindex"
2. Write multiple documents asynchronously
3. Handle errors and cleanup

Run this example:
    python examples/async_index_connector.py
"""

import asyncio
from datetime import datetime
from typing import Any

from utils import (
    configure_example_telemetry,
    create_async_kibana_client,
    print_config_info,
    print_kept,
    print_telemetry_info,
    setup_telemetry_cleanup,
    should_cleanup,
    should_enable_telemetry,
)


async def create_connector(client, index_name: str = "miconnectedindex") -> str:
    """Create an index connector and return its ID."""
    import logging

    logger = logging.getLogger(__name__)

    print(f"Creating index connector for '{index_name}'...")

    logger.info(
        "Creating async index connector",
        extra={
            "index_name": index_name,
            "connector_type": ".index",
            "operation": "create_connector",
            "async_mode": True,
        },
    )

    response = await client.actions.create(
        name=f"Async Index Connector - {index_name}",
        connector_type_id=".index",
        config={
            "index": index_name,
            "refresh": True,
            "executionTimeField": "@timestamp",
        },
    )

    connector = response.body  # Access the body attribute
    connector_id = connector["id"]
    print(f"✓ Created connector: {connector_id}")

    logger.info(
        "Async index connector created successfully",
        extra={
            "connector_id": connector_id,
            "index_name": index_name,
            "connector_name": connector["name"],
            "operation": "create_connector",
            "async_mode": True,
            "status": "success",
        },
    )

    return connector_id


async def write_document(
    client, connector_id: str, document: dict[str, Any]
) -> dict[str, Any]:
    """Write a single document using the connector."""
    # Add timestamp if not present
    if "@timestamp" not in document:
        document["@timestamp"] = datetime.utcnow().isoformat()

    result = await client.actions.execute(
        id=connector_id, params={"documents": [document]}
    )

    return result


async def write_documents_batch(
    client, connector_id: str, documents: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Write multiple documents concurrently."""
    import logging

    logger = logging.getLogger(__name__)

    print(f"Writing {len(documents)} documents concurrently...")

    logger.info(
        "Starting async batch document write",
        extra={
            "connector_id": connector_id,
            "document_count": len(documents),
            "operation": "write_documents_batch",
            "async_mode": True,
        },
    )

    # Create tasks for concurrent execution
    tasks = [write_document(client, connector_id, doc) for doc in documents]

    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    successful = 0
    failed = 0

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"  ❌ Document {i+1} failed: {result}")
            failed += 1
        else:
            print(f"  ✓ Document {i+1} written successfully")
            successful += 1

    print(f"Batch complete: {successful} successful, {failed} failed")

    logger.info(
        "Async batch document write completed",
        extra={
            "connector_id": connector_id,
            "total_documents": len(documents),
            "successful_documents": successful,
            "failed_documents": failed,
            "operation": "write_documents_batch",
            "async_mode": True,
            "status": "completed",
        },
    )

    return results


async def main():
    """Main async function."""
    print("=== Async Index Connector Example ===\n")

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
                "Async index connector example started",
                extra={
                    "traces_enabled": traces_configured,
                    "logs_enabled": logs_configured,
                    "example": "async_index_connector",
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
                "example": "async_index_connector",
                "async_mode": True,
            },
        )

    # Create async Kibana client with automatic configuration
    client = create_async_kibana_client()
    connector_id: str | None = None
    created: list[tuple[str, str]] = []

    try:
        # 1. Create the connector
        connector_id = await create_connector(client)
        created.append(("index connector", connector_id))

        # 2. Prepare sample documents
        sample_documents = [
            {
                "message": "User login successful",
                "level": "INFO",
                "service": "auth-service",
                "user_id": "user001",
                "ip_address": "192.168.1.10",
            },
            {
                "message": "Database query executed",
                "level": "DEBUG",
                "service": "database",
                "query_time_ms": 45,
                "table": "users",
            },
            {
                "message": "Cache miss occurred",
                "level": "WARNING",
                "service": "cache-service",
                "cache_key": "user:001:profile",
                "fallback_used": True,
            },
            {
                "message": "API rate limit exceeded",
                "level": "ERROR",
                "service": "api-gateway",
                "client_id": "client123",
                "limit": 1000,
                "current_count": 1001,
            },
            {
                "message": "Scheduled task completed",
                "level": "INFO",
                "service": "scheduler",
                "task_name": "daily_cleanup",
                "duration_seconds": 120,
            },
        ]

        # 3. Write documents in batch (concurrently)
        await write_documents_batch(client, connector_id, sample_documents)

        # 4. Write a single document
        print("\nWriting single document...")
        single_doc = {
            "message": "Single document test",
            "level": "INFO",
            "service": "example-service",
            "test": True,
        }

        await write_document(client, connector_id, single_doc)
        print("✓ Single document written successfully")

        # 5. Get connector information
        print("\nRetrieving connector information...")
        response = await client.actions.get(id=connector_id)
        connector_info = response.body  # Access the body attribute
        print(f"✓ Connector: {connector_info['name']}")
        print(f"  Type: {connector_info['connector_type_id']}")
        print(f"  Index: {connector_info['config']['index']}")

        print("\n🎉 Async example completed successfully!")
        print("   Check the 'miconnectedindex' index in Elasticsearch.")
        print(f"   Connector ID: {connector_id}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Teardown lives here (not on the happy path inside `try`) so a
        # mid-run exception still cleans up the connector that was created.
        if connector_id:
            if should_cleanup("\nDelete the connector? (y/N): "):
                print("Cleaning up...")
                try:
                    await client.actions.delete(id=connector_id)
                    print("✓ Connector deleted")
                except Exception as e:
                    # Some DELETE operations return empty responses which can
                    # cause JSON parsing errors. Check if the connector was
                    # actually deleted.
                    try:
                        await client.actions.get(id=connector_id)
                        print(f"❌ Failed to delete connector: {e}")
                    except Exception:
                        # If get() fails, the connector was likely deleted
                        print("✓ Connector deleted (confirmed)")
            else:
                print_kept(created)

        # Close the client
        await client.close()
        print("Client closed")


if __name__ == "__main__":
    print("🚀 Running async connector example...\n")

    # Run the async example
    asyncio.run(main())
