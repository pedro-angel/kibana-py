TimelineClient
==============

Client for the Kibana Security Timeline API.

Timelines are the Security Solution's workspace for investigating events and
alerts. The Timeline APIs cover Timeline and Timeline-template CRUD, per-user
draft Timelines, favorites, NDJSON export/import, prepackaged-Timeline
installation, Timeline copies, investigation notes (``/api/note``) and pinned
events (``/api/pinned_event``).

Timelines, notes and pinned events are space-scoped saved objects: a Timeline
created in one space is not visible from another space. Every method accepts
an optional ``space_id`` to target a specific space.

.. currentmodule:: kibana._sync.client.timeline

.. autoclass:: TimelineClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Creating and Managing Timelines

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create a Timeline
      created = client.timeline.create(
          timeline={
              "title": "Suspicious logons",
              "description": "Investigating a suspicious logon burst",
              "dateRange": {
                  "start": "2026-07-01T00:00:00.000Z",
                  "end": "2026-07-02T00:00:00.000Z",
              },
          }
      )
      timeline_id = created.body["savedObjectId"]

      # Get, update, list and delete
      fetched = client.timeline.get(id=timeline_id)
      client.timeline.update(
          timeline_id=timeline_id,
          version=fetched.body["version"],
          timeline={"title": "Suspicious logons (triaged)"},
      )
      found = client.timeline.get_all(search="Suspicious", page_size=10)
      client.timeline.delete(saved_object_ids=[timeline_id])

   .. rubric:: Notes and Pinned Events

   .. code-block:: python

      # Attach an investigation note to the Timeline
      note = client.timeline.create_note(
          note={"timelineId": timeline_id, "note": "Check host-1 first"}
      )
      note_id = note.body["note"]["noteId"]

      # Fetch the Timeline's notes, then delete them
      notes = client.timeline.get_notes(saved_object_ids=timeline_id)
      client.timeline.delete_notes(note_id=note_id)

      # Pin an event (by its document _id) and unpin it again
      pinned = client.timeline.pin_event(
          event_id="d3a1d35a3e84...", timeline_id=timeline_id
      )
      client.timeline.unpin_event(
          event_id="d3a1d35a3e84...",
          timeline_id=timeline_id,
          pinned_event_id=pinned.body["pinnedEventId"],
      )

   .. rubric:: Export and Import

   .. code-block:: python

      # Export Timelines as NDJSON (the parsed body is a list of dicts)
      exported = client.timeline.export(
          file_name="timelines.ndjson", ids=[timeline_id]
      )

      # Import them back (multipart/form-data upload)
      result = client.timeline.import_timelines(file=list(exported))
      print(result.body["success"], result.body["timelines_installed"])

   .. rubric:: Drafts, Favorites, Copies and Prepackaged Timelines

   .. code-block:: python

      # Per-user draft Timeline
      draft = client.timeline.get_draft(timeline_type="default")
      client.timeline.clean_draft(timeline_type="default")

      # Toggle the favorite mark for the current user
      client.timeline.favorite(timeline_id=timeline_id, timeline_type="default")

      # Copy a Timeline (including notes and pinned events)
      copy = client.timeline.copy(
          timeline_id_to_copy=timeline_id, timeline={"title": "Copy"}
      )

      # Install/update the Elastic prepackaged Timeline templates
      client.timeline.install_prepackaged()

AsyncTimelineClient
-------------------

Asynchronous version of the TimelineClient for use with async/await syntax.

.. autoclass:: kibana._async.client.timeline.AsyncTimelineClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncTimelineClient provides the same methods as TimelineClient but
   all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create a Timeline (async)
              created = await client.timeline.create(
                  timeline={"title": "Async investigation"}
              )
              timeline_id = created.body["savedObjectId"]

              # Attach a note (async)
              await client.timeline.create_note(
                  note={"timelineId": timeline_id, "note": "async note"}
              )

              # Clean up (async)
              await client.timeline.delete(saved_object_ids=[timeline_id])

      asyncio.run(main())
