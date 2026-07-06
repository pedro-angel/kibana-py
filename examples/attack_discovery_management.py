#!/usr/bin/env python3
"""
Attack Discovery Management Example

This example shows the minimal code needed to:
1. Create a space with the security solution view (Attack Discovery needs it)
2. Create a Gen AI connector for an OpenAI-compatible backend
3. Create, inspect, enable/disable and delete an Attack Discovery schedule
4. Search Attack discoveries and list generation runs
5. Clean up (schedule, connector, space)

Optionally set KBNPY_LMSTUDIO_OPENAI_URL / KBNPY_LMSTUDIO_MODEL to point the
connector at a real OpenAI-compatible backend (e.g. LM Studio). Note that the
connector's apiUrl must be the full /chat/completions endpoint.

Run this example:
    python examples/attack_discovery_management.py
"""

import os
import uuid

from utils import get_kibana_config

from kibana import Kibana

LLM_URL = os.getenv("KBNPY_LMSTUDIO_OPENAI_URL", "http://localhost:1234/v1")
LLM_MODEL = os.getenv("KBNPY_LMSTUDIO_MODEL", "qwen/qwen3.5-9b")


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    suffix = uuid.uuid4().hex[:8]
    space_id = f"kbnpy-attack-discovery-{suffix}"
    connector_id = None
    schedule_id = None
    try:
        # 1. Attack Discovery requires the securitySolutionAttackDiscovery
        #    feature, which is disabled in spaces with the Elasticsearch
        #    solution view -- create a security-solution space for the demo.
        client.spaces.create(id=space_id, name=space_id, solution="security")
        print(f"Created space {space_id}")

        # 2. Create a Gen AI connector (OpenAI-compatible backend)
        api_url = LLM_URL.rstrip("/")
        if not api_url.endswith("/chat/completions"):
            api_url = f"{api_url}/chat/completions"
        connector = client.connectors.create(
            name=f"kbnpy-attack-discovery-conn-{suffix}",
            connector_type_id=".gen-ai",
            config={
                "apiProvider": "OpenAI",
                "apiUrl": api_url,
                "defaultModel": LLM_MODEL,
            },
            secrets={"apiKey": "dummy-key"},
            space_id=space_id,
        )
        connector_id = connector.body["id"]
        print(f"Created .gen-ai connector {connector_id} -> {api_url}")

        # 3. Create a daily Attack Discovery schedule using that connector
        created = client.attack_discovery.create_schedule(
            name=f"kbnpy-daily-attack-discovery-{suffix}",
            params={
                "alerts_index_pattern": f".alerts-security.alerts-{space_id}",
                "api_config": {
                    "connectorId": connector_id,
                    "actionTypeId": ".gen-ai",
                    "name": connector.body["name"],
                },
                "size": 100,
            },
            schedule={"interval": "24h"},
            space_id=space_id,
        )
        schedule_id = created.body["id"]
        print(f"Created schedule {schedule_id} ({created.body['name']})")

        # Enable, inspect and disable the schedule
        client.attack_discovery.enable_schedule(id=schedule_id, space_id=space_id)
        fetched = client.attack_discovery.get_schedule(
            id=schedule_id, space_id=space_id
        )
        print(f"Schedule enabled: {fetched.body['enabled']}")
        client.attack_discovery.disable_schedule(id=schedule_id, space_id=space_id)

        found = client.attack_discovery.find_schedules(per_page=100, space_id=space_id)
        print(f"Schedules in space: {found.body['total']}")

        # 4. Search Attack discoveries and list generation runs
        discoveries = client.attack_discovery.find(
            start="now-24h", end="now", space_id=space_id
        )
        print(f"Attack discoveries in the last 24h: {discoveries.body['total']}")

        generations = client.attack_discovery.get_generations(
            size=10, space_id=space_id
        )
        print(f"Recent generation runs: {len(generations.body['generations'])}")
    finally:
        # 5. Clean up
        if schedule_id is not None:
            client.attack_discovery.delete_schedule(id=schedule_id, space_id=space_id)
            print(f"Deleted schedule {schedule_id}")
        if connector_id is not None:
            client.connectors.delete(id=connector_id, space_id=space_id)
            print(f"Deleted connector {connector_id}")
        try:
            client.spaces.delete(id=space_id)
            print(f"Deleted space {space_id}")
        except Exception:
            pass
        client.close()


if __name__ == "__main__":
    main()
