"""Kibana Uptime API client."""

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient

if TYPE_CHECKING:
    from kibana._sync.client import Kibana


class UptimeClient(NamespaceClient):
    """Client for the Kibana Uptime API.

    The Uptime app in Kibana uses Heartbeat data to monitor the availability
    of services. The Uptime settings API lets you read and update the
    app-wide settings: the Heartbeat index pattern used to query monitoring
    data, TLS certificate alerting thresholds, and default alert connectors
    and email recipients.

    Uptime settings are space-scoped: each Kibana space keeps its own
    settings document. Every method accepts an optional ``space_id`` to
    target a specific space (``None`` targets the default space or the space
    the client is scoped to).

    Reading the settings requires ``read`` privileges for the uptime feature
    in the Observability section of the Kibana feature privileges; updating
    them requires ``all`` privileges.

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Read the current settings
        >>> settings = client.uptime.get_settings()
        >>> print(settings.body["heartbeatIndices"])
        heartbeat-*
        >>>
        >>> # Partially update a single setting (other keys are preserved)
        >>> updated = client.uptime.update_settings(cert_age_threshold=365)
        >>> print(updated.body["certAgeThreshold"])
        365
    """

    def __init__(
        self,
        client: Kibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the UptimeClient.

        Args:
            client: The parent Kibana client instance to delegate requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> uptime_client = UptimeClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    def get_settings(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get uptime settings.

        Returns the Uptime app settings for the targeted space. You must
        have ``read`` privileges for the uptime feature in the Observability
        section of the Kibana feature privileges.

        Args:
            space_id: Optional space ID to read the settings from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the uptime settings:
                - heartbeatIndices: Index pattern used to query Heartbeat
                  data (default ``"heartbeat-*"``)
                - certExpirationThreshold: Days before a certificate expires
                  to trigger an alert (default 30)
                - certAgeThreshold: Days after a certificate is created to
                  trigger an alert (default 730)
                - defaultConnectors: List of connector IDs used as default
                  connectors for new alerts
                - defaultEmail: Default email configuration for new alerts
                  (``to``/``cc``/``bcc`` recipient lists)

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to read the
                uptime settings.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> settings = client.uptime.get_settings()
            >>> print(settings.body["heartbeatIndices"])
            heartbeat-*
            >>> print(settings.body["certExpirationThreshold"])
            30
        """
        path = self._build_space_path("/api/uptime/settings", space_id, validate_spaces)
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def update_settings(
        self,
        *,
        heartbeat_indices: str | None = None,
        cert_expiration_threshold: float | None = None,
        cert_age_threshold: float | None = None,
        default_connectors: list[str] | None = None,
        default_email: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update uptime settings.

        Updates the Uptime app settings for the targeted space. A partial
        update is supported: provided settings keys are merged with the
        existing settings and the full resulting settings object is
        returned. You must have ``all`` privileges for the uptime feature in
        the Observability section of the Kibana feature privileges.

        Args:
            heartbeat_indices: An index pattern string to be used within the
                Uptime app and alerts to query Heartbeat data (default
                ``"heartbeat-*"``).
            cert_expiration_threshold: The number of days before a
                certificate expires to trigger an alert (default 30).
            cert_age_threshold: The number of days after a certificate is
                created to trigger an alert (default 730).
            default_connectors: A list of connector IDs to be used as
                default connectors for new alerts.
            default_email: The default email configuration for new alerts,
                an object with optional ``to``, ``cc`` and ``bcc`` recipient
                lists, e.g. ``{"to": ["ops@example.com"], "cc": [], "bcc": []}``.
            space_id: Optional space ID to update the settings in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the full updated uptime settings
            (same shape as :meth:`get_settings`).

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to update the
                uptime settings.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = client.uptime.update_settings(
            ...     heartbeat_indices="heartbeat-8*",
            ...     cert_expiration_threshold=14,
            ... )
            >>> print(updated.body["heartbeatIndices"])
            heartbeat-8*
            >>> print(updated.body["certExpirationThreshold"])
            14
        """
        body: dict[str, Any] = {}
        if heartbeat_indices is not None:
            body["heartbeatIndices"] = heartbeat_indices
        if cert_expiration_threshold is not None:
            body["certExpirationThreshold"] = cert_expiration_threshold
        if cert_age_threshold is not None:
            body["certAgeThreshold"] = cert_age_threshold
        if default_connectors is not None:
            body["defaultConnectors"] = default_connectors
        if default_email is not None:
            body["defaultEmail"] = default_email

        path = self._build_space_path("/api/uptime/settings", space_id, validate_spaces)
        return self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )
