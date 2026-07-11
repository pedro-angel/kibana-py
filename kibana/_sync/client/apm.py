"""Kibana APM API client."""

from __future__ import annotations

import json
import uuid
from typing import Any

from elastic_transport import ObjectApiResponse

from .utils import NamespaceClient, _quote


def _build_sourcemap_multipart_body(
    *,
    service_name: str,
    service_version: str,
    bundle_filepath: str,
    sourcemap: str | bytes | dict[str, Any],
) -> tuple[bytes, str]:
    """Build a ``multipart/form-data`` body for the source map upload API.

    :param service_name: Value for the ``service_name`` form field
    :param service_version: Value for the ``service_version`` form field
    :param bundle_filepath: Value for the ``bundle_filepath`` form field
    :param sourcemap: Source map content for the ``sourcemap`` file field.
        A ``dict`` is JSON-encoded; ``str``/``bytes`` are sent as-is.
    :return: Tuple of (body bytes, content-type header value with boundary)

    The file part is sent as ``application/octet-stream``: live Kibana 9.4.3
    JSON-parses ``application/json`` multipart parts into objects, which then
    fail the route's string/buffer validation ("Input is not a Buffer").
    """
    if isinstance(sourcemap, dict):
        sourcemap_bytes = json.dumps(sourcemap).encode("utf-8")
    elif isinstance(sourcemap, str):
        sourcemap_bytes = sourcemap.encode("utf-8")
    else:
        sourcemap_bytes = sourcemap

    boundary = f"kbnpy{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for field_name, field_value in (
        ("service_name", service_name),
        ("service_version", service_version),
        ("bundle_filepath", bundle_filepath),
    ):
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{field_name}"\r\n'
                "\r\n"
                f"{field_value}\r\n"
            ).encode()
        )
    parts.append(
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="sourcemap"; '
            'filename="bundle.js.map"\r\n'
            "Content-Type: application/octet-stream\r\n"
            "\r\n"
        ).encode()
        + sourcemap_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class ApmClient(NamespaceClient):
    """Client for the Kibana APM (Application Performance Monitoring) API.

    Covers the Kibana 9.4.3 APM UI endpoints: APM agent keys, APM Server
    schema, service annotations, agent configurations, and RUM source maps.

    The endpoints are space-scoped: every method accepts an optional
    ``space_id`` to route the request through the ``/s/{space_id}`` path
    prefix (``None`` targets the default space or the space the client is
    scoped to). Note that agent configurations and source maps live in
    cluster-wide storage (the ``.apm-agent-configuration`` index and Fleet
    artifacts), so the same data is visible from every space; the space
    prefix scopes the API route and its privilege checks rather than the
    data.

    Required privileges vary per endpoint: agent configuration and source
    map writes need APM/APM settings write privileges; creating agent keys
    additionally requires the ``manage_own_api_key`` cluster privilege.

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create an agent configuration
        >>> client.apm.create_or_update_agent_configuration(
        ...     service_name="opbeans-node",
        ...     service_environment="production",
        ...     settings={"transaction_sample_rate": "0.5"},
        ... )
        >>>
        >>> # List agent configurations
        >>> for c in client.apm.get_agent_configurations().body["configurations"]:
        ...     print(c["service"], c["settings"])
    """

    # ----------------------------------------------------------------- #
    # Agent keys                                                        #
    # ----------------------------------------------------------------- #

    def create_agent_key(
        self,
        *,
        name: str,
        privileges: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create an APM agent key.

        Create a new agent key for APM. The user creating the key must have
        the ``manage_own_api_key`` cluster privilege and ``event:write`` /
        ``config_agent:read`` APM application privileges (superusers qualify).
        The key secret is returned only once, in the response.

        Args:
            name: The name of the APM agent key.
            privileges: The APM agent key privileges. One or more of
                ``"event:write"`` (required for ingesting APM agent events)
                and ``"config_agent:read"`` (required for APM agents to read
                agent configuration remotely).
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``agentKey`` object containing ``id``,
            ``name``, ``api_key`` and ``encoded`` (the base64 credentials).

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks the required
                privileges to create APM agent keys.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> response = client.apm.create_agent_key(
            ...     name="my-agent-key",
            ...     privileges=["event:write", "config_agent:read"],
            ... )
            >>> print(response.body["agentKey"]["encoded"])
        """
        path = self._build_space_path("/api/apm/agent_keys", space_id, validate_spaces)
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"name": name, "privileges": privileges},
        )

    # ----------------------------------------------------------------- #
    # APM Server schema                                                 #
    # ----------------------------------------------------------------- #

    def save_server_schema(
        self,
        *,
        schema: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Save APM Server schema.

        .. deprecated:: 9.4
            This endpoint is deprecated. It supports the APM Server to Fleet
            migration workflow in the Applications UI; manage the APM
            integration policy through Fleet instead.

        Save the APM Server settings schema used when migrating a standalone
        APM Server to a Fleet-managed APM integration.

        Args:
            schema: Schema object with APM Server settings (arbitrary
                key/value pairs, e.g. ``{"apm-server.host": "0.0.0.0:8200"}``).
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body on success.

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks APM settings write
                privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> client.apm.save_server_schema(
            ...     schema={"apm-server.host": "0.0.0.0:8200"}
            ... )
        """
        path = self._build_space_path(
            "/api/apm/fleet/apm_server_schema", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"schema": schema},
        )

    # ----------------------------------------------------------------- #
    # Annotations                                                       #
    # ----------------------------------------------------------------- #

    def create_annotation(
        self,
        *,
        service_name: str,
        timestamp: str,
        service_version: str,
        service_environment: str | None = None,
        message: str | None = None,
        tags: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a service annotation.

        Create a new annotation (e.g. a deployment marker) for a specific
        service. Annotations are stored in the ``observability-annotations``
        index and rendered in the Applications UI charts.

        Args:
            service_name: The name of the service (URL path parameter).
            timestamp: The date and time of the annotation, in ISO 8601
                format (maps to the ``@timestamp`` body field).
            service_version: The version of the service.
            service_environment: The environment of the service.
            message: The message displayed in the annotation. Defaults to
                ``service.version`` server-side.
            tags: Tags used by the Applications UI to distinguish APM
                annotations from other annotations. Defaults to ``["apm"]``;
                the ``apm`` tag cannot be removed.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the created annotation document
            (``_id``, ``_index`` and ``_source``).

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks annotation write
                privileges.
            NotFoundError: If the annotation feature is unavailable.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> response = client.apm.create_annotation(
            ...     service_name="opbeans-java",
            ...     timestamp="2026-07-03T08:52:00.000Z",
            ...     service_version="1.2.3",
            ...     service_environment="production",
            ...     message="Deployed 1.2.3",
            ... )
            >>> print(response.body["_source"]["annotation"]["type"])
            deployment
        """
        service: dict[str, Any] = {"version": service_version}
        if service_environment is not None:
            service["environment"] = service_environment

        body: dict[str, Any] = {"@timestamp": timestamp, "service": service}
        if message is not None:
            body["message"] = message
        if tags is not None:
            body["tags"] = tags

        path = self._build_space_path(
            f"/api/apm/services/{_quote(service_name)}/annotation",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def search_annotations(
        self,
        *,
        service_name: str,
        environment: str | None = None,
        start: str | None = None,
        end: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Search for annotations.

        Search for annotations related to a specific service.

        Note:
            The 9.4.3 OpenAPI spec marks all three query parameters as
            optional, but the live server rejects requests that omit any of
            them (400 Bad Request). Pass ``environment="ENVIRONMENT_ALL"``
            to search across all environments.

        Args:
            service_name: The name of the service (URL path parameter).
            environment: The environment to filter annotations by. The
                sentinel values ``"ENVIRONMENT_ALL"`` and
                ``"ENVIRONMENT_NOT_DEFINED"`` are accepted. Required by the
                live server.
            start: The start date for the search, in ISO 8601 format
                (date-time). Required by the live server.
            end: The end date for the search, in ISO 8601 format
                (date-time). Required by the live server.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``annotations`` list; each entry
            contains ``type``, ``id``, ``@timestamp`` and ``text``.

        Raises:
            BadRequestError: If the query parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks APM read privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> response = client.apm.search_annotations(
            ...     service_name="opbeans-java",
            ...     environment="production",
            ...     start="2026-07-01T00:00:00.000Z",
            ...     end="2026-07-04T00:00:00.000Z",
            ... )
            >>> for annotation in response.body["annotations"]:
            ...     print(annotation["text"])
        """
        params: dict[str, Any] = {}
        if environment is not None:
            params["environment"] = environment
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end

        path = self._build_space_path(
            f"/api/apm/services/{_quote(service_name)}/annotation/search",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- #
    # Agent configuration                                               #
    # ----------------------------------------------------------------- #

    def get_agent_configurations(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a list of agent configurations.

        Get all APM agent configurations stored in the
        ``.apm-agent-configuration`` index.

        Args:
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with a ``configurations`` list; each entry
            contains ``service``, ``settings``, ``@timestamp``,
            ``applied_by_agent``, ``etag`` and optionally ``agent_name``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks APM read privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> response = client.apm.get_agent_configurations()
            >>> for config in response.body["configurations"]:
            ...     print(config["service"], config["settings"])
        """
        path = self._build_space_path(
            "/api/apm/settings/agent-configuration", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def create_or_update_agent_configuration(
        self,
        *,
        settings: dict[str, str],
        service_name: str | None = None,
        service_environment: str | None = None,
        agent_name: str | None = None,
        overwrite: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create or update agent configuration.

        Create or update an APM agent configuration for a service. Omitting
        ``service_name``/``service_environment`` targets all services and/or
        all environments.

        Args:
            settings: Agent configuration settings as string key/value
                pairs (e.g. ``{"transaction_sample_rate": "0.5"}``).
            service_name: The name of the service the configuration applies
                to. Omit to target all services.
            service_environment: The environment of the service. Omit to
                target all environments.
            agent_name: The agent name, used by the UI to determine which
                settings to display.
            overwrite: If ``True``, an existing configuration for the same
                service/environment is overwritten.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body on success.

        Raises:
            BadRequestError: If the body is invalid (e.g. unknown setting).
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks APM settings write
                privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> client.apm.create_or_update_agent_configuration(
            ...     service_name="opbeans-node",
            ...     service_environment="production",
            ...     settings={"transaction_sample_rate": "0.5"},
            ...     agent_name="nodejs",
            ...     overwrite=True,
            ... )
        """
        service: dict[str, Any] = {}
        if service_name is not None:
            service["name"] = service_name
        if service_environment is not None:
            service["environment"] = service_environment

        body: dict[str, Any] = {"service": service, "settings": settings}
        if agent_name is not None:
            body["agent_name"] = agent_name

        params: dict[str, Any] = {}
        if overwrite is not None:
            params["overwrite"] = overwrite

        path = self._build_space_path(
            "/api/apm/settings/agent-configuration", space_id, validate_spaces
        )
        return self.perform_request(
            "PUT",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
            body=body,
        )

    def delete_agent_configuration(
        self,
        *,
        service_name: str | None = None,
        service_environment: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete agent configuration.

        Delete the APM agent configuration that matches the given service
        name and environment.

        Args:
            service_name: The name of the service the configuration applies
                to. Omit for an all-services configuration.
            service_environment: The environment of the service. Omit for an
                all-environments configuration.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the Elasticsearch delete result (e.g.
            ``result: "deleted"``).

        Raises:
            BadRequestError: If the body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks APM settings write
                privileges.
            NotFoundError: If no matching configuration exists.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> client.apm.delete_agent_configuration(
            ...     service_name="opbeans-node",
            ...     service_environment="production",
            ... )
        """
        service: dict[str, Any] = {}
        if service_name is not None:
            service["name"] = service_name
        if service_environment is not None:
            service["environment"] = service_environment

        path = self._build_space_path(
            "/api/apm/settings/agent-configuration", space_id, validate_spaces
        )
        return self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
            body={"service": service},
        )

    def get_agent_configuration(
        self,
        *,
        name: str | None = None,
        environment: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get single agent configuration.

        Get the single APM agent configuration matching the given service
        name and environment. Omitting ``name``/``environment`` returns the
        all-services/all-environments configuration if one exists.

        Args:
            name: The service name of the configuration.
            environment: The service environment of the configuration.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the configuration document: ``id``,
            ``service``, ``settings``, ``@timestamp``, ``applied_by_agent``,
            ``etag`` and optionally ``agent_name``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks APM read privileges.
            NotFoundError: If no matching configuration exists.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> response = client.apm.get_agent_configuration(
            ...     name="opbeans-node", environment="production"
            ... )
            >>> print(response.body["settings"])
            {'transaction_sample_rate': '0.5'}
        """
        params: dict[str, Any] = {}
        if name is not None:
            params["name"] = name
        if environment is not None:
            params["environment"] = environment

        path = self._build_space_path(
            "/api/apm/settings/agent-configuration/view", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    def search_agent_configurations(
        self,
        *,
        service_name: str | None = None,
        service_environment: str | None = None,
        etag: str | None = None,
        mark_as_applied_by_agent: bool | None = None,
        error: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Look up a single agent configuration (APM Server search).

        .. deprecated:: 9.4
            This endpoint is deprecated. It exists for APM Server / agents to
            poll configuration; use :meth:`get_agent_configuration` to read a
            configuration interactively.

        Search for a single agent configuration and update
        ``applied_by_agent``: if the ``etag`` matches the stored one,
        ``applied_by_agent`` is set to ``true``.

        Args:
            service_name: The name of the service.
            service_environment: The environment of the service.
            etag: If the etag matches the stored configuration,
                ``applied_by_agent`` will be set to ``true``.
            mark_as_applied_by_agent: If ``True``, forces
                ``applied_by_agent`` to ``true`` regardless of etag (needed
                for agents without etag support, e.g. Jaeger).
            error: If provided, the agent configuration is marked as errored
                and ``applied_by_agent`` is set to ``false``.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the matching Elasticsearch hit
            (``_id``, ``_index`` and ``_source`` with the configuration).

        Raises:
            BadRequestError: If the body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks APM read privileges.
            NotFoundError: If no matching configuration exists.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> response = client.apm.search_agent_configurations(
            ...     service_name="opbeans-node",
            ...     service_environment="production",
            ...     etag="0bc3b5ebf18fba8163fe4c96f491e3767a358f85",
            ... )
            >>> print(response.body["_source"]["settings"])
        """
        service: dict[str, Any] = {}
        if service_name is not None:
            service["name"] = service_name
        if service_environment is not None:
            service["environment"] = service_environment

        body: dict[str, Any] = {"service": service}
        if etag is not None:
            body["etag"] = etag
        if mark_as_applied_by_agent is not None:
            body["mark_as_applied_by_agent"] = mark_as_applied_by_agent
        if error is not None:
            body["error"] = error

        path = self._build_space_path(
            "/api/apm/settings/agent-configuration/search", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def get_environments(
        self,
        *,
        service_name: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get environments for service.

        Get the list of environments for a service, used when creating an
        agent configuration. Environments already covered by a configuration
        are flagged with ``alreadyConfigured``.

        Args:
            service_name: The name of the service. Omit to list environments
                across all services.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``environments`` list; each entry
            contains ``name`` (``ALL_OPTION_VALUE`` represents "all
            environments") and ``alreadyConfigured``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks APM read privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> response = client.apm.get_environments(
            ...     service_name="opbeans-node"
            ... )
            >>> for env in response.body["environments"]:
            ...     print(env["name"], env["alreadyConfigured"])
        """
        params: dict[str, Any] = {}
        if service_name is not None:
            params["serviceName"] = service_name

        path = self._build_space_path(
            "/api/apm/settings/agent-configuration/environments",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    def get_agent_name(
        self,
        *,
        service_name: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get agent name for service.

        Get the agent name for a service, derived from ingested APM data.
        Returns an empty object when the service has no APM data yet.

        Args:
            service_name: The name of the service.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``agentName`` field (e.g. ``nodejs``)
            when APM data exists for the service; empty body otherwise.

        Raises:
            BadRequestError: If ``service_name`` is missing.
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks APM read privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> response = client.apm.get_agent_name(
            ...     service_name="opbeans-node"
            ... )
            >>> print(response.body.get("agentName"))
            nodejs
        """
        path = self._build_space_path(
            "/api/apm/settings/agent-configuration/agent_name",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            params={"serviceName": service_name},
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- #
    # Source maps                                                       #
    # ----------------------------------------------------------------- #

    def get_sourcemaps(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get source maps.

        Get a list of the uploaded RUM source maps (stored as Fleet
        artifacts).

        Args:
            page: Page number (1-based).
            per_page: Number of source maps per page (``perPage`` query
                parameter).
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``artifacts`` list and a ``total``
            count; each artifact contains ``id``, ``identifier``, ``body``
            (with ``serviceName``, ``serviceVersion``, ``bundleFilepath``
            and ``sourceMap``), ``created`` and integrity metadata.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks APM read privileges.
            InternalServerError: If the Fleet artifacts store is
                unavailable.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> response = client.apm.get_sourcemaps(page=1, per_page=10)
            >>> for artifact in response.body["artifacts"]:
            ...     print(artifact["identifier"])
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page

        path = self._build_space_path("/api/apm/sourcemaps", space_id, validate_spaces)
        return self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    def upload_sourcemap(
        self,
        *,
        service_name: str,
        service_version: str,
        bundle_filepath: str,
        sourcemap: str | bytes | dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Upload a source map.

        Upload a RUM source map for a service so APM can un-minify RUM stack
        traces. The payload is sent as ``multipart/form-data``. The maximum
        payload size accepted by Kibana is ``1mb`` by default.

        Args:
            service_name: The name of the service that the source map should
                apply to.
            service_version: The version of the service that the source map
                should apply to.
            bundle_filepath: The absolute path of the final bundle as used
                in the web application.
            sourcemap: The source map content. It must follow the
                `source map format specification
                <https://tc39.es/ecma426/>`_. Accepts a ``dict`` (JSON
                encoded automatically), a JSON ``str``, or raw ``bytes``.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the created Fleet artifact: ``id``,
            ``identifier``, ``relative_url``, ``body`` (compressed),
            ``created`` and integrity metadata.

        Raises:
            BadRequestError: If the form fields or source map are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks APM settings write
                privileges.
            InternalServerError: If the Fleet artifacts store is
                unavailable.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> response = client.apm.upload_sourcemap(
            ...     service_name="opbeans-rum",
            ...     service_version="1.2.3",
            ...     bundle_filepath="http://localhost/static/js/bundle.js",
            ...     sourcemap={
            ...         "version": 3,
            ...         "file": "bundle.js",
            ...         "sources": ["app.js"],
            ...         "names": [],
            ...         "mappings": "AAAA",
            ...     },
            ... )
            >>> print(response.body["id"])
        """
        body, content_type = _build_sourcemap_multipart_body(
            service_name=service_name,
            service_version=service_version,
            bundle_filepath=bundle_filepath,
            sourcemap=sourcemap,
        )
        path = self._build_space_path("/api/apm/sourcemaps", space_id, validate_spaces)
        return self.perform_request(
            "POST",
            path,
            headers={
                "accept": "application/json",
                "content-type": content_type,
            },
            body=body,  # type: ignore[arg-type]
        )

    def delete_sourcemap(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete source map.

        Delete a previously uploaded source map by its artifact ID.

        Args:
            id: The ID of the source map artifact to delete (as returned by
                :meth:`get_sourcemaps` / :meth:`upload_sourcemap`, e.g.
                ``"apm:opbeans-rum-1.2.3-<sha256>"``).
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body on success.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks APM settings write
                privileges.
            InternalServerError: If the artifact cannot be deleted (e.g.
                unknown ID).
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> client.apm.delete_sourcemap(
            ...     id="apm:opbeans-rum-1.2.3-ba48e0ac0c14..."
            ... )
        """
        path = self._build_space_path(
            f"/api/apm/sourcemaps/{_quote(id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )
