UpgradeAssistantClient
======================

Client for the Kibana Upgrade Assistant API.

The Upgrade Assistant helps you prepare a cluster for a major version upgrade
by reporting deprecation issues that must be resolved first.

.. note::
   The Upgrade Assistant API is in **technical preview** in Kibana 9.4; it
   may change or be removed in a future release. It is not space-scoped.

.. currentmodule:: kibana._sync.client.upgrade_assistant

.. autoclass:: UpgradeAssistantClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Checking Upgrade Readiness

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      status = client.upgrade_assistant.status()

      if status.body["readyForUpgrade"]:
          print("Cluster is ready for the next major upgrade")
      else:
          print(status.body["details"])

AsyncUpgradeAssistantClient
---------------------------

Asynchronous version of the UpgradeAssistantClient for use with async/await
syntax.

.. autoclass:: kibana._async.client.upgrade_assistant.AsyncUpgradeAssistantClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncUpgradeAssistantClient provides the same methods as
   UpgradeAssistantClient but all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              status = await client.upgrade_assistant.status()
              print(status.body["readyForUpgrade"])

      asyncio.run(main())
