#!/usr/bin/env python3
"""
Streams Management Example

This example shows the minimal code needed to:
1. Enable streams (idempotent) and list the wired root streams
2. Fork a child stream off the ``logs.ecs`` root with a routing condition
3. Add a significant-events query and read the significant events
4. Export the stream's content pack (ZIP)
5. Clean up (delete the child stream, restore the enabled state)

The Streams APIs are a technical preview in Kibana 9.4.

Run this example:
    python examples/streams_management.py
"""

from datetime import UTC, datetime, timedelta

from utils import get_kibana_config

from kibana import Kibana
from kibana.exceptions import NotFoundError

ROOT = "logs.ecs"
CHILD = f"{ROOT}.kbnpyexample"


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    # Remember the prior state so we can restore it at the end
    try:
        client.streams.get(name=ROOT)
        was_enabled = True
    except NotFoundError:
        was_enabled = False

    try:
        # 1. Enable streams and list the wired roots
        client.streams.enable()
        streams = client.streams.get_all()
        print(f"Streams: {[s['name'] for s in streams.body['streams']]}")

        # 2. Fork a child stream: documents with service.name == "kbnpy-example"
        #    get routed from logs.ecs into the child
        client.streams.fork(
            name=ROOT,
            stream_name=CHILD,
            where={"field": "service.name", "eq": "kbnpy-example"},
        )
        print(f"Forked child stream {CHILD}")

        # 3. Add a significant-events query and read significant events
        esql = f'FROM {CHILD}, {CHILD}.* METADATA _id, _source | WHERE message LIKE "*error*"'
        client.streams.upsert_query(
            name=CHILD,
            query_id="kbnpy-example-errors",
            title="Error messages",
            esql=esql,
            description="Log lines mentioning errors",
        )
        # The time range must be ISO 8601 timestamps (relative "now-24h"
        # syntax is not accepted by this API)
        now = datetime.now(UTC)
        events = client.streams.get_significant_events(
            name=CHILD,
            from_=(now - timedelta(hours=24)).isoformat(),
            to=now.isoformat(),
            bucket_size="1h",
        )
        print(f"Significant-events queries: {len(events.body['significant_events'])}")

        # 4. Export the stream's content pack (a ZIP archive)
        exported = client.streams.export_content(
            name=CHILD,
            content_name="kbnpy-example-pack",
            description="Example content pack",
            version="1.0.0",
        )
        print(f"Exported content pack: {len(bytes(exported.body))} bytes (ZIP)")
    finally:
        # 5. Clean up: remove the child stream, restore the prior state
        try:
            client.streams.delete(name=CHILD)
            print(f"Deleted child stream {CHILD}")
        except NotFoundError:
            pass
        if not was_enabled:
            client.streams.disable()
            print("Disabled streams (restored prior state)")
        client.close()


if __name__ == "__main__":
    main()
