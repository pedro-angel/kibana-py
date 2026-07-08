DataViewsClient
===============

Client for the Kibana Data Views API.

Data views (formerly index patterns) tell Kibana which Elasticsearch indices,
data streams, and aliases to query. This client covers the full Kibana 9.4
data views surface: data view CRUD, field metadata updates, runtime field
management, the default data view, and saved object reference swapping.

All operations are space-aware: pass ``space_id`` to target a specific Kibana
space, or use ``client.space("my-space").data_views``.

.. currentmodule:: kibana._sync.client.data_views

.. autoclass:: DataViewsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Creating Data Views

   Create a data view with the :meth:`~DataViewsClient.create` method:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create a data view over an index pattern
      response = client.data_views.create(
          data_view={
              "title": "my-logs-*",
              "name": "My Logs",
              "timeFieldName": "@timestamp",
          }
      )

      view_id = response["data_view"]["id"]
      print(f"Created data view: {view_id}")

   .. rubric:: Retrieving Data Views

   .. code-block:: python

      # List all data views
      views = client.data_views.get_all()
      for view in views.body["data_view"]:
          print(view["id"], view.get("name") or view["title"])

      # Get a single data view
      view = client.data_views.get(view_id=view_id)
      print(view.body["data_view"]["title"])

   .. rubric:: Runtime Fields

   Manage runtime fields on a data view:

   .. code-block:: python

      # Add a runtime field
      client.data_views.create_runtime_field(
          view_id=view_id,
          name="hour_of_day",
          runtime_field={
              "type": "long",
              "script": {
                  "source": "emit(doc['@timestamp'].value.getHour())"
              },
          },
      )

      # Read it back
      field = client.data_views.get_runtime_field(
          view_id=view_id, name="hour_of_day"
      )

      # Update or delete it
      client.data_views.update_runtime_field(
          view_id=view_id,
          name="hour_of_day",
          runtime_field={
              "script": {
                  "source": "emit(doc['@timestamp'].value.getHour() + 1)"
              }
          },
      )
      client.data_views.delete_runtime_field(
          view_id=view_id, name="hour_of_day"
      )

   .. rubric:: Default Data View

   .. code-block:: python

      # Get the current default data view ID
      default = client.data_views.get_default()
      print(default.body["data_view_id"])

      # Set the default data view
      client.data_views.set_default(data_view_id=view_id)

   .. rubric:: Deleting Data Views

   .. code-block:: python

      client.data_views.delete(view_id=view_id)

   .. warning::
      Deleting a data view is a permanent operation and cannot be undone.

AsyncDataViewsClient
--------------------

Asynchronous version of the DataViewsClient for use with async/await syntax.

.. autoclass:: kibana._async.client.data_views.AsyncDataViewsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncDataViewsClient provides the same methods as DataViewsClient but
   all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create a data view (async)
              response = await client.data_views.create(
                  data_view={
                      "title": "async-logs-*",
                      "timeFieldName": "@timestamp",
                  }
              )
              view_id = response["data_view"]["id"]

              # List all data views (async)
              views = await client.data_views.get_all()

              # Delete (async)
              await client.data_views.delete(view_id=view_id)

      asyncio.run(main())
