"""Unit tests for UpgradeAssistantClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.upgrade_assistant import UpgradeAssistantClient
from kibana.exceptions import AuthorizationException, NotFoundError


class TestUpgradeAssistantClientInitialization:
    """Test UpgradeAssistantClient initialization."""

    def test_upgrade_assistant_client_initialization(self, mock_transport):
        """Test that UpgradeAssistantClient can be initialized with a parent client."""
        client = Kibana(_transport=mock_transport)
        ua_client = UpgradeAssistantClient(client)
        assert ua_client._client is client

    def test_upgrade_assistant_property_returns_client(self, mock_transport):
        """Test that client.upgrade_assistant returns an UpgradeAssistantClient."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.upgrade_assistant, UpgradeAssistantClient)

    def test_upgrade_assistant_property_caching(self, mock_transport):
        """Test that the upgrade_assistant property returns the same instance."""
        client = Kibana(_transport=mock_transport)
        assert client.upgrade_assistant is client.upgrade_assistant


class TestUpgradeAssistantClientStatus:
    """Test UpgradeAssistantClient.status() method."""

    def test_status_ready_for_upgrade(self, mock_transport):
        """Test status retrieval when the cluster is ready for upgrade."""
        mock_response = ObjectApiResponse(
            body={
                "readyForUpgrade": True,
                "details": "All deprecation warnings have been resolved.",
                "recentEsDeprecationLogs": {"count": 0, "logs": []},
                "kibanaApiDeprecations": [],
            },
            meta=Mock(status=200, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)
        result = client.upgrade_assistant.status()

        assert result.body["readyForUpgrade"] is True
        assert result.body["recentEsDeprecationLogs"]["count"] == 0

        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/upgrade_assistant/status"
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert call_kwargs.get("body") is None

    def test_status_not_ready_for_upgrade(self, mock_transport):
        """Test status retrieval when deprecation issues remain."""
        mock_response = ObjectApiResponse(
            body={
                "readyForUpgrade": False,
                "cluster": [
                    {
                        "message": "Cluster deprecated issue",
                        "details": (
                            "You have 2 system indices that must be migrated "
                            "and 5 Elasticsearch deprecation issues and 0 "
                            "Kibana deprecation issues that must be resolved "
                            "before upgrading."
                        ),
                    }
                ],
            },
            meta=Mock(status=200, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)
        result = client.upgrade_assistant.status()

        assert result.body["readyForUpgrade"] is False
        assert result.body["cluster"][0]["message"] == "Cluster deprecated issue"


class TestUpgradeAssistantClientErrorHandling:
    """Test UpgradeAssistantClient error handling."""

    def test_status_not_found_error(self, mock_transport):
        """Test that a 404 response raises NotFoundError."""
        mock_response = ObjectApiResponse(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Not Found",
            },
            meta=Mock(status=404, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)

        with pytest.raises(NotFoundError):
            client.upgrade_assistant.status()

    def test_status_authorization_error(self, mock_transport):
        """Test that a 403 response raises AuthorizationException."""
        mock_response = ObjectApiResponse(
            body={
                "statusCode": 403,
                "error": "Forbidden",
                "message": "Insufficient privileges",
            },
            meta=Mock(status=403, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)

        with pytest.raises(AuthorizationException):
            client.upgrade_assistant.status()
