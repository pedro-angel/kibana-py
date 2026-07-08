StreamsClient
=============

Client for the Kibana Streams API.

Streams provide a single-pane experience to manage log (and other) data in
Elasticsearch: routing (wired streams), processing pipelines, field mappings,
lifecycle, significant-events queries and linked attachments (dashboards,
rules, SLOs).

.. note::
   All Streams APIs are marked as **technical preview** in Kibana 9.4 and may
   change in future releases.

Streams must be enabled first (see :meth:`~StreamsClient.enable`); once
enabled, Kibana manages wired root streams (in 9.4 these are ``logs.ecs`` and
``logs.otel``) from which child streams can be forked.

Streams are space-scoped: every method accepts an optional ``space_id`` to
target a specific space.

.. currentmodule:: kibana._sync.client.streams

.. autoclass:: StreamsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Enabling Streams and Forking

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Enable streams, then fork a child stream from the ECS root
      client.streams.enable()
      client.streams.fork(
          name="logs.ecs",
          stream_name="logs.ecs.myapp",
          where={"field": "service.name", "eq": "myapp"},
      )

      # List all streams
      streams = client.streams.get_all()
      print([s["name"] for s in streams.body["streams"]])

      # Disable streams again (removes stream management)
      client.streams.disable()

   .. rubric:: Reading and Updating Stream Definitions

   .. code-block:: python

      # Get a stream definition (routing, processing, lifecycle, ...)
      stream = client.streams.get(name="logs.ecs.myapp")

      # Get only the ingest configuration
      ingest = client.streams.get_ingest(name="logs.ecs.myapp")

      # Delete a stream
      client.streams.delete(name="logs.ecs.myapp")

   .. rubric:: Significant Events Queries

   .. code-block:: python

      # Add a significant-events query (ES|QL) to a stream
      client.streams.upsert_query(
          name="logs.ecs.myapp",
          query_id="failed-logins",
          title="Failed logins",
          esql='FROM logs.ecs.myapp | WHERE event.outcome == "failure"',
      )

      # List queries attached to a stream
      queries = client.streams.get_queries(name="logs.ecs.myapp")

      # Read significant events
      events = client.streams.get_significant_events(
          name="logs.ecs.myapp",
          from_="2026-07-01T00:00:00.000Z",
          to="2026-07-03T00:00:00.000Z",
          bucket_size="1h",
      )

   .. rubric:: Attachments

   Link Kibana assets (dashboards, rules, SLOs) to a stream:

   .. code-block:: python

      # Link a dashboard to a stream
      client.streams.link_attachment(
          name="logs.ecs.myapp",
          attachment_id="my-dashboard-id",
          attachment_type="dashboard",
      )

      # List attachments
      attachments = client.streams.get_attachments(name="logs.ecs.myapp")

      # Unlink it again
      client.streams.unlink_attachment(
          name="logs.ecs.myapp",
          attachment_id="my-dashboard-id",
          attachment_type="dashboard",
      )

AsyncStreamsClient
------------------

Asynchronous version of the StreamsClient for use with async/await syntax.

.. autoclass:: kibana._async.client.streams.AsyncStreamsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncStreamsClient provides the same methods as StreamsClient but all
   methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Enable streams (async)
              await client.streams.enable()

              # List streams (async)
              streams = await client.streams.get_all()
              print([s["name"] for s in streams.body["streams"]])

      asyncio.run(main())
