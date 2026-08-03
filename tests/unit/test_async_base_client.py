"""Unit tests for AsyncBaseClient."""

import logging
from collections import namedtuple
from unittest.mock import AsyncMock, patch

import pytest
from elastic_transport import HttpHeaders

from kibana.exceptions import (
    ApiError,
    AuthenticationException,
    AuthorizationException,
    BadRequestError,
    ConflictError,
    NotFoundError,
)


class TestAsyncBaseClientInitialization:
    """Tests for AsyncBaseClient initialization."""

    @pytest.mark.asyncio
    async def test_init_with_transport(self, mock_async_transport):
        """Test AsyncBaseClient initialization with a Transport instance."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)

        assert client._transport is mock_async_transport
        assert isinstance(client._headers, HttpHeaders)


class TestAsyncPerformRequest:
    """Tests for AsyncBaseClient.perform_request() method."""

    @pytest.mark.asyncio
    async def test_perform_request_calls_transport(
        self, mock_async_transport, mock_response
    ):
        """Test that perform_request calls transport.perform_request."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"result": "success"}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        response = await client.perform_request("GET", "/api/status")

        mock_async_transport.perform_request.assert_called_once()
        assert response.body == {"result": "success"}

    @pytest.mark.asyncio
    async def test_perform_request_with_params(
        self, mock_async_transport, mock_response
    ):
        """Test perform_request with query parameters."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"items": []}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        await client.perform_request(
            "GET", "/api/saved_objects/_find", params={"type": "dashboard"}
        )

        call_args = mock_async_transport.perform_request.call_args
        # Params should be encoded in the target URL
        assert "target" in call_args[1]
        assert "type=dashboard" in call_args[1]["target"]

    @pytest.mark.asyncio
    async def test_perform_request_with_body(self, mock_async_transport, mock_response):
        """Test perform_request with request body."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"id": "test-id"}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        body_data = {"attributes": {"title": "Test"}}
        await client.perform_request(
            "POST", "/api/saved_objects/dashboard", body=body_data
        )

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["body"] == body_data

    @pytest.mark.asyncio
    async def test_perform_request_with_headers(
        self, mock_async_transport, mock_response
    ):
        """Test perform_request with custom headers."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        headers = {"X-Custom-Header": "value"}
        await client.perform_request("GET", "/api/status", headers=headers)

        call_args = mock_async_transport.perform_request.call_args
        assert "headers" in call_args[1]

    @pytest.mark.asyncio
    async def test_perform_request_processes_successful_response(
        self, mock_async_transport, mock_response
    ):
        """Test that successful responses are returned without raising exceptions."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"status": "green"}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        response = await client.perform_request("GET", "/api/status")

        assert response.body == {"status": "green"}
        assert response.meta.status == 200


