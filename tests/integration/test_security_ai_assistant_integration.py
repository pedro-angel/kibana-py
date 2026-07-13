"""Integration tests for SecurityAiAssistantClient against a live Kibana instance.

The chat/complete test requires a live OpenAI-compatible LLM backend and is
gated on the ``KBNPY_LMSTUDIO_OPENAI_URL`` environment variable (the base
URL of the backend, e.g. ``http://host.docker.internal:1234/v1`` as reachable
from the Kibana container). ``KBNPY_LMSTUDIO_MODEL`` selects the model.
"""

import os
import uuid

import pytest

from kibana.exceptions import ApiError, NotFoundError

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    is_kibana_available,
)

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)

PREFIX = "kbnpy-security_ai_assistant"

LMSTUDIO_URL = os.getenv("KBNPY_LMSTUDIO_OPENAI_URL")
LMSTUDIO_MODEL = os.getenv("KBNPY_LMSTUDIO_MODEL", "qwen/qwen3.5-9b")

# Timeout for real LLM round-trips (local models can be slow)
CHAT_REQUEST_TIMEOUT = 120.0


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
def unique_suffix():
    """Generate a unique suffix for test resource names."""
    return uuid.uuid4().hex[:12]


def _cleanup_conversation(client, conversation_id: str) -> None:
    """Delete a conversation, ignoring the case where it is already gone."""
    try:
        client.security_ai_assistant.delete_conversation(id=conversation_id)
    except NotFoundError:
        pass


def _cleanup_prompts(client, prompt_ids: list[str]) -> None:
    """Bulk-delete prompts, ignoring failures for already-deleted prompts."""
    if not prompt_ids:
        return
    try:
        client.security_ai_assistant.bulk_action_prompts(delete={"ids": prompt_ids})
    except ApiError:
        pass


def _cleanup_anonymization_fields(client, field_ids: list[str]) -> None:
    """Bulk-delete anonymization fields, ignoring already-deleted failures."""
    if not field_ids:
        return
    try:
        client.security_ai_assistant.bulk_action_anonymization_fields(
            delete={"ids": field_ids}
        )
    except ApiError:
        pass


def _cleanup_kb_entry(client, entry_id: str) -> None:
    """Delete a knowledge base entry, ignoring the case where it is gone."""
    try:
        client.security_ai_assistant.delete_knowledge_base_entry(id=entry_id)
    except ApiError:
        pass


class TestConversationsLifecycle:
    """Full lifecycle tests for Security AI Assistant conversations."""

    def test_conversation_crud_lifecycle(self, kibana_client, unique_suffix):
        title = f"{PREFIX}-conv-{unique_suffix}"
        created = kibana_client.security_ai_assistant.create_conversation(
            title=title,
            category="assistant",
            messages=[
                {
                    "content": "Hello, how can I assist you today?",
                    "role": "system",
                    "timestamp": "2026-01-01T12:00:00Z",
                }
            ],
        )
        conversation_id = created.body["id"]
        try:
            assert created.meta.status == 200
            assert created.body["title"] == title
            assert created.body["category"] == "assistant"
            assert len(created.body["messages"]) == 1

            # Get by ID
            fetched = kibana_client.security_ai_assistant.get_conversation(
                id=conversation_id
            )
            assert fetched.body["id"] == conversation_id
            assert fetched.body["title"] == title

            # Update the title (live 9.4.3 quirk: the update route accepts
            # `category` without error but does not modify it)
            updated_title = f"{title}-updated"
            updated = kibana_client.security_ai_assistant.update_conversation(
                id=conversation_id,
                title=updated_title,
                category="insights",
            )
            assert updated.body["title"] == updated_title
            assert updated.body["category"] == "assistant"

            # Find it by filter
            found = kibana_client.security_ai_assistant.find_conversations(
                filter=updated_title,
                sort_field="created_at",
                sort_order="desc",
                per_page=10,
            )
            assert found.body["total"] >= 1
            assert any(conv["id"] == conversation_id for conv in found.body["data"])
        finally:
            _cleanup_conversation(kibana_client, conversation_id)

        # After deletion the conversation must be gone (semantic 404)
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.security_ai_assistant.get_conversation(id=conversation_id)
        assert "not found" in str(exc_info.value).lower()

    def test_delete_all_conversations_with_exclusions(
        self, kibana_client, unique_suffix
    ):
        kept = kibana_client.security_ai_assistant.create_conversation(
            title=f"{PREFIX}-keep-{unique_suffix}",
        )
        kept_id = kept.body["id"]
        doomed = kibana_client.security_ai_assistant.create_conversation(
            title=f"{PREFIX}-doomed-{unique_suffix}",
        )
        doomed_id = doomed.body["id"]
        try:
            result = kibana_client.security_ai_assistant.delete_all_conversations(
                excluded_ids=[kept_id],
            )
            assert result.body["success"] is True
            assert result.body["totalDeleted"] >= 1

            # The excluded conversation survives; the other one is gone.
            survivor = kibana_client.security_ai_assistant.get_conversation(id=kept_id)
            assert survivor.body["id"] == kept_id
            with pytest.raises(NotFoundError):
                kibana_client.security_ai_assistant.get_conversation(id=doomed_id)
        finally:
            _cleanup_conversation(kibana_client, kept_id)
            _cleanup_conversation(kibana_client, doomed_id)

    def test_get_missing_conversation_semantic_404(self, kibana_client):
        missing_id = f"{PREFIX}-missing-{uuid.uuid4()}"
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.security_ai_assistant.get_conversation(id=missing_id)
        # Assert the server's semantic message, not just the status code
        assert missing_id in str(exc_info.value)
        assert "not found" in str(exc_info.value).lower()


