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

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import NotFoundError


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    prefix = resource_prefix(__file__)  # "kbnpy-security-ai-assistant"
    conversation_id = None
    prompt_ids: list[str] = []
    connector_id = None
    created: list[tuple[str, str]] = []
    try:
        # 1. Conversation lifecycle
        created_conv = client.security_ai_assistant.create_conversation(
            title=f"{prefix}: suspicious login investigation",
        )
        conversation_id = created_conv.body["id"]
        created.append(("conversation", conversation_id))
        print(f"Created conversation {conversation_id}")

        found = client.security_ai_assistant.find_conversations(
            filter="suspicious login", per_page=10
        )
        print(f"Found {found.body['total']} matching conversation(s)")

        client.security_ai_assistant.update_conversation(
            id=conversation_id,
            title=f"{prefix}: suspicious login investigation (triaged)",
        )
        print("Updated conversation title")

        # 2. Bulk-create two quick prompts, then bulk-delete them. Prompt
        # names must be unique, so clear only THIS example's own prior
        # prompts first (a kept previous run would otherwise 409 here).
        stale = client.security_ai_assistant.find_prompts(
            filter=f"{prefix}*", per_page=50
        )
        stale_ids = [prompt["id"] for prompt in stale.body["data"]]
        if stale_ids:
            client.security_ai_assistant.bulk_action_prompts(delete={"ids": stale_ids})

        bulk = client.security_ai_assistant.bulk_action_prompts(
            create=[
                {
                    "name": f"{prefix} - summarize alerts",
                    "content": "Summarize the open alerts of the last 24 hours.",
                    "promptType": "quick",
                },
                {
                    "name": f"{prefix} - explain rule",
                    "content": "Explain what this detection rule does.",
                    "promptType": "quick",
                },
            ],
        )
        prompt_ids = [
            prompt["id"] for prompt in bulk.body["attributes"]["results"]["created"]
        ]
        created.extend(("quick prompt", pid) for pid in prompt_ids)
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

        # 4. Optional live chat through an OpenAI-compatible backend. The
        # connector this creates is brought under the same keep/clean gate
        # as everything else below -- it is NOT torn down immediately, so
        # --no-cleanup keeps it around like any other created resource.
        llm_url = os.getenv("KBNPY_LMSTUDIO_OPENAI_URL")
        if llm_url:
            model = os.getenv("KBNPY_LMSTUDIO_MODEL", "qwen/qwen3.5-9b")
            connector = client.connectors.create(
                name=f"{prefix} - llm connector",
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
            created.append(("security AI connector", connector_id))
            print(f"Created AI connector {connector_id}")

            answer = client.options(
                request_timeout=120
            ).security_ai_assistant.chat_complete(
                connector_id=connector_id,
                messages=[{"role": "user", "content": "What is credential stuffing?"}],
                persist=False,
            )
            print(f"Model answered: {answer.body['data'][:120]}...")
        else:
            print("KBNPY_LMSTUDIO_OPENAI_URL not set; skipped (no LLM connector)")
    finally:
        # 5. Clean up
        if should_cleanup():
            if connector_id is not None:
                try:
                    client.connectors.delete(id=connector_id)
                    print(f"Deleted connector {connector_id}")
                except NotFoundError:
                    pass
            if prompt_ids:
                client.security_ai_assistant.bulk_action_prompts(
                    delete={"ids": prompt_ids}
                )
                print(f"Deleted {len(prompt_ids)} prompts")
            if conversation_id is not None:
                try:
                    client.security_ai_assistant.delete_conversation(id=conversation_id)
                    print(f"Deleted conversation {conversation_id}")
                except NotFoundError:
                    pass
        else:
            print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
