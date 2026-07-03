#!/usr/bin/env python3
"""
Observability AI Assistant Example

This example shows the minimal code needed to:
1. Create an AI (LLM) connector for the assistant to use
2. Generate a chat completion (the response is a server-sent event stream)
3. Clean up (delete the connector)

The chat completion API is a technical preview in Kibana 9.4. It needs a
working LLM connector (OpenAI, Azure OpenAI, Amazon Bedrock, ...). Set
OPENAI_API_KEY (and optionally OPENAI_API_URL) to talk to a real model;
without it the example uses a dummy key, so the stream simply carries an
error chunk from the failed LLM call — which still demonstrates the full
request/streaming flow.

Run this example:
    python examples/observability_ai_assistant_management.py
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

    connector_id = None
    try:
        # 1. Create an OpenAI connector for the assistant to use
        created = client.connectors.create(
            name="kbnpy-example-ai-assistant-connector",
            connector_type_id=".gen-ai",
            config={
                "apiProvider": "OpenAI",
                "apiUrl": os.getenv(
                    "OPENAI_API_URL", "https://api.openai.com/v1/chat/completions"
                ),
            },
            secrets={"apiKey": os.getenv("OPENAI_API_KEY", "dummy-key")},
        )
        connector_id = created.body["id"]
        print(f"Created AI connector {connector_id}")

        # 2. Generate a chat completion. Kibana streams the model output as
        #    server-sent events, so the body is raw bytes of "data: {...}"
        #    chunks terminated by "data: [DONE]".
        response = client.observability_ai_assistant.chat_complete(
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
    finally:
        # 3. Clean up
        if connector_id is not None:
            client.connectors.delete(id=connector_id)
            print(f"Deleted AI connector {connector_id}")
        client.close()


if __name__ == "__main__":
    main()
