"""Kibana Status API client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient

if TYPE_CHECKING:
    from kibana._sync.client import Kibana


class StatusClient(NamespaceClient):
    """Client for Kibana Status and system information API operations.

    The Status API provides health and operational information about the Kibana
    server and its dependencies. This is useful for monitoring, health checks,
    and troubleshooting. It also exposes the Kibana features registry
    (``GET /api/features``, technical preview in 9.4).

    Status levels (Kibana 8/9 "v8" format):
        - available: All services are operational
        - degraded: Some services are experiencing issues but Kibana is functional
        - unavailable: Critical services are down, Kibana may not be functional
        - critical: Kibana is in a critical state (defined by the spec enum)

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Check overall status
        >>> status = client.status.get_status()
        >>> print(status.body["status"]["overall"]["level"])
        available
        >>>
        >>> # Check core service statuses (elasticsearch, savedObjects)
        >>> for service, info in status.body["status"]["core"].items():
        ...     print(f"{service}: {info['level']}")
        elasticsearch: available
        savedObjects: available
        >>>
        >>> # Get operational statistics
        >>> stats = client.status.get_stats()
        >>> print(stats.body["process"]["memory"]["heap"]["used_bytes"])
    """

    def __init__(self, client: Kibana) -> None:
        """Initialize the StatusClient.

        Args:
            client: The parent Kibana client instance to delegate requests to.

        Example:
            >>> status_client = StatusClient(kibana_client)
        """
        super().__init__(client)

    def get_status(
        self,
        *,
        v7format: bool | None = None,
        v8format: bool | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """Get the current status of the Kibana server.

        Returns comprehensive health information about the Kibana server and
        its dependencies. This endpoint is commonly used for health checks
        in monitoring systems and load balancers.

        The default (v8) response includes:
            - Overall status level (available, degraded, unavailable, critical)
            - Core service statuses under ``status.core`` (elasticsearch,
              savedObjects)
            - Per-plugin statuses under ``status.plugins``
            - Version information (Kibana version, build number)
            - Server identification (name, UUID) and runtime metrics

        Args:
            v7format: Set to ``True`` to get the response in the legacy v7
                format, where ``status.overall`` has ``state``/``title`` keys
                and ``status.statuses`` is a *list* of service entries.
                Mutually exclusive with ``v8format``.
            v8format: Set to ``True`` to explicitly request the v8 format
                (the default shape described below). Mutually exclusive with
                ``v7format``; passing both yields a 400 Bad Request.

        Returns:
            ObjectApiResponse containing status information with the following
            structure (default v8 format):

            - ``status.overall.level`` -- Overall status level
            - ``status.overall.summary`` -- Human-readable status summary
            - ``status.core`` -- Dict of core service statuses
              (``elasticsearch``, ``savedObjects``)
            - ``status.plugins`` -- Dict of per-plugin statuses
            - ``version`` -- Kibana version information
            - ``name`` -- Server name
            - ``uuid`` -- Server UUID
            - ``metrics`` -- Last-collected runtime metrics

        Raises:
            BadRequestError: If both ``v7format`` and ``v8format`` are provided.
            ApiError: If Kibana returns an error response. Per the 9.4.3 spec,
                a 503 (with a status body) is returned when Kibana or an
                essential service is unavailable.
            TransportError: If unable to connect to Kibana.

        Note:
            This endpoint is anonymously accessible. Unauthenticated callers
            receive HTTP 200 with a redacted minimal body containing only
            ``{"status": {"overall": {"level": ...}}}`` — top-level ``name``,
            ``uuid`` and ``version`` keys are absent in that case.

        Example:
            >>> # Basic status check
            >>> status = client.status.get_status()
            >>> if status.body["status"]["overall"]["level"] == "available":
            ...     print("Kibana is healthy")
            ... else:
            ...     print("Kibana has issues")
            Kibana is healthy
            >>>
            >>> # Check a core service status
            >>> es_status = status.body["status"]["core"]["elasticsearch"]
            >>> print(f"Elasticsearch: {es_status['level']}")
            Elasticsearch: available
            >>>
            >>> # Get version information
            >>> version = status.body["version"]
            >>> print(f"Kibana {version['number']} (build {version['build_number']})")
            Kibana 9.4.3 (build 102392)
            >>>
            >>> # Legacy v7 format: statuses is a list
            >>> legacy = client.status.get_status(v7format=True)
            >>> print(legacy.body["status"]["overall"]["state"])
            green
        """
        params: dict[str, Any] = {}
        if v7format is not None:
            params["v7format"] = v7format
        if v8format is not None:
            params["v8format"] = v8format
        return self.perform_request(
            "GET",
            "/api/status",
            params=params or None,
            headers={"accept": "application/json"},
        )

    def get_stats(
        self,
        *,
        extended: bool | None = None,
        legacy: bool | None = None,
        exclude_usage: bool | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """Get operational statistics about the Kibana server.

        Returns detailed performance and resource utilization metrics for the
        Kibana server. This is useful for monitoring, capacity planning, and
        performance troubleshooting.

        Note:
            ``GET /api/stats`` is not part of the official Kibana 9.4.3
            OpenAPI document, but it is served by the usage-collection plugin
            and verified working against a live 9.4.3 server.

        The response includes:
            - process: Process metrics — ``memory.heap.used_bytes`` /
              ``total_bytes``, ``memory.resident_set_size_bytes``,
              ``uptime_ms``, event loop delay/utilization
            - os: OS metrics — ``platform``, ``platform_release``, ``load``,
              ``memory.total_bytes`` / ``free_bytes`` / ``used_bytes``,
              ``uptime_ms``
            - response_times: HTTP response times (``avg_ms``, ``max_ms``)
            - requests: Request counts (total, disconnects, status_codes)
            - concurrent_connections: Current connection count
            - kibana: Server identification (uuid, name, version, status)
            - elasticsearch_client: ES client socket/queue statistics

        Args:
            extended: When ``True``, include additional payload such as
                ``usage`` and the ``cluster_uuid``.
            legacy: When ``True``, format the extended payload in the legacy
                (camelCase) style, e.g. ``clusterUuid`` instead of
                ``cluster_uuid``.
            exclude_usage: When ``True`` (with ``extended``), skip collecting
                the ``usage`` payload. On live 9.4.3 the ``usage`` key is
                present but empty either way (usage collection moved out of
                ``/api/stats``).

        Returns:
            ObjectApiResponse containing statistics with the following structure:
                - process: Process-level metrics (memory, uptime_ms, event loop)
                - os: Operating system metrics (platform, load, memory)
                - response_times: HTTP response time statistics (avg_ms, max_ms)
                - requests: Request count statistics
                - concurrent_connections: Current connection count
                - kibana: Server metadata (uuid, name, version, status)

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to view stats.
            TransportError: If unable to connect to Kibana.

        Example:
            >>> # Get server statistics
            >>> stats = client.status.get_stats()
            >>>
            >>> # Check memory usage (9.x field names)
            >>> heap = stats.body["process"]["memory"]["heap"]
            >>> used_mb = heap["used_bytes"] / (1024 * 1024)
            >>> total_mb = heap["total_bytes"] / (1024 * 1024)
            >>> print(f"Heap: {used_mb:.1f}MB / {total_mb:.1f}MB")
            Heap: 245.3MB / 512.0MB
            >>>
            >>> # Check uptime
            >>> uptime_hours = stats.body["process"]["uptime_ms"] / 3600000
            >>> print(f"Uptime: {uptime_hours:.1f} hours")
            Uptime: 24.5 hours
            >>>
            >>> # Check response times
            >>> response_times = stats.body.get("response_times", {})
            >>> if "avg_ms" in response_times:
            ...     print(f"Avg response time: {response_times['avg_ms']:.0f}ms")
            Avg response time: 45ms
            >>>
            >>> # Check concurrent connections
            >>> connections = stats.body.get("concurrent_connections", 0)
            >>> print(f"Active connections: {connections}")
            Active connections: 12
        """
        params: dict[str, Any] = {}
        if extended is not None:
            params["extended"] = extended
        if legacy is not None:
            params["legacy"] = legacy
        if exclude_usage is not None:
            params["exclude_usage"] = exclude_usage
        return self.perform_request(
            "GET",
            "/api/stats",
            params=params or None,
            headers={"accept": "application/json"},
        )

    def get_features(self) -> ObjectApiResponse[Any]:
        """Get information about all Kibana features.

        Features are used by spaces and security to refine and secure access
        to Kibana. Each feature describes its category, associated apps,
        catalogue entries, and the privileges it exposes.

        Note:
            Technical preview in 9.4 — this endpoint (``GET /api/features``)
            may change or be removed in a future release.

        Returns:
            ObjectApiResponse whose body is a JSON *array* of feature objects
            (a ``ListApiResponse`` at runtime). Each feature object contains:

            - ``id`` -- Feature identifier (e.g. ``"dashboard_v2"``)
            - ``name`` -- Human-readable feature name
            - ``category`` -- Feature category (id, label, order)
            - ``app`` -- List of associated Kibana app IDs
            - ``catalogue`` -- List of associated catalogue entry IDs
            - ``privileges`` -- Privilege definitions (``all``/``read``), when
              the feature exposes security privileges
            - ``order`` -- Display ordering hint (optional)

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to read features.
            TransportError: If unable to connect to Kibana.

        Example:
            >>> features = client.status.get_features()
            >>> for feature in features.body[:3]:
            ...     print(feature["id"], "-", feature["name"])
            searchSynonyms - Synonyms
            discover_v2 - Discover
            dashboard_v2 - Dashboard
        """
        return self.perform_request(
            "GET",
            "/api/features",
            headers={"accept": "application/json"},
        )
