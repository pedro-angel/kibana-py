ListsClient
===========

Client for the Kibana Security Lists API.

Value lists hold values of a single Elasticsearch type (``ip``, ``keyword``,
``ip_range``, ...) that Security detection rule exceptions can reference,
e.g. a list of known-bad IP addresses. A value list is a container; the
individual values live in list items, which can be managed one by one or
imported from a newline-separated text file.

Value lists are stored in per-space ``.lists-<space>`` and ``.items-<space>``
data streams that must exist before lists can be created. All Lists APIs are
space-scoped: every method accepts an optional ``space_id`` to target a
specific space.

.. currentmodule:: kibana._sync.client.lists

.. autoclass:: ListsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Preparing the Value List Data Streams

   .. code-block:: python

      from kibana import Kibana
      from kibana.exceptions import NotFoundError

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Value lists live in per-space data streams; create them once
      try:
          status = client.lists.get_index_status()
      except NotFoundError:
          client.lists.create_index()

   .. rubric:: Managing Value Lists

   .. code-block:: python

      # Create a list of bad IPs
      created = client.lists.create(
          name="Bad ips",
          description="Known bad IP addresses",
          type="ip",
          id="bad-ips",
      )

      # Read, replace, patch and search
      fetched = client.lists.get(id="bad-ips")
      client.lists.update(
          id="bad-ips",
          name="Bad ips - updated",
          description="Latest bad IPs",
          _version=fetched.body["_version"],
      )
      client.lists.patch(id="bad-ips", name="Bad ips - patched")
      found = client.lists.find(filter="type:ip", per_page=50)

      # Deleting a list also deletes all of its items
      client.lists.delete(id="bad-ips")

   .. rubric:: Managing List Items

   .. code-block:: python

      # Add individual values
      item = client.lists.create_item(
          list_id="bad-ips", value="192.0.2.1", refresh="wait_for"
      )

      # Look items up by ID, or by list_id + value (returns an array)
      by_id = client.lists.get_item(id=item.body["id"])
      by_value = client.lists.get_item(list_id="bad-ips", value="192.0.2.1")

      # Update / patch / delete
      client.lists.update_item(id=item.body["id"], value="192.0.2.2")
      client.lists.patch_item(id=item.body["id"], value="192.0.2.3")
      client.lists.delete_item(list_id="bad-ips", value="192.0.2.3")

      # Paginate through a list's items
      page = client.lists.find_items(list_id="bad-ips", per_page=100)

   .. rubric:: Importing and Exporting Values

   .. code-block:: python

      # Import values into an existing list (newline-separated upload)
      client.lists.import_items(
          file=["198.51.100.1", "198.51.100.2"],
          list_id="bad-ips",
          refresh="wait_for",
      )

      # Or create a brand-new list from a file: id/name come from filename
      client.lists.import_items(
          file="203.0.113.1\n203.0.113.2\n",
          type="ip",
          filename="more-bad-ips.txt",
      )

      # Export values (one entry per item value)
      exported = client.lists.export_items(list_id="bad-ips")
      for value in exported:
          print(value)

   .. rubric:: Privileges

   .. code-block:: python

      privileges = client.lists.get_privileges()
      print(privileges.body["is_authenticated"])

AsyncListsClient
----------------

Asynchronous version of the ListsClient for use with async/await syntax.

.. autoclass:: kibana._async.client.lists.AsyncListsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncListsClient provides the same methods as ListsClient but all
   methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create a list and add a value (async)
              created = await client.lists.create(
                  name="Bad ips",
                  description="Known bad IP addresses",
                  type="ip",
              )
              list_id = created.body["id"]
              await client.lists.create_item(
                  list_id=list_id, value="192.0.2.1", refresh="wait_for"
              )

              # Export and clean up (async)
              exported = await client.lists.export_items(list_id=list_id)
              await client.lists.delete(id=list_id)

      asyncio.run(main())
