"""Async Kibana Fleet Elastic Package Manager (EPM) API client."""

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient, _quote
from kibana.serializer import RawSerializer

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


def _ensure_raw_serializer(client: Any, content_type: str) -> None:
    """Register a pass-through serializer for an archive mimetype.

    elastic-transport serializes request bodies based on the content-type
    header and rejects mimetypes it does not know. Package archives
    (``application/zip`` / ``application/gzip``) are pre-encoded bytes, so a
    raw pass-through serializer is registered on the transport's serializer
    collection the first time such an upload is performed.

    :param client: Parent (Async)Kibana client owning the transport
    :param content_type: Content type of the upload (parameters are ignored)
    """
    transport = getattr(client, "_transport", None)
    collection = getattr(transport, "serializers", None)
    if collection is None:
        return
    mimetype = content_type.partition(";")[0].strip()
    if mimetype and mimetype not in collection.serializers:
        serializer = RawSerializer()
        serializer.mimetype = mimetype
        collection.serializers[mimetype] = serializer


def _normalize_name_items(
    items: list[str | dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize a list of package identifiers to ``{"name": ...}`` dicts.

    Accepts plain package-name strings or already-shaped dicts (e.g.
    ``{"name": "tcp", "version": "2.3.1"}``) and returns a list of dicts as
    required by the Fleet bulk package operation request schemas.

    :param items: Package names or dicts
    :return: List of dicts, strings converted to ``{"name": <string>}``
    """
    normalized: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            normalized.append({"name": item})
        else:
            normalized.append(item)
    return normalized


class AsyncFleetEpmClient(AsyncNamespaceClient):
    """Async client for the Kibana Fleet Elastic Package Manager (EPM) API.

    The Elastic Package Manager APIs browse, install, upgrade, roll back and
    uninstall integration packages from the Elastic Package Registry, manage
    their Kibana/Elasticsearch assets, create custom integrations, and inspect
    the data streams shipped by installed packages.

    All Fleet EPM operations are space-aware: every method accepts an optional
    ``space_id`` to target a specific space (``None`` targets the default
    space or the space the client is scoped to).

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Browse the registry and install a pinned package version
        >>> await client.fleet_epm.get_categories()
        >>> await client.fleet_epm.install_package(pkg_name="tcp", pkg_version="2.3.1")
        >>>
        >>> # Inspect and uninstall it again
        >>> pkg = await client.fleet_epm.get_package(pkg_name="tcp")
        >>> print(pkg.body["item"]["status"])
        installed
        >>> await client.fleet_epm.uninstall_package(pkg_name="tcp")
    """

    def __init__(
        self,
        client: AsyncKibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the AsyncFleetEpmClient.

        Args:
            client: The parent AsyncKibana client instance to delegate requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> fleet_epm_client = AsyncFleetEpmClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    # ------------------------------------------------------------------
    # Package discovery
    # ------------------------------------------------------------------

    async def get_categories(
        self,
        *,
        prerelease: bool | None = None,
        include_policy_templates: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get package categories.

        ``GET /api/fleet/epm/categories``

        Retrieves the list of integration categories known to the Elastic
        Package Registry together with the number of packages in each one.

        Args:
            prerelease: Whether to include categories from prerelease
                (beta/technical preview) package versions.
            include_policy_templates: Whether policy templates should be
                counted towards the category totals.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``items`` array of categories, each
            with ``id``, ``title``, ``count`` and optional ``parent_id`` /
            ``parent_title``.

        Raises:
            BadRequestError: If the query parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> categories = await client.fleet_epm.get_categories()
            >>> print(categories.body["items"][0]["id"])
            advanced_analytics_ueba
        """
        params: dict[str, Any] = {}
        if prerelease is not None:
            params["prerelease"] = prerelease
        if include_policy_templates is not None:
            params["include_policy_templates"] = include_policy_templates

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/epm/categories", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    async def get_packages(
        self,
        *,
        category: str | None = None,
        prerelease: bool | None = None,
        exclude_install_status: bool | None = None,
        with_package_policies_count: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get packages.

        ``GET /api/fleet/epm/packages``

        Lists the packages available from the Elastic Package Registry,
        merged with the installation status of each package on this Kibana.

        Args:
            category: Only return packages belonging to this category ID.
            prerelease: Whether to include prerelease (beta/technical
                preview) package versions.
            exclude_install_status: When True, the (potentially expensive)
                per-package install status is omitted from the response.
            with_package_policies_count: When True, include the number of
                package policies that use each package.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``items`` array of package summaries
            (``name``, ``version``, ``title``, ``status``, ...).

        Raises:
            BadRequestError: If the query parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> packages = await client.fleet_epm.get_packages(category="custom")
            >>> print([p["name"] for p in packages.body["items"]][:3])
            ['log', 'tcp', 'udp']
        """
        params: dict[str, Any] = {}
        if category is not None:
            params["category"] = category
        if prerelease is not None:
            params["prerelease"] = prerelease
        if exclude_install_status is not None:
            params["excludeInstallStatus"] = exclude_install_status
        if with_package_policies_count is not None:
            params["withPackagePoliciesCount"] = with_package_policies_count

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/epm/packages", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    async def get_installed_packages(
        self,
        *,
        data_stream_type: str | None = None,
        show_only_active_data_streams: bool | None = None,
        name_query: str | None = None,
        search_after: list[str | float] | None = None,
        per_page: int | None = None,
        sort_order: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get installed packages.

        ``GET /api/fleet/epm/packages/installed``

        Lists the packages installed on this Kibana, with their data streams
        and pagination support.

        Args:
            data_stream_type: Only include data streams of this type. One of
                ``"logs"``, ``"metrics"``, ``"traces"``, ``"synthetics"`` or
                ``"profiling"``.
            show_only_active_data_streams: Only include data streams that
                currently have backing indices.
            name_query: Filter installed packages by name substring.
            search_after: Cursor from a previous response's ``searchAfter``
                for deep pagination.
            per_page: Maximum number of packages to return.
            sort_order: Sort order for the results: ``"asc"`` or ``"desc"``.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``items`` (installed packages with
            ``name``, ``version``, ``status``, ``dataStreams``), ``total``
            and an optional ``searchAfter`` cursor.

        Raises:
            BadRequestError: If the query parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> installed = await client.fleet_epm.get_installed_packages(per_page=10)
            >>> print(installed.body["total"])
            4
        """
        params: dict[str, Any] = {}
        if data_stream_type is not None:
            params["dataStreamType"] = data_stream_type
        if show_only_active_data_streams is not None:
            params["showOnlyActiveDataStreams"] = show_only_active_data_streams
        if name_query is not None:
            params["nameQuery"] = name_query
        if search_after is not None:
            params["searchAfter"] = search_after
        if per_page is not None:
            params["perPage"] = per_page
        if sort_order is not None:
            params["sortOrder"] = sort_order

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/epm/packages/installed", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    async def get_limited_packages(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a limited package list.

        ``GET /api/fleet/epm/packages/limited``

        Lists the installed packages that are "limited": packages that may
        only be added once to an agent policy (for example the Endpoint
        Security package).

        Args:
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``items`` array of limited package
            names.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> limited = await client.fleet_epm.get_limited_packages()
            >>> print(limited.body["items"])
            []
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/epm/packages/limited", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def get_package(
        self,
        *,
        pkg_name: str,
        pkg_version: str | None = None,
        ignore_unverified: bool | None = None,
        prerelease: bool | None = None,
        full: bool | None = None,
        with_metadata: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a package.

        ``GET /api/fleet/epm/packages/{pkgName}`` or
        ``GET /api/fleet/epm/packages/{pkgName}/{pkgVersion}``

        Retrieves detailed information about a package (latest version if
        ``pkg_version`` is omitted), including its installation status and
        assets.

        Args:
            pkg_name: Name of the package (e.g. ``"nginx"``).
            pkg_version: Specific package version to fetch. When omitted, the
                latest available version is returned.
            ignore_unverified: Whether to return the package even if its
                signature cannot be verified.
            prerelease: Whether prerelease versions may be returned as the
                latest version.
            full: When True, return the full package manifest and assets.
            with_metadata: When True, include package metadata (e.g.
                ``has_policies``) in the response.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``item`` object describing the package
            (``name``, ``version``, ``status``, ``latestVersion``,
            ``installationInfo`` when installed, ...) and optional
            ``metadata``.

        Raises:
            NotFoundError: If the package does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> pkg = await client.fleet_epm.get_package(pkg_name="tcp")
            >>> print(pkg.body["item"]["latestVersion"])
            2.3.1
        """
        params: dict[str, Any] = {}
        if ignore_unverified is not None:
            params["ignoreUnverified"] = ignore_unverified
        if prerelease is not None:
            params["prerelease"] = prerelease
        if full is not None:
            params["full"] = full
        if with_metadata is not None:
            params["withMetadata"] = with_metadata

        base_path = f"/api/fleet/epm/packages/{_quote(pkg_name)}"
        if pkg_version is not None:
            base_path = f"{base_path}/{_quote(pkg_version)}"

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(base_path, space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    async def get_package_stats(
        self,
        *,
        pkg_name: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get package stats.

        ``GET /api/fleet/epm/packages/{pkgName}/stats``

        Retrieves usage statistics for a package: how many agent policies and
        package policies use it.

        Args:
            pkg_name: Name of the package.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with a ``response`` object containing
            ``agent_policy_count`` and ``package_policy_count``.

        Raises:
            NotFoundError: If the package does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> stats = await client.fleet_epm.get_package_stats(pkg_name="tcp")
            >>> print(stats.body["response"]["package_policy_count"])
            0
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/epm/packages/{_quote(pkg_name)}/stats", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def get_package_file(
        self,
        *,
        pkg_name: str,
        pkg_version: str,
        file_path: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a package file.

        ``GET /api/fleet/epm/packages/{pkgName}/{pkgVersion}/{filePath}``

        Downloads a single file from a package archive (for example its
        manifest, docs or images).

        Args:
            pkg_name: Name of the package.
            pkg_version: Version of the package.
            file_path: Path of the file inside the package archive (e.g.
                ``"manifest.yml"`` or ``"docs/README.md"``). Slashes are
                preserved.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ApiResponse whose body is the raw file content: text files (YAML,
            Markdown, ...) are returned as ``str``, binary files (images) as
            ``bytes``, and JSON files as parsed objects.

        Raises:
            NotFoundError: If the package or file does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> manifest = await client.fleet_epm.get_package_file(
            ...     pkg_name="tcp", pkg_version="2.3.1", file_path="manifest.yml"
            ... )
            >>> print(manifest.body.splitlines()[1])
            name: tcp
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/epm/packages/{_quote(pkg_name)}/{_quote(pkg_version)}"
            f"/{_quote(file_path, safe='/')}",
            space_id,
        )
        return await self.perform_request(
            "GET",
            path,
        )

    async def get_package_dependencies(
        self,
        *,
        pkg_name: str,
        pkg_version: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get package dependencies.

        ``GET /api/fleet/epm/packages/{pkgName}/{pkgVersion}/dependencies``

        Lists the packages that a given package version depends on.

        Args:
            pkg_name: Name of the package.
            pkg_version: Version of the package.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``items`` array of dependency packages
            (``name`` and ``version`` each).

        Raises:
            NotFoundError: If the package does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> deps = await client.fleet_epm.get_package_dependencies(
            ...     pkg_name="tcp", pkg_version="2.3.1"
            ... )
            >>> print(deps.body["items"])
            []
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/epm/packages/{_quote(pkg_name)}/{_quote(pkg_version)}"
            "/dependencies",
            space_id,
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def get_verification_key_id(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a package signature verification key ID.

        ``GET /api/fleet/epm/verification_key_id``

        Returns the ID of the PGP key used to verify package signatures, or
        ``null`` if package verification is disabled.

        Args:
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``id`` string (or ``None``).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> key = await client.fleet_epm.get_verification_key_id()
            >>> print(key.body["id"])
            d27d666cd88e42b4
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/epm/verification_key_id", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Install / update / uninstall
    # ------------------------------------------------------------------

    async def install_package(
        self,
        *,
        pkg_name: str,
        pkg_version: str | None = None,
        force: bool | None = None,
        ignore_constraints: bool | None = None,
        prerelease: bool | None = None,
        ignore_mapping_update_errors: bool | None = None,
        skip_data_stream_rollover: bool | None = None,
        skip_dependency_check: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Install a package from the registry.

        ``POST /api/fleet/epm/packages/{pkgName}`` or
        ``POST /api/fleet/epm/packages/{pkgName}/{pkgVersion}``

        Installs a package (latest version if ``pkg_version`` is omitted)
        from the Elastic Package Registry, creating all of its Kibana and
        Elasticsearch assets.

        Note: installing a version older than the latest available one is
        rejected by Kibana with a 400 ("out-of-date") unless ``force=True``.

        Args:
            pkg_name: Name of the package to install.
            pkg_version: Specific version to install. When omitted, the
                latest available version is installed.
            force: Force installation (e.g. of an outdated version or over a
                failed install).
            ignore_constraints: Ignore the package's Kibana version
                constraints.
            prerelease: Whether prerelease versions may be selected as the
                latest version.
            ignore_mapping_update_errors: Continue the installation even if
                updating index mappings fails.
            skip_data_stream_rollover: Do not roll over existing data streams
                when mappings change.
            skip_dependency_check: Skip the check for packages this package
                depends on.
            space_id: Optional space ID to install the package in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``items`` array of created assets and a
            ``_meta`` object with ``install_source`` and ``name``.

        Raises:
            BadRequestError: If the version is out-of-date and ``force`` is
                not set, or the request is otherwise invalid.
            NotFoundError: If the package does not exist.
            ConflictError: If a concurrent installation is in progress.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.fleet_epm.install_package(
            ...     pkg_name="tcp", pkg_version="2.3.1"
            ... )
            >>> print(result.body["_meta"]["install_source"])
            registry
        """
        params: dict[str, Any] = {}
        if prerelease is not None:
            params["prerelease"] = prerelease
        if ignore_mapping_update_errors is not None:
            params["ignoreMappingUpdateErrors"] = ignore_mapping_update_errors
        if skip_data_stream_rollover is not None:
            params["skipDataStreamRollover"] = skip_data_stream_rollover
        if skip_dependency_check is not None:
            params["skipDependencyCheck"] = skip_dependency_check

        body: dict[str, Any] = {}
        if force is not None:
            body["force"] = force
        if ignore_constraints is not None:
            body["ignore_constraints"] = ignore_constraints

        base_path = f"/api/fleet/epm/packages/{_quote(pkg_name)}"
        if pkg_version is not None:
            base_path = f"{base_path}/{_quote(pkg_version)}"

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(base_path, space_id)
        return await self.perform_request(
            "POST",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
            body=body if body else None,
        )

    async def install_package_by_upload(
        self,
        *,
        content: bytes,
        content_type: str = "application/zip",
        ignore_mapping_update_errors: bool | None = None,
        skip_data_stream_rollover: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Install a package by upload.

        ``POST /api/fleet/epm/packages``

        Installs a package from an uploaded ``.zip`` or ``.tar.gz`` archive
        instead of the Elastic Package Registry. The archive bytes are sent
        as the raw request body.

        Args:
            content: Raw bytes of the package archive.
            content_type: Content type of the archive:
                ``"application/zip"`` (default) or ``"application/gzip"``.
            ignore_mapping_update_errors: Continue the installation even if
                updating index mappings fails.
            skip_data_stream_rollover: Do not roll over existing data streams
                when mappings change.
            space_id: Optional space ID to install the package in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``items`` array of created assets and a
            ``_meta`` object with ``install_source: "upload"`` and ``name``.

        Raises:
            BadRequestError: If the archive is invalid.
            ConflictError: If a concurrent installation is in progress.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> with open("tcp-2.3.1.zip", "rb") as f:
            ...     result = await client.fleet_epm.install_package_by_upload(
            ...         content=f.read()
            ...     )
            >>> print(result.body["_meta"]["install_source"])
            upload
        """
        params: dict[str, Any] = {}
        if ignore_mapping_update_errors is not None:
            params["ignoreMappingUpdateErrors"] = ignore_mapping_update_errors
        if skip_data_stream_rollover is not None:
            params["skipDataStreamRollover"] = skip_data_stream_rollover

        _ensure_raw_serializer(self._client, content_type)
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/epm/packages", space_id)
        return await self.perform_request(
            "POST",
            path,
            params=params if params else None,
            headers={
                "accept": "application/json",
                "content-type": content_type,
            },
            body=content,  # type: ignore[arg-type]
        )

    async def update_package(
        self,
        *,
        pkg_name: str,
        pkg_version: str | None = None,
        keep_policies_up_to_date: bool | None = None,
        namespace_customization_enabled_for: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update package settings.

        ``PUT /api/fleet/epm/packages/{pkgName}`` or
        ``PUT /api/fleet/epm/packages/{pkgName}/{pkgVersion}``

        Updates settings of an installed package, such as whether its package
        policies should be automatically kept up to date.

        Args:
            pkg_name: Name of the installed package.
            pkg_version: Version of the installed package. Optional; the
                installed package is targeted either way.
            keep_policies_up_to_date: Automatically upgrade the package's
                policies when the package is upgraded.
            namespace_customization_enabled_for: Namespaces for which
                namespace-level customization is enabled on this package.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``item`` object describing the updated
            package.

        Raises:
            BadRequestError: If the body is invalid or the package is not
                installed.
            NotFoundError: If the package does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.fleet_epm.update_package(
            ...     pkg_name="tcp", keep_policies_up_to_date=False
            ... )
            >>> print(updated.body["item"]["keepPoliciesUpToDate"])
            False
        """
        body: dict[str, Any] = {}
        if keep_policies_up_to_date is not None:
            body["keepPoliciesUpToDate"] = keep_policies_up_to_date
        if namespace_customization_enabled_for is not None:
            body["namespace_customization_enabled_for"] = (
                namespace_customization_enabled_for
            )

        base_path = f"/api/fleet/epm/packages/{_quote(pkg_name)}"
        if pkg_version is not None:
            base_path = f"{base_path}/{_quote(pkg_version)}"

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(base_path, space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def uninstall_package(
        self,
        *,
        pkg_name: str,
        pkg_version: str | None = None,
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete (uninstall) a package.

        ``DELETE /api/fleet/epm/packages/{pkgName}`` or
        ``DELETE /api/fleet/epm/packages/{pkgName}/{pkgVersion}``

        Uninstalls a package, removing its Kibana and Elasticsearch assets.

        Args:
            pkg_name: Name of the package to uninstall.
            pkg_version: Version of the installed package. Optional; the
                installed package is targeted either way.
            force: Force the uninstall even if the package is in use or
                required by policies.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``items`` array of deleted assets.

        Raises:
            BadRequestError: If the package is in use and ``force`` is not
                set.
            NotFoundError: If the package is not installed.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.fleet_epm.uninstall_package(pkg_name="tcp")
            >>> print(len(result.body["items"]) >= 0)
            True
        """
        params: dict[str, Any] = {}
        if force is not None:
            params["force"] = force

        base_path = f"/api/fleet/epm/packages/{_quote(pkg_name)}"
        if pkg_version is not None:
            base_path = f"{base_path}/{_quote(pkg_version)}"

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(base_path, space_id)
        return await self.perform_request(
            "DELETE",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    async def rollback_package(
        self,
        *,
        pkg_name: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Rollback a package to its previous version.

        ``POST /api/fleet/epm/packages/{pkgName}/rollback``

        Rolls an upgraded package back to the previously installed version.
        Requires that the package was previously upgraded on this Kibana so a
        previous version is known.

        Args:
            pkg_name: Name of the installed package to roll back.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``version`` (the version rolled back to)
            and ``success``.

        Raises:
            BadRequestError: If there is no previous version to roll back to.
            NotFoundError: If the package is not installed.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.fleet_epm.rollback_package(pkg_name="tcp")
            >>> print(result.body["success"])
            True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/epm/packages/{_quote(pkg_name)}/rollback", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def review_upgrade(
        self,
        *,
        pkg_name: str,
        action: str,
        target_version: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Review a pending policy upgrade for a package with deprecations.

        ``POST /api/fleet/epm/packages/{pkgName}/review_upgrade``

        Records the review decision (accept/decline/pending) for a pending
        package policy upgrade that contains deprecated configuration.

        Args:
            pkg_name: Name of the package with a pending upgrade review.
            action: Review decision: ``"accept"``, ``"decline"`` or
                ``"pending"``.
            target_version: The package version the pending upgrade targets.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse describing the review result.

        Raises:
            NotFoundError: If there is no pending upgrade review for the
                package/version (message: ``"No pending upgrade review for
                <pkg>@<version>"``).
            BadRequestError: If the body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.fleet_epm.review_upgrade(
            ...     pkg_name="tcp", action="accept", target_version="2.3.1"
            ... )
        """
        body: dict[str, Any] = {
            "action": action,
            "target_version": target_version,
        }

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/epm/packages/{_quote(pkg_name)}/review_upgrade", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    async def bulk_install_packages(
        self,
        *,
        packages: list[str | dict[str, Any]],
        force: bool | None = None,
        prerelease: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk install packages.

        ``POST /api/fleet/epm/packages/_bulk``

        Installs multiple packages from the Elastic Package Registry in one
        request. Unlike the other bulk package operations this endpoint is
        synchronous: the result for every package is in the response.

        Args:
            packages: Packages to install. Each entry is either a package
                name string (latest version) or a dict with ``name`` and
                ``version`` (and optional ``prerelease``).
            force: Force installation of the packages.
            prerelease: Whether prerelease versions may be selected as latest
                versions.
            space_id: Optional space ID to install the packages in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``items`` array holding a success or
            error result per package.

        Raises:
            BadRequestError: If the body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.fleet_epm.bulk_install_packages(
            ...     packages=["tcp", {"name": "udp", "version": "2.5.1"}]
            ... )
            >>> print([i["name"] for i in result.body["items"]])
            ['tcp', 'udp']
        """
        params: dict[str, Any] = {}
        if prerelease is not None:
            params["prerelease"] = prerelease

        body: dict[str, Any] = {"packages": packages}
        if force is not None:
            body["force"] = force

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/epm/packages/_bulk", space_id)
        return await self.perform_request(
            "POST",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
            body=body,
        )

    async def bulk_upgrade_packages(
        self,
        *,
        packages: list[str | dict[str, Any]],
        force: bool | None = None,
        prerelease: bool | None = None,
        upgrade_package_policies: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk upgrade packages.

        ``POST /api/fleet/epm/packages/_bulk_upgrade``

        Starts an asynchronous bulk upgrade of installed packages. The
        response contains a ``taskId``; poll
        :meth:`get_bulk_upgrade_status` for progress and results.

        Args:
            packages: Packages to upgrade. Each entry is either a package
                name string or a dict with ``name`` and optional ``version``
                (defaults to the latest available version).
            force: Force the upgrades.
            prerelease: Whether prerelease versions may be upgrade targets.
            upgrade_package_policies: Also upgrade the packages' package
                policies.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the ``taskId`` of the upgrade task.

        Raises:
            BadRequestError: If the body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> started = await client.fleet_epm.bulk_upgrade_packages(packages=["tcp"])
            >>> task_id = started.body["taskId"]
        """
        body: dict[str, Any] = {"packages": _normalize_name_items(packages)}
        if force is not None:
            body["force"] = force
        if prerelease is not None:
            body["prerelease"] = prerelease
        if upgrade_package_policies is not None:
            body["upgrade_package_policies"] = upgrade_package_policies

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/epm/packages/_bulk_upgrade", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_bulk_upgrade_status(
        self,
        *,
        task_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get bulk upgrade packages details.

        ``GET /api/fleet/epm/packages/_bulk_upgrade/{taskId}``

        Retrieves the status of an asynchronous bulk upgrade started with
        :meth:`bulk_upgrade_packages`.

        Args:
            task_id: The ``taskId`` returned by the bulk upgrade request.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``status`` (``"pending"``, ``"success"``
            or ``"failed"``), per-package ``results`` when finished, and an
            ``error`` object on failure.

        Raises:
            NotFoundError: If no bulk upgrade task exists for the ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> status = await client.fleet_epm.get_bulk_upgrade_status(task_id=task_id)
            >>> print(status.body["status"])
            success
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/epm/packages/_bulk_upgrade/{_quote(task_id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def bulk_uninstall_packages(
        self,
        *,
        packages: list[dict[str, Any]],
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk uninstall packages.

        ``POST /api/fleet/epm/packages/_bulk_uninstall``

        Starts an asynchronous bulk uninstall of installed packages. The
        response contains a ``taskId``; poll
        :meth:`get_bulk_uninstall_status` for progress and results.

        Args:
            packages: Packages to uninstall. Each entry is a dict with
                ``name`` and ``version`` (both required by the API).
            force: Force the uninstalls even if packages are in use.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the ``taskId`` of the uninstall task.

        Raises:
            BadRequestError: If the body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> started = await client.fleet_epm.bulk_uninstall_packages(
            ...     packages=[{"name": "tcp", "version": "2.3.1"}]
            ... )
            >>> task_id = started.body["taskId"]
        """
        body: dict[str, Any] = {"packages": packages}
        if force is not None:
            body["force"] = force

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/fleet/epm/packages/_bulk_uninstall", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_bulk_uninstall_status(
        self,
        *,
        task_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get bulk uninstall packages details.

        ``GET /api/fleet/epm/packages/_bulk_uninstall/{taskId}``

        Retrieves the status of an asynchronous bulk uninstall started with
        :meth:`bulk_uninstall_packages`.

        Args:
            task_id: The ``taskId`` returned by the bulk uninstall request.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``status`` (``"pending"``, ``"success"``
            or ``"failed"``), per-package ``results`` when finished, and an
            ``error`` object on failure.

        Raises:
            NotFoundError: If no bulk uninstall task exists for the ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> status = await client.fleet_epm.get_bulk_uninstall_status(task_id=task_id)
            >>> print(status.body["status"])
            success
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/epm/packages/_bulk_uninstall/{_quote(task_id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def bulk_rollback_packages(
        self,
        *,
        packages: list[str | dict[str, Any]],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk rollback packages.

        ``POST /api/fleet/epm/packages/_bulk_rollback``

        Starts an asynchronous bulk rollback of upgraded packages to their
        previous versions. The response contains a ``taskId``; poll
        :meth:`get_bulk_rollback_status` for progress and results.

        Args:
            packages: Packages to roll back. Each entry is either a package
                name string or a dict with ``name``.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the ``taskId`` of the rollback task.

        Raises:
            BadRequestError: If the body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> started = await client.fleet_epm.bulk_rollback_packages(packages=["tcp"])
            >>> task_id = started.body["taskId"]
        """
        body: dict[str, Any] = {"packages": _normalize_name_items(packages)}

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/fleet/epm/packages/_bulk_rollback", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_bulk_rollback_status(
        self,
        *,
        task_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get bulk rollback packages details.

        ``GET /api/fleet/epm/packages/_bulk_rollback/{taskId}``

        Retrieves the status of an asynchronous bulk rollback started with
        :meth:`bulk_rollback_packages`.

        Args:
            task_id: The ``taskId`` returned by the bulk rollback request.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``status`` (``"pending"``, ``"success"``
            or ``"failed"``), per-package ``results`` when finished, and an
            ``error`` object on failure.

        Raises:
            NotFoundError: If no bulk rollback task exists for the ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> status = await client.fleet_epm.get_bulk_rollback_status(task_id=task_id)
            >>> print(status.body["status"])
            success
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/epm/packages/_bulk_rollback/{_quote(task_id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    async def bulk_get_assets(
        self,
        *,
        asset_ids: list[dict[str, Any]],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk get assets.

        ``POST /api/fleet/epm/bulk_assets``

        Retrieves details (including app links) for a set of package assets
        by ID and type, e.g. the assets listed in an install response.

        Args:
            asset_ids: Assets to fetch. Each entry is a dict with ``id`` and
                ``type`` (e.g. ``{"id": "logs-tcp.generic", "type":
                "index_template"}``).
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``items`` array of asset details
            (``id``, ``type``, ``attributes``, ``appLink``).

        Raises:
            BadRequestError: If the body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> assets = await client.fleet_epm.bulk_get_assets(
            ...     asset_ids=[{"id": "logs-tcp.generic", "type": "index_template"}]
            ... )
            >>> print(assets.body["items"][0]["appLink"])
            /app/management/data/index_management/templates/logs-tcp.generic
        """
        body: dict[str, Any] = {"assetIds": asset_ids}

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/epm/bulk_assets", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def install_kibana_assets(
        self,
        *,
        pkg_name: str,
        pkg_version: str,
        force: bool | None = None,
        space_ids: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Install Kibana assets for a package.

        ``POST /api/fleet/epm/packages/{pkgName}/{pkgVersion}/kibana_assets``

        (Re-)installs the Kibana assets (dashboards, visualizations, ...) of
        an installed package, optionally into additional spaces.

        Args:
            pkg_name: Name of the installed package.
            pkg_version: Version of the installed package.
            force: Force the asset installation.
            space_ids: When provided, assets are installed in the specified
                spaces instead of the current space.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``success: true`` on success.

        Raises:
            BadRequestError: If the package is not installed.
            NotFoundError: If the package does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.fleet_epm.install_kibana_assets(
            ...     pkg_name="tcp", pkg_version="2.3.1"
            ... )
            >>> print(result.body["success"])
            True
        """
        body: dict[str, Any] = {}
        if force is not None:
            body["force"] = force
        if space_ids is not None:
            body["space_ids"] = space_ids

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/epm/packages/{_quote(pkg_name)}/{_quote(pkg_version)}"
            "/kibana_assets",
            space_id,
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body if body else None,
        )

    async def delete_kibana_assets(
        self,
        *,
        pkg_name: str,
        pkg_version: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete Kibana assets for a package.

        ``DELETE /api/fleet/epm/packages/{pkgName}/{pkgVersion}/kibana_assets``

        Removes the Kibana assets a package installed into the current space.
        Note: Kibana rejects deleting the assets from the space where the
        package itself was installed — uninstall the package instead.

        Args:
            pkg_name: Name of the installed package.
            pkg_version: Version of the installed package.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``success: true`` on success.

        Raises:
            BadRequestError: If called in the space where the package was
                installed (message: ``"Impossible to delete kibana assets
                from the space where the package was installed, you must
                uninstall the package."``).
            NotFoundError: If the package does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.fleet_epm.delete_kibana_assets(
            ...     pkg_name="tcp", pkg_version="2.3.1", space_id="other-space"
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/epm/packages/{_quote(pkg_name)}/{_quote(pkg_version)}"
            "/kibana_assets",
            space_id,
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    async def install_rule_assets(
        self,
        *,
        pkg_name: str,
        pkg_version: str,
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Install Kibana alert rules for a package.

        ``POST /api/fleet/epm/packages/{pkgName}/{pkgVersion}/rule_assets``

        Installs the alerting rule assets shipped by an installed package.

        Args:
            pkg_name: Name of the installed package.
            pkg_version: Version of the installed package.
            force: Force the rule asset installation.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``success: true`` on success.

        Raises:
            BadRequestError: If the package is not installed.
            NotFoundError: If the package does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.fleet_epm.install_rule_assets(
            ...     pkg_name="tcp", pkg_version="2.3.1"
            ... )
            >>> print(result.body["success"])
            True
        """
        body: dict[str, Any] = {}
        if force is not None:
            body["force"] = force

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/epm/packages/{_quote(pkg_name)}/{_quote(pkg_version)}"
            "/rule_assets",
            space_id,
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body if body else None,
        )

    async def delete_datastream_assets(
        self,
        *,
        pkg_name: str,
        pkg_version: str,
        package_policy_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete assets for an input package.

        ``DELETE /api/fleet/epm/packages/{pkgName}/{pkgVersion}/datastream_assets``

        Deletes the data-stream assets an input package created for a
        specific package policy.

        Args:
            pkg_name: Name of the installed input package.
            pkg_version: Version of the installed input package.
            package_policy_id: ID of the package policy whose data-stream
                assets should be deleted.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``success: true`` on success.

        Raises:
            NotFoundError: If the package policy does not exist (message:
                ``"Package policy with id <id> not found"``).
            BadRequestError: If the package is not an installed input
                package.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.fleet_epm.delete_datastream_assets(
            ...     pkg_name="tcp", pkg_version="2.3.1",
            ...     package_policy_id="d5b1e4b0-...",
            ... )
        """
        params: dict[str, Any] = {"packagePolicyId": package_policy_id}

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/epm/packages/{_quote(pkg_name)}/{_quote(pkg_version)}"
            "/datastream_assets",
            space_id,
        )
        return await self.perform_request(
            "DELETE",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def authorize_transforms(
        self,
        *,
        pkg_name: str,
        pkg_version: str,
        transforms: list[str | dict[str, Any]],
        prerelease: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Authorize transforms.

        ``POST /api/fleet/epm/packages/{pkgName}/{pkgVersion}/transforms/authorize``

        Re-authorizes the Elasticsearch transforms installed by a package so
        they run with the current user's permissions.

        Args:
            pkg_name: Name of the installed package.
            pkg_version: Version of the installed package.
            transforms: Transforms to authorize. Each entry is either a
                transform ID string or a dict with ``transformId``.
            prerelease: Whether prerelease package versions are considered.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ApiResponse whose body is a list with one result per transform
            (``transformId``, ``success``, optional ``error``).

        Raises:
            BadRequestError: If the body is invalid.
            NotFoundError: If the package does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.fleet_epm.authorize_transforms(
            ...     pkg_name="ti_util", pkg_version="1.1.0",
            ...     transforms=["logs-ti_util.latest_ioc-default-1.1.0"],
            ... )
        """
        normalized: list[dict[str, Any]] = []
        for transform in transforms:
            if isinstance(transform, str):
                normalized.append({"transformId": transform})
            else:
                normalized.append(transform)

        params: dict[str, Any] = {}
        if prerelease is not None:
            params["prerelease"] = prerelease

        body: dict[str, Any] = {"transforms": normalized}

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/epm/packages/{_quote(pkg_name)}/{_quote(pkg_version)}"
            "/transforms/authorize",
            space_id,
        )
        return await self.perform_request(
            "POST",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
            body=body,
        )

    # ------------------------------------------------------------------
    # Custom integrations
    # ------------------------------------------------------------------

    async def create_custom_integration(
        self,
        *,
        integration_name: str,
        datasets: list[dict[str, Any]],
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a custom integration.

        ``POST /api/fleet/epm/custom_integrations``

        Creates and installs a custom integration package with the given
        datasets (index templates, ingest pipelines and component templates
        are generated automatically).

        Args:
            integration_name: Name of the custom integration package.
            datasets: Datasets the integration ships. Each entry is a dict
                with ``name`` and ``type`` (one of ``"logs"``, ``"metrics"``,
                ``"traces"``, ``"synthetics"``, ``"profiling"``). Maximum of
                10 datasets.
            force: Force creation even if the integration already exists.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``items`` array of created assets and a
            ``_meta`` object with ``install_source: "custom"``.

        Raises:
            BadRequestError: If the body is invalid.
            ConflictError: If the integration already exists and ``force`` is
                not set.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = await client.fleet_epm.create_custom_integration(
            ...     integration_name="my_custom_app",
            ...     datasets=[{"name": "my_custom_app.access", "type": "logs"}],
            ... )
            >>> print(created.body["_meta"]["install_source"])
            custom
        """
        body: dict[str, Any] = {
            "integrationName": integration_name,
            "datasets": datasets,
        }
        if force is not None:
            body["force"] = force

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/epm/custom_integrations", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def update_custom_integration(
        self,
        *,
        pkg_name: str,
        read_me_data: str,
        categories: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a custom integration.

        ``PUT /api/fleet/epm/custom_integrations/{pkgName}``

        Updates a previously created custom integration (its README and
        categories), bumping the integration's patch version.

        Args:
            pkg_name: Name of the custom integration package.
            read_me_data: README (Markdown) content for the integration.
                Required by the API.
            categories: Categories to assign to the integration.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the integration ``id`` and a ``result``
            object containing the new ``version`` and ``status``.

        Raises:
            BadRequestError: If ``read_me_data`` is missing or the body is
                otherwise invalid.
            NotFoundError: If the custom integration does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.fleet_epm.update_custom_integration(
            ...     pkg_name="my_custom_app",
            ...     read_me_data="# My custom app",
            ...     categories=["custom"],
            ... )
            >>> print(updated.body["result"]["version"])
            1.0.1
        """
        body: dict[str, Any] = {"readMeData": read_me_data}
        if categories is not None:
            body["categories"] = categories

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/epm/custom_integrations/{_quote(pkg_name)}", space_id
        )
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    # ------------------------------------------------------------------
    # Data streams and templates
    # ------------------------------------------------------------------

    async def get_data_streams(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get Fleet data streams.

        ``GET /api/fleet/data_streams``

        Lists the data streams created by Fleet-managed integrations,
        including their size, last-activity timestamp and associated
        dashboards.

        Args:
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with a ``data_streams`` array (each entry has
            ``index``, ``dataset``, ``namespace``, ``type``, ``package``,
            ``size_in_bytes``, ``dashboards``, ...).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> streams = await client.fleet_epm.get_data_streams()
            >>> print(type(streams.body["data_streams"]))
            <class 'list'>
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/data_streams", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def find_data_streams(
        self,
        *,
        type: str | None = None,
        dataset_query: str | None = None,
        sort_order: str | None = None,
        uncategorised_only: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Find EPM data streams.

        ``GET /api/fleet/epm/data_streams``

        Lists existing data-stream names known to the Elastic Package
        Manager, filtered by type and dataset query (used e.g. when creating
        custom integrations).

        Args:
            type: Only include data streams of this type. One of ``"logs"``,
                ``"metrics"``, ``"traces"``, ``"synthetics"`` or
                ``"profiling"``.
            dataset_query: Filter data streams by dataset name substring.
            sort_order: Sort order for the results: ``"asc"`` or ``"desc"``.
            uncategorised_only: Only include data streams that do not belong
                to any installed package.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``items`` array of data streams (each
            with a ``name``).

        Raises:
            BadRequestError: If the query parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> streams = await client.fleet_epm.find_data_streams(type="logs")
            >>> print(streams.body["items"][0]["name"])
            logs-elastic_agent-default
        """
        params: dict[str, Any] = {}
        if type is not None:
            params["type"] = type
        if dataset_query is not None:
            params["datasetQuery"] = dataset_query
        if sort_order is not None:
            params["sortOrder"] = sort_order
        if uncategorised_only is not None:
            params["uncategorisedOnly"] = uncategorised_only

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/fleet/epm/data_streams", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    async def get_inputs_template(
        self,
        *,
        pkg_name: str,
        pkg_version: str,
        format: str | None = None,
        prerelease: bool | None = None,
        ignore_unverified: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an inputs template.

        ``GET /api/fleet/epm/templates/{pkgName}/{pkgVersion}/inputs``

        Retrieves the agent inputs template of a package, as JSON or YAML —
        useful for standalone-agent configuration.

        Args:
            pkg_name: Name of the package.
            pkg_version: Version of the package.
            format: Response format: ``"json"``, ``"yml"`` or ``"yaml"``.
                Defaults to YAML on the server.
            prerelease: Whether prerelease package versions are considered.
            ignore_unverified: Whether to use the package even if its
                signature cannot be verified.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ApiResponse whose body is an object with an ``inputs`` array for
            ``format="json"``, or the raw YAML string otherwise.

        Raises:
            NotFoundError: If the package does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> template = await client.fleet_epm.get_inputs_template(
            ...     pkg_name="tcp", pkg_version="2.3.1", format="json"
            ... )
            >>> print(template.body["inputs"][0]["type"])
            tcp
        """
        params: dict[str, Any] = {}
        if format is not None:
            params["format"] = format
        if prerelease is not None:
            params["prerelease"] = prerelease
        if ignore_unverified is not None:
            params["ignoreUnverified"] = ignore_unverified

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/fleet/epm/templates/{_quote(pkg_name)}/{_quote(pkg_version)}"
            "/inputs",
            space_id,
        )
        return await self.perform_request(
            "GET",
            path,
            params=params if params else None,
        )
