"""Async Kibana Workflows API client."""

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


class AsyncWorkflowsClient(AsyncNamespaceClient):
    """Async client for the Kibana Workflows API.

    Workflows automate sequences of steps (connector calls, Elasticsearch
    requests, Kibana actions, ...) defined in a YAML document. The Workflows
    APIs are generally available since Kibana 9.4.0.

    Workflows are space-scoped resources: a workflow created in one space is
    not visible from another space. Every method accepts an optional
    ``space_id`` to target a specific space (``None`` targets the default
    space or the space the client is scoped to).

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> yaml_definition = '''
        ... name: my-workflow
        ... enabled: true
        ... triggers:
        ...   - type: manual
        ... steps:
        ...   - name: log_step
        ...     type: console
        ...     with:
        ...       message: "hello world"
        ... '''
        >>> created = await client.workflows.create(yaml=yaml_definition)
        >>> workflow_id = created.body["id"]
        >>>
        >>> run = await client.workflows.run(id=workflow_id, inputs={})
        >>> execution_id = run.body["workflowExecutionId"]
        >>> execution = await client.workflows.get_execution(execution_id=execution_id)
        >>> await client.workflows.delete(id=workflow_id)
    """

    def __init__(
        self,
        client: AsyncKibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the AsyncWorkflowsClient.

        Args:
            client: The parent AsyncKibana client instance to delegate requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> workflows_client = AsyncWorkflowsClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    async def create(
        self,
        *,
        yaml: str,
        id: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a workflow.

        Creates a new workflow from a YAML definition. The definition
        describes the workflow ``name``, ``enabled`` flag, ``triggers`` and
        ``steps`` (see :meth:`get_schema` for the full JSON schema).

        Args:
            yaml: The YAML definition of the workflow (max 1 MiB).
            id: Optional custom workflow ID (3-255 chars, lowercase
                alphanumerics and hyphens, e.g. ``"my-workflow-1"``). If
                omitted, Kibana generates one.
            space_id: Optional space ID to create the workflow in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created workflow, including
            ``id``, ``name``, ``enabled``, ``yaml``, the parsed
            ``definition``, ``valid`` and audit fields (``createdBy``,
            ``createdAt``, ...).

        Raises:
            BadRequestError: If the YAML definition is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = await client.workflows.create(
            ...     id="my-workflow",
            ...     yaml="name: my-workflow\\nenabled: true\\n...",
            ... )
            >>> print(created.body["valid"])
            True
        """
        body: dict[str, Any] = {"yaml": yaml}
        if id is not None:
            body["id"] = id
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/workflows/workflow", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a workflow.

        Retrieves a single workflow by its ID, including its YAML source and
        parsed definition.

        Args:
            id: The workflow ID.
            space_id: Optional space ID to get the workflow from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the workflow (``id``, ``name``,
            ``description``, ``enabled``, ``yaml``, ``definition``,
            ``valid``, audit fields).

        Raises:
            NotFoundError: If the workflow does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> workflow = await client.workflows.get(id="my-workflow")
            >>> print(workflow.body["name"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/workflows/workflow/{_quote(id)}", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update(
        self,
        *,
        id: str,
        yaml: str | None = None,
        name: str | None = None,
        description: str | None = None,
        enabled: bool | None = None,
        tags: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a workflow.

        Partially updates a workflow. Provide a new ``yaml`` definition to
        replace the whole workflow, or individual fields (``name``,
        ``description``, ``enabled``, ``tags``) for targeted changes.

        Args:
            id: The workflow ID.
            yaml: New YAML definition for the workflow.
            name: New workflow name.
            description: New workflow description.
            enabled: Whether the workflow is enabled (it must be enabled to
                be run with :meth:`run`).
            tags: New list of tags.
            space_id: Optional space ID the workflow lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the update summary (``id``,
            ``enabled``, ``valid``, ``validationErrors``,
            ``lastUpdatedAt``, ``lastUpdatedBy``).

        Raises:
            NotFoundError: If the workflow does not exist.
            BadRequestError: If the update payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.workflows.update(id="my-workflow", enabled=True)
        """
        body: dict[str, Any] = {}
        if yaml is not None:
            body["yaml"] = yaml
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if enabled is not None:
            body["enabled"] = enabled
        if tags is not None:
            body["tags"] = tags
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/workflows/workflow/{_quote(id)}", space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete(
        self,
        *,
        id: str,
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a workflow.

        Deletes a single workflow by its ID.

        Args:
            id: The workflow ID.
            force: If True, force deletion even when the workflow has
                running executions (default: False).
            space_id: Optional space ID the workflow lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body on success.

        Raises:
            NotFoundError: If the workflow does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.workflows.delete(id="my-workflow")
        """
        params: dict[str, Any] = {}
        if force is not None:
            params["force"] = force
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/workflows/workflow/{_quote(id)}", space_id)
        return await self.perform_request(
            "DELETE",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def clone(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Clone a workflow.

        Creates a copy of an existing workflow. The clone gets a derived ID
        (e.g. ``"<id>-copy"``) and name (``"<name> Copy"``).

        Args:
            id: The ID of the workflow to clone.
            space_id: Optional space ID the workflow lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the cloned workflow (``id``,
            ``name``, ``yaml``, ``definition``, ...).

        Raises:
            NotFoundError: If the workflow does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> cloned = await client.workflows.clone(id="my-workflow")
            >>> print(cloned.body["id"])
            my-workflow-copy
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/workflows/workflow/{_quote(id)}/clone", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def run(
        self,
        *,
        id: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Run a workflow.

        Triggers a production execution of an **enabled** workflow. Use
        :meth:`test` to run a disabled workflow or an ad-hoc YAML definition.

        Args:
            id: The workflow ID.
            inputs: Key-value inputs for the workflow execution (pass ``{}``
                when the workflow declares no inputs).
            metadata: Optional metadata to attach to the execution.
            space_id: Optional space ID the workflow lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``workflowExecutionId``, the ID of
            the started execution.

        Raises:
            BadRequestError: If the workflow is disabled or inputs are
                invalid.
            NotFoundError: If the workflow does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> run = await client.workflows.run(id="my-workflow", inputs={})
            >>> print(run.body["workflowExecutionId"])
        """
        body: dict[str, Any] = {"inputs": inputs}
        if metadata is not None:
            body["metadata"] = metadata
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/workflows/workflow/{_quote(id)}/run", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_all(
        self,
        *,
        query: str | None = None,
        size: int | None = None,
        page: int | None = None,
        enabled: list[bool] | None = None,
        created_by: list[str] | None = None,
        tags: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get (search) workflows.

        Searches workflows with optional text query, filters and pagination.

        Args:
            query: Text query matched against workflow names/descriptions.
            size: Number of workflows per page (minimum 1).
            page: Page number (minimum 1).
            enabled: Filter by enabled state; a list so both states can be
                requested, e.g. ``[True]`` or ``[True, False]``.
            created_by: Filter by creator usernames.
            tags: Filter by tags.
            space_id: Optional space ID to search in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``results`` (list of workflow
            summaries), ``total``, ``page`` and ``size``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = await client.workflows.get_all(query="my-workflow", size=10)
            >>> print(found.body["total"])
        """
        params: dict[str, Any] = {}
        if query is not None:
            params["query"] = query
        if size is not None:
            params["size"] = size
        if page is not None:
            params["page"] = page
        if enabled is not None:
            params["enabled"] = enabled
        if created_by is not None:
            params["createdBy"] = created_by
        if tags is not None:
            params["tags"] = tags
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/workflows", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def bulk_create(
        self,
        *,
        workflows: list[dict[str, Any]],
        overwrite: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk create workflows.

        Creates up to 500 workflows in one request.

        Args:
            workflows: List of workflow objects, each with a required
                ``"yaml"`` key and an optional ``"id"`` key.
            overwrite: If True, overwrite workflows that already exist with
                the given IDs (default: False).
            space_id: Optional space ID to create the workflows in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``created`` (list of created
            workflows) and per-entry errors for the ones that failed.

        Raises:
            BadRequestError: If the payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.workflows.bulk_create(
            ...     workflows=[{"id": "wf-1", "yaml": "name: wf-1\\n..."}],
            ... )
            >>> print(len(result.body["created"]))
            1
        """
        params: dict[str, Any] = {}
        if overwrite is not None:
            params["overwrite"] = overwrite
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/workflows", space_id)
        return await self.perform_request(
            "POST",
            path,
            params=params,
            headers={"accept": "application/json"},
            body={"workflows": workflows},
        )

    async def bulk_delete(
        self,
        *,
        ids: list[str],
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk delete workflows.

        Deletes up to 1000 workflows by ID in one request.

        Args:
            ids: List of workflow IDs to delete.
            force: If True, force deletion even when workflows have running
                executions (default: False).
            space_id: Optional space ID the workflows live in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``total``, ``deleted`` and
            ``failures``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.workflows.bulk_delete(ids=["wf-1", "wf-2"])
            >>> print(result.body["deleted"])
            2
        """
        params: dict[str, Any] = {}
        if force is not None:
            params["force"] = force
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/workflows", space_id)
        return await self.perform_request(
            "DELETE",
            path,
            params=params,
            headers={"accept": "application/json"},
            body={"ids": ids},
        )

    async def mget(
        self,
        *,
        ids: list[str],
        source: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get workflows by IDs (multi-get).

        Looks up 1-500 workflows by ID in one request.

        Args:
            ids: List of workflow IDs to look up.
            source: Optional list of source fields to include in each
                returned workflow (1-10 fields).
            space_id: Optional space ID the workflows live in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is the list of found workflows
            (a ``ListApiResponse`` at runtime).

        Raises:
            BadRequestError: If the payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = await client.workflows.mget(ids=["wf-1", "wf-2"])
            >>> print([wf["id"] for wf in found.body])
        """
        body: dict[str, Any] = {"ids": ids}
        if source is not None:
            body["source"] = source
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/workflows/mget", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def export(
        self,
        *,
        ids: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Export workflows.

        Exports 1-500 workflows as normalized YAML documents suitable for
        re-import via :meth:`bulk_create`.

        Args:
            ids: List of workflow IDs to export.
            space_id: Optional space ID the workflows live in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``entries`` (list of ``{"id",
            "yaml"}`` objects) and a ``manifest`` with export counts.

        Raises:
            BadRequestError: If the payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> exported = await client.workflows.export(ids=["wf-1"])
            >>> print(exported.body["entries"][0]["yaml"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/workflows/export", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"ids": ids},
        )

    async def get_aggs(
        self,
        *,
        fields: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get workflow aggregations.

        Aggregates workflow field values (e.g. distinct ``tags`` or
        ``createdBy`` values with document counts), typically used to build
        filter UIs.

        Args:
            fields: Fields to aggregate on (1-25 fields, e.g.
                ``["tags", "createdBy"]``).
            space_id: Optional space ID to aggregate in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse mapping each requested field to a list of
            ``{"key", "doc_count"}`` buckets.

        Raises:
            BadRequestError: If ``fields`` is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> aggs = await client.workflows.get_aggs(fields=["createdBy"])
            >>> print(aggs.body["createdBy"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/workflows/aggs", space_id)
        return await self.perform_request(
            "GET",
            path,
            params={"fields": fields},
            headers={"accept": "application/json"},
        )

    async def get_connectors(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get available connectors.

        Lists connector types (and existing connector instances) that can be
        used in workflow steps.

        Args:
            space_id: Optional space ID to list connectors for.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``connectorTypes``, a mapping of
            action type ID (e.g. ``".slack"``) to its metadata and
            ``instances``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> connectors = await client.workflows.get_connectors()
            >>> print(sorted(connectors.body["connectorTypes"]))
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/workflows/connectors", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def get_schema(
        self,
        *,
        loose: bool,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the workflow JSON schema.

        Returns the JSON schema (draft-07) that workflow YAML definitions
        are validated against — useful for editor integration and
        client-side validation.

        Args:
            loose: Required. If True, return a loose variant of the schema
                (more permissive validation); if False, the strict schema.
            space_id: Optional space ID.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the JSON schema document.

        Raises:
            BadRequestError: If ``loose`` is missing or invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> schema = await client.workflows.get_schema(loose=False)
            >>> print(schema.body["$schema"])
            http://json-schema.org/draft-07/schema#
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/workflows/schema", space_id)
        return await self.perform_request(
            "GET",
            path,
            params={"loose": loose},
            headers={"accept": "application/json"},
        )

    async def get_stats(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get workflow statistics.

        Returns aggregate statistics about workflows and their executions.

        Args:
            space_id: Optional space ID to get statistics for.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``workflows`` (``enabled`` /
            ``disabled`` counts) and ``executions`` statistics.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> stats = await client.workflows.get_stats()
            >>> print(stats.body["workflows"])
            {'enabled': 1, 'disabled': 0}
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/workflows/stats", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def test(
        self,
        *,
        inputs: dict[str, Any],
        workflow_id: str | None = None,
        workflow_yaml: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Test a workflow.

        Starts a test execution of either an existing workflow
        (``workflow_id``) or an ad-hoc YAML definition (``workflow_yaml``).
        Test runs work even when the workflow is disabled.

        Args:
            inputs: Key-value inputs for the test execution (pass ``{}``
                when the workflow declares no inputs).
            workflow_id: ID of an existing workflow to test.
            workflow_yaml: YAML definition to test (alternative to
                ``workflow_id``).
            space_id: Optional space ID.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``workflowExecutionId``, the ID of
            the started test execution.

        Raises:
            BadRequestError: If the workflow reference or the inputs are
                invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> test_run = await client.workflows.test(
            ...     workflow_id="my-workflow", inputs={}
            ... )
            >>> print(test_run.body["workflowExecutionId"])
        """
        body: dict[str, Any] = {"inputs": inputs}
        if workflow_id is not None:
            body["workflowId"] = workflow_id
        if workflow_yaml is not None:
            body["workflowYaml"] = workflow_yaml
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/workflows/test", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def test_step(
        self,
        *,
        step_id: str,
        context_override: dict[str, Any],
        workflow_yaml: str,
        workflow_id: str | None = None,
        execution_context: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Test a single workflow step.

        Starts a test execution of one step from a workflow YAML definition,
        with optional context overrides.

        Args:
            step_id: ID (name) of the step to test.
            context_override: Context overrides for the step execution
                (pass ``{}`` for none).
            workflow_yaml: YAML definition of the workflow containing the
                step.
            workflow_id: Optional ID of the workflow containing the step.
            execution_context: Optional execution context for the step.
            space_id: Optional space ID.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``workflowExecutionId``, the ID of
            the started step test execution.

        Raises:
            BadRequestError: If the step or YAML definition is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> test_run = await client.workflows.test_step(
            ...     step_id="log_step",
            ...     context_override={},
            ...     workflow_yaml="name: my-workflow\\n...",
            ... )
            >>> print(test_run.body["workflowExecutionId"])
        """
        body: dict[str, Any] = {
            "stepId": step_id,
            "contextOverride": context_override,
            "workflowYaml": workflow_yaml,
        }
        if workflow_id is not None:
            body["workflowId"] = workflow_id
        if execution_context is not None:
            body["executionContext"] = execution_context
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/workflows/step/test", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_executions(
        self,
        *,
        workflow_id: str,
        statuses: list[str] | None = None,
        execution_types: list[str] | None = None,
        executed_by: list[str] | None = None,
        omit_step_runs: bool | None = None,
        page: int | None = None,
        size: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get workflow executions.

        Lists the executions of a workflow, with optional filters and
        pagination.

        Args:
            workflow_id: The workflow ID.
            statuses: Filter by execution statuses (``"pending"``,
                ``"waiting"``, ``"waiting_for_input"``, ``"running"``,
                ``"completed"``, ``"failed"``, ``"cancelled"``,
                ``"timed_out"``, ``"skipped"``).
            execution_types: Filter by execution type (``"test"`` and/or
                ``"production"``).
            executed_by: Filter by usernames that triggered the executions.
            omit_step_runs: If True, omit step run details from the results.
            page: Page number (minimum 1).
            size: Number of executions per page (1-100).
            space_id: Optional space ID the workflow lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``results`` (list of execution
            summaries with ``id``, ``status``, ``startedAt``, ...),
            ``total``, ``page`` and ``size``.

        Raises:
            NotFoundError: If the workflow does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> executions = await client.workflows.get_executions(
            ...     workflow_id="my-workflow", statuses=["completed"]
            ... )
            >>> print(executions.body["total"])
        """
        params: dict[str, Any] = {}
        if statuses is not None:
            params["statuses"] = statuses
        if execution_types is not None:
            params["executionTypes"] = execution_types
        if executed_by is not None:
            params["executedBy"] = executed_by
        if omit_step_runs is not None:
            params["omitStepRuns"] = omit_step_runs
        if page is not None:
            params["page"] = page
        if size is not None:
            params["size"] = size
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/workflows/workflow/{_quote(workflow_id)}/executions", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def get_step_executions(
        self,
        *,
        workflow_id: str,
        step_id: str | None = None,
        include_input: bool | None = None,
        include_output: bool | None = None,
        page: int | None = None,
        size: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get workflow step executions.

        Lists step-level executions across the runs of a workflow.

        Args:
            workflow_id: The workflow ID.
            step_id: Filter by a specific step ID (name).
            include_input: If True, include step input in the results.
            include_output: If True, include step output in the results.
            page: Page number (minimum 1).
            size: Number of step executions per page (1-100).
            space_id: Optional space ID the workflow lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``results`` (list of step
            executions with ``id``, ``stepId``, ``status``, ...), ``total``,
            ``page`` and ``size``.

        Raises:
            NotFoundError: If the workflow does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> steps = await client.workflows.get_step_executions(
            ...     workflow_id="my-workflow", step_id="log_step"
            ... )
            >>> print(steps.body["results"][0]["status"])
        """
        params: dict[str, Any] = {}
        if step_id is not None:
            params["stepId"] = step_id
        if include_input is not None:
            params["includeInput"] = include_input
        if include_output is not None:
            params["includeOutput"] = include_output
        if page is not None:
            params["page"] = page
        if size is not None:
            params["size"] = size
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/workflows/workflow/{_quote(workflow_id)}/executions/steps", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def cancel_all_executions(
        self,
        *,
        workflow_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Cancel all active workflow executions.

        Cancels every active (pending/waiting/running) execution of a
        workflow. Completed executions are unaffected.

        Args:
            workflow_id: The workflow ID.
            space_id: Optional space ID the workflow lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body on success.

        Raises:
            NotFoundError: If the workflow does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.workflows.cancel_all_executions(
            ...     workflow_id="my-workflow"
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/workflows/workflow/{_quote(workflow_id)}/executions/cancel", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def get_execution(
        self,
        *,
        execution_id: str,
        include_input: bool | None = None,
        include_output: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a workflow execution.

        Retrieves a single workflow execution by its ID, including status,
        timing, the workflow definition snapshot and step executions.

        Args:
            execution_id: The execution ID (as returned by :meth:`run` or
                :meth:`test`).
            include_input: If True, include execution input in the response.
            include_output: If True, include execution output in the
                response.
            space_id: Optional space ID the execution lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the execution (``id``, ``status``,
            ``workflowId``, ``isTestRun``, ``startedAt``, ``finishedAt``,
            ``stepExecutions``, ...).

        Raises:
            NotFoundError: If the execution does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> execution = await client.workflows.get_execution(
            ...     execution_id="be42ad95-..."
            ... )
            >>> print(execution.body["status"])
            completed
        """
        params: dict[str, Any] = {}
        if include_input is not None:
            params["includeInput"] = include_input
        if include_output is not None:
            params["includeOutput"] = include_output
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/workflows/executions/{_quote(execution_id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def cancel_execution(
        self,
        *,
        execution_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Cancel a workflow execution.

        Requests cancellation of a single workflow execution. Cancelling an
        already-finished execution is a no-op.

        Args:
            execution_id: The execution ID.
            space_id: Optional space ID the execution lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body on success.

        Raises:
            NotFoundError: If the execution does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.workflows.cancel_execution(execution_id="be42ad95-...")
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/workflows/executions/{_quote(execution_id)}/cancel", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def resume_execution(
        self,
        *,
        execution_id: str,
        input: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Resume a workflow execution.

        Resumes an execution that is in the ``waiting_for_input`` status,
        providing the input it is waiting for.

        Args:
            execution_id: The execution ID.
            input: Input data to resume the execution with (pass ``{}`` for
                none).
            space_id: Optional space ID the execution lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the resume result.

        Raises:
            ConflictError: If the execution is not in the
                ``waiting_for_input`` status.
            NotFoundError: If the execution does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.workflows.resume_execution(
            ...     execution_id="be42ad95-...", input={"approved": True}
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/workflows/executions/{_quote(execution_id)}/resume", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"input": input},
        )

    async def get_execution_children(
        self,
        *,
        execution_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get child executions.

        Lists the child executions spawned by a workflow execution (e.g.
        sub-workflow runs).

        Args:
            execution_id: The parent execution ID.
            space_id: Optional space ID the execution lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is the list of child executions
            (a ``ListApiResponse`` at runtime; empty when there are none).

        Raises:
            NotFoundError: If the execution does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> children = await client.workflows.get_execution_children(
            ...     execution_id="be42ad95-..."
            ... )
            >>> print(len(children.body))
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/workflows/executions/{_quote(execution_id)}/children", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def get_execution_logs(
        self,
        *,
        execution_id: str,
        step_execution_id: str | None = None,
        size: int | None = None,
        page: int | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get execution logs.

        Retrieves the log entries produced by a workflow execution, with
        optional step filtering, sorting and pagination.

        Args:
            execution_id: The execution ID.
            step_execution_id: Filter logs to a single step execution.
            size: Number of log entries per page (1-100, default 100).
            page: Page number (minimum 1, default 1).
            sort_field: Field to sort by (e.g. ``"timestamp"``).
            sort_order: Sort order, ``"asc"`` or ``"desc"``.
            space_id: Optional space ID the execution lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``logs`` (list of entries with
            ``timestamp``, ``level``, ``message``, ...), ``total``, ``page``
            and ``size``.

        Raises:
            NotFoundError: If the execution does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> logs = await client.workflows.get_execution_logs(
            ...     execution_id="be42ad95-...", sort_order="asc"
            ... )
            >>> for entry in logs.body["logs"]:
            ...     print(entry["level"], entry["message"])
        """
        params: dict[str, Any] = {}
        if step_execution_id is not None:
            params["stepExecutionId"] = step_execution_id
        if size is not None:
            params["size"] = size
        if page is not None:
            params["page"] = page
        if sort_field is not None:
            params["sortField"] = sort_field
        if sort_order is not None:
            params["sortOrder"] = sort_order
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/workflows/executions/{_quote(execution_id)}/logs", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def get_step_execution(
        self,
        *,
        execution_id: str,
        step_execution_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a step execution.

        Retrieves a single step execution from a workflow execution.

        Args:
            execution_id: The workflow execution ID.
            step_execution_id: The step execution ID (as listed in
                :meth:`get_step_executions` or in the execution's
                ``stepExecutions``).
            space_id: Optional space ID the execution lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the step execution (``id``,
            ``stepId``, ``stepType``, ``status``, ``startedAt``, ...).

        Raises:
            NotFoundError: If the execution or step execution does not
                exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> step = await client.workflows.get_step_execution(
            ...     execution_id="be42ad95-...",
            ...     step_execution_id="27e59f68d0d8...",
            ... )
            >>> print(step.body["stepId"], step.body["status"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/workflows/executions/{_quote(execution_id)}"
            f"/step/{_quote(step_execution_id)}",
            space_id,
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )
