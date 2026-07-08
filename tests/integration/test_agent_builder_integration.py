"""Integration tests for AgentBuilderClient against a live Kibana instance."""

import base64
import json
import os
import urllib.request
import uuid

import pytest

from kibana.exceptions import ApiError, BadRequestError, NotFoundError

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    get_integration_test_config,
    is_kibana_available,
)

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)

RESOURCE_PREFIX = "kbnpy-agent-builder"
# Tool IDs may not contain hyphens before the namespace separator, so tools
# use an underscore variant of the prefix.
TOOL_NAMESPACE = "kbnpy_agent_builder"

MISSING_CONVERSATION_ID = f"{RESOURCE_PREFIX}-missing-{uuid.uuid4().hex[:12]}"


def _es_request(method: str, path: str, body: dict | None = None) -> None:
    """Perform a minimal Elasticsearch request for test index setup/teardown."""
    es_url = os.getenv("ES_URL") or os.getenv("ES_LOCAL_URL", "http://localhost:9200")
    _, basic_auth, _ = get_integration_test_config()
    request = urllib.request.Request(
        f"{es_url}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    if basic_auth:
        token = base64.b64encode(f"{basic_auth[0]}:{basic_auth[1]}".encode()).decode()
        request.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(request) as response:
        response.read()


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
async def async_kibana_client():
    """Create an AsyncKibana client for testing with automatic configuration."""
    client = create_test_async_kibana_client(auth_method="auto")
    yield client
    await client.close()


@pytest.fixture(scope="module")
def es_index():
    """Create a tiny backing Elasticsearch index; delete it afterwards."""
    index_name = f"{RESOURCE_PREFIX}-idx-{uuid.uuid4().hex[:8]}"
    _es_request(
        "PUT",
        f"/{index_name}",
        {"mappings": {"properties": {"msg": {"type": "keyword"}}}},
    )
    _es_request("POST", f"/{index_name}/_doc?refresh=true", {"msg": "hello"})
    yield index_name
    _es_request("DELETE", f"/{index_name}")


def _cleanup_tool(client, tool_id: str, space_id: str | None = None) -> None:
    """Delete a tool, ignoring the case where it is already gone."""
    try:
        client.agent_builder.delete_tool(tool_id=tool_id, force=True, space_id=space_id)
    except NotFoundError:
        pass


def _cleanup_agent(client, agent_id: str) -> None:
    """Delete an agent, ignoring the case where it is already gone."""
    try:
        client.agent_builder.delete_agent(id=agent_id)
    except NotFoundError:
        pass


def _cleanup_skill(client, skill_id: str) -> None:
    """Delete a skill, ignoring the case where it is already gone."""
    try:
        client.agent_builder.delete_skill(skill_id=skill_id, force=True)
    except NotFoundError:
        pass


class TestAgentBuilderTools:
    """Live tests for the Agent Builder tools API."""

    def test_tool_lifecycle_and_execute(self, kibana_client, es_index):
        """Test create/get/list/update/execute/delete for an ES|QL tool."""
        tool_id = f"{TOOL_NAMESPACE}.lifecycle_{uuid.uuid4().hex[:8]}"
        query = f"FROM {es_index} | LIMIT 5"
        created = kibana_client.agent_builder.create_tool(
            id=tool_id,
            type="esql",
            description="kbnpy lifecycle tool",
            configuration={"query": query, "params": {}},
            tags=["kbnpy"],
        )
        try:
            assert created.body["id"] == tool_id
            assert created.body["type"] == "esql"
            assert created.body["configuration"]["query"] == query
            # The server derives an (empty) parameter schema for the query
            assert created.body["schema"]["type"] == "object"

            fetched = kibana_client.agent_builder.get_tool(tool_id=tool_id)
            assert fetched.body["id"] == tool_id
            assert fetched.body["tags"] == ["kbnpy"]

            listed = kibana_client.agent_builder.list_tools()
            assert any(t["id"] == tool_id for t in listed.body["results"])

            updated = kibana_client.agent_builder.update_tool(
                tool_id=tool_id, description="kbnpy updated tool"
            )
            assert updated.body["description"] == "kbnpy updated tool"

            # A static ES|QL tool executes without an LLM connector
            executed = kibana_client.agent_builder.execute_tool(
                tool_id=tool_id, tool_params={}
            )
            results = executed.body["results"]
            esql_results = [r for r in results if r["type"] == "esql_results"]
            assert esql_results, f"no esql_results in {results}"
            assert esql_results[0]["data"]["values"] == [["hello"]]
        finally:
            _cleanup_tool(kibana_client, tool_id)

        with pytest.raises(NotFoundError):
            kibana_client.agent_builder.get_tool(tool_id=tool_id)

    def test_get_missing_tool_raises_not_found(self, kibana_client):
        """Test that getting a nonexistent tool raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.agent_builder.get_tool(
                tool_id=f"{TOOL_NAMESPACE}.missing_{uuid.uuid4().hex[:8]}"
            )


class TestAgentBuilderAgents:
    """Live tests for the Agent Builder agents API."""

    def test_agent_lifecycle(self, kibana_client):
        """Test create/get/list/update/delete for a custom agent."""
        agent_id = f"{RESOURCE_PREFIX}-agent-{uuid.uuid4().hex[:8]}"
        created = kibana_client.agent_builder.create_agent(
            id=agent_id,
            name="kbnpy agent",
            description="kbnpy integration test agent",
            configuration={
                "instructions": "Be brief.",
                "tools": [{"tool_ids": []}],
            },
            labels=["kbnpy"],
        )
        try:
            assert created.body["id"] == agent_id
            assert created.body["name"] == "kbnpy agent"
            assert created.body["labels"] == ["kbnpy"]

            fetched = kibana_client.agent_builder.get_agent(id=agent_id)
            assert fetched.body["id"] == agent_id
            assert fetched.body["configuration"]["instructions"] == "Be brief."

            listed = kibana_client.agent_builder.list_agents()
            assert any(a["id"] == agent_id for a in listed.body["results"])

            updated = kibana_client.agent_builder.update_agent(
                id=agent_id, description="kbnpy updated agent"
            )
            assert updated.body["description"] == "kbnpy updated agent"
        finally:
            _cleanup_agent(kibana_client, agent_id)

        with pytest.raises(NotFoundError):
            kibana_client.agent_builder.get_agent(id=agent_id)

    def test_builtin_agent_is_listed(self, kibana_client):
        """Test that the built-in Elastic AI agent exists."""
        agent = kibana_client.agent_builder.get_agent(id="elastic-ai-agent")
        assert agent.body["id"] == "elastic-ai-agent"
        assert agent.body["type"] == "chat"

    def test_get_agent_consumption(self, kibana_client):
        """Test the consumption endpoint for the built-in agent.

        The backing ``.chat-conversations`` index is created lazily by the
        first persisted conversation; on a stack that has never run a
        conversation the endpoint returns a 500 index_not_found error.
        """
        try:
            consumption = kibana_client.agent_builder.get_agent_consumption(
                agent_id="elastic-ai-agent", size=5, sort_order="desc"
            )
        except ApiError as exc:
            if "index_not_found" in str(exc):
                pytest.skip(
                    "consumption backing index .chat-conversations does not "
                    "exist yet (no conversation has ever been persisted on "
                    "this stack; conversations require an LLM connector)"
                )
            raise
        assert "results" in consumption.body


class TestAgentBuilderConversations:
    """Live tests for the Agent Builder conversations API."""

    def test_list_conversations(self, kibana_client):
        """Test that conversations can be listed (with and without a filter)."""
        listed = kibana_client.agent_builder.list_conversations()
        assert isinstance(listed.body["results"], list)

        filtered = kibana_client.agent_builder.list_conversations(
            agent_id="elastic-ai-agent"
        )
        assert isinstance(filtered.body["results"], list)

    def test_get_missing_conversation_raises_not_found(self, kibana_client):
        """Test that getting a nonexistent conversation raises NotFoundError."""
        with pytest.raises(NotFoundError, match="not found"):
            kibana_client.agent_builder.get_conversation(
                conversation_id=MISSING_CONVERSATION_ID
            )

    def test_delete_missing_conversation_raises_not_found(self, kibana_client):
        """Test that deleting a nonexistent conversation raises NotFoundError."""
        with pytest.raises(NotFoundError, match="not found"):
            kibana_client.agent_builder.delete_conversation(
                conversation_id=MISSING_CONVERSATION_ID
            )


class TestAgentBuilderAttachments:
    """Live tests for the conversation attachments API.

    Creating a real conversation requires a working LLM connector, which the
    test stack does not have; every attachment route is exercised against a
    nonexistent conversation and must come back with the API's specific
    "Conversation ... not found" 404 (proving the route and request shape
    are accepted by the live server).
    """

    def test_list_attachments_missing_conversation(self, kibana_client):
        """Test the list attachments route against the live server."""
        with pytest.raises(NotFoundError, match="not found"):
            kibana_client.agent_builder.list_attachments(
                conversation_id=MISSING_CONVERSATION_ID, include_deleted=True
            )

    def test_create_attachment_missing_conversation(self, kibana_client):
        """Test the create attachment route against the live server."""
        with pytest.raises(NotFoundError, match="not found"):
            kibana_client.agent_builder.create_attachment(
                conversation_id=MISSING_CONVERSATION_ID,
                type="text",
                data="kbnpy attachment",
                description="kbnpy",
            )

    def test_update_attachment_missing_conversation(self, kibana_client):
        """Test the update attachment route against the live server."""
        with pytest.raises(NotFoundError, match="not found"):
            kibana_client.agent_builder.update_attachment(
                conversation_id=MISSING_CONVERSATION_ID,
                attachment_id="att-1",
                data="updated",
            )

    def test_rename_attachment_missing_conversation(self, kibana_client):
        """Test the rename attachment route against the live server."""
        with pytest.raises(NotFoundError, match="not found"):
            kibana_client.agent_builder.rename_attachment(
                conversation_id=MISSING_CONVERSATION_ID,
                attachment_id="att-1",
                description="renamed",
            )

    def test_delete_attachment_missing_conversation(self, kibana_client):
        """Test the delete attachment route against the live server."""
        with pytest.raises(NotFoundError, match="not found"):
            kibana_client.agent_builder.delete_attachment(
                conversation_id=MISSING_CONVERSATION_ID,
                attachment_id="att-1",
                permanent=True,
            )

    def test_restore_attachment_missing_conversation(self, kibana_client):
        """Test the restore attachment route against the live server."""
        with pytest.raises(NotFoundError, match="not found"):
            kibana_client.agent_builder.restore_attachment(
                conversation_id=MISSING_CONVERSATION_ID, attachment_id="att-1"
            )

    def test_update_attachment_origin_missing_conversation(self, kibana_client):
        """Test the update attachment origin route against the live server."""
        with pytest.raises(NotFoundError, match="not found"):
            kibana_client.agent_builder.update_attachment_origin(
                conversation_id=MISSING_CONVERSATION_ID,
                attachment_id="att-1",
                origin="abc123",
            )

    def test_check_stale_attachments_missing_conversation(self, kibana_client):
        """Test the attachment staleness route against the live server."""
        with pytest.raises(NotFoundError, match="not found"):
            kibana_client.agent_builder.check_stale_attachments(
                conversation_id=MISSING_CONVERSATION_ID
            )


class TestAgentBuilderConverse:
    """Live tests for the converse APIs."""

    def test_converse_validation_error(self, kibana_client):
        """Test that the live server rejects an invalid action value."""
        with pytest.raises(BadRequestError, match="request body.action"):
            kibana_client.agent_builder.converse(input="hi", action="bogus")

    def test_converse_async_validation_error(self, kibana_client):
        """Test that the SSE endpoint validates the body before streaming."""
        with pytest.raises(BadRequestError, match="request body.action"):
            kibana_client.agent_builder.converse_async(input="hi", action="bogus")

    def test_converse_round_trip(self, kibana_client):
        """Test a full converse round trip (needs a working LLM connector)."""
        try:
            reply = kibana_client.agent_builder.converse(
                input="Reply with the single word: pong"
            )
        except ApiError as exc:
            pytest.skip(
                "converse requires a working LLM connector which the live "
                f"test stack does not provide (server said: {exc.message})"
            )
        conversation_id = reply.body["conversation_id"]
        try:
            assert "response" in reply.body
        finally:
            kibana_client.agent_builder.delete_conversation(
                conversation_id=conversation_id
            )

    def test_converse_async_returns_event_stream(self, kibana_client):
        """Test that converse/async responds with server-sent events.

        Without a working LLM connector the stream still completes with an
        ``event: error`` block, so the SSE transport itself is verified
        either way.
        """
        stream = kibana_client.agent_builder.converse_async(
            input="Reply with the single word: pong"
        )
        assert stream.meta.status == 200
        assert isinstance(stream.body, str)
        assert "event:" in stream.body
        assert "data:" in stream.body


class TestAgentBuilderA2A:
    """Live tests for the A2A protocol endpoints."""

    def test_get_a2a_card(self, kibana_client):
        """Test fetching the built-in agent's A2A card."""
        card = kibana_client.agent_builder.get_a2a_card(agent_id="elastic-ai-agent")
        assert card.body["name"] == "Elastic AI Agent"
        assert card.body["protocolVersion"]
        assert "capabilities" in card.body

    def test_send_a2a_task(self, kibana_client):
        """Test sending a JSON-RPC message/send task.

        The A2A endpoint answers with a JSON-RPC envelope even when no LLM
        connector is available (the failure is reported inside the result
        message), so the protocol round trip is verified either way.
        """
        response = kibana_client.agent_builder.send_a2a_task(
            agent_id="elastic-ai-agent",
            payload={
                "jsonrpc": "2.0",
                "id": f"{RESOURCE_PREFIX}-task-1",
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": "Hello"}],
                        "messageId": f"{RESOURCE_PREFIX}-msg-1",
                    }
                },
            },
        )
        assert response.body["jsonrpc"] == "2.0"
        assert "result" in response.body or "error" in response.body


