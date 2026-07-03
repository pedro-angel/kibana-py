#!/usr/bin/env python3
"""
Maintenance Windows Management Example

This example shows the minimal code needed to:
1. Create a maintenance window (a scheduled period during which rule
   notifications are suppressed)
2. Get it by ID and search for it with find
3. Archive and unarchive it
4. Update it (rename + disable)
5. Clean up (delete the maintenance window)

Maintenance windows require a Platinum or higher license (or a trial).
The Maintenance Windows API is generally available in Kibana 9.4.

Run this example:
    python examples/maintenance_windows_management.py
"""

from datetime import UTC, datetime, timedelta

from utils import get_kibana_config

from kibana import Kibana


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    # Start next week so the maintenance window is "upcoming". (Kibana only
    # materializes recurring events within a limited look-ahead horizon, so a
    # far-future start would be reported as "finished".)
    start = (datetime.now(UTC) + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    mw_id = None
    try:
        # 1. Create a weekly two-hour maintenance window scoped by a KQL query
        created = client.maintenance_windows.create(
            title="kbnpy-example-weekly-maintenance",
            schedule={
                "custom": {
                    "start": start,
                    "duration": "2h",
                    "timezone": "UTC",
                    "recurring": {"every": "1w"},
                }
            },
            scope={"alerting": {"query": {"kql": 'tags: "maintenance"'}}},
        )
        mw_id = created.body["id"]
        print(f"Created maintenance window {mw_id} (status={created.body['status']})")

        # 2. Get it by ID and search for it
        fetched = client.maintenance_windows.get(id=mw_id)
        print(f"Fetched by ID: title={fetched.body['title']}")

        found = client.maintenance_windows.find(
            title="kbnpy-example-weekly-maintenance", status=["upcoming", "running"]
        )
        print(f"Find matched {found.body['total']} maintenance window(s)")

        # 3. Archive it, then restore it
        archived = client.maintenance_windows.archive(id=mw_id)
        print(f"Archived: status={archived.body['status']}")

        restored = client.maintenance_windows.unarchive(id=mw_id)
        print(f"Unarchived: status={restored.body['status']}")

        # 4. Update: rename and disable it
        updated = client.maintenance_windows.update(
            id=mw_id,
            title="kbnpy-example-weekly-maintenance-renamed",
            enabled=False,
        )
        print(f"Updated: title={updated.body['title']} status={updated.body['status']}")
    finally:
        # 5. Clean up
        if mw_id is not None:
            client.maintenance_windows.delete(id=mw_id)
            print(f"Deleted maintenance window {mw_id}")
        client.close()


if __name__ == "__main__":
    main()
