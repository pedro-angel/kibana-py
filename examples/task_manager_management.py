#!/usr/bin/env python3
"""
Task Manager health example.

Shows how to read the Kibana Task Manager health report: overall status,
monitored stats sections, configuration, and workload.

Run this example:
    python examples/task_manager_management.py
"""

from utils import get_kibana_config

from kibana import Kibana


def main() -> None:
    """Check the Kibana task manager health."""
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    try:
        response = client.task_manager.health()
        health = response.body

        print(f"Kibana instance: {health['id']}")
        print(f"Overall task manager status: {health['status']}")
        print(f"Last update: {health['last_update']}")

        print("\nMonitored stats sections:")
        for section, info in health["stats"].items():
            print(f"  {section}: {info['status']} (as of {info['timestamp']})")

        configuration = health["stats"]["configuration"]["value"]
        print("\nConfiguration:")
        print(f"  poll_interval: {configuration.get('poll_interval')} ms")
        print(f"  claim_strategy: {configuration.get('claim_strategy')}")
        print(f"  capacity: {configuration.get('capacity')}")

        workload = health["stats"]["workload"]["value"]
        print("\nWorkload:")
        print(f"  task count: {workload.get('count')}")
        print(f"  distinct task types: {len(workload.get('task_types', []))}")

        drift = health["stats"]["runtime"]["value"].get("drift", {})
        if drift:
            print("\nRuntime drift (ms):")
            print(
                f"  p50={drift.get('p50')} p90={drift.get('p90')} p99={drift.get('p99')}"
            )
    finally:
        client.close()


if __name__ == "__main__":
    main()
