SavedObjectsClient
==================

Client for managing Kibana saved objects through the Saved Objects API.

Saved Objects in Kibana are entities like dashboards, visualizations, index patterns,
and other configuration items. This API provides methods to create, read, update,
and delete saved objects, as well as bulk operations and import/export functionality.

.. currentmodule:: kibana

.. autoclass:: SavedObjectsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Overview

   The SavedObjectsClient provides comprehensive methods for managing Kibana saved objects.
   Saved objects can be scoped to specific Kibana Spaces for multi-tenancy.

   .. rubric:: Creating Saved Objects

   Create a new saved object with the :meth:`~SavedObjectsClient.create` method:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601")

      # Create a dashboard
      dashboard = client.saved_objects.create(
          type="dashboard",
          attributes={
              "title": "My Dashboard",
              "description": "A sample dashboard"
          }
      )

      dashboard_id = dashboard.body["id"]
      print(f"Created dashboard: {dashboard_id}")

      # Create with a specific ID
      visualization = client.saved_objects.create(
          type="visualization",
          id="my-viz-id",
          attributes={
              "title": "My Visualization",
              "visState": "{}"
          }
      )

   .. rubric:: Saved Object Types

   Common saved object types include:

   - ``dashboard`` - Kibana dashboards
   - ``visualization`` - Visualizations
   - ``index-pattern`` - Index patterns
   - ``search`` - Saved searches
   - ``lens`` - Lens visualizations
   - ``map`` - Maps
   - ``canvas-workpad`` - Canvas workpads

   .. code-block:: python

      # Create an index pattern
      index_pattern = client.saved_objects.create(
          type="index-pattern",
          attributes={
              "title": "logs-*",
              "timeFieldName": "@timestamp"
          }
      )

      # Create a saved search
      search = client.saved_objects.create(
          type="search",
          attributes={
              "title": "Error Logs",
              "columns": ["message", "level"],
              "sort": [["@timestamp", "desc"]]
          }
      )

   .. rubric:: Retrieving Saved Objects

   Get saved objects by type and ID:

   .. code-block:: python

      # Get a specific saved object
      obj = client.saved_objects.get(
          type="dashboard",
          id=dashboard_id
      )

      print(f"Title: {obj.body['attributes']['title']}")

      # Get multiple saved objects at once
      objects = client.saved_objects.bulk_get(
          objects=[
              {"type": "dashboard", "id": "dashboard-1"},
              {"type": "visualization", "id": "viz-1"},
              {"type": "index-pattern", "id": "pattern-1"}
          ]
      )

   .. rubric:: Updating Saved Objects

   Update saved object attributes:

   .. code-block:: python

      # Update a dashboard
      updated = client.saved_objects.update(
          type="dashboard",
          id=dashboard_id,
          attributes={
              "title": "Updated Dashboard Title",
              "description": "Updated description"
          }
      )

      # Partial update (only specified attributes are updated)
      updated = client.saved_objects.update(
          type="dashboard",
          id=dashboard_id,
          attributes={
              "description": "New description only"
          }
      )

   .. rubric:: Deleting Saved Objects

   Delete saved objects:

   .. code-block:: python

      # Delete a single saved object
      client.saved_objects.delete(
          type="dashboard",
          id=dashboard_id
      )

      # Bulk delete multiple saved objects
      result = client.saved_objects.bulk_delete(
          objects=[
              {"type": "dashboard", "id": "dashboard-1"},
              {"type": "visualization", "id": "viz-1"}
          ]
      )

   .. rubric:: Finding Saved Objects

   Search for saved objects with filters:

   .. code-block:: python

      # Find all dashboards
      dashboards = client.saved_objects.find(
          type="dashboard"
      )

      for dashboard in dashboards.body["saved_objects"]:
          print(f"{dashboard['id']}: {dashboard['attributes']['title']}")

      # Find with search query
      results = client.saved_objects.find(
          type="dashboard",
          search="error",
          search_fields=["title", "description"]
      )

      # Find with pagination
      results = client.saved_objects.find(
          type="visualization",
          page=1,
          per_page=20
      )

   .. rubric:: Bulk Operations

   Perform bulk create and update operations:

   .. code-block:: python

      # Bulk create multiple saved objects
      result = client.saved_objects.bulk_create(
          objects=[
              {
                  "type": "dashboard",
                  "attributes": {"title": "Dashboard 1"}
              },
              {
                  "type": "dashboard",
                  "attributes": {"title": "Dashboard 2"}
              },
              {
                  "type": "visualization",
                  "attributes": {"title": "Viz 1"}
              }
          ]
      )

      # Bulk update
      result = client.saved_objects.bulk_update(
          objects=[
              {
                  "type": "dashboard",
                  "id": "dashboard-1",
                  "attributes": {"title": "Updated Dashboard 1"}
              },
              {
                  "type": "dashboard",
                  "id": "dashboard-2",
                  "attributes": {"title": "Updated Dashboard 2"}
              }
          ]
      )

   .. rubric:: Export and Import

   Export and import saved objects:

   .. code-block:: python

      # Export saved objects
      export_data = client.saved_objects.export(
          objects=[
              {"type": "dashboard", "id": "dashboard-1"},
              {"type": "visualization", "id": "viz-1"}
          ]
      )

      # Export all objects of a type
      export_data = client.saved_objects.export(
          type="dashboard"
      )

      # Import saved objects
      result = client.saved_objects.import_objects(
          file=export_data,
          overwrite=True
      )

   .. rubric:: Space-Scoped Operations

   Work with saved objects in specific spaces:

   .. code-block:: python

      # Create saved object in a specific space
      dashboard = client.saved_objects.create(
          type="dashboard",
          attributes={"title": "Marketing Dashboard"},
          space_id="marketing"
      )

      # Or use a space-scoped client
      marketing_client = client.space("marketing")
      dashboard = marketing_client.saved_objects.create(
          type="dashboard",
          attributes={"title": "Marketing Dashboard"}
      )

      # Find saved objects in a specific space
      results = client.saved_objects.find(
          type="dashboard",
          space_id="marketing"
      )

   .. rubric:: Error Handling

   Handle common errors when working with saved objects:

   .. code-block:: python

      from kibana.exceptions import (
          NotFoundError,
          ConflictError,
          BadRequestError,
          SpaceNotFoundError
      )

      try:
          obj = client.saved_objects.create(
              type="dashboard",
              id="my-dashboard",
              attributes={"title": "My Dashboard"},
              space_id="marketing"
          )
      except SpaceNotFoundError as e:
          print(f"Space not found: {e.space_id}")
      except ConflictError as e:
          print(f"Object already exists: {e.message}")
      except BadRequestError as e:
          print(f"Invalid attributes: {e.message}")

      try:
          obj = client.saved_objects.get(
              type="dashboard",
              id="nonexistent"
          )
      except NotFoundError as e:
          print(f"Object not found: {e.message}")

