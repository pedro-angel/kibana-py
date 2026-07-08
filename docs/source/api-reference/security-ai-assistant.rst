SecurityAiAssistantClient
=========================

Client for the Kibana Security AI Assistant API.

The Security AI Assistant helps security analysts triage alerts, write
queries and investigate incidents through a large language model. This
client manages the assistant's building blocks -- conversations, prompts,
anonymization fields and Knowledge Base entries -- and can request model
responses via ``chat_complete`` using any AI connector (``.gen-ai``,
``.bedrock``, ``.gemini``, ...) configured in Kibana.

All Security AI Assistant resources are space-scoped: a conversation or
prompt created in one space is not visible from another space. Every method
accepts an optional ``space_id`` to target a specific space.

.. currentmodule:: kibana._sync.client.security_ai_assistant

.. autoclass:: SecurityAiAssistantClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Managing Conversations

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create a conversation
      conv = client.security_ai_assistant.create_conversation(
          title="Suspicious login investigation",
          messages=[
              {
                  "content": "Investigate the failed logins on host web-01.",
                  "role": "user",
                  "timestamp": "2026-01-01T12:00:00Z",
              }
          ],
      )
      conversation_id = conv.body["id"]

      # Search, update and delete conversations
      found = client.security_ai_assistant.find_conversations(
          filter="Suspicious", sort_field="created_at", sort_order="desc"
      )
      client.security_ai_assistant.update_conversation(
          id=conversation_id, title="Suspicious login investigation (triaged)"
      )
      client.security_ai_assistant.delete_conversation(id=conversation_id)

      # Delete every conversation except the ones listed
      client.security_ai_assistant.delete_all_conversations(
          excluded_ids=["keep-this-conversation-id"]
      )

   .. rubric:: Prompts and Anonymization Fields

   Prompts and anonymization fields are managed through ``_find`` and
   ``_bulk_action`` endpoints:

   .. code-block:: python

      # Bulk-create prompts
      result = client.security_ai_assistant.bulk_action_prompts(
          create=[
              {
                  "name": "Summarize alerts",
                  "content": "Summarize the open alerts of the last 24 hours.",
                  "promptType": "quick",
              }
          ],
      )
      prompt_id = result.body["attributes"]["results"]["created"][0]["id"]

      # Update and delete in one bulk call
      client.security_ai_assistant.bulk_action_prompts(
          update=[{"id": prompt_id, "content": "Summarize critical alerts."}],
      )
      client.security_ai_assistant.bulk_action_prompts(
          delete={"ids": [prompt_id]},
      )

      # Control which fields may be sent to the model (and anonymized)
      client.security_ai_assistant.bulk_action_anonymization_fields(
          create=[{"field": "user.name", "allowed": True, "anonymized": True}],
      )
      fields = client.security_ai_assistant.find_anonymization_fields(
          filter='field: "user.name"'
      )

   .. rubric:: Knowledge Base

   .. code-block:: python

      # Check and run the Knowledge Base setup (ELSER model + content)
      status = client.security_ai_assistant.get_knowledge_base()
      if status.body["is_setup_available"]:
          client.security_ai_assistant.setup_knowledge_base(
              ignore_security_labs=True
          )

      # Create a document entry the assistant can use as context
      entry = client.security_ai_assistant.create_knowledge_base_entry(
          type="document",
          name="Password reset runbook",
          kb_resource="user",
          source="/runbooks/password-reset.md",
          text="To reset a password, open the settings page ...",
      )
      entry_id = entry.body["id"]

      # Find, update, and delete entries
      client.security_ai_assistant.find_knowledge_base_entries(per_page=50)
      client.security_ai_assistant.update_knowledge_base_entry(
          id=entry_id,
          type="document",
          name="Password reset runbook (v2)",
          kb_resource="user",
          source="/runbooks/password-reset.md",
          text="Updated instructions ...",
      )
      client.security_ai_assistant.delete_knowledge_base_entry(id=entry_id)

   .. rubric:: Chatting With the Model

   ``chat_complete`` routes the messages through a Kibana AI connector. LLM
   calls can be slow, so raise the request timeout for these calls:

   .. code-block:: python

      response = client.options(request_timeout=120).security_ai_assistant.chat_complete(
          connector_id="my-openai-connector",
          messages=[
              {"role": "user", "content": "What are common phishing techniques?"}
          ],
          persist=False,
      )
      print(response.body["data"])

AsyncSecurityAiAssistantClient
------------------------------

Asynchronous version of the SecurityAiAssistantClient for use with
async/await syntax.

.. autoclass:: kibana._async.client.security_ai_assistant.AsyncSecurityAiAssistantClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncSecurityAiAssistantClient provides the same methods as
   SecurityAiAssistantClient but all methods are async and must be awaited:

   .. code-block:: python

      import asyncio

      from kibana import AsyncKibana

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              conv = await client.security_ai_assistant.create_conversation(
                  title="Async investigation",
              )
              found = await client.security_ai_assistant.find_conversations(
                  filter="Async investigation",
              )
              await client.security_ai_assistant.delete_conversation(
                  id=conv.body["id"],
              )

      asyncio.run(main())
