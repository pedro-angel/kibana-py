Kibana Client
=============

The main synchronous client for interacting with Kibana's REST API.

.. currentmodule:: kibana

.. autoclass:: Kibana
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__, __enter__, __exit__

   .. rubric:: Initialization

   The Kibana client can be initialized with various connection and authentication options:

   .. code-block:: python

      from kibana import Kibana

      # Basic initialization with URL
      client = Kibana("http://localhost:5601")

      # With API key authentication
      client = Kibana(
          "http://localhost:5601",
          api_key="your_api_key"
      )

      # With basic authentication
      client = Kibana(
          "http://localhost:5601",
          basic_auth=("username", "password")
      )

      # With multiple hosts
      client = Kibana([
          "http://localhost:5601",
          "http://localhost:5602"
      ])

   .. rubric:: Context Manager Usage

   The client can be used as a context manager to ensure proper resource cleanup:

   .. code-block:: python

      with Kibana("http://localhost:5601") as client:
          # Use the client
          status = client.status.get_status()
          print(status.body["status"]["overall"]["level"])
      # Client is automatically closed

   .. rubric:: Namespace Clients

   The Kibana client provides access to various API namespaces through properties:

   - :attr:`~Kibana.actions` - Actions API for managing connectors
   - :attr:`~Kibana.spaces` - Spaces API for managing Kibana Spaces
   - :attr:`~Kibana.saved_objects` - Saved Objects API for managing saved objects
   - :attr:`~Kibana.status` - Status API for monitoring server health

   .. rubric:: Space-Scoped Operations

   Create a space-scoped client for operations within a specific space:

   .. code-block:: python

      # Create space-scoped client with validation
      marketing_client = client.space("marketing")

      # All operations are automatically scoped to the "marketing" space
      connector = marketing_client.actions.create(
          name="Marketing Webhook",
          connector_type_id=".webhook",
          config={"url": "https://example.com/webhook"}
      )

      # Create space-scoped client without validation (for performance)
      fast_client = client.space("marketing", validate=False)

SpaceScopedKibana
-----------------

A space-scoped client that automatically operates within a specific space context.

.. autoclass:: SpaceScopedKibana
   :members:
   :show-inheritance:
   :special-members: __init__, __enter__, __exit__

   .. rubric:: Usage

   Space-scoped clients are created using the :meth:`Kibana.space` method:

   .. code-block:: python

      # Create space-scoped client
      marketing_client = client.space("marketing")

      # All operations inherit the space context
      connector = marketing_client.actions.create(
          name="Test Connector",
          connector_type_id=".index",
          config={"index": "test"}
      )

      # The connector is created in the "marketing" space
      # No need to pass space_id parameter

   .. rubric:: Validation

   By default, space-scoped clients validate that the space exists when created.
   This can be disabled for performance-critical scenarios:

   .. code-block:: python

      # With validation (default)
      client_with_validation = client.space("marketing")

      # Without validation (faster, but may fail on operations if space doesn't exist)
      client_without_validation = client.space("marketing", validate=False)
