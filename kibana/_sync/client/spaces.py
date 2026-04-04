"""Kibana Spaces API client."""

from typing import Any

from elastic_transport import ObjectApiResponse

from .utils import NamespaceClient


class SpacesClient(NamespaceClient):
    """Client for Kibana Spaces API.

    Spaces allow you to organize your Kibana objects (dashboards, visualizations,
    index patterns, etc.) into separate, isolated areas. Each space has its own
    set of saved objects and can be used to implement multi-tenancy, enabling
    different teams or projects to work independently within the same Kibana instance.

    Key features of Spaces:
        - Isolated saved objects per space
        - Customizable appearance (color, initials)
        - Feature-level access control (disable specific features per space)
        - URL-based space selection (/s/space-id/app/...)
        - Default space always exists and cannot be deleted

    Common use cases:
        - Multi-tenant SaaS applications
        - Department or team isolation
        - Development/staging/production environments
        - Customer-specific dashboards and visualizations

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a space for marketing team
        >>> space = client.spaces.create(
        ...     id="marketing",
        ...     name="Marketing Team",
        ...     description="Space for marketing analytics",
        ...     color="#FF6B6B",
        ...     initials="MK"
        ... )
        >>>
        >>> # List all spaces
        >>> spaces = client.spaces.get_all()
        >>> for space in spaces.body:
        ...     print(f"{space['name']} ({space['id']})")
        >>>
        >>> # Work within a specific space
        >>> marketing_client = client.space("marketing")
        >>> connectors = marketing_client.actions.get_all()
    """

    def create(
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

        Creates a new Kibana space with the specified configuration. The space ID
        must be unique and URL-friendly (lowercase, no special characters except
        hyphens and underscores).

        Args:
            id: Unique identifier for the space. Must be URL-friendly (lowercase,
                alphanumeric, hyphens, underscores). Cannot be changed after creation.
                Examples: "marketing", "team-a", "prod_env"
            name: Display name for the space. This is shown in the Kibana UI and
                can contain any characters.
            description: Optional description explaining the purpose of the space.
                Displayed in the space selector.
            color: Optional hex color code for the space avatar (e.g., "#FF0000",
                "#00FF00"). Used in the Kibana UI for visual identification.
            initials: Optional initials to display in the space avatar (max 2
                characters). If not provided, Kibana generates them from the name.
            disabled_features: Optional list of Kibana feature IDs to disable in
                this space. Common features include:
                - "discover": Discover app
                - "dashboard": Dashboards
                - "canvas": Canvas
                - "maps": Maps
                - "ml": Machine Learning
                - "apm": APM
                - "infrastructure": Infrastructure monitoring
                - "logs": Logs
                - "uptime": Uptime monitoring

        Returns:
            ObjectApiResponse containing the created space details including id,
            name, description, color, initials, and disabledFeatures.

        Raises:
            ValueError: If required parameters (id, name) are missing.
            BadRequestError: If the space ID format is invalid.
            ConflictError: If a space with the same ID already exists.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to create spaces.

        Example:
            >>> # Create a basic space
            >>> space = client.spaces.create(
            ...     id="engineering",
            ...     name="Engineering Team"
            ... )
            >>>
            >>> # Create a space with full configuration
            >>> space = client.spaces.create(
            ...     id="marketing",
            ...     name="Marketing Analytics",
            ...     description="Marketing team's analytics workspace",
            ...     color="#FF6B6B",
            ...     initials="MA",
            ...     disabled_features=["ml", "apm"]
            ... )
            >>> print(space.body["id"])
            marketing
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

        return self.perform_request(
            "POST",
            "/api/spaces/space",
            body=body,
        )

    def get(
        self,
        *,
        id: str,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """Get a space by ID.

        Retrieves detailed information about a specific space including its
        configuration, enabled features, and metadata.

        Args:
            id: The space ID to retrieve (e.g., "default", "marketing").

        Returns:
            ObjectApiResponse containing the space details including id, name,
            description, color, initials, disabledFeatures, and metadata.

        Raises:
            ValueError: If the id parameter is missing.
            NotFoundError: If the space does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to view the space.

        Example:
            >>> space = client.spaces.get(id="marketing")
            >>> print(space.body["name"])
            Marketing Team
            >>> print(space.body["color"])
            #FF6B6B
            >>> print(space.body.get("disabledFeatures", []))
            ['ml', 'apm']
        """
        if not id:
            raise ValueError("Parameter 'id' is required")

        return self.perform_request(
            "GET",
            f"/api/spaces/space/{id}",
        )

    def get_all(self) -> ObjectApiResponse[list[dict[str, Any]]]:
        """Get all spaces.

        Retrieves a list of all spaces in the Kibana instance that the
        authenticated user has access to view.

        Returns:
            ObjectApiResponse containing a list of all spaces. Each space
            includes id, name, description, color, initials, disabledFeatures,
            and other metadata.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to list spaces.

        Example:
            >>> spaces = client.spaces.get_all()
            >>> for space in spaces.body:
            ...     print(f"{space['name']} ({space['id']})")
            ...     if space.get('description'):
            ...         print(f"  Description: {space['description']}")
            Default (default)
            Marketing Team (marketing)
              Description: Marketing team's analytics workspace
            Engineering (engineering)
        """
        return self.perform_request(
            "GET",
            "/api/spaces/space",
        )

    def update(
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

        Updates the configuration of an existing space. Only the provided
        parameters will be updated; omitted parameters remain unchanged.
        Note that the space ID cannot be changed after creation.

        Args:
            id: The space ID to update (cannot be changed).
            name: Optional new display name for the space.
            description: Optional new description. Pass empty string to clear.
            color: Optional new hex color code (e.g., "#00FF00").
            initials: Optional new initials (max 2 characters).
            disabled_features: Optional new list of disabled feature IDs.
                This replaces the entire list, not appends to it.

        Returns:
            ObjectApiResponse containing the updated space details.

        Raises:
            ValueError: If the id parameter is missing.
            NotFoundError: If the space does not exist.
            BadRequestError: If the update parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to update the space.

        Example:
            >>> # Update space name and color
            >>> space = client.spaces.update(
            ...     id="marketing",
            ...     name="Marketing & Sales",
            ...     color="#00FF00"
            ... )
            >>>
            >>> # Disable additional features
            >>> space = client.spaces.update(
            ...     id="marketing",
            ...     disabled_features=["ml", "apm", "canvas"]
            ... )
            >>>
            >>> # Clear description
            >>> space = client.spaces.update(
            ...     id="marketing",
            ...     description=""
            ... )
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

        return self.perform_request(
            "PUT",
            f"/api/spaces/space/{id}",
            body=body,
        )

    def delete(
        self,
        *,
        id: str,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """Delete a space.

        Permanently deletes a space and all its associated saved objects
        (dashboards, visualizations, index patterns, etc.). This operation
        cannot be undone.

        Warning:
            Deleting a space will permanently delete all saved objects within
            that space. This includes dashboards, visualizations, saved searches,
            and other Kibana objects. The default space cannot be deleted.

        Args:
            id: The space ID to delete. Cannot be "default".

        Returns:
            ObjectApiResponse, typically empty for successful deletion.

        Raises:
            ValueError: If the id parameter is missing.
            NotFoundError: If the space does not exist.
            BadRequestError: If attempting to delete the default space.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to delete the space.

        Example:
            >>> # Delete a space
            >>> client.spaces.delete(id="old-project")
            >>>
            >>> # Verify deletion
            >>> try:
            ...     client.spaces.get(id="old-project")
            ... except NotFoundError:
            ...     print("Space successfully deleted")
            Space successfully deleted
        """
        if not id:
            raise ValueError("Parameter 'id' is required")

        return self.perform_request(
            "DELETE",
            f"/api/spaces/space/{id}",
        )
