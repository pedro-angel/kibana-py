"""Async Kibana Fleet outputs and connectivity API client."""

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


class AsyncFleetOutputsClient(AsyncNamespaceClient):
    """Async client for the Kibana Fleet outputs and connectivity API.

    Manages where Elastic Agents send their data and how they reach the
    Elastic Stack:

    - **Outputs** (``/api/fleet/outputs``): Elasticsearch, remote
      Elasticsearch, Logstash and Kafka destinations for agent data.
    - **Fleet Server hosts** (``/api/fleet/fleet_server_hosts``): the URLs
      agents use to contact Fleet Server.
    - **Proxies** (``/api/fleet/proxies``): Fleet proxies that sit between
      agents and outputs, Fleet Server or the agent binary source.
    - **Agent binary download sources** (``/api/fleet/agent_download_sources``):
      the locations agents download their binaries from.
    - **Remote synced integrations** (``/api/fleet/remote_synced_integrations``):
      status of integration syncing to remote Elasticsearch outputs.
    - **Cloud connectors** (``/api/fleet/cloud_connectors``): reusable cloud
      credentials (AWS/Azure/GCP) shared by agentless package policies.

    Every method accepts an optional ``space_id`` to target a specific Kibana
    space (``None`` targets the default space or the space the client is
    scoped to).

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # List outputs, then create and delete a Logstash output
        >>> outputs = await client.fleet_outputs.get_outputs()
        >>> created = await client.fleet_outputs.create_output(
        ...     name="my-logstash",
        ...     type="logstash",
        ...     hosts=["logstash.example.com:5044"],
        ... )
        >>> await client.fleet_outputs.delete_output(
        ...     output_id=created.body["item"]["id"]
        ... )
    """

    def __init__(
        self,
        client: AsyncKibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the AsyncFleetOutputsClient.

        Args:
            client: The parent AsyncKibana client instance to delegate
                requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> fleet_outputs_client = AsyncFleetOutputsClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    @staticmethod
    def _build_output_body(
        *,
        name: str | None,
        type: str | None,
        hosts: list[str] | None,
        id: str | None,
        is_default: bool | None,
        is_default_monitoring: bool | None,
        is_internal: bool | None,
        is_preconfigured: bool | None,
        allow_edit: list[str] | None,
        ca_sha256: str | None,
        ca_trusted_fingerprint: str | None,
        config_yaml: str | None,
        preset: str | None,
        proxy_id: str | None,
        secrets: dict[str, Any] | None,
        shipper: dict[str, Any] | None,
        ssl: dict[str, Any] | None,
        fields: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build an output request body from the shared output parameters."""
        body: dict[str, Any] = {}
        for key, value in (
            ("name", name),
            ("type", type),
            ("hosts", hosts),
            ("id", id),
            ("is_default", is_default),
            ("is_default_monitoring", is_default_monitoring),
            ("is_internal", is_internal),
            ("is_preconfigured", is_preconfigured),
            ("allow_edit", allow_edit),
            ("ca_sha256", ca_sha256),
            ("ca_trusted_fingerprint", ca_trusted_fingerprint),
            ("config_yaml", config_yaml),
            ("preset", preset),
            ("proxy_id", proxy_id),
            ("secrets", secrets),
            ("shipper", shipper),
            ("ssl", ssl),
        ):
            if value is not None:
                body[key] = value
        if fields:
            body.update(fields)
        return body

    # ----------------------------------------------------------------- #
    # Outputs                                                            #
    # ----------------------------------------------------------------- #

    async def get_outputs(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get outputs.

        Lists all Fleet outputs, including the default Elasticsearch output.

        Args:
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``items`` (list of outputs), plus
            ``page``, ``perPage`` and ``total``.

        Raises:
            BadRequestError: If the request is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> outputs = await client.fleet_outputs.get_outputs()
            >>> for output in outputs.body["items"]:
            ...     print(output["id"], output["type"], output["is_default"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/outputs", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def create_output(
        self,
        *,
        name: str,
        type: str,
        hosts: list[str],
        id: str | None = None,
        is_default: bool | None = None,
        is_default_monitoring: bool | None = None,
        is_internal: bool | None = None,
        is_preconfigured: bool | None = None,
        allow_edit: list[str] | None = None,
        ca_sha256: str | None = None,
        ca_trusted_fingerprint: str | None = None,
        config_yaml: str | None = None,
        preset: str | None = None,
        proxy_id: str | None = None,
        secrets: dict[str, Any] | None = None,
        shipper: dict[str, Any] | None = None,
        ssl: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create output.

        Creates a Fleet output of type ``elasticsearch``,
        ``remote_elasticsearch``, ``logstash`` or ``kafka``. Type-specific
        properties (for example Kafka authentication or remote Elasticsearch
        sync settings) are passed via ``fields``.

        Args:
            name: The output name.
            type: The output type: ``elasticsearch``,
                ``remote_elasticsearch``, ``logstash`` or ``kafka``.
            hosts: The output host URLs (for example
                ``["https://es.example.com:9200"]`` or, for Kafka,
                ``["kafka.example.com:9092"]``).
            id: Optional fixed ID for the output.
            is_default: Whether this output is the default for agent data.
            is_default_monitoring: Whether this output is the default for
                agent monitoring data.
            is_internal: Whether the output is internal (hidden in the UI).
            is_preconfigured: Whether the output is preconfigured.
            allow_edit: List of properties that remain editable when the
                output is preconfigured.
            ca_sha256: SHA-256 of the CA certificate used by agents.
            ca_trusted_fingerprint: Trusted fingerprint of the CA
                certificate.
            config_yaml: Advanced YAML configuration for the output.
            preset: Performance preset for Elasticsearch-like outputs:
                ``balanced``, ``custom``, ``throughput``, ``scale`` or
                ``latency``.
            proxy_id: ID of the Fleet proxy to reach this output through.
            secrets: Secret values (for example
                ``{"ssl": {"key": "..."}}`` or, for remote Elasticsearch,
                ``{"service_token": "..."}``).
            shipper: Shipper settings (disk queue, compression, ...).
            ssl: SSL settings: ``certificate``,
                ``certificate_authorities``, ``key`` and
                ``verification_mode``.
            fields: Additional type-specific properties merged into the
                request body verbatim, for example Kafka settings
                (``{"auth_type": "user_pass", "username": "...",
                "password": "...", "topic": "..."}``) or remote
                Elasticsearch settings (``{"service_token": "...",
                "sync_integrations": True, "kibana_url": "..."}``).
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the created output under ``item``.

        Raises:
            BadRequestError: If the output definition is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = await client.fleet_outputs.create_output(
            ...     name="my-kafka",
            ...     type="kafka",
            ...     hosts=["kafka.example.com:9092"],
            ...     fields={
            ...         "auth_type": "user_pass",
            ...         "username": "fleet",
            ...         "password": "secret",
            ...         "topic": "agent-events",
            ...     },
            ... )
            >>> print(created.body["item"]["id"])
        """
        body = self._build_output_body(
            name=name,
            type=type,
            hosts=hosts,
            id=id,
            is_default=is_default,
            is_default_monitoring=is_default_monitoring,
            is_internal=is_internal,
            is_preconfigured=is_preconfigured,
            allow_edit=allow_edit,
            ca_sha256=ca_sha256,
            ca_trusted_fingerprint=ca_trusted_fingerprint,
            config_yaml=config_yaml,
            preset=preset,
            proxy_id=proxy_id,
            secrets=secrets,
            shipper=shipper,
            ssl=ssl,
            fields=fields,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/outputs", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_output(
        self,
        *,
        output_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get output.

        Gets a single Fleet output by ID.

        Args:
            output_id: The output ID.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the output under ``item``.

        Raises:
            NotFoundError: If the output does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> output = await client.fleet_outputs.get_output(
            ...     output_id="fleet-default-output"
            ... )
            >>> print(output.body["item"]["type"])
            elasticsearch
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/outputs/{_quote(output_id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update_output(
        self,
        *,
        output_id: str,
        name: str | None = None,
        type: str | None = None,
        hosts: list[str] | None = None,
        is_default: bool | None = None,
        is_default_monitoring: bool | None = None,
        is_internal: bool | None = None,
        is_preconfigured: bool | None = None,
        allow_edit: list[str] | None = None,
        ca_sha256: str | None = None,
        ca_trusted_fingerprint: str | None = None,
        config_yaml: str | None = None,
        preset: str | None = None,
        proxy_id: str | None = None,
        secrets: dict[str, Any] | None = None,
        shipper: dict[str, Any] | None = None,
        ssl: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update output.

        Updates a Fleet output by ID. Only the provided properties are sent;
        omitted properties keep their current values. Note that Kafka
        outputs require ``name`` on update.

        Args:
            output_id: The output ID.
            name: The output name.
            type: The output type (change requires type-specific fields).
            hosts: The output host URLs.
            is_default: Whether this output is the default for agent data.
            is_default_monitoring: Whether this output is the default for
                agent monitoring data.
            is_internal: Whether the output is internal (hidden in the UI).
            is_preconfigured: Whether the output is preconfigured.
            allow_edit: List of properties that remain editable when the
                output is preconfigured.
            ca_sha256: SHA-256 of the CA certificate used by agents.
            ca_trusted_fingerprint: Trusted fingerprint of the CA
                certificate.
            config_yaml: Advanced YAML configuration for the output.
            preset: Performance preset for Elasticsearch-like outputs:
                ``balanced``, ``custom``, ``throughput``, ``scale`` or
                ``latency``.
            proxy_id: ID of the Fleet proxy to reach this output through.
            secrets: Secret values (see :meth:`create_output`).
            shipper: Shipper settings (disk queue, compression, ...).
            ssl: SSL settings: ``certificate``,
                ``certificate_authorities``, ``key`` and
                ``verification_mode``.
            fields: Additional type-specific properties merged into the
                request body verbatim (see :meth:`create_output`).
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the updated output under ``item``.

        Raises:
            NotFoundError: If the output does not exist.
            BadRequestError: If the update is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.fleet_outputs.update_output(
            ...     output_id="my-output-id",
            ...     name="renamed-output",
            ... )
            >>> print(updated.body["item"]["name"])
            renamed-output
        """
        body = self._build_output_body(
            name=name,
            type=type,
            hosts=hosts,
            id=None,
            is_default=is_default,
            is_default_monitoring=is_default_monitoring,
            is_internal=is_internal,
            is_preconfigured=is_preconfigured,
            allow_edit=allow_edit,
            ca_sha256=ca_sha256,
            ca_trusted_fingerprint=ca_trusted_fingerprint,
            config_yaml=config_yaml,
            preset=preset,
            proxy_id=proxy_id,
            secrets=secrets,
            shipper=shipper,
            ssl=ssl,
            fields=fields,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/outputs/{_quote(output_id)}", space_id
        )
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete_output(
        self,
        *,
        output_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete output.

        Deletes a Fleet output by ID. The default output cannot be deleted.

        Args:
            output_id: The output ID.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the deleted output's ``id``.

        Raises:
            NotFoundError: If the output does not exist.
            BadRequestError: If the output cannot be deleted (for example
                the default output).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.fleet_outputs.delete_output(output_id="my-output-id")
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/outputs/{_quote(output_id)}", space_id
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    async def get_output_health(
        self,
        *,
        output_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the latest output health.

        Gets the most recent health report for an output. Outputs that have
        not been health-checked yet report ``state: "UNKNOWN"``.

        Args:
            output_id: The output ID.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``state``, ``message`` and
            ``timestamp``.

        Raises:
            NotFoundError: If the output does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> health = await client.fleet_outputs.get_output_health(
            ...     output_id="my-output-id"
            ... )
            >>> print(health.body["state"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/outputs/{_quote(output_id)}/health", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- #
    # Fleet Server hosts                                                 #
    # ----------------------------------------------------------------- #

    async def get_fleet_server_hosts(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get Fleet Server hosts.

        Lists all Fleet Server host configurations.

        Args:
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``items`` (list of Fleet Server
            hosts), plus ``page``, ``perPage`` and ``total``.

        Raises:
            BadRequestError: If the request is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> hosts = await client.fleet_outputs.get_fleet_server_hosts()
            >>> for host in hosts.body["items"]:
            ...     print(host["id"], host["host_urls"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/fleet_server_hosts", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def create_fleet_server_host(
        self,
        *,
        name: str,
        host_urls: list[str],
        id: str | None = None,
        is_default: bool | None = None,
        is_internal: bool | None = None,
        is_preconfigured: bool | None = None,
        proxy_id: str | None = None,
        secrets: dict[str, Any] | None = None,
        ssl: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a Fleet Server host.

        Args:
            name: The Fleet Server host name.
            host_urls: The Fleet Server URLs agents connect to (for example
                ``["https://fleet.example.com:8220"]``).
            id: Optional fixed ID for the Fleet Server host.
            is_default: Whether this is the default Fleet Server host.
            is_internal: Whether the host is internal (hidden in the UI).
            is_preconfigured: Whether the host is preconfigured.
            proxy_id: ID of the Fleet proxy used to reach Fleet Server.
            secrets: Secret values, for example
                ``{"ssl": {"key": "...", "es_key": "...", "agent_key": "..."}}``.
            ssl: SSL settings: ``certificate``, ``certificate_authorities``,
                ``key``, ``client_auth`` plus ``es_*`` and ``agent_*``
                variants for the Elasticsearch and agent connections.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the created Fleet Server host under
            ``item``.

        Raises:
            BadRequestError: If the host definition is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = await client.fleet_outputs.create_fleet_server_host(
            ...     name="my-fleet-server",
            ...     host_urls=["https://fleet.example.com:8220"],
            ... )
            >>> print(created.body["item"]["id"])
        """
        body: dict[str, Any] = {}
        for key, value in (
            ("name", name),
            ("host_urls", host_urls),
            ("id", id),
            ("is_default", is_default),
            ("is_internal", is_internal),
            ("is_preconfigured", is_preconfigured),
            ("proxy_id", proxy_id),
            ("secrets", secrets),
            ("ssl", ssl),
        ):
            if value is not None:
                body[key] = value
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/fleet_server_hosts", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_fleet_server_host(
        self,
        *,
        item_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a Fleet Server host.

        Gets a single Fleet Server host by ID.

        Args:
            item_id: The Fleet Server host ID.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the Fleet Server host under ``item``.

        Raises:
            NotFoundError: If the Fleet Server host does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> host = await client.fleet_outputs.get_fleet_server_host(
            ...     item_id="my-host-id"
            ... )
            >>> print(host.body["item"]["host_urls"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/fleet_server_hosts/{_quote(item_id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update_fleet_server_host(
        self,
        *,
        item_id: str,
        name: str | None = None,
        host_urls: list[str] | None = None,
        is_default: bool | None = None,
        is_internal: bool | None = None,
        proxy_id: str | None = None,
        secrets: dict[str, Any] | None = None,
        ssl: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a Fleet Server host.

        Updates a Fleet Server host by ID. Only the provided properties are
        sent; omitted properties keep their current values.

        Args:
            item_id: The Fleet Server host ID.
            name: The Fleet Server host name.
            host_urls: The Fleet Server URLs agents connect to.
            is_default: Whether this is the default Fleet Server host.
            is_internal: Whether the host is internal (hidden in the UI).
            proxy_id: ID of the Fleet proxy used to reach Fleet Server.
            secrets: Secret values (see :meth:`create_fleet_server_host`).
            ssl: SSL settings (see :meth:`create_fleet_server_host`).
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the updated Fleet Server host under
            ``item``.

        Raises:
            NotFoundError: If the Fleet Server host does not exist.
            BadRequestError: If the update is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.fleet_outputs.update_fleet_server_host(
            ...     item_id="my-host-id",
            ...     name="renamed-fleet-server",
            ... )
            >>> print(updated.body["item"]["name"])
            renamed-fleet-server
        """
        body: dict[str, Any] = {}
        for key, value in (
            ("name", name),
            ("host_urls", host_urls),
            ("is_default", is_default),
            ("is_internal", is_internal),
            ("proxy_id", proxy_id),
            ("secrets", secrets),
            ("ssl", ssl),
        ):
            if value is not None:
                body[key] = value
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/fleet_server_hosts/{_quote(item_id)}", space_id
        )
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete_fleet_server_host(
        self,
        *,
        item_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a Fleet Server host.

        Deletes a Fleet Server host by ID.

        Args:
            item_id: The Fleet Server host ID.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the deleted host's ``id``.

        Raises:
            NotFoundError: If the Fleet Server host does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.fleet_outputs.delete_fleet_server_host(
            ...     item_id="my-host-id"
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/fleet_server_hosts/{_quote(item_id)}", space_id
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- #
    # Proxies                                                            #
    # ----------------------------------------------------------------- #

    async def get_proxies(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get proxies.

        Lists all Fleet proxies.

        Args:
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``items`` (list of proxies), plus
            ``page``, ``perPage`` and ``total``.

        Raises:
            BadRequestError: If the request is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> proxies = await client.fleet_outputs.get_proxies()
            >>> for proxy in proxies.body["items"]:
            ...     print(proxy["id"], proxy["url"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/proxies", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def create_proxy(
        self,
        *,
        name: str,
        url: str,
        id: str | None = None,
        certificate: str | None = None,
        certificate_authorities: str | None = None,
        certificate_key: str | None = None,
        is_preconfigured: bool | None = None,
        proxy_headers: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a proxy.

        Creates a Fleet proxy that agents can use to reach Fleet Server,
        outputs or the agent binary download source.

        Args:
            name: The proxy name.
            url: The proxy URL (for example
                ``"https://proxy.example.com:3128"``).
            id: Optional fixed ID for the proxy.
            certificate: Client certificate (PEM) used to connect to the
                proxy.
            certificate_authorities: CA certificates (PEM) used to verify
                the proxy.
            certificate_key: Client certificate key (PEM).
            is_preconfigured: Whether the proxy is preconfigured.
            proxy_headers: Extra headers sent to the proxy, as a mapping of
                header name to string/number/boolean value.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the created proxy under ``item``.

        Raises:
            BadRequestError: If the proxy definition is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = await client.fleet_outputs.create_proxy(
            ...     name="my-proxy",
            ...     url="https://proxy.example.com:3128",
            ... )
            >>> print(created.body["item"]["id"])
        """
        body: dict[str, Any] = {}
        for key, value in (
            ("name", name),
            ("url", url),
            ("id", id),
            ("certificate", certificate),
            ("certificate_authorities", certificate_authorities),
            ("certificate_key", certificate_key),
            ("is_preconfigured", is_preconfigured),
            ("proxy_headers", proxy_headers),
        ):
            if value is not None:
                body[key] = value
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/proxies", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_proxy(
        self,
        *,
        item_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a proxy.

        Gets a single Fleet proxy by ID.

        Args:
            item_id: The proxy ID.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the proxy under ``item``.

        Raises:
            NotFoundError: If the proxy does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> proxy = await client.fleet_outputs.get_proxy(item_id="my-proxy-id")
            >>> print(proxy.body["item"]["url"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/fleet/proxies/{_quote(item_id)}", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update_proxy(
        self,
        *,
        item_id: str,
        name: str | None = None,
        url: str | None = None,
        certificate: str | None = None,
        certificate_authorities: str | None = None,
        certificate_key: str | None = None,
        proxy_headers: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a proxy.

        Updates a Fleet proxy by ID. Only the provided properties are sent;
        omitted properties keep their current values.

        Args:
            item_id: The proxy ID.
            name: The proxy name.
            url: The proxy URL.
            certificate: Client certificate (PEM) used to connect to the
                proxy.
            certificate_authorities: CA certificates (PEM) used to verify
                the proxy.
            certificate_key: Client certificate key (PEM).
            proxy_headers: Extra headers sent to the proxy.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the updated proxy under ``item``.

        Raises:
            NotFoundError: If the proxy does not exist.
            BadRequestError: If the update is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.fleet_outputs.update_proxy(
            ...     item_id="my-proxy-id",
            ...     name="renamed-proxy",
            ... )
            >>> print(updated.body["item"]["name"])
            renamed-proxy
        """
        body: dict[str, Any] = {}
        for key, value in (
            ("name", name),
            ("url", url),
            ("certificate", certificate),
            ("certificate_authorities", certificate_authorities),
            ("certificate_key", certificate_key),
            ("proxy_headers", proxy_headers),
        ):
            if value is not None:
                body[key] = value
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/fleet/proxies/{_quote(item_id)}", space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete_proxy(
        self,
        *,
        item_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a proxy.

        Deletes a Fleet proxy by ID.

        Args:
            item_id: The proxy ID.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the deleted proxy's ``id``.

        Raises:
            NotFoundError: If the proxy does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.fleet_outputs.delete_proxy(item_id="my-proxy-id")
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/fleet/proxies/{_quote(item_id)}", space_id)
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- #
    # Agent binary download sources                                      #
    # ----------------------------------------------------------------- #

    async def get_agent_download_sources(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get agent binary download sources.

        Lists all agent binary download sources, including the default
        Elastic artifacts source.

        Args:
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``items`` (list of download
            sources), plus ``page``, ``perPage`` and ``total``.

        Raises:
            BadRequestError: If the request is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> sources = await client.fleet_outputs.get_agent_download_sources()
            >>> for source in sources.body["items"]:
            ...     print(source["id"], source["host"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agent_download_sources", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def create_agent_download_source(
        self,
        *,
        name: str,
        host: str,
        id: str | None = None,
        is_default: bool | None = None,
        proxy_id: str | None = None,
        auth: dict[str, Any] | None = None,
        secrets: dict[str, Any] | None = None,
        ssl: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create an agent binary download source.

        Args:
            name: The download source name.
            host: The base URL agents download binaries from (for example
                ``"https://artifacts.example.com/downloads/"``).
            id: Optional fixed ID for the download source.
            is_default: Whether this is the default download source.
            proxy_id: ID of the Fleet proxy used to reach the source.
            auth: Authentication settings: ``username``/``password``,
                ``api_key`` and/or ``headers`` (list of ``{"key", "value"}``
                objects).
            secrets: Secret values, for example
                ``{"auth": {"password": "..."}}`` or
                ``{"ssl": {"key": "..."}}``.
            ssl: SSL settings: ``certificate``, ``certificate_authorities``
                and ``key``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the created download source under
            ``item``.

        Raises:
            BadRequestError: If the download source definition is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = await client.fleet_outputs.create_agent_download_source(
            ...     name="my-artifacts-mirror",
            ...     host="https://artifacts.example.com/downloads/",
            ... )
            >>> print(created.body["item"]["id"])
        """
        body: dict[str, Any] = {}
        for key, value in (
            ("name", name),
            ("host", host),
            ("id", id),
            ("is_default", is_default),
            ("proxy_id", proxy_id),
            ("auth", auth),
            ("secrets", secrets),
            ("ssl", ssl),
        ):
            if value is not None:
                body[key] = value
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/agent_download_sources", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_agent_download_source(
        self,
        *,
        source_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an agent binary download source.

        Gets a single agent binary download source by ID.

        Args:
            source_id: The download source ID.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the download source under ``item``.

        Raises:
            NotFoundError: If the download source does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> source = await client.fleet_outputs.get_agent_download_source(
            ...     source_id="fleet-default-download-source"
            ... )
            >>> print(source.body["item"]["host"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agent_download_sources/{_quote(source_id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update_agent_download_source(
        self,
        *,
        source_id: str,
        name: str,
        host: str,
        is_default: bool | None = None,
        proxy_id: str | None = None,
        auth: dict[str, Any] | None = None,
        secrets: dict[str, Any] | None = None,
        ssl: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update an agent binary download source.

        Updates an agent binary download source by ID. ``name`` and ``host``
        are required by the API on every update.

        Args:
            source_id: The download source ID.
            name: The download source name.
            host: The base URL agents download binaries from.
            is_default: Whether this is the default download source.
            proxy_id: ID of the Fleet proxy used to reach the source.
            auth: Authentication settings (see
                :meth:`create_agent_download_source`).
            secrets: Secret values (see
                :meth:`create_agent_download_source`).
            ssl: SSL settings (see :meth:`create_agent_download_source`).
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the updated download source under
            ``item``.

        Raises:
            NotFoundError: If the download source does not exist.
            BadRequestError: If the update is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.fleet_outputs.update_agent_download_source(
            ...     source_id="my-source-id",
            ...     name="renamed-mirror",
            ...     host="https://artifacts.example.com/downloads/",
            ... )
            >>> print(updated.body["item"]["name"])
            renamed-mirror
        """
        body: dict[str, Any] = {"name": name, "host": host}
        for key, value in (
            ("is_default", is_default),
            ("proxy_id", proxy_id),
            ("auth", auth),
            ("secrets", secrets),
            ("ssl", ssl),
        ):
            if value is not None:
                body[key] = value
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agent_download_sources/{_quote(source_id)}", space_id
        )
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete_agent_download_source(
        self,
        *,
        source_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete an agent binary download source.

        Deletes an agent binary download source by ID.

        Args:
            source_id: The download source ID.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the deleted download source's
            ``id``.

        Raises:
            NotFoundError: If the download source does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.fleet_outputs.delete_agent_download_source(
            ...     source_id="my-source-id"
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/agent_download_sources/{_quote(source_id)}", space_id
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- #
    # Remote synced integrations                                         #
    # ----------------------------------------------------------------- #

    async def get_remote_synced_integrations_status(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get remote synced integrations status.

        Gets the status of integration syncing on this cluster, i.e. the
        integrations synced *to* this cluster by a remote Elasticsearch
        output with ``sync_integrations`` enabled. When syncing has never
        run, the response contains an ``error`` field (for example
        ``"Follower index not found"``) and an empty ``integrations`` list.

        Args:
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``integrations`` (each with
            ``package_name``, ``package_version`` and ``sync_status``) and
            optionally ``error`` and ``custom_assets``.

        Raises:
            BadRequestError: If the request is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> status = (
            ...     await client.fleet_outputs.get_remote_synced_integrations_status()
            ... )
            >>> print(status.body["integrations"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/fleet/remote_synced_integrations/status", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def get_remote_synced_integrations_remote_status(
        self,
        *,
        output_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get remote synced integrations status by output ID.

        Gets the syncing status reported by the remote cluster behind the
        given ``remote_elasticsearch`` output. The output must be a remote
        Elasticsearch output with ``sync_integrations`` enabled, otherwise
        the API responds with a 400 error.

        Args:
            output_id: The ID of a ``remote_elasticsearch`` output.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``integrations`` (each with
            ``package_name``, ``package_version`` and ``sync_status``) and
            optionally ``error`` and ``custom_assets``.

        Raises:
            BadRequestError: If the output is not a remote Elasticsearch
                output or syncing is not enabled.
            NotFoundError: If the output does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> status = await client.fleet_outputs.get_remote_synced_integrations_remote_status(
            ...     output_id="my-remote-output-id"
            ... )
            >>> print(status.body["integrations"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/remote_synced_integrations/{_quote(output_id)}/remote_status",
            space_id,
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- #
    # Cloud connectors                                                   #
    # ----------------------------------------------------------------- #

    async def get_cloud_connectors(
        self,
        *,
        page: int | str | None = None,
        per_page: int | str | None = None,
        kuery: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get cloud connectors.

        Lists Fleet cloud connectors. Technical preview in 9.4.

        Args:
            page: Page number to return.
            per_page: Number of connectors per page.
            kuery: KQL filter query.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``items`` (list of cloud
            connectors).

        Raises:
            BadRequestError: If the request is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> connectors = await client.fleet_outputs.get_cloud_connectors()
            >>> for connector in connectors.body["items"]:
            ...     print(connector["id"], connector["cloudProvider"])
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page
        if kuery is not None:
            params["kuery"] = kuery
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/cloud_connectors", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def create_cloud_connector(
        self,
        *,
        name: str,
        cloud_provider: str,
        vars: dict[str, Any],
        account_type: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create cloud connector.

        Creates a Fleet cloud connector holding reusable cloud credentials.
        Technical preview in 9.4.

        Args:
            name: The connector name. For AWS connectors the role ARN is
                commonly used as the name, matching UI behavior.
            cloud_provider: The cloud provider: ``aws``, ``azure`` or
                ``gcp``.
            vars: Connector variables. For AWS:
                ``{"role_arn": {"value": "arn:aws:iam::...", "type": "text"},
                "external_id": {"value": {"id": "<20-char-secret-id>",
                "isSecretRef": True}, "type": "password"}}``. The
                ``external_id`` must be a secret reference; plain values are
                rejected.
            account_type: The account type: ``single-account`` or
                ``organization-account``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the created cloud connector under
            ``item`` (including ``verification_status`` and
            ``packagePolicyCount``).

        Raises:
            BadRequestError: If the connector definition or its vars are
                invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = await client.fleet_outputs.create_cloud_connector(
            ...     name="arn:aws:iam::123456789012:role/my-role",
            ...     cloud_provider="aws",
            ...     vars={
            ...         "role_arn": {
            ...             "value": "arn:aws:iam::123456789012:role/my-role",
            ...             "type": "text",
            ...         },
            ...         "external_id": {
            ...             "value": {"id": "AbCdEfGhIjKlMnOpQrSt", "isSecretRef": True},
            ...             "type": "password",
            ...         },
            ...     },
            ... )
            >>> print(created.body["item"]["id"])
        """
        body: dict[str, Any] = {
            "name": name,
            "cloudProvider": cloud_provider,
            "vars": vars,
        }
        if account_type is not None:
            body["accountType"] = account_type
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/cloud_connectors", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_cloud_connector(
        self,
        *,
        cloud_connector_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get cloud connector.

        Gets a single Fleet cloud connector by ID. Technical preview in 9.4.

        Args:
            cloud_connector_id: The cloud connector ID.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the cloud connector under ``item``.

        Raises:
            BadRequestError: If the connector does not exist (the Fleet
                cloud connector API wraps not-found errors in a 400
                response).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> connector = await client.fleet_outputs.get_cloud_connector(
            ...     cloud_connector_id="my-connector-id"
            ... )
            >>> print(connector.body["item"]["cloudProvider"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/cloud_connectors/{_quote(cloud_connector_id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update_cloud_connector(
        self,
        *,
        cloud_connector_id: str,
        name: str | None = None,
        vars: dict[str, Any] | None = None,
        account_type: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update cloud connector.

        Updates a Fleet cloud connector by ID. Only the provided properties
        are sent; omitted properties keep their current values. Technical
        preview in 9.4.

        Args:
            cloud_connector_id: The cloud connector ID.
            name: The connector name.
            vars: Connector variables (see :meth:`create_cloud_connector`).
            account_type: The account type: ``single-account`` or
                ``organization-account``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the updated cloud connector under
            ``item``.

        Raises:
            BadRequestError: If the update is invalid or the connector does
                not exist (the Fleet cloud connector API wraps not-found
                errors in a 400 response).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.fleet_outputs.update_cloud_connector(
            ...     cloud_connector_id="my-connector-id",
            ...     name="arn:aws:iam::123456789012:role/my-renamed-role",
            ... )
            >>> print(updated.body["item"]["name"])
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if vars is not None:
            body["vars"] = vars
        if account_type is not None:
            body["accountType"] = account_type
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/cloud_connectors/{_quote(cloud_connector_id)}", space_id
        )
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete_cloud_connector(
        self,
        *,
        cloud_connector_id: str,
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete cloud connector.

        Deletes a Fleet cloud connector by ID. Technical preview in 9.4.

        Args:
            cloud_connector_id: The cloud connector ID.
            force: Force deletion even if the connector is in use by
                package policies.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the deleted connector's ``id``.

        Raises:
            BadRequestError: If the connector is in use (without ``force``)
                or does not exist (the Fleet cloud connector API wraps
                not-found errors in a 400 response).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.fleet_outputs.delete_cloud_connector(
            ...     cloud_connector_id="my-connector-id",
            ...     force=True,
            ... )
        """
        params: dict[str, Any] = {}
        if force is not None:
            params["force"] = force
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/cloud_connectors/{_quote(cloud_connector_id)}", space_id
        )
        return await self.perform_request(
            "DELETE",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def get_cloud_connector_usage(
        self,
        *,
        cloud_connector_id: str,
        page: int | None = None,
        per_page: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get cloud connector usage.

        Lists the package policies that use a cloud connector. Technical
        preview in 9.4.

        Args:
            cloud_connector_id: The cloud connector ID.
            page: Page number to return.
            per_page: Number of package policies per page.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``items`` (package policies using
            the connector), plus ``page``, ``perPage`` and ``total``.

        Raises:
            BadRequestError: If the connector does not exist (the Fleet
                cloud connector API wraps not-found errors in a 400
                response).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> usage = await client.fleet_outputs.get_cloud_connector_usage(
            ...     cloud_connector_id="my-connector-id"
            ... )
            >>> print(usage.body["total"])
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/cloud_connectors/{_quote(cloud_connector_id)}/usage", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )
