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

from utils import get_kibana_config

from kibana import Kibana


def main():
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    created_ids = []
    try:
        # 1. Create a dashboard (the server assigns the ID)
        created = client.dashboards.create(
            title="kbnpy-example Team Overview",
            description="Created by the kibana-py dashboards example",
            tags=["kbnpy-example-tag"],
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
        dashboard_id = created.body["id"]
        created_ids.append(dashboard_id)
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
        upserted = client.dashboards.update(
            id="kbnpy-example-custom-id",
            title="kbnpy-example Custom ID Dashboard",
        )
        created_ids.append(upserted.body["id"])
        print(f"✓ Upserted dashboard with custom ID: {upserted.body['id']}")

        # 4. Search: simple_query_string on title/description + tag filters
        results = client.dashboards.get_all(query="kbnpy-example*", per_page=10, page=1)
        print(f"✓ Search found {results.body['total']} dashboard(s):")
        for item in results.body["dashboards"]:
            print(f"  - {item['id']}: {item['data']['title']}")

        tagged = client.dashboards.get_all(tags=["kbnpy-example-tag"])
        print(f"✓ Tag filter found {tagged.body['total']} dashboard(s)")

    finally:
        # 5. Clean up
        for dashboard_id in created_ids:
            try:
                client.dashboards.delete(id=dashboard_id)
                print(f"✓ Deleted dashboard: {dashboard_id}")
            except Exception as e:
                print(f"❌ Failed to delete {dashboard_id}: {e}")
        client.close()


if __name__ == "__main__":
    main()
