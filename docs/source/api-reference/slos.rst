SlosClient
==========

Client for the Kibana SLOs (Service Level Objectives) API.

SLOs let you set measurable targets (availability, latency, ...) for your
services based on Elasticsearch data and track error budgets against those
targets. The SLO APIs require an appropriate license (Platinum or trial).

All endpoints are space-scoped: the official API paths are rooted at
``/s/{spaceId}/api/observability/slos``. Every method therefore accepts
``space_id`` (``None`` targets the default space) and ``validate_spaces`` to
override space-existence validation per call.

.. currentmodule:: kibana._sync.client.slos

.. autoclass:: SlosClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Creating SLOs

   Create an SLO with the :meth:`~SlosClient.create` method:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create an SLO based on a custom KQL indicator
      slo = client.slos.create(
          name="my-service availability",
          description="99% of requests are good over 30 days",
          indicator={
              "type": "sli.kql.custom",
              "params": {
                  "index": "my-service-logs",
                  "good": "status: ok",
                  "total": "",
                  "timestampField": "@timestamp",
              },
          },
          time_window={"duration": "30d", "type": "rolling"},
          budgeting_method="occurrences",
          objective={"target": 0.99},
      )

      slo_id = slo.body["id"]

   .. rubric:: Finding and Retrieving SLOs

   .. code-block:: python

      # Get a single SLO (with its computed summary)
      slo = client.slos.get(slo_id=slo_id)

      # Find SLOs with a KQL query
      results = client.slos.find(kql_query="slo.name:my-service*")
      for slo in results.body["results"]:
          print(slo["name"], slo["summary"]["status"])

      # List SLO definitions
      definitions = client.slos.find_definitions(search="my-service*")

   .. rubric:: SLO Lifecycle

   .. code-block:: python

      # Disable and re-enable an SLO
      client.slos.disable(slo_id=slo_id)
      client.slos.enable(slo_id=slo_id)

      # Reset an SLO (recompute rollup data from scratch)
      client.slos.reset(slo_id=slo_id)

      # Delete an SLO
      client.slos.delete(slo_id=slo_id)

   .. rubric:: Bulk Operations

   .. code-block:: python

      # Bulk delete SLOs (asynchronous server-side task)
      task = client.slos.bulk_delete(slo_ids=[slo_id, "another-slo-id"])

      # Check the status of the bulk delete task
      status = client.slos.bulk_delete_status(task_id=task.body["taskId"])

AsyncSlosClient
---------------

Asynchronous version of the SlosClient for use with async/await syntax.

.. autoclass:: kibana._async.client.slos.AsyncSlosClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncSlosClient provides the same methods as SlosClient but all methods
   are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create an SLO (async)
              slo = await client.slos.create(
                  name="async availability",
                  description="Availability SLO created asynchronously",
                  indicator={
                      "type": "sli.kql.custom",
                      "params": {
                          "index": "my-service-logs",
                          "good": "status: ok",
                          "total": "",
                          "timestampField": "@timestamp",
                      },
                  },
                  time_window={"duration": "30d", "type": "rolling"},
                  budgeting_method="occurrences",
                  objective={"target": 0.99},
              )

              # Find SLOs (async)
              results = await client.slos.find()

              # Delete (async)
              await client.slos.delete(slo_id=slo.body["id"])

      asyncio.run(main())
