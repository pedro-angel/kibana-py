#!/usr/bin/env python3
"""
Security AI Assistant Management Example

This example shows the minimal code needed to:
1. Create, find, update and delete an assistant conversation
2. Bulk-create and bulk-delete quick prompts
3. Inspect anonymization fields and the Knowledge Base status
4. (Optional) Ask a model a question via chat/complete when an
   OpenAI-compatible backend is configured through the
   KBNPY_LMSTUDIO_OPENAI_URL / KBNPY_LMSTUDIO_MODEL environment variables

Run this example:
    python examples/security_ai_assistant_management.py
"""

import os

from utils import get_kibana_config

from kibana import Kibana


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    conversation_id = None
    prompt_ids = []
    try:
        # 1. Conversation lifecycle
        created = client.security_ai_assistant.create_conversation(
            title="kbnpy example: suspicious login investigation",
        )
        conversation_id = created.body["id"]
        print(f"Created conversation {conversation_id}")

        found = client.security_ai_assistant.find_conversations(
            filter="suspicious login", per_page=10
        )
        print(f"Found {found.body['total']} matching conversation(s)")

        client.security_ai_assistant.update_conversation(
            id=conversation_id,
            title="kbnpy example: suspicious login investigation (triaged)",
        )
        print("Updated conversation title")

        # 2. Bulk-create two quick prompts, then bulk-delete them
        bulk = client.security_ai_assistant.bulk_action_prompts(
            create=[
                {
                    "name": "kbnpy example - summarize alerts",
                    "content": "Summarize the open alerts of the last 24 hours.",
                    "promptType": "quick",
                },
                {
                    "name": "kbnpy example - explain rule",
                    "content": "Explain what this detection rule does.",
                    "promptType": "quick",
                },
            ],
        )
        prompt_ids = [
            prompt["id"] for prompt in bulk.body["attributes"]["results"]["created"]
        ]
        print(f"Created {len(prompt_ids)} prompts")

        # 3. Anonymization fields and Knowledge Base status
        fields = client.security_ai_assistant.find_anonymization_fields(per_page=5)
        print(f"Anonymization fields configured: {fields.body['total']}")

        kb_status = client.security_ai_assistant.get_knowledge_base()
        print(
            "Knowledge Base: elser_exists="
            f"{kb_status.body.get('elser_exists')} "
            f"setup_available={kb_status.body.get('is_setup_available')}"
        )

        # 4. Optional live chat through an OpenAI-compatible backend
        llm_url = os.getenv("KBNPY_LMSTUDIO_OPENAI_URL")
        if llm_url:
            model = os.getenv("KBNPY_LMSTUDIO_MODEL", "qwen/qwen3.5-9b")
            connector = client.connectors.create(
                name="kbnpy example - security assistant llm",
                connector_type_id=".gen-ai",
                config={
                    "apiProvider": "OpenAI",
                    # The OpenAI connector posts to apiUrl directly, so it
                    # must be the full chat completions endpoint.
                    "apiUrl": f"{llm_url.rstrip('/')}/chat/completions",
                    "defaultModel": model,
                },
                secrets={"apiKey": "dummy-key"},
            )
            connector_id = connector.body["id"]
            try:
                answer = client.options(
                    request_timeout=120
                ).security_ai_assistant.chat_complete(
                    connector_id=connector_id,
                    messages=[
                        {"role": "user", "content": "What is credential stuffing?"}
                    ],
                    persist=False,
                )
                print(f"Model answered: {answer.body['data'][:120]}...")
            finally:
                client.connectors.delete(id=connector_id)
        else:
            print("KBNPY_LMSTUDIO_OPENAI_URL not set; skipping chat/complete demo")
    finally:
        # 5. Clean up
        if prompt_ids:
            client.security_ai_assistant.bulk_action_prompts(delete={"ids": prompt_ids})
            print(f"Deleted {len(prompt_ids)} prompts")
        if conversation_id is not None:
            client.security_ai_assistant.delete_conversation(id=conversation_id)
            print(f"Deleted conversation {conversation_id}")
        client.close()


if __name__ == "__main__":
    main()
