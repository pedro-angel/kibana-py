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

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import ApiError, NotFoundError

UPTIME_QUERY = "select * from uptime;"


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    prefix = resource_prefix(__file__)  # "kbnpy-osquery"
    saved_query_id = f"{prefix}-uptime"
    pack_name = f"{prefix}-pack"
    pack_id = None
    created: list[tuple[str, str]] = []
    try:
        # Idempotent start: clear only THIS example's own prior resources,
        # in the same order as teardown (pack, then saved query). Neither
        # find_packs() nor find_saved_queries() supports filtering by name,
        # and delete needs the server-generated saved_object_id (not the
        # requested literal id/name), so existing ones are paged through
        # and matched, then deleted by their real saved_object_id.
        existing_packs = client.osquery.find_packs(page=1, page_size=100).body["data"]
        for p in existing_packs:
            if p["name"] == pack_name:
                client.osquery.delete_pack(id=p["saved_object_id"])
        existing_queries = client.osquery.find_saved_queries(
            page=1, page_size=100
        ).body["data"]
        for q in existing_queries:
            if q["id"] == saved_query_id:
                client.osquery.delete_saved_query(id=q["saved_object_id"])

        # 1. Create a saved query
        saved = client.osquery.create_saved_query(
            id=saved_query_id,
            query=UPTIME_QUERY,
            interval="60",
            description="Host uptime (kibana-py example)",
            ecs_mapping={"host.uptime": {"field": "total_seconds"}},
        )
        saved_query_id = saved.body["data"]["saved_object_id"]
        created.append(("osquery saved query", saved_query_id))
        print(f"Created saved query {saved_query_id}")

        # 2. Create a pack that schedules the same query every hour
        pack = client.osquery.create_pack(
            name=pack_name,
            description="Track host uptime (kibana-py example)",
            enabled=False,  # set policy_ids and enabled=True to schedule it
            queries={"uptime": {"query": UPTIME_QUERY, "interval": 3600}},
        )
        pack_id = pack.body["data"]["saved_object_id"]
        created.append(("osquery pack", pack_id))
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
        # 5. Clean up — pack before saved query (they're independent, but
        # this preserves the original teardown order).
        if should_cleanup():
            if pack_id is not None:
                client.osquery.delete_pack(id=pack_id)
                print(f"Deleted pack {pack_id}")
            try:
                client.osquery.delete_saved_query(id=saved_query_id)
                print(f"Deleted saved query {saved_query_id}")
            except NotFoundError:
                pass
        else:
            print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
