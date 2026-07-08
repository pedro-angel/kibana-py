OsqueryClient
=============

Client for the Kibana Security Osquery API.

Osquery lets you query hosts like a database using SQL. Kibana's Osquery
Manager integration runs queries on Elastic Agents and stores the results in
Elasticsearch. The API manages three resource types: **packs** (named sets of
queries scheduled on agent policies), **saved queries** (reusable single
queries), and **live queries** (one-off queries dispatched to a selection of
agents).

Osquery resources are space-aware: a pack or saved query created in one space
is not visible from another space. Every method accepts an optional
``space_id`` to target a specific space.

.. currentmodule:: kibana._sync.client.osquery

.. autoclass:: OsqueryClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Managing Packs

   A pack groups queries and schedules them on the agent policies it is
   assigned to:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create a pack with one scheduled query
      pack = client.osquery.create_pack(
          name="my_pack",
          description="Track host uptime",
          enabled=False,
          queries={
              "uptime": {"query": "select * from uptime;", "interval": 3600}
          },
      )
      pack_id = pack.body["data"]["saved_object_id"]

      # List, fetch, update and delete packs
      packs = client.osquery.find_packs(page=1, page_size=20)
      details = client.osquery.get_pack(id=pack_id)

      # Note: the server treats updates as replacements — send every
      # field you want to keep.
      client.osquery.update_pack(
          id=pack_id,
          name="my_pack",
          description="Track host uptime (updated)",
          enabled=False,
          queries={
              "uptime": {"query": "select * from uptime;", "interval": 600}
          },
      )
      client.osquery.delete_pack(id=pack_id)

   .. rubric:: Managing Saved Queries

   Saved queries are reusable SQL queries that can be run as live queries or
   added to packs:

   .. code-block:: python

      saved = client.osquery.create_saved_query(
          id="my_saved_query",
          query="select * from uptime;",
          interval="60",  # the server requires a string, not an integer
          description="Host uptime",
          ecs_mapping={"host.uptime": {"field": "total_seconds"}},
      )
      saved_object_id = saved.body["data"]["saved_object_id"]

      queries = client.osquery.find_saved_queries(page_size=100)
      details = client.osquery.get_saved_query(id=saved_object_id)

      # Updates are replacements too; `new_id` (the saved query name)
      # is always required by the server.
      client.osquery.update_saved_query(
          id=saved_object_id,
          new_id="my_saved_query",
          query="select * from uptime;",
          interval="120",
      )
      client.osquery.delete_saved_query(id=saved_object_id)

   .. rubric:: Running Live Queries

   Live queries are dispatched to agents immediately. They require at least
   one enrolled Elastic Agent running the Osquery Manager integration:

   .. code-block:: python

      live = client.osquery.create_live_query(
          query="select * from uptime;",
          agent_all=True,
          ecs_mapping={"host.uptime": {"field": "total_seconds"}},
      )
      live_query_id = live.body["data"]["action_id"]
      action_id = live.body["data"]["queries"][0]["action_id"]

      # Check the status and fetch per-query results
      details = client.osquery.get_live_query(id=live_query_id)
      results = client.osquery.get_live_query_results(
          id=live_query_id, action_id=action_id, page_size=100
      )

      # List past live queries
      history = client.osquery.find_live_queries(kuery="user_id:elastic")

AsyncOsqueryClient
------------------

Asynchronous version of the OsqueryClient for use with async/await syntax.

.. autoclass:: kibana._async.client.osquery.AsyncOsqueryClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncOsqueryClient provides the same methods as OsqueryClient but all
   methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create a saved query (async)
              saved = await client.osquery.create_saved_query(
                  id="my_async_saved_query",
                  query="select * from uptime;",
                  interval="60",
              )
              saved_object_id = saved.body["data"]["saved_object_id"]

              # List packs and saved queries (async)
              packs = await client.osquery.find_packs(page_size=20)
              queries = await client.osquery.find_saved_queries(page_size=20)

              # Clean up (async)
              await client.osquery.delete_saved_query(id=saved_object_id)

      asyncio.run(main())