class TestAsyncErrorResponseProcessing:
    """Tests for async error response processing."""

    @pytest.mark.asyncio
    async def test_400_raises_bad_request_error(
        self, mock_async_transport, mock_response
    ):
        """Test that 400 status raises BadRequestError."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"error": "Invalid request"}, status=400)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(BadRequestError) as exc_info:
            await client.perform_request("POST", "/api/saved_objects/dashboard")

        assert exc_info.value.status_code == 400
        assert exc_info.value.body == {"error": "Invalid request"}

    @pytest.mark.asyncio
    async def test_401_raises_authentication_exception(
        self, mock_async_transport, mock_response
    ):
        """Test that 401 status raises AuthenticationException."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"error": "Unauthorized"}, status=401)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(AuthenticationException) as exc_info:
            await client.perform_request("GET", "/api/status")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_403_raises_authorization_exception(
        self, mock_async_transport, mock_response
    ):
        """Test that 403 status raises AuthorizationException."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"error": "Forbidden"}, status=403)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(AuthorizationException) as exc_info:
            await client.perform_request("GET", "/api/spaces/space")

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_404_raises_not_found_error(
        self, mock_async_transport, mock_response
    ):
        """Test that 404 status raises NotFoundError."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"error": "Not found"}, status=404)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(NotFoundError) as exc_info:
            await client.perform_request("GET", "/api/saved_objects/dashboard/missing")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_409_raises_conflict_error(self, mock_async_transport, mock_response):
        """Test that 409 status raises ConflictError."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"error": "Conflict"}, status=409)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(ConflictError) as exc_info:
            await client.perform_request("POST", "/api/saved_objects/dashboard")

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_500_raises_generic_api_error(
        self, mock_async_transport, mock_response
    ):
        """Test that unmapped status codes raise generic ApiError."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={"error": "Internal server error"}, status=500
            )
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(ApiError) as exc_info:
            await client.perform_request("GET", "/api/status")

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_error_includes_response_meta(
        self, mock_async_transport, mock_response
    ):
        """Test that errors include response metadata."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"error": "Not found"}, status=404)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(NotFoundError) as exc_info:
            await client.perform_request("GET", "/api/saved_objects/dashboard/missing")

        assert exc_info.value.meta is not None
        assert exc_info.value.meta.status == 404


class TestAsyncOptionsMethod:
    """Tests for AsyncBaseClient.options() method."""

    @pytest.mark.asyncio
    async def test_options_creates_new_instance(self, mock_async_transport):
        """Test that options() creates a new client instance."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(request_timeout=30)

        assert new_client is not client
        assert isinstance(new_client, AsyncBaseClient)

    @pytest.mark.asyncio
    async def test_options_with_api_key_string(self, mock_async_transport):
        """Test options() stores API key string on new client."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(api_key="test_api_key")

        assert new_client is not client
        assert new_client._api_key == "test_api_key"

    @pytest.mark.asyncio
    async def test_options_with_api_key_tuple(self, mock_async_transport):
        """Test options() stores API key tuple on new client."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(api_key=("id", "key"))

        assert new_client is not client
        assert new_client._api_key == ("id", "key")

    @pytest.mark.asyncio
    async def test_options_with_basic_auth(self, mock_async_transport):
        """Test options() stores basic auth on new client."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(basic_auth=("username", "password"))

        assert new_client is not client
        assert new_client._basic_auth == ("username", "password")

    @pytest.mark.asyncio
    async def test_options_with_bearer_auth(self, mock_async_transport):
        """Test options() stores bearer token on new client."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(bearer_auth="bearer_token")

        assert new_client is not client
        assert new_client._bearer_auth == "bearer_token"

    @pytest.mark.asyncio
    async def test_options_with_headers(self, mock_async_transport):
        """Test options() stores custom headers on new client."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(headers={"X-Custom": "value"})

        assert new_client is not client
        assert new_client._custom_headers == {"X-Custom": "value"}

    @pytest.mark.asyncio
    async def test_options_with_request_timeout(self, mock_async_transport):
        """Test options() stores request timeout on new client."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(request_timeout=60.0)

        assert new_client is not client
        assert new_client._request_timeout == 60.0

    @pytest.mark.asyncio
    async def test_options_preserves_transport(self, mock_async_transport):
        """Test that options() preserves the transport instance."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(request_timeout=30)

        # Both should reference the same transport
        assert new_client._transport is mock_async_transport


class TestAsyncLogging:
    """Tests for async logging functionality."""

    @pytest.mark.asyncio
    @patch("kibana._async.client._base.logger")
    async def test_perform_request_logs_debug(
        self, mock_logger, mock_async_transport, mock_response
    ):
        """Test that perform_request logs at DEBUG level."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"result": "success"}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        await client.perform_request("GET", "/api/status")

        # Verify debug logging was called
        assert mock_logger.debug.called

    @pytest.mark.asyncio
    @patch("kibana._async.client._base.logger")
    async def test_error_response_logs_at_debug_level(
        self, mock_logger, mock_async_transport, mock_response
    ):
        """Test that error responses are logged at DEBUG level."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"error": "Not found"}, status=404)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(NotFoundError):
            await client.perform_request("GET", "/api/saved_objects/dashboard/missing")

        assert mock_logger.debug.called

    @pytest.mark.asyncio
    async def test_debug_logging_redacts_secrets_nested_in_list(
        self, mock_async_transport, mock_response, caplog
    ):
        """A ``secrets`` dict nested inside a list-valued field is redacted.

        Async twin of the sync regression test for GitHub #78.
        """
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"result": "success"}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        body = {
            "connectors": [{"name": "my-webhook", "secrets": {"password": "hunter2"}}]
        }

        with caplog.at_level(logging.DEBUG, logger="kibana"):
            await client.perform_request("POST", "/api/actions/connector", body=body)

        log_messages = " ".join(record.message for record in caplog.records)
        assert "hunter2" not in log_messages
        assert "[REDACTED]" in log_messages
        assert "my-webhook" in log_messages

    @pytest.mark.asyncio
    async def test_debug_logging_redacts_response_body_secrets(
        self, mock_async_transport, mock_response, caplog
    ):
        """Secrets echoed back in a response body are redacted.

        Async twin of the sync regression test for GitHub #102.
        """
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "saved_objects": [
                        {
                            "id": "conn-1",
                            "attributes": {"name": "my-webhook", "password": "hunter2"},
                        }
                    ]
                },
                status=200,
            )
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with caplog.at_level(logging.DEBUG, logger="kibana"):
            await client.perform_request("POST", "/api/saved_objects/_bulk_create")

        log_messages = " ".join(record.message for record in caplog.records)
        assert "hunter2" not in log_messages
        assert "[REDACTED]" in log_messages
        assert "my-webhook" in log_messages

    @pytest.mark.asyncio
    async def test_debug_logging_redacts_list_shaped_response_body(
        self, mock_async_transport, mock_response, caplog
    ):
        """A top-level JSON array response is redacted element by element.

        Async twin of the sync regression test for GitHub #102.
        """
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body=[
                    {"name": "first", "api_key": "sk-live-abc123"},
                    {"name": "second"},
                ],
                status=200,
            )
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with caplog.at_level(logging.DEBUG, logger="kibana"):
            await client.perform_request("GET", "/api/actions/connectors")

        log_messages = " ".join(record.message for record in caplog.records)
        assert "sk-live-abc123" not in log_messages
        assert "[REDACTED]" in log_messages
        assert "second" in log_messages

    @pytest.mark.asyncio
    async def test_debug_logging_pathologically_deep_dict_body_does_not_raise(
        self, mock_async_transport, mock_response, caplog
    ):
        """A ~1000-deep dict body must not raise ``RecursionError`` out of
        ``perform_request`` when DEBUG logging is enabled -- the request
        must still reach the transport instead of aborting.

        Async twin of the sync regression test for the #78 fix-round MAJOR
        (recursion-depth cap).
        """
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"result": "success"}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        body: dict = {"leaf": "value"}
        for _ in range(1000):
            body = {"nested": body}

        with caplog.at_level(logging.DEBUG, logger="kibana"):
            await client.perform_request("POST", "/api/actions/connector", body=body)

        mock_async_transport.perform_request.assert_called_once()
        log_messages = " ".join(record.message for record in caplog.records)
        assert "<redaction depth limit>" in log_messages

    @pytest.mark.asyncio
    async def test_debug_logging_pathologically_deep_list_body_does_not_raise(
        self, mock_async_transport, mock_response, caplog
    ):
        """Same fail-closed guarantee for a ~1000-deep list body (the other
        recursion axis, same shared depth cap). Async twin of the sync test."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"result": "success"}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        items: list = ["leaf"]
        for _ in range(1000):
            items = [items]
        body = {"items": items}

        with caplog.at_level(logging.DEBUG, logger="kibana"):
            await client.perform_request("POST", "/api/actions/connector", body=body)

        mock_async_transport.perform_request.assert_called_once()
        log_messages = " ".join(record.message for record in caplog.records)
        assert "<redaction depth limit>" in log_messages

    @pytest.mark.asyncio
    async def test_debug_logging_namedtuple_bearing_body_does_not_raise(
        self, mock_async_transport, mock_response, caplog
    ):
        """A namedtuple-valued body field must not crash ``perform_request``.

        Async twin of the sync regression test for the #78 fix-round
        BLOCKER (``type(values)(redacted_elements)`` crashing on a
        multi-field namedtuple).
        """
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"result": "success"}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        Point = namedtuple("Point", ["x", "y"])
        body = {
            "connectors": Point(x={"secrets": {"password": "hunter2"}}, y="keep-me")
        }

        with caplog.at_level(logging.DEBUG, logger="kibana"):
            await client.perform_request("POST", "/api/actions/connector", body=body)

        mock_async_transport.perform_request.assert_called_once()
        log_messages = " ".join(record.message for record in caplog.records)
        assert "hunter2" not in log_messages
        assert "[REDACTED]" in log_messages
        assert "keep-me" in log_messages

    @pytest.mark.asyncio
    async def test_debug_logging_redacts_secrets_in_top_level_list_body(
        self, mock_async_transport, mock_response, caplog
    ):
        """A sensitive key inside an element of a TOP-LEVEL LIST body is
        redacted, not just one nested inside a dict.

        Async twin of the sync regression test for GitHub #92
        (``saved_objects.bulk_create`` and the other bulk endpoints send a
        bare list body, which bypassed ``_redact_body_secrets`` entirely).
        """
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"saved_objects": []}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        body = [
            {"type": "tag", "attributes": {"name": "one"}},
            {"type": "connector", "attributes": {"secrets": {"password": "hunter2"}}},
        ]

        with caplog.at_level(logging.DEBUG, logger="kibana"):
            await client.perform_request(
                "POST", "/api/saved_objects/_bulk_create", body=body
            )

        log_messages = " ".join(record.message for record in caplog.records)
        assert "hunter2" not in log_messages
        assert "[REDACTED]" in log_messages
        assert "raw bytes" not in log_messages

    @pytest.mark.asyncio
    async def test_debug_logging_redacts_secrets_in_top_level_tuple_body(
        self, mock_async_transport, mock_response, caplog
    ):
        """Tuple variant of the top-level-list case: a bare tuple body is
        redacted element-wise too. Async twin of the sync test."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"saved_objects": []}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        body = ({"type": "connector", "secrets": {"token": "abc123"}},)

        with caplog.at_level(logging.DEBUG, logger="kibana"):
            await client.perform_request(
                "POST", "/api/saved_objects/_bulk_create", body=body
            )

        log_messages = " ".join(record.message for record in caplog.records)
        assert "abc123" not in log_messages
        assert "[REDACTED]" in log_messages
        assert "raw bytes" not in log_messages

    @pytest.mark.asyncio
    async def test_debug_logging_top_level_empty_list_body_does_not_raise(
        self, mock_async_transport, mock_response, caplog
    ):
        """An empty top-level list body is logged without error. Async twin
        of the sync test."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"saved_objects": []}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with caplog.at_level(logging.DEBUG, logger="kibana"):
            await client.perform_request(
                "POST", "/api/saved_objects/_bulk_get", body=[]
            )

        mock_async_transport.perform_request.assert_called_once()
        log_messages = " ".join(record.message for record in caplog.records)
        assert "Request body: []" in log_messages

    @pytest.mark.asyncio
    async def test_debug_logging_top_level_list_of_scalars_untouched(
        self, mock_async_transport, mock_response, caplog
    ):
        """A top-level list of plain scalars passes through unredacted and
        unchanged. Async twin of the sync test."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"statuses": []}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with caplog.at_level(logging.DEBUG, logger="kibana"):
            await client.perform_request(
                "POST", "/api/saved_objects/_bulk_delete", body=["tag-1", "tag-2"]
            )

        log_messages = " ".join(record.message for record in caplog.records)
        assert "tag-1" in log_messages
        assert "tag-2" in log_messages

    @pytest.mark.asyncio
    async def test_debug_logging_top_level_list_body_is_not_mutated(
        self, mock_async_transport, mock_response, caplog
    ):
        """The caller's original top-level list body is never modified in
        place by DEBUG-log redaction. Async twin of the sync test."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"saved_objects": []}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        secrets_dict = {"password": "hunter2"}
        obj = {"type": "connector", "attributes": {"secrets": secrets_dict}}
        body = [obj]

        with caplog.at_level(logging.DEBUG, logger="kibana"):
            await client.perform_request(
                "POST", "/api/saved_objects/_bulk_create", body=body
            )

        assert body == [obj]
        assert body[0] is obj
        assert body[0]["attributes"]["secrets"] is secrets_dict
        assert body[0]["attributes"]["secrets"]["password"] == "hunter2"
