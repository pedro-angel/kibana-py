AsyncKibana Client
==================

The main asynchronous client for interacting with Kibana's REST API using async/await syntax.

.. currentmodule:: kibana

.. autoclass:: AsyncKibana
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__, __aenter__, __aexit__

   .. rubric:: Initialization

   The AsyncKibana client can be initialized with the same options as the synchronous client:

   .. code-block:: python

      from kibana import AsyncKibana

      # Basic initialization with URL
      client = AsyncKibana("http://localhost:5601")

      # With API key authentication
      client = AsyncKibana(
          "http://localhost:5601",
          api_key="your_api_key"
      )

      # With basic authentication
      client = AsyncKibana(
          "http://localhost:5601",
          basic_auth=("username", "password")
      )

   .. rubric:: Async Context Manager Usage

   The async client should be used as an async context manager to ensure proper resource cleanup:

   .. code-block:: python

      async with AsyncKibana("http://localhost:5601") as client:
          # Use the client with await
          status = await client.status.get_status()
          print(status.body["status"]["overall"]["level"])
      # Client is automatically closed

   .. rubric:: Concurrent Operations

   The async client enables concurrent operations for improved performance:

   .. code-block:: python

      import asyncio
      from kibana import AsyncKibana

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Execute multiple operations concurrently
              results = await asyncio.gather(
                  client.actions.get_all(),
                  client.spaces.get_all(),
                  client.status.get_status()
              )
              actions, spaces, status = results

      asyncio.run(main())

   .. rubric:: Namespace Clients

   The AsyncKibana client provides access to various API namespaces through properties:

   - :attr:`~AsyncKibana.actions` - Async Actions API for managing connectors
   - :attr:`~AsyncKibana.spaces` - Async Spaces API for managing Kibana Spaces
   - :attr:`~AsyncKibana.saved_objects` - Async Saved Objects API for managing saved objects
   - :attr:`~AsyncKibana.status` - Async Status API for monitoring server health

   All namespace client methods are async and must be awaited.

   .. rubric:: Space-Scoped Operations

   Create a space-scoped async client for operations within a specific space:

   .. code-block:: python

      # Create space-scoped client with validation
      marketing_client = client.space("marketing")

      # All operations are automatically scoped to the "marketing" space
      connector = await marketing_client.actions.create(
          name="Marketing Webhook",
          connector_type_id=".webhook",
          config={"url": "https://example.com/webhook"}
      )

      # Create space-scoped client without validation (for performance)
      fast_client = client.space("marketing", validate=False)

AsyncSpaceScopedKibana
----------------------

A space-scoped async client that automatically operates within a specific space context.

.. autoclass:: kibana._async.client.AsyncSpaceScopedKibana
   :members:
   :show-inheritance:
   :special-members: __init__, __aenter__, __aexit__

   .. rubric:: Usage

   Space-scoped async clients are created using the :meth:`AsyncKibana.space` method:

   .. code-block:: python

      # Create space-scoped client
      marketing_client = client.space("marketing")

      # All operations inherit the space context and must be awaited
      connector = await marketing_client.actions.create(
          name="Test Connector",
          connector_type_id=".index",
          config={"index": "test"}
      )

      # The connector is created in the "marketing" space
      # No need to pass space_id parameter

   .. rubric:: Async Context Manager

   Space-scoped async clients can also be used as async context managers:

   .. code-block:: python

      async with client.space("marketing") as marketing_client:
          # Perform operations in the marketing space
          connector = await marketing_client.actions.create(
              name="Test Connector",
              connector_type_id=".index",
              config={"index": "test"}
          )
      # Client is automatically closed

   .. rubric:: Validation

   By default, space-scoped clients validate that the space exists. For async clients,
   validation happens on first use rather than at creation time:

   .. code-block:: python

      # With validation (default) - validated on first operation
      client_with_validation = client.space("marketing")

      # Without validation (faster, but may fail on operations if space doesn't exist)
      client_without_validation = client.space("marketing", validate=False)
