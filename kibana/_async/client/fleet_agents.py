"""Async Kibana Fleet Elastic Agents API client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


class AsyncFleetAgentsClient(AsyncNamespaceClient):
    """Async client for the Kibana Fleet Elastic Agents API.

    Manages Elastic Agents enrolled in Fleet: listing and inspecting agents,
    per-agent operations (update, reassign, unenroll, upgrade, request
    diagnostics, migrate, rollback), bulk variants of those operations, agent
    action bookkeeping (status, cancel), diagnostics file uploads, agent
    status summaries, and Fleet agents setup.

    Fleet agent APIs are space-scoped: agents are visible in the Kibana space
    of the agent policy they are assigned to. Every method accepts an
    optional ``space_id`` to target a specific space (``None`` targets the
    default space or the space the client is scoped to).

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # List enrolled agents and get a status summary
        >>> agents = await client.fleet_agents.get_all(per_page=50)
        >>> summary = await client.fleet_agents.get_status()
        >>> print(summary.body["results"]["online"])
        >>>
        >>> # Upgrade every agent on a policy
        >>> await client.fleet_agents.bulk_upgrade(
        ...     agents='fleet-agents.policy_id : "my-policy"',
        ...     version="9.4.3",
        ... )
    """

    def __init__(
        self,
        client: AsyncKibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the AsyncFleetAgentsClient.

        Args:
            client: The parent AsyncKibana client instance to delegate requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> fleet_agents_client = AsyncFleetAgentsClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    # ----------------------------------------------------------------- #
    # Agent status                                                       #
    # ----------------------------------------------------------------- #

    async def get_status(
        self,
        *,
        policy_id: str | None = None,
        policy_ids: list[str] | None = None,
        kuery: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an agent status summary.

        Gets a summary of agent statuses (online, offline, error, updating,
        ...), optionally filtered by agent policy.

        Args:
            policy_id: Filter by a single agent policy ID.
            policy_ids: Filter by one or more agent policy IDs.
            kuery: A KQL query string to filter results.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - results: Per-status agent counts (``online``, ``error``,
                  ``offline``, ``updating``, ``inactive``, ``unenrolled``,
                  ``orphaned``, ``uninstalled``, ``all``, ``active``,
                  ``other``, ``events``).

        Raises:
            BadRequestError: If the request parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> summary = await client.fleet_agents.get_status()
            >>> print(summary.body["results"]["online"])
            5
        """
        params: dict[str, Any] = {}
        if policy_id is not None:
            params["policyId"] = policy_id
        if policy_ids is not None:
            params["policyIds"] = policy_ids
        if kuery is not None:
            params["kuery"] = kuery

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agent_status", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    async def get_incoming_data(
        self,
        *,
        agents_ids: list[str] | str,
        pkg_name: str | None = None,
        pkg_version: str | None = None,
        preview_data: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get incoming agent data.

        Gets the data streams that the given agents are actively sending
        data to. Requires the ``fleet-agents-read`` privilege.

        Args:
            agents_ids: Agent IDs to check data for, as a list or a single
                comma-separated string.
            pkg_name: Filter by integration package name.
            pkg_version: Filter by integration package version.
            preview_data: When True, return a preview of the ingested data.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - items: One entry per agent ID mapping to ``{"data": bool}``.
                - dataPreview: Preview documents when ``preview_data`` is
                  True.

        Raises:
            BadRequestError: If the request parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> data = await client.fleet_agents.get_incoming_data(
            ...     agents_ids=["agent-id-1", "agent-id-2"]
            ... )
            >>> print(data.body["items"])
        """
        params: dict[str, Any] = {"agentsIds": agents_ids}
        if pkg_name is not None:
            params["pkgName"] = pkg_name
        if pkg_version is not None:
            params["pkgVersion"] = pkg_version
        if preview_data is not None:
            params["previewData"] = preview_data

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agent_status/data", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- #
    # Listing and per-agent CRUD                                         #
    # ----------------------------------------------------------------- #

    async def get_all(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
        kuery: str | None = None,
        show_agentless: bool | None = None,
        show_inactive: bool | None = None,
        with_metrics: bool | None = None,
        show_upgradeable: bool | None = None,
        get_status_summary: bool | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        search_after: str | None = None,
        open_pit: bool | None = None,
        pit_id: str | None = None,
        pit_keep_alive: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get agents.

        Lists agents, with optional filtering and pagination. Requires the
        ``fleet-agents-read`` privilege.

        Args:
            page: Page number.
            per_page: Number of results per page (default: 20).
            kuery: A KQL query string to filter results (for example,
                ``'fleet-agents.tags : "production"'``).
            show_agentless: When True, include agentless agents in the
                results (default: True).
            show_inactive: When True, include inactive agents in the results
                (default: False).
            with_metrics: When True, include CPU and memory metrics in the
                response (default: False).
            show_upgradeable: When True, only return agents that are
                upgradeable (default: False).
            get_status_summary: When True, return a summary of agent
                statuses in the response (default: False).
            sort_field: Field to sort results by.
            sort_order: Sort order, ``"asc"`` or ``"desc"``.
            search_after: JSON-encoded array of sort values for
                ``search_after`` pagination.
            open_pit: When True, opens a new point-in-time for pagination.
            pit_id: Point-in-time ID for pagination.
            pit_keep_alive: Duration to keep the point-in-time alive, for
                example ``"1m"``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - items: The list of agents.
                - total / page / perPage: Pagination info.
                - statusSummary: Per-status counts when
                  ``get_status_summary`` is True.
                - pit / nextSearchAfter: Pagination cursors when requested.

        Raises:
            BadRequestError: If the request parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> agents = await client.fleet_agents.get_all(
            ...     kuery='fleet-agents.status : "online"', per_page=50
            ... )
            >>> for agent in agents.body["items"]:
            ...     print(agent["id"], agent["status"])
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page
        if kuery is not None:
            params["kuery"] = kuery
        if show_agentless is not None:
            params["showAgentless"] = show_agentless
        if show_inactive is not None:
            params["showInactive"] = show_inactive
        if with_metrics is not None:
            params["withMetrics"] = with_metrics
        if show_upgradeable is not None:
            params["showUpgradeable"] = show_upgradeable
        if get_status_summary is not None:
            params["getStatusSummary"] = get_status_summary
        if sort_field is not None:
            params["sortField"] = sort_field
        if sort_order is not None:
            params["sortOrder"] = sort_order
        if search_after is not None:
            params["searchAfter"] = search_after
        if open_pit is not None:
            params["openPit"] = open_pit
        if pit_id is not None:
            params["pitId"] = pit_id
        if pit_keep_alive is not None:
            params["pitKeepAlive"] = pit_keep_alive

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agents", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    async def get_by_actions(
        self,
        *,
        action_ids: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get agents by action ids.

        Retrieves the IDs of agents associated with specific action IDs.
        Requires the ``fleet-agents-read`` privilege.

        Args:
            action_ids: The action IDs to look up agents for.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - items: The list of agent IDs associated with the actions.

        Raises:
            BadRequestError: If the request body is invalid.
            NotFoundError: If no agent action has ever been created (the
                backing ``.fleet-actions`` index does not exist yet).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> agents = await client.fleet_agents.get_by_actions(
            ...     action_ids=["action-id-1", "action-id-2"]
            ... )
            >>> print(agents.body["items"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agents", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"actionIds": action_ids},
        )

    async def get(
        self,
        *,
        agent_id: str,
        with_metrics: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an agent.

        Gets an agent by ID. Requires the ``fleet-agents-read`` privilege.

        Args:
            agent_id: The agent ID.
            with_metrics: When True, include CPU and memory metrics in the
                response (default: False).
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - item: The agent (``id``, ``status``, ``policy_id``,
                  ``local_metadata``, ``tags``, ...).

        Raises:
            NotFoundError: If no agent exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> agent = await client.fleet_agents.get(agent_id="agent-id-1")
            >>> print(agent.body["item"]["status"])
            online
        """
        params: dict[str, Any] = {}
        if with_metrics is not None:
            params["withMetrics"] = with_metrics

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/fleet/agents/{_quote(agent_id)}", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    async def update(
        self,
        *,
        agent_id: str,
        tags: list[str] | None = None,
        user_provided_metadata: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update an agent.

        Updates an agent by ID. Only the user-editable fields (``tags`` and
        ``user_provided_metadata``) can be changed. Requires the
        ``fleet-agents-all`` privilege.

        Args:
            agent_id: The agent ID.
            tags: The list of tags to assign to the agent (replaces the
                existing tags).
            user_provided_metadata: User-provided metadata to attach to the
                agent.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - item: The updated agent.

        Raises:
            NotFoundError: If no agent exists with the given ID.
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> updated = await client.fleet_agents.update(
            ...     agent_id="agent-id-1", tags=["production", "linux"]
            ... )
            >>> print(updated.body["item"]["tags"])
            ['production', 'linux']
        """
        body: dict[str, Any] = {}
        if tags is not None:
            body["tags"] = tags
        if user_provided_metadata is not None:
            body["user_provided_metadata"] = user_provided_metadata

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/fleet/agents/{_quote(agent_id)}", space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete(
        self,
        *,
        agent_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete an agent.

        Deletes an agent by ID. This removes the agent document from Fleet;
        it does not uninstall the Elastic Agent from the host. Requires the
        ``fleet-agents-all`` privilege.

        Args:
            agent_id: The agent ID.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - action: ``"deleted"`` on success.

        Raises:
            NotFoundError: If no agent exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.fleet_agents.delete(agent_id="agent-id-1")
            >>> print(result.body["action"])
            deleted
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/fleet/agents/{_quote(agent_id)}", space_id)
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- #
    # Per-agent operations                                               #
    # ----------------------------------------------------------------- #

    async def create_action(
        self,
        *,
        agent_id: str,
        action: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create an agent action.

        Creates an action for the given agent, for example a ``SETTINGS``
        action to change its log level. Requires the ``fleet-agents-all``
        privilege.

        Args:
            agent_id: The agent ID.
            action: The action object. Either
                ``{"type": "UNENROLL" | "UPGRADE" | "POLICY_REASSIGN",
                "data": ..., "ack_data": ...}`` or
                ``{"type": "SETTINGS", "data": {"log_level": "debug" |
                "info" | "warning" | "error" | None}}``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - item: The created action (``id``, ``type``,
                  ``created_at``, ...).

        Raises:
            NotFoundError: If no agent exists with the given ID.
            BadRequestError: If the action payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.fleet_agents.create_action(
            ...     agent_id="agent-id-1",
            ...     action={"type": "SETTINGS", "data": {"log_level": "debug"}},
            ... )
            >>> print(result.body["item"]["type"])
            SETTINGS
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agents/{_quote(agent_id)}/actions", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"action": action},
        )

    async def get_effective_config(
        self,
        *,
        agent_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an agent's effective config.

        Technical preview in 9.4. Gets the effective (fully resolved)
        configuration that the agent is running with. Requires the
        ``fleet-agents-read`` privilege.

        Args:
            agent_id: The agent ID.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the agent's effective
            configuration document.

        Raises:
            NotFoundError: If no agent exists with the given ID (or no agent
                has ever enrolled, in which case the backing
                ``.fleet-agents`` index does not exist yet).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> config = await client.fleet_agents.get_effective_config(
            ...     agent_id="agent-id-1"
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agents/{_quote(agent_id)}/effective_config", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def migrate(
        self,
        *,
        agent_id: str,
        enrollment_token: str,
        uri: str,
        settings: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Migrate a single agent.

        Migrates the agent to another Fleet Server / cluster identified by
        its URI, enrolling it with the given enrollment token. Requires the
        ``fleet-agents-all`` privilege.

        Args:
            agent_id: The agent ID.
            enrollment_token: The enrollment token to use on the target
                cluster.
            uri: The URI of the target Fleet Server (for example,
                ``"https://fleet.example.com:8220"``).
            settings: Optional migration settings (``ca_sha256``,
                ``certificate_authorities``, ``elastic_agent_cert``,
                ``elastic_agent_cert_key``,
                ``elastic_agent_cert_key_passphrase``, ``headers``,
                ``insecure``, ``proxy_disabled``, ``proxy_headers``,
                ``proxy_url``, ``replace_token``, ``staging``, ``tags``).
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse describing the created migrate action.

        Raises:
            NotFoundError: If no agent exists with the given ID.
            BadRequestError: If the request body is invalid (for example,
                the agent is tamper-protected or agentless).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.fleet_agents.migrate(
            ...     agent_id="agent-id-1",
            ...     enrollment_token="token123",
            ...     uri="https://fleet.example.com:8220",
            ... )
        """
        body: dict[str, Any] = {
            "enrollment_token": enrollment_token,
            "uri": uri,
        }
        if settings is not None:
            body["settings"] = settings

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agents/{_quote(agent_id)}/migrate", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def change_privilege_level(
        self,
        *,
        agent_id: str,
        user_info: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Change agent privilege level.

        Changes the privilege level of the agent, for example switching it
        to run in unprivileged mode. Requires the ``fleet-agents-all``
        privilege.

        Args:
            agent_id: The agent ID.
            user_info: Optional user information for running the agent
                unprivileged (``username``, ``groupname``, ``password``).
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse describing the created privilege-level-change
            action.

        Raises:
            NotFoundError: If no agent exists with the given ID.
            BadRequestError: If the agent cannot change privilege level (for
                example, its policy contains integrations that require root
                access).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.fleet_agents.change_privilege_level(
            ...     agent_id="agent-id-1",
            ...     user_info={"username": "elastic-agent-user"},
            ... )
        """
        body: dict[str, Any] = {}
        if user_info is not None:
            body["user_info"] = user_info

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agents/{_quote(agent_id)}/privilege_level_change", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def reassign(
        self,
        *,
        agent_id: str,
        policy_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Reassign an agent.

        Reassigns the agent to a different agent policy. Requires the
        ``fleet-agents-all`` privilege.

        Args:
            agent_id: The agent ID.
            policy_id: The ID of the agent policy to assign the agent to.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body on success.

        Raises:
            NotFoundError: If the agent or the agent policy does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.fleet_agents.reassign(
            ...     agent_id="agent-id-1", policy_id="agent-policy-id-2"
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agents/{_quote(agent_id)}/reassign", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"policy_id": policy_id},
        )

    async def request_diagnostics(
        self,
        *,
        agent_id: str,
        additional_metrics: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Request agent diagnostics.

        Requests a diagnostics bundle from the agent. The resulting file
        upload can be listed with :meth:`get_uploads` and downloaded with
        :meth:`get_file`. Requires the ``fleet-agents-read`` privilege.

        Args:
            agent_id: The agent ID.
            additional_metrics: Additional metrics to include in the
                diagnostics bundle (allowed value: ``"CPU"``).
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - actionId: The ID of the created request-diagnostics
                  action.

        Raises:
            NotFoundError: If no agent exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.fleet_agents.request_diagnostics(
            ...     agent_id="agent-id-1", additional_metrics=["CPU"]
            ... )
            >>> print(result.body["actionId"])
        """
        body: dict[str, Any] = {}
        if additional_metrics is not None:
            body["additional_metrics"] = additional_metrics

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agents/{_quote(agent_id)}/request_diagnostics", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def rollback(
        self,
        *,
        agent_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Rollback an agent.

        Technical preview in 9.4. Rolls the agent back to its previous
        version after an upgrade. Requires the ``fleet-agents-all``
        privilege.

        Args:
            agent_id: The agent ID.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse describing the created rollback action.

        Raises:
            NotFoundError: If no agent exists with the given ID.
            BadRequestError: If the agent has no available rollback.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.fleet_agents.rollback(agent_id="agent-id-1")
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agents/{_quote(agent_id)}/rollback", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def unenroll(
        self,
        *,
        agent_id: str,
        force: bool | None = None,
        revoke: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Unenroll an agent.

        Unenrolls the agent from Fleet. The agent stops checking in and its
        API keys are invalidated. Requires the ``fleet-agents-all``
        privilege.

        Args:
            agent_id: The agent ID.
            force: When True, unenroll the agent immediately even if it is
                a hosted (managed) agent.
            revoke: When True, revoke the agent's API keys immediately
                instead of waiting for the agent to acknowledge the action.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body on success.

        Raises:
            NotFoundError: If no agent exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.fleet_agents.unenroll(agent_id="agent-id-1", revoke=True)
        """
        body: dict[str, Any] = {}
        if force is not None:
            body["force"] = force
        if revoke is not None:
            body["revoke"] = revoke

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agents/{_quote(agent_id)}/unenroll", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def upgrade(
        self,
        *,
        agent_id: str,
        version: str,
        source_uri: str | None = None,
        force: bool | None = None,
        skip_rate_limit_check: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Upgrade an agent.

        Upgrades the agent to the given version. Requires the
        ``fleet-agents-all`` privilege.

        Args:
            agent_id: The agent ID.
            version: The version to upgrade the agent to.
            source_uri: Optional URI to download the agent artifact from
                (instead of the default artifact registry).
            force: When True, force the upgrade even if the agent is not
                upgradeable (for example, a hosted agent).
            skip_rate_limit_check: When True, skip the upgrade rate limit
                check.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body on success.

        Raises:
            NotFoundError: If no agent exists with the given ID.
            BadRequestError: If the version is not valid for the agent.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.fleet_agents.upgrade(
            ...     agent_id="agent-id-1", version="9.4.3"
            ... )
        """
        body: dict[str, Any] = {"version": version}
        if source_uri is not None:
            body["source_uri"] = source_uri
        if force is not None:
            body["force"] = force
        if skip_rate_limit_check is not None:
            body["skipRateLimitCheck"] = skip_rate_limit_check

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agents/{_quote(agent_id)}/upgrade", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_uploads(
        self,
        *,
        agent_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get agent uploads.

        Lists the files (for example, diagnostics bundles) uploaded by the
        agent. Requires the ``fleet-agents-read`` privilege.

        Args:
            agent_id: The agent ID.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - items: The list of uploaded files (``id``, ``name``,
                  ``filePath``, ``createTime``, ``status``, ``actionId``).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> uploads = await client.fleet_agents.get_uploads(agent_id="agent-id-1")
            >>> for item in uploads.body["items"]:
            ...     print(item["name"], item["status"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agents/{_quote(agent_id)}/uploads", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- #
    # Agent actions                                                      #
    # ----------------------------------------------------------------- #

    async def get_action_status(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
        date: str | None = None,
        latest: int | None = None,
        error_size: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an agent action status.

        Lists the statuses of recent agent actions (upgrades, unenrollments,
        reassignments, ...). Requires the ``fleet-agents-read`` privilege.

        Args:
            page: Page number (default: 0).
            per_page: Number of results per page (default: 20).
            date: Filter actions by date (ISO 8601).
            latest: Return actions created in the latest N milliseconds.
            error_size: Number of ``latestErrors`` entries to return per
                action (default: 5).
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - items: Action statuses (``actionId``, ``type``,
                  ``status``, ``nbAgentsActioned``, ``nbAgentsAck``,
                  ``creationTime``, ``latestErrors``, ...).

        Raises:
            BadRequestError: If the request parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> statuses = await client.fleet_agents.get_action_status(per_page=10)
            >>> for action in statuses.body["items"]:
            ...     print(action["actionId"], action["type"], action["status"])
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page
        if date is not None:
            params["date"] = date
        if latest is not None:
            params["latest"] = latest
        if error_size is not None:
            params["errorSize"] = error_size

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agents/action_status", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    async def cancel_action(
        self,
        *,
        action_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Cancel an agent action.

        Cancels an in-progress agent action by its ID. Requires the
        ``fleet-agents-all`` privilege.

        Args:
            action_id: The ID of the action to cancel.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - item: The created ``CANCEL`` action (``id``, ``type``,
                  ``created_at``, ...).

        Raises:
            NotFoundError: If no action exists with the given ID (or no
                agent action has ever been created, in which case the
                backing ``.fleet-actions`` index does not exist yet).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.fleet_agents.cancel_action(
            ...     action_id="action-id-1"
            ... )
            >>> print(result.body["item"]["type"])
            CANCEL
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agents/actions/{_quote(action_id)}/cancel", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def get_available_versions(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get available agent versions.

        Lists the Elastic Agent versions available for upgrades.

        Args:
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - items: The list of available version strings.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> versions = await client.fleet_agents.get_available_versions()
            >>> print(versions.body["items"][0])
            9.4.3
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agents/available_versions", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- #
    # Bulk operations                                                    #
    # ----------------------------------------------------------------- #

    async def bulk_migrate(
        self,
        *,
        agents: list[str] | str,
        enrollment_token: str,
        uri: str,
        settings: dict[str, Any] | None = None,
        batch_size: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Migrate multiple agents.

        Bulk version of :meth:`migrate`: migrates the selected agents to
        another Fleet Server / cluster. Requires the ``fleet-agents-all``
        privilege.

        Args:
            agents: Agents to migrate — either a list of agent IDs or a KQL
                query string selecting agents.
            enrollment_token: The enrollment token to use on the target
                cluster.
            uri: The URI of the target Fleet Server.
            settings: Optional migration settings (same keys as
                :meth:`migrate`, minus ``replace_token``).
            batch_size: Batch size for processing the selected agents.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - actionId: The ID of the created bulk migrate action.

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.fleet_agents.bulk_migrate(
            ...     agents=["agent-id-1", "agent-id-2"],
            ...     enrollment_token="token123",
            ...     uri="https://fleet.example.com:8220",
            ... )
            >>> print(result.body["actionId"])
        """
        body: dict[str, Any] = {
            "agents": agents,
            "enrollment_token": enrollment_token,
            "uri": uri,
        }
        if settings is not None:
            body["settings"] = settings
        if batch_size is not None:
            body["batchSize"] = batch_size

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agents/bulk_migrate", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def bulk_change_privilege_level(
        self,
        *,
        agents: list[str] | str,
        user_info: dict[str, Any] | None = None,
        batch_size: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk change agent privilege level.

        Bulk version of :meth:`change_privilege_level`: changes the
        privilege level of the selected agents. Requires the
        ``fleet-agents-all`` privilege.

        Args:
            agents: Agents to update — either a list of agent IDs or a KQL
                query string selecting agents.
            user_info: Optional user information for running the agents
                unprivileged (``username``, ``groupname``, ``password``).
            batch_size: Batch size for processing the selected agents.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - actionId: The ID of the created bulk action.

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.fleet_agents.bulk_change_privilege_level(
            ...     agents=["agent-id-1", "agent-id-2"],
            ...     user_info={"username": "elastic-agent-user"},
            ... )
            >>> print(result.body["actionId"])
        """
        body: dict[str, Any] = {"agents": agents}
        if user_info is not None:
            body["user_info"] = user_info
        if batch_size is not None:
            body["batchSize"] = batch_size

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/fleet/agents/bulk_privilege_level_change", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def bulk_reassign(
        self,
        *,
        agents: list[str] | str,
        policy_id: str,
        batch_size: int | None = None,
        include_inactive: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk reassign agents.

        Bulk version of :meth:`reassign`: reassigns the selected agents to a
        different agent policy. Requires the ``fleet-agents-all`` privilege.

        Args:
            agents: Agents to reassign — either a list of agent IDs or a KQL
                query string selecting agents.
            policy_id: The ID of the agent policy to assign the agents to.
            batch_size: Batch size for processing the selected agents.
            include_inactive: When True, include inactive agents in the
                selection.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - actionId: The ID of the created bulk reassign action.

        Raises:
            NotFoundError: If the agent policy does not exist.
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.fleet_agents.bulk_reassign(
            ...     agents='fleet-agents.status : "offline"',
            ...     policy_id="agent-policy-id-2",
            ... )
            >>> print(result.body["actionId"])
        """
        body: dict[str, Any] = {"agents": agents, "policy_id": policy_id}
        if batch_size is not None:
            body["batchSize"] = batch_size
        if include_inactive is not None:
            body["includeInactive"] = include_inactive

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agents/bulk_reassign", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def bulk_request_diagnostics(
        self,
        *,
        agents: list[str] | str,
        additional_metrics: list[str] | None = None,
        batch_size: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk request diagnostics from agents.

        Bulk version of :meth:`request_diagnostics`: requests diagnostics
        bundles from the selected agents. Requires the ``fleet-agents-read``
        privilege.

        Args:
            agents: Agents to request diagnostics from — either a list of
                agent IDs or a KQL query string selecting agents.
            additional_metrics: Additional metrics to include in the
                diagnostics bundles (allowed value: ``"CPU"``).
            batch_size: Batch size for processing the selected agents.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - actionId: The ID of the created bulk action.

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.fleet_agents.bulk_request_diagnostics(
            ...     agents=["agent-id-1", "agent-id-2"],
            ...     additional_metrics=["CPU"],
            ... )
            >>> print(result.body["actionId"])
        """
        body: dict[str, Any] = {"agents": agents}
        if additional_metrics is not None:
            body["additional_metrics"] = additional_metrics
        if batch_size is not None:
            body["batchSize"] = batch_size

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/fleet/agents/bulk_request_diagnostics", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def bulk_rollback(
        self,
        *,
        agents: list[str] | str,
        batch_size: int | None = None,
        include_inactive: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk rollback agents.

        Technical preview in 9.4. Bulk version of :meth:`rollback`: rolls
        the selected agents back to their previous versions. Requires the
        ``fleet-agents-all`` privilege.

        Args:
            agents: Agents to roll back — either a list of agent IDs or a
                KQL query string selecting agents.
            batch_size: Batch size for processing the selected agents.
            include_inactive: When True, include inactive agents in the
                selection.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - actionIds: The IDs of the created rollback actions (note:
                  unlike the other bulk operations, this endpoint returns a
                  list of action IDs).

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.fleet_agents.bulk_rollback(
            ...     agents=["agent-id-1", "agent-id-2"]
            ... )
            >>> print(result.body["actionIds"])
        """
        body: dict[str, Any] = {"agents": agents}
        if batch_size is not None:
            body["batchSize"] = batch_size
        if include_inactive is not None:
            body["includeInactive"] = include_inactive

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agents/bulk_rollback", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def bulk_unenroll(
        self,
        *,
        agents: list[str] | str,
        force: bool | None = None,
        revoke: bool | None = None,
        batch_size: int | None = None,
        include_inactive: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk unenroll agents.

        Bulk version of :meth:`unenroll`: unenrolls the selected agents from
        Fleet. Requires the ``fleet-agents-all`` privilege.

        Args:
            agents: Agents to unenroll — either a list of agent IDs or a KQL
                query string selecting agents.
            force: When True, unenroll hosted (managed) agents too.
            revoke: When True, revoke the agents' API keys immediately.
            batch_size: Batch size for processing the selected agents.
            include_inactive: When True, include inactive agents in the
                selection.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - actionId: The ID of the created bulk unenroll action.

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.fleet_agents.bulk_unenroll(
            ...     agents='fleet-agents.status : "inactive"',
            ...     revoke=True,
            ...     include_inactive=True,
            ... )
            >>> print(result.body["actionId"])
        """
        body: dict[str, Any] = {"agents": agents}
        if force is not None:
            body["force"] = force
        if revoke is not None:
            body["revoke"] = revoke
        if batch_size is not None:
            body["batchSize"] = batch_size
        if include_inactive is not None:
            body["includeInactive"] = include_inactive

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agents/bulk_unenroll", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def bulk_update_tags(
        self,
        *,
        agents: list[str] | str,
        tags_to_add: list[str] | None = None,
        tags_to_remove: list[str] | None = None,
        batch_size: int | None = None,
        include_inactive: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk update agent tags.

        Adds and/or removes tags on the selected agents. Requires the
        ``fleet-agents-all`` privilege.

        Args:
            agents: Agents to update — either a list of agent IDs or a KQL
                query string selecting agents.
            tags_to_add: Tags to add to the selected agents.
            tags_to_remove: Tags to remove from the selected agents.
            batch_size: Batch size for processing the selected agents.
            include_inactive: When True, include inactive agents in the
                selection.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - actionId: The ID of the created bulk action.

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.fleet_agents.bulk_update_tags(
            ...     agents=["agent-id-1", "agent-id-2"],
            ...     tags_to_add=["production"],
            ...     tags_to_remove=["staging"],
            ... )
            >>> print(result.body["actionId"])
        """
        body: dict[str, Any] = {"agents": agents}
        if tags_to_add is not None:
            body["tagsToAdd"] = tags_to_add
        if tags_to_remove is not None:
            body["tagsToRemove"] = tags_to_remove
        if batch_size is not None:
            body["batchSize"] = batch_size
        if include_inactive is not None:
            body["includeInactive"] = include_inactive

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/fleet/agents/bulk_update_agent_tags", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def bulk_upgrade(
        self,
        *,
        agents: list[str] | str,
        version: str,
        source_uri: str | None = None,
        rollout_duration_seconds: int | None = None,
        start_time: str | None = None,
        force: bool | None = None,
        skip_rate_limit_check: bool | None = None,
        batch_size: int | None = None,
        include_inactive: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk upgrade agents.

        Bulk version of :meth:`upgrade`: upgrades the selected agents to the
        given version, optionally rolled out over a time window. Requires
        the ``fleet-agents-all`` privilege.

        Args:
            agents: Agents to upgrade — either a list of agent IDs or a KQL
                query string selecting agents.
            version: The version to upgrade the agents to.
            source_uri: Optional URI to download the agent artifact from.
            rollout_duration_seconds: Duration in seconds over which to
                spread the upgrade rollout.
            start_time: ISO 8601 time at which to start the rollout.
            force: When True, force the upgrade even for agents that are not
                upgradeable.
            skip_rate_limit_check: When True, skip the upgrade rate limit
                check.
            batch_size: Batch size for processing the selected agents.
            include_inactive: When True, include inactive agents in the
                selection.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - actionId: The ID of the created bulk upgrade action.

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.fleet_agents.bulk_upgrade(
            ...     agents='fleet-agents.policy_id : "my-policy"',
            ...     version="9.4.3",
            ...     rollout_duration_seconds=3600,
            ... )
            >>> print(result.body["actionId"])
        """
        body: dict[str, Any] = {"agents": agents, "version": version}
        if source_uri is not None:
            body["source_uri"] = source_uri
        if rollout_duration_seconds is not None:
            body["rollout_duration_seconds"] = rollout_duration_seconds
        if start_time is not None:
            body["start_time"] = start_time
        if force is not None:
            body["force"] = force
        if skip_rate_limit_check is not None:
            body["skipRateLimitCheck"] = skip_rate_limit_check
        if batch_size is not None:
            body["batchSize"] = batch_size
        if include_inactive is not None:
            body["includeInactive"] = include_inactive

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agents/bulk_upgrade", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    # ----------------------------------------------------------------- #
    # Uploaded files                                                     #
    # ----------------------------------------------------------------- #

    async def get_file(
        self,
        *,
        file_id: str,
        file_name: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an uploaded file.

        Downloads a file uploaded by an agent (for example, a diagnostics
        bundle requested with :meth:`request_diagnostics`). Requires the
        ``fleet-agents-read`` privilege.

        Args:
            file_id: The ID of the uploaded file (from :meth:`get_uploads`).
            file_name: The name of the uploaded file.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body contains the raw file content.

        Raises:
            ApiError: If the file does not exist (the live server responds
                with a 500 ``index_not_found_exception`` when no agent file
                has ever been uploaded).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> content = await client.fleet_agents.get_file(
            ...     file_id="file-id-1",
            ...     file_name="elastic-agent-diagnostics.zip",
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agents/files/{_quote(file_id)}/{_quote(file_name)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
        )

    async def delete_file(
        self,
        *,
        file_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete an uploaded file.

        Deletes a file uploaded by an agent. Requires the
        ``fleet-agents-all`` privilege.

        Args:
            file_id: The ID of the uploaded file to delete.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - id: The ID of the deleted file.
                - deleted: Whether the file was deleted.

        Raises:
            NotFoundError: If the file does not exist (or no agent file has
                ever been uploaded, in which case the backing file-data
                index does not exist yet).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.fleet_agents.delete_file(file_id="file-id-1")
            >>> print(result.body["deleted"])
            True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agents/files/{_quote(file_id)}", space_id
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- #
    # Setup and tags                                                     #
    # ----------------------------------------------------------------- #

    async def get_setup_status(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get agent setup info.

        Gets a summary of the Fleet agent setup status. ``isReady``
        indicates whether the setup is ready; if not,
        ``missing_requirements`` lists what is missing (for example, a
        Fleet Server).

        Args:
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - isReady: Whether agent setup is ready.
                - missing_requirements: Missing requirements (for example,
                  ``"fleet_server"``, ``"api_keys"``).
                - missing_optional_features: Missing optional features.
                - is_secrets_storage_enabled / is_space_awareness_enabled /
                  ...: Feature flags.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> setup = await client.fleet_agents.get_setup_status()
            >>> print(setup.body["isReady"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agents/setup", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def initiate_setup(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Initiate Fleet setup.

        Initiates the Fleet agents setup process (creates the required
        Fleet index templates, packages and policies if missing). This is
        idempotent: calling it when Fleet is already set up succeeds.

        Args:
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - isInitialized: Whether Fleet is initialized.
                - nonFatalErrors: Any non-fatal errors hit during setup.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.fleet_agents.initiate_setup()
            >>> print(result.body["isInitialized"])
            True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agents/setup", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def get_tags(
        self,
        *,
        kuery: str | None = None,
        show_inactive: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get agent tags.

        Lists the distinct tags across agents. Requires the
        ``fleet-agents-read`` privilege.

        Args:
            kuery: A KQL query string to filter the agents whose tags are
                aggregated.
            show_inactive: When True, include tags of inactive agents
                (default: False).
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - items: The list of distinct tag strings.

        Raises:
            BadRequestError: If the request parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> tags = await client.fleet_agents.get_tags()
            >>> print(tags.body["items"])
            ['production', 'linux']
        """
        params: dict[str, Any] = {}
        if kuery is not None:
            params["kuery"] = kuery
        if show_inactive is not None:
            params["showInactive"] = show_inactive

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agents/tags", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )
