#!/usr/bin/env python3
"""
Agent Builder Management Example

This example shows the minimal code needed to:
1. Create an ES|QL tool and execute it directly (no LLM required)
2. Create a custom agent that can use the tool
3. Fetch the agent's A2A protocol card
4. Talk to the MCP server (initialize handshake)
5. Chat with the agent via converse (requires an LLM connector)
6. Clean up (delete the agent and the tool)

The Agent Builder APIs are generally available since Kibana 9.2 (skills,
plugins, attachments and consumption are technical previews).

Run this example:
    python examples/agent_builder_management.py
"""

from utils import get_kibana_config

from kibana import Kibana
from kibana.exceptions import ApiError

TOOL_ID = "kbnpy_example.cluster_indices"
AGENT_ID = "kbnpy-example-agent"


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    tool_created = agent_created = False
    try:
        # 1. Create an ES|QL tool with a static query and run it directly
        client.agent_builder.create_tool(
            id=TOOL_ID,
            type="esql",
            description="Count documents in the Kibana event log",
            configuration={
                "query": "FROM .kibana-event-log* METADATA _index "
                "| STATS doc_count = COUNT(*)",
                "params": {},
            },
            tags=["kbnpy-example"],
        )
        tool_created = True
        print(f"Created tool {TOOL_ID}")

        executed = client.agent_builder.execute_tool(tool_id=TOOL_ID, tool_params={})
        for result in executed.body["results"]:
            if result["type"] == "esql_results":
                print(f"  Tool result: {result['data']['values']}")

        # 2. Create an agent that can use the tool
        client.agent_builder.create_agent(
            id=AGENT_ID,
            name="kbnpy example agent",
            description="Example agent created by kibana-py",
            configuration={
                "instructions": "Answer briefly using your tools.",
                "tools": [{"tool_ids": [TOOL_ID]}],
            },
            labels=["kbnpy-example"],
        )
        agent_created = True
        print(f"Created agent {AGENT_ID}")

        # 3. Fetch the agent's A2A card (Agent2Agent protocol descriptor)
        card = client.agent_builder.get_a2a_card(agent_id=AGENT_ID)
        print(f"A2A card: {card.body['name']} (A2A {card.body['protocolVersion']})")

        # 4. Initialize a session against the built-in MCP server
        mcp = client.agent_builder.send_mcp_request(
            payload={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "kibana-py-example", "version": "1.0.0"},
                },
            }
        )
        print(f"MCP server: {mcp.body['result']['serverInfo']['name']}")

        # 5. Chat with the agent (this needs a working LLM connector)
        try:
            reply = client.agent_builder.converse(
                input="How many documents are in the event log?",
                agent_id=AGENT_ID,
            )
            print(f"Agent reply: {reply.body['response']['message']}")
            client.agent_builder.delete_conversation(
                conversation_id=reply.body["conversation_id"]
            )
        except ApiError as exc:
            print(f"converse skipped (no LLM connector available): {exc.message}")
    finally:
        # 6. Clean up
        if agent_created:
            client.agent_builder.delete_agent(id=AGENT_ID)
            print(f"Deleted agent {AGENT_ID}")
        if tool_created:
            client.agent_builder.delete_tool(tool_id=TOOL_ID, force=True)
            print(f"Deleted tool {TOOL_ID}")
        client.close()


if __name__ == "__main__":
    main()
