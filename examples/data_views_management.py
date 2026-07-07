#!/usr/bin/env python3
"""
Data Views Management Example

Demonstrates the Kibana Data Views API:
1. Creating a data view
2. Listing and retrieving data views
3. Updating a data view and its field metadata
4. Managing runtime fields (create/upsert, get, update, delete)
5. Reading the default data view and previewing a reference swap
6. Cleaning up

Run this example:
    python examples/data_views_management.py
"""

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import NotFoundError


def main() -> None:
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    prefix = resource_prefix(__file__)  # "kbnpy-data-views"
    view_id = f"{prefix}-view"
    created: list[tuple[str, str]] = []
    try:
        # 0. Idempotent start: clear only THIS example's own prior data view,
        # then create fresh
        try:
            client.data_views.delete(view_id=view_id)
        except NotFoundError:
            pass

        # 1. Create a data view (allowNoIndex lets it exist without data)
        created_view = client.data_views.create(
            data_view={
                "id": view_id,
                "title": f"{prefix}-logs-*",
                "name": "Example logs",
                "timeFieldName": "@timestamp",
                "allowNoIndex": True,
            }
        )
        created.append(("data view", view_id))
        print(f"Created data view: {created_view['data_view']['id']}")

        # 2. List all data views and fetch ours back
        listed = client.data_views.get_all()
        print(f"Data views in space: {len(listed['data_view'])}")
        fetched = client.data_views.get(view_id=view_id)
        print(f"Fetched '{fetched['data_view']['name']}'")

        # 3. Update the data view, then attach field metadata
        client.data_views.update(
            view_id=view_id,
            data_view={"name": "Example logs (renamed)"},
        )
        client.data_views.update_fields_metadata(
            view_id=view_id,
            fields={"message": {"customLabel": "Log message"}},
        )
        print("Updated data view name and field metadata")

        # 4. Runtime field lifecycle
        client.data_views.create_runtime_field(
            view_id=view_id,
            name="hello_field",
            runtime_field={"type": "keyword", "script": {"source": "emit('hello')"}},
        )
        client.data_views.update_runtime_field(
            view_id=view_id,
            name="hello_field",
            runtime_field={"script": {"source": "emit('hello world')"}},
        )
        rt = client.data_views.get_runtime_field(view_id=view_id, name="hello_field")
        print(f"Runtime field script: {rt['fields'][0]['runtimeField']['script']}")
        client.data_views.delete_runtime_field(view_id=view_id, name="hello_field")
        print("Runtime field created, updated, and deleted")

        # 5. Default data view + dry-run of a reference swap
        default = client.data_views.get_default()
        print(f"Default data view id: {default['data_view_id'] or '(none)'}")
        preview = client.data_views.preview_swap_references(
            from_id=view_id, to_id=view_id
        )
        print(f"Swap preview would change {len(preview['result'])} saved object(s)")
    finally:
        # 6. Clean up
        if should_cleanup():
            try:
                client.data_views.delete(view_id=view_id)
                print(f"Deleted data view: {view_id}")
            except NotFoundError:
                pass
        else:
            print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
