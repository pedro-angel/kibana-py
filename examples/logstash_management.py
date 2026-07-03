#!/usr/bin/env python3
"""
Logstash Centralized Pipeline Management Example

Demonstrates the Kibana Logstash pipeline management API (Technical Preview):
1. Create a centrally-managed pipeline
2. Read it back
3. Update it (PUT is an upsert)
4. List all pipelines
5. Delete it

Pipelines are stored in Elasticsearch, so no running Logstash instance is
required to manage the definitions.

Run this example:
    python examples/logstash_management.py
"""

from utils import get_kibana_config

from kibana import Kibana

PIPELINE_ID = "kbnpy-logstash-example-pipeline"


def main():
    # Build a client from the automatic example configuration
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    try:
        # 1. Create a pipeline (204 No Content on success)
        print(f"Creating pipeline '{PIPELINE_ID}'...")
        client.logstash.create_or_update(
            id=PIPELINE_ID,
            pipeline="input { stdin {} } output { stdout {} }",
            description="Example pipeline created by kibana-py",
            settings={"queue.type": "memory", "pipeline.workers": 1},
        )
        print("Pipeline created")

        # 2. Read it back
        pipeline = client.logstash.get(id=PIPELINE_ID).body
        print(f"Fetched pipeline: {pipeline['id']}")
        print(f"  description: {pipeline.get('description', '')}")
        print(f"  definition:  {pipeline['pipeline']}")
        print(f"  settings:    {pipeline.get('settings', {})}")

        # 3. Update the same pipeline (upsert on the same ID)
        print("Updating pipeline definition...")
        client.logstash.create_or_update(
            id=PIPELINE_ID,
            pipeline="input { generator { count => 1 } } output { stdout {} }",
            description="Example pipeline (updated)",
        )
        updated = client.logstash.get(id=PIPELINE_ID).body
        print(f"Updated description: {updated.get('description', '')}")

        # 4. List all pipelines
        pipelines = client.logstash.get_all().body["pipelines"]
        print(f"Found {len(pipelines)} pipeline(s):")
        for entry in pipelines:
            print(f"  - {entry['id']} (last modified: {entry.get('last_modified')})")

    finally:
        # 5. Clean up: delete the example pipeline
        try:
            client.logstash.delete(id=PIPELINE_ID)
            print(f"Deleted pipeline '{PIPELINE_ID}'")
        except Exception as e:
            print(f"Cleanup failed for '{PIPELINE_ID}': {e}")
        client.close()


if __name__ == "__main__":
    main()
