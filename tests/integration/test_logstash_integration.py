"""Integration tests for LogstashClient against a live Kibana instance.

The Logstash centralized pipeline management API stores pipeline definitions
in Elasticsearch, so full CRUD works without a running Logstash instance.
All resources created here are prefixed with ``kbnpy-logstash-`` and cleaned
up after each test.
"""

import uuid

import pytest

from kibana.exceptions import NotFoundError

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

PIPELINE_DEFINITION = "input { stdin {} } output { stdout {} }"


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
def created_pipelines(kibana_client):
    """Track pipeline IDs created during a test and delete them afterwards."""
    pipeline_ids: list[str] = []
    yield pipeline_ids

    for pipeline_id in pipeline_ids:
        try:
            kibana_client.logstash.delete(id=pipeline_id)
        except NotFoundError:
            pass  # Already deleted by the test itself
        except Exception as e:  # pragma: no cover - cleanup best effort
            print(f"Warning: failed to clean up pipeline {pipeline_id}: {e}")


@pytest.fixture
def unique_pipeline_id():
    """Generate a unique, prefixed pipeline ID for testing."""
    return f"kbnpy-logstash-{uuid.uuid4().hex[:12]}"


class TestLogstashPipelineCrud:
    """Full CRUD round-trips against the live Logstash pipeline API."""

    def test_create_get_update_delete_pipeline(
        self, kibana_client, created_pipelines, unique_pipeline_id
    ):
        """Create, read, upsert-update, and delete a pipeline."""
        # Create
        create_response = kibana_client.logstash.create_or_update(
            id=unique_pipeline_id,
            pipeline=PIPELINE_DEFINITION,
            description="kibana-py integration test pipeline",
            settings={"queue.type": "memory"},
        )
        created_pipelines.append(unique_pipeline_id)
        assert create_response.meta.status == 204

        # Get
        get_response = kibana_client.logstash.get(id=unique_pipeline_id)
        assert get_response.meta.status == 200
        assert get_response.body["id"] == unique_pipeline_id
        assert get_response.body["pipeline"] == PIPELINE_DEFINITION
        assert get_response.body["description"] == (
            "kibana-py integration test pipeline"
        )
        assert get_response.body["settings"] == {"queue.type": "memory"}

        # Update (PUT is an upsert on the same ID)
        updated_definition = "input { generator { count => 1 } } output { stdout {} }"
        update_response = kibana_client.logstash.create_or_update(
            id=unique_pipeline_id,
            pipeline=updated_definition,
            description="updated by kibana-py integration test",
        )
        assert update_response.meta.status == 204

        get_after_update = kibana_client.logstash.get(id=unique_pipeline_id)
        assert get_after_update.body["pipeline"] == updated_definition
        assert get_after_update.body["description"] == (
            "updated by kibana-py integration test"
        )

        # Delete
        delete_response = kibana_client.logstash.delete(id=unique_pipeline_id)
        assert delete_response.meta.status == 204

        with pytest.raises(NotFoundError):
            kibana_client.logstash.get(id=unique_pipeline_id)

    def test_create_minimal_pipeline(
        self, kibana_client, created_pipelines, unique_pipeline_id
    ):
        """Create a pipeline with only the required ``pipeline`` field."""
        response = kibana_client.logstash.create_or_update(
            id=unique_pipeline_id,
            pipeline=PIPELINE_DEFINITION,
        )
        created_pipelines.append(unique_pipeline_id)
        assert response.meta.status == 204

        get_response = kibana_client.logstash.get(id=unique_pipeline_id)
        assert get_response.body["id"] == unique_pipeline_id
        assert get_response.body["pipeline"] == PIPELINE_DEFINITION

    def test_get_all_contains_created_pipeline(
        self, kibana_client, created_pipelines, unique_pipeline_id
    ):
        """The pipelines list includes a freshly created pipeline."""
        kibana_client.logstash.create_or_update(
            id=unique_pipeline_id,
            pipeline=PIPELINE_DEFINITION,
            description="kibana-py list test",
        )
        created_pipelines.append(unique_pipeline_id)

        response = kibana_client.logstash.get_all()
        assert response.meta.status == 200
        assert isinstance(response.body["pipelines"], list)

        entries = {p["id"]: p for p in response.body["pipelines"]}
        assert unique_pipeline_id in entries
        entry = entries[unique_pipeline_id]
        assert entry["description"] == "kibana-py list test"
        # last_modified is always present; username appears when security is on
        assert "last_modified" in entry


class TestLogstashPipelineErrors:
    """Error behavior of the live Logstash pipeline API."""

    def test_get_missing_pipeline_raises_not_found(self, kibana_client):
        """Getting a nonexistent pipeline raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.logstash.get(
                id=f"kbnpy-logstash-missing-{uuid.uuid4().hex[:8]}"
            )

    def test_delete_missing_pipeline_raises_not_found(self, kibana_client):
        """Deleting a nonexistent pipeline raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.logstash.delete(
                id=f"kbnpy-logstash-missing-{uuid.uuid4().hex[:8]}"
            )


class TestAsyncLogstashPipeline:
    """Async round-trip against the live Logstash pipeline API."""

    async def test_async_create_get_list_delete_pipeline(self, unique_pipeline_id):
        """Full async CRUD round-trip with cleanup."""
        client = create_test_async_kibana_client(auth_method="auto")
        try:
            create_response = await client.logstash.create_or_update(
                id=unique_pipeline_id,
                pipeline=PIPELINE_DEFINITION,
                description="kibana-py async integration test",
            )
            assert create_response.meta.status == 204

            try:
                get_response = await client.logstash.get(id=unique_pipeline_id)
                assert get_response.body["id"] == unique_pipeline_id
                assert get_response.body["pipeline"] == PIPELINE_DEFINITION

                list_response = await client.logstash.get_all()
                listed_ids = {p["id"] for p in list_response.body["pipelines"]}
                assert unique_pipeline_id in listed_ids
            finally:
                delete_response = await client.logstash.delete(id=unique_pipeline_id)
                assert delete_response.meta.status == 204

            with pytest.raises(NotFoundError):
                await client.logstash.get(id=unique_pipeline_id)
        finally:
            await client.close()
