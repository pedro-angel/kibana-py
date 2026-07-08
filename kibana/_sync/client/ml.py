"""Kibana Machine Learning API client."""

from typing import Any

from elastic_transport import ObjectApiResponse

from .utils import NamespaceClient


class MlClient(NamespaceClient):
    """Client for the Kibana Machine Learning API.

    Provides access to the machine learning saved objects APIs, which keep
    Kibana saved objects in sync with machine learning jobs and trained
    models, and manage the Kibana spaces those objects belong to.

    All operations are space-scoped: pass ``space_id`` to target a specific
    Kibana space, or omit it to target the default space.

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Simulate a sync to see what would change
        >>> result = client.ml.sync(simulate=True)
        >>> print(result.body["savedObjectsCreated"])
    """

    def sync(
        self,
        *,
        simulate: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Sync machine learning saved objects.

        Synchronizes Kibana saved objects for machine learning jobs and
        trained models. You must have ``all`` privileges for the **Machine
        Learning** feature in the **Analytics** section of the Kibana
        feature privileges. This API runs automatically when you start
        Kibana and periodically thereafter.

        Args:
            simulate: When ``True``, simulates the synchronization by
                returning only the list of actions that would be performed.
            space_id: Optional space ID to scope the operation to. ``None``
                targets the default space.
            validate_spaces: Override the client-level space validation
                setting for this call.

        Returns:
            ObjectApiResponse with the sync results:
                - ``savedObjectsCreated``: Saved objects created for jobs or
                  trained models that were missing them.
                - ``savedObjectsDeleted``: Saved objects deleted because the
                  referenced job or trained model no longer exists.
                - ``datafeedsAdded``: Datafeed identifiers added to anomaly
                  detection job saved objects that were missing them.
                - ``datafeedsRemoved``: Datafeed identifiers removed because
                  the datafeed no longer exists.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> # Dry run: list actions without performing them
            >>> result = client.ml.sync(simulate=True)
            >>> print(result.body["savedObjectsCreated"])
            >>>
            >>> # Perform the synchronization in the "marketing" space
            >>> result = client.ml.sync(space_id="marketing")
        """
        params: dict[str, Any] = {}
        if simulate is not None:
            params["simulate"] = simulate

        path = self._build_space_path(
            "/api/ml/saved_objects/sync",
            space_id,
            validate_spaces=validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def update_jobs_spaces(
        self,
        *,
        job_ids: list[str],
        job_type: str,
        spaces_to_add: list[str],
        spaces_to_remove: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update the spaces assigned to machine learning jobs.

        Updates a list of machine learning jobs to add and/or remove them
        from the given Kibana spaces.

        Args:
            job_ids: Identifiers of the jobs to update.
            job_type: Type of the jobs: ``"anomaly-detector"`` or
                ``"data-frame-analytics"``.
            spaces_to_add: Space IDs to add the jobs to (may be empty).
            spaces_to_remove: Space IDs to remove the jobs from (``["*"]``
                removes them from all current spaces; may be empty).
            space_id: Optional space ID to scope the operation to. ``None``
                targets the default space.
            validate_spaces: Override the client-level space validation
                setting for this call.

        Returns:
            ObjectApiResponse mapping each job ID to its result, e.g.
            ``{"my-job": {"success": True, "type": "anomaly-detector"}}``.
            Failures are reported per job with ``success: False`` and an
            ``error`` message, while the HTTP status remains 200.

        Raises:
            BadRequestError: If the request body fails validation (e.g. an
                unknown ``job_type``).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = client.ml.update_jobs_spaces(
            ...     job_ids=["my-job"],
            ...     job_type="anomaly-detector",
            ...     spaces_to_add=["marketing"],
            ...     spaces_to_remove=[],
            ... )
            >>> print(result.body["my-job"]["success"])
        """
        body: dict[str, Any] = {
            "jobIds": job_ids,
            "jobType": job_type,
            "spacesToAdd": spaces_to_add,
            "spacesToRemove": spaces_to_remove,
        }

        path = self._build_space_path(
            "/api/ml/saved_objects/update_jobs_spaces",
            space_id,
            validate_spaces=validate_spaces,
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def update_trained_models_spaces(
        self,
        *,
        model_ids: list[str],
        spaces_to_add: list[str],
        spaces_to_remove: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update the spaces assigned to trained models.

        Updates a list of trained models to add and/or remove them from the
        given Kibana spaces.

        Args:
            model_ids: Identifiers of the trained models to update.
            spaces_to_add: Space IDs to add the models to (may be empty).
            spaces_to_remove: Space IDs to remove the models from (``["*"]``
                removes them from all current spaces; may be empty).
            space_id: Optional space ID to scope the operation to. ``None``
                targets the default space.
            validate_spaces: Override the client-level space validation
                setting for this call.

        Returns:
            ObjectApiResponse mapping each model ID to its result, e.g.
            ``{"my-model": {"success": True, "type": "trained-model"}}``.
            Failures are reported per model with ``success: False`` and an
            ``error`` message, while the HTTP status remains 200.

        Raises:
            BadRequestError: If the request body fails validation.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = client.ml.update_trained_models_spaces(
            ...     model_ids=["my-model"],
            ...     spaces_to_add=["marketing"],
            ...     spaces_to_remove=[],
            ... )
            >>> print(result.body["my-model"]["success"])
        """
        body: dict[str, Any] = {
            "modelIds": model_ids,
            "spacesToAdd": spaces_to_add,
            "spacesToRemove": spaces_to_remove,
        }

        path = self._build_space_path(
            "/api/ml/saved_objects/update_trained_models_spaces",
            space_id,
            validate_spaces=validate_spaces,
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )
