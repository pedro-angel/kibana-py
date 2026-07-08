"""Unit tests for AgentBuilderClient."""

import pytest

from kibana._sync.client import Kibana
from kibana._sync.client.agent_builder import AgentBuilderClient
from kibana.exceptions import BadRequestError, NotFoundError

AGENT_ID = "kbnpy-agent-1"
TOOL_ID = "kbnpy_ns.example_tool"
SKILL_ID = "kbnpy-skill-1"
CONVERSATION_ID = "696ccd6d-4bff-4b26-a62e-522ccf2dcd16"
ATTACHMENT_ID = "att-1"

AGENT_CONFIGURATION = {
    "instructions": "Be helpful.",
    "tools": [{"tool_ids": ["platform.core.search"]}],
}

TOOL_CONFIGURATION = {"query": "FROM kbnpy-idx | LIMIT 5", "params": {}}


def _agent_body(**overrides):
    """Build a representative agent response body."""
    body = {
        "id": AGENT_ID,
        "type": "chat",
        "name": "kbnpy agent",
        "description": "test agent",
        "labels": ["kbnpy"],
        "visibility": "public",
        "configuration": AGENT_CONFIGURATION,
        "readonly": False,
    }
    body.update(overrides)
    return body


def _tool_body(**overrides):
    """Build a representative tool response body."""
    body = {
        "id": TOOL_ID,
        "type": "esql",
        "description": "test tool",
        "tags": [],
        "configuration": TOOL_CONFIGURATION,
        "readonly": False,
        "schema": {"type": "object", "properties": {}},
    }
    body.update(overrides)
    return body


def _skill_body(**overrides):
    """Build a representative skill response body."""
    body = {
        "id": SKILL_ID,
        "name": "kbnpy skill",
        "description": "test skill",
        "content": "# Instructions",
        "referenced_content": [],
        "tool_ids": [],
        "readonly": False,
        "experimental": False,
    }
    body.update(overrides)
    return body


def _attachment_body(**overrides):
    """Build a representative attachment response body."""
    body = {
        "id": ATTACHMENT_ID,
        "type": "text",
        "description": "Meeting notes",
        "hidden": False,
        "data": "notes",
    }
    body.update(overrides)
    return body


