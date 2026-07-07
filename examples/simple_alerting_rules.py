#!/usr/bin/env python3
"""
Simple Alerting Rules Example

This example shows the minimal code needed to:
1. Create an index-threshold alerting rule
2. Retrieve the rule
3. Search for rules
4. Update the rule
5. Clean up the rule

Run this example:
    python examples/simple_alerting_rules.py
"""

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
logger = logging.getLogger("kibana.examples.alerting_rules")


def main():
    # Print configuration information
    print_config_info()

    # Configure telemetry with log forwarding
    telemetry_enabled = should_enable_telemetry()
    traces_configured, logs_configured = configure_example_telemetry(
        enabled=telemetry_enabled,
        logs_enabled=telemetry_enabled,
    )
    print_telemetry_info()

    # Set up automatic telemetry cleanup
    setup_telemetry_cleanup()

    # Log example start
    logger.info(
        "Starting alerting rules example",
        extra={
            "example": "simple_alerting_rules",
            "traces_enabled": traces_configured,
            "logs_enabled": logs_configured,
        },
    )

    # Initialize Kibana client with automatic configuration
    client = create_kibana_client()

    # Namespace the display name and use a STABLE rule id so repeated runs
    # replace this example's own rule instead of accumulating a new one.
    prefix = resource_prefix(__file__)
    rule_name = f"{prefix} High Request Count"
    rule_id = f"{prefix}-rule"

    try:
        # 0. Idempotent start: clear this example's own leftover rule (own
        # scope only, by stable id) from a previous kept run.
        try:
            client.alerting.rule.delete(id=rule_id)
            print(f"Cleared leftover rule {rule_id!r}")
        except NotFoundError:
            pass

        # 1. Create an index-threshold rule
        print("Creating alerting rule...")
        logger.info(
            "Creating alerting rule",
            extra={"rule_name": rule_name, "operation": "create"},
        )

        create_response = client.alerting.rule.create(
            id=rule_id,
            name=rule_name,
            consumer="alerts",
            rule_type_id=".index-threshold",
            schedule={"interval": "1m"},
            params={
                "index": ["*"],
                "timeField": "@timestamp",
                "aggType": "count",
                "thresholdComparator": ">",
                "timeWindowSize": 5,
                "timeWindowUnit": "m",
                "threshold": [100],
            },
            tags=["example", "kibana-py"],
        )

        rule = create_response.body
        rule_id = rule["id"]

        logger.info(
            "Rule created successfully",
            extra={
                "rule_id": rule_id,
                "rule_name": rule["name"],
                "rule_type": rule["rule_type_id"],
                "operation": "create",
            },
        )

        print(f"✓ Created rule: {rule['name']} (ID: {rule_id})")
        print(f"  Type: {rule['rule_type_id']}")
        print(f"  Schedule: every {rule['schedule']['interval']}")
        print(f"  Enabled: {rule['enabled']}")

        # 2. Get the rule by ID
        print("\nRetrieving rule...")
        logger.info(
            "Retrieving rule",
            extra={"rule_id": rule_id, "operation": "get"},
        )
        get_response = client.alerting.rule.get(id=rule_id)
        fetched = get_response.body

        print(f"✓ Retrieved rule: {fetched['name']}")
        print(f"  Tags: {fetched.get('tags', [])}")
        print(f"  Created: {fetched.get('created_at', 'N/A')}")

        # 3. Find rules matching a search
        print("\nSearching for rules...")
        logger.info(
            "Searching for rules",
            extra={"search": "High Request", "operation": "find"},
        )
        find_response = client.alerting.rule.find(
            search="High Request",
            sort_field="name",
        )
        results = find_response.body

        print(f"✓ Found {results['total']} rule(s)")
        for r in results["data"]:
            print(f"    - {r['name']} ({r['rule_type_id']})")

        # 4. Update the rule
        print("\nUpdating rule...")
        logger.info(
            "Updating rule",
            extra={"rule_id": rule_id, "operation": "update"},
        )
        update_response = client.alerting.rule.update(
            id=rule_id,
            name=f"{rule_name} (updated)",
            schedule={"interval": "5m"},
            params={
                "index": ["*"],
                "timeField": "@timestamp",
                "aggType": "count",
                "thresholdComparator": ">",
                "timeWindowSize": 10,
                "timeWindowUnit": "m",
                "threshold": [200],
            },
            tags=["example", "kibana-py", "updated"],
        )
        updated = update_response.body

        logger.info(
            "Rule updated successfully",
            extra={
                "rule_id": rule_id,
                "rule_name": updated["name"],
                "operation": "update",
            },
        )

        print(f"✓ Updated rule: {updated['name']}")
        print(f"  Schedule: every {updated['schedule']['interval']}")
        print(f"  Tags: {updated.get('tags', [])}")

        print("\n🎉 Success! Your alerting rule is ready.")
        print(f"   Rule ID: {rule_id}")
        print(
            "   Access it at: http://localhost:5601/app/management/insightsAndAlerting/triggersActions/rules"
        )

        # Ask user about cleanup
        print(f"\nRule '{updated['name']}' was created for this example.")
        if should_cleanup("Delete the rule? (y/N): "):
            print("Cleaning up...")
            logger.info(
                "Deleting rule",
                extra={"rule_id": rule_id, "operation": "delete"},
            )
            try:
                client.alerting.rule.delete(id=rule_id)
                print("✓ Rule deleted")
                logger.info(
                    "Rule deleted successfully",
                    extra={"rule_id": rule_id, "operation": "delete"},
                )
            except Exception as e:
                try:
                    client.alerting.rule.get(id=rule_id)
                    print(f"❌ Failed to delete rule: {e}")
                    logger.error(
                        "Failed to delete rule",
                        extra={"rule_id": rule_id, "error": str(e)},
                    )
                except Exception:
                    print("✓ Rule deleted (confirmed)")
                    logger.info(
                        "Rule deletion confirmed",
                        extra={"rule_id": rule_id, "operation": "delete"},
                    )
        else:
            logger.info("Rule kept by user choice", extra={"rule_id": rule_id})
            print_kept([("alerting rule", rule_id)])

    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(
            "Alerting rules example failed",
            extra={"error": str(e), "example": "simple_alerting_rules"},
        )
    finally:
        logger.info("Alerting rules example completed")
        client.close()


if __name__ == "__main__":
    main()
