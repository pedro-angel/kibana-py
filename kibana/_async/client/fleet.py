"""Async Kibana Fleet core API (setup, settings, health) client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


class AsyncFleetClient(AsyncNamespaceClient):
    """Async client for the Kibana Fleet core API (setup, settings, health).

    Fleet provides a web-based UI and APIs in Kibana for centrally managing
    Elastic Agents and their policies. This client covers the Fleet
    internals: initializing Fleet (``setup``), reading and updating the
    global Fleet settings, reading and updating the per-space Fleet
    settings, checking Fleet Server health, and checking the current user's
    Fleet permissions.

    All Fleet APIs are space-aware: every method accepts an optional
    ``space_id`` to target a specific Kibana space (``None`` targets the
    default space or the space the client is scoped to).

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Initialize Fleet (idempotent)
        >>> result = await client.fleet.setup()
        >>> print(result.body["isInitialized"])
        True
        >>>
        >>> # Read the global Fleet settings
        >>> settings = await client.fleet.get_settings()
        >>> print(settings.body["item"]["id"])
        fleet-default-settings
    """

    def __init__(
        self,
        client: AsyncKibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the AsyncFleetClient.

        Args:
            client: The parent AsyncKibana client instance to delegate
                requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> fleet_client = AsyncFleetClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    async def setup(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Initiate Fleet setup.

        Initialize Fleet and create the necessary Elasticsearch resources
        for Fleet to operate. Safe to call multiple times (idempotent).
        Returns the initialization status and any non-fatal errors
        encountered during setup.

        Args:
            space_id: Optional space ID to run the setup in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the setup result:
                - isInitialized: True if Fleet is ready to accept agent
                  enrollment
                - nonFatalErrors: List of ``{"name", "message"}`` objects
                  describing non-blocking issues encountered during setup

        Raises:
            BadRequestError: If the request is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            ApiError: If Fleet setup fails with an internal server error.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.fleet.setup()
            >>> print(result.body["isInitialized"])
            True
            >>> print(result.body["nonFatalErrors"])
            []
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/setup", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def get_settings(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get settings.

        Get the global Fleet settings.

        Args:
            space_id: Optional space ID to read the settings from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing an ``item`` object with the global
            Fleet settings, including ``id``, ``version``,
            ``prerelease_integrations_enabled``,
            ``delete_unenrolled_agents``, ``preconfigured_fields``,
            ``ilm_migration_status`` and secret-storage requirement flags.

        Raises:
            NotFoundError: If Fleet settings have not been initialized.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges
                (requires ``fleet-settings-read``).
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> settings = await client.fleet.get_settings()
            >>> print(settings.body["item"]["prerelease_integrations_enabled"])
            False
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/settings", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update_settings(
        self,
        *,
        additional_yaml_config: str | None = None,
        delete_unenrolled_agents: dict[str, Any] | None = None,
        has_seen_add_data_notice: bool | None = None,
        integration_knowledge_enabled: bool | None = None,
        kibana_ca_sha256: str | None = None,
        kibana_urls: list[str] | None = None,
        prerelease_integrations_enabled: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update settings.

        Update the global Fleet settings. Only the provided fields are
        changed; omitted fields keep their current values.

        Args:
            additional_yaml_config: Deprecated. Additional Fleet Server YAML
                configuration.
            delete_unenrolled_agents: Automatic deletion policy for
                unenrolled agents, an object with the required keys
                ``enabled`` (bool) and ``is_preconfigured`` (bool).
            has_seen_add_data_notice: Deprecated. Whether the "add data"
                notice has been dismissed.
            integration_knowledge_enabled: Whether integration knowledge
                content is enabled.
            kibana_ca_sha256: Deprecated. SHA-256 of the Kibana CA
                certificate.
            kibana_urls: Deprecated. Kibana URLs used by agents (maximum 10
                URI strings).
            prerelease_integrations_enabled: Whether pre-release
                integrations may be installed from the package registry.
            space_id: Optional space ID to update the settings in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing an ``item`` object with the updated
            global Fleet settings.

        Raises:
            BadRequestError: If the request body is invalid.
            NotFoundError: If Fleet settings have not been initialized.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges
                (requires ``fleet-settings-all``).
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.fleet.update_settings(
            ...     prerelease_integrations_enabled=True,
            ... )
            >>> print(updated.body["item"]["prerelease_integrations_enabled"])
            True
        """
        body: dict[str, Any] = {}
        if additional_yaml_config is not None:
            body["additional_yaml_config"] = additional_yaml_config
        if delete_unenrolled_agents is not None:
            body["delete_unenrolled_agents"] = delete_unenrolled_agents
        if has_seen_add_data_notice is not None:
            body["has_seen_add_data_notice"] = has_seen_add_data_notice
        if integration_knowledge_enabled is not None:
            body["integration_knowledge_enabled"] = integration_knowledge_enabled
        if kibana_ca_sha256 is not None:
            body["kibana_ca_sha256"] = kibana_ca_sha256
        if kibana_urls is not None:
            body["kibana_urls"] = kibana_urls
        if prerelease_integrations_enabled is not None:
            body["prerelease_integrations_enabled"] = prerelease_integrations_enabled

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/settings", space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_space_settings(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get space settings.

        Get the Fleet settings for the current Kibana space. Added in
        Kibana 9.1.0.

        Args:
            space_id: Optional space ID to read the space settings from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing an ``item`` object with:
                - allowed_namespace_prefixes: List of namespace prefixes
                  allowed in this space
                - managed_by: Optional identifier of the manager of these
                  settings

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> settings = await client.fleet.get_space_settings()
            >>> print(settings.body["item"]["allowed_namespace_prefixes"])
            []
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/space_settings", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update_space_settings(
        self,
        *,
        allowed_namespace_prefixes: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create or update space settings.

        Create or update the Fleet settings for the current Kibana space.
        Added in Kibana 9.1.0.

        Note: as of Kibana 9.4.3 the live server rejects prefixes that
        contain a ``-`` character (``Must not contain -``), even though the
        published OpenAPI schema allows arbitrary strings.

        Args:
            allowed_namespace_prefixes: List of namespace prefixes (maximum
                10) that data streams in this space are allowed to use.
                Pass an empty list to remove all restrictions.
            space_id: Optional space ID to update the space settings in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing an ``item`` object with the updated
            ``allowed_namespace_prefixes`` (and optionally ``managed_by``).

        Raises:
            BadRequestError: If the request body is invalid (for example, a
                prefix containing ``-``).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges
                (requires ``fleet-settings-all``).
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.fleet.update_space_settings(
            ...     allowed_namespace_prefixes=["teama", "teamb"],
            ... )
            >>> print(updated.body["item"]["allowed_namespace_prefixes"])
            ['teama', 'teamb']
        """
        body: dict[str, Any] = {}
        if allowed_namespace_prefixes is not None:
            body["allowed_namespace_prefixes"] = allowed_namespace_prefixes

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/space_settings", space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def health_check(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Check Fleet Server health.

        Check the health status of a Fleet Server instance by its host ID.
        Returns the server status and name if available.

        Args:
            id: The Fleet Server host ID to check (the ID of a Fleet Server
                host configured in Fleet settings).
            space_id: Optional space ID to run the health check in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the health check result:
                - status: Fleet Server status (e.g. ``"ONLINE"`` or
                  ``"OFFLINE"``)
                - name: The Fleet Server name, if available
                - host_id: The checked host ID, if the host is unreachable

        Raises:
            BadRequestError: If the host ID exists but has no associated
                host URLs configured.
            NotFoundError: If no Fleet Server host exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges
                (requires ``fleet-settings-all``).
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> health = await client.fleet.health_check(
            ...     id="fleet-server-host-id-1"
            ... )
            >>> print(health.body["status"])
            ONLINE
        """
        body: dict[str, Any] = {"id": id}

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/health_check", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def check_permissions(
        self,
        *,
        fleet_server_setup: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Check permissions.

        Check whether the current user has the required permissions to use
        Fleet. Optionally verifies Fleet Server setup privileges.

        Args:
            fleet_server_setup: When True, check Fleet Server setup
                privileges in addition to standard Fleet privileges.
            space_id: Optional space ID to check the permissions in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the permission check result:
                - success: True if the user has all required permissions
                - error: Present when success is False; one of
                  ``"MISSING_SECURITY"``, ``"MISSING_PRIVILEGES"`` or
                  ``"MISSING_FLEET_SERVER_SETUP_PRIVILEGES"``

        Raises:
            BadRequestError: If the request is invalid.
            AuthenticationException: If authentication fails.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> perms = await client.fleet.check_permissions()
            >>> print(perms.body["success"])
            True
        """
        params: dict[str, Any] = {}
        if fleet_server_setup is not None:
            params["fleetServerSetup"] = fleet_server_setup

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/check-permissions", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )
