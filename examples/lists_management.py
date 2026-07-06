#!/usr/bin/env python3
"""
Security Value Lists Management Example

This example shows the minimal code needed to:
1. Check that the value list data streams exist (create them if needed)
2. Create a value list of IPs
3. Add a single list item
4. Import more values from a newline-separated payload
5. Find and export the list items
6. Clean up (delete the list and all of its items)

Run this example:
    python examples/lists_management.py
"""

import time

from utils import get_kibana_config

from kibana import Kibana
from kibana.exceptions import NotFoundError


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    list_id = "kbnpy-example-bad-ips"
    try:
        # 1. Make sure the value list data streams exist
        try:
            status = client.lists.get_index_status()
        except NotFoundError:
            client.lists.create_index()
            status = client.lists.get_index_status()
        print(f"Value list data streams ready: {status.body}")

        # 2. Create a value list of IPs
        created = client.lists.create(
            name="Bad ips (kibana-py example)",
            description="Known bad IP addresses",
            type="ip",
            id=list_id,
        )
        print(f"Created list {created.body['id']} (type={created.body['type']})")

        # 3. Add a single list item
        item = client.lists.create_item(
            list_id=list_id, value="192.0.2.1", refresh="wait_for"
        )
        print(f"Added item {item.body['id']} value={item.body['value']}")

        # 4. Import more values (newline-separated file upload)
        client.lists.import_items(
            file=["198.51.100.1", "198.51.100.2"],
            list_id=list_id,
            refresh="wait_for",
        )
        # Imported items land slightly asynchronously; give Kibana a moment
        for _ in range(20):
            found = client.lists.find_items(list_id=list_id)
            if found.body["total"] >= 3:
                break
            time.sleep(0.5)
        print(f"List now holds {found.body['total']} items")

        # 5. Export the values (newline-separated dump, parsed into a list)
        exported = client.lists.export_items(list_id=list_id)
        print(f"Exported values: {sorted(str(v) for v in exported.body)}")
    finally:
        # 6. Clean up: deleting the list also deletes all of its items
        try:
            client.lists.delete(id=list_id)
            print(f"Deleted list {list_id}")
        except NotFoundError:
            pass
        client.close()


if __name__ == "__main__":
    main()
