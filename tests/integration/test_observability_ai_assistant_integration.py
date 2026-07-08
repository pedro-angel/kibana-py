"""Integration tests for ObservabilityAiAssistantClient against a live Kibana.

The Observability AI Assistant chat completion API (Technical Preview in
9.4) needs an AI (LLM) connector. The live test stack has no real LLM
credentials, so these tests create a throwaway ``.gen-ai`` connector that
points at an unreachable local port. Kibana accepts the connector and the
chat/complete endpoint still opens its server-sent-event stream (HTTP 200,
``application/octet-stream``) — the stream then carries an error chunk from
the failed LLM call followed by ``data: [DONE]``. That exercises the full
request/streaming path without an actual model. Validating real model
output would require genuine LLM credentials, which the stack lacks.
"""

import uuid

import pytest

from kibana.exceptions import BadRequestError, NotFoundError

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    is_kibana_available,
    safe_delete_connector,
)

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)


def _messages() -> list[dict]:
    """Build a minimal, valid conversation history."""
    return [
        {
            "@timestamp": "2026-07-03T00:00:00.000Z",
            "message": {"role": "user", "content": "Is my cluster healthy?"},
        }
    ]


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


@pytest.fixture
def ai_connector_id(kibana_client):
    """Create a throwaway .gen-ai connector pointing at an unreachable port.

    Kibana does not verify connector credentials at creation time, so the
    connector is accepted; any chat completion through it fails fast with a
    connection error streamed as an SSE error chunk.
    """
    created = kibana_client.actions.create(
        name=f"kbnpy-observability-ai-assistant-{uuid.uuid4().hex[:12]}",
        connector_type_id=".gen-ai",
        config={
            "apiProvider": "OpenAI",
            "apiUrl": "http://localhost:59999/v1/chat/completions",
        },
        secrets={"apiKey": "kbnpy-dummy-key"},
    )
    connector_id = created.body["id"]
    yield connector_id
    safe_delete_connector(kibana_client, connector_id)


class TestObservabilityAiAssistantChatComplete:
    """Live tests for the chat/complete endpoint."""

    def test_chat_complete_streams_sse(self, kibana_client, ai_connector_id):
        """Test that a chat completion opens an SSE stream (HTTP 200)."""
        response = kibana_client.observability_ai_assistant.chat_complete(
            messages=_messages(),
            connector_id=ai_connector_id,
            persist=False,
            disable_functions=True,
            instructions=["Answer concisely."],
            title="kbnpy-observability-ai-assistant smoke conversation",
        )

        assert response.meta.status == 200
        # Kibana 9.4.3 serves the stream as application/octet-stream bytes.
        assert response.meta.headers.get("content-type", "").startswith(
            "application/octet-stream"
        )
        assert isinstance(response.body, bytes)
        # The stream is SSE-framed and always terminated by data: [DONE];
        # with the dummy connector the single event is an LLM error chunk.
        assert b"data: " in response.body
        assert b"data: [DONE]" in response.body

    def test_chat_complete_space_scoped(self, kibana_client, ai_connector_id):
        """Test chat completion through the /s/{space_id} path prefix."""
        response = kibana_client.observability_ai_assistant.chat_complete(
            messages=_messages(),
            connector_id=ai_connector_id,
            persist=False,
            disable_functions=True,
            space_id="default",
        )

        assert response.meta.status == 200
        assert b"data: [DONE]" in response.body

    def test_chat_complete_unknown_connector_raises_not_found(self, kibana_client):
        """Test the live 404 for a connector ID that does not exist."""
        missing_id = f"kbnpy-observability-ai-assistant-missing-{uuid.uuid4().hex[:8]}"
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.observability_ai_assistant.chat_complete(
                messages=_messages(),
                connector_id=missing_id,
                persist=False,
            )
        assert "No connector or inference endpoint found" in str(exc_info.value)

    def test_chat_complete_invalid_message_shape_raises_bad_request(
        self, kibana_client, ai_connector_id
    ):
        """Test the live 400 when a message misses required fields."""
        with pytest.raises(BadRequestError) as exc_info:
            kibana_client.observability_ai_assistant.chat_complete(
                # Missing the required @timestamp field.
                messages=[{"message": {"role": "user", "content": "hi"}}],
                connector_id=ai_connector_id,
                persist=False,
            )
        assert "Failed to validate" in str(exc_info.value)


class TestAsyncObservabilityAiAssistantChatComplete:
    """Async live round-trip for the chat/complete endpoint."""

    @pytest.mark.asyncio
    async def test_async_chat_complete_streams_sse(
        self, async_kibana_client, ai_connector_id
    ):
        """Test the async chat completion SSE round-trip."""
        response = await async_kibana_client.observability_ai_assistant.chat_complete(
            messages=_messages(),
            connector_id=ai_connector_id,
            persist=False,
            disable_functions=True,
        )

        assert response.meta.status == 200
        assert isinstance(response.body, bytes)
        assert b"data: [DONE]" in response.body

    @pytest.mark.asyncio
    async def test_async_chat_complete_unknown_connector_raises_not_found(
        self, async_kibana_client
    ):
        """Test the live 404 for an unknown connector via the async client."""
        missing_id = f"kbnpy-observability-ai-assistant-missing-{uuid.uuid4().hex[:8]}"
        with pytest.raises(NotFoundError):
            await async_kibana_client.observability_ai_assistant.chat_complete(
                messages=_messages(),
                connector_id=missing_id,
                persist=False,
            )
