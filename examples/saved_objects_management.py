#!/usr/bin/env python3
"""
Saved Objects Management Example

Demonstrates the Saved Objects HTTP API:
1. Create saved objects (single and bulk)
2. Find objects with search/reference filters
3. Export objects as NDJSON
4. Delete and restore them via import (round trip)
5. Resolve import conflicts
6. Clean up

Note: the single-object and bulk CRUD endpoints are deprecated in Kibana
9.4.3 in favor of type-specific APIs (dashboards, data views, ...) and the
export/import APIs, but remain functional.

Run this example:
    python examples/saved_objects_management.py
"""

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import NotFoundError

PREFIX = resource_prefix(__file__)  # "kbnpy-saved-objects"


def tag_attributes(name: str) -> dict:
    return {"name": name, "description": "kibana-py example", "color": "#00bfb3"}


def main():
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    created: list[tuple[str, str]] = []  # (type, id) pairs for cleanup
    try:
        # 0. Idempotent start: clear only THIS example's own prior objects
        for obj_type, obj_id in [
            ("tag", f"{PREFIX}-tag"),
            ("dashboard", f"{PREFIX}-dashboard"),
            ("tag", f"{PREFIX}-bulk-0"),
            ("tag", f"{PREFIX}-bulk-1"),
        ]:
            try:
                client.saved_objects.delete(type=obj_type, id=obj_id, force=True)
            except NotFoundError:
                pass

        # 1. Create a tag and a dashboard referencing it
        tag = client.saved_objects.create(
            type="tag", id=f"{PREFIX}-tag", attributes=tag_attributes(PREFIX)
        )
        created.append(("tag", tag["id"]))
        print(f"Created tag: {tag['id']}")

        dashboard = client.saved_objects.create(
            type="dashboard",
            id=f"{PREFIX}-dashboard",
            attributes={"title": f"{PREFIX} dashboard"},
            references=[{"type": "tag", "id": tag["id"], "name": "tag-ref"}],
        )
        created.append(("dashboard", dashboard["id"]))
        print(f"Created dashboard: {dashboard['id']}")

        # 2. Bulk create two more tags in one request
        bulk = client.saved_objects.bulk_create(
            objects=[
                {
                    "type": "tag",
                    "id": f"{PREFIX}-bulk-{i}",
                    "attributes": tag_attributes(f"{PREFIX}-bulk-{i}"),
                }
                for i in range(2)
            ]
        )
        for obj in bulk["saved_objects"]:
            created.append((obj["type"], obj["id"]))
        print(f"Bulk-created {len(bulk['saved_objects'])} tags")

        # 3. Find: search_fields/type accept lists (sent as repeated keys),
        #    has_reference filters by reference to another object
        results = client.saved_objects.find(
            type=["tag", "dashboard"],
            search=f"{PREFIX}*",
            search_fields=["name", "title"],
            per_page=20,
        )
        print(f"Find matched {results['total']} object(s)")

        referencing = client.saved_objects.find(
            type="dashboard", has_reference={"type": "tag", "id": tag["id"]}
        )
        print(f"Dashboards referencing the tag: {referencing['total']}")

        # 4. Export the dashboard (with referenced objects) as NDJSON.
        #    The parsed response body is a list of dicts; the last line is
        #    an export-details summary.
        exported = client.saved_objects.export(
            objects=[{"type": "dashboard", "id": dashboard["id"]}],
            include_references_deep=True,
        )
        lines = list(exported)
        print(f"Exported {lines[-1]['exportedCount']} object(s)")

        # 5. Delete the dashboard, then restore it by importing the export
        client.saved_objects.delete(type="dashboard", id=dashboard["id"])
        print("Deleted dashboard")

        imported = client.saved_objects.import_objects(file=lines, overwrite=True)
        print(f"Import success={imported['success']} count={imported['successCount']}")

        restored = client.saved_objects.get(type="dashboard", id=dashboard["id"])
        print(f"Restored dashboard title: {restored['attributes']['title']}")

        # 6. Importing again without overwrite reports conflicts, which
        #    resolve_import_errors can retry with explicit overwrites
        conflict = client.saved_objects.import_objects(file=lines)
        if not conflict["success"]:
            retries = [
                {"type": e["type"], "id": e["id"], "overwrite": True}
                for e in conflict["errors"]
            ]
            resolved = client.saved_objects.resolve_import_errors(
                file=lines, retries=retries
            )
            print(f"Resolved {resolved['successCount']} import conflict(s)")

    finally:
        # 7. Clean up everything we created (bulk_delete for the tags)
        if should_cleanup():
            tags = [{"type": t, "id": i} for t, i in created if t == "tag"]
            others = [(t, i) for t, i in created if t != "tag"]
            try:
                if tags:
                    result = client.saved_objects.bulk_delete(objects=tags, force=True)
                    ok = sum(1 for s in result["statuses"] if s["success"])
                    print(f"Bulk-deleted {ok}/{len(tags)} tags")
            except Exception as e:
                print(f"Failed to bulk-delete tags: {e}")
            for obj_type, obj_id in others:
                try:
                    client.saved_objects.delete(type=obj_type, id=obj_id, force=True)
                    print(f"Deleted {obj_type}: {obj_id}")
                except Exception as e:
                    print(f"Failed to delete {obj_type}/{obj_id}: {e}")
        else:
            print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
