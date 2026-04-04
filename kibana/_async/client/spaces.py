"""Async Kibana Spaces API client."""

from typing import Any

from elastic_transport import ObjectApiResponse

from .utils import AsyncNamespaceClient


class AsyncSpacesClient(AsyncNamespaceClient):
    """Async client for Kibana Spaces API.

    Spaces allow you to organize your Kibana objects (dashboards, visualizations, etc.)
    into separate, isolated areas. Each space can have its own set of saved objects
    and can be used to implement multi-tenancy.
    """

    async def create(
        self,
        *,
        id: str,
        name: str,
        description: str | None = None,
        color: str | None = None,
        initials: str | None = None,
        disabled_features: list[str] | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """Create a new space.

        :param id: Unique identifier for the space (URL-friendly)
        :param name: Display name for the space
        :param description: Optional description of the space
        :param color: Optional hex color code for the space (e.g., "#FF0000")
        :param initials: Optional initials to display for the space (max 2 characters)
        :param disabled_features: Optional list of feature IDs to disable in this space
        :return: ObjectApiResponse containing the created space details
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
        if disabled_features is not None:
            body["disabledFeatures"] = disabled_features

        return await self.perform_request(
            "POST",
            "/api/spaces/space",
            body=body,
        )

    async def get(
        self,
        *,
        id: str,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """Get a space by ID.

        :param id: The space ID to retrieve
        :return: ObjectApiResponse containing the space details
        """
        if not id:
            raise ValueError("Parameter 'id' is required")

        return await self.perform_request(
            "GET",
            f"/api/spaces/space/{id}",
        )

    async def get_all(self) -> ObjectApiResponse[list[dict[str, Any]]]:
        """Get all spaces.

        :return: ObjectApiResponse containing a list of all spaces
        """
        return await self.perform_request(
            "GET",
            "/api/spaces/space",
        )

    async def update(
        self,
        *,
        id: str,
        name: str | None = None,
        description: str | None = None,
        color: str | None = None,
        initials: str | None = None,
        disabled_features: list[str] | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """Update a space.

        :param id: The space ID to update
        :param name: Optional new display name for the space
        :param description: Optional new description
        :param color: Optional new hex color code
        :param initials: Optional new initials
        :param disabled_features: Optional new list of disabled features
        :return: ObjectApiResponse containing the updated space details
        """
        if not id:
            raise ValueError("Parameter 'id' is required")

        # Kibana Spaces API requires the id in the request body
        body: dict[str, Any] = {"id": id}

        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if color is not None:
            body["color"] = color
        if initials is not None:
            body["initials"] = initials
        if disabled_features is not None:
            body["disabledFeatures"] = disabled_features

        return await self.perform_request(
            "PUT",
            f"/api/spaces/space/{id}",
            body=body,
        )

    async def delete(
        self,
        *,
        id: str,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """Delete a space.

        :param id: The space ID to delete
        :return: ObjectApiResponse (typically empty for successful deletion)
        """
        if not id:
            raise ValueError("Parameter 'id' is required")

        return await self.perform_request(
            "DELETE",
            f"/api/spaces/space/{id}",
        )
