#!/usr/bin/env python3
"""
SLOs Management Example

Demonstrates the Kibana SLO (Service Level Objective) API:
1. Create an SLO with a custom KQL indicator
2. Get it back and list SLOs (find / find_definitions)
3. Update it
4. Disable / enable it
5. Bulk delete it and poll the deletion task status

Requires a Platinum-level (or trial) license.

Run this example:
    python examples/slos_management.py
"""

import time
import uuid

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import ApiError

PREFIX = resource_prefix(__file__)  # "kbnpy-slos"
SLO_NAME = f"{PREFIX}-{uuid.uuid4().hex[:8]}"


def main() -> None:
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    slo_id: str | None = None
    created: list[tuple[str, str]] = []
    try:
        # 1. Create an SLO: 99% of documents in the last 7 days are "good"
        try:
            created_slo = client.slos.create(
                name=SLO_NAME,
                description="Example availability SLO managed by kibana-py",
                indicator={
                    "type": "sli.kql.custom",
                    "params": {
                        "index": f"{PREFIX}-logs-*",
                        "good": "status: ok",
                        "total": "",
                        "timestampField": "@timestamp",
                    },
                },
                time_window={"duration": "7d", "type": "rolling"},
                budgeting_method="occurrences",
                objective={"target": 0.99},
                tags=["kbnpy", "slos"],
            )
        except ApiError as exc:
            # SLOs require a Platinum-level (or trial) license; assert the
            # real rejection instead of crashing when unlicensed.
            print(f"SLO creation rejected (license required?): {exc}")
            return
        slo_id = created_slo.body["id"]
        created.append(("slo", slo_id))
        print(f"Created SLO {SLO_NAME!r} with id {slo_id}")

        # 2. Read it back and list SLOs
        slo = client.slos.get(slo_id=slo_id)
        print(f"Fetched SLO: enabled={slo.body['enabled']}, tags={slo.body['tags']}")

        found = client.slos.find(kql_query=f'slo.name:"{SLO_NAME}"')
        print(f"find() matched {found.body['total']} SLO(s)")

        definitions = client.slos.find_definitions(search=SLO_NAME)
        print(f"find_definitions() matched {definitions.body['total']} definition(s)")

        # 3. Update (partial: only the provided fields change)
        updated = client.slos.update(
            slo_id=slo_id, description="Updated description", tags=["kbnpy"]
        )
        print(f"Updated description to {updated.body['description']!r}")

        # 4. Disable and re-enable
        client.slos.disable(slo_id=slo_id)
        print(f"Disabled: enabled={client.slos.get(slo_id=slo_id).body['enabled']}")
        client.slos.enable(slo_id=slo_id)
        print(f"Enabled:  enabled={client.slos.get(slo_id=slo_id).body['enabled']}")
    finally:
        # 5. Clean up: bulk delete (asynchronous) + poll the task status,
        # with a single-delete fallback if the bulk task does not finish
        # in time. Only runs when the caller opts into cleanup.
        if slo_id is not None:
            if should_cleanup():
                task = client.slos.bulk_delete(slo_ids=[slo_id])
                task_id = task.body["taskId"]
                print(f"Bulk delete started, task {task_id}")

                deadline = time.time() + 60
                done = False
                while time.time() < deadline:
                    status = client.slos.bulk_delete_status(task_id=task_id)
                    if status.body.get("isDone"):
                        print(f"Bulk delete finished: {status.body.get('results')}")
                        done = True
                        break
                    time.sleep(2)

                if not done:  # fallback cleanup if bulk delete did not finish
                    try:
                        client.slos.delete(slo_id=slo_id)
                        print(f"Deleted SLO {slo_id}")
                    except ApiError as exc:
                        print(f"Cleanup failed: {exc}")
            else:
                print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
