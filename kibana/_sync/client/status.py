"""Kibana Status API client."""

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient

if TYPE_CHECKING:
    from kibana._sync.client import Kibana


class StatusClient(NamespaceClient):
    """Client for Kibana Status API operations.

    The Status API provides health and operational information about the Kibana
    server and its dependencies. This is useful for monitoring, health checks,
    and troubleshooting.

    Status levels:
        - available: All services are operational
        - degraded: Some services are experiencing issues but Kibana is functional
        - unavailable: Critical services are down, Kibana may not be functional

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Check overall status
        >>> status = client.status.get_status()
        >>> print(status.body["status"]["overall"]["level"])
        available
        >>>
        >>> # Check individual service statuses
        >>> for service, info in status.body["status"]["statuses"].items():
        ...     print(f"{service}: {info['level']}")
        elasticsearch: available
        savedObjects: available
        >>>
        >>> # Get operational statistics
        >>> stats = client.status.get_stats()
        >>> print(stats.body["process"]["memory"]["heap"]["used_in_bytes"])
    """

    def __init__(self, client: "Kibana") -> None:
        """Initialize the StatusClient.

        Args:
            client: The parent Kibana client instance to delegate requests to.

        Example:
            >>> status_client = StatusClient(kibana_client)
        """
        super().__init__(client)

    def get_status(self) -> ObjectApiResponse[dict[str, Any]]:
        """Get the current status of the Kibana server.

        Returns comprehensive health information about the Kibana server and
        its dependencies. This endpoint is commonly used for health checks
        in monitoring systems and load balancers.

        The response includes:
            - Overall status level (available, degraded, unavailable)
            - Individual service statuses (Elasticsearch, SavedObjects, etc.)
            - Version information (Kibana version, build number)
            - Server identification (name, UUID)
            - Detailed status messages for each service

        Returns:
            ObjectApiResponse containing status information with the following structure:
                - status.overall.level: Overall status level
                - status.overall.summary: Human-readable status summary
                - status.statuses: Dictionary of individual service statuses
                - version: Kibana version information
                - name: Server name
                - uuid: Server UUID

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to view status.
            TransportError: If unable to connect to Kibana.

        Example:
            >>> # Basic status check
            >>> status = client.status.get_status()
            >>> if status.body["status"]["overall"]["level"] == "available":
            ...     print("Kibana is healthy")
            ... else:
            ...     print("Kibana has issues")
            Kibana is healthy
            >>>
            >>> # Check specific service status
            >>> es_status = status.body["status"]["statuses"]["elasticsearch"]
            >>> print(f"Elasticsearch: {es_status['level']}")
            >>> if es_status['level'] != 'available':
            ...     print(f"Issue: {es_status.get('summary', 'Unknown')}")
            Elasticsearch: available
            >>>
            >>> # Get version information
            >>> version = status.body["version"]
            >>> print(f"Kibana {version['number']} (build {version['build_number']})")
            Kibana 8.11.0 (build 12345)
        """
        return self.perform_request(
            "GET",
            "/api/status",
            headers={"accept": "application/json"},
        )

    def get_stats(self) -> ObjectApiResponse[dict[str, Any]]:
        """Get operational statistics about the Kibana server.

        Returns detailed performance and resource utilization metrics for the
        Kibana server. This is useful for monitoring, capacity planning, and
        performance troubleshooting.

        The response includes:
            - Process metrics (memory usage, uptime, event loop delay)
            - OS metrics (platform, CPU load, memory, uptime)
            - HTTP metrics (response times, request counts, connections)
            - Request statistics (total, disconnects, status codes)

        Returns:
            ObjectApiResponse containing statistics with the following structure:
                - process: Process-level metrics (memory, uptime, event loop)
                - os: Operating system metrics (platform, load, memory)
                - response_times: HTTP response time statistics
                - requests: Request count statistics
                - concurrent_connections: Current connection count

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to view stats.
            TransportError: If unable to connect to Kibana.

        Example:
            >>> # Get server statistics
            >>> stats = client.status.get_stats()
            >>>
            >>> # Check memory usage
            >>> heap = stats.body["process"]["memory"]["heap"]
            >>> used_mb = heap["used_in_bytes"] / (1024 * 1024)
            >>> total_mb = heap["total_in_bytes"] / (1024 * 1024)
            >>> print(f"Heap: {used_mb:.1f}MB / {total_mb:.1f}MB")
            Heap: 245.3MB / 512.0MB
            >>>
            >>> # Check uptime
            >>> uptime_sec = stats.body["process"]["uptime_in_millis"] / 1000
            >>> uptime_hours = uptime_sec / 3600
            >>> print(f"Uptime: {uptime_hours:.1f} hours")
            Uptime: 24.5 hours
            >>>
            >>> # Check response times
            >>> response_times = stats.body.get("response_times", {})
            >>> if "avg_in_millis" in response_times:
            ...     print(f"Avg response time: {response_times['avg_in_millis']}ms")
            Avg response time: 45ms
            >>>
            >>> # Check concurrent connections
            >>> connections = stats.body.get("concurrent_connections", 0)
            >>> print(f"Active connections: {connections}")
            Active connections: 12
        """
        return self.perform_request(
            "GET",
            "/api/stats",
            headers={"accept": "application/json"},
        )
