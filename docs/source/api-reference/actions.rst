ActionsClient
=============

Client for managing Kibana action connectors through the Actions API.

Actions (also known as connectors) enable integration with external systems for alerting,
notifications, and automation workflows in Kibana.

.. currentmodule:: kibana

.. autoclass:: ActionsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Overview

   The ActionsClient provides methods to create, retrieve, update, delete, and execute
   action connectors. Connectors can be scoped to specific Kibana Spaces for multi-tenancy.

   .. rubric:: Creating Connectors

   Create a new connector with the :meth:`~ActionsClient.create` method:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601")

      # Create an index connector
      connector = client.actions.create(
          name="My Index Connector",
          connector_type_id=".index",
          config={
              "index": "my-index",
              "executionTimeField": "@timestamp"
          }
      )

      connector_id = connector.body["id"]
      print(f"Created connector: {connector_id}")

   .. rubric:: Space-Scoped Connectors

   Connectors can be created and managed within specific Kibana Spaces:

   .. code-block:: python

      # Create connector in a specific space
      connector = client.actions.create(
          name="Marketing Webhook",
          connector_type_id=".webhook",
          config={"url": "https://marketing.example.com/webhook"},
          space_id="marketing"
      )

      # Or use a space-scoped client
      marketing_client = client.space("marketing")
      connector = marketing_client.actions.create(
          name="Marketing Webhook",
          connector_type_id=".webhook",
          config={"url": "https://marketing.example.com/webhook"}
      )

   .. rubric:: Listing Connectors

   Retrieve all connectors or list available connector types:

   .. code-block:: python

      # Get all connectors
      connectors = client.actions.get_all()
      for connector in connectors.body:
          print(f"{connector['name']}: {connector['connector_type_id']}")

      # List available connector types
      types = client.actions.list_types()
      for connector_type in types.body:
          print(f"{connector_type['id']}: {connector_type['name']}")

   .. rubric:: Executing Connectors

   Execute a connector with specific parameters:

   .. code-block:: python

      # Execute a webhook connector
      result = client.actions.execute(
          id=connector_id,
          params={
              "body": '{"message": "Alert triggered!"}'
          }
      )

      print(f"Execution status: {result.body['status']}")

   .. rubric:: Updating and Deleting

   Update connector configuration or delete connectors:

   .. code-block:: python

      # Update connector
      updated = client.actions.update(
          id=connector_id,
          name="Updated Connector Name",
          config={"url": "https://new-url.example.com/webhook"}
      )

      # Delete connector
      client.actions.delete(id=connector_id)

   .. rubric:: Error Handling

   Handle common errors when working with connectors:

   .. code-block:: python

      from kibana.exceptions import (
          NotFoundError,
          ConflictError,
          BadRequestError,
          SpaceNotFoundError
      )

      try:
          connector = client.actions.create(
              name="Test Connector",
              connector_type_id=".webhook",
              config={"url": "https://example.com/webhook"},
              space_id="marketing"
          )
      except SpaceNotFoundError as e:
          print(f"Space not found: {e.space_id}")
      except BadRequestError as e:
          print(f"Invalid configuration: {e.message}")
      except ConflictError as e:
          print(f"Connector already exists: {e.message}")

AsyncActionsClient
------------------

Asynchronous version of the ActionsClient for use with async/await syntax.

.. autoclass:: kibana._async.client.actions.AsyncActionsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncActionsClient provides the same methods as ActionsClient but all methods
   are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create connector (async)
              connector = await client.actions.create(
                  name="Async Webhook",
                  connector_type_id=".webhook",
                  config={"url": "https://example.com/webhook"}
              )

              # Get all connectors (async)
              connectors = await client.actions.get_all()

              # Execute connector (async)
              result = await client.actions.execute(
                  id=connector.body["id"],
                  params={"body": '{"message": "Test"}'}
              )

      asyncio.run(main())

   .. rubric:: Concurrent Operations

   Perform multiple connector operations concurrently:

   .. code-block:: python

      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create multiple connectors concurrently
              connectors = await asyncio.gather(
                  client.actions.create(
                      name="Webhook 1",
                      connector_type_id=".webhook",
                      config={"url": "https://example1.com/webhook"}
                  ),
                  client.actions.create(
                      name="Webhook 2",
                      connector_type_id=".webhook",
                      config={"url": "https://example2.com/webhook"}
                  ),
                  client.actions.create(
                      name="Index Connector",
                      connector_type_id=".index",
                      config={"index": "logs"}
                  )
              )

              print(f"Created {len(connectors)} connectors")

      asyncio.run(main())
