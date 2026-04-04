"""Async Kibana Status API client."""

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


class AsyncStatusClient(AsyncNamespaceClient):
    """Async client for Kibana Status API operations."""

    def __init__(self, client: "AsyncKibana") -> None:
        """
        Initialize the AsyncStatusClient.

        :param client: The parent AsyncKibana client instance
        """
        super().__init__(client)

    async def get_status(self) -> ObjectApiResponse[dict[str, Any]]:
        """
        Get the current status of the Kibana server.

        Returns information about the Kibana server status including:
        - Overall status level (available, degraded, unavailable)
        - Individual service statuses (Elasticsearch, SavedObjects, etc.)
        - Version information
        - Server name and UUID

        :return: ObjectApiResponse containing status information
        """
        return await self.perform_request(
            "GET",
            "/api/status",
            headers={"accept": "application/json"},
        )

    async def get_stats(self) -> ObjectApiResponse[dict[str, Any]]:
        """
        Get operational statistics about the Kibana server.

        Returns detailed metrics including:
        - Process information (memory usage, uptime)
        - OS information (platform, load, memory)
        - Response times and request counts
        - Concurrent connections

        :return: ObjectApiResponse containing statistics
        """
        return await self.perform_request(
            "GET",
            "/api/stats",
            headers={"accept": "application/json"},
        )
