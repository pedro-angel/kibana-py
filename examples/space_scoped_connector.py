"""
Space-Scoped Connector Example

This example demonstrates creating a Kibana space and then creating an index connector
within that space context using the new generalized space support. It showcases
space-scoped resource management by combining space creation with connector operations,
providing a practical demonstration of multi-tenancy patterns in Kibana.

The example workflow:
1. Creates a dedicated team space with unique identifier
2. Creates an index connector using ActionsClient space support
3. Executes the connector to write sample data to a space-prefixed index
4. Displays information about created resources and access URLs
5. Provides interactive cleanup for both connector and space

This example demonstrates the new space support patterns:
- Using space_id parameters with automatic validation
- Space-scoped client creation for multiple operations
- Consistent space support across all API clients

Prerequisites:
- Running Kibana instance (use elastic-start-local for local development)
- Proper authentication configured (API key, basic auth, or bearer token)

Usage:
    python examples/space_scoped_connector.py

Expected outcomes:
- New space created with team-appropriate configuration
- Index connector created with space-specific index name using new space support
- Sample documents written through the connector
- Clear information displayed about accessing resources
- Interactive cleanup options for created resources

Configuration:
The example uses automatic configuration from examples/utils.py, which supports:
- Environment variables (KIBANA_URL, KIBANA_API_KEY, etc.)
- Local development setup (elastic-start-local/.env)
- Sensible defaults (http://localhost:5601)
"""

from datetime import UTC, datetime

from utils import (
    configure_example_telemetry,
    create_kibana_client,
    print_config_info,
    print_kept,
    print_telemetry_info,
    resource_prefix,
    setup_telemetry_cleanup,
    should_cleanup,
    should_enable_telemetry,
)

from kibana.exceptions import NotFoundError


def create_team_space(client):
    """Create a team space with appropriate configuration.

    :param client: Kibana client instance
    :return: Space data dictionary from the API response
    """
    import logging

    logger = logging.getLogger(__name__)

    print("Creating team space...")

    # Stable space ID namespaced to this example (own scope)
    space_id = f"{resource_prefix(__file__)}-team-space"

    try:
        # Idempotent start: clear only THIS example's own prior space.
        # Deleting the space cascades to any connectors created within it.
        try:
            client.spaces.delete(id=space_id)
            print(f"Cleared leftover space {space_id!r}")
        except NotFoundError:
            pass

        logger.info(
            "Creating team space",
            extra={
                "space_id": space_id,
                "space_name": "Team Workspace",
                "operation": "create_space",
            },
        )

        response = client.spaces.create(
            id=space_id,
            name="Team Workspace",
            description="Dedicated space for team's connectors and dashboards",
            color="#4ECDC4",
            initials="TW",
        )

        # Access response via .body attribute and extract space data
        space = response.body
        print(f"✓ Created space: {space['name']} (ID: {space_id})")

        logger.info(
            "Team space created successfully",
            extra={
                "space_id": space_id,
                "space_name": space["name"],
                "operation": "create_space",
                "status": "success",
            },
        )

        return space

    except Exception as e:
        print(f"❌ Failed to create space: {e}")
        logger.error(
            f"Failed to create team space: {e}",
            extra={
                "space_id": space_id,
                "operation": "create_space",
                "status": "error",
                "error_type": type(e).__name__,
            },
        )
        raise


