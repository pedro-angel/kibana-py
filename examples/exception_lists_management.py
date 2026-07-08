#!/usr/bin/env python3
"""
Exception Lists Management Example

This example shows the minimal code needed to:
1. Create a detection exception list
2. Add an exception item that suppresses alerts for a trusted host
3. Read the list, its items and the per-OS summary
4. Export the list as NDJSON and re-import it as a new list
5. Clean up (delete the lists)

Run this example:
    python examples/exception_lists_management.py
"""

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import NotFoundError


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    prefix = resource_prefix(__file__)  # "kbnpy-exception-lists"
    list_id = f"{prefix}-trusted-hosts"
    imported_id = None
    created: list[tuple[str, str]] = []
    try:
        # Idempotent start: clear only THIS example's own prior list
        try:
            client.exception_lists.delete(list_id=list_id)
        except NotFoundError:
            pass

        # 1. Create a detection exception list
        created_list = client.exception_lists.create(
            name="Trusted hosts (kibana-py example)",
            description="Hosts that should never generate detection alerts",
            type="detection",
            list_id=list_id,
            tags=["kibana-py-example"],
        )
        created.append(("exception list", list_id))
        print(f"Created exception list {created_list.body['id']} ({list_id})")

        # 2. Add an exception item for a trusted host
        item = client.exception_lists.create_item(
            list_id=list_id,
            name="Trusted build server",
            description="Suppress alerts from the CI build server",
            os_types=["linux"],
            entries=[
                {
                    "field": "host.name",
                    "operator": "included",
                    "type": "match",
                    "value": "build-server-01",
                }
            ],
        )
        print(f"Created exception item {item.body['item_id']}")

        # 3. Read the list, its items and the per-OS summary
        items = client.exception_lists.find_items(list_id=list_id)
        summary = client.exception_lists.get_summary(list_id=list_id)
        print(f"List now has {items.body['total']} item(s); summary: {summary.body}")

        # 4. Export as NDJSON and re-import as a brand new list
        exported = client.exception_lists.export(
            id=created_list.body["id"], list_id=list_id, namespace_type="single"
        )
        result = client.exception_lists.import_lists(
            file=exported.body, as_new_list=True
        )
        print(f"Re-imported: success={result.body['success']}")

        # Find the imported copy so we can clean it up
        found = client.exception_lists.find(
            filter='exception-list.attributes.name:"Trusted hosts (kibana-py example)"',
            per_page=100,
        )
        for lst in found.body["data"]:
            if lst["id"] != created_list.body["id"]:
                imported_id = lst["id"]
                created.append(("exception list (imported copy)", imported_id))
                print(f"Imported copy has list_id {lst['list_id']}")
    finally:
        # 5. Clean up both lists (items are deleted with their list)
        if should_cleanup():
            try:
                client.exception_lists.delete(list_id=list_id)
                print(f"Deleted exception list {list_id}")
            except NotFoundError:
                pass
            if imported_id is not None:
                try:
                    client.exception_lists.delete(id=imported_id)
                    print(f"Deleted imported copy {imported_id}")
                except NotFoundError:
                    pass
        else:
            print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
