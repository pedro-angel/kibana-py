ActionsClient (deprecated)
==========================

Deprecated alias of the :doc:`Connectors API client <connectors>`.

.. warning::
   Kibana renamed "actions" to "connectors". The REST API still lives under
   ``/api/actions``, but the canonical client namespace is now
   ``client.connectors``. ``client.actions`` remains as a thin
   backwards-compatible alias and will be removed in a future release.
   **Use** :class:`~kibana._sync.client.connectors.ConnectorsClient`
   **via** ``client.connectors`` **instead** — see :doc:`connectors` for
   full documentation.

Migrating is a rename only; every method keeps the same signature:

.. code-block:: python

   from kibana import Kibana

   client = Kibana("http://localhost:5601", api_key="your_api_key")

   # Deprecated, but still works:
   client.actions.list_types()

   # Prefer this:
   client.connectors.list_types()

.. currentmodule:: kibana

.. autoclass:: ActionsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   All methods are inherited unchanged from
   :class:`~kibana._sync.client.connectors.ConnectorsClient`; see
   :doc:`connectors` for usage examples.

AsyncActionsClient
------------------

Deprecated alias of
:class:`~kibana._async.client.connectors.AsyncConnectorsClient`. Use
``client.connectors`` on :class:`~kibana.AsyncKibana` instead.

.. autoclass:: kibana._async.client.actions.AsyncActionsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__
