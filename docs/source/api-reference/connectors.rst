ConnectorsClient
================

Client for the Kibana Connectors API (``/api/actions``).

Connectors enable integration with external systems for alerting,
notifications, and automation workflows. This client provides methods to
create, read, update, delete, and run connectors, list the available
connector types, and handle OAuth 2.0 callback flows, with full support for
Kibana Spaces.

.. note::
   Kibana renamed "actions" to "connectors". The canonical client namespace
   is ``client.connectors``; ``client.actions`` remains as a deprecated,
   backwards-compatible alias (see :doc:`actions`).

.. currentmodule:: kibana._sync.client.connectors

.. autoclass:: ConnectorsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Overview

   Connectors can be scoped to specific spaces, enabling multi-tenancy where
   different teams or projects can have isolated sets of connectors.

   Common connector types:

   - ``.webhook`` - HTTP webhooks for custom integrations
   - ``.slack`` - Slack messages and notifications
   - ``.email`` - Email notifications
   - ``.index`` - Write to Elasticsearch indices
   - ``.server-log`` - Server log entries
   - ``.pagerduty`` - PagerDuty incident management
   - ``.servicenow`` - ServiceNow ticket creation
   - ``.teams`` - Microsoft Teams messages
   - ``.jira`` - Jira issue creation

   .. rubric:: Creating Connectors

   Create a connector with the :meth:`~ConnectorsClient.create` method:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create a webhook connector
      connector = client.connectors.create(
          name="Alert Webhook",
          connector_type_id=".webhook",
          config={"url": "https://example.com/webhook"},
          secrets={"user": "admin", "password": "secret"},
      )

      connector_id = connector.body["id"]
      print(f"Created connector: {connector_id}")

   .. rubric:: Listing Connectors and Connector Types

   .. code-block:: python

      # Get all connectors
      connectors = client.connectors.get_all()
      for connector in connectors.body:
          print(f"{connector['name']}: {connector['connector_type_id']}")

      # List available connector types
      types = client.connectors.list_types()
      for connector_type in types.body:
          print(f"{connector_type['id']}: {connector_type['name']}")

   .. rubric:: Running Connectors

   Run a connector with specific parameters:

   .. code-block:: python

      result = client.connectors.execute(
          id=connector_id,
          params={"body": '{"message": "Alert triggered!"}'},
      )

      print(f"Execution status: {result.body['status']}")

   .. rubric:: Updating and Deleting

   .. code-block:: python

      # Update connector configuration
      updated = client.connectors.update(
          id=connector_id,
          name="Updated Webhook",
          config={"url": "https://new-url.example.com/webhook"},
      )

      # Delete the connector
      client.connectors.delete(id=connector_id)

   .. rubric:: Space-Scoped Connectors

   .. code-block:: python

      # Create a connector in a specific space
      connector = client.connectors.create(
          name="Marketing Webhook",
          connector_type_id=".webhook",
          config={"url": "https://marketing.example.com/webhook"},
          space_id="marketing",
      )

      # Or use a space-scoped client
      marketing = client.space("marketing")
      connector = marketing.connectors.create(
          name="Marketing Log",
          connector_type_id=".server-log",
      )

   .. rubric:: Error Handling

   .. code-block:: python

      from kibana.exceptions import (
          NotFoundError,
          BadRequestError,
          SpaceNotFoundError,
      )

      try:
          connector = client.connectors.get(id="nonexistent")
      except NotFoundError:
          print("Connector not found")
      except BadRequestError as e:
          print(f"Invalid request: {e.message}")
      except SpaceNotFoundError as e:
          print(f"Space not found: {e.space_id}")

AsyncConnectorsClient
---------------------

Asynchronous version of the ConnectorsClient for use with async/await syntax.

.. autoclass:: kibana._async.client.connectors.AsyncConnectorsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncConnectorsClient provides the same methods as ConnectorsClient but
   all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create a connector (async)
              connector = await client.connectors.create(
                  name="Async Webhook",
                  connector_type_id=".webhook",
                  config={"url": "https://example.com/webhook"},
              )

              # Run it (async)
              result = await client.connectors.execute(
                  id=connector.body["id"],
                  params={"body": '{"message": "Test"}'},
              )

              # Delete it (async)
              await client.connectors.delete(id=connector.body["id"])

      asyncio.run(main())

   .. rubric:: Concurrent Operations

   .. code-block:: python

      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create multiple connectors concurrently
              connectors = await asyncio.gather(
                  client.connectors.create(
                      name="Webhook 1",
                      connector_type_id=".webhook",
                      config={"url": "https://example1.com/webhook"},
                  ),
                  client.connectors.create(
                      name="Webhook 2",
                      connector_type_id=".webhook",
                      config={"url": "https://example2.com/webhook"},
                  ),
              )
              print(f"Created {len(connectors)} connectors")

      asyncio.run(main())
