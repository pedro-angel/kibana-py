ExceptionListsClient
====================

Client for the Kibana Security Exceptions API.

Exception lists group exception items that prevent Elastic Security detection
rules from generating alerts when their conditions match. This client covers
the exception list containers and their items, shared exception lists, rule
default exceptions and the Elastic Endpoint exception list.

Exception lists with ``namespace_type="single"`` are space-scoped resources,
while ``namespace_type="agnostic"`` lists are shared across all Kibana spaces.
Every method accepts an optional ``space_id`` to target a specific space.

.. currentmodule:: kibana._sync.client.exception_lists

.. autoclass:: ExceptionListsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Managing Exception Lists and Items

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create a detection exception list
      created = client.exception_lists.create(
          name="Trusted hosts",
          description="Hosts that never alert",
          type="detection",
          list_id="trusted-hosts",
      )

      # Add an exception item to it
      item = client.exception_lists.create_item(
          list_id="trusted-hosts",
          name="Trusted build server",
          description="Suppress alerts from the CI build server",
          entries=[{
              "field": "host.name",
              "operator": "included",
              "type": "match",
              "value": "build-server-01",
          }],
      )

      # Inspect the list
      items = client.exception_lists.find_items(list_id="trusted-hosts")
      summary = client.exception_lists.get_summary(list_id="trusted-hosts")

      # Clean up (items are deleted with their list)
      client.exception_lists.delete(list_id="trusted-hosts")

   .. rubric:: Duplicating, Exporting and Importing

   .. code-block:: python

      # Duplicate a list together with its items
      duplicate = client.exception_lists.duplicate(
          list_id="trusted-hosts", namespace_type="single"
      )

      # Export as NDJSON (requires BOTH id and list_id)
      exported = client.exception_lists.export(
          id=created.body["id"],
          list_id="trusted-hosts",
          namespace_type="single",
      )

      # Re-import; as_new_list generates fresh list_id/item_id values
      result = client.exception_lists.import_lists(
          file=exported.body, as_new_list=True
      )
      print(result.body["success"])

   .. rubric:: Shared Exception Lists and Rule Default Exceptions

   .. code-block:: python

      # Create a shared exception list (detection type, generated list_id)
      shared = client.exception_lists.create_shared_list(
          name="Shared exceptions",
          description="Exceptions shared across rules",
      )

      # Attach exception items directly to a detection rule's default list
      # (pass the rule's UUID id, not the human readable rule_id)
      client.exception_lists.create_rule_exceptions(
          id="4656dc92-5832-11ea-8e2d-0242ac130003",
          items=[{
              "name": "Rule exception",
              "description": "Suppress the build server",
              "type": "simple",
              "entries": [{
                  "field": "host.name",
                  "operator": "included",
                  "type": "match",
                  "value": "build-server-01",
              }],
          }],
      )

   .. rubric:: The Elastic Endpoint Exception List

   The endpoint exception list (fixed ``list_id`` ``"endpoint_list"``) is
   space agnostic and applies to all Elastic Endpoint agents. Creating it is
   idempotent: if it already exists the API returns an empty object.

   .. code-block:: python

      client.exception_lists.create_endpoint_list()

      ep_item = client.exception_lists.create_endpoint_item(
          name="Trusted process",
          description="Ignore the backup agent",
          os_types=["linux"],
          entries=[{
              "field": "process.executable.caseless",
              "operator": "included",
              "type": "match",
              "value": "/opt/backup/agent",
          }],
      )

      found = client.exception_lists.find_endpoint_items(per_page=50)
      client.exception_lists.delete_endpoint_item(
          item_id=ep_item.body["item_id"]
      )

AsyncExceptionListsClient
-------------------------

Asynchronous version of the ExceptionListsClient for use with async/await
syntax.

.. autoclass:: kibana._async.client.exception_lists.AsyncExceptionListsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncExceptionListsClient provides the same methods as
   ExceptionListsClient but all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              created = await client.exception_lists.create(
                  name="Trusted hosts",
                  description="Hosts that never alert",
                  type="detection",
                  list_id="trusted-hosts",
              )

              await client.exception_lists.create_item(
                  list_id="trusted-hosts",
                  name="Trusted build server",
                  description="Suppress alerts from the CI build server",
                  entries=[{
                      "field": "host.name",
                      "operator": "included",
                      "type": "match",
                      "value": "build-server-01",
                  }],
              )

              items = await client.exception_lists.find_items(
                  list_id="trusted-hosts"
              )
              print(items.body["total"])

              await client.exception_lists.delete(list_id="trusted-hosts")

      asyncio.run(main())