class TestPrompts:
    """Tests for prompt find and bulk actions."""

    def test_prompts_bulk_lifecycle(self, kibana_client, unique_suffix):
        name_one = f"{PREFIX}-prompt-one-{unique_suffix}"
        name_two = f"{PREFIX}-prompt-two-{unique_suffix}"
        created_ids: list[str] = []
        try:
            # Bulk create two prompts
            created = kibana_client.security_ai_assistant.bulk_action_prompts(
                create=[
                    {
                        "name": name_one,
                        "content": "Summarize the open alerts.",
                        "promptType": "quick",
                    },
                    {
                        "name": name_two,
                        "content": "You are a security analyst.",
                        "promptType": "system",
                    },
                ],
            )
            assert created.body["success"] is True
            created_prompts = created.body["attributes"]["results"]["created"]
            assert len(created_prompts) == 2
            created_ids = [prompt["id"] for prompt in created_prompts]
            id_one = next(
                prompt["id"] for prompt in created_prompts if prompt["name"] == name_one
            )

            # Find the first prompt by filter
            found = kibana_client.security_ai_assistant.find_prompts(
                filter=name_one,
                per_page=10,
            )
            assert found.body["total"] >= 1
            assert any(prompt["id"] == id_one for prompt in found.body["data"])

            # Bulk update the first prompt's content
            updated = kibana_client.security_ai_assistant.bulk_action_prompts(
                update=[{"id": id_one, "content": "Summarize critical alerts."}],
            )
            assert updated.body["success"] is True
            updated_prompt = updated.body["attributes"]["results"]["updated"][0]
            assert updated_prompt["content"] == "Summarize critical alerts."

            # Bulk delete both prompts
            deleted = kibana_client.security_ai_assistant.bulk_action_prompts(
                delete={"ids": created_ids},
            )
            assert deleted.body["success"] is True
            assert sorted(deleted.body["attributes"]["results"]["deleted"]) == sorted(
                created_ids
            )
            created_ids = []
        finally:
            _cleanup_prompts(kibana_client, created_ids)


class TestAnonymizationFields:
    """Tests for anonymization field find and bulk actions."""

    def test_anonymization_fields_bulk_lifecycle(self, kibana_client, unique_suffix):
        field_name = f"kbnpy.secai.{unique_suffix}"
        created_ids: list[str] = []
        try:
            created = (
                kibana_client.security_ai_assistant.bulk_action_anonymization_fields(
                    create=[
                        {"field": field_name, "allowed": True, "anonymized": False}
                    ],
                )
            )
            assert created.body["success"] is True
            created_field = created.body["attributes"]["results"]["created"][0]
            created_ids = [created_field["id"]]
            assert created_field["field"] == field_name
            assert created_field["allowed"] is True

            # Find the created field by filter
            found = kibana_client.security_ai_assistant.find_anonymization_fields(
                filter=f'field: "{field_name}"',
                per_page=10,
            )
            assert found.body["total"] >= 1
            assert any(item["field"] == field_name for item in found.body["data"])

            # Bulk update: flip the anonymized flag
            updated = (
                kibana_client.security_ai_assistant.bulk_action_anonymization_fields(
                    update=[{"id": created_ids[0], "anonymized": True}],
                )
            )
            assert updated.body["success"] is True
            updated_field = updated.body["attributes"]["results"]["updated"][0]
            assert updated_field["anonymized"] is True

            # Bulk delete
            deleted = (
                kibana_client.security_ai_assistant.bulk_action_anonymization_fields(
                    delete={"ids": created_ids},
                )
            )
            assert deleted.body["success"] is True
            assert deleted.body["attributes"]["results"]["deleted"] == created_ids
            created_ids = []
        finally:
            _cleanup_anonymization_fields(kibana_client, created_ids)

    def test_find_anonymization_fields_default_page(self, kibana_client):
        found = kibana_client.security_ai_assistant.find_anonymization_fields(
            per_page=5,
        )
        assert found.meta.status == 200
        assert "data" in found.body
        assert found.body["perPage"] == 5


