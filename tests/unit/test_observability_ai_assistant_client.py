"""Unit tests for ObservabilityAiAssistantClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import BinaryApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.observability_ai_assistant import (
    ObservabilityAiAssistantClient,
)
from kibana.exceptions import BadRequestError, NotFoundError

CHAT_COMPLETE_PATH = "/api/observability_ai_assistant/chat/complete"


def _messages() -> list[dict]:
    """Build a minimal, valid conversation history."""
    return [
        {
            "@timestamp": "2026-07-03T00:00:00.000Z",
            "message": {"role": "user", "content": "Is my cluster healthy?"},
        }
    ]


def _sse_stream_body() -> bytes:
    """Kibana 9.4.3 chat/complete 200 body: a raw SSE chunk stream."""
    return (
        b'data: {"model":"unknown","choices":[{"delta":{"content":"Yes."},'
        b'"finish_reason":null,"index":0}],"created":1750936626911,'
        b'"id":"9c8eff9b-4fd4-4203-a4ab-2e364688deff",'
        b'"object":"chat.completion.chunk"}\n\n'
        b"data: [DONE]\n\n"
    )


def _sse_response() -> BinaryApiResponse:
    """Wrap the SSE stream in the response type the live server produces."""
    return BinaryApiResponse(
        body=_sse_stream_body(),
        meta=Mock(status=200, headers={"content-type": "application/octet-stream"}),
    )


class TestObservabilityAiAssistantClientInitialization:
    """Test ObservabilityAiAssistantClient initialization."""

    def test_client_initialization(self, mock_transport):
        """Test that the client can be initialized with a parent client."""
        client = Kibana(_transport=mock_transport)
        ai_client = ObservabilityAiAssistantClient(client)
        assert ai_client._client is client

    def test_property_returns_client(self, mock_transport):
        """Test that client.observability_ai_assistant returns the right type."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(
            client.observability_ai_assistant, ObservabilityAiAssistantClient
        )

    def test_property_caching(self, mock_transport):
        """Test that the property returns the same instance."""
        client = Kibana(_transport=mock_transport)
        assert client.observability_ai_assistant is client.observability_ai_assistant


class TestObservabilityAiAssistantChatComplete:
    """Test ObservabilityAiAssistantClient.chat_complete() method."""

    def test_chat_complete_minimal(self, mock_transport):
        """Test chat completion with only the required parameters."""
        mock_transport.perform_request.return_value = _sse_response()

        client = Kibana(_transport=mock_transport)
        result = client.observability_ai_assistant.chat_complete(
            messages=_messages(),
            connector_id="my-connector",
            persist=False,
        )

        assert result.meta.status == 200
        assert b"data: [DONE]" in result.body

        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == CHAT_COMPLETE_PATH
        assert call_kwargs["body"] == {
            "messages": _messages(),
            "connectorId": "my-connector",
            "persist": False,
        }
        assert call_kwargs["headers"]["accept"] == (
            "text/event-stream, application/json"
        )
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_chat_complete_all_params(self, mock_transport):
        """Test that every optional parameter maps to its camelCase body key."""
        mock_transport.perform_request.return_value = _sse_response()

        actions = [
            {
                "name": "get_cluster_health",
                "description": "Fetch cluster health.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "includeShardStats": {"type": "boolean", "default": False}
                    },
                },
            }
        ]
        instructions = [
            "Answer concisely.",
            {"id": "instr-1", "text": "Use the get_cluster_health tool."},
        ]

        client = Kibana(_transport=mock_transport)
        client.observability_ai_assistant.chat_complete(
            messages=_messages(),
            connector_id="my-connector",
            persist=True,
            actions=actions,
            conversation_id="conv-123",
            disable_functions=False,
            instructions=instructions,
            title="Cluster health check",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == CHAT_COMPLETE_PATH
        assert call_kwargs["body"] == {
            "messages": _messages(),
            "connectorId": "my-connector",
            "persist": True,
            "actions": actions,
            "conversationId": "conv-123",
            "disableFunctions": False,
            "instructions": instructions,
            "title": "Cluster health check",
        }

    def test_chat_complete_omits_unset_optionals(self, mock_transport):
        """Test that unset optional parameters are not sent in the body."""
        mock_transport.perform_request.return_value = _sse_response()

        client = Kibana(_transport=mock_transport)
        client.observability_ai_assistant.chat_complete(
            messages=_messages(),
            connector_id="my-connector",
            persist=False,
        )

        body = mock_transport.perform_request.call_args[1]["body"]
        for key in (
            "actions",
            "conversationId",
            "disableFunctions",
            "instructions",
            "title",
        ):
            assert key not in body

    def test_chat_complete_space_scoped(self, mock_transport):
        """Test that space_id prefixes the path with /s/{space_id}."""
        mock_transport.perform_request.return_value = _sse_response()

        client = Kibana(_transport=mock_transport)
        client.observability_ai_assistant.chat_complete(
            messages=_messages(),
            connector_id="my-connector",
            persist=False,
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == f"/s/marketing{CHAT_COMPLETE_PATH}"


class TestObservabilityAiAssistantErrorHandling:
    """Test ObservabilityAiAssistantClient error handling."""

    def test_chat_complete_unknown_connector_not_found(
        self, mock_transport, mock_response
    ):
        """Test the live 404 shape for an unknown connector ID."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": (
                    "No connector or inference endpoint found for ID 'missing'"
                ),
                "attributes": {"data": None},
            },
            status=404,
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(NotFoundError, match="No connector or inference"):
            client.observability_ai_assistant.chat_complete(
                messages=_messages(),
                connector_id="missing",
                persist=False,
            )

    def test_chat_complete_validation_error(self, mock_transport, mock_response):
        """Test the live 400 shape when the body fails schema validation."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 400,
                "error": "Bad Request",
                "message": (
                    "Failed to validate: in /0/connectorId: undefined does "
                    "not match expected type string"
                ),
                "attributes": {"data": None},
            },
            status=400,
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(BadRequestError, match="Failed to validate"):
            client.observability_ai_assistant.chat_complete(
                messages=_messages(),
                connector_id="",
                persist=False,
            )