class TestAgentBuilderMcp:
    """Live tests for the MCP server endpoint."""

    def test_mcp_initialize(self, kibana_client):
        """Test the MCP initialize handshake."""
        response = kibana_client.agent_builder.send_mcp_request(
            payload={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "kibana-py-tests", "version": "1.0.0"},
                },
            }
        )
        assert response.body["result"]["serverInfo"]["name"] == "elastic-mcp-server"

    def test_mcp_tools_list_with_namespace_filter(self, kibana_client):
        """Test listing MCP tools filtered to the platform.core namespace."""
        response = kibana_client.agent_builder.send_mcp_request(
            payload={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            namespace="platform.core",
        )
        tools = response.body["result"]["tools"]
        assert tools
        assert all(t["name"].startswith("platform_core_") for t in tools)


class TestAgentBuilderSkills:
    """Live tests for the Agent Builder skills API (technical preview)."""

    def test_skill_lifecycle(self, kibana_client):
        """Test create/get/list/update/delete for a skill."""
        skill_id = f"{RESOURCE_PREFIX}-skill-{uuid.uuid4().hex[:8]}"
        created = kibana_client.agent_builder.create_skill(
            id=skill_id,
            name="kbnpy skill",
            description="kbnpy integration test skill",
            content="# kbnpy\nBe brief.",
        )
        try:
            assert created.body["id"] == skill_id
            assert created.body["content"] == "# kbnpy\nBe brief."

            fetched = kibana_client.agent_builder.get_skill(skill_id=skill_id)
            assert fetched.body["name"] == "kbnpy skill"

            listed = kibana_client.agent_builder.list_skills(include_plugins=False)
            assert any(s["id"] == skill_id for s in listed.body["results"])

            updated = kibana_client.agent_builder.update_skill(
                skill_id=skill_id, description="kbnpy updated skill"
            )
            assert updated.body["description"] == "kbnpy updated skill"
        finally:
            _cleanup_skill(kibana_client, skill_id)

        with pytest.raises(NotFoundError):
            kibana_client.agent_builder.get_skill(skill_id=skill_id)


class TestAgentBuilderPlugins:
    """Live tests for the Agent Builder plugins API (technical preview).

    On the default Kibana 9.4.3 configuration the plugins routes are not
    registered (feature-flag gated) and every call returns a plain 404, in
    contrast to the OpenAPI spec which documents them unconditionally.
    """

    def test_list_plugins(self, kibana_client):
        """Test listing plugins, tolerating the feature-flagged 404."""
        try:
            listed = kibana_client.agent_builder.list_plugins()
        except NotFoundError:
            pytest.skip(
                "plugins API is not enabled on this Kibana 9.4.3 stack "
                "(technical-preview routes are feature-flag gated and "
                "return 404)"
            )
        assert isinstance(listed.body, dict)

    def test_get_missing_plugin_raises_not_found(self, kibana_client):
        """Test that a missing plugin (or disabled plugins API) yields 404."""
        with pytest.raises(NotFoundError):
            kibana_client.agent_builder.get_plugin(
                plugin_id=f"{RESOURCE_PREFIX}-missing-{uuid.uuid4().hex[:8]}"
            )

    def test_delete_missing_plugin_raises_not_found(self, kibana_client):
        """Test that deleting a missing plugin (or disabled API) yields 404."""
        with pytest.raises(NotFoundError):
            kibana_client.agent_builder.delete_plugin(
                plugin_id=f"{RESOURCE_PREFIX}-missing-{uuid.uuid4().hex[:8]}",
                force=True,
            )

    def test_install_plugin_fails_safely(self, kibana_client):
        """Test that install never succeeds against this stack.

        With the plugins API disabled the route 404s; were it enabled, the
        unreachable URL would still make the install fail, so no plugin is
        ever left behind.
        """
        with pytest.raises(ApiError):
            kibana_client.agent_builder.install_plugin(
                url="http://127.0.0.1:1/kbnpy-nonexistent-plugin.zip"
            )


class TestAgentBuilderSpaceScoped:
    """Space-scoped tests for the Agent Builder API."""

    def test_tool_is_space_scoped(self, kibana_client, es_index):
        """Test that a tool created in a space is not visible elsewhere."""
        space_id = f"{RESOURCE_PREFIX}-{uuid.uuid4().hex[:8]}"
        tool_id = f"{TOOL_NAMESPACE}.spaced_{uuid.uuid4().hex[:8]}"
        kibana_client.spaces.create(id=space_id, name=space_id)
        try:
            created = kibana_client.agent_builder.create_tool(
                id=tool_id,
                type="esql",
                description="kbnpy space-scoped tool",
                configuration={"query": f"FROM {es_index} | LIMIT 1", "params": {}},
                space_id=space_id,
            )
            assert created.body["id"] == tool_id

            # Visible in its own space
            fetched = kibana_client.agent_builder.get_tool(
                tool_id=tool_id, space_id=space_id
            )
            assert fetched.body["id"] == tool_id

            # Not visible in the default space
            with pytest.raises(NotFoundError):
                kibana_client.agent_builder.get_tool(tool_id=tool_id)
        finally:
            _cleanup_tool(kibana_client, tool_id, space_id=space_id)
            kibana_client.spaces.delete(id=space_id)


class TestAsyncAgentBuilder:
    """Async round-trip tests for the Agent Builder API."""

    @pytest.mark.asyncio
    async def test_async_tool_lifecycle_and_execute(
        self, async_kibana_client, es_index
    ):
        """Test the full tool lifecycle with the async client."""
        tool_id = f"{TOOL_NAMESPACE}.async_{uuid.uuid4().hex[:8]}"
        created = await async_kibana_client.agent_builder.create_tool(
            id=tool_id,
            type="esql",
            description="kbnpy async tool",
            configuration={"query": f"FROM {es_index} | LIMIT 5", "params": {}},
        )
        try:
            assert created.body["id"] == tool_id

            fetched = await async_kibana_client.agent_builder.get_tool(tool_id=tool_id)
            assert fetched.body["description"] == "kbnpy async tool"

            executed = await async_kibana_client.agent_builder.execute_tool(
                tool_id=tool_id, tool_params={}
            )
            esql_results = [
                r for r in executed.body["results"] if r["type"] == "esql_results"
            ]
            assert esql_results[0]["data"]["values"] == [["hello"]]
        finally:
            try:
                await async_kibana_client.agent_builder.delete_tool(
                    tool_id=tool_id, force=True
                )
            except NotFoundError:
                pass

        with pytest.raises(NotFoundError):
            await async_kibana_client.agent_builder.get_tool(tool_id=tool_id)

    @pytest.mark.asyncio
    async def test_async_list_agents_and_mcp(self, async_kibana_client):
        """Test async list_agents and an async MCP initialize handshake."""
        agents = await async_kibana_client.agent_builder.list_agents()
        assert any(a["id"] == "elastic-ai-agent" for a in agents.body["results"])

        response = await async_kibana_client.agent_builder.send_mcp_request(
            payload={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "kibana-py-tests", "version": "1.0.0"},
                },
            }
        )
        assert response.body["result"]["serverInfo"]["name"] == "elastic-mcp-server"
