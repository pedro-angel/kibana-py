"""Async Kibana Spaces API client."""

from __future__ import annotations

from typing import Any

from elastic_transport import ObjectApiResponse

from .utils import AsyncNamespaceClient, _quote


class AsyncSpacesClient(AsyncNamespaceClient):
    """Async client for Kibana Spaces API.

    Spaces allow you to organize your Kibana objects (dashboards, visualizations,
    index patterns, etc.) into separate, isolated areas. Each space has its own
    set of saved objects and can be used to implement multi-tenancy, enabling
    different teams or projects to work independently within the same Kibana instance.

    Key features of Spaces:
        - Isolated saved objects per space
        - Customizable appearance (color, initials, custom avatar image)
        - Solution views ("es", "oblt", "security", "classic") introduced in 9.x
        - Feature-level access control (disable specific features per space)
        - URL-based space selection (/s/space-id/app/...)
        - Copying and sharing saved objects between spaces
        - Default space always exists and cannot be deleted

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a space for the marketing team
        >>> space = await client.spaces.create(
        ...     id="marketing",
        ...     name="Marketing Team",
        ...     description="Space for marketing analytics",
        ...     color="#FF6B6B",
        ...     initials="MK",
        ...     solution="classic",
        ... )
        >>>
        >>> # List all spaces
        >>> spaces = await client.spaces.get_all()
        >>> for space in spaces.body:
        ...     print(f"{space['name']} ({space['id']})")
        >>>
        >>> # Work within a specific space
        >>> marketing_client = client.space("marketing")
        >>> connectors = await marketing_client.actions.get_all()
    """

    async def create(
        self,
        *,
        id: str,
        name: str,
        description: str | None = None,
        color: str | None = None,
        initials: str | None = None,
        image_url: str | None = None,
        disabled_features: list[str] | None = None,
        solution: str | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a new space.

        Creates a new Kibana space with the specified configuration. The space ID
        must be unique and URL-friendly (lowercase alphanumeric, hyphens and
        underscores only) and cannot be changed after creation.

        Args:
            id: Unique identifier for the space. Limited to lowercase
                alphanumeric, underscore, and hyphen characters (a-z, 0-9, _, -).
                Examples: "marketing", "team-a", "prod_env".
            name: Display name for the space. Shown in the Kibana UI and can
                contain any characters.
            description: Optional description explaining the purpose of the
                space. Displayed in the space selector.
            color: Optional hexadecimal color code for the space avatar (e.g.,
                "#FF0000"). By default, the color is generated from the name.
            initials: Optional one or two characters shown in the space avatar.
                If not provided, Kibana generates them from the name.
            image_url: Optional data-URL encoded image to display in the space
                avatar instead of initials. For best results use a 64x64 image.
                Sent as the ``imageUrl`` body field.
            disabled_features: Optional list of Kibana feature IDs to turn off
                in this space (e.g., "discover", "dashboard", "canvas", "maps",
                "ml", "apm", "slo", "uptime").
            solution: Optional solution view for the space. One of ``"es"``
                (Elasticsearch), ``"oblt"`` (Observability), ``"security"``
                (Security), or ``"classic"``. Controls which navigation and
                features the space presents.

        Returns:
            ObjectApiResponse containing the created space details including id,
            name, description, color, initials, disabledFeatures, and solution.

        Raises:
            ValueError: If required parameters (id, name) are empty.
            BadRequestError: If the space ID format or solution value is invalid.
            ConflictError: If a space with the same ID already exists.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to create spaces.

        Example:
            >>> # Create a basic space
            >>> space = await client.spaces.create(id="engineering", name="Engineering")
            >>>
            >>> # Create an Observability solution space with full configuration
            >>> space = await client.spaces.create(
            ...     id="oblt-team",
            ...     name="Observability Team",
            ...     description="O11y workspace",
            ...     color="#FF6B6B",
            ...     initials="OT",
            ...     disabled_features=["ml"],
            ...     solution="oblt",
            ... )
            >>> print(space.body["solution"])
            oblt
        """
        if not id:
            raise ValueError("Parameter 'id' is required")
        if not name:
            raise ValueError("Parameter 'name' is required")

        body: dict[str, Any] = {
            "id": id,
            "name": name,
        }

        if description is not None:
            body["description"] = description
        if color is not None:
            body["color"] = color
        if initials is not None:
            body["initials"] = initials
        if image_url is not None:
            body["imageUrl"] = image_url
        if disabled_features is not None:
            body["disabledFeatures"] = disabled_features
        if solution is not None:
            body["solution"] = solution

        return await self.perform_request(
            "POST",
            "/api/spaces/space",
            body=body,
        )

    async def get(
        self,
        *,
        id: str,
    ) -> ObjectApiResponse[Any]:
        """Get a space by ID.

        Retrieves detailed information about a specific space including its
        configuration, disabled features, and solution view.

        Args:
            id: The space ID to retrieve (e.g., "default", "marketing").

        Returns:
            ObjectApiResponse containing the space details including id, name,
            description, color, initials, disabledFeatures, and solution.

        Raises:
            ValueError: If the id parameter is empty.
            NotFoundError: If the space does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to view the space.

        Example:
            >>> space = await client.spaces.get(id="marketing")
            >>> print(space.body["name"])
            Marketing Team
            >>> print(space.body.get("disabledFeatures", []))
            ['ml', 'apm']
        """
        if not id:
            raise ValueError("Parameter 'id' is required")

        return await self.perform_request(
            "GET",
            f"/api/spaces/space/{_quote(id)}",
        )

    async def get_all(
        self,
        *,
        purpose: str | None = None,
        include_authorized_purposes: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get all spaces.

        Retrieves a list of all spaces in the Kibana instance that the
        authenticated user has access to view, optionally filtered by the
        purpose the user is authorized for.

        Args:
            purpose: Optional purpose to filter spaces by user authorization.
                One of ``"any"``, ``"copySavedObjectsIntoSpace"``, or
                ``"shareSavedObjectsIntoSpace"``. Cannot be combined with
                ``include_authorized_purposes=True`` (Kibana rejects the
                combination with a 400 error).
            include_authorized_purposes: When True, each returned space includes
                an ``authorizedPurposes`` map describing which purposes the
                current user is authorized for. Must be False (or omitted) when
                ``purpose`` is specified.

        Returns:
            ObjectApiResponse containing a list of all spaces. Each space
            includes id, name, description, color, initials, disabledFeatures,
            solution, and (if requested) authorizedPurposes.

        Raises:
            BadRequestError: If ``purpose`` is combined with
                ``include_authorized_purposes=True`` or the purpose is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to list spaces.

        Example:
            >>> spaces = await client.spaces.get_all(include_authorized_purposes=True)
            >>> for space in spaces.body:
            ...     print(space["id"], space.get("authorizedPurposes"))
            >>>
            >>> # Only spaces the user may copy saved objects into
            >>> spaces = await client.spaces.get_all(purpose="copySavedObjectsIntoSpace")
        """
        params: dict[str, Any] = {}
        if purpose is not None:
            params["purpose"] = purpose
        if include_authorized_purposes is not None:
            params["include_authorized_purposes"] = include_authorized_purposes

        return await self.perform_request(
            "GET",
            "/api/spaces/space",
            params=params if params else None,
        )

    async def update(
        self,
        *,
        id: str,
        name: str,
        description: str | None = None,
        color: str | None = None,
        initials: str | None = None,
        image_url: str | None = None,
        disabled_features: list[str] | None = None,
        solution: str | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a space.

        Sends an HTTP PUT that replaces the space configuration: Kibana
        requires both ``id`` and ``name`` in the request body (calls that omit
        the name are rejected with a 400 error). On Kibana 9.4.3, body fields
        with schema defaults are reset when omitted (notably
        ``disabled_features`` resets to ``[]``), while other omitted optional
        fields (description, color, initials, image_url, solution) are
        preserved. For predictable results treat this as a full replace:
        ``get()`` the space first and re-send every field you want to keep.
        The space ID itself cannot be changed after creation.

        Args:
            id: The space ID to update (cannot be changed).
            name: Display name for the space (required by the PUT body schema,
                so the current name must be re-sent even if unchanged).
            description: Description for the space. Pass an empty string to
                clear an existing description; omitting it preserves it.
            color: Hexadecimal color code for the space avatar (e.g., "#00FF00").
            initials: One or two characters shown in the space avatar.
            image_url: Data-URL encoded image for the space avatar. Sent as the
                ``imageUrl`` body field.
            disabled_features: List of feature IDs turned off in the space.
                Replaces the entire list; omitting it re-enables all features.
            solution: Solution view for the space. One of ``"es"``, ``"oblt"``,
                ``"security"``, or ``"classic"``.

        Returns:
            ObjectApiResponse containing the updated space details.

        Raises:
            ValueError: If the id or name parameter is empty.
            NotFoundError: If the space does not exist.
            BadRequestError: If the update parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to update the space.

        Example:
            >>> # Read-modify-write to change only the color
            >>> current = (await client.spaces.get(id="marketing")).body
            >>> space = await client.spaces.update(
            ...     id="marketing",
            ...     name=current["name"],
            ...     description=current.get("description"),
            ...     color="#00FF00",
            ...     disabled_features=current.get("disabledFeatures"),
            ... )
        """
        if not id:
            raise ValueError("Parameter 'id' is required")
        if not name:
            raise ValueError("Parameter 'name' is required")

        # Kibana Spaces API requires both id and name in the PUT body
        body: dict[str, Any] = {
            "id": id,
            "name": name,
        }

        if description is not None:
            body["description"] = description
        if color is not None:
            body["color"] = color
        if initials is not None:
            body["initials"] = initials
        if image_url is not None:
            body["imageUrl"] = image_url
        if disabled_features is not None:
            body["disabledFeatures"] = disabled_features
        if solution is not None:
            body["solution"] = solution

        return await self.perform_request(
            "PUT",
            f"/api/spaces/space/{_quote(id)}",
            body=body,
        )

    async def delete(
        self,
        *,
        id: str,
    ) -> ObjectApiResponse[Any]:
        """Delete a space.

        Permanently deletes a space and all its associated saved objects
        (dashboards, visualizations, data views, etc.). This operation
        cannot be undone.

        Warning:
            Deleting a space permanently deletes every saved object within
            that space. The default space cannot be deleted.

        Args:
            id: The space ID to delete. Cannot be "default".

        Returns:
            ObjectApiResponse, empty (HTTP 204) for successful deletion.

        Raises:
            ValueError: If the id parameter is empty.
            NotFoundError: If the space does not exist.
            BadRequestError: If attempting to delete a reserved space.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to delete the space.

        Example:
            >>> await client.spaces.delete(id="old-project")
        """
        if not id:
            raise ValueError("Parameter 'id' is required")

        return await self.perform_request(
            "DELETE",
            f"/api/spaces/space/{_quote(id)}",
        )

    async def copy_saved_objects(
        self,
        *,
        spaces: list[str],
        objects: list[dict[str, Any]],
        include_references: bool | None = None,
        create_new_copies: bool | None = None,
        overwrite: bool | None = None,
        compatibility_mode: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Copy saved objects between spaces.

        Copies saved objects from the current space (the one the client is
        scoped to, or the default space) into one or more target spaces. The
        response reports, per target space, whether the copy succeeded and any
        per-object errors (e.g., conflicts) that can subsequently be retried
        with :meth:`resolve_copy_saved_objects_errors`.

        Args:
            spaces: Identifiers of the target spaces to copy the objects into
                (max 100).
            objects: Saved objects to copy, each a dict with ``"type"`` and
                ``"id"`` keys (max 1000). Example:
                ``[{"type": "dashboard", "id": "my-dashboard"}]``.
            include_references: When True, all saved objects related to the
                specified objects are also copied. Server default: False.
            create_new_copies: Create new copies of the objects with
                regenerated identifiers and reset origin, avoiding conflict
                errors. Server default: True. Cannot be combined with
                ``overwrite`` or ``compatibility_mode``.
            overwrite: When True, conflicting objects in the target space are
                automatically overwritten. Server default: False. Cannot be
                combined with ``create_new_copies``.
            compatibility_mode: Apply adjustments to maintain compatibility
                between different Kibana versions. Server default: False.
                Cannot be combined with ``create_new_copies``.

        Returns:
            ObjectApiResponse mapping each target space ID to a result object
            with ``success``, ``successCount``, ``successResults``, and
            (on failure) ``errors``.

        Raises:
            BadRequestError: If mutually exclusive options are combined or the
                request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to copy into a
                target space.

        Example:
            >>> result = await client.spaces.copy_saved_objects(
            ...     spaces=["marketing"],
            ...     objects=[{"type": "dashboard", "id": "sales-dash"}],
            ...     include_references=True,
            ... )
            >>> print(result.body["marketing"]["success"])
            True
        """
        body: dict[str, Any] = {
            "spaces": spaces,
            "objects": objects,
        }

        if include_references is not None:
            body["includeReferences"] = include_references
        if create_new_copies is not None:
            body["createNewCopies"] = create_new_copies
        if overwrite is not None:
            body["overwrite"] = overwrite
        if compatibility_mode is not None:
            body["compatibilityMode"] = compatibility_mode

        return await self.perform_request(
            "POST",
            "/api/spaces/_copy_saved_objects",
            body=body,
        )

    async def resolve_copy_saved_objects_errors(
        self,
        *,
        retries: dict[str, list[dict[str, Any]]],
        objects: list[dict[str, Any]],
        include_references: bool | None = None,
        create_new_copies: bool | None = None,
        compatibility_mode: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Resolve conflicts encountered while copying saved objects.

        Overwrites specific saved objects that failed to copy in a previous
        :meth:`copy_saved_objects` call. Use the errors reported in that call's
        response to build the ``retries`` map.

        Args:
            retries: Map of target space ID to the list of retry instructions
                for that space. Each retry is a dict with required ``"type"``
                and ``"id"`` keys and optional ``"overwrite"`` (bool),
                ``"destinationId"`` (str), ``"createNewCopy"`` (bool), and
                ``"ignoreMissingReferences"`` (bool) keys.
            objects: The same saved objects passed to the original copy call,
                each a dict with ``"type"`` and ``"id"`` keys (max 1000).
            include_references: When True, related saved objects are also
                copied. Server default: False.
            create_new_copies: Create new copies with regenerated identifiers.
                Server default: True.
            compatibility_mode: Apply cross-version compatibility adjustments.
                Server default: False. Cannot be combined with
                ``create_new_copies``.

        Returns:
            ObjectApiResponse mapping each target space ID to a result object
            with ``success``, ``successCount``, and ``successResults``.

        Raises:
            BadRequestError: If the retry instructions are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.spaces.resolve_copy_saved_objects_errors(
            ...     objects=[{"type": "dashboard", "id": "sales-dash"}],
            ...     retries={
            ...         "marketing": [
            ...             {"type": "dashboard", "id": "sales-dash", "overwrite": True}
            ...         ]
            ...     },
            ...     create_new_copies=False,
            ... )
            >>> print(result.body["marketing"]["success"])
            True
        """
        body: dict[str, Any] = {
            "retries": retries,
            "objects": objects,
        }

        if include_references is not None:
            body["includeReferences"] = include_references
        if create_new_copies is not None:
            body["createNewCopies"] = create_new_copies
        if compatibility_mode is not None:
            body["compatibilityMode"] = compatibility_mode

        return await self.perform_request(
            "POST",
            "/api/spaces/_resolve_copy_saved_objects_errors",
            body=body,
        )

    async def disable_legacy_url_aliases(
        self,
        *,
        aliases: list[dict[str, Any]],
    ) -> ObjectApiResponse[Any]:
        """Disable legacy URL aliases.

        Disables legacy URL aliases that were created when Kibana upgraded
        objects to be shareable across spaces, so that the old object URLs no
        longer redirect to the new objects.

        Args:
            aliases: Legacy URL aliases to disable (max 1000). Each alias is a
                dict with required keys ``"targetSpace"`` (the space where the
                alias target object exists), ``"targetType"`` (the type of the
                target object), and ``"sourceId"`` (the legacy object
                identifier).

        Returns:
            ObjectApiResponse, empty (HTTP 204) on success.

        Raises:
            BadRequestError: If the alias specifications are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.spaces.disable_legacy_url_aliases(
            ...     aliases=[
            ...         {
            ...             "targetSpace": "marketing",
            ...             "targetType": "dashboard",
            ...             "sourceId": "legacy-dash-id",
            ...         }
            ...     ]
            ... )
        """
        body: dict[str, Any] = {"aliases": aliases}

        return await self.perform_request(
            "POST",
            "/api/spaces/_disable_legacy_url_aliases",
            body=body,
        )

    async def get_shareable_references(
        self,
        *,
        objects: list[dict[str, Any]],
    ) -> ObjectApiResponse[Any]:
        """Get shareable references for saved objects.

        Collects references and spaces context for the given saved objects —
        used to determine which objects (and their transitive references) will
        be affected before sharing them to other spaces with
        :meth:`update_objects_spaces`.

        Args:
            objects: Saved objects to collect references for, each a dict with
                ``"type"`` and ``"id"`` keys (max 1000).

        Returns:
            ObjectApiResponse with an ``objects`` list; each entry includes the
            object's ``type``, ``id``, ``spaces``, and any inbound/outbound
            reference information (e.g. ``inboundReferences``,
            ``spacesWithMatchingAliases``, ``spacesWithMatchingOrigins``).

        Raises:
            BadRequestError: If the object specifications are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> refs = await client.spaces.get_shareable_references(
            ...     objects=[{"type": "dashboard", "id": "sales-dash"}]
            ... )
            >>> for obj in refs.body["objects"]:
            ...     print(obj["type"], obj["id"], obj["spaces"])
        """
        body: dict[str, Any] = {"objects": objects}

        return await self.perform_request(
            "POST",
            "/api/spaces/_get_shareable_references",
            body=body,
        )

    async def update_objects_spaces(
        self,
        *,
        objects: list[dict[str, Any]],
        spaces_to_add: list[str],
        spaces_to_remove: list[str],
    ) -> ObjectApiResponse[Any]:
        """Update the spaces that saved objects are shared to.

        Adds the given saved objects to and/or removes them from the specified
        spaces (sharing, not copying — the same object becomes visible in
        multiple spaces). Use ``"*"`` in ``spaces_to_add`` to share to all
        spaces.

        Args:
            objects: Saved objects to update, each a dict with ``"type"`` and
                ``"id"`` keys (max 1000). The object type must be shareable
                across spaces.
            spaces_to_add: Identifiers of the spaces the objects should be
                added to (max 1000). Pass an empty list to only remove.
            spaces_to_remove: Identifiers of the spaces the objects should be
                removed from (max 1000). Pass an empty list to only add.

        Returns:
            ObjectApiResponse with an ``objects`` list; each entry includes the
            object's ``type``, ``id``, and updated ``spaces`` array (and an
            ``error`` field for objects that could not be updated).

        Raises:
            BadRequestError: If the object type is not shareable or the request
                is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges in any affected
                space.

        Example:
            >>> result = await client.spaces.update_objects_spaces(
            ...     objects=[{"type": "dashboard", "id": "sales-dash"}],
            ...     spaces_to_add=["marketing"],
            ...     spaces_to_remove=[],
            ... )
            >>> print(result.body["objects"][0]["spaces"])
            ['default', 'marketing']
        """
        body: dict[str, Any] = {
            "objects": objects,
            "spacesToAdd": spaces_to_add,
            "spacesToRemove": spaces_to_remove,
        }

        return await self.perform_request(
            "POST",
            "/api/spaces/_update_objects_spaces",
            body=body,
        )