class TestKnowledgeBase:
    """Tests for Knowledge Base status, setup and entries."""

    def test_get_knowledge_base_status(self, kibana_client):
        status = kibana_client.security_ai_assistant.get_knowledge_base()
        assert status.meta.status == 200
        assert "is_setup_available" in status.body
        assert "elser_exists" in status.body

    def test_get_knowledge_base_status_for_resource(self, kibana_client):
        status = kibana_client.security_ai_assistant.get_knowledge_base(
            resource="security_labs",
        )
        assert status.meta.status == 200
        assert "security_labs_exists" in status.body

    def test_setup_knowledge_base(self, kibana_client):
        # ignore_security_labs=True keeps the setup light on the dev stack
        result = kibana_client.security_ai_assistant.setup_knowledge_base(
            ignore_security_labs=True,
        )
        assert result.meta.status == 200
        assert result.body["success"] is True

    def test_setup_knowledge_base_for_resource(self, kibana_client):
        result = kibana_client.security_ai_assistant.setup_knowledge_base(
            resource="user",
            ignore_security_labs=True,
        )
        assert result.meta.status == 200
        assert result.body["success"] is True

    def test_knowledge_base_entry_crud_lifecycle(
        self, kibana_client, unique_suffix, elser_ready
    ):
        entry_name = f"{PREFIX}-kb-entry-{unique_suffix}"
        created = kibana_client.security_ai_assistant.create_knowledge_base_entry(
            type="document",
            name=entry_name,
            kb_resource="user",
            source=f"/kbnpy/{unique_suffix}.txt",
            text="To rotate credentials, open the security settings page.",
        )
        entry_id = created.body["id"]
        try:
            assert created.meta.status == 200
            assert created.body["name"] == entry_name
            assert created.body["type"] == "document"
            assert created.body["kbResource"] == "user"

            # Get by ID
            fetched = kibana_client.security_ai_assistant.get_knowledge_base_entry(
                id=entry_id,
            )
            assert fetched.body["id"] == entry_id
            assert fetched.body["name"] == entry_name

            # Update (full replace with the document union fields)
            updated = kibana_client.security_ai_assistant.update_knowledge_base_entry(
                id=entry_id,
                type="document",
                name=f"{entry_name}-updated",
                kb_resource="user",
                source=f"/kbnpy/{unique_suffix}.txt",
                text="Updated: rotate credentials monthly.",
            )
            assert updated.body["name"] == f"{entry_name}-updated"
            assert updated.body["text"] == "Updated: rotate credentials monthly."

            # Find it
            found = kibana_client.security_ai_assistant.find_knowledge_base_entries(
                per_page=100,
            )
            assert found.body["total"] >= 1
            assert any(item["id"] == entry_id for item in found.body["data"])

            # Delete
            deleted = kibana_client.security_ai_assistant.delete_knowledge_base_entry(
                id=entry_id,
            )
            assert deleted.body["id"] == entry_id
        finally:
            _cleanup_kb_entry(kibana_client, entry_id)

        # After deletion the entry must be gone
        with pytest.raises(NotFoundError):
            kibana_client.security_ai_assistant.get_knowledge_base_entry(id=entry_id)

    def test_bulk_action_knowledge_base_entries(
        self, kibana_client, unique_suffix, elser_ready
    ):
        entry_name = f"{PREFIX}-kb-bulk-{unique_suffix}"
        created_ids: list[str] = []
        try:
            created = (
                kibana_client.security_ai_assistant.bulk_action_knowledge_base_entries(
                    create=[
                        {
                            "type": "document",
                            "name": entry_name,
                            "kbResource": "user",
                            "source": f"/kbnpy/{unique_suffix}-bulk.txt",
                            "text": "Bulk-created knowledge base entry.",
                        }
                    ],
                )
            )
            assert created.body["success"] is True
            created_entry = created.body["attributes"]["results"]["created"][0]
            created_ids = [created_entry["id"]]
            assert created_entry["name"] == entry_name

            # Bulk update
            updated = (
                kibana_client.security_ai_assistant.bulk_action_knowledge_base_entries(
                    update=[
                        {
                            "id": created_ids[0],
                            "type": "document",
                            "name": f"{entry_name}-updated",
                            "kbResource": "user",
                            "source": f"/kbnpy/{unique_suffix}-bulk.txt",
                            "text": "Bulk-updated knowledge base entry.",
                        }
                    ],
                )
            )
            assert updated.body["success"] is True
            updated_entry = updated.body["attributes"]["results"]["updated"][0]
            assert updated_entry["name"] == f"{entry_name}-updated"

            # Bulk delete
            deleted = (
                kibana_client.security_ai_assistant.bulk_action_knowledge_base_entries(
                    delete={"ids": created_ids},
                )
            )
            assert deleted.body["success"] is True
            assert deleted.body["attributes"]["results"]["deleted"] == created_ids
            created_ids = []
        finally:
            for entry_id in created_ids:
                _cleanup_kb_entry(kibana_client, entry_id)


