#!/usr/bin/env python3
"""
Visualizations Management Example

Demonstrates the Kibana Visualizations HTTP API (technical preview in 9.4):
1. Create a Lens metric visualization
2. Get it by ID
3. Update (rename) it
4. Search visualizations by title
5. Delete it (with cleanup in finally)

Run this example:
    python examples/visualizations_management.py
"""

import uuid

from utils import create_kibana_client

from kibana.exceptions import NotFoundError

PREFIX = "kbnpy-visualizations-example"


def metric_config(title: str) -> dict:
    """Minimal Lens metric visualization: count of docs in an index pattern."""
    return {
        "type": "metric",
        "title": title,
        "data_source": {
            "type": "data_view_spec",
            "index_pattern": "logs-*",
        },
        "query": {"expression": "", "language": "kql"},
        "metrics": [{"type": "primary", "operation": "count"}],
    }


def main() -> None:
    client = create_kibana_client()
    title = f"{PREFIX}-{uuid.uuid4().hex[:8]}"
    viz_id = None
    try:
        # 1. Create — the server assigns the ID and returns {id, data, meta}
        created = client.visualizations.create(data=metric_config(title))
        viz_id = created.body["id"]
        print(f"Created visualization {viz_id!r} titled {title!r}")

        # 2. Get by ID
        fetched = client.visualizations.get(id=viz_id)
        print(f"Fetched type={fetched.body['data']['type']}")
        print(f"        created_at={fetched.body['meta']['created_at']}")

        # 3. Update — the body fully replaces the stored configuration
        renamed = f"{title}-renamed"
        updated = client.visualizations.update(id=viz_id, data=metric_config(renamed))
        print(f"Renamed to {updated.body['data']['title']!r}")

        # 4. Search by title text (paginated envelope: data + meta)
        results = client.visualizations.get_all(query=f"{PREFIX}*", per_page=10)
        print(f"Search found {results.body['meta']['total']} visualization(s):")
        for item in results.body["data"]:
            print(f"  - {item['id']}: {item['data']['title']}")
    finally:
        # 5. Delete (cleanup)
        if viz_id is not None:
            try:
                client.visualizations.delete(id=viz_id)
                print(f"Deleted visualization {viz_id!r}")
            except NotFoundError:
                pass
        client.close()


if __name__ == "__main__":
    main()
