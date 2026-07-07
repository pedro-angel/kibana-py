#!/usr/bin/env python3
"""
Attack Discovery Management Example

This example shows the minimal code needed to:
1. Create (or reuse) a space with the security solution view (Attack
   Discovery needs it) -- a STABLE id shared across runs
2. Idempotent start: clear this example's own leftover connector, matched
   by a STABLE id, so re-running a kept example replaces its connector
   instead of accumulating a new one
3. Create a Gen AI connector for an OpenAI-compatible backend
4. Idempotent start: clear this example's own leftover schedule(s), matched
   by name prefix, so re-running a kept example replaces its schedule
   instead of accumulating a new one
5. Create, inspect, enable/disable and delete an Attack Discovery schedule
6. Search Attack discoveries and list generation runs
7. Clean up (schedule, connector, space) in reverse creation order

Optionally set KBNPY_LMSTUDIO_OPENAI_URL / KBNPY_LMSTUDIO_MODEL to point the
connector at a real OpenAI-compatible backend (e.g. LM Studio). Note that the
connector's apiUrl must be the full /chat/completions endpoint. The happy
path below does not require the LLM to actually be reachable -- it only
exercises the schedule/discovery API surface, which works against a
connector configuration alone.

Run this example:
    python examples/attack_discovery_management.py
"""

import os
import uuid

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import NotFoundError

LLM_URL = os.getenv("KBNPY_LMSTUDIO_OPENAI_URL", "http://localhost:1234/v1")
LLM_MODEL = os.getenv("KBNPY_LMSTUDIO_MODEL", "qwen/qwen3.5-9b")


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    prefix = resource_prefix(__file__)  # "kbnpy-attack-discovery"
    suffix = uuid.uuid4().hex[:8]
    # STABLE space id: the schedule idempotent-start below (step 4) needs a
    # space that survives across kept runs to find and replace its own prior
    # schedule, so the space itself is shared infra -- created only if
    # missing, like the value-list data streams in lists_management.py.
    space_id = prefix
    # STABLE connector id: like the space, the connector would otherwise
    # accumulate a fresh uuid-suffixed instance on every kept re-run --
    # pre-delete any leftover under this id (own scope) before creating a
    # fresh one, the same Pattern-S used in connectors_management.py.
    connector_id = f"{prefix}-conn"
    schedule_id = None
    created: list[tuple[str, str]] = []
    try:
        # 1. Attack Discovery requires the securitySolutionAttackDiscovery
        #    feature, which is disabled in spaces with the Elasticsearch
        #    solution view -- create (or reuse) a security-solution space
        #    for the demo.
        try:
            client.spaces.get(id=space_id)
            print(f"Reusing existing space {space_id}")
        except NotFoundError:
            client.spaces.create(id=space_id, name=space_id, solution="security")
            print(f"Created space {space_id}")
        created.append(("space", space_id))

        # 2. Idempotent start: clear any leftover connector under this
        #    example's stable id (own scope only) before creating fresh.
        try:
            client.connectors.delete(id=connector_id, space_id=space_id)
            print(f"Cleared leftover connector {connector_id!r}")
        except NotFoundError:
            pass

        # 3. Create a Gen AI connector (OpenAI-compatible backend)
        api_url = LLM_URL.rstrip("/")
        if not api_url.endswith("/chat/completions"):
            api_url = f"{api_url}/chat/completions"
        connector = client.connectors.create(
            id=connector_id,
            name=f"{prefix}-conn-{suffix}",
            connector_type_id=".gen-ai",
            config={
                "apiProvider": "OpenAI",
                "apiUrl": api_url,
                "defaultModel": LLM_MODEL,
            },
            secrets={"apiKey": "dummy-key"},
            space_id=space_id,
        )
        created.append(("connector", connector_id))
        print(f"Created .gen-ai connector {connector_id} -> {api_url}")

        # 4. Idempotent start: the schedule is the resource most worth not
        #    accumulating (it's a periodic background job). Since the space
        #    is now shared/reused across runs, clear this example's OWN
        #    leftover schedule(s) -- matched by name prefix, own scope only
        #    -- before creating a fresh one. find_schedules() has no
        #    server-side name filter, so filter client-side.
        leftover_schedules = client.attack_discovery.find_schedules(
            per_page=100, space_id=space_id
        )
        cleared = 0
        for sched in leftover_schedules.body["data"]:
            if sched["name"].startswith(prefix):
                try:
                    client.attack_discovery.delete_schedule(
                        id=sched["id"], space_id=space_id
                    )
                    cleared += 1
                except NotFoundError:
                    pass
        if cleared:
            print(f"Cleared {cleared} leftover schedule(s)")

        # 5. Create a daily Attack Discovery schedule using that connector
        created_schedule = client.attack_discovery.create_schedule(
            name=f"{prefix}-daily-{suffix}",
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
        schedule_id = created_schedule.body["id"]
        created.append(("schedule", schedule_id))
        print(f"Created schedule {schedule_id} ({created_schedule.body['name']})")

        # Enable, inspect and disable the schedule
        client.attack_discovery.enable_schedule(id=schedule_id, space_id=space_id)
        fetched = client.attack_discovery.get_schedule(
            id=schedule_id, space_id=space_id
        )
        print(f"Schedule enabled: {fetched.body['enabled']}")
        client.attack_discovery.disable_schedule(id=schedule_id, space_id=space_id)

        found = client.attack_discovery.find_schedules(per_page=100, space_id=space_id)
        print(f"Schedules in space: {found.body['total']}")

        # 6. Search Attack discoveries and list generation runs. This does
        # NOT require the LLM connector to be reachable -- it only reports
        # counts (likely 0 without a real backend generating discoveries).
        discoveries = client.attack_discovery.find(
            start="now-24h", end="now", space_id=space_id
        )
        print(f"Attack discoveries in the last 24h: {discoveries.body['total']}")

        generations = client.attack_discovery.get_generations(
            size=10, space_id=space_id
        )
        print(f"Recent generation runs: {len(generations.body['generations'])}")
    finally:
        # 7. Clean up in reverse creation order: schedule -> connector -> space
        if should_cleanup():
            if schedule_id is not None:
                try:
                    client.attack_discovery.delete_schedule(
                        id=schedule_id, space_id=space_id
                    )
                    print(f"Deleted schedule {schedule_id}")
                except NotFoundError:
                    pass
            try:
                client.connectors.delete(id=connector_id, space_id=space_id)
                print(f"Deleted connector {connector_id}")
            except NotFoundError:
                pass
            try:
                client.spaces.delete(id=space_id)
                print(f"Deleted space {space_id}")
            except NotFoundError:
                pass
        else:
            print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
