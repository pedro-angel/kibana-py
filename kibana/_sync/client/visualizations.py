"""Kibana Visualizations API client."""

from __future__ import annotations

import json
from typing import Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient, _quote


def _string_array(value: str | list[str]) -> str:
    """Encode a string-array query parameter the way Kibana expects.

    The Visualizations API validates array-valued query parameters with
    ``schema.arrayOf``; a single bare value (``fields=title``) is rejected
    with ``400 could not parse array value from json input``, so values are
    always encoded as a JSON array string (``fields=["title"]``), which the
    live server accepts for both single and multiple entries.

    :param value: A single field name or a list of field names
    :return: Compact JSON array string
    """
    if isinstance(value, str):
        value = [value]
    return json.dumps(list(value), separators=(",", ":"))


class VisualizationsClient(NamespaceClient):
    """Client for the Kibana Visualizations HTTP API.

    Technical preview in 9.4 (added in 9.4.0). Manages Lens visualizations
    (metric, XY, pie, gauge, heatmap, tag cloud, region map, datatable,
    mosaic, treemap, waffle, legacy metric) through the ``/api/visualizations``
    endpoints. Responses use the same ``{id, data, meta}`` envelope as the
    Dashboards API: ``data`` holds the chart configuration and ``meta`` holds
    timestamps and version information.

    All operations support Kibana spaces via the ``space_id`` parameter or a
    space-scoped client created with ``client.space("my-space")``.

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a metric visualization
        >>> created = client.visualizations.create(
        ...     data={
        ...         "type": "metric",
        ...         "title": "Total log documents",
        ...         "data_source": {
        ...             "type": "data_view_spec",
        ...             "index_pattern": "logs-*",
        ...         },
        ...         "query": {"expression": "", "language": "kql"},
        ...         "metrics": [{"type": "primary", "operation": "count"}],
        ...     }
        ... )
        >>> viz_id = created.body["id"]
        >>>
        >>> # Search visualizations by title
        >>> results = client.visualizations.get_all(query="Total log*")
        >>> print(results.body["meta"]["total"])
    """

    def get_all(
        self,
        *,
        query: str | None = None,
        search_fields: str | list[str] | None = None,
        fields: str | list[str] | None = None,
        page: int | None = None,
        per_page: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Search visualizations.

        Technical preview in 9.4. Returns a paginated envelope with a ``data``
        array of ``{id, data, meta}`` items and a ``meta`` object containing
        ``page``, ``per_page`` and ``total``.

        Args:
            query: Text to match against ``search_fields``. Supports simple
                query syntax (e.g. trailing ``*`` wildcards).
            search_fields: Attribute field(s) the ``query`` is matched
                against (e.g. ``["title"]``). Note: on live Kibana 9.4.3 this
                parameter triggers a ``500 Internal Server Error`` (server-side
                bug in the technical preview API); prefer ``query`` alone until
                fixed upstream.
            fields: Attribute field(s) to return in the ``data`` payload of
                each result (e.g. ``["title"]``); omit to return the full
                visualization configuration. Note: on live Kibana 9.4.3 this
                parameter triggers a ``500 Internal Server Error`` whenever
                the search matches existing objects (server-side bug in the
                technical preview API).
            page: Page number (default 1).
            per_page: Results per page (default 20, maximum 1000).
            space_id: Optional space ID to scope the operation to.
            validate_spaces: Override space validation for this call.

        Returns:
            ObjectApiResponse with ``data`` (list of visualizations) and
            ``meta`` (``page``, ``per_page``, ``total``).

        Raises:
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> results = client.visualizations.get_all(
            ...     query="sales*", per_page=10
            ... )
            >>> for item in results.body["data"]:
            ...     print(item["id"], item["data"]["title"])
        """
        path = self._build_space_path("/api/visualizations", space_id, validate_spaces)
        params: dict[str, Any] = {}
        if query is not None:
            params["query"] = query
        if search_fields is not None:
            params["search_fields"] = _string_array(search_fields)
        if fields is not None:
            params["fields"] = _string_array(fields)
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        return self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    def create(
        self,
        *,
        data: dict[str, Any],
        overwrite: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a visualization.

        Technical preview in 9.4. The server assigns the visualization ID and
        returns the created object in the ``{id, data, meta}`` envelope.

        Args:
            data: Visualization configuration (the Lens API config). Must
                include ``type`` (one of ``metric``, ``xy``, ``pie``,
                ``gauge``, ``heatmap``, ``tagcloud``, ``regionmap``,
                ``datatable``, ``mosaic``, ``treemap``, ``waffle`` or a legacy
                metric), a ``data_source`` (data view reference or spec),
                a ``query`` filter and the chart-type-specific dimensions
                (e.g. ``metrics`` for metric charts).
            overwrite: When True, overwrite an existing object on ID clash.
            space_id: Optional space ID to create the visualization in.
            validate_spaces: Override space validation for this call.

        Returns:
            ObjectApiResponse with ``id``, ``data`` (normalized configuration)
            and ``meta`` (``created_at``, ``updated_at``, ``version`` ...).

        Raises:
            BadRequestError: If the configuration fails schema validation.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> created = client.visualizations.create(
            ...     data={
            ...         "type": "metric",
            ...         "title": "Order count",
            ...         "data_source": {
            ...             "type": "data_view_spec",
            ...             "index_pattern": "orders-*",
            ...         },
            ...         "query": {"expression": "", "language": "kql"},
            ...         "metrics": [{"type": "primary", "operation": "count"}],
            ...     }
            ... )
            >>> print(created.body["id"])
        """
        path = self._build_space_path("/api/visualizations", space_id, validate_spaces)
        params: dict[str, Any] = {}
        if overwrite is not None:
            params["overwrite"] = overwrite
        return self.perform_request(
            "POST",
            path,
            params=params or None,
            body=data,
        )

    def get(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a visualization by ID.

        Technical preview in 9.4.

        Args:
            id: The visualization ID.
            space_id: Optional space ID to read the visualization from.
            validate_spaces: Override space validation for this call.

        Returns:
            ObjectApiResponse with ``id``, ``data`` (the visualization
            configuration) and ``meta``.

        Raises:
            NotFoundError: If no visualization exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> viz = client.visualizations.get(id="my-viz-id")
            >>> print(viz.body["data"]["title"])
        """
        if not id:
            raise ValueError("Parameter 'id' is required")
        path = self._build_space_path(
            f"/api/visualizations/{_quote(id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def update(
        self,
        *,
        id: str,
        data: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update (or create with a chosen ID) a visualization.

        Technical preview in 9.4. The body fully replaces the stored
        configuration. If no visualization exists with the given ID the
        server creates one (upsert; HTTP 201 instead of 200).

        Args:
            id: The visualization ID to update or create.
            data: Full visualization configuration (same shape as ``create``).
            space_id: Optional space ID the visualization lives in.
            validate_spaces: Override space validation for this call.

        Returns:
            ObjectApiResponse with the updated ``id``, ``data`` and ``meta``.

        Raises:
            BadRequestError: If the configuration fails schema validation.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> updated = client.visualizations.update(
            ...     id="my-viz-id",
            ...     data={
            ...         "type": "metric",
            ...         "title": "Order count (renamed)",
            ...         "data_source": {
            ...             "type": "data_view_spec",
            ...             "index_pattern": "orders-*",
            ...         },
            ...         "query": {"expression": "", "language": "kql"},
            ...         "metrics": [{"type": "primary", "operation": "count"}],
            ...     },
            ... )
            >>> print(updated.body["data"]["title"])
        """
        if not id:
            raise ValueError("Parameter 'id' is required")
        path = self._build_space_path(
            f"/api/visualizations/{_quote(id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "PUT",
            path,
            body=data,
        )

    def delete(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a visualization by ID.

        Technical preview in 9.4. Returns HTTP 204 with an empty body on
        success.

        Args:
            id: The visualization ID to delete.
            space_id: Optional space ID the visualization lives in.
            validate_spaces: Override space validation for this call.

        Returns:
            ObjectApiResponse with an empty body (HTTP 204 No Content).

        Raises:
            NotFoundError: If no visualization exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> client.visualizations.delete(id="my-viz-id")
        """
        if not id:
            raise ValueError("Parameter 'id' is required")
        path = self._build_space_path(
            f"/api/visualizations/{_quote(id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "DELETE",
            path,
        )