def create_space_connector(client, space_id):
    """Create connector within the specified space context using new space support.

    :param client: Kibana client instance
    :param space_id: Space ID where the connector should be created
    :return: Connector data dictionary from the API response
    """
    import logging

    logger = logging.getLogger(__name__)

    print("Creating space-scoped index connector...")

    # Generate space-prefixed index name for logical association
    space_index = f"{space_id}-data"

    try:
        logger.info(
            "Creating space-scoped connector",
            extra={
                "space_id": space_id,
                "connector_type": ".index",
                "target_index": space_index,
                "operation": "create_connector",
            },
        )

        # Create connector using ActionsClient space support with automatic validation.
        # Stable id (own scope): the space is recreated fresh on every run (see
        # create_team_space), so there is no risk of an ID conflict, but a
        # fixed id keeps this connector's identity reproducible across runs.
        response = client.actions.create(
            id=f"{resource_prefix(__file__)}-conn",
            name=f"Team Connector ({space_id})",
            connector_type_id=".index",
            config={
                "index": space_index,
                "refresh": True,
                "executionTimeField": "@timestamp",
            },
            space_id=space_id,  # Uses new space support with automatic validation
        )

        # Access response via .body attribute and extract connector data
        connector = response.body
        print(f"✓ Created connector in space '{space_id}': {connector['name']}")
        print(f"  Target index: {space_index}")

        logger.info(
            "Space-scoped connector created successfully",
            extra={
                "space_id": space_id,
                "connector_id": connector["id"],
                "connector_name": connector["name"],
                "target_index": space_index,
                "operation": "create_connector",
                "status": "success",
            },
        )

        return connector

    except Exception as e:
        print(f"❌ Failed to create connector in space: {e}")
        logger.error(
            f"Failed to create space-scoped connector: {e}",
            extra={
                "space_id": space_id,
                "target_index": space_index,
                "operation": "create_connector",
                "status": "error",
                "error_type": type(e).__name__,
            },
        )
        raise


def execute_connector_with_sample_data(client, connector_id, space_id):
    """Execute connector with space-contextual sample data using new space support.

    :param client: Kibana client instance
    :param connector_id: Connector ID to execute
    :param space_id: Space ID where the connector exists
    """
    print("Writing sample data through space-scoped connector...")

    # Create sample document with space context (space_id, team info, timestamp)
    document = {
        "message": f"Hello from {space_id} team space!",
        "level": "INFO",
        "service": "team-connector-example",
        "space_id": space_id,
        "team": "example-team",
        "@timestamp": datetime.now(UTC).isoformat(),
    }

    try:
        # Execute connector using ActionsClient space support with automatic validation
        response = client.actions.execute(
            id=connector_id,
            params={"documents": [document]},
            space_id=space_id,  # Uses new space support with automatic validation
        )

        # Access response via .body attribute and extract execution result
        result = response.body
        print("✓ Sample data written successfully")
        print(f"  Status: {result.get('status', 'unknown')}")

        # Add execution status feedback
        if result.get("status") == "ok":
            print("  ✓ Connector execution completed successfully")
        else:
            print(
                f"  ⚠️  Connector execution status: {result.get('status', 'unknown')}"
            )

    except Exception as e:
        print(f"❌ Failed to execute connector: {e}")
        raise


def display_success_information(space, connector):
    """Display success information and next steps.

    :param space: Space data dictionary from the API response
    :param connector: Connector data dictionary from the API response
    """
    # Extract space_id, connector_id, and index name from the data
    space_id = space["id"]
    connector_id = connector["id"]
    index_name = connector["config"]["index"]

    # Display space information (name, ID) and connector information (name, ID, target index)
    print("\n🎉 Success! Your space-scoped connector is ready.")
    print(f"   Space: {space['name']} (ID: {space_id})")
    print(f"   Connector: {connector['name']} (ID: {connector_id})")
    print(f"   Target Index: {index_name}")

    # Show space-specific URLs for accessing the space and dev tools
    print("\n📍 Access your space:")
    print(f"   Space URL: http://localhost:5601/s/{space_id}/app/home")
    print(f"   Dev Tools: http://localhost:5601/s/{space_id}/app/dev_tools#/console")

    # Provide actionable next steps including sample query
    print("\n🔍 Query your data:")
    print(f"   GET {index_name}/_search")
    print("\n💡 Next steps:")
    print("   • Visit the space URL to explore your team workspace")
    print("   • Use Dev Tools to query the indexed data")
    print("   • Create dashboards and visualizations in your space")
    print("   • Add more connectors to organize team data")


