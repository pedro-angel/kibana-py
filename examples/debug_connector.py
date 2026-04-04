#!/usr/bin/env python3
"""
Debug the connector creation to see what's happening.
"""

from utils import (
    configure_example_telemetry,
    create_kibana_client,
    print_config_info,
    print_telemetry_info,
    setup_telemetry_cleanup,
    should_cleanup,
    should_enable_telemetry,
)


def main():
    # Print configuration information
    print_config_info()

    # Configure telemetry with detailed information for debugging
    telemetry_enabled = should_enable_telemetry()
    configure_example_telemetry(enabled=telemetry_enabled)
    print_telemetry_info()

    # Set up automatic telemetry cleanup
    setup_telemetry_cleanup()

    # Use automatic configuration from environment or local .env
    client = create_kibana_client()

    try:
        print("Testing connection...")

        # First, let's try to list existing connectors
        print("Listing existing connectors...")
        try:
            connectors_response = client.actions.get_all()
            connectors = connectors_response.body  # Access the body attribute
            print(f"✓ Found {len(connectors)} existing connectors")
            for conn in connectors:
                print(f"  - {conn.get('name', 'Unknown')} ({conn.get('id', 'No ID')})")
        except Exception as e:
            print(f"❌ Failed to list connectors: {e}")
            return

        # List available connector types
        print("\nListing available connector types...")
        try:
            types_response = client.actions.list_types()
            types = types_response.body  # Access the body attribute
            print(f"✓ Found {len(types)} connector types")
            index_type = None
            for conn_type in types:
                print(
                    f"  - {conn_type.get('id', 'Unknown')}: {conn_type.get('name', 'Unknown')}"
                )
                if conn_type.get("id") == ".index":
                    index_type = conn_type
                    print(
                        f"    ✓ Index connector available: {conn_type.get('enabled', 'Unknown status')}"
                    )
        except Exception as e:
            print(f"❌ Failed to list connector types: {e}")
            return

        if not index_type:
            print("❌ Index connector type not available")
            return

        # Now try to create the connector
        print("\nCreating index connector...")
        try:
            response = client.actions.create(
                name="Debug Index Connector",
                connector_type_id=".index",
                config={
                    "index": "miconnectedindex",
                    "refresh": True,
                    "executionTimeField": "@timestamp",
                },
            )

            print(f"✓ Response type: {type(response)}")
            print(f"✓ Response meta: {response.meta}")

            # Access the response body
            connector_data = response.body
            print(f"✓ Connector data: {connector_data}")

            if isinstance(connector_data, dict) and "id" in connector_data:
                connector_id = connector_data["id"]
                print(f"✓ Created connector with ID: {connector_id}")
                print(f"✓ Connector name: {connector_data.get('name', 'Unknown')}")
                print(
                    f"✓ Connector type: {connector_data.get('connector_type_id', 'Unknown')}"
                )

                # Ask user about cleanup
                print("\n🎉 Debug connector created successfully!")
                print("   This example created a connector for debugging purposes.")
                if should_cleanup("Delete the debug connector? (y/N): "):
                    print("Cleaning up debug connector...")
                    try:
                        client.actions.delete(id=connector_id)
                        print("✓ Debug connector deleted")
                    except Exception as e:
                        # Some DELETE operations return empty responses which can cause JSON parsing errors
                        # Check if the connector was actually deleted
                        try:
                            client.actions.get(id=connector_id)
                            print(f"❌ Failed to delete connector: {e}")
                        except Exception:
                            # If get() fails, the connector was likely deleted successfully
                            print("✓ Debug connector deleted (confirmed)")
                else:
                    print(f"✓ Debug connector kept (ID: {connector_id})")
            else:
                print("❌ Could not extract connector ID from response")
                return

        except Exception as e:
            print(f"❌ Failed to create connector: {e}")
            import traceback

            traceback.print_exc()
            return

    except Exception as e:
        print(f"❌ General error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()
