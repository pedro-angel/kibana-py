"""Kibana Security (roles and sessions) API client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._sync.client import Kibana


class SecurityClient(NamespaceClient):
    """Client for the Kibana Security (roles and sessions) API.

    Provides role management (create-or-update, get, query, bulk update and
    delete Kibana roles, including their Elasticsearch and Kibana privilege
    definitions) and user-session invalidation.

    The Security API is not space-scoped: roles and sessions are global to
    the Kibana instance. Space-level access is granted through the
    ``kibana`` privilege entries of a role (each entry lists the ``spaces``
    it applies to).

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create or update a role
        >>> client.security.create_or_update_role(
        ...     name="my-role",
        ...     elasticsearch={
        ...         "cluster": ["monitor"],
        ...         "indices": [{"names": ["logs-*"], "privileges": ["read"]}],
        ...     },
        ...     kibana=[{"base": ["read"], "spaces": ["default"]}],
        ... )
        >>>
        >>> # Retrieve it
        >>> role = client.security.get_role(name="my-role")
        >>> print(role.body["name"])
        my-role
    """

    def __init__(self, client: Kibana) -> None:
        """Initialize the SecurityClient.

        Args:
            client: The parent Kibana client instance to delegate requests to.

        Example:
            >>> security_client = SecurityClient(kibana_client)
        """
        super().__init__(client)

    def get_all_roles(
        self,
        *,
        replace_deprecated_privileges: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get all Kibana roles.

        Retrieves every role, including reserved and system roles, with
        their Elasticsearch and Kibana privilege definitions.

        Args:
            replace_deprecated_privileges: If ``True`` and the response
                contains any privileges that are associated with deprecated
                features, they are omitted in favor of details about the
                appropriate replacement feature privileges.

        Returns:
            ObjectApiResponse containing a list of role objects. Each role
            has ``name``, ``description``, ``metadata``, ``elasticsearch``
            (cluster/indices/run_as privileges), ``kibana`` (base/feature
            privileges per space) and ``transient_metadata``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to read roles.
            TransportError: If unable to connect to Kibana.

        Example:
            >>> roles = client.security.get_all_roles()
            >>> for role in roles.body:
            ...     print(role["name"])
            superuser
            my-role
        """
        params: dict[str, Any] = {}
        if replace_deprecated_privileges is not None:
            params["replaceDeprecatedPrivileges"] = replace_deprecated_privileges
        return self.perform_request(
            "GET",
            "/api/security/role",
            params=params or None,
            headers={"accept": "application/json"},
        )

    def get_role(
        self,
        *,
        name: str,
        replace_deprecated_privileges: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a Kibana role by name.

        Args:
            name: The role name (required).
            replace_deprecated_privileges: If ``True`` and the response
                contains any privileges that are associated with deprecated
                features, they are omitted in favor of details about the
                appropriate replacement feature privileges.

        Returns:
            ObjectApiResponse containing the role object with ``name``,
            ``description``, ``metadata``, ``elasticsearch`` and ``kibana``
            privilege definitions.

        Raises:
            ValueError: If ``name`` is empty.
            NotFoundError: If the role does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to read roles.

        Example:
            >>> role = client.security.get_role(name="my-role")
            >>> print(role.body["elasticsearch"]["cluster"])
            ['monitor']
        """
        if not name:
            raise ValueError("Parameter 'name' is required")
        params: dict[str, Any] = {}
        if replace_deprecated_privileges is not None:
            params["replaceDeprecatedPrivileges"] = replace_deprecated_privileges
        return self.perform_request(
            "GET",
            f"/api/security/role/{_quote(name)}",
            params=params or None,
            headers={"accept": "application/json"},
        )

    def create_or_update_role(
        self,
        *,
        name: str,
        elasticsearch: dict[str, Any],
        description: str | None = None,
        kibana: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        create_only: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a new Kibana role or update an existing one.

        Args:
            name: The role name. Must be 1-1024 characters (required).
            elasticsearch: Elasticsearch privileges for the role (required).
                Supported keys:

                - ``cluster``: list of cluster privilege names.
                - ``indices``: list of index privilege objects, each with
                  ``names`` and ``privileges`` (and optionally
                  ``field_security``, ``query``,
                  ``allow_restricted_indices``).
                - ``remote_cluster``: list of objects with ``clusters``
                  and ``privileges`` for remote clusters.
                - ``remote_indices``: list of remote index privilege
                  objects (like ``indices`` plus ``clusters``).
                - ``run_as``: list of usernames the role can impersonate.
            description: Optional description for the role (max 2048 chars).
            kibana: Kibana privileges for the role. A list of objects, each
                with ``base`` (base privileges such as ``["all"]`` or
                ``["read"]``), ``feature`` (a mapping of feature ID to a list
                of feature privileges; mutually exclusive with a non-empty
                ``base``) and ``spaces`` (the space IDs the entry applies to,
                or ``["*"]`` for all spaces).
            metadata: Optional arbitrary metadata to store with the role.
            create_only: If ``True``, the request fails if a role with the
                given name already exists (create-only semantics). Defaults
                to ``False`` on the server (create or update).

        Returns:
            ObjectApiResponse with an empty body (the server returns
            ``204 No Content`` on success).

        Raises:
            ValueError: If ``name`` is empty.
            BadRequestError: If the privilege definitions are invalid.
            ConflictError: If ``create_only=True`` and the role already
                exists.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to manage
                roles.

        Example:
            >>> client.security.create_or_update_role(
            ...     name="log-reader",
            ...     description="Read-only access to logs",
            ...     elasticsearch={
            ...         "cluster": [],
            ...         "indices": [
            ...             {"names": ["logs-*"], "privileges": ["read"]}
            ...         ],
            ...     },
            ...     kibana=[{"base": ["read"], "spaces": ["*"]}],
            ...     metadata={"version": 1},
            ... )
        """
        if not name:
            raise ValueError("Parameter 'name' is required")
        params: dict[str, Any] = {}
        if create_only is not None:
            params["createOnly"] = create_only
        body: dict[str, Any] = {"elasticsearch": elasticsearch}
        if description is not None:
            body["description"] = description
        if kibana is not None:
            body["kibana"] = kibana
        if metadata is not None:
            body["metadata"] = metadata
        return self.perform_request(
            "PUT",
            f"/api/security/role/{_quote(name)}",
            params=params or None,
            body=body,
        )

    def delete_role(self, *, name: str) -> ObjectApiResponse[Any]:
        """Delete a Kibana role by name.

        Reserved roles cannot be deleted.

        Args:
            name: The role name (required).

        Returns:
            ObjectApiResponse with an empty body (the server returns
            ``204 No Content`` on success).

        Raises:
            ValueError: If ``name`` is empty.
            NotFoundError: If the role does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to manage
                roles.

        Example:
            >>> client.security.delete_role(name="log-reader")
        """
        if not name:
            raise ValueError("Parameter 'name' is required")
        return self.perform_request(
            "DELETE",
            f"/api/security/role/{_quote(name)}",
        )

    def bulk_create_or_update_roles(
        self,
        *,
        roles: dict[str, dict[str, Any]],
    ) -> ObjectApiResponse[Any]:
        """Create new Kibana roles or update existing ones in bulk.

        Args:
            roles: A mapping of role name to role definition (required).
                Each definition accepts the same keys as
                :meth:`create_or_update_role`: ``elasticsearch`` (required by
                the server), ``kibana``, ``description`` and ``metadata``.

        Returns:
            ObjectApiResponse summarizing the outcome per role, with keys
            such as ``created``, ``updated`` and ``errors``.

        Raises:
            BadRequestError: If a role definition is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to manage
                roles.

        Example:
            >>> result = client.security.bulk_create_or_update_roles(
            ...     roles={
            ...         "role-a": {"elasticsearch": {"cluster": ["monitor"]}},
            ...         "role-b": {
            ...             "elasticsearch": {},
            ...             "kibana": [{"base": ["read"], "spaces": ["*"]}],
            ...         },
            ...     }
            ... )
            >>> print(result.body.get("created"))
            ['role-a', 'role-b']
        """
        return self.perform_request(
            "POST",
            "/api/security/roles",
            body={"roles": roles},
        )

    def query_roles(
        self,
        *,
        query: str | None = None,
        from_: int | None = None,
        size: int | None = None,
        sort: dict[str, Any] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> ObjectApiResponse[Any]:
        """Query Kibana roles with optional filters, paging and sorting.

        Args:
            query: Free-text query string used to match role names.
            from_: Zero-based offset of the first role to return (paging).
            size: Maximum number of roles to return (paging).
            sort: Sort definition with required keys ``field`` and
                ``direction`` (``"asc"`` or ``"desc"``), e.g.
                ``{"field": "name", "direction": "asc"}``.
            filters: Additional filters. Supports ``showReservedRoles``
                (bool) to include or exclude reserved roles.

        Returns:
            ObjectApiResponse containing the matching roles, typically with
            ``roles`` (the page of role objects), ``count`` and ``total``.

        Raises:
            BadRequestError: If the query payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to read roles.

        Example:
            >>> result = client.security.query_roles(
            ...     query="kbnpy",
            ...     from_=0,
            ...     size=10,
            ...     sort={"field": "name", "direction": "asc"},
            ...     filters={"showReservedRoles": False},
            ... )
            >>> print(result.body["total"])
            2
        """
        body: dict[str, Any] = {}
        if query is not None:
            body["query"] = query
        if from_ is not None:
            body["from"] = from_
        if size is not None:
            body["size"] = size
        if sort is not None:
            body["sort"] = sort
        if filters is not None:
            body["filters"] = filters
        return self.perform_request(
            "POST",
            "/api/security/role/_query",
            body=body,
        )

    def invalidate_sessions(
        self,
        *,
        match: str,
        query: dict[str, Any] | None = None,
    ) -> ObjectApiResponse[Any]:
        """Invalidate user sessions that match a query.

        To use this API, you must be a superuser.

        Warning:
            Calling this with ``match="all"`` logs out every user of the
            Kibana instance. Prefer ``match="query"`` with a narrow
            ``query`` to target specific sessions.

        Args:
            match: How Kibana determines which sessions to invalidate
                (required). ``"all"`` invalidates every existing session;
                ``"query"`` invalidates only the sessions that match
                ``query``.
            query: The query used to match sessions when ``match`` is
                ``"query"``. An object with a required ``provider``
                (``{"type": ..., "name": ...}``, ``type`` required — e.g.
                ``basic``, ``token``, ``saml``, ``oidc``, ``kerberos`` or
                ``pki``) and an optional ``username``.

        Returns:
            ObjectApiResponse with the number of successfully invalidated
            sessions in ``total``.

        Raises:
            BadRequestError: If the payload is invalid (e.g. ``match`` is
                not ``"all"`` or ``"query"``).
            AuthenticationException: If authentication fails.
            AuthorizationException: If the calling user is not a superuser.

        Example:
            >>> result = client.security.invalidate_sessions(
            ...     match="query",
            ...     query={
            ...         "provider": {"type": "basic"},
            ...         "username": "some-user",
            ...     },
            ... )
            >>> print(result.body["total"])
            0
        """
        body: dict[str, Any] = {"match": match}
        if query is not None:
            body["query"] = query
        return self.perform_request(
            "POST",
            "/api/security/session/_invalidate",
            body=body,
        )
