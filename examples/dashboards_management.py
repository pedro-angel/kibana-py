#!/usr/bin/env python3
"""
Dashboards Management Example (tech preview API, Kibana 9.4+)

Demonstrates the Dashboards HTTP API:
1. Create a dashboard with a markdown panel, tags and a time range
2. Get it back and inspect the data model
3. Upsert a dashboard with a custom ID (PUT)
4. Search dashboards with query/tags filters and pagination
5. Clean up

Run this example:
    python examples/dashboards_management.py
"""

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana


def main():
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    prefix = resource_prefix(__file__)  # "kbnpy-dashboards"
    tag = f"{prefix}-tag"
    created: list[tuple[str, str]] = []
    try:
        # 1. Create a dashboard (the server assigns the ID)
        created_dashboard = client.dashboards.create(
            title=f"{prefix} Team Overview",
            description="Created by the kibana-py dashboards example",
            tags=[tag],
            time_range={"from": "now-7d", "to": "now"},
            panels=[
                {
                    "type": "markdown",
                    "grid": {"x": 0, "y": 0, "w": 48, "h": 8},
                    "config": {
                        "title": "Welcome",
                        "content": "# Team Overview\nManaged by *kibana-py*.",
                        "settings": {"open_links_in_new_tab": True},
                    },
                }
            ],
        )
        dashboard_id = created_dashboard.body["id"]
        created.append(("dashboard", dashboard_id))
        print(f"✓ Created dashboard: {dashboard_id}")

        # 2. Read it back: responses are {id, data, meta} envelopes
        fetched = client.dashboards.get(id=dashboard_id)
        data = fetched.body["data"]
        print(f"  Title: {data['title']}")
        print(f"  Tags: {data['tags']}")
        print(f"  Time range: {data['time_range']}")
        print(f"  Panels: {[p['type'] for p in data['panels']]}")
        print(f"  Updated at: {fetched.body['meta']['updated_at']}")

        # 3. Upsert with a custom ID — create() cannot take an id;
        #    PUT creates the dashboard when the ID does not exist yet.
        custom_id = f"{prefix}-custom-id"
        upserted = client.dashboards.update(
            id=custom_id,
            title=f"{prefix} Custom ID Dashboard",
        )
        created.append(("dashboard", upserted.body["id"]))
        print(f"✓ Upserted dashboard with custom ID: {upserted.body['id']}")

        # 4. Search: simple_query_string on title/description + tag filters
        results = client.dashboards.get_all(query=f"{prefix}*", per_page=10, page=1)
        print(f"✓ Search found {results.body['total']} dashboard(s):")
        for item in results.body["dashboards"]:
            print(f"  - {item['id']}: {item['data']['title']}")

        tagged = client.dashboards.get_all(tags=[tag])
        print(f"✓ Tag filter found {tagged.body['total']} dashboard(s)")

    finally:
        # 5. Clean up
        if should_cleanup():
            for _, dashboard_id in created:
                try:
                    client.dashboards.delete(id=dashboard_id)
                    print(f"✓ Deleted dashboard: {dashboard_id}")
                except Exception as e:
                    print(f"❌ Failed to delete {dashboard_id}: {e}")
        else:
            print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
