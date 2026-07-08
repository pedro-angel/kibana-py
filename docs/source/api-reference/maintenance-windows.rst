MaintenanceWindowsClient
========================

Client for the Kibana Maintenance Windows API.

A maintenance window suppresses rule notifications for a scheduled period of
time: alerts continue to be created, but their actions (notifications) are
not run while a maintenance window is active. Maintenance windows require a
Platinum or higher license.

Maintenance windows are space-scoped: a maintenance window created in one
space only affects rules in that space. Every method accepts an optional
``space_id`` to target a specific space.

.. currentmodule:: kibana._sync.client.maintenance_windows

.. autoclass:: MaintenanceWindowsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Creating Maintenance Windows

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create a one-hour maintenance window
      created = client.maintenance_windows.create(
          title="Weekend maintenance",
          schedule={
              "custom": {
                  "start": "2030-01-05T00:00:00.000Z",
                  "duration": "1h",
              }
          },
      )
      mw_id = created.body["id"]

   .. rubric:: Finding and Retrieving

   .. code-block:: python

      # Find maintenance windows
      results = client.maintenance_windows.find(status="upcoming")
      for mw in results.body["maintenanceWindows"]:
          print(mw["id"], mw["title"], mw["status"])

      # Get a single maintenance window
      mw = client.maintenance_windows.get(id=mw_id)

   .. rubric:: Updating, Archiving, and Deleting

   .. code-block:: python

      # Update the schedule
      client.maintenance_windows.update(
          id=mw_id,
          title="Weekend maintenance (extended)",
          schedule={
              "custom": {
                  "start": "2030-01-05T00:00:00.000Z",
                  "duration": "2h",
              }
          },
      )

      # Archive it once it is no longer needed
      client.maintenance_windows.archive(id=mw_id)

      # Or bring it back
      client.maintenance_windows.unarchive(id=mw_id)

      # Delete it
      client.maintenance_windows.delete(id=mw_id)

AsyncMaintenanceWindowsClient
-----------------------------

Asynchronous version of the MaintenanceWindowsClient for use with async/await
syntax.

.. autoclass:: kibana._async.client.maintenance_windows.AsyncMaintenanceWindowsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncMaintenanceWindowsClient provides the same methods as
   MaintenanceWindowsClient but all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create a maintenance window (async)
              created = await client.maintenance_windows.create(
                  title="Async maintenance",
                  schedule={
                      "custom": {
                          "start": "2030-01-05T00:00:00.000Z",
                          "duration": "1h",
                      }
                  },
              )

              # Archive and delete (async)
              await client.maintenance_windows.archive(
                  id=created.body["id"]
              )
              await client.maintenance_windows.delete(id=created.body["id"])

      asyncio.run(main())
