"""Async Kibana Alerting API client."""

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


class AsyncRulesClient(AsyncNamespaceClient):
    """Async client for Kibana Alerting (Rules) API operations."""

    async def create(
        self,
        name: str,
        consumer: str,
        rule_type_id: str,
        schedule: dict[str, Any],
        params: dict[str, Any],
        actions: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
        notify_when: str | None = None,
        enabled: bool = True,
        throttle: str | None = None,
        space_id: str | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """Create a new rule.

        Args:
            name: Human-readable name for the rule.
            consumer: The consumer of the rule (e.g. 'alerts').
            rule_type_id: The ID of the rule type.
            schedule: Schedule for running the rule.
            params: Rule-type specific parameters.
            actions: List of actions to run when the rule triggers.
            tags: List of tags to organize the rule.
            notify_when: When to notify (e.g. 'onActionGroupChange').
            enabled: Whether the rule is enabled.
            throttle: How long to wait between actions (e.g. '1m').
            space_id: Optional space ID.

        Returns:
            The created rule.
        """
        if not name:
            raise ValueError("Parameter 'name' is required")
        if not consumer:
            raise ValueError("Parameter 'consumer' is required")
        if not rule_type_id:
            raise ValueError("Parameter 'rule_type_id' is required")
        if schedule is None:
            raise ValueError("Parameter 'schedule' is required")
        if params is None:
            raise ValueError("Parameter 'params' is required")

        body: dict[str, Any] = {
            "name": name,
            "consumer": consumer,
            "rule_type_id": rule_type_id,
            "schedule": schedule,
            "params": params,
            "enabled": enabled,
        }

        if actions is not None:
            body["actions"] = actions
        if tags is not None:
            body["tags"] = tags
        if notify_when is not None:
            body["notify_when"] = notify_when
        if throttle is not None:
            body["throttle"] = throttle

        path = self._build_space_path("/api/alerting/rule", space_id)

        return await self.perform_request("POST", path, body=body)

    async def get(
        self, id: str, space_id: str | None = None
    ) -> ObjectApiResponse[dict[str, Any]]:
        """Retrieve a rule by ID.

        Args:
            id: Rule ID.
            space_id: Optional space ID.

        Returns:
            The rule object.
        """
        if not id:
            raise ValueError("Parameter 'id' is required")

        path = self._build_space_path(f"/api/alerting/rule/{_quote(id)}", space_id)
        return await self.perform_request("GET", path)

    async def update(
        self,
        id: str,
        name: str,
        schedule: dict[str, Any],
        params: dict[str, Any],
        actions: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
        notify_when: str | None = None,
        throttle: str | None = None,
        space_id: str | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """Update an existing rule.

        Note: ``rule_type_id`` and ``enabled`` are immutable after creation.
        Use the enable/disable API to change the enabled state.

        Args:
            id: Rule ID to update.
            name: Human-readable name for the rule.
            schedule: Schedule for running the rule.
            params: Rule-type specific parameters.
            actions: List of actions to run when the rule triggers.
            tags: List of tags to organize the rule.
            notify_when: When to notify.
            throttle: How long to wait between actions.
            space_id: Optional space ID.

        Returns:
            The updated rule.
        """
        if not id:
            raise ValueError("Parameter 'id' is required")

        body: dict[str, Any] = {
            "name": name,
            "schedule": schedule,
            "params": params,
        }

        if actions is not None:
            body["actions"] = actions
        if tags is not None:
            body["tags"] = tags
        if notify_when is not None:
            body["notify_when"] = notify_when
        if throttle is not None:
            body["throttle"] = throttle

        path = self._build_space_path(f"/api/alerting/rule/{_quote(id)}", space_id)
        return await self.perform_request("PUT", path, body=body)

    async def delete(
        self, id: str, space_id: str | None = None
    ) -> ObjectApiResponse[dict[str, Any]]:
        """Delete a rule.

        Args:
            id: Rule ID.
            space_id: Optional space ID.

        Returns:
            The result of the deletion.
        """
        if not id:
            raise ValueError("Parameter 'id' is required")

        path = self._build_space_path(f"/api/alerting/rule/{_quote(id)}", space_id)
        return await self.perform_request("DELETE", path)

    async def find(
        self,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
        sort_field: str | None = None,
        sort_order: str | None = "asc",
        fields: list[str] | None = None,
        filter: str | None = None,
        space_id: str | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """Find rules.

        Args:
            search: Search string.
            page: Page number.
            per_page: Items per page.
            sort_field: Field to sort by.
            sort_order: Sort order ('asc' or 'desc').
            fields: List of fields to return.
            filter: KQL filter string.
            space_id: Optional space ID.

        Returns:
            List of rules matching the criteria.
        """
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
            "sort_order": sort_order,
        }

        if search:
            params["search"] = search
        if sort_field:
            params["sort_field"] = sort_field
        if fields:
            params["fields"] = fields
        if filter:
            params["filter"] = filter

        path = self._build_space_path("/api/alerting/rules/_find", space_id)
        return await self.perform_request("GET", path, params=params)


class AsyncAlertingClient(AsyncNamespaceClient):
    """Async client for Kibana Alerting API operations."""

    def __init__(self, client: "AsyncKibana") -> None:
        """Initialize the AsyncAlertingClient.

        Args:
            client: The parent AsyncKibana client instance.
        """
        super().__init__(client)
        self._rule = AsyncRulesClient(client)

    @property
    def rule(self) -> AsyncRulesClient:
        """Access rule operations."""
        return self._rule
