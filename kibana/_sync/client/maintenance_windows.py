"""Kibana Maintenance Windows API client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._sync.client import Kibana


class MaintenanceWindowsClient(NamespaceClient):
    """Client for the Kibana Maintenance Windows API.

    A maintenance window suppresses rule notifications for a scheduled period
    of time: alerts continue to be created, but their actions (notifications)
    are not run while a maintenance window is active. Maintenance windows
    require a Platinum or higher license.

    The Maintenance Windows API is generally available in Kibana 9.4 (create,
    get, update, delete, archive and unarchive were added in 9.1.0; find was
    added in 9.2.0).

    Maintenance windows are space-scoped: a maintenance window created in one
    space only affects rules in that space. Every method accepts an optional
    ``space_id`` to target a specific space (``None`` targets the default
    space or the space the client is scoped to).

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a one-hour maintenance window
        >>> created = client.maintenance_windows.create(
        ...     title="Weekend maintenance",
        ...     schedule={
        ...         "custom": {
        ...             "start": "2030-01-05T00:00:00.000Z",
        ...             "duration": "1h",
        ...         }
        ...     },
        ... )
        >>> mw_id = created.body["id"]
        >>>
        >>> # Archive it once it is no longer needed, then delete it
        >>> client.maintenance_windows.archive(id=mw_id)
        >>> client.maintenance_windows.delete(id=mw_id)
    """

    def __init__(
        self,
        client: Kibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the MaintenanceWindowsClient.

        Args:
            client: The parent Kibana client instance to delegate requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> maintenance_windows_client = MaintenanceWindowsClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    def create(
        self,
        *,
        title: str,
        schedule: dict[str, Any],
        enabled: bool | None = None,
        scope: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a maintenance window.

        Generally available; added in 9.1.0. You must have ``read``
        privileges for the Maintenance Windows feature in the Management
        section of the Kibana feature privileges.

        Args:
            title: The name of the maintenance window. While this name does
                not have to be unique, a distinctive name helps you identify
                a specific maintenance window.
            schedule: The schedule of the maintenance window. An object with
                a required ``custom`` key, for example::

                    {
                        "custom": {
                            "start": "2030-01-05T00:00:00.000Z",  # required
                            "duration": "2h",                     # required
                            "timezone": "UTC",
                            "recurring": {
                                "every": "1w",
                                "onWeekDay": ["MO", "FR"],
                                "onMonthDay": [1, 15],
                                "onMonth": [1, 6],
                                "occurrences": 10,
                                "end": "2031-01-01T00:00:00.000Z",
                            },
                        }
                    }

                ``duration`` accepts ``<integer><unit>`` values where unit is
                one of ``d``, ``h``, ``m`` or ``s``; ``recurring.every``
                accepts ``d``, ``w``, ``M`` or ``y`` units.
            enabled: Whether the maintenance window is enabled. Disabled
                maintenance windows do not suppress notifications.
            scope: An object narrowing the affected rules with a KQL query,
                for example ``{"alerting": {"query": {"kql": "..."}}}``. When
                omitted, the maintenance window affects all rules in the space.
            space_id: Optional space ID to create the maintenance window in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created maintenance window:
                - id: The identifier for the maintenance window
                - title / enabled / schedule / scope: as configured
                - status: "running", "upcoming", "finished", "archived" or
                  "disabled"
                - created_at / created_by / updated_at / updated_by: metadata

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges or license.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = client.maintenance_windows.create(
            ...     title="Monthly patch window",
            ...     schedule={
            ...         "custom": {
            ...             "start": "2030-01-01T00:00:00.000Z",
            ...             "duration": "4h",
            ...             "recurring": {"every": "1M", "onMonthDay": [1]},
            ...         }
            ...     },
            ...     scope={"alerting": {"query": {"kql": 'tags: "maintenance"'}}},
            ... )
            >>> print(created.body["title"])
            Monthly patch window
        """
        body: dict[str, Any] = {
            "title": title,
            "schedule": schedule,
        }
        if enabled is not None:
            body["enabled"] = enabled
        if scope is not None:
            body["scope"] = scope

        path = self._build_space_path(
            "/api/maintenance_window", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def get(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get maintenance window details.

        Generally available; added in 9.1.0. You must have ``read``
        privileges for the Maintenance Windows feature in the Management
        section of the Kibana feature privileges.

        Args:
            id: The identifier for the maintenance window.
            space_id: Optional space ID to get the maintenance window from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the maintenance window (``id``,
            ``title``, ``enabled``, ``schedule``, ``scope``, ``status`` and
            created/updated metadata).

        Raises:
            NotFoundError: If the maintenance window does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges or license.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> window = client.maintenance_windows.get(id="da4c2f57-...")
            >>> print(window.body["title"])
            Weekend maintenance
        """
        path = self._build_space_path(
            f"/api/maintenance_window/{_quote(id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def find(
        self,
        *,
        title: str | None = None,
        created_by: str | None = None,
        status: str | list[str] | None = None,
        page: int | None = None,
        per_page: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Search for maintenance windows.

        Generally available; added in 9.2.0. Retrieves a paginated list of
        maintenance windows, optionally filtered by title, creator or status.
        You must have ``read`` privileges for the Maintenance Windows feature
        in the Management section of the Kibana feature privileges.

        Args:
            title: The title of the maintenance window.
            created_by: The user who created the maintenance window.
            status: The status of the maintenance window. One (or a list) of
                ``"running"``, ``"upcoming"``, ``"finished"``, ``"archived"``
                or ``"disabled"``.
            page: The page number to return (1-100, default 1).
            per_page: The number of maintenance windows to return per page
                (1-100, default 10).
            space_id: Optional space ID to search in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing:
                - maintenanceWindows: The list of matching maintenance windows
                - total: The total number of matching maintenance windows
                - page / per_page: The pagination values used

        Raises:
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges or license.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = client.maintenance_windows.find(
            ...     status=["running", "upcoming"], per_page=50
            ... )
            >>> for window in found.body["maintenanceWindows"]:
            ...     print(window["id"], window["title"])
        """
        params: dict[str, Any] = {}
        if title is not None:
            params["title"] = title
        if created_by is not None:
            params["created_by"] = created_by
        if status is not None:
            params["status"] = status
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page

        path = self._build_space_path(
            "/api/maintenance_window/_find", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def update(
        self,
        *,
        id: str,
        title: str | None = None,
        enabled: bool | None = None,
        schedule: dict[str, Any] | None = None,
        scope: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a maintenance window.

        Generally available; added in 9.1.0. Performs a partial update: only
        the provided fields are changed. You must have ``all`` privileges for
        the Maintenance Windows feature in the Management section of the
        Kibana feature privileges.

        Args:
            id: The identifier for the maintenance window.
            title: The new name of the maintenance window.
            enabled: Whether the maintenance window is enabled. Disabled
                maintenance windows do not suppress notifications.
            schedule: The new schedule of the maintenance window; an object
                with a required ``custom`` key (see
                :meth:`MaintenanceWindowsClient.create`).
            scope: An object narrowing the affected rules with a KQL query,
                for example ``{"alerting": {"query": {"kql": "..."}}}``.
            space_id: Optional space ID the maintenance window lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated maintenance window.

        Raises:
            NotFoundError: If the maintenance window does not exist.
            BadRequestError: If the request body is invalid.
            ConflictError: If the maintenance window was concurrently updated.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges or license.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = client.maintenance_windows.update(
            ...     id="da4c2f57-...", enabled=False
            ... )
            >>> print(updated.body["status"])
            disabled
        """
        body: dict[str, Any] = {}
        if title is not None:
            body["title"] = title
        if enabled is not None:
            body["enabled"] = enabled
        if schedule is not None:
            body["schedule"] = schedule
        if scope is not None:
            body["scope"] = scope

        path = self._build_space_path(
            f"/api/maintenance_window/{_quote(id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def delete(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a maintenance window.

        Generally available; added in 9.1.0. You must have ``all`` privileges
        for the Maintenance Windows feature in the Management section of the
        Kibana feature privileges.

        Args:
            id: The identifier for the maintenance window.
            space_id: Optional space ID the maintenance window lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body (HTTP 204) on success.

        Raises:
            NotFoundError: If the maintenance window does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges or license.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> client.maintenance_windows.delete(id="da4c2f57-...")
        """
        path = self._build_space_path(
            f"/api/maintenance_window/{_quote(id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    def archive(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Archive a maintenance window.

        Generally available; added in 9.1.0. An archived maintenance window
        no longer suppresses notifications and is hidden from the active
        lists in the UI. You must have ``all`` privileges for the Maintenance
        Windows feature in the Management section of the Kibana feature
        privileges.

        Args:
            id: The identifier for the maintenance window.
            space_id: Optional space ID the maintenance window lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the archived maintenance window
            (its ``status`` becomes ``"archived"`` unless it is disabled).

        Raises:
            NotFoundError: If the maintenance window does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges or license.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> archived = client.maintenance_windows.archive(id="da4c2f57-...")
            >>> print(archived.body["status"])
            archived
        """
        path = self._build_space_path(
            f"/api/maintenance_window/{_quote(id)}/_archive",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    def unarchive(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Unarchive a maintenance window.

        Generally available; added in 9.1.0. Restores an archived maintenance
        window; its status is recomputed from its schedule. You must have
        ``all`` privileges for the Maintenance Windows feature in the
        Management section of the Kibana feature privileges.

        Args:
            id: The identifier for the maintenance window.
            space_id: Optional space ID the maintenance window lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the unarchived maintenance window.
            Note: in Kibana 9.4.3 the recomputed ``status`` is derived from
            the events Kibana materializes within a limited look-ahead
            horizon, so a window whose schedule lies in the far future is
            reported as ``"finished"`` rather than ``"upcoming"``.

        Raises:
            NotFoundError: If the maintenance window does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges or license.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> restored = client.maintenance_windows.unarchive(id="da4c2f57-...")
            >>> print(restored.body["status"] != "archived")
            True
        """
        path = self._build_space_path(
            f"/api/maintenance_window/{_quote(id)}/_unarchive",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )
