TaskManagerClient
=================

Client for the Kibana Task Manager API.

Task Manager is the Kibana service that runs background tasks such as
alerting rules, actions, reporting jobs, and telemetry collection. This API
exposes the health and performance statistics of the task manager on the
Kibana instance that serves the request.

The Task Manager API is not space-scoped: it always operates at the Kibana
instance level.

.. currentmodule:: kibana._sync.client.task_manager

.. autoclass:: TaskManagerClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Checking Task Manager Health

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      health = client.task_manager.health()

      # Overall status: OK, warn, or error
      print(f"Task manager status: {health.body['status']}")

      # Drill into the individual stat sections: configuration,
      # runtime, workload, capacity_estimation
      stats = health.body["stats"]
      for section, report in stats.items():
          print(f"{section}: {report['status']}")

   .. rubric:: Monitoring Integration

   The health endpoint is designed for monitoring systems and health checks:

   .. code-block:: python

      def check_task_manager(client):
          health = client.task_manager.health()
          status = health.body["status"]
          if status != "OK":
              print(f"ALERT: task manager status is {status}")
          return status == "OK"

AsyncTaskManagerClient
----------------------

Asynchronous version of the TaskManagerClient for use with async/await
syntax.

.. autoclass:: kibana._async.client.task_manager.AsyncTaskManagerClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncTaskManagerClient provides the same methods as TaskManagerClient
   but all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              health = await client.task_manager.health()
              print(health.body["status"])

      asyncio.run(main())
