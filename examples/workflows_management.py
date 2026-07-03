#!/usr/bin/env python3
"""
Workflows Management Example

This example shows the minimal code needed to:
1. Create a workflow from a YAML definition (manual trigger + console step)
2. Get and search workflows
3. Run the workflow and poll its execution until it finishes
4. Read the execution logs
5. Clean up (delete the workflow)

The Workflows APIs are generally available since Kibana 9.4.0.

Run this example:
    python examples/workflows_management.py
"""

import time

from utils import get_kibana_config

from kibana import Kibana

WORKFLOW_ID = "kbnpy-example-workflow"

WORKFLOW_YAML = f"""name: {WORKFLOW_ID}
description: kibana-py example workflow
enabled: true
tags:
  - kbnpy-example
triggers:
  - type: manual
steps:
  - name: log_step
    type: console
    with:
      message: "hello from kibana-py"
"""


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    created = False
    try:
        # 1. Create the workflow from its YAML definition
        workflow = client.workflows.create(id=WORKFLOW_ID, yaml=WORKFLOW_YAML).body
        created = True
        print(f"Created workflow {workflow['id']} (valid={workflow['valid']})")

        # 2. Get it by ID and find it via search
        fetched = client.workflows.get(id=WORKFLOW_ID).body
        print(f"Fetched workflow: name={fetched['name']} enabled={fetched['enabled']}")

        found = client.workflows.get_all(query=WORKFLOW_ID, size=10).body
        print(f"Search found {found['total']} workflow(s)")

        # 3. Run it and poll the execution until it reaches a terminal status
        run = client.workflows.run(id=WORKFLOW_ID, inputs={}).body
        execution_id = run["workflowExecutionId"]
        print(f"Started execution {execution_id}")

        status = "pending"
        for _ in range(60):
            execution = client.workflows.get_execution(execution_id=execution_id).body
            status = execution["status"]
            if status in ("completed", "failed", "cancelled", "timed_out"):
                break
            time.sleep(1)
        print(f"Execution finished with status: {status}")

        # 4. Read the execution logs (indexed asynchronously — poll briefly)
        for _ in range(30):
            logs = client.workflows.get_execution_logs(
                execution_id=execution_id, sort_order="asc"
            ).body
            if logs["total"] >= 1:
                break
            time.sleep(1)
        for entry in logs["logs"]:
            if entry["level"] == "info":
                print(f"  [{entry['level']}] {entry['message']}")
    finally:
        # 5. Clean up
        if created:
            client.workflows.delete(id=WORKFLOW_ID, force=True)
            print(f"Deleted workflow {WORKFLOW_ID}")
        client.close()


if __name__ == "__main__":
    main()
