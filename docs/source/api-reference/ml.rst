MlClient
========

Client for the Kibana Machine Learning API.

Provides access to the machine learning saved objects APIs, which keep Kibana
saved objects in sync with machine learning jobs and trained models, and
manage the Kibana spaces those objects belong to.

All operations are space-scoped: pass ``space_id`` to target a specific
Kibana space, or omit it to target the default space.

.. currentmodule:: kibana._sync.client.ml

.. autoclass:: MlClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Syncing Saved Objects

   Synchronize Kibana saved objects for machine learning jobs and trained
   models with :meth:`~MlClient.sync`:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Simulate first to see what would change
      result = client.ml.sync(simulate=True)
      print(result.body["savedObjectsCreated"])

      # Then run the sync for real
      result = client.ml.sync()

   .. rubric:: Managing Job and Model Spaces

   Move machine learning jobs and trained models between Kibana spaces:

   .. code-block:: python

      # Add anomaly detection jobs to a space, remove them from another
      client.ml.update_jobs_spaces(
          job_ids=["my-job"],
          job_type="anomaly-detector",
          spaces_to_add=["marketing"],
          spaces_to_remove=["default"],
      )

      # Same for trained models
      client.ml.update_trained_models_spaces(
          model_ids=["my-model"],
          spaces_to_add=["marketing"],
          spaces_to_remove=[],
      )

AsyncMlClient
-------------

Asynchronous version of the MlClient for use with async/await syntax.

.. autoclass:: kibana._async.client.ml.AsyncMlClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncMlClient provides the same methods as MlClient but all methods are
   async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Simulate a sync (async)
              result = await client.ml.sync(simulate=True)
              print(result.body)

      asyncio.run(main())
