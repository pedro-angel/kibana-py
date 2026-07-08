#!/usr/bin/env python3
"""
Observability AI Assistant Example

This example shows the minimal code needed to:
1. Create an AI (LLM) connector for the assistant to use
2. Generate a chat completion (the response is a server-sent event stream)
3. Clean up (delete the connector)

The chat completion API is a technical preview in Kibana 9.4 and needs a
working, reachable LLM connector. Set KBNPY_LMSTUDIO_OPENAI_URL (and
optionally KBNPY_LMSTUDIO_MODEL) to point the connector at a real
OpenAI-compatible backend (e.g. LM Studio). Without it there's no connector
to demonstrate against, so the example prints a "skipped" message instead of
creating a connector that can only fail.

Run this example:
    python examples/observability_ai_assistant_management.py
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

    prefix = resource_prefix(__file__)  # "kbnpy-observability-ai-assistant"
    connector_id = None
    created: list[tuple[str, str]] = []
    try:
        llm_url = os.getenv("KBNPY_LMSTUDIO_OPENAI_URL")
        if llm_url:
            model = os.getenv("KBNPY_LMSTUDIO_MODEL", "qwen/qwen3.5-9b")
            api_url = llm_url.rstrip("/")
            if not api_url.endswith("/chat/completions"):
                api_url = f"{api_url}/chat/completions"

            # 0. Idempotent start: clear only THIS example's own prior
            # connector, then create fresh. Connector IDs are capped at 36
            # characters and this example's prefix is already 32, so the
            # bare prefix is used as the ID rather than "{prefix}-conn".
            stable_connector_id = prefix
            try:
                client.connectors.delete(id=stable_connector_id)
            except NotFoundError:
                pass

            # 1. Create an OpenAI-compatible connector for the assistant to use
            created_conn = client.connectors.create(
                id=stable_connector_id,
                name=f"{prefix}-connector",
                connector_type_id=".gen-ai",
                config={
                    "apiProvider": "OpenAI",
                    "apiUrl": api_url,
                    "defaultModel": model,
                },
                secrets={"apiKey": "dummy-key"},
            )
            connector_id = created_conn.body["id"]
            created.append(("observability AI connector", connector_id))
            print(f"Created AI connector {connector_id} -> {api_url}")

            # 2. Generate a chat completion. Kibana streams the model output
            #    as server-sent events, so the body is raw bytes of
            #    "data: {...}" chunks terminated by "data: [DONE]".
            response = client.options(
                request_timeout=120
            ).observability_ai_assistant.chat_complete(
                connector_id=connector_id,
                persist=False,  # don't save the conversation in Kibana
                disable_functions=True,  # plain completion, no tool calls
                instructions=["Answer in one short sentence."],
                messages=[
                    {
                        "@timestamp": "2026-07-03T00:00:00.000Z",
                        "message": {
                            "role": "user",
                            "content": "Is my Elasticsearch cluster healthy right now?",
                        },
                    }
                ],
            )
            print(f"Chat completion HTTP {response.meta.status}; SSE stream:")
            for line in response.body.decode("utf-8").splitlines():
                if line.strip():
                    print(f"  {line}")
        else:
            print("KBNPY_LMSTUDIO_OPENAI_URL not set; skipped (no LLM connector)")
    finally:
        # 3. Clean up
        if connector_id is not None:
            if should_cleanup():
                try:
                    client.connectors.delete(id=connector_id)
                    print(f"Deleted AI connector {connector_id}")
                except NotFoundError:
                    pass
            else:
                print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