AsyncSavedObjectsClient
-----------------------

Asynchronous version of the SavedObjectsClient for use with async/await syntax.

.. autoclass:: kibana._async.client.saved_objects.AsyncSavedObjectsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncSavedObjectsClient provides the same methods as SavedObjectsClient but all
   methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create saved object (async)
              dashboard = await client.saved_objects.create(
                  type="dashboard",
                  attributes={"title": "Async Dashboard"}
              )

              # Get saved object (async)
              obj = await client.saved_objects.get(
                  type="dashboard",
                  id=dashboard.body["id"]
              )

              # Find saved objects (async)
              results = await client.saved_objects.find(
                  type="dashboard"
              )

              # Delete saved object (async)
              await client.saved_objects.delete(
                  type="dashboard",
                  id=dashboard.body["id"]
              )

      asyncio.run(main())

   .. rubric:: Concurrent Operations

   Perform multiple saved object operations concurrently:

   .. code-block:: python

      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create multiple saved objects concurrently
              objects = await asyncio.gather(
                  client.saved_objects.create(
                      type="dashboard",
                      attributes={"title": "Dashboard 1"}
                  ),
                  client.saved_objects.create(
                      type="dashboard",
                      attributes={"title": "Dashboard 2"}
                  ),
                  client.saved_objects.create(
                      type="visualization",
                      attributes={"title": "Viz 1"}
                  )
              )

              print(f"Created {len(objects)} saved objects")

              # Retrieve multiple objects concurrently
              retrieved = await asyncio.gather(
                  client.saved_objects.get(
                      type="dashboard",
                      id=objects[0].body["id"]
                  ),
                  client.saved_objects.get(
                      type="dashboard",
                      id=objects[1].body["id"]
                  ),
                  client.saved_objects.get(
                      type="visualization",
                      id=objects[2].body["id"]
                  )
              )

      asyncio.run(main())
