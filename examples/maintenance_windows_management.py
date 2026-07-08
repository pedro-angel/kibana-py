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

Maintenance windows require a Platinum or higher license (or a trial). The
Maintenance Windows API is generally available in Kibana 9.4. On an
unlicensed (Basic) stack, creation is rejected -- this example asserts that
exact rejection instead of crashing or skipping silently.

Run this example:
    python examples/maintenance_windows_management.py
"""

from datetime import UTC, datetime, timedelta

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import AuthorizationException, NotFoundError


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    prefix = resource_prefix(__file__)  # "kbnpy-maintenance-windows"
    title = f"{prefix}-weekly-maintenance"

    # Start next week so the maintenance window is "upcoming". (Kibana only
    # materializes recurring events within a limited look-ahead horizon, so a
    # far-future start would be reported as "finished".)
    start = (datetime.now(UTC) + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    mw_id = None
    created: list[tuple[str, str]] = []
    try:
        # 0. Idempotent start: this example's maintenance windows get
        # server-assigned IDs, so there is no fixed ID to pre-delete.
        # Instead clear this example's OWN leftovers from earlier kept runs
        # by matching the title prefix (own scope only — this also catches
        # the "-renamed" title left behind by step 4 below).
        #
        # 1. Create a weekly two-hour maintenance window scoped by a KQL
        # query. This requires a Platinum/Enterprise license (or trial);
        # assert the exact rejection rather than crashing or skipping
        # silently when unlicensed.
        try:
            leftovers = client.maintenance_windows.find(per_page=100)
            stale = [
                mw
                for mw in leftovers.body["maintenanceWindows"]
                if mw["title"].startswith(prefix)
            ]
            for mw in stale:
                try:
                    client.maintenance_windows.delete(id=mw["id"])
                except NotFoundError:
                    pass
            if stale:
                print(f"Cleared {len(stale)} leftover maintenance window(s)")

            created_mw = client.maintenance_windows.create(
                title=title,
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
        except AuthorizationException as exc:
            print(f"Maintenance window creation rejected (license required): {exc}")
            return
        mw_id = created_mw.body["id"]
        created.append(("maintenance window", mw_id))
        print(
            f"Created maintenance window {mw_id} (status={created_mw.body['status']})"
        )

        # 2. Get it by ID and search for it
        fetched = client.maintenance_windows.get(id=mw_id)
        print(f"Fetched by ID: title={fetched.body['title']}")

        found = client.maintenance_windows.find(
            title=title, status=["upcoming", "running"]
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
            title=f"{title}-renamed",
            enabled=False,
        )
        print(f"Updated: title={updated.body['title']} status={updated.body['status']}")
    finally:
        # 5. Clean up
        if mw_id is not None:
            if should_cleanup():
                try:
                    client.maintenance_windows.delete(id=mw_id)
                    print(f"Deleted maintenance window {mw_id}")
                except NotFoundError:
                    pass
            else:
                print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
