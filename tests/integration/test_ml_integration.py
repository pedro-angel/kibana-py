"""Integration tests for MlClient / AsyncMlClient against a live stack.

These tests exercise the Kibana machine learning saved objects APIs:

- GET  /api/ml/saved_objects/sync
- POST /api/ml/saved_objects/update_jobs_spaces
- POST /api/ml/saved_objects/update_trained_models_spaces

Most tests are read-only (``simulate=True``) or target nonexistent
``kbnpy-ml-`` prefixed IDs, which the API reports as per-item errors in a
200 response without changing any state. The lifecycle test creates a tiny
throwaway anomaly detection job directly in Elasticsearch (prefixed
``kbnpy-ml-``) and always cleans it up.
"""

import os
import uuid

import pytest

from kibana.exceptions import BadRequestError

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    get_integration_test_config,
    is_kibana_available,
)

# Skip all tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)

SYNC_RESPONSE_KEYS = {
    "savedObjectsCreated",
    "savedObjectsDeleted",
    "datafeedsAdded",
    "datafeedsRemoved",
}


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing."""
    client = create_test_kibana_client()
    yield client
    client.close()


@pytest.fixture
async def async_kibana_client():
    """Create an AsyncKibana client for testing."""
    client = create_test_async_kibana_client()
    yield client
    await client.close()


def _es_config():
    """Return (es_url, basic_auth) for direct Elasticsearch access."""
    es_url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    _, basic_auth, _ = get_integration_test_config()
    return es_url, basic_auth


class TestMlSyncIntegration:
    """Integration tests for MlClient.sync()."""

    def test_sync_simulate(self, kibana_client):
        """Simulated sync returns the four documented result sections."""
        response = kibana_client.ml.sync(simulate=True)

        assert response.meta.status == 200
        assert SYNC_RESPONSE_KEYS <= set(response.body.keys())
        for key in SYNC_RESPONSE_KEYS:
            assert isinstance(response.body[key], dict)

    def test_sync_simulate_space_scoped(self, kibana_client):
        """Simulated sync works via the /s/{space_id} path variant."""
        response = kibana_client.ml.sync(simulate=True, space_id="default")

        assert response.meta.status == 200
        assert SYNC_RESPONSE_KEYS <= set(response.body.keys())


class TestMlUpdateJobsSpacesIntegration:
    """Integration tests for MlClient.update_jobs_spaces()."""

    def test_update_jobs_spaces_unknown_job_reports_per_item_error(self, kibana_client):
        """Unknown job IDs yield success=False per item in a 200 response."""
        job_id = f"kbnpy-ml-missing-{uuid.uuid4().hex[:8]}"

        response = kibana_client.ml.update_jobs_spaces(
            job_ids=[job_id],
            job_type="anomaly-detector",
            spaces_to_add=["default"],
            spaces_to_remove=[],
        )

        assert response.meta.status == 200
        result = response.body[job_id]
        assert result["success"] is False
        assert result["type"] == "anomaly-detector"
        assert "No known job" in result["error"]

    def test_update_jobs_spaces_unknown_dfa_job(self, kibana_client):
        """The data-frame-analytics job type is accepted by the API."""
        job_id = f"kbnpy-ml-missing-dfa-{uuid.uuid4().hex[:8]}"

        response = kibana_client.ml.update_jobs_spaces(
            job_ids=[job_id],
            job_type="data-frame-analytics",
            spaces_to_add=["default"],
            spaces_to_remove=[],
        )

        assert response.meta.status == 200
        result = response.body[job_id]
        assert result["success"] is False
        assert result["type"] == "data-frame-analytics"

    def test_update_jobs_spaces_invalid_job_type_raises(self, kibana_client):
        """An unknown jobType fails route validation with a 400."""
        with pytest.raises(BadRequestError) as exc_info:
            kibana_client.ml.update_jobs_spaces(
                job_ids=["kbnpy-ml-any-job"],
                job_type="bogus-type",
                spaces_to_add=[],
                spaces_to_remove=[],
            )

        assert "jobType" in str(exc_info.value)


class TestMlUpdateTrainedModelsSpacesIntegration:
    """Integration tests for MlClient.update_trained_models_spaces()."""

    def test_update_trained_models_spaces_unknown_model(self, kibana_client):
        """Unknown model IDs yield success=False per item in a 200 response."""
        model_id = f"kbnpy-ml-missing-model-{uuid.uuid4().hex[:8]}"

        response = kibana_client.ml.update_trained_models_spaces(
            model_ids=[model_id],
            spaces_to_add=["default"],
            spaces_to_remove=[],
        )

        assert response.meta.status == 200
        result = response.body[model_id]
        assert result["success"] is False
        assert result["type"] == "trained-model"
        assert "No known trained model" in result["error"]


class TestMlJobLifecycleIntegration:
    """Full round-trip: real ML job, sync, spaces update, cleanup."""

    def test_job_sync_and_update_spaces_lifecycle(self, kibana_client):
        """A real anomaly detection job can be synced and space-assigned."""
        requests = pytest.importorskip("requests")

        es_url, basic_auth = _es_config()
        if basic_auth is None:
            pytest.skip("Elasticsearch basic auth credentials not available")

        job_id = f"kbnpy-ml-itest-{uuid.uuid4().hex[:8]}"
        job_url = f"{es_url}/_ml/anomaly_detectors/{job_id}"
        job_config = {
            "analysis_config": {
                "bucket_span": "15m",
                "detectors": [{"function": "count"}],
            },
            "data_description": {"time_field": "@timestamp"},
        }

        created = False
        try:
            # Create a tiny throwaway job directly in Elasticsearch
            resp = requests.put(job_url, json=job_config, auth=basic_auth, timeout=30)
            if resp.status_code != 200:
                pytest.skip(
                    f"Could not create ML job in Elasticsearch: "
                    f"{resp.status_code} {resp.text[:200]}"
                )
            created = True

            # A real sync creates the Kibana saved object for the new job.
            # (Kibana also runs this periodically, so the job may already be
            # synced by the time we call it; either way the follow-up
            # update_jobs_spaces call must succeed.)
            sync_response = kibana_client.ml.sync()
            assert sync_response.meta.status == 200
            assert SYNC_RESPONSE_KEYS <= set(sync_response.body.keys())

            # Now the job is known to Kibana and can be space-assigned
            update_response = kibana_client.ml.update_jobs_spaces(
                job_ids=[job_id],
                job_type="anomaly-detector",
                spaces_to_add=["default"],
                spaces_to_remove=[],
            )
            assert update_response.meta.status == 200
            result = update_response.body[job_id]
            assert result == {"success": True, "type": "anomaly-detector"}
        finally:
            if created:
                # Delete the ES job, then sync so Kibana drops its saved object
                requests.delete(job_url, auth=basic_auth, timeout=30)
                kibana_client.ml.sync()


class TestAsyncMlIntegration:
    """Async round-trip tests for AsyncMlClient."""

    async def test_async_sync_simulate(self, async_kibana_client):
        """Async simulated sync returns the documented result sections."""
        response = await async_kibana_client.ml.sync(simulate=True)

        assert response.meta.status == 200
        assert SYNC_RESPONSE_KEYS <= set(response.body.keys())

    async def test_async_update_jobs_spaces_unknown_job(self, async_kibana_client):
        """Async update reports per-item errors for unknown job IDs."""
        job_id = f"kbnpy-ml-missing-async-{uuid.uuid4().hex[:8]}"

        response = await async_kibana_client.ml.update_jobs_spaces(
            job_ids=[job_id],
            job_type="anomaly-detector",
            spaces_to_add=["default"],
            spaces_to_remove=[],
        )

        assert response.meta.status == 200
        result = response.body[job_id]
        assert result["success"] is False
        assert "No known job" in result["error"]

    async def test_async_update_trained_models_spaces_unknown_model(
        self, async_kibana_client
    ):
        """Async trained-model update reports per-item errors."""
        model_id = f"kbnpy-ml-missing-model-async-{uuid.uuid4().hex[:8]}"

        response = await async_kibana_client.ml.update_trained_models_spaces(
            model_ids=[model_id],
            spaces_to_add=["default"],
            spaces_to_remove=[],
        )

        assert response.meta.status == 200
        result = response.body[model_id]
        assert result["success"] is False
        assert result["type"] == "trained-model"
