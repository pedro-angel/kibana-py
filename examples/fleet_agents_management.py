#!/usr/bin/env python3
"""
Fleet Elastic Agents Management Example

This example shows the minimal code needed to:
1. Check the Fleet agents setup status (and initiate setup)
2. List enrolled agents and get an agent status summary
3. List agent tags and available agent versions
4. Create a bulk agent action and inspect / cancel it

The dev stack usually has no enrolled agents, so the listings may be empty;
the bulk diagnostics action still demonstrates the action lifecycle.

Run this example:
    python examples/fleet_agents_management.py
"""

from utils import get_kibana_config

from kibana import Kibana


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    try:
        # 1. Fleet agents setup
        setup = client.fleet_agents.get_setup_status()
        print(f"Fleet agents setup ready: {setup.body['isReady']}")
        if setup.body.get("missing_requirements"):
            print(f"  Missing requirements: {setup.body['missing_requirements']}")
        client.fleet_agents.initiate_setup()

        # 2. List agents and summarize their statuses
        agents = client.fleet_agents.get_all(per_page=10, get_status_summary=True)
        print(f"Enrolled agents: {agents.body['total']}")
        for agent in agents.body["items"]:
            print(f"  {agent['id']}: {agent.get('status')} ({agent.get('policy_id')})")

        summary = client.fleet_agents.get_status()
        results = summary.body["results"]
        print(f"Status summary: online={results['online']} error={results['error']}")

        # 3. Tags and upgradable versions
        tags = client.fleet_agents.get_tags(show_inactive=True)
        print(f"Agent tags: {tags.body['items']}")
        versions = client.fleet_agents.get_available_versions()
        print(f"Latest available agent version: {versions.body['items'][0]}")

        # 4. Bulk action lifecycle: request diagnostics, inspect, cancel
        created = client.fleet_agents.bulk_request_diagnostics(
            agents=["kbnpy-fleet-agents-example-missing-agent"],
        )
        action_id = created.body["actionId"]
        print(f"Created bulk diagnostics action {action_id}")

        statuses = client.fleet_agents.get_action_status(per_page=5)
        for action in statuses.body["items"]:
            print(f"  action {action['actionId']}: {action['type']} {action['status']}")

        cancelled = client.fleet_agents.cancel_action(action_id=action_id)
        print(f"Cancelled action {action_id}: {cancelled.body['item']['type']}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
