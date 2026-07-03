ObservabilityAiAssistantClient
==============================

Client for the Kibana Observability AI Assistant API.

The Observability AI Assistant chat completion API generates responses from a
large language model (LLM) based on the current conversation context. It also
handles any tool (function) requests within the conversation, which may
trigger multiple calls to the underlying LLM.

.. note::
   The API is marked as **technical preview** in Kibana 9.4 and may change or
   be removed in a future release.

The API requires a preconfigured AI (LLM) connector (for example an OpenAI,
Azure OpenAI or Amazon Bedrock connector) identified by ``connector_id``.
Conversations are space-scoped: every method accepts an optional ``space_id``
to target a specific space.

.. currentmodule:: kibana._sync.client.observability_ai_assistant

.. autoclass:: ObservabilityAiAssistantClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Chat Completion

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      response = client.observability_ai_assistant.chat_complete(
          connector_id="my-openai-connector",
          persist=False,
          messages=[
              {
                  "@timestamp": "2026-07-03T00:00:00.000Z",
                  "message": {
                      "role": "user",
                      "content": "Is my Elasticsearch cluster healthy?",
                  },
              }
          ],
      )

      print(response.body)  # raw SSE stream of completion chunks

   .. note::
      On success (HTTP 200) Kibana streams the model output as server-sent
      events (``data: {...}`` chunks terminated by ``data: [DONE]``) with
      content type ``application/octet-stream``, so the returned response
      body is the raw event stream rather than a parsed JSON object.

   .. rubric:: Persisting Conversations

   Set ``persist=True`` to store the conversation so it can be continued
   later (and pass ``conversation_id`` to append to an existing one):

   .. code-block:: python

      response = client.observability_ai_assistant.chat_complete(
          connector_id="my-openai-connector",
          persist=True,
          title="Cluster health check",
          messages=[
              {
                  "@timestamp": "2026-07-03T00:00:00.000Z",
                  "message": {
                      "role": "user",
                      "content": "Summarize the alerts from the last hour.",
                  },
              }
          ],
      )

AsyncObservabilityAiAssistantClient
-----------------------------------

Asynchronous version of the ObservabilityAiAssistantClient for use with
async/await syntax.

.. autoclass:: kibana._async.client.observability_ai_assistant.AsyncObservabilityAiAssistantClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncObservabilityAiAssistantClient provides the same methods as
   ObservabilityAiAssistantClient but all methods are async and must be
   awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              response = await client.observability_ai_assistant.chat_complete(
                  connector_id="my-openai-connector",
                  persist=False,
                  messages=[
                      {
                          "@timestamp": "2026-07-03T00:00:00.000Z",
                          "message": {
                              "role": "user",
                              "content": "Is my cluster healthy?",
                          },
                      }
                  ],
              )

      asyncio.run(main())
