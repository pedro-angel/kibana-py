"""Async Kibana Data Views API client."""

from __future__ import annotations

from typing import Any

from elastic_transport import ObjectApiResponse

from .utils import AsyncNamespaceClient, _quote


class AsyncDataViewsClient(AsyncNamespaceClient):
    """Async client for the Kibana Data Views API.

    Data views (formerly index patterns) tell Kibana which Elasticsearch
    indices, data streams, and aliases to query. This client covers the
    full Kibana 9.4.3 data views surface: data view CRUD, field metadata
    updates, runtime field management, the default data view, and saved
    object reference swapping.

    All operations are space-aware: pass ``space_id`` to target a specific
    Kibana space, or use ``client.space("my-space").data_views``.

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a data view over an index
        >>> response = await client.data_views.create(
        ...     data_view={
        ...         "title": "my-logs-*",
        ...         "name": "My Logs",
        ...         "timeFieldName": "@timestamp",
        ...     }
        ... )
        >>> view_id = response["data_view"]["id"]
        >>>
        >>> # Add a runtime field
        >>> await client.data_views.create_runtime_field(
        ...     view_id=view_id,
        ...     name="hour_of_day",
        ...     runtime_field={
        ...         "type": "long",
        ...         "script": {
        ...             "source": "emit(doc['@timestamp'].value.getHour())"
        ...         },
        ...     },
        ... )
    """

    async def get_all(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get all data views.

        Retrieves a list of all data views in the space, with their
        identifiers, titles, names, and namespaces.

        Args:
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            Response with a ``data_view`` array of data view summaries.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> response = await client.data_views.get_all()
            >>> for view in response["data_view"]:
            ...     print(view["id"], view["title"])
        """
        path = self._build_space_path("/api/data_views", space_id)
        await self._maybe_validate_space(space_id, validate_spaces)
        return await self.perform_request("GET", path)

    async def create(
        self,
        *,
        data_view: dict[str, Any],
        override: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a data view.

        Args:
            data_view: The data view object. Requires ``title`` (a
                comma-separated list of data streams, indices, and aliases
                to search). Optional keys include ``id``, ``name``,
                ``timeFieldName``, ``allowNoIndex``, ``fieldAttrs``,
                ``fieldFormats``, ``namespaces``, ``runtimeFieldMap``,
                ``sourceFilters``, ``type``, ``typeMeta``, and ``version``.
            override: Override an existing data view if one with the
                provided title already exists. Defaults to false.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            Response with the created ``data_view`` object.

        Raises:
            ValueError: If ``data_view`` is missing.
            BadRequestError: If the data view definition is invalid or a
                data view with the same title exists and ``override`` is
                not set.

        Example:
            >>> response = await client.data_views.create(
            ...     data_view={
            ...         "title": "my-logs-*",
            ...         "timeFieldName": "@timestamp",
            ...     }
            ... )
            >>> print(response["data_view"]["id"])
        """
        if data_view is None:
            raise ValueError("Parameter 'data_view' is required")

        body: dict[str, Any] = {"data_view": data_view}
        if override is not None:
            body["override"] = override

        path = self._build_space_path("/api/data_views/data_view", space_id)
        await self._maybe_validate_space(space_id, validate_spaces)
        return await self.perform_request("POST", path, body=body)

    async def get(
        self,
        *,
        view_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a data view.

        Args:
            view_id: The data view identifier.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            Response with the full ``data_view`` object, including fields.

        Raises:
            ValueError: If ``view_id`` is missing.
            NotFoundError: If the data view does not exist.

        Example:
            >>> response = await client.data_views.get(view_id="my-view-id")
            >>> print(response["data_view"]["title"])
        """
        if not view_id:
            raise ValueError("Parameter 'view_id' is required")

        path = self._build_space_path(
            f"/api/data_views/data_view/{_quote(view_id)}", space_id
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        return await self.perform_request("GET", path)

    async def update(
        self,
        *,
        view_id: str,
        data_view: dict[str, Any],
        refresh_fields: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a data view.

        Only the properties present in ``data_view`` are updated; all other
        properties keep their current values.

        Args:
            view_id: The data view identifier.
            data_view: The data view properties to update, e.g. ``title``,
                ``name``, ``timeFieldName``, ``allowNoIndex``,
                ``fieldFormats``, ``runtimeFieldMap``, ``sourceFilters``,
                ``type``, or ``typeMeta``.
            refresh_fields: Reload the data view fields after the update.
                Defaults to false.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            Response with the updated ``data_view`` object.

        Raises:
            ValueError: If ``view_id`` or ``data_view`` is missing.
            NotFoundError: If the data view does not exist.
            BadRequestError: If the update payload is invalid.

        Example:
            >>> await client.data_views.update(
            ...     view_id="my-view-id",
            ...     data_view={"name": "Renamed view"},
            ...     refresh_fields=True,
            ... )
        """
        if not view_id:
            raise ValueError("Parameter 'view_id' is required")
        if data_view is None:
            raise ValueError("Parameter 'data_view' is required")

        body: dict[str, Any] = {"data_view": data_view}
        if refresh_fields is not None:
            body["refresh_fields"] = refresh_fields

        path = self._build_space_path(
            f"/api/data_views/data_view/{_quote(view_id)}", space_id
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        return await self.perform_request("POST", path, body=body)

    async def delete(
        self,
        *,
        view_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a data view.

        WARNING: When you delete a data view, it cannot be recovered.

        Args:
            view_id: The data view identifier.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            Empty response on success.

        Raises:
            ValueError: If ``view_id`` is missing.
            NotFoundError: If the data view does not exist.

        Example:
            >>> await client.data_views.delete(view_id="my-view-id")
        """
        if not view_id:
            raise ValueError("Parameter 'view_id' is required")

        path = self._build_space_path(
            f"/api/data_views/data_view/{_quote(view_id)}", space_id
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        return await self.perform_request("DELETE", path)

    async def update_fields_metadata(
        self,
        *,
        view_id: str,
        fields: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update data view fields metadata.

        Updates presentation metadata for fields, such as ``count``,
        ``customLabel``, ``customDescription``, and ``format``.

        Args:
            fields: Map of field names to the metadata to set, e.g.
                ``{"my_field": {"customLabel": "My label", "count": 5}}``.
            view_id: The data view identifier.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            Response with the updated ``data_view`` object.

        Raises:
            ValueError: If ``view_id`` or ``fields`` is missing.
            NotFoundError: If the data view does not exist.
            BadRequestError: If the fields payload is invalid.

        Example:
            >>> await client.data_views.update_fields_metadata(
            ...     view_id="my-view-id",
            ...     fields={"response_code": {"customLabel": "Status"}},
            ... )
        """
        if not view_id:
            raise ValueError("Parameter 'view_id' is required")
        if fields is None:
            raise ValueError("Parameter 'fields' is required")

        body: dict[str, Any] = {"fields": fields}

        path = self._build_space_path(
            f"/api/data_views/data_view/{_quote(view_id)}/fields",
            space_id,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        return await self.perform_request("POST", path, body=body)

    async def create_runtime_field(
        self,
        *,
        view_id: str,
        name: str,
        runtime_field: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a runtime field.

        Fails if a runtime field with the same name already exists; use
        :meth:`create_or_update_runtime_field` for upsert semantics.

        Args:
            view_id: The data view identifier.
            name: The name for the new runtime field.
            runtime_field: The runtime field definition object, e.g.
                ``{"type": "keyword", "script": {"source": "emit('a')"}}``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            Response with the created runtime ``fields`` and the updated
            ``data_view`` object.

        Raises:
            ValueError: If a required parameter is missing.
            NotFoundError: If the data view does not exist.
            BadRequestError: If the field already exists or the definition
                is invalid.

        Example:
            >>> await client.data_views.create_runtime_field(
            ...     view_id="my-view-id",
            ...     name="hour_of_day",
            ...     runtime_field={
            ...         "type": "long",
            ...         "script": {
            ...             "source": "emit(doc['@timestamp'].value.getHour())"
            ...         },
            ...     },
            ... )
        """
        if not view_id:
            raise ValueError("Parameter 'view_id' is required")
        if not name:
            raise ValueError("Parameter 'name' is required")
        if runtime_field is None:
            raise ValueError("Parameter 'runtime_field' is required")

        body: dict[str, Any] = {"name": name, "runtimeField": runtime_field}

        path = self._build_space_path(
            f"/api/data_views/data_view/{_quote(view_id)}/runtime_field",
            space_id,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        return await self.perform_request("POST", path, body=body)

    async def create_or_update_runtime_field(
        self,
        *,
        view_id: str,
        name: str,
        runtime_field: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create or update a runtime field.

        Upsert semantics: creates the runtime field if it does not exist,
        or replaces its definition if it does.

        Args:
            view_id: The data view identifier.
            name: The name for the runtime field.
            runtime_field: The runtime field definition object, e.g.
                ``{"type": "keyword", "script": {"source": "emit('a')"}}``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            Response with the runtime ``fields`` and the updated
            ``data_view`` object.

        Raises:
            ValueError: If a required parameter is missing.
            NotFoundError: If the data view does not exist.
            BadRequestError: If the field definition is invalid.

        Example:
            >>> await client.data_views.create_or_update_runtime_field(
            ...     view_id="my-view-id",
            ...     name="hour_of_day",
            ...     runtime_field={
            ...         "type": "long",
            ...         "script": {
            ...             "source": "emit(doc['@timestamp'].value.getHour())"
            ...         },
            ...     },
            ... )
        """
        if not view_id:
            raise ValueError("Parameter 'view_id' is required")
        if not name:
            raise ValueError("Parameter 'name' is required")
        if runtime_field is None:
            raise ValueError("Parameter 'runtime_field' is required")

        body: dict[str, Any] = {"name": name, "runtimeField": runtime_field}

        path = self._build_space_path(
            f"/api/data_views/data_view/{_quote(view_id)}/runtime_field",
            space_id,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        return await self.perform_request("PUT", path, body=body)

    async def get_runtime_field(
        self,
        *,
        view_id: str,
        name: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a runtime field.

        Args:
            view_id: The data view identifier.
            name: The name of the runtime field.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            Response with the runtime ``fields`` and the owning
            ``data_view`` object.

        Raises:
            ValueError: If ``view_id`` or ``name`` is missing.
            NotFoundError: If the data view or runtime field does not exist.

        Example:
            >>> response = await client.data_views.get_runtime_field(
            ...     view_id="my-view-id", name="hour_of_day"
            ... )
            >>> print(response["fields"][0]["runtimeField"]["type"])
        """
        if not view_id:
            raise ValueError("Parameter 'view_id' is required")
        if not name:
            raise ValueError("Parameter 'name' is required")

        path = self._build_space_path(
            f"/api/data_views/data_view/{_quote(view_id)}"
            f"/runtime_field/{_quote(name)}",
            space_id,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        return await self.perform_request("GET", path)

    async def update_runtime_field(
        self,
        *,
        view_id: str,
        name: str,
        runtime_field: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a runtime field.

        Updates an existing runtime field definition. You can update the
        ``type`` and ``script`` of the runtime field.

        Args:
            view_id: The data view identifier.
            name: The name of the runtime field to update.
            runtime_field: The runtime field properties to update, e.g.
                ``{"script": {"source": "emit('b')"}}``.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            Response with the runtime ``fields`` and the updated
            ``data_view`` object.

        Raises:
            ValueError: If a required parameter is missing.
            NotFoundError: If the data view or runtime field does not exist.
            BadRequestError: If the field definition is invalid.

        Example:
            >>> await client.data_views.update_runtime_field(
            ...     view_id="my-view-id",
            ...     name="hour_of_day",
            ...     runtime_field={"script": {"source": "emit(0)"}},
            ... )
        """
        if not view_id:
            raise ValueError("Parameter 'view_id' is required")
        if not name:
            raise ValueError("Parameter 'name' is required")
        if runtime_field is None:
            raise ValueError("Parameter 'runtime_field' is required")

        body: dict[str, Any] = {"runtimeField": runtime_field}

        path = self._build_space_path(
            f"/api/data_views/data_view/{_quote(view_id)}"
            f"/runtime_field/{_quote(name)}",
            space_id,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        return await self.perform_request("POST", path, body=body)

    async def delete_runtime_field(
        self,
        *,
        view_id: str,
        name: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a runtime field from a data view.

        Args:
            view_id: The data view identifier.
            name: The name of the runtime field to delete.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            Empty response on success.

        Raises:
            ValueError: If ``view_id`` or ``name`` is missing.
            NotFoundError: If the data view or runtime field does not exist.

        Example:
            >>> await client.data_views.delete_runtime_field(
            ...     view_id="my-view-id", name="hour_of_day"
            ... )
        """
        if not view_id:
            raise ValueError("Parameter 'view_id' is required")
        if not name:
            raise ValueError("Parameter 'name' is required")

        path = self._build_space_path(
            f"/api/data_views/data_view/{_quote(view_id)}"
            f"/runtime_field/{_quote(name)}",
            space_id,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        return await self.perform_request("DELETE", path)

    async def get_default(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the default data view.

        Args:
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            Response with the default ``data_view_id`` (an empty string when
            no default data view is set).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> response = await client.data_views.get_default()
            >>> print(response["data_view_id"])
        """
        path = self._build_space_path("/api/data_views/default", space_id)
        await self._maybe_validate_space(space_id, validate_spaces)
        return await self.perform_request("GET", path)

    async def set_default(
        self,
        *,
        data_view_id: str | None,
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Set the default data view.

        Args:
            data_view_id: The data view identifier to set as default.
                NOTE: The API does not validate whether it is a valid
                identifier. Use ``None`` to unset the default data view.
            force: Update the default even when one is already set.
                Defaults to false.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            Response with ``acknowledged: true`` on success.

        Raises:
            BadRequestError: If the request payload is invalid.

        Example:
            >>> await client.data_views.set_default(
            ...     data_view_id="my-view-id", force=True
            ... )
        """
        body: dict[str, Any] = {"data_view_id": data_view_id}
        if force is not None:
            body["force"] = force

        path = self._build_space_path("/api/data_views/default", space_id)
        await self._maybe_validate_space(space_id, validate_spaces)
        return await self.perform_request("POST", path, body=body)

    async def swap_references(
        self,
        *,
        from_id: str,
        to_id: str,
        from_type: str | None = None,
        for_id: str | list[str] | None = None,
        for_type: str | None = None,
        delete: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Swap saved object references.

        Changes saved object references from one data view identifier to
        another. WARNING: Misuse can break large numbers of saved objects.
        Practicing with a backup is recommended; use
        :meth:`preview_swap_references` to dry-run the operation first.

        Args:
            from_id: The saved object reference to change.
            to_id: New saved object reference value to replace the old value.
            from_type: The type of the saved object reference to alter.
                Defaults to ``index-pattern`` (data views).
            for_id: Limit the affected saved objects to one or more by
                identifier (a single ID or a list of IDs).
            for_type: Limit the affected saved objects by type.
            delete: Delete the referenced saved object (``from_id``) if all
                its references are removed. Defaults to false.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            Response with a ``result`` array of the changed saved objects
            and, when ``delete`` is used, a ``deleteStatus`` object.

        Raises:
            ValueError: If ``from_id`` or ``to_id`` is missing.
            BadRequestError: If the request payload is invalid.

        Example:
            >>> response = await client.data_views.swap_references(
            ...     from_id="old-view-id",
            ...     to_id="new-view-id",
            ...     delete=True,
            ... )
            >>> print(response["deleteStatus"]["deletePerformed"])
        """
        if not from_id:
            raise ValueError("Parameter 'from_id' is required")
        if not to_id:
            raise ValueError("Parameter 'to_id' is required")

        body: dict[str, Any] = {"fromId": from_id, "toId": to_id}
        if from_type is not None:
            body["fromType"] = from_type
        if for_id is not None:
            body["forId"] = for_id
        if for_type is not None:
            body["forType"] = for_type
        if delete is not None:
            body["delete"] = delete

        path = self._build_space_path("/api/data_views/swap_references", space_id)
        await self._maybe_validate_space(space_id, validate_spaces)
        return await self.perform_request("POST", path, body=body)

    async def preview_swap_references(
        self,
        *,
        from_id: str,
        to_id: str,
        from_type: str | None = None,
        for_id: str | list[str] | None = None,
        for_type: str | None = None,
        delete: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Preview a saved object reference swap.

        Dry-runs :meth:`swap_references` and reports which saved objects
        would be changed, without modifying anything.

        Args:
            from_id: The saved object reference to change.
            to_id: New saved object reference value to replace the old value.
            from_type: The type of the saved object reference to alter.
                Defaults to ``index-pattern`` (data views).
            for_id: Limit the affected saved objects to one or more by
                identifier (a single ID or a list of IDs).
            for_type: Limit the affected saved objects by type.
            delete: Whether the swap would delete the referenced saved
                object once all its references are removed.
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            Response with a ``result`` array of the saved objects that
            would be changed.

        Raises:
            ValueError: If ``from_id`` or ``to_id`` is missing.
            BadRequestError: If the request payload is invalid.

        Example:
            >>> response = await client.data_views.preview_swap_references(
            ...     from_id="old-view-id", to_id="new-view-id"
            ... )
            >>> print(response["result"])
        """
        if not from_id:
            raise ValueError("Parameter 'from_id' is required")
        if not to_id:
            raise ValueError("Parameter 'to_id' is required")

        body: dict[str, Any] = {"fromId": from_id, "toId": to_id}
        if from_type is not None:
            body["fromType"] = from_type
        if for_id is not None:
            body["forId"] = for_id
        if for_type is not None:
            body["forType"] = for_type
        if delete is not None:
            body["delete"] = delete

        path = self._build_space_path(
            "/api/data_views/swap_references/_preview", space_id
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        return await self.perform_request("POST", path, body=body)