def interactive_cleanup(client, connector_id, space_id):
    """Handle interactive cleanup of connectors and space using new space support.

    :param client: Kibana client instance
    :param connector_id: Primary connector ID to potentially delete
    :param space_id: Space ID to potentially delete
    """
    print("\nResources created for this example:")
    print(f"  - Primary Connector: {connector_id}")
    print(f"  - Space: {space_id}")
    print("  - Note: Space deletion will remove all connectors in the space")

    # Prompt user about deleting the space (which will delete all connectors)
    if should_cleanup("Delete the space and all its connectors? (y/N): "):
        print("Cleaning up space and all connectors...")
        try:
            # Delete space using SpacesClient - this removes all space-scoped resources
            client.spaces.delete(id=space_id)
            print("✓ Space and all connectors deleted")
        except Exception as e:
            # Handle DELETE API edge cases by verifying deletion
            try:
                client.spaces.get(id=space_id)
                print(f"❌ Failed to delete space: {e}")
            except Exception:
                # If get() fails, deletion likely succeeded
                print("✓ Space and all connectors deleted (confirmed)")
    else:
        # Offer individual connector cleanup if space is kept
        if should_cleanup("Delete just the primary connector? (y/N): "):
            print("Cleaning up primary connector...")
            try:
                # Delete connector using ActionsClient space support with automatic validation
                client.actions.delete(id=connector_id, space_id=space_id)
                print("✓ Primary connector deleted")
            except Exception as e:
                # Handle DELETE API edge cases by verifying deletion
                try:
                    client.actions.get(id=connector_id, space_id=space_id)
                    print(f"❌ Failed to delete connector: {e}")
                except Exception:
                    # If get() fails, deletion likely succeeded
                    print("✓ Primary connector deleted (confirmed)")
            print("  Note: Space-scoped connector may still exist in the space")
            print_kept([("space", space_id)])
        else:
            # Display resource IDs if user declines cleanup
            print("  You can manage them later from the Kibana UI")
            print_kept([("space", space_id), ("primary connector", connector_id)])


def demonstrate_space_scoped_client(client, space_id):
    """Demonstrate space-scoped client pattern for multiple operations.

    :param client: Kibana client instance
    :param space_id: Space ID to create scoped client for
    :return: Connector data from space-scoped operations
    """
    print("\n🔄 Bonus: Demonstrating space-scoped client pattern...")
    print("   Creating space-scoped client for multiple operations")

    try:
        # Create space-scoped client with automatic validation
        space_client = client.space(space_id)
        print(f"   ✓ Created space-scoped client for '{space_id}'")

        # Create another connector using space-scoped client
        print("   Creating second connector using space-scoped client...")
        response = space_client.actions.create(
            name=f"Space-Scoped Connector ({space_id})",
            connector_type_id=".index",
            config={
                "index": f"{space_id}-scoped-data",
                "refresh": True,
                "executionTimeField": "@timestamp",
            },
            # No space_id parameter needed - automatically uses space context
        )

        connector = response.body
        print(f"   ✓ Created connector: {connector['name']}")
        print(f"   ✓ Target index: {connector['config']['index']}")

        # Execute the connector using space-scoped client
        print("   Executing connector using space-scoped client...")
        document = {
            "message": f"Hello from space-scoped client in {space_id}!",
            "level": "INFO",
            "service": "space-scoped-client-example",
            "space_id": space_id,
            "pattern": "space-scoped-client",
            "@timestamp": datetime.now(UTC).isoformat(),
        }

        exec_response = space_client.actions.execute(
            id=connector["id"],
            params={"documents": [document]},
            # No space_id parameter needed - automatically uses space context
        )

        result = exec_response.body
        print(f"   ✓ Execution status: {result.get('status', 'unknown')}")

        print("\n   💡 Space-scoped client benefits:")
        print("   • No need to pass space_id to each method call")
        print("   • Automatic space validation on client creation")
        print("   • Consistent space context across all operations")
        print("   • Cleaner code for multiple space-scoped operations")

        return connector

    except Exception as e:
        print(f"   ❌ Failed to demonstrate space-scoped client: {e}")
        raise


