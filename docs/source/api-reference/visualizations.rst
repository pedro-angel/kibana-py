VisualizationsClient
====================

Client for the Kibana Visualizations HTTP API.

.. note::
   The Visualizations HTTP API is in **technical preview** (added in Kibana
   9.4.0) and may change in future releases.

Manages Lens visualizations (metric, XY, pie, gauge, heatmap, tag cloud,
region map, datatable, mosaic, treemap, waffle, legacy metric) through the
``/api/visualizations`` endpoints. Responses use the same ``{id, data, meta}``
envelope as the :doc:`Dashboards API <dashboards>`: ``data`` holds the chart
configuration and ``meta`` holds timestamps and version information.

All operations support Kibana spaces via the ``space_id`` parameter or a
space-scoped client created with ``client.space("my-space")``.

.. currentmodule:: kibana._sync.client.visualizations

.. autoclass:: VisualizationsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Creating Visualizations

   Create a Lens visualization with the :meth:`~VisualizationsClient.create`
   method. The ``data`` object carries the chart type and configuration:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create a metric visualization
      created = client.visualizations.create(
          data={
              "type": "metric",
              "title": "Total log documents",
              "data_source": {
                  "type": "data_view_spec",
                  "index_pattern": "logs-*",
              },
              "query": {"expression": "", "language": "kql"},
              "metrics": [{"type": "primary", "operation": "count"}],
          }
      )

      viz_id = created.body["id"]
      print(f"Created visualization: {viz_id}")

   .. rubric:: Retrieving and Searching

   .. code-block:: python

      # Get a visualization by ID
      viz = client.visualizations.get(id=viz_id)
      print(viz.body["data"]["title"])

      # Search visualizations by title
      results = client.visualizations.get_all(query="Total log*")
      print(f"Total matches: {results.body['meta']['total']}")

   .. rubric:: Updating and Deleting

   .. code-block:: python

      # Replace the visualization configuration
      client.visualizations.update(
          id=viz_id,
          data={
              "type": "metric",
              "title": "Total log documents (updated)",
              "data_source": {
                  "type": "data_view_spec",
                  "index_pattern": "logs-*",
              },
              "query": {"expression": "", "language": "kql"},
              "metrics": [{"type": "primary", "operation": "count"}],
          },
      )

      # Delete the visualization
      client.visualizations.delete(id=viz_id)

   .. rubric:: Space-Scoped Visualizations

   .. code-block:: python

      # Target a space explicitly
      viz = client.visualizations.create(
          data={"type": "metric", "title": "Marketing metric"},
          space_id="marketing",
      )

      # Or use a space-scoped client
      marketing = client.space("marketing")
      viz = marketing.visualizations.get_all()

AsyncVisualizationsClient
-------------------------

Asynchronous version of the VisualizationsClient for use with async/await
syntax.

.. autoclass:: kibana._async.client.visualizations.AsyncVisualizationsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncVisualizationsClient provides the same methods as
   VisualizationsClient but all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create a visualization (async)
              created = await client.visualizations.create(
                  data={
                      "type": "metric",
                      "title": "Async metric",
                      "data_source": {
                          "type": "data_view_spec",
                          "index_pattern": "logs-*",
                      },
                      "query": {"expression": "", "language": "kql"},
                      "metrics": [{"type": "primary", "operation": "count"}],
                  }
              )

              # Search visualizations (async)
              results = await client.visualizations.get_all(query="Async*")

              # Delete (async)
              await client.visualizations.delete(id=created.body["id"])

      asyncio.run(main())