class TestChatComplete:
    """Live chat/complete round-trip through an OpenAI-compatible backend."""

    @pytest.mark.skipif(
        not LMSTUDIO_URL,
        reason="KBNPY_LMSTUDIO_OPENAI_URL not set (no live LLM backend available)",
    )
    def test_chat_complete_round_trip(self, kibana_client, unique_suffix):
        # The Kibana OpenAI connector posts to apiUrl directly, so it must be
        # the full chat completions endpoint, not just the /v1 base URL.
        api_url = f"{LMSTUDIO_URL.rstrip('/')}/chat/completions"
        connector = kibana_client.connectors.create(
            name=f"{PREFIX}-llm-{unique_suffix}",
            connector_type_id=".gen-ai",
            config={
                "apiProvider": "OpenAI",
                "apiUrl": api_url,
                "defaultModel": LMSTUDIO_MODEL,
            },
            secrets={"apiKey": "dummy-key"},
        )
        connector_id = connector.body["id"]
        try:
            # Local models can be slow: raise the request timeout for the call
            patient_client = kibana_client.options(request_timeout=CHAT_REQUEST_TIMEOUT)
            response = patient_client.security_ai_assistant.chat_complete(
                connector_id=connector_id,
                messages=[
                    {
                        "role": "user",
                        "content": "Reply with exactly the word: pong",
                    }
                ],
                persist=False,
                is_stream=False,
            )
            assert response.meta.status == 200
            assert response.body["status"] == "ok"
            assert response.body["connector_id"] == connector_id
            assert isinstance(response.body["data"], str)
            assert len(response.body["data"].strip()) > 0
        finally:
            kibana_client.connectors.delete(id=connector_id)


class TestAsyncSecurityAiAssistant:
    """Async round-trip tests for the Security AI Assistant API."""

    async def test_async_conversation_round_trip(
        self, async_kibana_client, unique_suffix
    ):
        title = f"{PREFIX}-async-conv-{unique_suffix}"
        created = await async_kibana_client.security_ai_assistant.create_conversation(
            title=title,
        )
        conversation_id = created.body["id"]
        try:
            assert created.body["title"] == title

            fetched = await async_kibana_client.security_ai_assistant.get_conversation(
                id=conversation_id,
            )
            assert fetched.body["id"] == conversation_id

            found = await async_kibana_client.security_ai_assistant.find_conversations(
                filter=title,
                per_page=10,
            )
            assert found.body["total"] >= 1
        finally:
            try:
                await async_kibana_client.security_ai_assistant.delete_conversation(
                    id=conversation_id,
                )
            except NotFoundError:
                pass

        with pytest.raises(NotFoundError):
            await async_kibana_client.security_ai_assistant.get_conversation(
                id=conversation_id,
            )

    async def test_async_knowledge_base_status(self, async_kibana_client):
        status = await async_kibana_client.security_ai_assistant.get_knowledge_base()
        assert status.meta.status == 200
        assert "is_setup_available" in status.body
