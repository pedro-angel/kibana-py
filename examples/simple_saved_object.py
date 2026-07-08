#!/usr/bin/env python3
"""
Simple Saved Object Example

This example shows the minimal code needed to:
1. Create a data view (index pattern) for APM traces
2. Create a visualization that uses the data view
3. Retrieve the saved objects
4. Clean up the saved objects

Run this example:
    python examples/simple_saved_object.py
"""

import json
import logging

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

# Set up logger for this example
logger = logging.getLogger("kibana.examples.simple_saved_object")


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
        "Starting simple saved object example",
        extra={
            "example": "simple_saved_object",
            "traces_enabled": traces_configured,
            "logs_enabled": logs_configured,
        },
    )

    # Initialize Kibana client with automatic configuration
    client = create_kibana_client()

    prefix = resource_prefix(__file__)  # "kbnpy-simple-saved-object"
    data_view_id = f"{prefix}-apm-traces"
    viz_id = f"{prefix}-viz"
    created: list[tuple[str, str]] = []

    try:
        # Idempotent start: clear only THIS example's own prior resources.
        # Dependency order matters: the visualization references the data
        # view, so it must be deleted first.
        try:
            client.saved_objects.delete(type="visualization", id=viz_id)
        except NotFoundError:
            pass
        try:
            client.saved_objects.delete(type="index-pattern", id=data_view_id)
        except NotFoundError:
            pass

        # 1. Create a data view (index pattern) for APM traces
        print("Creating data view...")
        logger.info(
            "Creating data view saved object",
            extra={
                "object_type": "index-pattern",
                "object_id": data_view_id,
                "operation": "create",
            },
        )

        dv_response = client.saved_objects.create(
            type="index-pattern",
            attributes={
                "title": "traces-apm*",
                "timeFieldName": "@timestamp",
            },
            id=data_view_id,
        )

        dv_object = dv_response.body
        created.append(("data view (index-pattern)", data_view_id))
        print(f"✓ Created data view: {dv_object['id']}")
        print(f"  Pattern: {dv_object['attributes']['title']}")
        logger.info(
            "Data view created successfully",
            extra={
                "object_id": dv_object["id"],
                "object_type": dv_object["type"],
                "pattern": dv_object["attributes"]["title"],
                "operation": "create",
            },
        )

        # 2. Create a visualization saved object
        print("Creating visualization...")
        logger.info(
            "Creating visualization saved object",
            extra={
                "object_type": "visualization",
                "object_id": viz_id,
                "operation": "create",
            },
        )

        vis_state = json.dumps(
            {
                "title": "kibana-py Total Transactions",
                "type": "metric",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "count",
                        "params": {},
                        "schema": "metric",
                    }
                ],
                "params": {
                    "addTooltip": True,
                    "addLegend": False,
                    "type": "metric",
                    "metric": {
                        "percentageMode": False,
                        "useRanges": False,
                        "colorSchema": "Green to Red",
                        "metricColorMode": "None",
                        "colorsRange": [{"from": 0, "to": 10000}],
                        "labels": {"show": True},
                        "invertColors": False,
                        "style": {
                            "bgFill": "#000",
                            "bgColor": False,
                            "labelColor": False,
                            "subText": "",
                            "fontSize": 60,
                        },
                    },
                },
            }
        )

        search_source = json.dumps(
            {
                "query": {
                    "query": "service.name: kibana-py",
                    "language": "kuery",
                },
                "filter": [],
                "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
            }
        )

        create_response = client.saved_objects.create(
            type="visualization",
            attributes={
                "title": "kibana-py Total Transactions",
                "visState": vis_state,
                "uiStateJSON": "{}",
                "description": "Total transaction count for the kibana-py service",
                "version": 1,
                "kibanaSavedObjectMeta": {"searchSourceJSON": search_source},
            },
            id=viz_id,
            references=[
                {
                    "id": data_view_id,
                    "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                    "type": "index-pattern",
                }
            ],
        )

        saved_object = create_response.body  # Access the body attribute
        obj_id = saved_object["id"]
        created.append(("visualization", obj_id))

        logger.info(
            "Visualization created successfully",
            extra={
                "object_id": obj_id,
                "object_type": saved_object["type"],
                "title": saved_object["attributes"]["title"],
                "operation": "create",
            },
        )

        print(f"✓ Created visualization: {obj_id}")
        print(f"  Title: {saved_object['attributes']['title']}")
        print(f"  Type: {saved_object['type']}")

        # 3. Retrieve the saved object
        logger.info(
            "Retrieving saved object", extra={"object_id": obj_id, "operation": "get"}
        )
        get_response = client.saved_objects.get(
            type="visualization",
            id=obj_id,
        )
        retrieved = get_response.body  # Access the body attribute
        print(f"✓ Retrieved visualization: {retrieved['attributes']['title']}")

        print("\n🎉 Success! Your visualization is ready.")
        print(f"   Object ID: {obj_id}")
        print("   Access it in Kibana's Visualize app")

    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(
            "Saved object example failed",
            extra={"error": str(e), "example": "simple_saved_object"},
        )
    finally:
        # 4. Clean up (or keep). Delete ordering matters: the visualization
        # references the data view, so it must be deleted first.
        if should_cleanup("Delete the visualization and data view? (y/N): "):
            print("Cleaning up...")
            logger.info(
                "Deleting saved objects",
                extra={
                    "object_id": viz_id,
                    "data_view_id": data_view_id,
                    "operation": "delete",
                },
            )
            try:
                client.saved_objects.delete(type="visualization", id=viz_id)
                print("✓ Visualization deleted")
                logger.info(
                    "Visualization deleted successfully",
                    extra={"object_id": viz_id, "operation": "delete"},
                )
            except Exception as e:
                # Check if the object was actually deleted
                try:
                    client.saved_objects.get(type="visualization", id=viz_id)
                    print(f"❌ Failed to delete visualization: {e}")
                    logger.error(
                        "Failed to delete visualization",
                        extra={"object_id": viz_id, "error": str(e)},
                    )
                except Exception:
                    print("✓ Visualization deleted (confirmed)")
                    logger.info(
                        "Visualization deletion confirmed",
                        extra={"object_id": viz_id, "operation": "delete"},
                    )
            try:
                client.saved_objects.delete(type="index-pattern", id=data_view_id)
                print("✓ Data view deleted")
                logger.info(
                    "Data view deleted successfully",
                    extra={"object_id": data_view_id, "operation": "delete"},
                )
            except Exception as e:
                try:
                    client.saved_objects.get(type="index-pattern", id=data_view_id)
                    print(f"❌ Failed to delete data view: {e}")
                    logger.error(
                        "Failed to delete data view",
                        extra={"object_id": data_view_id, "error": str(e)},
                    )
                except Exception:
                    print("✓ Data view deleted (confirmed)")
                    logger.info(
                        "Data view deletion confirmed",
                        extra={"object_id": data_view_id, "operation": "delete"},
                    )
        else:
            print_kept(created)
            logger.info(
                "Saved objects kept by user choice",
                extra={"object_id": viz_id, "data_view_id": data_view_id},
            )
        logger.info("Simple saved object example completed")
        client.close()


if __name__ == "__main__":
    main()
