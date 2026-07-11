"""Async Kibana Logstash Configuration Management API client."""

from __future__ import annotations

from typing import Any

from elastic_transport import ObjectApiResponse

from .utils import AsyncNamespaceClient, _quote


class AsyncLogstashClient(AsyncNamespaceClient):
    """Async client for the Kibana Logstash Configuration Management API.

    Manage centrally-managed Logstash pipelines that are stored in
    Elasticsearch and distributed to Logstash instances configured with
    ``xpack.management`` (centralized pipeline management). A running
    Logstash instance is not required to create, read, update, or delete
    pipeline definitions.

    All endpoints in this namespace are in **Technical Preview** in
    Kibana 9.4 and are not space-scoped.

    Required privileges: the ``logstash_admin`` built-in role (or a
    customized Logstash writer role) for write operations, and the
    ``logstash_admin`` built-in role (or a customized Logstash reader
    role) for read operations.

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a pipeline
        >>> await client.logstash.create_or_update(
        ...     id="hello-world",
        ...     pipeline="input { stdin {} } output { stdout {} }",
        ...     description="Just a simple pipeline",
        ... )
        >>>
        >>> # List all pipelines
        >>> for p in (await client.logstash.get_all()).body["pipelines"]:
        ...     print(p["id"])
        hello-world
    """

    async def get_all(self) -> ObjectApiResponse[Any]:
        """Get all Logstash pipelines.

        Get a list of all centrally-managed Logstash pipelines.
        Limit the number of pipelines to 10,000 or fewer; as the number of
        pipelines nears and surpasses 10,000, you may see performance issues
        on Kibana. The ``username`` property appears in the response when
        security is enabled and depends on when the pipeline was created or
        last updated.

        Technical preview in 9.4.

        Returns:
            ObjectApiResponse with a ``pipelines`` list; each entry contains
            ``id``, ``description``, ``last_modified`` and, when security is
            enabled, ``username``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks the ``logstash_admin``
                role or a customized Logstash reader role.

        Example:
            >>> response = await client.logstash.get_all()
            >>> for pipeline in response.body["pipelines"]:
            ...     print(pipeline["id"], pipeline.get("description", ""))
            hello-world Just a simple pipeline
        """
        return await self.perform_request(
            "GET",
            "/api/logstash/pipelines",
            headers={"accept": "application/json"},
        )

    async def get(self, *, id: str) -> ObjectApiResponse[Any]:
        """Get a Logstash pipeline.

        Get information for a centrally-managed Logstash pipeline.

        Technical preview in 9.4.

        Args:
            id: An identifier for the pipeline.

        Returns:
            ObjectApiResponse with the pipeline document: ``id``,
            ``description``, ``pipeline`` (the pipeline definition),
            ``settings`` and, when security is enabled, ``username``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks the ``logstash_admin``
                role or a customized Logstash reader role.
            NotFoundError: If no pipeline exists with the given ``id``.

        Example:
            >>> response = await client.logstash.get(id="hello-world")
            >>> print(response.body["pipeline"])
            input { stdin {} } output { stdout {} }
        """
        return await self.perform_request(
            "GET",
            f"/api/logstash/pipeline/{_quote(id)}",
            headers={"accept": "application/json"},
        )

    async def create_or_update(
        self,
        *,
        id: str,
        pipeline: str,
        description: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create or update a Logstash pipeline.

        Create a centrally-managed Logstash pipeline or update an existing
        pipeline (the operation is an upsert on ``id``).

        Technical preview in 9.4.

        Args:
            id: An identifier for the pipeline. It must begin with a letter
                or underscore and can contain only letters, underscores,
                dashes, hyphens, and numbers.
            pipeline: A definition for the pipeline, as a Logstash pipeline
                configuration string.
            description: A description of the pipeline.
            settings: Supported settings, represented as object keys,
                include ``pipeline.workers``, ``pipeline.batch.size``,
                ``pipeline.batch.delay``, ``pipeline.ecs_compatibility``,
                ``pipeline.ordered``, ``queue.type``, ``queue.max_bytes``
                and ``queue.checkpoint.writes``.

        Returns:
            ObjectApiResponse with an empty body (the server replies
            ``204 No Content`` on success).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks the ``logstash_admin``
                role or a customized Logstash writer role.
            BadRequestError: If the pipeline identifier or body is invalid.

        Example:
            >>> await client.logstash.create_or_update(
            ...     id="hello-world",
            ...     pipeline="input { stdin {} } output { stdout {} }",
            ...     description="Just a simple pipeline",
            ...     settings={"queue.type": "persisted"},
            ... )
        """
        body: dict[str, Any] = {"pipeline": pipeline}
        if description is not None:
            body["description"] = description
        if settings is not None:
            body["settings"] = settings
        return await self.perform_request(
            "PUT",
            f"/api/logstash/pipeline/{_quote(id)}",
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete(self, *, id: str) -> ObjectApiResponse[Any]:
        """Delete a Logstash pipeline.

        Delete a centrally-managed Logstash pipeline.

        Technical preview in 9.4.

        Args:
            id: An identifier for the pipeline.

        Returns:
            ObjectApiResponse with an empty body (the server replies
            ``204 No Content`` on success).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If the user lacks the ``logstash_admin``
                role or a customized Logstash writer role.
            NotFoundError: If no pipeline exists with the given ``id``.

        Example:
            >>> await client.logstash.delete(id="hello-world")
        """
        return await self.perform_request(
            "DELETE",
            f"/api/logstash/pipeline/{_quote(id)}",
            headers={"accept": "application/json"},
        )