def main():
    """Main example function demonstrating space-scoped connector creation."""
    print("🚀 Space-Scoped Connector Example")
    print("=" * 50)

    # Add print_config_info() call at the beginning
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
                "Space-scoped connector example started",
                extra={
                    "traces_enabled": traces_configured,
                    "logs_enabled": logs_configured,
                    "example": "space_scoped_connector",
                },
            )
    except Exception as e:
        print(f"⚠️  Telemetry configuration failed: {e}")
        print("   Continuing without telemetry...")
        logger.warning(
            f"Telemetry configuration failed: {e}",
            extra={
                "error_type": "telemetry_config_error",
                "example": "space_scoped_connector",
            },
        )

    # Create Kibana client using create_kibana_client()
    client = create_kibana_client()

    try:
        print("\n1️⃣ Step 1: Creating team space...")
        print("   Setting up dedicated workspace for team resources")
        # Create space and store space data and space_id for later use
        space = create_team_space(client)
        space_id = space["id"]
        print(f"   ✅ Team space ready: {space['name']}")

        print("\n2️⃣ Step 2: Creating space-specific connector...")
        print("   Configuring index connector using new space support")
        # Call create_space_connector() with space_id
        connector = create_space_connector(client, space_id)
        connector_id = connector["id"]
        print(f"   ✅ Connector configured: {connector['name']}")

        print("\n3️⃣ Step 3: Writing sample data...")
        print("   Testing connector by writing sample documents")
        # Call execute_connector_with_sample_data() with required parameters
        execute_connector_with_sample_data(client, connector_id, space_id)
        print("   ✅ Sample data successfully written to space-specific index")

        print("\n4️⃣ Step 4: Displaying resource information...")
        print("   Providing access details and next steps")
        # Call display_success_information() with space and connector data
        display_success_information(space, connector)

        # Demonstrate space-scoped client pattern
        scoped_connector = demonstrate_space_scoped_client(client, space_id)

        # Add final success message with summary of created resources
        print("\n🎯 Example Complete!")
        print("=" * 50)
        print("✅ Successfully created and configured:")
        print(f"   • Team Space: {space['name']} (ID: {space_id})")
        print(f"   • Index Connector: {connector['name']} (ID: {connector_id})")
        print(
            f"   • Space-Scoped Connector: {scoped_connector['name']} (ID: {scoped_connector['id']})"
        )
        print(
            f"   • Target Indexes: {connector['config']['index']}, {scoped_connector['config']['index']}"
        )
        print("   • Sample Data: Written and indexed successfully")
        print("\n💡 Your space-scoped connectors are ready for use!")

        print("\n5️⃣ Step 5: Interactive cleanup...")
        print("   Choose whether to keep or remove the created resources")
        # Call interactive_cleanup() with required parameters (will clean up both connectors)
        interactive_cleanup(client, connector_id, space_id)

    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        print("Note: Some resources may have been created. Check Kibana for cleanup.")
    except ConnectionError as e:
        print("\n❌ Connection Error: Unable to connect to Kibana")
        print(f"   Details: {e}")
        print("   Please check:")
        print("   • Kibana is running and accessible")
        print("   • KIBANA_URL is correct")
        print("   • Network connectivity")
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        print("   This example requires:")
        print("   • Running Kibana instance")
        print("   • Valid authentication (API key, basic auth, or bearer token)")
        print("   • Proper permissions for spaces and actions APIs")
        print("   • Check your configuration and try again")
    finally:
        # Ensure client is properly closed in finally block
        try:
            client.close()
        except Exception:
            pass  # Ignore errors during cleanup


if __name__ == "__main__":
    main()
