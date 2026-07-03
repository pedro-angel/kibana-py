LogstashClient
==============

Client for the Kibana Logstash Configuration Management API.

Manage centrally-managed Logstash pipelines that are stored in Elasticsearch
and distributed to Logstash instances configured with ``xpack.management``
(centralized pipeline management). A running Logstash instance is not
required to create, read, update, or delete pipeline definitions.

.. note::
   All endpoints in this namespace are in **technical preview** in Kibana 9.4
   and are not space-scoped.

Required privileges: the ``logstash_admin`` built-in role (or a customized
Logstash writer role) for write operations, and the ``logstash_admin``
built-in role (or a customized Logstash reader role) for read operations.

.. currentmodule:: kibana._sync.client.logstash

.. autoclass:: LogstashClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Managing Pipelines

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create (or replace) a pipeline
      client.logstash.create_or_update(
          id="hello-world",
          pipeline="input { stdin {} } output { stdout {} }",
          description="Just a simple pipeline",
      )

      # List all pipelines
      for p in client.logstash.get_all().body["pipelines"]:
          print(p["id"])

      # Get a single pipeline (includes the pipeline definition)
      pipeline = client.logstash.get(id="hello-world")
      print(pipeline.body["pipeline"])

      # Delete the pipeline
      client.logstash.delete(id="hello-world")

   .. rubric:: Pipeline Settings

   Pipelines accept optional Logstash settings (worker counts, batch sizes,
   queue configuration):

   .. code-block:: python

      client.logstash.create_or_update(
          id="tuned-pipeline",
          pipeline="input { stdin {} } output { stdout {} }",
          settings={
              "pipeline.workers": 2,
              "pipeline.batch.size": 250,
              "queue.type": "persisted",
          },
      )

AsyncLogstashClient
-------------------

Asynchronous version of the LogstashClient for use with async/await syntax.

.. autoclass:: kibana._async.client.logstash.AsyncLogstashClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncLogstashClient provides the same methods as LogstashClient but all
   methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create a pipeline (async)
              await client.logstash.create_or_update(
                  id="async-pipeline",
                  pipeline="input { stdin {} } output { stdout {} }",
              )

              # List pipelines (async)
              pipelines = await client.logstash.get_all()

              # Delete (async)
              await client.logstash.delete(id="async-pipeline")

      asyncio.run(main())
