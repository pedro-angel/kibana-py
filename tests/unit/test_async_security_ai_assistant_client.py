"""Unit tests for AsyncSecurityAiAssistantClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._async.client import AsyncKibana
from kibana._async.client.security_ai_assistant import (
    AsyncSecurityAiAssistantClient,
)


def _response(body: dict) -> ObjectApiResponse:
    """Build a mocked 200 ObjectApiResponse."""
    return ObjectApiResponse(body=body, meta=Mock(status=200, headers={}))


def _conversation_body() -> dict:
    """Kibana 9.4.3 conversation response body."""
    return {
        "id": "abc123",
        "title": "Security Discussion",
        "category": "assistant",
        "createdAt": "2026-01-01T12:01:00Z",
        "createdBy": {"id": "u_1", "name": "elastic"},
        "users": [{"id": "u_1", "name": "elastic"}],
        "messages": [
            {
                "id": "m1",
                "content": "hello",
                "role": "user",
                "timestamp": "2026-01-01T12:00:00Z",
            }
        ],
        "namespace": "default",
    }


def _kb_entry_body() -> dict:
    """Kibana 9.4.3 knowledge base document entry response body."""
    return {
        "id": "kb123",
        "createdAt": "2026-01-01T12:00:00Z",
        "createdBy": "u_1",
        "updatedAt": "2026-01-01T12:00:00Z",
        "updatedBy": "u_1",
        "global": False,
        "users": [{"id": "u_1", "name": "elastic"}],
        "name": "Example Entry",
        "namespace": "default",
        "type": "document",
        "kbResource": "user",
        "source": "/documents/example.txt",
        "required": False,
        "text": "This is the content of the document.",
    }


class TestAsyncSecurityAiAssistantClientInitialization:
    """Test AsyncSecurityAiAssistantClient initialization and wiring."""

    async def test_initialization(self, mock_async_transport):
        client = AsyncKibana(_transport=mock_async_transport)
        ns_client = AsyncSecurityAiAssistantClient(client)
        assert ns_client._client is client

    async def test_property_returns_client(self, mock_async_transport):
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.security_ai_assistant, AsyncSecurityAiAssistantClient)


class TestConversations:
    """Test conversation CRUD, find, and delete-all methods."""

    async def test_create_conversation(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(
            _conversation_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.security_ai_assistant.create_conversation(
            title="Security Discussion",
            category="assistant",
            exclude_from_last_conversation_storage=False,
            messages=[
                {
                    "content": "hello",
                    "role": "user",
                    "timestamp": "2026-01-01T12:00:00Z",
                }
            ],
            replacements={},
            api_config={"connectorId": "conn1", "actionTypeId": ".gen-ai"},
        )

        assert result.body["id"] == "abc123"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert (
            call_kwargs["target"]
            == "/api/security_ai_assistant/current_user/conversations"
        )
        assert call_kwargs["body"] == {
            "title": "Security Discussion",
            "category": "assistant",
            "excludeFromLastConversationStorage": False,
            "messages": [
                {
                    "content": "hello",
                    "role": "user",
                    "timestamp": "2026-01-01T12:00:00Z",
                }
            ],
            "replacements": {},
            "apiConfig": {"connectorId": "conn1", "actionTypeId": ".gen-ai"},
        }

    async def test_get_conversation(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(
            _conversation_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.security_ai_assistant.get_conversation(id="abc 123")

        assert result.body["title"] == "Security Discussion"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        # Path parameter must be URL-encoded
        assert (
            call_kwargs["target"]
            == "/api/security_ai_assistant/current_user/conversations/abc%20123"
        )

    async def test_update_conversation(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(
            _conversation_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.security_ai_assistant.update_conversation(
            id="abc123",
            title="Updated Security Discussion",
            category="insights",
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert (
            call_kwargs["target"]
            == "/api/security_ai_assistant/current_user/conversations/abc123"
        )
        # The body must include the id alongside the updated fields
        assert call_kwargs["body"] == {
            "id": "abc123",
            "title": "Updated Security Discussion",
            "category": "insights",
        }

    async def test_delete_conversation(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response({})

        client = AsyncKibana(_transport=mock_async_transport)
        await client.security_ai_assistant.delete_conversation(id="abc123")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert (
            call_kwargs["target"]
            == "/api/security_ai_assistant/current_user/conversations/abc123"
        )

    async def test_find_conversations_param_encoding(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(
            {"page": 1, "perPage": 20, "total": 0, "data": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.security_ai_assistant.find_conversations(
            filter="Security",
            sort_field="created_at",
            sort_order="desc",
            page=2,
            per_page=5,
            is_owner=True,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/security_ai_assistant/current_user/conversations/_find"
            "?filter=Security&sort_field=created_at&sort_order=desc"
            "&page=2&per_page=5&is_owner=true"
        )

    async def test_find_conversations_without_params(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(
            {"page": 1, "perPage": 20, "total": 0, "data": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.security_ai_assistant.find_conversations()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == "/api/security_ai_assistant/current_user/conversations/_find"
        )

    async def test_delete_all_conversations(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(
            {"success": True, "totalDeleted": 2, "failures": None}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.security_ai_assistant.delete_all_conversations(
            excluded_ids=["abc123", "def456"]
        )

        assert result.body["success"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert (
            call_kwargs["target"]
            == "/api/security_ai_assistant/current_user/conversations"
        )
        assert call_kwargs["body"] == {"excludedIds": ["abc123", "def456"]}

    async def test_delete_all_conversations_without_body(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response({"success": True})

        client = AsyncKibana(_transport=mock_async_transport)
        await client.security_ai_assistant.delete_all_conversations()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs.get("body") is None


class TestPrompts:
    """Test prompt find and bulk action methods."""

    async def test_find_prompts_param_encoding(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(
            {"page": 1, "perPage": 20, "total": 0, "data": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.security_ai_assistant.find_prompts(
            fields=["id", "name"],
            filter="security",
            sort_field="name",
            sort_order="asc",
            page=1,
            per_page=10,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/security_ai_assistant/prompts/_find"
            "?fields=id&fields=name&filter=security&sort_field=name"
            "&sort_order=asc&page=1&per_page=10"
        )

    async def test_bulk_action_prompts(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(
            {
                "success": True,
                "prompts_count": 3,
                "attributes": {
                    "results": {
                        "created": [],
                        "updated": [],
                        "deleted": [],
                        "skipped": [],
                    },
                    "summary": {
                        "failed": 0,
                        "skipped": 0,
                        "succeeded": 3,
                        "total": 3,
                    },
                },
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.security_ai_assistant.bulk_action_prompts(
            create=[
                {"name": "P1", "content": "content 1", "promptType": "quick"},
            ],
            update=[{"id": "prompt1", "content": "updated"}],
            delete={"ids": ["prompt2"]},
        )

        assert result.body["success"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert (
            call_kwargs["target"] == "/api/security_ai_assistant/prompts/_bulk_action"
        )
        assert call_kwargs["body"] == {
            "create": [
                {"name": "P1", "content": "content 1", "promptType": "quick"},
            ],
            "update": [{"id": "prompt1", "content": "updated"}],
            "delete": {"ids": ["prompt2"]},
        }


class TestAnonymizationFields:
    """Test anonymization field find and bulk action methods."""

    async def test_find_anonymization_fields_param_encoding(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(
            {"page": 1, "perPage": 20, "total": 0, "data": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.security_ai_assistant.find_anonymization_fields(
            filter='field: "host.name"',
            sort_field="field",
            sort_order="asc",
            page=1,
            per_page=100,
            all_data=True,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/security_ai_assistant/anonymization_fields/_find"
            "?filter=field%3A+%22host.name%22&sort_field=field&sort_order=asc"
            "&page=1&per_page=100&all_data=true"
        )

    async def test_bulk_action_anonymization_fields(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(
            {
                "success": True,
                "anonymization_fields_count": 1,
                "attributes": {
                    "results": {
                        "created": [],
                        "updated": [],
                        "deleted": ["field1"],
                        "skipped": [],
                    },
                    "summary": {
                        "failed": 0,
                        "skipped": 0,
                        "succeeded": 1,
                        "total": 1,
                    },
                },
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.security_ai_assistant.bulk_action_anonymization_fields(
            create=[{"field": "host.name", "allowed": True, "anonymized": False}],
            delete={"ids": ["field1"]},
        )

        assert result.body["attributes"]["results"]["deleted"] == ["field1"]
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert (
            call_kwargs["target"]
            == "/api/security_ai_assistant/anonymization_fields/_bulk_action"
        )
        assert call_kwargs["body"] == {
            "create": [{"field": "host.name", "allowed": True, "anonymized": False}],
            "delete": {"ids": ["field1"]},
        }


class TestKnowledgeBaseSetup:
    """Test Knowledge Base status and setup methods."""

    async def test_get_knowledge_base(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(
            {
                "elser_exists": True,
                "is_setup_available": True,
                "is_setup_in_progress": False,
                "security_labs_exists": False,
                "defend_insights_exists": False,
                "user_data_exists": False,
                "product_documentation_status": "installed",
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.security_ai_assistant.get_knowledge_base()

        assert result.body["elser_exists"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/security_ai_assistant/knowledge_base"

    async def test_get_knowledge_base_for_resource(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(
            {"elser_exists": True}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.security_ai_assistant.get_knowledge_base(resource="security_labs")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == "/api/security_ai_assistant/knowledge_base/security_labs"
        )

    async def test_setup_knowledge_base(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response({"success": True})

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.security_ai_assistant.setup_knowledge_base(
            model_id="elser-model-001",
            ignore_security_labs=True,
        )

        assert result.body["success"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/security_ai_assistant/knowledge_base"
            "?modelId=elser-model-001&ignoreSecurityLabs=true"
        )

    async def test_setup_knowledge_base_for_resource(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response({"success": True})

        client = AsyncKibana(_transport=mock_async_transport)
        await client.security_ai_assistant.setup_knowledge_base(resource="user")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/security_ai_assistant/knowledge_base/user"


class TestKnowledgeBaseEntries:
    """Test Knowledge Base entry CRUD, find and bulk action methods."""

    async def test_create_knowledge_base_entry_document(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(_kb_entry_body())

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.security_ai_assistant.create_knowledge_base_entry(
            type="document",
            name="Example Entry",
            kb_resource="user",
            source="/documents/example.txt",
            text="This is the content of the document.",
            required=False,
            global_=False,
        )

        assert result.body["id"] == "kb123"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert (
            call_kwargs["target"] == "/api/security_ai_assistant/knowledge_base/entries"
        )
        assert call_kwargs["body"] == {
            "type": "document",
            "name": "Example Entry",
            "kbResource": "user",
            "source": "/documents/example.txt",
            "text": "This is the content of the document.",
            "required": False,
            "global": False,
        }

    async def test_create_knowledge_base_entry_index(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response({"id": "kb456"})

        client = AsyncKibana(_transport=mock_async_transport)
        await client.security_ai_assistant.create_knowledge_base_entry(
            type="index",
            name="KB index entry",
            index="knowledge-base-index",
            field="content",
            description="Query this index for KB content.",
            query_description="Search for documents with the given keywords.",
            input_schema=[
                {
                    "fieldName": "title",
                    "fieldType": "string",
                    "description": "The title of the document.",
                }
            ],
            output_fields=["title", "content"],
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "type": "index",
            "name": "KB index entry",
            "index": "knowledge-base-index",
            "field": "content",
            "description": "Query this index for KB content.",
            "queryDescription": "Search for documents with the given keywords.",
            "inputSchema": [
                {
                    "fieldName": "title",
                    "fieldType": "string",
                    "description": "The title of the document.",
                }
            ],
            "outputFields": ["title", "content"],
        }

    async def test_get_knowledge_base_entry(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(_kb_entry_body())

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.security_ai_assistant.get_knowledge_base_entry(id="kb123")

        assert result.body["name"] == "Example Entry"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert (
            call_kwargs["target"]
            == "/api/security_ai_assistant/knowledge_base/entries/kb123"
        )

    async def test_update_knowledge_base_entry(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(_kb_entry_body())

        client = AsyncKibana(_transport=mock_async_transport)
        await client.security_ai_assistant.update_knowledge_base_entry(
            id="kb123",
            type="document",
            name="Example Entry (updated)",
            kb_resource="user",
            source="/documents/example.txt",
            text="Updated content.",
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert (
            call_kwargs["target"]
            == "/api/security_ai_assistant/knowledge_base/entries/kb123"
        )
        assert call_kwargs["body"] == {
            "type": "document",
            "name": "Example Entry (updated)",
            "kbResource": "user",
            "source": "/documents/example.txt",
            "text": "Updated content.",
        }

    async def test_delete_knowledge_base_entry(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response({"id": "kb123"})

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.security_ai_assistant.delete_knowledge_base_entry(
            id="kb123"
        )

        assert result.body["id"] == "kb123"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert (
            call_kwargs["target"]
            == "/api/security_ai_assistant/knowledge_base/entries/kb123"
        )

    async def test_find_knowledge_base_entries_param_encoding(
        self, mock_async_transport
    ):
        mock_async_transport.perform_request.return_value = _response(
            {"page": 1, "perPage": 20, "total": 0, "data": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.security_ai_assistant.find_knowledge_base_entries(
            filter="runbook",
            sort_field="created_at",
            sort_order="desc",
            page=1,
            per_page=25,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/security_ai_assistant/knowledge_base/entries/_find"
            "?filter=runbook&sort_field=created_at&sort_order=desc&page=1&per_page=25"
        )

    async def test_bulk_action_knowledge_base_entries(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(
            {
                "success": True,
                "attributes": {
                    "results": {
                        "created": [],
                        "updated": [],
                        "deleted": ["kb123"],
                        "skipped": [],
                    },
                    "summary": {
                        "failed": 0,
                        "skipped": 0,
                        "succeeded": 1,
                        "total": 1,
                    },
                },
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.security_ai_assistant.bulk_action_knowledge_base_entries(
            delete={"ids": ["kb123"]},
        )

        assert result.body["attributes"]["results"]["deleted"] == ["kb123"]
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert (
            call_kwargs["target"]
            == "/api/security_ai_assistant/knowledge_base/entries/_bulk_action"
        )
        assert call_kwargs["body"] == {"delete": {"ids": ["kb123"]}}


class TestChatComplete:
    """Test the chat/complete method."""

    async def test_chat_complete(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(
            {
                "connector_id": "conn-001",
                "data": "pong",
                "trace_data": {},
                "replacements": {},
                "status": "ok",
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.security_ai_assistant.chat_complete(
            connector_id="conn-001",
            messages=[{"role": "user", "content": "ping"}],
            persist=False,
            is_stream=False,
            model="gpt-4",
            response_language="en",
            content_references_disabled=True,
        )

        assert result.body["data"] == "pong"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/security_ai_assistant/chat/complete"
            "?content_references_disabled=true"
        )
        assert call_kwargs["body"] == {
            "connectorId": "conn-001",
            "messages": [{"role": "user", "content": "ping"}],
            "persist": False,
            "isStream": False,
            "model": "gpt-4",
            "responseLanguage": "en",
        }

    async def test_chat_complete_minimal_body(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response({"status": "ok"})

        client = AsyncKibana(_transport=mock_async_transport)
        await client.security_ai_assistant.chat_complete(
            connector_id="conn-001",
            messages=[{"role": "user", "content": "ping"}],
            persist=True,
            conversation_id="abc123",
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/security_ai_assistant/chat/complete"
        assert call_kwargs["body"] == {
            "connectorId": "conn-001",
            "messages": [{"role": "user", "content": "ping"}],
            "persist": True,
            "conversationId": "abc123",
        }


class TestSecurityAiAssistantSpaceScoping:
    """Test space-scoped path building."""

    async def test_space_scoped_find_conversations(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(
            {"page": 1, "perPage": 20, "total": 0, "data": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.security_ai_assistant.find_conversations(
            space_id="team-a", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/s/team-a/api/security_ai_assistant/current_user/conversations/_find"
        )

    async def test_space_scoped_chat_complete(self, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response({"status": "ok"})

        client = AsyncKibana(_transport=mock_async_transport)
        await client.security_ai_assistant.chat_complete(
            connector_id="conn-001",
            messages=[{"role": "user", "content": "ping"}],
            persist=False,
            space_id="team-a",
            validate_spaces=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"] == "/s/team-a/api/security_ai_assistant/chat/complete"
        )


class TestSecurityAiAssistantErrorHandling:
    """Test error mapping for the Security AI Assistant client."""

    async def test_get_conversation_not_found(self, mock_async_transport):
        from kibana.exceptions import NotFoundError

        mock_async_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "message": 'conversation id: "missing" not found',
                "status_code": 404,
            },
            meta=Mock(status=404, headers={}),
        )

        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(NotFoundError):
            await client.security_ai_assistant.get_conversation(id="missing")

    async def test_chat_complete_bad_request(self, mock_async_transport):
        from kibana.exceptions import BadRequestError

        mock_async_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 400,
                "error": "Bad Request",
                "message": "[request body]: connectorId: Required",
            },
            meta=Mock(status=400, headers={}),
        )

        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(BadRequestError):
            await client.security_ai_assistant.chat_complete(
                connector_id="",
                messages=[],
                persist=False,
            )