class TestAgentBuilderClientInitialization:
    """Test AgentBuilderClient initialization."""

    def test_agent_builder_client_initialization(self, mock_transport):
        """Test that AgentBuilderClient can be initialized with a parent client."""
        client = Kibana(_transport=mock_transport)
        agent_builder_client = AgentBuilderClient(client)
        assert agent_builder_client._client is client

    def test_agent_builder_property_returns_client(self, mock_transport):
        """Test that client.agent_builder returns an AgentBuilderClient."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.agent_builder, AgentBuilderClient)

    def test_agent_builder_property_caching(self, mock_transport):
        """Test that the agent_builder property returns the same instance."""
        client = Kibana(_transport=mock_transport)
        assert client.agent_builder is client.agent_builder


class TestAgentBuilderClientAgents:
    """Test AgentBuilderClient agent CRUD methods."""

    def test_list_agents(self, mock_transport, mock_response):
        """Test listing agents."""
        mock_transport.perform_request.return_value = mock_response(
            body={"results": [_agent_body()]}
        )

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.list_agents()

        assert result.body["results"][0]["id"] == AGENT_ID

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/agent_builder/agents"
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert call_kwargs.get("body") is None

    def test_create_agent_minimal(self, mock_transport, mock_response):
        """Test creating an agent with only the required parameters."""
        mock_transport.perform_request.return_value = mock_response(body=_agent_body())

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.create_agent(
            id=AGENT_ID,
            name="kbnpy agent",
            description="test agent",
            configuration=AGENT_CONFIGURATION,
        )

        assert result.body["id"] == AGENT_ID

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/agent_builder/agents"
        assert call_kwargs["body"] == {
            "id": AGENT_ID,
            "name": "kbnpy agent",
            "description": "test agent",
            "configuration": AGENT_CONFIGURATION,
        }
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_create_agent_with_all_parameters(self, mock_transport, mock_response):
        """Test creating an agent with every optional field."""
        mock_transport.perform_request.return_value = mock_response(body=_agent_body())

        client = Kibana(_transport=mock_transport)
        client.agent_builder.create_agent(
            id=AGENT_ID,
            name="kbnpy agent",
            description="test agent",
            configuration=AGENT_CONFIGURATION,
            avatar_color="#BFDBFF",
            avatar_symbol="KA",
            labels=["kbnpy"],
            visibility="private",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "id": AGENT_ID,
            "name": "kbnpy agent",
            "description": "test agent",
            "configuration": AGENT_CONFIGURATION,
            "avatar_color": "#BFDBFF",
            "avatar_symbol": "KA",
            "labels": ["kbnpy"],
            "visibility": "private",
        }

    def test_get_agent(self, mock_transport, mock_response):
        """Test getting an agent by ID."""
        mock_transport.perform_request.return_value = mock_response(body=_agent_body())

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.get_agent(id=AGENT_ID)

        assert result.body["name"] == "kbnpy agent"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == f"/api/agent_builder/agents/{AGENT_ID}"
        assert call_kwargs.get("body") is None

    def test_get_agent_url_encodes_id(self, mock_transport, mock_response):
        """Test that the agent ID is URL-encoded in the path."""
        mock_transport.perform_request.return_value = mock_response(body=_agent_body())

        client = Kibana(_transport=mock_transport)
        client.agent_builder.get_agent(id="id with/special")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/agent_builder/agents/id%20with%2Fspecial"

    def test_update_agent_partial(self, mock_transport, mock_response):
        """Test that only the provided fields are sent in the PUT body."""
        mock_transport.perform_request.return_value = mock_response(
            body=_agent_body(description="updated")
        )

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.update_agent(id=AGENT_ID, description="updated")

        assert result.body["description"] == "updated"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == f"/api/agent_builder/agents/{AGENT_ID}"
        assert call_kwargs["body"] == {"description": "updated"}

    def test_delete_agent(self, mock_transport, mock_response):
        """Test deleting an agent."""
        mock_transport.perform_request.return_value = mock_response(
            body={"success": True}
        )

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.delete_agent(id=AGENT_ID)

        assert result.body["success"] is True

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == f"/api/agent_builder/agents/{AGENT_ID}"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs.get("body") is None

    def test_get_agent_consumption(self, mock_transport, mock_response):
        """Test getting agent consumption data with filters."""
        mock_transport.perform_request.return_value = mock_response(
            body={"results": [], "total": 0}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.get_agent_consumption(
            agent_id=AGENT_ID,
            has_warnings=True,
            search="kbnpy",
            search_after=[1700000000000],
            size=10,
            sort_field="total_tokens",
            sort_order="desc",
            usernames=["elastic"],
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert (
            call_kwargs["target"] == f"/api/agent_builder/agents/{AGENT_ID}/consumption"
        )
        assert call_kwargs["body"] == {
            "has_warnings": True,
            "search": "kbnpy",
            "search_after": [1700000000000],
            "size": 10,
            "sort_field": "total_tokens",
            "sort_order": "desc",
            "usernames": ["elastic"],
        }

    def test_get_agent_consumption_defaults_to_empty_body(
        self, mock_transport, mock_response
    ):
        """Test that consumption defaults send an empty JSON body."""
        mock_transport.perform_request.return_value = mock_response(
            body={"results": [], "total": 0}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.get_agent_consumption(agent_id=AGENT_ID)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {}


class TestAgentBuilderClientTools:
    """Test AgentBuilderClient tool CRUD and execute methods."""

    def test_list_tools(self, mock_transport, mock_response):
        """Test listing tools."""
        mock_transport.perform_request.return_value = mock_response(
            body={"results": [_tool_body()]}
        )

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.list_tools()

        assert result.body["results"][0]["id"] == TOOL_ID

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/agent_builder/tools"

    def test_create_tool(self, mock_transport, mock_response):
        """Test creating an ES|QL tool."""
        mock_transport.perform_request.return_value = mock_response(body=_tool_body())

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.create_tool(
            id=TOOL_ID,
            type="esql",
            configuration=TOOL_CONFIGURATION,
            description="test tool",
            tags=["kbnpy"],
        )

        assert result.body["id"] == TOOL_ID

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/agent_builder/tools"
        assert call_kwargs["body"] == {
            "id": TOOL_ID,
            "type": "esql",
            "configuration": TOOL_CONFIGURATION,
            "description": "test tool",
            "tags": ["kbnpy"],
        }

    def test_get_tool(self, mock_transport, mock_response):
        """Test getting a tool by ID."""
        mock_transport.perform_request.return_value = mock_response(body=_tool_body())

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.get_tool(tool_id=TOOL_ID)

        assert result.body["type"] == "esql"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == f"/api/agent_builder/tools/{TOOL_ID}"

    def test_update_tool(self, mock_transport, mock_response):
        """Test updating a tool."""
        mock_transport.perform_request.return_value = mock_response(
            body=_tool_body(description="updated")
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.update_tool(
            tool_id=TOOL_ID,
            configuration=TOOL_CONFIGURATION,
            description="updated",
            tags=["kbnpy"],
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == f"/api/agent_builder/tools/{TOOL_ID}"
        assert call_kwargs["body"] == {
            "configuration": TOOL_CONFIGURATION,
            "description": "updated",
            "tags": ["kbnpy"],
        }

    def test_delete_tool_with_force(self, mock_transport, mock_response):
        """Test that the force flag is encoded as a boolean query parameter."""
        mock_transport.perform_request.return_value = mock_response(
            body={"success": True}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.delete_tool(tool_id=TOOL_ID, force=True)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == f"/api/agent_builder/tools/{TOOL_ID}?force=true"

    def test_execute_tool(self, mock_transport, mock_response):
        """Test executing a tool."""
        mock_transport.perform_request.return_value = mock_response(
            body={"results": [{"type": "esql_results", "data": {}}]}
        )

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.execute_tool(
            tool_id=TOOL_ID,
            tool_params={"limit": 5},
            connector_id="my-connector",
        )

        assert result.body["results"][0]["type"] == "esql_results"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/agent_builder/tools/_execute"
        assert call_kwargs["body"] == {
            "tool_id": TOOL_ID,
            "tool_params": {"limit": 5},
            "connector_id": "my-connector",
        }


class TestAgentBuilderClientConversations:
    """Test AgentBuilderClient conversation methods."""

    def test_list_conversations(self, mock_transport, mock_response):
        """Test listing conversations without a filter."""
        mock_transport.perform_request.return_value = mock_response(
            body={"results": []}
        )

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.list_conversations()

        assert result.body["results"] == []

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/agent_builder/conversations"

    def test_list_conversations_with_agent_filter(self, mock_transport, mock_response):
        """Test listing conversations filtered by agent ID."""
        mock_transport.perform_request.return_value = mock_response(
            body={"results": []}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.list_conversations(agent_id=AGENT_ID)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == f"/api/agent_builder/conversations?agent_id={AGENT_ID}"
        )

    def test_get_conversation(self, mock_transport, mock_response):
        """Test getting a conversation by ID."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": CONVERSATION_ID, "title": "kbnpy", "rounds": []}
        )

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.get_conversation(conversation_id=CONVERSATION_ID)

        assert result.body["id"] == CONVERSATION_ID

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert (
            call_kwargs["target"]
            == f"/api/agent_builder/conversations/{CONVERSATION_ID}"
        )

    def test_delete_conversation(self, mock_transport, mock_response):
        """Test deleting a conversation by ID."""
        mock_transport.perform_request.return_value = mock_response(
            body={"success": True}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.delete_conversation(conversation_id=CONVERSATION_ID)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert (
            call_kwargs["target"]
            == f"/api/agent_builder/conversations/{CONVERSATION_ID}"
        )


class TestAgentBuilderClientAttachments:
    """Test AgentBuilderClient conversation attachment methods."""

    def test_list_attachments(self, mock_transport, mock_response):
        """Test listing attachments with the include_deleted flag."""
        mock_transport.perform_request.return_value = mock_response(
            body={"attachments": [_attachment_body()]}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.list_attachments(
            conversation_id=CONVERSATION_ID, include_deleted=True
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            f"/api/agent_builder/conversations/{CONVERSATION_ID}"
            "/attachments?include_deleted=true"
        )

    def test_create_attachment(self, mock_transport, mock_response):
        """Test creating an attachment with all fields."""
        mock_transport.perform_request.return_value = mock_response(
            body=_attachment_body()
        )

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.create_attachment(
            conversation_id=CONVERSATION_ID,
            type="text",
            data="notes",
            description="Meeting notes",
            hidden=False,
            id=ATTACHMENT_ID,
            origin="document:notes-v1",
        )

        assert result.body["id"] == ATTACHMENT_ID

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert (
            call_kwargs["target"]
            == f"/api/agent_builder/conversations/{CONVERSATION_ID}/attachments"
        )
        assert call_kwargs["body"] == {
            "type": "text",
            "data": "notes",
            "description": "Meeting notes",
            "hidden": False,
            "id": ATTACHMENT_ID,
            "origin": "document:notes-v1",
        }

    def test_update_attachment(self, mock_transport, mock_response):
        """Test updating an attachment's content."""
        mock_transport.perform_request.return_value = mock_response(
            body=_attachment_body(data="updated")
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.update_attachment(
            conversation_id=CONVERSATION_ID,
            attachment_id=ATTACHMENT_ID,
            data="updated",
            description="Meeting notes v2",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == (
            f"/api/agent_builder/conversations/{CONVERSATION_ID}"
            f"/attachments/{ATTACHMENT_ID}"
        )
        assert call_kwargs["body"] == {
            "data": "updated",
            "description": "Meeting notes v2",
        }

    def test_rename_attachment(self, mock_transport, mock_response):
        """Test renaming an attachment via PATCH."""
        mock_transport.perform_request.return_value = mock_response(
            body=_attachment_body(description="renamed")
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.rename_attachment(
            conversation_id=CONVERSATION_ID,
            attachment_id=ATTACHMENT_ID,
            description="renamed",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["target"] == (
            f"/api/agent_builder/conversations/{CONVERSATION_ID}"
            f"/attachments/{ATTACHMENT_ID}"
        )
        assert call_kwargs["body"] == {"description": "renamed"}

    def test_delete_attachment_with_permanent(self, mock_transport, mock_response):
        """Test that the permanent flag is encoded as a query parameter."""
        mock_transport.perform_request.return_value = mock_response(
            body={"success": True}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.delete_attachment(
            conversation_id=CONVERSATION_ID,
            attachment_id=ATTACHMENT_ID,
            permanent=True,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == (
            f"/api/agent_builder/conversations/{CONVERSATION_ID}"
            f"/attachments/{ATTACHMENT_ID}?permanent=true"
        )

    def test_restore_attachment(self, mock_transport, mock_response):
        """Test restoring a soft-deleted attachment."""
        mock_transport.perform_request.return_value = mock_response(
            body=_attachment_body()
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.restore_attachment(
            conversation_id=CONVERSATION_ID, attachment_id=ATTACHMENT_ID
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            f"/api/agent_builder/conversations/{CONVERSATION_ID}"
            f"/attachments/{ATTACHMENT_ID}/_restore"
        )
        assert call_kwargs.get("body") is None

    def test_update_attachment_origin(self, mock_transport, mock_response):
        """Test updating an attachment's origin."""
        mock_transport.perform_request.return_value = mock_response(
            body=_attachment_body(origin="abc123")
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.update_attachment_origin(
            conversation_id=CONVERSATION_ID,
            attachment_id=ATTACHMENT_ID,
            origin="abc123",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == (
            f"/api/agent_builder/conversations/{CONVERSATION_ID}"
            f"/attachments/{ATTACHMENT_ID}/origin"
        )
        assert call_kwargs["body"] == {"origin": "abc123"}

    def test_check_stale_attachments(self, mock_transport, mock_response):
        """Test checking attachment staleness."""
        mock_transport.perform_request.return_value = mock_response(
            body={"attachments": [{"id": ATTACHMENT_ID, "is_stale": False}]}
        )

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.check_stale_attachments(
            conversation_id=CONVERSATION_ID
        )

        assert result.body["attachments"][0]["is_stale"] is False

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            f"/api/agent_builder/conversations/{CONVERSATION_ID}/attachments/stale"
        )


class TestAgentBuilderClientConverse:
    """Test AgentBuilderClient.converse() and converse_async() methods."""

    def test_converse_minimal(self, mock_transport, mock_response):
        """Test sending a chat message with only an input."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "conversation_id": CONVERSATION_ID,
                "response": {"message": "Hi!"},
                "steps": [],
            }
        )

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.converse(input="Hello")

        assert result.body["response"]["message"] == "Hi!"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/agent_builder/converse"
        assert call_kwargs["body"] == {"input": "Hello"}
        assert call_kwargs["headers"]["accept"] == "application/json"

    def test_converse_with_all_parameters(self, mock_transport, mock_response):
        """Test that all converse fields map to the documented body keys."""
        mock_transport.perform_request.return_value = mock_response(
            body={"conversation_id": CONVERSATION_ID}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.converse(
            input="Hello",
            agent_id=AGENT_ID,
            conversation_id=CONVERSATION_ID,
            connector_id="my-connector",
            attachments=[{"type": "text", "data": "notes"}],
            browser_api_tools=[{"id": "b1", "description": "d", "schema": {}}],
            capabilities={"visualizations": True},
            configuration_overrides={"instructions": "Short answers."},
            prompts={"prompt-1": {"allow": True}},
            action="regenerate",
            execution_mode="local",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "input": "Hello",
            "agent_id": AGENT_ID,
            "conversation_id": CONVERSATION_ID,
            "connector_id": "my-connector",
            "attachments": [{"type": "text", "data": "notes"}],
            "browser_api_tools": [{"id": "b1", "description": "d", "schema": {}}],
            "capabilities": {"visualizations": True},
            "configuration_overrides": {"instructions": "Short answers."},
            "prompts": {"prompt-1": {"allow": True}},
            "action": "regenerate",
            "_execution_mode": "local",
        }

    def test_converse_with_inference_id(self, mock_transport, mock_response):
        """Test that inference_id is sent instead of connector_id."""
        mock_transport.perform_request.return_value = mock_response(
            body={"conversation_id": CONVERSATION_ID}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.converse(input="Hello", inference_id="my-inference")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "input": "Hello",
            "inference_id": "my-inference",
        }

    def test_converse_async_streams_events(self, mock_transport, mock_response):
        """Test that converse_async targets the SSE endpoint with the right accept."""
        mock_transport.perform_request.return_value = mock_response(
            body='event: message_chunk\ndata: {"text_chunk": "Hi"}\n\n'
        )

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.converse_async(input="Hello", agent_id=AGENT_ID)

        assert "message_chunk" in result.body

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/agent_builder/converse/async"
        assert call_kwargs["body"] == {"input": "Hello", "agent_id": AGENT_ID}
        assert call_kwargs["headers"]["accept"] == "text/event-stream"
        assert call_kwargs["headers"]["content-type"] == "application/json"


class TestAgentBuilderClientA2A:
    """Test AgentBuilderClient A2A protocol methods."""

    def test_get_a2a_card(self, mock_transport, mock_response):
        """Test getting an agent's A2A card."""
        mock_transport.perform_request.return_value = mock_response(
            body={"name": "kbnpy agent", "protocolVersion": "0.3.0"}
        )

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.get_a2a_card(agent_id=AGENT_ID)

        assert result.body["protocolVersion"] == "0.3.0"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == f"/api/agent_builder/a2a/{AGENT_ID}.json"

    def test_send_a2a_task(self, mock_transport, mock_response):
        """Test sending an A2A JSON-RPC task."""
        payload = {
            "jsonrpc": "2.0",
            "id": "task-1",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Hello"}],
                    "messageId": "msg-1",
                }
            },
        }
        mock_transport.perform_request.return_value = mock_response(
            body={"jsonrpc": "2.0", "id": "task-1", "result": {"kind": "message"}}
        )

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.send_a2a_task(agent_id=AGENT_ID, payload=payload)

        assert result.body["result"]["kind"] == "message"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == f"/api/agent_builder/a2a/{AGENT_ID}"
        assert call_kwargs["body"] == payload


class TestAgentBuilderClientMcp:
    """Test AgentBuilderClient.send_mcp_request() method."""

    def test_send_mcp_request(self, mock_transport, mock_response):
        """Test sending an MCP JSON-RPC request with the dual accept header."""
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        mock_transport.perform_request.return_value = mock_response(
            body={"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
        )

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.send_mcp_request(payload=payload)

        assert result.body["result"]["tools"] == []

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/agent_builder/mcp"
        assert call_kwargs["body"] == payload
        # The live MCP endpoint rejects requests whose accept header does not
        # include both mimetypes with a 406.
        assert call_kwargs["headers"]["accept"] == "application/json, text/event-stream"

    def test_send_mcp_request_with_namespace(self, mock_transport, mock_response):
        """Test that the namespace filter is encoded as a query parameter."""
        mock_transport.perform_request.return_value = mock_response(
            body={"jsonrpc": "2.0", "id": 1, "result": {}}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.send_mcp_request(
            payload={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            namespace="platform.core",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/agent_builder/mcp?namespace=platform.core"


class TestAgentBuilderClientSkills:
    """Test AgentBuilderClient skill CRUD methods."""

    def test_list_skills(self, mock_transport, mock_response):
        """Test listing skills with the include_plugins flag."""
        mock_transport.perform_request.return_value = mock_response(
            body={"results": [_skill_body()]}
        )

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.list_skills(include_plugins=True)

        assert result.body["results"][0]["id"] == SKILL_ID

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/agent_builder/skills?include_plugins=true"

    def test_create_skill(self, mock_transport, mock_response):
        """Test creating a skill."""
        mock_transport.perform_request.return_value = mock_response(body=_skill_body())

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.create_skill(
            id=SKILL_ID,
            name="kbnpy skill",
            description="test skill",
            content="# Instructions",
            referenced_content=[
                {"name": "ref", "relativePath": "ref.md", "content": "text"}
            ],
            tool_ids=["platform.core.search"],
        )

        assert result.body["id"] == SKILL_ID

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/agent_builder/skills"
        assert call_kwargs["body"] == {
            "id": SKILL_ID,
            "name": "kbnpy skill",
            "description": "test skill",
            "content": "# Instructions",
            "referenced_content": [
                {"name": "ref", "relativePath": "ref.md", "content": "text"}
            ],
            "tool_ids": ["platform.core.search"],
        }

    def test_get_skill(self, mock_transport, mock_response):
        """Test getting a skill by ID."""
        mock_transport.perform_request.return_value = mock_response(body=_skill_body())

        client = Kibana(_transport=mock_transport)
        result = client.agent_builder.get_skill(skill_id=SKILL_ID)

        assert result.body["name"] == "kbnpy skill"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == f"/api/agent_builder/skills/{SKILL_ID}"

    def test_update_skill(self, mock_transport, mock_response):
        """Test that only the provided fields are sent in the PUT body."""
        mock_transport.perform_request.return_value = mock_response(
            body=_skill_body(description="updated")
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.update_skill(skill_id=SKILL_ID, description="updated")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == f"/api/agent_builder/skills/{SKILL_ID}"
        assert call_kwargs["body"] == {"description": "updated"}

    def test_delete_skill_with_force(self, mock_transport, mock_response):
        """Test deleting a skill with the force flag."""
        mock_transport.perform_request.return_value = mock_response(
            body={"success": True}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.delete_skill(skill_id=SKILL_ID, force=True)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert (
            call_kwargs["target"] == f"/api/agent_builder/skills/{SKILL_ID}?force=true"
        )


class TestAgentBuilderClientPlugins:
    """Test AgentBuilderClient plugin methods."""

    def test_list_plugins(self, mock_transport, mock_response):
        """Test listing plugins."""
        mock_transport.perform_request.return_value = mock_response(
            body={"results": []}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.list_plugins()

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/agent_builder/plugins"

    def test_get_plugin(self, mock_transport, mock_response):
        """Test getting a plugin by ID."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "my-plugin"}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.get_plugin(plugin_id="my-plugin")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/agent_builder/plugins/my-plugin"

    def test_install_plugin(self, mock_transport, mock_response):
        """Test installing a plugin from a URL."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "my-plugin"}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.install_plugin(
            url="https://github.com/example/agent-plugin",
            plugin_name="my-plugin",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/agent_builder/plugins/install"
        assert call_kwargs["body"] == {
            "url": "https://github.com/example/agent-plugin",
            "plugin_name": "my-plugin",
        }

    def test_delete_plugin_with_force(self, mock_transport, mock_response):
        """Test deleting a plugin with the force flag."""
        mock_transport.perform_request.return_value = mock_response(
            body={"success": True}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.delete_plugin(plugin_id="my-plugin", force=True)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert (
            call_kwargs["target"] == "/api/agent_builder/plugins/my-plugin?force=true"
        )


class TestAgentBuilderClientSpaceScoped:
    """Test space-scoped path building for the Agent Builder API."""

    def test_list_agents_in_space(self, mock_transport, mock_response):
        """Test listing agents in a specific space."""
        mock_transport.perform_request.return_value = mock_response(
            body={"results": []}
        )

        client = Kibana(_transport=mock_transport)
        client.agent_builder.list_agents(space_id="marketing", validate_spaces=False)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/agent_builder/agents"

    def test_create_tool_in_space(self, mock_transport, mock_response):
        """Test creating a tool in a specific space."""
        mock_transport.perform_request.return_value = mock_response(body=_tool_body())

        client = Kibana(_transport=mock_transport)
        client.agent_builder.create_tool(
            id=TOOL_ID,
            type="esql",
            configuration=TOOL_CONFIGURATION,
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/agent_builder/tools"


class TestAgentBuilderClientErrorHandling:
    """Test AgentBuilderClient error handling."""

    def test_get_agent_not_found_error(self, mock_transport, mock_response):
        """Test that a 404 response raises NotFoundError."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Agent nope not found",
            },
            status=404,
        )

        client = Kibana(_transport=mock_transport)

        with pytest.raises(NotFoundError):
            client.agent_builder.get_agent(id="nope")

    def test_converse_bad_request_error(self, mock_transport, mock_response):
        """Test that a 400 response raises BadRequestError."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 400,
                "error": "Bad Request",
                "message": "[request body]: invalid",
            },
            status=400,
        )

        client = Kibana(_transport=mock_transport)

        with pytest.raises(BadRequestError):
            client.agent_builder.converse(input="Hello", action="bogus")
