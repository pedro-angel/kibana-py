"""Kibana Fleet agent and package policies API client."""

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._sync.client import Kibana


class FleetPoliciesClient(NamespaceClient):
    """Client for the Kibana Fleet agent and package policies API.

    Agent policies define how Elastic Agents behave: which outputs they ship
    data to, their monitoring settings and which integrations they run.
    Package policies attach an integration package (with its inputs and
    variables) to one or more agent policies. Agentless policies deploy an
    integration without a self-managed Elastic Agent (Elastic Cloud /
    serverless only).

    Fleet policies are space-aware resources: every method accepts an
    optional ``space_id`` to target a specific space (``None`` targets the
    default space or the space the client is scoped to).

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create an agent policy and attach a package policy to it
        >>> policy = client.fleet_policies.create_agent_policy(
        ...     name="my-agent-policy",
        ...     namespace="default",
        ...     sys_monitoring=False,
        ... )
        >>> policy_id = policy.body["item"]["id"]
        >>>
        >>> pkg = client.fleet_policies.create_package_policy(
        ...     name="my-package-policy",
        ...     package={"name": "log", "version": "2.4.4"},
        ...     policy_ids=[policy_id],
        ...     inputs={"logs-logfile": {"enabled": True}},
        ... )
        >>>
        >>> # Clean up
        >>> client.fleet_policies.delete_package_policy(
        ...     package_policy_id=pkg.body["item"]["id"]
        ... )
        >>> client.fleet_policies.delete_agent_policy(agent_policy_id=policy_id)
    """

    def __init__(
        self,
        client: Kibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the FleetPoliciesClient.

        Args:
            client: The parent Kibana client instance to delegate requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> fleet_policies_client = FleetPoliciesClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    # ----------------------------------------------------------------- #
    # Agent policies                                                     #
    # ----------------------------------------------------------------- #

    def get_agent_policies(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        show_upgradeable: bool | None = None,
        kuery: str | None = None,
        no_agent_count: bool | None = None,
        with_agent_count: bool | None = None,
        full: bool | None = None,
        format: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get agent policies.

        ``GET /api/fleet/agent_policies``

        Lists agent policies, optionally filtered with a KQL query and
        paginated.

        Args:
            page: Page number to return (1-based).
            per_page: Number of policies per page.
            sort_field: Field to sort the results by.
            sort_order: Sort direction, either ``"asc"`` or ``"desc"``.
            show_upgradeable: Only return policies with agents that can be
                upgraded.
            kuery: KQL filter, e.g.
                ``'ingest-agent-policies.name:"my-policy"'``.
            no_agent_count: Do not compute the agent count per policy
                (deprecated in favor of ``with_agent_count``).
            with_agent_count: Include the number of enrolled agents for each
                policy.
            full: Return the full policy representation (including package
                policies).
            format: Representation of package policies within each agent
                policy: ``"simplified"`` or ``"legacy"``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``items`` (list of agent policies),
            ``total``, ``page`` and ``perPage``.

        Raises:
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> policies = client.fleet_policies.get_agent_policies(
            ...     kuery='ingest-agent-policies.name:"my-policy"', per_page=5
            ... )
            >>> print(policies.body["total"])
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page
        if sort_field is not None:
            params["sortField"] = sort_field
        if sort_order is not None:
            params["sortOrder"] = sort_order
        if show_upgradeable is not None:
            params["showUpgradeable"] = show_upgradeable
        if kuery is not None:
            params["kuery"] = kuery
        if no_agent_count is not None:
            params["noAgentCount"] = no_agent_count
        if with_agent_count is not None:
            params["withAgentCount"] = with_agent_count
        if full is not None:
            params["full"] = full
        if format is not None:
            params["format"] = format

        path = self._build_space_path(
            "/api/fleet/agent_policies", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    def create_agent_policy(
        self,
        *,
        name: str,
        namespace: str,
        advanced_settings: dict[str, Any] | None = None,
        agent_features: list[dict[str, Any]] | None = None,
        agentless: dict[str, Any] | None = None,
        bump_revision: bool | None = None,
        data_output_id: str | None = None,
        description: str | None = None,
        download_source_id: str | None = None,
        fleet_server_host_id: str | None = None,
        force: bool | None = None,
        global_data_tags: list[dict[str, Any]] | None = None,
        has_agent_version_conditions: bool | None = None,
        has_fleet_server: bool | None = None,
        id: str | None = None,
        inactivity_timeout: int | None = None,
        is_default: bool | None = None,
        is_default_fleet_server: bool | None = None,
        is_managed: bool | None = None,
        is_protected: bool | None = None,
        is_verifier: bool | None = None,
        keep_monitoring_alive: bool | None = None,
        min_agent_version: str | None = None,
        monitoring_diagnostics: dict[str, Any] | None = None,
        monitoring_enabled: list[str] | None = None,
        monitoring_http: dict[str, Any] | None = None,
        monitoring_output_id: str | None = None,
        monitoring_pprof_enabled: bool | None = None,
        overrides: dict[str, Any] | None = None,
        package_agent_version_conditions: list[dict[str, Any]] | None = None,
        required_versions: list[dict[str, Any]] | None = None,
        space_ids: list[str] | None = None,
        supports_agentless: bool | None = None,
        unenroll_timeout: int | None = None,
        sys_monitoring: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create an agent policy.

        ``POST /api/fleet/agent_policies``

        Args:
            name: Name of the agent policy (must be unique).
            namespace: Default data stream namespace for the policy's
                integrations (e.g. ``"default"``).
            advanced_settings: Advanced agent settings (e.g. log level).
            agent_features: Agent feature flags, list of
                ``{"name": ..., "enabled": ...}`` objects.
            agentless: Agentless deployment configuration.
            bump_revision: Bump the policy revision on creation.
            data_output_id: ID of the output used for integration data.
            description: Human-readable description of the policy.
            download_source_id: ID of the agent binary download source.
            fleet_server_host_id: ID of the Fleet Server host to use.
            force: Force creation even if some preconditions fail.
            global_data_tags: Tags added to every document produced by the
                policy, list of ``{"name": ..., "value": ...}`` objects.
            has_agent_version_conditions: Whether the policy has agent
                version conditions.
            has_fleet_server: Whether the policy hosts a Fleet Server.
            id: Explicit ID for the new policy (auto-generated when omitted).
            inactivity_timeout: Seconds of inactivity before an agent is
                marked inactive (minimum 0, default 1209600).
            is_default: Mark as the default agent policy.
            is_default_fleet_server: Mark as the default Fleet Server policy.
            is_managed: Mark the policy as hosted/managed (cannot be edited
                in the UI).
            is_protected: Enable agent tamper protection.
            is_verifier: Whether the policy is a verifier policy.
            keep_monitoring_alive: Keep the monitoring server alive even when
                monitoring is disabled.
            min_agent_version: Minimum agent version allowed to enroll.
            monitoring_diagnostics: Monitoring diagnostics rate limit /
                uploader settings.
            monitoring_enabled: What to monitor on the agents; any of
                ``"logs"``, ``"metrics"``, ``"traces"``.
            monitoring_http: Monitoring HTTP endpoint settings.
            monitoring_output_id: ID of the output used for agent monitoring
                data.
            monitoring_pprof_enabled: Enable pprof profiling endpoints on
                the agents.
            overrides: Overrides applied on top of the compiled full agent
                policy.
            package_agent_version_conditions: Per-package agent version
                conditions, list of ``{"packageName": ...,
                "versionCondition": ...}`` objects.
            required_versions: Target agent versions for automatic upgrades,
                list of ``{"version": ..., "percentage": ...}`` objects.
            space_ids: IDs of the spaces the policy is shared with.
            supports_agentless: Whether the policy supports agentless
                integrations (Elastic Cloud / serverless only).
            unenroll_timeout: Seconds after which inactive agents are
                automatically unenrolled.
            sys_monitoring: Query flag; when True, also create a ``system``
                monitoring package policy on the new agent policy.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``item`` containing the created agent
            policy (``id``, ``name``, ``namespace``, ``revision``, ...).

        Raises:
            BadRequestError: If the request body is invalid (e.g. duplicate
                name).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = client.fleet_policies.create_agent_policy(
            ...     name="my-agent-policy",
            ...     namespace="default",
            ...     description="Policy for web servers",
            ...     monitoring_enabled=["logs", "metrics"],
            ...     sys_monitoring=False,
            ... )
            >>> print(created.body["item"]["id"])
        """
        params: dict[str, Any] = {}
        if sys_monitoring is not None:
            params["sys_monitoring"] = sys_monitoring

        body: dict[str, Any] = {"name": name, "namespace": namespace}
        optional_fields: dict[str, Any] = {
            "advanced_settings": advanced_settings,
            "agent_features": agent_features,
            "agentless": agentless,
            "bumpRevision": bump_revision,
            "data_output_id": data_output_id,
            "description": description,
            "download_source_id": download_source_id,
            "fleet_server_host_id": fleet_server_host_id,
            "force": force,
            "global_data_tags": global_data_tags,
            "has_agent_version_conditions": has_agent_version_conditions,
            "has_fleet_server": has_fleet_server,
            "id": id,
            "inactivity_timeout": inactivity_timeout,
            "is_default": is_default,
            "is_default_fleet_server": is_default_fleet_server,
            "is_managed": is_managed,
            "is_protected": is_protected,
            "is_verifier": is_verifier,
            "keep_monitoring_alive": keep_monitoring_alive,
            "min_agent_version": min_agent_version,
            "monitoring_diagnostics": monitoring_diagnostics,
            "monitoring_enabled": monitoring_enabled,
            "monitoring_http": monitoring_http,
            "monitoring_output_id": monitoring_output_id,
            "monitoring_pprof_enabled": monitoring_pprof_enabled,
            "overrides": overrides,
            "package_agent_version_conditions": package_agent_version_conditions,
            "required_versions": required_versions,
            "space_ids": space_ids,
            "supports_agentless": supports_agentless,
            "unenroll_timeout": unenroll_timeout,
        }
        body.update({k: v for k, v in optional_fields.items() if v is not None})

        path = self._build_space_path(
            "/api/fleet/agent_policies", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            params=params or None,
            headers={"accept": "application/json"},
            body=body,
        )

    def bulk_get_agent_policies(
        self,
        *,
        ids: list[str],
        full: bool | None = None,
        ignore_missing: bool | None = None,
        format: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk get agent policies.

        ``POST /api/fleet/agent_policies/_bulk_get``

        Args:
            ids: List of agent policy IDs to fetch.
            full: Return the full policy representation (including package
                policies).
            ignore_missing: When True, missing IDs are silently skipped
                instead of producing a 404.
            format: Representation of package policies within each agent
                policy: ``"simplified"`` or ``"legacy"``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``items`` containing the requested agent
            policies.

        Raises:
            BadRequestError: If the request body is invalid.
            NotFoundError: If an ID is missing and ``ignore_missing`` is not
                set.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> policies = client.fleet_policies.bulk_get_agent_policies(
            ...     ids=["policy-1", "policy-2"], ignore_missing=True
            ... )
            >>> print(len(policies.body["items"]))
        """
        params: dict[str, Any] = {}
        if format is not None:
            params["format"] = format

        body: dict[str, Any] = {"ids": ids}
        if full is not None:
            body["full"] = full
        if ignore_missing is not None:
            body["ignoreMissing"] = ignore_missing

        path = self._build_space_path(
            "/api/fleet/agent_policies/_bulk_get", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            params=params or None,
            headers={"accept": "application/json"},
            body=body,
        )

    def get_agent_policy(
        self,
        *,
        agent_policy_id: str,
        format: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an agent policy.

        ``GET /api/fleet/agent_policies/{agentPolicyId}``

        Args:
            agent_policy_id: ID of the agent policy.
            format: Representation of package policies within the agent
                policy: ``"simplified"`` or ``"legacy"``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``item`` containing the agent policy.

        Raises:
            NotFoundError: If the agent policy does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> policy = client.fleet_policies.get_agent_policy(
            ...     agent_policy_id="policy-1"
            ... )
            >>> print(policy.body["item"]["name"])
        """
        params: dict[str, Any] = {}
        if format is not None:
            params["format"] = format

        path = self._build_space_path(
            f"/api/fleet/agent_policies/{_quote(agent_policy_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    def update_agent_policy(
        self,
        *,
        agent_policy_id: str,
        name: str,
        namespace: str,
        advanced_settings: dict[str, Any] | None = None,
        agent_features: list[dict[str, Any]] | None = None,
        agentless: dict[str, Any] | None = None,
        bump_revision: bool | None = None,
        data_output_id: str | None = None,
        description: str | None = None,
        download_source_id: str | None = None,
        fleet_server_host_id: str | None = None,
        force: bool | None = None,
        global_data_tags: list[dict[str, Any]] | None = None,
        has_agent_version_conditions: bool | None = None,
        has_fleet_server: bool | None = None,
        id: str | None = None,
        inactivity_timeout: int | None = None,
        is_default: bool | None = None,
        is_default_fleet_server: bool | None = None,
        is_managed: bool | None = None,
        is_protected: bool | None = None,
        is_verifier: bool | None = None,
        keep_monitoring_alive: bool | None = None,
        min_agent_version: str | None = None,
        monitoring_diagnostics: dict[str, Any] | None = None,
        monitoring_enabled: list[str] | None = None,
        monitoring_http: dict[str, Any] | None = None,
        monitoring_output_id: str | None = None,
        monitoring_pprof_enabled: bool | None = None,
        overrides: dict[str, Any] | None = None,
        package_agent_version_conditions: list[dict[str, Any]] | None = None,
        required_versions: list[dict[str, Any]] | None = None,
        space_ids: list[str] | None = None,
        supports_agentless: bool | None = None,
        unenroll_timeout: int | None = None,
        format: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update an agent policy.

        ``PUT /api/fleet/agent_policies/{agentPolicyId}``

        This is a full update: ``name`` and ``namespace`` are required and
        omitted optional fields fall back to their defaults.

        Args:
            agent_policy_id: ID of the agent policy to update.
            name: Name of the agent policy.
            namespace: Default data stream namespace for the policy's
                integrations.
            advanced_settings: Advanced agent settings (e.g. log level).
            agent_features: Agent feature flags, list of
                ``{"name": ..., "enabled": ...}`` objects.
            agentless: Agentless deployment configuration.
            bump_revision: Bump the policy revision even without changes.
            data_output_id: ID of the output used for integration data.
            description: Human-readable description of the policy.
            download_source_id: ID of the agent binary download source.
            fleet_server_host_id: ID of the Fleet Server host to use.
            force: Force the update even if some preconditions fail (e.g.
                the policy is managed).
            global_data_tags: Tags added to every document produced by the
                policy, list of ``{"name": ..., "value": ...}`` objects.
            has_agent_version_conditions: Whether the policy has agent
                version conditions.
            has_fleet_server: Whether the policy hosts a Fleet Server.
            id: Policy ID field carried in the body.
            inactivity_timeout: Seconds of inactivity before an agent is
                marked inactive.
            is_default: Mark as the default agent policy.
            is_default_fleet_server: Mark as the default Fleet Server policy.
            is_managed: Mark the policy as hosted/managed.
            is_protected: Enable agent tamper protection.
            is_verifier: Whether the policy is a verifier policy.
            keep_monitoring_alive: Keep the monitoring server alive even when
                monitoring is disabled.
            min_agent_version: Minimum agent version allowed to enroll.
            monitoring_diagnostics: Monitoring diagnostics rate limit /
                uploader settings.
            monitoring_enabled: What to monitor on the agents; any of
                ``"logs"``, ``"metrics"``, ``"traces"``.
            monitoring_http: Monitoring HTTP endpoint settings.
            monitoring_output_id: ID of the output used for agent monitoring
                data.
            monitoring_pprof_enabled: Enable pprof profiling endpoints on
                the agents.
            overrides: Overrides applied on top of the compiled full agent
                policy.
            package_agent_version_conditions: Per-package agent version
                conditions.
            required_versions: Target agent versions for automatic upgrades.
            space_ids: IDs of the spaces the policy is shared with.
            supports_agentless: Whether the policy supports agentless
                integrations (Elastic Cloud / serverless only).
            unenroll_timeout: Seconds after which inactive agents are
                automatically unenrolled.
            format: Representation of package policies in the response:
                ``"simplified"`` or ``"legacy"``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``item`` containing the updated agent
            policy (with a bumped ``revision``).

        Raises:
            BadRequestError: If the request body is invalid.
            NotFoundError: If the agent policy does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = client.fleet_policies.update_agent_policy(
            ...     agent_policy_id="policy-1",
            ...     name="my-agent-policy",
            ...     namespace="default",
            ...     description="Updated description",
            ... )
            >>> print(updated.body["item"]["revision"])
        """
        params: dict[str, Any] = {}
        if format is not None:
            params["format"] = format

        body: dict[str, Any] = {"name": name, "namespace": namespace}
        optional_fields: dict[str, Any] = {
            "advanced_settings": advanced_settings,
            "agent_features": agent_features,
            "agentless": agentless,
            "bumpRevision": bump_revision,
            "data_output_id": data_output_id,
            "description": description,
            "download_source_id": download_source_id,
            "fleet_server_host_id": fleet_server_host_id,
            "force": force,
            "global_data_tags": global_data_tags,
            "has_agent_version_conditions": has_agent_version_conditions,
            "has_fleet_server": has_fleet_server,
            "id": id,
            "inactivity_timeout": inactivity_timeout,
            "is_default": is_default,
            "is_default_fleet_server": is_default_fleet_server,
            "is_managed": is_managed,
            "is_protected": is_protected,
            "is_verifier": is_verifier,
            "keep_monitoring_alive": keep_monitoring_alive,
            "min_agent_version": min_agent_version,
            "monitoring_diagnostics": monitoring_diagnostics,
            "monitoring_enabled": monitoring_enabled,
            "monitoring_http": monitoring_http,
            "monitoring_output_id": monitoring_output_id,
            "monitoring_pprof_enabled": monitoring_pprof_enabled,
            "overrides": overrides,
            "package_agent_version_conditions": package_agent_version_conditions,
            "required_versions": required_versions,
            "space_ids": space_ids,
            "supports_agentless": supports_agentless,
            "unenroll_timeout": unenroll_timeout,
        }
        body.update({k: v for k, v in optional_fields.items() if v is not None})

        path = self._build_space_path(
            f"/api/fleet/agent_policies/{_quote(agent_policy_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "PUT",
            path,
            params=params or None,
            headers={"accept": "application/json"},
            body=body,
        )

    def get_auto_upgrade_agents_status(
        self,
        *,
        agent_policy_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the auto-upgrade agents status for an agent policy.

        ``GET /api/fleet/agent_policies/{agentPolicyId}/auto_upgrade_agents_status``

        Reports how many agents run each target version configured in the
        policy's ``required_versions`` (automatic upgrades).

        Args:
            agent_policy_id: ID of the agent policy.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``currentVersions`` (per-version agent
            counts and failed upgrades) and ``totalAgents``.

        Raises:
            BadRequestError: If the request is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> status = client.fleet_policies.get_auto_upgrade_agents_status(
            ...     agent_policy_id="policy-1"
            ... )
            >>> print(status.body["totalAgents"])
        """
        path = self._build_space_path(
            f"/api/fleet/agent_policies/{_quote(agent_policy_id)}"
            "/auto_upgrade_agents_status",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def copy_agent_policy(
        self,
        *,
        agent_policy_id: str,
        name: str,
        description: str | None = None,
        format: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Copy an agent policy.

        ``POST /api/fleet/agent_policies/{agentPolicyId}/copy``

        Duplicates the agent policy (including its package policies) under a
        new name.

        Args:
            agent_policy_id: ID of the agent policy to copy.
            name: Name for the new (copied) agent policy; must be unique.
            description: Description for the new agent policy.
            format: Representation of package policies in the response:
                ``"simplified"`` or ``"legacy"``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``item`` containing the newly created
            copy of the agent policy.

        Raises:
            BadRequestError: If the name is already in use.
            NotFoundError: If the agent policy does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> copy = client.fleet_policies.copy_agent_policy(
            ...     agent_policy_id="policy-1", name="policy-1 (copy)"
            ... )
            >>> print(copy.body["item"]["id"])
        """
        params: dict[str, Any] = {}
        if format is not None:
            params["format"] = format

        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description

        path = self._build_space_path(
            f"/api/fleet/agent_policies/{_quote(agent_policy_id)}/copy",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "POST",
            path,
            params=params or None,
            headers={"accept": "application/json"},
            body=body,
        )

    def download_agent_policy(
        self,
        *,
        agent_policy_id: str,
        download: bool | None = None,
        standalone: bool | None = None,
        kubernetes: bool | None = None,
        revision: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Download an agent policy as YAML.

        ``GET /api/fleet/agent_policies/{agentPolicyId}/download``

        Returns the compiled policy document served as a downloadable
        ``elastic-agent.yml`` file. The live server responds with
        ``text/x-yaml``, so the response body is the raw YAML string (the
        returned object is a ``TextApiResponse`` at runtime).

        Args:
            agent_policy_id: ID of the agent policy.
            download: Serve the document as a file download.
            standalone: Render the standalone (non-Fleet-managed) variant of
                the policy.
            kubernetes: Render the Kubernetes manifest variant of the policy.
            revision: Specific policy revision to download (defaults to the
                latest).
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is the YAML policy document as a
            string.

        Raises:
            BadRequestError: If the request is invalid.
            NotFoundError: If the agent policy does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> yaml_doc = client.fleet_policies.download_agent_policy(
            ...     agent_policy_id="policy-1"
            ... )
            >>> print(yaml_doc.body[:20])
        """
        params: dict[str, Any] = {}
        if download is not None:
            params["download"] = download
        if standalone is not None:
            params["standalone"] = standalone
        if kubernetes is not None:
            params["kubernetes"] = kubernetes
        if revision is not None:
            params["revision"] = revision

        path = self._build_space_path(
            f"/api/fleet/agent_policies/{_quote(agent_policy_id)}/download",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "text/x-yaml, application/json"},
        )

    def get_full_agent_policy(
        self,
        *,
        agent_policy_id: str,
        download: bool | None = None,
        standalone: bool | None = None,
        kubernetes: bool | None = None,
        revision: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a full (compiled) agent policy.

        ``GET /api/fleet/agent_policies/{agentPolicyId}/full``

        Returns the complete policy document as JSON — the same content an
        enrolled Elastic Agent receives, including outputs and compiled
        inputs.

        Args:
            agent_policy_id: ID of the agent policy.
            download: Serve the document as a file download.
            standalone: Render the standalone (non-Fleet-managed) variant of
                the policy.
            kubernetes: Render the Kubernetes manifest variant of the policy.
            revision: Specific policy revision to fetch (defaults to the
                latest).
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``item`` containing the full agent policy
            document (or the Kubernetes manifest string when
            ``kubernetes=True``).

        Raises:
            BadRequestError: If the request is invalid.
            NotFoundError: If the agent policy does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> full = client.fleet_policies.get_full_agent_policy(
            ...     agent_policy_id="policy-1"
            ... )
            >>> print(full.body["item"]["outputs"].keys())
        """
        params: dict[str, Any] = {}
        if download is not None:
            params["download"] = download
        if standalone is not None:
            params["standalone"] = standalone
        if kubernetes is not None:
            params["kubernetes"] = kubernetes
        if revision is not None:
            params["revision"] = revision

        path = self._build_space_path(
            f"/api/fleet/agent_policies/{_quote(agent_policy_id)}/full",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    def get_agent_policy_outputs(
        self,
        *,
        agent_policy_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get outputs for an agent policy.

        ``GET /api/fleet/agent_policies/{agentPolicyId}/outputs``

        Args:
            agent_policy_id: ID of the agent policy.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``item`` describing the ``data`` and
            ``monitoring`` outputs used by the policy (and per-integration
            output overrides).

        Raises:
            BadRequestError: If the request is invalid.
            NotFoundError: If the agent policy does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> outputs = client.fleet_policies.get_agent_policy_outputs(
            ...     agent_policy_id="policy-1"
            ... )
            >>> print(outputs.body["item"]["data"]["output"]["id"])
        """
        path = self._build_space_path(
            f"/api/fleet/agent_policies/{_quote(agent_policy_id)}/outputs",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def delete_agent_policy(
        self,
        *,
        agent_policy_id: str,
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete an agent policy.

        ``POST /api/fleet/agent_policies/delete``

        Deletes the agent policy and its package policies. Policies with
        enrolled agents cannot be deleted.

        Args:
            agent_policy_id: ID of the agent policy to delete.
            force: Force deletion even if the policy is marked as managed.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the ``id`` and ``name`` of the deleted
            agent policy.

        Raises:
            BadRequestError: If the policy cannot be deleted (e.g. agents
                are still enrolled or the policy does not exist).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> deleted = client.fleet_policies.delete_agent_policy(
            ...     agent_policy_id="policy-1"
            ... )
            >>> print(deleted.body["id"])
        """
        body: dict[str, Any] = {"agentPolicyId": agent_policy_id}
        if force is not None:
            body["force"] = force

        path = self._build_space_path(
            "/api/fleet/agent_policies/delete", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def get_agent_policies_outputs(
        self,
        *,
        ids: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get outputs for multiple agent policies.

        ``POST /api/fleet/agent_policies/outputs``

        Args:
            ids: List of agent policy IDs.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``items``: one entry per agent policy
            describing its ``data`` and ``monitoring`` outputs.

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> outputs = client.fleet_policies.get_agent_policies_outputs(
            ...     ids=["policy-1", "policy-2"]
            ... )
            >>> print(len(outputs.body["items"]))
        """
        path = self._build_space_path(
            "/api/fleet/agent_policies/outputs", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"ids": ids},
        )

    # ----------------------------------------------------------------- #
    # Agentless policies                                                 #
    # ----------------------------------------------------------------- #

    def create_agentless_policy(
        self,
        *,
        name: str,
        package: dict[str, Any],
        additional_datastreams_permissions: list[str] | None = None,
        cloud_connector: dict[str, Any] | None = None,
        condition: str | None = None,
        description: str | None = None,
        force: bool | None = None,
        global_data_tags: list[dict[str, Any]] | None = None,
        id: str | None = None,
        inputs: dict[str, Any] | None = None,
        namespace: str | None = None,
        policy_template: str | None = None,
        var_group_selections: dict[str, Any] | None = None,
        vars: dict[str, Any] | None = None,
        format: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create an agentless policy.

        ``POST /api/fleet/agentless_policies``

        Deploys an integration without a self-managed Elastic Agent. The
        agentless feature is only available in Elastic Cloud and serverless
        environments; on self-managed deployments the server rejects the
        request with a 400 error.

        Args:
            name: Name for the agentless integration policy.
            package: The integration package, e.g.
                ``{"name": "cspm", "version": "1.0.0"}``.
            additional_datastreams_permissions: Additional data stream
                permission patterns granted to the policy.
            cloud_connector: Cloud connector settings, e.g.
                ``{"enabled": True, "target_csp": "aws"}``.
            condition: Condition under which the inputs are active.
            description: Human-readable description of the policy.
            force: Force creation even if some preconditions fail.
            global_data_tags: Tags added to every document produced by the
                policy, list of ``{"name": ..., "value": ...}`` objects.
            id: Explicit ID for the new policy (auto-generated when omitted).
            inputs: Package policy inputs in the simplified (object) format,
                keyed by ``<policy_template>-<input_type>``.
            namespace: Data stream namespace for the policy's data.
            policy_template: Name of the package policy template to use.
            var_group_selections: Selected variable groups, keyed by group
                name.
            vars: Package-level variables in the simplified format.
            format: Response format: ``"simplified"`` (default) or
                ``"legacy"``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``item`` containing the created package
            policy backing the agentless deployment.

        Raises:
            BadRequestError: If the request is invalid or the deployment
                does not support the agentless feature.
            ConflictError: If an agentless policy with the same name exists.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = client.fleet_policies.create_agentless_policy(
            ...     name="my-agentless-policy",
            ...     package={"name": "cspm", "version": "1.0.0"},
            ... )
            >>> print(created.body["item"]["id"])
        """
        params: dict[str, Any] = {}
        if format is not None:
            params["format"] = format

        body: dict[str, Any] = {"name": name, "package": package}
        optional_fields: dict[str, Any] = {
            "additional_datastreams_permissions": (additional_datastreams_permissions),
            "cloud_connector": cloud_connector,
            "condition": condition,
            "description": description,
            "force": force,
            "global_data_tags": global_data_tags,
            "id": id,
            "inputs": inputs,
            "namespace": namespace,
            "policy_template": policy_template,
            "var_group_selections": var_group_selections,
            "vars": vars,
        }
        body.update({k: v for k, v in optional_fields.items() if v is not None})

        path = self._build_space_path(
            "/api/fleet/agentless_policies", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            params=params or None,
            headers={"accept": "application/json"},
            body=body,
        )

    def delete_agentless_policy(
        self,
        *,
        policy_id: str,
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete an agentless policy.

        ``DELETE /api/fleet/agentless_policies/{policyId}``

        Tears down the agentless deployment and deletes the backing package
        policy. On the live 9.4.3 server this endpoint responds 200 with
        ``{"id": ...}`` even for unknown policy IDs (idempotent delete).

        Args:
            policy_id: ID of the agentless policy to delete.
            force: Force deletion even if some preconditions fail.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the ``id`` of the deleted policy.

        Raises:
            BadRequestError: If the request is invalid.
            ConflictError: If the policy cannot be deleted right now.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> deleted = client.fleet_policies.delete_agentless_policy(
            ...     policy_id="agentless-policy-1"
            ... )
            >>> print(deleted.body["id"])
        """
        params: dict[str, Any] = {}
        if force is not None:
            params["force"] = force

        path = self._build_space_path(
            f"/api/fleet/agentless_policies/{_quote(policy_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "DELETE",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- #
    # Package policies                                                   #
    # ----------------------------------------------------------------- #

    def get_package_policies(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        show_upgradeable: bool | None = None,
        kuery: str | None = None,
        format: str | None = None,
        with_agent_count: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get package policies.

        ``GET /api/fleet/package_policies``

        Lists package policies (integration policies), optionally filtered
        with a KQL query and paginated.

        Args:
            page: Page number to return (1-based).
            per_page: Number of policies per page.
            sort_field: Field to sort the results by.
            sort_order: Sort direction, either ``"asc"`` or ``"desc"``.
            show_upgradeable: Only return policies that can be upgraded to a
                newer package version.
            kuery: KQL filter, e.g.
                ``'ingest-package-policies.package.name:"nginx"'``.
            format: Response format: ``"simplified"`` or ``"legacy"``.
            with_agent_count: Include the number of agents using each policy.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``items`` (list of package policies),
            ``total``, ``page`` and ``perPage``.

        Raises:
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> policies = client.fleet_policies.get_package_policies(
            ...     kuery='ingest-package-policies.package.name:"log"'
            ... )
            >>> print(policies.body["total"])
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page
        if sort_field is not None:
            params["sortField"] = sort_field
        if sort_order is not None:
            params["sortOrder"] = sort_order
        if show_upgradeable is not None:
            params["showUpgradeable"] = show_upgradeable
        if kuery is not None:
            params["kuery"] = kuery
        if format is not None:
            params["format"] = format
        if with_agent_count is not None:
            params["withAgentCount"] = with_agent_count

        path = self._build_space_path(
            "/api/fleet/package_policies", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    def create_package_policy(
        self,
        *,
        name: str,
        package: dict[str, Any],
        additional_datastreams_permissions: list[str] | None = None,
        cloud_connector: dict[str, Any] | None = None,
        cloud_connector_id: str | None = None,
        cloud_connector_name: str | None = None,
        condition: str | None = None,
        description: str | None = None,
        enabled: bool | None = None,
        force: bool | None = None,
        global_data_tags: list[dict[str, Any]] | None = None,
        id: str | None = None,
        inputs: list[dict[str, Any]] | dict[str, Any] | None = None,
        is_managed: bool | None = None,
        namespace: str | None = None,
        output_id: str | None = None,
        overrides: dict[str, Any] | None = None,
        package_agent_version_condition: str | None = None,
        policy_id: str | None = None,
        policy_ids: list[str] | None = None,
        policy_template: str | None = None,
        space_ids: list[str] | None = None,
        supports_agentless: bool | None = None,
        supports_cloud_connector: bool | None = None,
        var_group_selections: dict[str, Any] | None = None,
        vars: dict[str, Any] | None = None,
        format: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a package policy.

        ``POST /api/fleet/package_policies``

        Attaches an integration package to one or more agent policies. The
        API accepts two body formats: the classic (legacy) format with
        ``inputs`` as a list of input objects, and the simplified format
        with ``inputs`` as an object keyed by
        ``<policy_template>-<input_type>``. Pass a list or a dict for
        ``inputs`` accordingly. If the package is not installed yet, Kibana
        installs it from the registry as part of this call.

        Args:
            name: Name for the package policy (must be unique).
            package: The integration package, e.g.
                ``{"name": "log", "version": "2.4.4"}``.
            additional_datastreams_permissions: Additional data stream
                permission patterns granted to the policy.
            cloud_connector: Cloud connector settings (simplified format).
            cloud_connector_id: ID of an existing cloud connector (classic
                format).
            cloud_connector_name: Name of the cloud connector (classic
                format).
            condition: Condition under which the inputs are active
                (simplified format).
            description: Human-readable description of the policy.
            enabled: Whether the package policy is enabled (classic format).
            force: Force creation even if some preconditions fail (e.g.
                package below the minimum required version).
            global_data_tags: Tags added to every document produced by the
                policy, list of ``{"name": ..., "value": ...}`` objects.
            id: Explicit ID for the new policy (auto-generated when omitted).
            inputs: Package policy inputs: a list of input objects (classic
                format) or an object keyed by
                ``<policy_template>-<input_type>`` (simplified format).
            is_managed: Mark the policy as managed (classic format).
            namespace: Data stream namespace for the policy's data; falls
                back to the agent policy's namespace when omitted.
            output_id: ID of the output to send this integration's data to
                (classic format).
            overrides: Overrides for the compiled package policy (classic
                format); use only in automation.
            package_agent_version_condition: Agent version condition for the
                package (classic format).
            policy_id: ID of the agent policy to add this policy to
                (deprecated, use ``policy_ids``).
            policy_ids: IDs of the agent policies to add this policy to.
            policy_template: Name of the package policy template to use
                (simplified format).
            space_ids: IDs of the spaces the policy is available in (classic
                format, sent as ``spaceIds``).
            supports_agentless: Whether the policy supports agentless
                deployments (classic format).
            supports_cloud_connector: Whether the policy supports cloud
                connectors (classic format).
            var_group_selections: Selected variable groups, keyed by group
                name.
            vars: Package-level variables (simplified format, or classic
                input-level structure).
            format: Response format: ``"simplified"`` or ``"legacy"``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``item`` containing the created package
            policy.

        Raises:
            BadRequestError: If the request body is invalid (e.g. unknown
                input or stream).
            ConflictError: If a package policy with the same name exists.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = client.fleet_policies.create_package_policy(
            ...     name="my-log-policy",
            ...     package={"name": "log", "version": "2.4.4"},
            ...     policy_ids=["policy-1"],
            ...     inputs={
            ...         "logs-logfile": {
            ...             "enabled": True,
            ...             "streams": {
            ...                 "log.logs": {
            ...                     "enabled": True,
            ...                     "vars": {"paths": ["/var/log/app.log"]},
            ...                 }
            ...             },
            ...         }
            ...     },
            ... )
            >>> print(created.body["item"]["id"])
        """
        params: dict[str, Any] = {}
        if format is not None:
            params["format"] = format

        body: dict[str, Any] = {"name": name, "package": package}
        optional_fields: dict[str, Any] = {
            "additional_datastreams_permissions": (additional_datastreams_permissions),
            "cloud_connector": cloud_connector,
            "cloud_connector_id": cloud_connector_id,
            "cloud_connector_name": cloud_connector_name,
            "condition": condition,
            "description": description,
            "enabled": enabled,
            "force": force,
            "global_data_tags": global_data_tags,
            "id": id,
            "inputs": inputs,
            "is_managed": is_managed,
            "namespace": namespace,
            "output_id": output_id,
            "overrides": overrides,
            "package_agent_version_condition": package_agent_version_condition,
            "policy_id": policy_id,
            "policy_ids": policy_ids,
            "policy_template": policy_template,
            "spaceIds": space_ids,
            "supports_agentless": supports_agentless,
            "supports_cloud_connector": supports_cloud_connector,
            "var_group_selections": var_group_selections,
            "vars": vars,
        }
        body.update({k: v for k, v in optional_fields.items() if v is not None})

        path = self._build_space_path(
            "/api/fleet/package_policies", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            params=params or None,
            headers={"accept": "application/json"},
            body=body,
        )

    def bulk_get_package_policies(
        self,
        *,
        ids: list[str],
        ignore_missing: bool | None = None,
        format: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk get package policies.

        ``POST /api/fleet/package_policies/_bulk_get``

        Args:
            ids: List of package policy IDs to fetch.
            ignore_missing: When True, missing IDs are silently skipped
                instead of producing a 404.
            format: Response format: ``"simplified"`` or ``"legacy"``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``items`` containing the requested
            package policies.

        Raises:
            BadRequestError: If the request body is invalid.
            NotFoundError: If an ID is missing and ``ignore_missing`` is not
                set.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> policies = client.fleet_policies.bulk_get_package_policies(
            ...     ids=["pkg-policy-1"], ignore_missing=True
            ... )
            >>> print(len(policies.body["items"]))
        """
        params: dict[str, Any] = {}
        if format is not None:
            params["format"] = format

        body: dict[str, Any] = {"ids": ids}
        if ignore_missing is not None:
            body["ignoreMissing"] = ignore_missing

        path = self._build_space_path(
            "/api/fleet/package_policies/_bulk_get", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            params=params or None,
            headers={"accept": "application/json"},
            body=body,
        )

    def get_package_policy(
        self,
        *,
        package_policy_id: str,
        format: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a package policy.

        ``GET /api/fleet/package_policies/{packagePolicyId}``

        Args:
            package_policy_id: ID of the package policy.
            format: Response format: ``"simplified"`` or ``"legacy"``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``item`` containing the package policy.

        Raises:
            NotFoundError: If the package policy does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> policy = client.fleet_policies.get_package_policy(
            ...     package_policy_id="pkg-policy-1"
            ... )
            >>> print(policy.body["item"]["name"])
        """
        params: dict[str, Any] = {}
        if format is not None:
            params["format"] = format

        path = self._build_space_path(
            f"/api/fleet/package_policies/{_quote(package_policy_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    def update_package_policy(
        self,
        *,
        package_policy_id: str,
        package: dict[str, Any],
        name: str | None = None,
        additional_datastreams_permissions: list[str] | None = None,
        cloud_connector: dict[str, Any] | None = None,
        cloud_connector_id: str | None = None,
        cloud_connector_name: str | None = None,
        condition: str | None = None,
        description: str | None = None,
        enabled: bool | None = None,
        force: bool | None = None,
        global_data_tags: list[dict[str, Any]] | None = None,
        id: str | None = None,
        inputs: list[dict[str, Any]] | dict[str, Any] | None = None,
        is_managed: bool | None = None,
        namespace: str | None = None,
        output_id: str | None = None,
        overrides: dict[str, Any] | None = None,
        package_agent_version_condition: str | None = None,
        policy_id: str | None = None,
        policy_ids: list[str] | None = None,
        policy_template: str | None = None,
        space_ids: list[str] | None = None,
        supports_agentless: bool | None = None,
        supports_cloud_connector: bool | None = None,
        var_group_selections: dict[str, Any] | None = None,
        vars: dict[str, Any] | None = None,
        version: str | None = None,
        format: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a package policy.

        ``PUT /api/fleet/package_policies/{packagePolicyId}``

        Accepts the same two body formats as
        :meth:`create_package_policy` (classic with ``inputs`` as a list,
        simplified with ``inputs`` as an object). ``name`` is required by
        the simplified format.

        Args:
            package_policy_id: ID of the package policy to update.
            package: The integration package, e.g.
                ``{"name": "log", "version": "2.4.4"}``.
            name: Name for the package policy.
            additional_datastreams_permissions: Additional data stream
                permission patterns granted to the policy.
            cloud_connector: Cloud connector settings (simplified format).
            cloud_connector_id: ID of an existing cloud connector (classic
                format).
            cloud_connector_name: Name of the cloud connector (classic
                format).
            condition: Condition under which the inputs are active
                (simplified format).
            description: Human-readable description of the policy.
            enabled: Whether the package policy is enabled (classic format).
            force: Force the update even if some preconditions fail.
            global_data_tags: Tags added to every document produced by the
                policy.
            id: Policy ID field carried in the body (simplified format).
            inputs: Package policy inputs: a list of input objects (classic
                format) or an object keyed by
                ``<policy_template>-<input_type>`` (simplified format).
            is_managed: Mark the policy as managed (classic format).
            namespace: Data stream namespace for the policy's data.
            output_id: ID of the output to send this integration's data to
                (classic format).
            overrides: Overrides for the compiled package policy (classic
                format).
            package_agent_version_condition: Agent version condition for the
                package (classic format).
            policy_id: ID of the agent policy the policy belongs to
                (deprecated, use ``policy_ids``).
            policy_ids: IDs of the agent policies the policy belongs to.
            policy_template: Name of the package policy template to use
                (simplified format).
            space_ids: IDs of the spaces the policy is available in (classic
                format, sent as ``spaceIds``).
            supports_agentless: Whether the policy supports agentless
                deployments (classic format).
            supports_cloud_connector: Whether the policy supports cloud
                connectors (classic format).
            var_group_selections: Selected variable groups, keyed by group
                name.
            vars: Package-level variables (simplified format, or classic
                input-level structure).
            version: Saved-object version of the policy (classic format,
                optimistic concurrency).
            format: Response format: ``"simplified"`` or ``"legacy"``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``item`` containing the updated package
            policy (with a bumped ``revision``).

        Raises:
            BadRequestError: If the request body is invalid.
            AuthorizationException: If insufficient privileges.
            NotFoundError: If the package policy does not exist.
            AuthenticationException: If authentication fails.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = client.fleet_policies.update_package_policy(
            ...     package_policy_id="pkg-policy-1",
            ...     package={"name": "log", "version": "2.4.4"},
            ...     description="Updated description",
            ... )
            >>> print(updated.body["item"]["revision"])
        """
        params: dict[str, Any] = {}
        if format is not None:
            params["format"] = format

        body: dict[str, Any] = {"package": package}
        optional_fields: dict[str, Any] = {
            "name": name,
            "additional_datastreams_permissions": (additional_datastreams_permissions),
            "cloud_connector": cloud_connector,
            "cloud_connector_id": cloud_connector_id,
            "cloud_connector_name": cloud_connector_name,
            "condition": condition,
            "description": description,
            "enabled": enabled,
            "force": force,
            "global_data_tags": global_data_tags,
            "id": id,
            "inputs": inputs,
            "is_managed": is_managed,
            "namespace": namespace,
            "output_id": output_id,
            "overrides": overrides,
            "package_agent_version_condition": package_agent_version_condition,
            "policy_id": policy_id,
            "policy_ids": policy_ids,
            "policy_template": policy_template,
            "spaceIds": space_ids,
            "supports_agentless": supports_agentless,
            "supports_cloud_connector": supports_cloud_connector,
            "var_group_selections": var_group_selections,
            "vars": vars,
            "version": version,
        }
        body.update({k: v for k, v in optional_fields.items() if v is not None})

        path = self._build_space_path(
            f"/api/fleet/package_policies/{_quote(package_policy_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "PUT",
            path,
            params=params or None,
            headers={"accept": "application/json"},
            body=body,
        )

    def delete_package_policy(
        self,
        *,
        package_policy_id: str,
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a package policy.

        ``DELETE /api/fleet/package_policies/{packagePolicyId}``

        Args:
            package_policy_id: ID of the package policy to delete.
            force: Force deletion even if the policy is used by agents or
                marked as managed.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the ``id`` of the deleted package policy.

        Raises:
            BadRequestError: If the policy cannot be deleted or does not
                exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> deleted = client.fleet_policies.delete_package_policy(
            ...     package_policy_id="pkg-policy-1"
            ... )
            >>> print(deleted.body["id"])
        """
        params: dict[str, Any] = {}
        if force is not None:
            params["force"] = force

        path = self._build_space_path(
            f"/api/fleet/package_policies/{_quote(package_policy_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "DELETE",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    def bulk_delete_package_policies(
        self,
        *,
        package_policy_ids: list[str],
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk delete package policies.

        ``POST /api/fleet/package_policies/delete``

        Args:
            package_policy_ids: IDs of the package policies to delete.
            force: Force deletion even if the policies are used by agents or
                marked as managed.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is a list with one result entry per
            policy (``id``, ``name``, ``success``, ...).

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> results = client.fleet_policies.bulk_delete_package_policies(
            ...     package_policy_ids=["pkg-policy-1"], force=True
            ... )
            >>> print(results.body[0]["success"])
        """
        body: dict[str, Any] = {"packagePolicyIds": package_policy_ids}
        if force is not None:
            body["force"] = force

        path = self._build_space_path(
            "/api/fleet/package_policies/delete", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def upgrade_package_policies(
        self,
        *,
        package_policy_ids: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Upgrade package policies to the latest installed package version.

        ``POST /api/fleet/package_policies/upgrade``

        Args:
            package_policy_ids: IDs of the package policies to upgrade.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is a list with one result entry per
            policy (``id``, ``name``, ``success`` and optional ``statusCode``
            / ``body`` on failure).

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> results = client.fleet_policies.upgrade_package_policies(
            ...     package_policy_ids=["pkg-policy-1"]
            ... )
            >>> print(results.body[0]["success"])
        """
        path = self._build_space_path(
            "/api/fleet/package_policies/upgrade", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"packagePolicyIds": package_policy_ids},
        )

    def upgrade_package_policies_dry_run(
        self,
        *,
        package_policy_ids: list[str],
        package_version: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Dry run a package policy upgrade.

        ``POST /api/fleet/package_policies/upgrade/dryrun``

        Computes the diff an upgrade would produce without persisting any
        change.

        Args:
            package_policy_ids: IDs of the package policies to check.
            package_version: Target package version to simulate the upgrade
                against (defaults to the latest installed version).
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is a list with one result entry per
            policy, each containing ``name``, ``diff`` (current vs proposed
            policy) and ``hasErrors``.

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> results = client.fleet_policies.upgrade_package_policies_dry_run(
            ...     package_policy_ids=["pkg-policy-1"]
            ... )
            >>> print(results.body[0]["hasErrors"])
        """
        body: dict[str, Any] = {"packagePolicyIds": package_policy_ids}
        if package_version is not None:
            body["packageVersion"] = package_version

        path = self._build_space_path(
            "/api/fleet/package_policies/upgrade/dryrun", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )
