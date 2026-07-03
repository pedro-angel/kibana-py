"""Unit tests for AsyncUpgradeAssistantClient."""

from unittest.mock import AsyncMock

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client.upgrade_assistant import AsyncUpgradeAssistantClient
from kibana.exceptions import AuthorizationException, NotFoundError


class TestAsyncUpgradeAssistantClientInitialization:
    """Test AsyncUpgradeAssistantClient initialization."""

    @pytest.mark.asyncio
    async def test_upgrade_assistant_client_initialization(self, mock_async_transport):
        """Test that AsyncUpgradeAssistantClient can be initialized with a parent."""
        client = AsyncKibana(_transport=mock_async_transport)
        ua_client = AsyncUpgradeAssistantClient(client)
        assert ua_client._client is client

    @pytest.mark.asyncio
    async def test_upgrade_assistant_property_returns_client(
        self, mock_async_transport
    ):
        """Test that client.upgrade_assistant returns an AsyncUpgradeAssistantClient."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.upgrade_assistant, AsyncUpgradeAssistantClient)

    @pytest.mark.asyncio
    async def test_upgrade_assistant_property_caching(self, mock_async_transport):
        """Test that the upgrade_assistant property returns the same instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert client.upgrade_assistant is client.upgrade_assistant


class TestAsyncUpgradeAssistantClientStatus:
    """Test AsyncUpgradeAssistantClient.status() method."""

    @pytest.mark.asyncio
    async def test_status_ready_for_upgrade(self, mock_async_transport, mock_response):
        """Test status retrieval when the cluster is ready for upgrade."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "readyForUpgrade": True,
                    "details": "All deprecation warnings have been resolved.",
                    "recentEsDeprecationLogs": {"count": 0, "logs": []},
                    "kibanaApiDeprecations": [],
                },
                status=200,
            )
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.upgrade_assistant.status()

        assert result.body["readyForUpgrade"] is True
        assert result.body["recentEsDeprecationLogs"]["count"] == 0

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/upgrade_assistant/status"
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_status_not_ready_for_upgrade(
        self, mock_async_transport, mock_response
    ):
        """Test status retrieval when deprecation issues remain."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "readyForUpgrade": False,
                    "cluster": [
                        {
                            "message": "Cluster deprecated issue",
                            "details": (
                                "You have 2 system indices that must be "
                                "migrated and 5 Elasticsearch deprecation "
                                "issues and 0 Kibana deprecation issues that "
                                "must be resolved before upgrading."
                            ),
                        }
                    ],
                },
                status=200,
            )
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.upgrade_assistant.status()

        assert result.body["readyForUpgrade"] is False
        assert result.body["cluster"][0]["message"] == "Cluster deprecated issue"


class TestAsyncUpgradeAssistantClientErrorHandling:
    """Test AsyncUpgradeAssistantClient error handling."""

    @pytest.mark.asyncio
    async def test_status_not_found_error(self, mock_async_transport, mock_response):
        """Test that a 404 response raises NotFoundError."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "statusCode": 404,
                    "error": "Not Found",
                    "message": "Not Found",
                },
                status=404,
            )
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(NotFoundError):
            await client.upgrade_assistant.status()

    @pytest.mark.asyncio
    async def test_status_authorization_error(
        self, mock_async_transport, mock_response
    ):
        """Test that a 403 response raises AuthorizationException."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "statusCode": 403,
                    "error": "Forbidden",
                    "message": "Insufficient privileges",
                },
                status=403,
            )
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(AuthorizationException):
            await client.upgrade_assistant.status()
