"""Unit tests for AsyncMlClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._async.client import AsyncKibana
from kibana._async.client.ml import AsyncMlClient


@pytest.fixture
def client(mock_async_transport):
    """Create an AsyncKibana client backed by a mocked transport."""
    return AsyncKibana(_transport=mock_async_transport)


def _mock_response(mock_async_transport, body, status=200):
    response = ObjectApiResponse(body=body, meta=Mock(status=status, headers={}))
    mock_async_transport.perform_request.return_value = response
    return response


class TestAsyncMlClientInitialization:
    """Test AsyncMlClient initialization and wiring."""

    def test_ml_property_returns_ml_client(self, client):
        """client.ml is an AsyncMlClient instance bound to the parent client."""
        assert isinstance(client.ml, AsyncMlClient)
        assert client.ml._client is client

    def test_ml_property_caching(self, client):
        """client.ml returns the same instance on repeated access."""
        assert client.ml is client.ml


class TestAsyncMlClientSync:
    """Test AsyncMlClient.sync()."""

    async def test_sync_default(self, client, mock_async_transport):
        """sync() issues GET /api/ml/saved_objects/sync with no params."""
        _mock_response(
            mock_async_transport,
            {
                "savedObjectsCreated": {},
                "savedObjectsDeleted": {},
                "datafeedsAdded": {},
                "datafeedsRemoved": {},
            },
        )

        result = await client.ml.sync()

        assert result.body["savedObjectsCreated"] == {}
        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/ml/saved_objects/sync"
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert "body" not in call_kwargs

    async def test_sync_simulate_true(self, client, mock_async_transport):
        """simulate=True is encoded as the lowercase query string 'true'."""
        _mock_response(
            mock_async_transport,
            {
                "savedObjectsCreated": {
                    "anomaly-detector": {"myjob1": {"success": True}}
                },
                "savedObjectsDeleted": {},
                "datafeedsAdded": {},
                "datafeedsRemoved": {},
            },
        )

        result = await client.ml.sync(simulate=True)

        created = result.body["savedObjectsCreated"]["anomaly-detector"]
        assert created["myjob1"]["success"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/ml/saved_objects/sync?simulate=true"

    async def test_sync_simulate_false(self, client, mock_async_transport):
        """simulate=False is encoded as 'false', not omitted."""
        _mock_response(mock_async_transport, {})

        await client.ml.sync(simulate=False)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/ml/saved_objects/sync?simulate=false"

    async def test_sync_space_scoped(self, client, mock_async_transport):
        """space_id prefixes the path with /s/{space_id}."""
        _mock_response(mock_async_transport, {})

        await client.ml.sync(simulate=True, space_id="marketing", validate_spaces=False)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == "/s/marketing/api/ml/saved_objects/sync?simulate=true"
        )


class TestAsyncMlClientUpdateJobsSpaces:
    """Test AsyncMlClient.update_jobs_spaces()."""

    async def test_update_jobs_spaces(self, client, mock_async_transport):
        """update_jobs_spaces() POSTs the camelCase body to the right path."""
        _mock_response(
            mock_async_transport,
            {"test-job": {"success": True, "type": "anomaly-detector"}},
        )

        result = await client.ml.update_jobs_spaces(
            job_ids=["test-job"],
            job_type="anomaly-detector",
            spaces_to_add=["default"],
            spaces_to_remove=["*"],
        )

        assert result.body["test-job"]["success"] is True
        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/ml/saved_objects/update_jobs_spaces"
        assert call_kwargs["body"] == {
            "jobIds": ["test-job"],
            "jobType": "anomaly-detector",
            "spacesToAdd": ["default"],
            "spacesToRemove": ["*"],
        }
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    async def test_update_jobs_spaces_per_item_error(
        self, client, mock_async_transport
    ):
        """Per-job failures come back in a 200 body, no exception raised."""
        _mock_response(
            mock_async_transport,
            {
                "missing-job": {
                    "success": False,
                    "type": "anomaly-detector",
                    "error": "No known job with id 'missing-job'",
                }
            },
        )

        result = await client.ml.update_jobs_spaces(
            job_ids=["missing-job"],
            job_type="anomaly-detector",
            spaces_to_add=[],
            spaces_to_remove=["default"],
        )

        assert result.body["missing-job"]["success"] is False
        assert "No known job" in result.body["missing-job"]["error"]

    async def test_update_jobs_spaces_space_scoped(self, client, mock_async_transport):
        """space_id prefixes the path with /s/{space_id}."""
        _mock_response(mock_async_transport, {})

        await client.ml.update_jobs_spaces(
            job_ids=["test-job"],
            job_type="data-frame-analytics",
            spaces_to_add=["default"],
            spaces_to_remove=[],
            space_id="team-a",
            validate_spaces=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"] == "/s/team-a/api/ml/saved_objects/update_jobs_spaces"
        )
        assert call_kwargs["body"]["jobType"] == "data-frame-analytics"

    async def test_update_jobs_spaces_bad_request(self, client, mock_async_transport):
        """A 400 response raises BadRequestError."""
        from kibana.exceptions import BadRequestError

        _mock_response(
            mock_async_transport,
            {
                "statusCode": 400,
                "error": "Bad Request",
                "message": "[request body.jobType]: types that failed validation",
            },
            status=400,
        )

        with pytest.raises(BadRequestError):
            await client.ml.update_jobs_spaces(
                job_ids=["test-job"],
                job_type="bogus",
                spaces_to_add=[],
                spaces_to_remove=[],
            )


class TestAsyncMlClientUpdateTrainedModelsSpaces:
    """Test AsyncMlClient.update_trained_models_spaces()."""

    async def test_update_trained_models_spaces(self, client, mock_async_transport):
        """update_trained_models_spaces() POSTs the camelCase body."""
        _mock_response(
            mock_async_transport,
            {"test-model": {"success": True, "type": "trained-model"}},
        )

        result = await client.ml.update_trained_models_spaces(
            model_ids=["test-model"],
            spaces_to_add=["default"],
            spaces_to_remove=["*"],
        )

        assert result.body["test-model"]["success"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert (
            call_kwargs["target"]
            == "/api/ml/saved_objects/update_trained_models_spaces"
        )
        assert call_kwargs["body"] == {
            "modelIds": ["test-model"],
            "spacesToAdd": ["default"],
            "spacesToRemove": ["*"],
        }
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    async def test_update_trained_models_spaces_space_scoped(
        self, client, mock_async_transport
    ):
        """space_id prefixes the path with /s/{space_id}."""
        _mock_response(mock_async_transport, {})

        await client.ml.update_trained_models_spaces(
            model_ids=["test-model"],
            spaces_to_add=[],
            spaces_to_remove=["default"],
            space_id="team-b",
            validate_spaces=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == "/s/team-b/api/ml/saved_objects/update_trained_models_spaces"
        )


class TestAsyncMlClientErrorHandling:
    """Test AsyncMlClient error mapping."""

    async def test_sync_authentication_error(self, client, mock_async_transport):
        """A 401 response raises AuthenticationException."""
        from kibana.exceptions import AuthenticationException

        _mock_response(
            mock_async_transport,
            {
                "statusCode": 401,
                "error": "Unauthorized",
                "message": "unable to authenticate user",
            },
            status=401,
        )

        with pytest.raises(AuthenticationException):
            await client.ml.sync()

    async def test_sync_not_found_error(self, client, mock_async_transport):
        """A 404 response raises NotFoundError."""
        from kibana.exceptions import NotFoundError

        _mock_response(
            mock_async_transport,
            {"statusCode": 404, "error": "Not Found", "message": "Not Found"},
            status=404,
        )

        with pytest.raises(NotFoundError):
            await client.ml.sync()
