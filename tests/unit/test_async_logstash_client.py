"""Unit tests for AsyncLogstashClient."""

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client.logstash import AsyncLogstashClient
from kibana.exceptions import AuthorizationException, NotFoundError


class TestAsyncLogstashClientInitialization:
    """Test AsyncLogstashClient initialization and wiring."""

    @pytest.mark.asyncio
    async def test_logstash_client_initialization(self, mock_async_transport):
        """Test that AsyncLogstashClient can be initialized with a parent client."""
        client = AsyncKibana(_transport=mock_async_transport)
        logstash_client = AsyncLogstashClient(client)
        assert logstash_client._client is client

    @pytest.mark.asyncio
    async def test_logstash_property_returns_logstash_client(
        self, mock_async_transport
    ):
        """Test that client.logstash returns an AsyncLogstashClient instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.logstash, AsyncLogstashClient)

    @pytest.mark.asyncio
    async def test_logstash_property_caching(self, mock_async_transport):
        """Test that the logstash property returns the same instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert client.logstash is client.logstash


class TestAsyncLogstashClientGetAll:
    """Test AsyncLogstashClient.get_all() method."""

    @pytest.mark.asyncio
    async def test_get_all_success(self, mock_async_transport, mock_response):
        """Test successful retrieval of all pipelines."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "pipelines": [
                    {
                        "id": "hello-world",
                        "description": "Just a simple pipeline",
                        "last_modified": "2026-04-14T12:23:29.772Z",
                        "username": "elastic",
                    },
                    {
                        "id": "sleepy-pipeline",
                        "description": "",
                        "last_modified": "2026-03-24T03:41:30.554Z",
                    },
                ]
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.logstash.get_all()

        assert len(result.body["pipelines"]) == 2
        assert result.body["pipelines"][0]["id"] == "hello-world"

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/logstash/pipelines"
        assert call_kwargs["headers"] == {"accept": "application/json"}


class TestAsyncLogstashClientGet:
    """Test AsyncLogstashClient.get() method."""

    @pytest.mark.asyncio
    async def test_get_success(self, mock_async_transport, mock_response):
        """Test successful retrieval of a single pipeline."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "id": "hello-world",
                "description": "Just a simple pipeline",
                "username": "elastic",
                "pipeline": "input { stdin {} } output { stdout {} }",
                "settings": {"queue.type": "persistent"},
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.logstash.get(id="hello-world")

        assert result.body["id"] == "hello-world"
        assert result.body["pipeline"] == "input { stdin {} } output { stdout {} }"

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/logstash/pipeline/hello-world"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    @pytest.mark.asyncio
    async def test_get_url_encodes_id(self, mock_async_transport, mock_response):
        """Test that pipeline IDs are URL-encoded in the path."""
        mock_async_transport.perform_request.return_value = mock_response(body={})

        client = AsyncKibana(_transport=mock_async_transport)
        await client.logstash.get(id="my pipeline/1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/logstash/pipeline/my%20pipeline%2F1"

    @pytest.mark.asyncio
    async def test_get_not_found(self, mock_async_transport, mock_response):
        """Test that a 404 response raises NotFoundError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Not Found",
            },
            status=404,
        )

        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(NotFoundError):
            await client.logstash.get(id="missing-pipeline")


class TestAsyncLogstashClientCreateOrUpdate:
    """Test AsyncLogstashClient.create_or_update() method."""

    @pytest.mark.asyncio
    async def test_create_or_update_minimal(self, mock_async_transport, mock_response):
        """Test pipeline creation with only the required body field."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=204
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.logstash.create_or_update(
            id="hello-world",
            pipeline="input { stdin {} } output { stdout {} }",
        )

        assert result.meta.status == 204
        assert result.body == {}

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/logstash/pipeline/hello-world"
        # Optional fields must not be sent when omitted
        assert call_kwargs["body"] == {
            "pipeline": "input { stdin {} } output { stdout {} }"
        }
        # Write requests carry CSRF and JSON content-type headers
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["accept"] == "application/json"

    @pytest.mark.asyncio
    async def test_create_or_update_full_body(
        self, mock_async_transport, mock_response
    ):
        """Test pipeline creation with description and settings."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=204
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.logstash.create_or_update(
            id="hello-world",
            pipeline="input { stdin {} } output { stdout {} }",
            description="Just a simple pipeline",
            settings={"queue.type": "persisted", "pipeline.workers": 2},
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "pipeline": "input { stdin {} } output { stdout {} }",
            "description": "Just a simple pipeline",
            "settings": {"queue.type": "persisted", "pipeline.workers": 2},
        }

    @pytest.mark.asyncio
    async def test_create_or_update_authorization_error(
        self, mock_async_transport, mock_response
    ):
        """Test that a 403 response raises AuthorizationException."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 403,
                "error": "Forbidden",
                "message": "Insufficient privileges",
            },
            status=403,
        )

        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(AuthorizationException):
            await client.logstash.create_or_update(
                id="p1", pipeline="input {} output {}"
            )


class TestAsyncLogstashClientDelete:
    """Test AsyncLogstashClient.delete() method."""

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_async_transport, mock_response):
        """Test successful pipeline deletion (204 No Content)."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=204
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.logstash.delete(id="hello-world")

        assert result.meta.status == 204
        assert result.body == {}

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/logstash/pipeline/hello-world"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert "body" not in call_kwargs

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_async_transport, mock_response):
        """Test that deleting a missing pipeline raises NotFoundError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Not Found",
            },
            status=404,
        )

        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(NotFoundError):
            await client.logstash.delete(id="missing-pipeline")
