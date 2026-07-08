#!/usr/bin/env python3
"""
Connector Management Example

Demonstrates advanced connector operations that apply to any connector type,
using an index connector as the example. Builds on simple_index_connector.py:
1. List available connector types
2. List existing connectors
3. Batch-write multiple documents
4. Update connector configuration at runtime
5. Structured error handling with specific exception types

For the basics (create, write one document, clean up), see simple_index_connector.py.

Prerequisites:
- Running Kibana instance (default: http://localhost:5601)
- Proper authentication (API key, basic auth, or bearer token)
- Elasticsearch cluster with write permissions

Run this example:
    python examples/connector_management.py
"""

import logging
from datetime import datetime
from typing import Any

from kibana.exceptions import (
    BadRequestError,
    ConflictError,
    KibanaException,
    NotFoundError,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IndexConnectorManager:
    """Class-based connector management with advanced operations."""

    def __init__(self):
        """Initialize the manager with automatic Kibana client configuration."""
        from utils import (
            configure_example_telemetry,
            create_kibana_client,
            get_kibana_config,
            resource_prefix,
            setup_telemetry_cleanup,
            should_enable_telemetry,
        )

        # Namespaced per-example index so re-runs (and other examples that
        # also target ".index" connectors) don't collide on a shared name.
        self.index_name = f"{resource_prefix(__file__)}-index"
        self.connector_name = f"Index Connector - {self.index_name}"
        self.connector_id: str | None = None

        # Configure telemetry with production-ready error handling
        try:
            telemetry_enabled = should_enable_telemetry()
            traces_configured, logs_configured = configure_example_telemetry(
                enabled=telemetry_enabled,
                logs_enabled=telemetry_enabled,
            )

            setup_telemetry_cleanup()

            if traces_configured or logs_configured:
                logger.info(
                    "OpenTelemetry configured successfully",
                    extra={
                        "traces_enabled": traces_configured,
                        "logs_enabled": logs_configured,
                        "component": "IndexConnectorManager",
                        "initialization": True,
                    },
                )
        except Exception as e:
            logger.warning(
                f"Telemetry configuration failed: {e}",
                extra={
                    "error_type": "telemetry_config_error",
                    "component": "IndexConnectorManager",
                },
            )

        self.kibana_url, _, _ = get_kibana_config()
        self.client = create_kibana_client()
        logger.info(
            f"Initialized Kibana client for {self.kibana_url}",
            extra={
                "kibana_url": self.kibana_url,
                "component": "IndexConnectorManager",
                "operation": "client_initialization",
            },
        )

    def create_or_find_connector(self) -> dict[str, Any]:
        """
        Create an index connector, or find an existing one by name.

        :return: Connector details
        :raises BadRequestError: If configuration is invalid
        """
        try:
            config = {
                "index": self.index_name,
                "refresh": True,
                "executionTimeField": "@timestamp",
            }

            logger.info(
                f"Creating index connector: {self.connector_name}",
                extra={
                    "connector_name": self.connector_name,
                    "connector_type": ".index",
                    "target_index": self.index_name,
                    "operation": "create_connector",
                },
            )
            response = self.client.actions.create(
                name=self.connector_name,
                connector_type_id=".index",
                config=config,
            )

            connector = response.body
            self.connector_id = connector["id"]
            logger.info(
                f"Successfully created connector with ID: {self.connector_id}",
                extra={
                    "connector_id": self.connector_id,
                    "connector_name": self.connector_name,
                    "target_index": self.index_name,
                    "operation": "create_connector",
                    "status": "success",
                },
            )
            return connector

        except ConflictError:
            logger.warning(
                f"Connector '{self.connector_name}' already exists, reusing it",
                extra={
                    "connector_name": self.connector_name,
                    "operation": "create_connector",
                    "status": "conflict",
                },
            )
            return self._find_existing_connector()
        except BadRequestError as e:
            logger.error(
                f"Invalid connector configuration: {e}",
                extra={
                    "connector_name": self.connector_name,
                    "operation": "create_connector",
                    "status": "error",
                    "error_type": "BadRequestError",
                },
            )
            raise
        except KibanaException as e:
            logger.error(
                f"Failed to create connector: {e}",
                extra={
                    "connector_name": self.connector_name,
                    "operation": "create_connector",
                    "status": "error",
                    "error_type": type(e).__name__,
                },
            )
            raise

    def _find_existing_connector(self) -> dict[str, Any]:
        """Find existing connector by name."""
        response = self.client.actions.get_all()
        connectors = response.body
        for connector in connectors:
            if connector["name"] == self.connector_name:
                self.connector_id = connector["id"]
                logger.info(f"Found existing connector with ID: {self.connector_id}")
                return connector

        raise NotFoundError(f"Connector '{self.connector_name}' not found")

    def execute_connector(self, document: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the connector to write a document to the index.

        :param document: Document to write to the index
        :return: Execution result
        :raises ValueError: If connector not created
        :raises BadRequestError: If document is invalid
        """
        if not self.connector_id:
            raise ValueError(
                "Connector not created. Call create_or_find_connector() first."
            )

        if "@timestamp" not in document:
            document["@timestamp"] = datetime.utcnow().isoformat()

        params = {"documents": [document]}

        try:
            logger.info(
                f"Executing connector {self.connector_id} with document",
                extra={
                    "connector_id": self.connector_id,
                    "document_count": 1,
                    "target_index": self.index_name,
                    "operation": "execute_connector",
                    "document_keys": list(document.keys()),
                },
            )
            response = self.client.actions.execute(id=self.connector_id, params=params)

            result = response.body
            logger.info(
                "Document successfully written to index",
                extra={
                    "connector_id": self.connector_id,
                    "target_index": self.index_name,
                    "operation": "execute_connector",
                    "status": "success",
                    "execution_result": result.get("status", "unknown"),
                },
            )
            return result

        except BadRequestError as e:
            logger.error(
                f"Invalid execution parameters: {e}",
                extra={
                    "connector_id": self.connector_id,
                    "operation": "execute_connector",
                    "status": "error",
                    "error_type": "BadRequestError",
                },
            )
            raise
        except KibanaException as e:
            logger.error(
                f"Failed to execute connector: {e}",
                extra={
                    "connector_id": self.connector_id,
                    "operation": "execute_connector",
                    "status": "error",
                    "error_type": type(e).__name__,
                },
            )
            raise

    def write_sample_data(self) -> None:
        """Write a batch of sample documents to demonstrate bulk writes."""
        sample_documents = [
            {
                "message": "Application started successfully",
                "level": "INFO",
                "service": "web-server",
                "host": "server-01",
                "user_id": "user123",
                "request_id": "req-001",
            },
            {
                "message": "Database connection established",
                "level": "INFO",
                "service": "database",
                "host": "db-server-01",
                "connection_pool_size": 10,
                "response_time_ms": 45,
            },
            {
                "message": "High memory usage detected",
                "level": "WARNING",
                "service": "monitoring",
                "host": "server-02",
                "memory_usage_percent": 85.7,
                "threshold_percent": 80,
            },
            {
                "message": "User authentication failed",
                "level": "ERROR",
                "service": "auth-service",
                "host": "auth-server-01",
                "user_id": "user456",
                "ip_address": "192.168.1.100",
                "reason": "invalid_credentials",
            },
        ]

        logger.info(
            f"Writing {len(sample_documents)} sample documents",
            extra={
                "document_count": len(sample_documents),
                "target_index": self.index_name,
                "operation": "write_sample_data",
            },
        )

        for i, doc in enumerate(sample_documents, 1):
            try:
                self.execute_connector(doc)
                logger.info(
                    f"Document {i}/{len(sample_documents)} written successfully",
                    extra={
                        "document_number": i,
                        "total_documents": len(sample_documents),
                        "document_level": doc.get("level"),
                        "document_service": doc.get("service"),
                        "operation": "write_sample_data",
                        "status": "success",
                    },
                )
            except Exception as e:
                logger.error(
                    f"Failed to write document {i}: {e}",
                    extra={
                        "document_number": i,
                        "total_documents": len(sample_documents),
                        "operation": "write_sample_data",
                        "status": "error",
                        "error_type": type(e).__name__,
                    },
                )

    def update_connector(self, new_config: dict[str, Any]) -> dict[str, Any]:
        """
        Update the connector configuration.

        :param new_config: New configuration parameters
        :return: Updated connector details
        :raises ValueError: If connector not created
        """
        if not self.connector_id:
            raise ValueError(
                "Connector not created. Call create_or_find_connector() first."
            )

        try:
            logger.info(f"Updating connector {self.connector_id}")
            response = self.client.actions.update(
                id=self.connector_id,
                name=self.connector_name,  # API requires name parameter
                config=new_config,
            )
            result = response.body
            logger.info("Connector updated successfully")
            return result
        except KibanaException as e:
            logger.error(f"Failed to update connector: {e}")
            raise

    def delete_connector(self) -> None:
        """
        Delete the connector.

        :raises ValueError: If connector not created
        """
        if not self.connector_id:
            raise ValueError(
                "Connector not created. Call create_or_find_connector() first."
            )

        try:
            logger.info(f"Deleting connector {self.connector_id}")
            self.client.actions.delete(id=self.connector_id)
            logger.info("Connector deleted successfully")
            self.connector_id = None
        except NotFoundError:
            logger.warning(
                f"Connector {self.connector_id} not found (may already be deleted)"
            )
            self.connector_id = None
        except KibanaException as e:
            logger.error(f"Failed to delete connector: {e}")
            raise

    def list_all_connectors(self) -> None:
        """List all available connectors."""
        try:
            response = self.client.actions.get_all()
            connectors = response.body
            logger.info(f"Found {len(connectors)} connectors:")

            for connector in connectors:
                print(f"  - {connector['name']} ({connector['id']})")
                print(f"    Type: {connector['connector_type_id']}")
                print(f"    Enabled: {connector.get('is_preconfigured', False)}")
                print()

        except KibanaException as e:
            logger.error(f"Failed to list connectors: {e}")
            raise

    def list_connector_types(self) -> None:
        """List all available connector types."""
        try:
            response = self.client.actions.list_types()
            types = response.body
            logger.info(f"Found {len(types)} connector types:")

            for connector_type in types:
                print(f"  - {connector_type['id']}: {connector_type['name']}")
                print(f"    Enabled: {connector_type.get('enabled', False)}")
                if connector_type.get("enabled_in_config"):
                    print(f"    Config enabled: {connector_type['enabled_in_config']}")
                if connector_type.get("enabled_in_license"):
                    print(
                        f"    License enabled: {connector_type['enabled_in_license']}"
                    )
                print()

        except KibanaException as e:
            logger.error(f"Failed to list connector types: {e}")
            raise

    def close(self) -> None:
        """Close the Kibana client."""
        self.client.close()
        logger.info("Kibana client closed")


def main():
    """Run advanced connector operations: list types, bulk write, update config."""
    from utils import print_config_info, print_telemetry_info

    print_config_info()
    print_telemetry_info()

    manager = None

    try:
        manager = IndexConnectorManager()

        print("=== Advanced Index Connector Example ===\n")

        # --- Operations not covered in simple_index_connector.py ---

        # 1. Discover available connector types
        print("1. Available connector types:")
        manager.list_connector_types()

        # 2. List existing connectors
        print("2. Existing connectors:")
        manager.list_all_connectors()

        # 3. Create (or reuse) a connector for the remaining operations
        print("3. Setting up connector...")
        connector = manager.create_or_find_connector()
        print(f"   Using connector: {connector['name']} (ID: {connector['id']})")
        print()

        # 4. Batch-write sample data
        print("4. Batch-writing sample documents...")
        manager.write_sample_data()
        print()

        # 5. Update connector configuration at runtime
        print("5. Updating connector configuration...")
        new_config = {
            "index": manager.index_name,
            "refresh": False,  # Change refresh setting
            "executionTimeField": "timestamp",  # Change timestamp field
        }
        manager.update_connector(new_config)
        print("   Connector updated successfully")
        print()

        # 6. Write with the updated configuration
        print("6. Writing document with updated configuration...")
        test_doc = {
            "message": "Test document with updated config",
            "level": "INFO",
            "service": "example-service",
            "timestamp": datetime.utcnow().isoformat(),
        }
        manager.execute_connector(test_doc)
        print()

        print("=== Example completed successfully! ===")
        print(
            f"Check your Elasticsearch index '{manager.index_name}' for the written documents."
        )

        # Interactive cleanup
        if manager and manager.connector_id:
            from utils import print_kept, should_cleanup

            print(f"\nConnector '{connector['name']}' was created for this example.")
            if should_cleanup("Delete the connector? (y/N): "):
                print("Cleaning up...")
                try:
                    manager.delete_connector()
                    print("✓ Connector deleted")
                except Exception as e:
                    try:
                        manager.client.actions.get(id=manager.connector_id)
                        print(f"❌ Failed to delete connector: {e}")
                    except Exception:
                        print("✓ Connector deleted (confirmed)")
            else:
                print_kept([("connector", manager.connector_id)])

    except KeyboardInterrupt:
        print("\nExample interrupted by user")
    except Exception as e:
        logger.error(f"Example failed: {e}")
        print(f"Error: {e}")
    finally:
        if manager:
            try:
                manager.close()
            except Exception as e:
                logger.error(f"Cleanup failed: {e}")


if __name__ == "__main__":
    main()
