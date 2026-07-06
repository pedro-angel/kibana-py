#!/usr/bin/env python3
"""
Osquery Management Example

This example shows the minimal code needed to:
1. Create a saved query (a reusable Osquery SQL query)
2. Create a pack that schedules the query
3. List packs and saved queries
4. Run a live query (requires at least one enrolled Elastic Agent)
5. Clean up (delete the pack and the saved query)

Run this example:
    python examples/osquery_management.py
"""

from utils import get_kibana_config

from kibana import Kibana
from kibana.exceptions import ApiError

UPTIME_QUERY = "select * from uptime;"


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    saved_query_id = None
    pack_id = None
    try:
        # 1. Create a saved query
        saved = client.osquery.create_saved_query(
            id="kbnpy_example_uptime",
            query=UPTIME_QUERY,
            interval="60",
            description="Host uptime (kibana-py example)",
            ecs_mapping={"host.uptime": {"field": "total_seconds"}},
        )
        saved_query_id = saved.body["data"]["saved_object_id"]
        print(f"Created saved query {saved_query_id}")

        # 2. Create a pack that schedules the same query every hour
        pack = client.osquery.create_pack(
            name="kbnpy-example-pack",
            description="Track host uptime (kibana-py example)",
            enabled=False,  # set policy_ids and enabled=True to schedule it
            queries={"uptime": {"query": UPTIME_QUERY, "interval": 3600}},
        )
        pack_id = pack.body["data"]["saved_object_id"]
        print(f"Created pack {pack_id}")

        # 3. List packs and saved queries
        packs = client.osquery.find_packs(page=1, page_size=10)
        print(f"Packs: {packs.body['total']}")
        queries = client.osquery.find_saved_queries(page=1, page_size=10)
        print(f"Saved queries: {queries.body['total']}")

        # 4. Run a live query on all agents (needs enrolled Elastic Agents
        #    running the Osquery Manager integration)
        try:
            live = client.osquery.create_live_query(query=UPTIME_QUERY, agent_all=True)
            action_id = live.body["data"]["action_id"]
            print(f"Live query queued: action_id={action_id}")

            details = client.osquery.get_live_query(id=action_id)
            print(f"Live query status: {details.body['data'].get('status')}")
        except ApiError as exc:
            print(f"Live query not dispatched (no enrolled agents?): {exc.message}")
    finally:
        # 5. Clean up
        if pack_id is not None:
            client.osquery.delete_pack(id=pack_id)
            print(f"Deleted pack {pack_id}")
        if saved_query_id is not None:
            client.osquery.delete_saved_query(id=saved_query_id)
            print(f"Deleted saved query {saved_query_id}")
        client.close()


if __name__ == "__main__":
    main()
