#!/usr/bin/env python3
"""
Security Timeline Management Example

This example shows the minimal code needed to:
1. Create a Security Timeline
2. Add an investigation note and pin an event to it
3. Export the Timeline as NDJSON
4. Clean up (delete the note and the Timeline)

Run this example:
    python examples/timeline_management.py
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

    timeline_id = None
    try:
        # 1. Create a Timeline
        created = client.timeline.create(
            timeline={
                "title": "kbnpy-example-investigation",
                "description": "Investigating suspicious logons",
                "dateRange": {
                    "start": "2026-07-01T00:00:00.000Z",
                    "end": "2026-07-02T00:00:00.000Z",
                },
            }
        )
        timeline_id = created.body["savedObjectId"]
        print(f"Created timeline {timeline_id} ({created.body['title']})")

        # 2a. Add an investigation note
        note = client.timeline.create_note(
            note={"timelineId": timeline_id, "note": "Check host-1 first"}
        )
        note_id = note.body["note"]["noteId"]
        print(f"Added note {note_id}: {note.body['note']['note']}")

        # 2b. Pin an event (its Elasticsearch document _id) to the Timeline
        pinned = client.timeline.pin_event(
            event_id="example-event-document-id", timeline_id=timeline_id
        )
        print(f"Pinned event as {pinned.body['pinnedEventId']}")

        # 3. Export the Timeline as NDJSON (one timeline per line)
        exported = client.timeline.export(
            file_name="timelines.ndjson", ids=[timeline_id]
        )
        print(f"Exported {len(list(exported))} timeline(s) as NDJSON")

        # 4a. Delete the note
        client.timeline.delete_notes(note_id=note_id)
        print(f"Deleted note {note_id}")
    finally:
        # 4b. Delete the Timeline (also removes its pinned events)
        if timeline_id is not None:
            client.timeline.delete(saved_object_ids=[timeline_id])
            print(f"Deleted timeline {timeline_id}")
        client.close()


if __name__ == "__main__":
    main()
