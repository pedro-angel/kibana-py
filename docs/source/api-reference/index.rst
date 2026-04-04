API Reference
=============

Complete API reference for the Kibana Python client.

This section provides detailed documentation for all public classes, methods, and exceptions
in the kibana-py library. The documentation is automatically generated from code docstrings
and includes usage examples.

.. toctree::
   :maxdepth: 2
   :caption: Client Classes

   client
   async-client

.. toctree::
   :maxdepth: 2
   :caption: Namespace Clients

   actions
   spaces
   saved-objects
   status

.. toctree::
   :maxdepth: 2
   :caption: Error Handling

   exceptions

Overview
--------

The Kibana Python client provides both synchronous and asynchronous interfaces for
interacting with Kibana's REST API. The client is organized into namespace clients
that group related functionality:

Main Clients
^^^^^^^^^^^^

- :class:`~kibana.Kibana` - Synchronous client for Kibana API
- :class:`~kibana.AsyncKibana` - Asynchronous client for Kibana API
- :class:`~kibana.SpaceScopedKibana` - Space-scoped synchronous client
- :class:`~kibana.AsyncSpaceScopedKibana` - Space-scoped asynchronous client

Namespace Clients
^^^^^^^^^^^^^^^^^

- :class:`~kibana.ActionsClient` - Manage action connectors
- :class:`~kibana.SpacesClient` - Manage Kibana Spaces
- :class:`~kibana.SavedObjectsClient` - Manage saved objects
- :class:`~kibana._sync.client.status.StatusClient` - Monitor server health

Exception Classes
^^^^^^^^^^^^^^^^^

- :class:`~kibana.KibanaException` - Base exception class
- :class:`~kibana.ApiError` - API-level errors
- :class:`~kibana.TransportError` - Transport-level errors
- :class:`~kibana.SpaceError` - Space-related errors

Quick Start
-----------

Synchronous Client
^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from kibana import Kibana

   # Initialize client
   client = Kibana(
       "http://localhost:5601",
       api_key="your_api_key"
   )

   # Use namespace clients
   status = client.status.get_status()
   connectors = client.actions.get_all()
   spaces = client.spaces.get_all()

   # Close client
   client.close()

Asynchronous Client
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from kibana import AsyncKibana
   import asyncio

   async def main():
       # Initialize async client
       async with AsyncKibana("http://localhost:5601") as client:
           # Use namespace clients with await
           status = await client.status.get_status()
           connectors = await client.actions.get_all()
           spaces = await client.spaces.get_all()

   asyncio.run(main())

Space-Scoped Operations
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from kibana import Kibana

   client = Kibana("http://localhost:5601")

   # Create space-scoped client
   marketing_client = client.space("marketing")

   # All operations are scoped to "marketing" space
   connector = marketing_client.actions.create(
       name="Marketing Webhook",
       connector_type_id=".webhook",
       config={"url": "https://example.com/webhook"}
   )

Error Handling
^^^^^^^^^^^^^^

.. code-block:: python

   from kibana import Kibana
   from kibana.exceptions import (
       NotFoundError,
       BadRequestError,
       SpaceNotFoundError
   )

   client = Kibana("http://localhost:5601")

   try:
       connector = client.actions.get(id="my-connector")
   except NotFoundError:
       print("Connector not found")
   except BadRequestError as e:
       print(f"Invalid request: {e.message}")
   except SpaceNotFoundError as e:
       print(f"Space not found: {e.space_id}")

See Also
--------

- :doc:`../installation` - Installation instructions
- :doc:`../quickstart` - Quick start guide
- :doc:`../user-guide/index` - User guide with detailed examples
- :doc:`../examples/index` - Example code and patterns
