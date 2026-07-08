AgentBuilderClient
==================

Client for the Kibana Agent Builder API.

Agent Builder lets you create and manage AI agents, tools, skills and
plugins, chat with agents (with conversation persistence and attachments),
and expose agents through the A2A and MCP protocols.

The core Agent Builder APIs (agents, tools, conversations, converse, A2A,
MCP) are generally available since Kibana 9.2.0. The attachments,
consumption, skills and plugins APIs are in technical preview. Chat-related
operations (converse, A2A tasks, MCP tool calls) require a configured LLM
connector.

Agent Builder resources are space-scoped: every method accepts an optional
``space_id`` to target a specific space.

.. currentmodule:: kibana._sync.client.agent_builder

.. autoclass:: AgentBuilderClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Tools and Agents

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create an ES|QL tool
      client.agent_builder.create_tool(
          id="my_ns.lookup",
          type="esql",
          description="Look up documents",
          configuration={"query": "FROM my-index | LIMIT 10", "params": {}},
      )

      # Create an agent that can use it
      client.agent_builder.create_agent(
          id="my-agent",
          name="My Agent",
          description="Searches my data",
          configuration={"tools": [{"tool_ids": ["my_ns.lookup"]}]},
      )

      # List agents and tools
      agents = client.agent_builder.list_agents()
      tools = client.agent_builder.list_tools()
      for agent in agents.body["results"]:
          print(agent["id"], agent["name"])

   .. rubric:: Chatting with Agents

   Chat requires a configured LLM connector:

   .. code-block:: python

      reply = client.agent_builder.converse(
          input="What data do I have?",
          agent_id="my-agent",
      )
      print(reply.body["response"]["message"])

      # Continue an existing conversation
      reply = client.agent_builder.converse(
          input="Show me more.",
          agent_id="my-agent",
          conversation_id=reply.body["conversation_id"],
      )

      # Browse persisted conversations
      conversations = client.agent_builder.list_conversations(
          agent_id="my-agent"
      )

   .. rubric:: Executing Tools Directly

   .. code-block:: python

      result = client.agent_builder.execute_tool(
          tool_id="my_ns.lookup",
          tool_params={},
      )

   .. rubric:: A2A and MCP Protocols

   .. code-block:: python

      # Fetch the A2A agent card for an agent
      card = client.agent_builder.get_a2a_card(agent_id="my-agent")

      # Send a JSON-RPC request to the MCP server endpoint
      response = client.agent_builder.send_mcp_request(
          payload={
              "jsonrpc": "2.0",
              "id": 1,
              "method": "tools/list",
          }
      )

   .. rubric:: Cleaning Up

   .. code-block:: python

      client.agent_builder.delete_agent(id="my-agent")
      client.agent_builder.delete_tool(tool_id="my_ns.lookup")

AsyncAgentBuilderClient
-----------------------

Asynchronous version of the AgentBuilderClient for use with async/await
syntax.

.. autoclass:: kibana._async.client.agent_builder.AsyncAgentBuilderClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncAgentBuilderClient provides the same methods as AgentBuilderClient
   but all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # List agents and tools concurrently
              agents, tools = await asyncio.gather(
                  client.agent_builder.list_agents(),
                  client.agent_builder.list_tools(),
              )

              # Chat with an agent (async, requires an LLM connector)
              reply = await client.agent_builder.converse(
                  input="What data do I have?",
                  agent_id="my-agent",
              )

      asyncio.run(main())
