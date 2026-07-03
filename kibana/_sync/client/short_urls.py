"""Kibana Short URLs API client."""

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._sync.client import Kibana


class ShortUrlsClient(NamespaceClient):
    """Client for the Kibana Short URLs API.

    Kibana URLs may be long and cumbersome; short URLs are much easier to
    remember and share. Short URLs are created by specifying a locator ID and
    locator parameters. When a short URL is resolved, the locator ID and
    locator parameters are used to redirect the user to the right Kibana page.

    All Short URL APIs are marked as **Technical Preview** in Kibana 9.4 and
    may change in future releases.

    Short URLs are space-scoped saved objects: a short URL created in one
    space is not visible from another space. Every method accepts an optional
    ``space_id`` to target a specific space (``None`` targets the default
    space or the space the client is scoped to).

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a short URL using the legacy short URL locator
        >>> created = client.short_urls.create(
        ...     locator_id="LEGACY_SHORT_URL_LOCATOR",
        ...     params={"url": "/app/dashboards"},
        ... )
        >>> slug = created.body["slug"]
        >>>
        >>> # Resolve it by slug, then delete it
        >>> resolved = client.short_urls.resolve(slug=slug)
        >>> client.short_urls.delete(id=resolved.body["id"])
    """

    def __init__(
        self,
        client: Kibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the ShortUrlsClient.

        Args:
            client: The parent Kibana client instance to delegate requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> short_urls_client = ShortUrlsClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    def create(
        self,
        *,
        locator_id: str,
        params: dict[str, Any],
        slug: str | None = None,
        human_readable_slug: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a short URL.

        Technical preview in 9.4. Creates a Kibana short URL from a locator
        ID and its parameters. When the short URL is resolved, the locator
        redirects the user to the right Kibana page.

        Warning: locator ``params`` are not validated by Kibana, which allows
        you to pass arbitrary and ill-formed data into the API that can break
        Kibana. Make sure any data that you send to the API is properly
        formed.

        Args:
            locator_id: The identifier for the locator (for example,
                ``"LEGACY_SHORT_URL_LOCATOR"`` or ``"DASHBOARD_APP_LOCATOR"``).
            params: An object which contains all necessary parameters for the
                given locator to resolve to a Kibana location.
            slug: A custom short URL slug. The slug is the part of the short
                URL that identifies it. It may consist of latin alphabet
                letters, numbers, and ``-._`` characters and must be between
                3 and 255 characters long.
            human_readable_slug: When ``slug`` is omitted and this is set to
                True, the API generates a random human-readable slug instead
                of a random short string.
            space_id: Optional space ID to create the short URL in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created short URL:
                - id: The identifier for the short URL
                - slug: The slug that resolves to this short URL
                - locator: The locator ``id``, ``version`` and ``state``
                - accessCount / accessDate / createDate: usage metadata

        Raises:
            BadRequestError: If the request body is invalid (e.g. bad slug).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = client.short_urls.create(
            ...     locator_id="LEGACY_SHORT_URL_LOCATOR",
            ...     params={"url": "/app/dashboards"},
            ...     slug="my-dashboards",
            ... )
            >>> print(created.body["slug"])
            my-dashboards
        """
        body: dict[str, Any] = {
            "locatorId": locator_id,
            "params": params,
        }
        if slug is not None:
            body["slug"] = slug
        if human_readable_slug is not None:
            body["humanReadableSlug"] = human_readable_slug

        path = self._build_space_path("/api/short_url", space_id, validate_spaces)
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
        """Get a short URL.

        Technical preview in 9.4. Gets a single Kibana short URL by its
        identifier.

        Args:
            id: The identifier for the short URL.
            space_id: Optional space ID to get the short URL from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the short URL (``id``, ``slug``,
            ``locator``, ``accessCount``, ``accessDate``, ``createDate``).

        Raises:
            NotFoundError: If the short URL does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> url = client.short_urls.get(id="7f2f37bc-...-d64b0e20df6f")
            >>> print(url.body["locator"]["id"])
            LEGACY_SHORT_URL_LOCATOR
        """
        path = self._build_space_path(
            f"/api/short_url/{_quote(id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def resolve(
        self,
        *,
        slug: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Resolve a short URL.

        Technical preview in 9.4. Resolves a Kibana short URL by its slug and
        returns the full short URL object, including the locator that can be
        used to navigate to the target Kibana page.

        Args:
            slug: The slug of the short URL.
            space_id: Optional space ID to resolve the short URL in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the short URL (``id``, ``slug``,
            ``locator``, ``accessCount``, ``accessDate``, ``createDate``).

        Raises:
            NotFoundError: If no short URL exists for the slug.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> resolved = client.short_urls.resolve(slug="my-dashboards")
            >>> print(resolved.body["id"])
            7f2f37bc-...-d64b0e20df6f
        """
        path = self._build_space_path(
            f"/api/short_url/_slug/{_quote(slug)}", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def delete(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a short URL.

        Technical preview in 9.4. Deletes a Kibana short URL by its
        identifier. After deletion, the slug no longer resolves.

        Args:
            id: The identifier for the short URL.
            space_id: Optional space ID to delete the short URL from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty (``null``) body on success.

        Raises:
            NotFoundError: If the short URL does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> client.short_urls.delete(id="7f2f37bc-...-d64b0e20df6f")
        """
        path = self._build_space_path(
            f"/api/short_url/{_quote(id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )
