"""Kibana Task Manager API client."""

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient

if TYPE_CHECKING:
    from kibana._sync.client import Kibana


class TaskManagerClient(NamespaceClient):
    """Client for the Kibana Task Manager API.

    Task Manager is the Kibana service that runs background tasks such as
    alerting rules, actions, reporting jobs, and telemetry collection. This
    API exposes the health and performance statistics of the task manager
    on the Kibana instance that serves the request.

    The Task Manager API is not space-scoped: it always operates at the
    Kibana instance level.

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Check task manager health
        >>> health = client.task_manager.health()
        >>> print(health.body["status"])
        OK
    """

    def __init__(self, client: Kibana) -> None:
        """Initialize the TaskManagerClient.

        Args:
            client: The parent Kibana client instance to delegate requests to.

        Example:
            >>> task_manager_client = TaskManagerClient(kibana_client)
        """
        super().__init__(client)

    def health(self) -> ObjectApiResponse[dict[str, Any]]:
        """Get the health status of the Kibana task manager.

        Returns a health report for the task manager on the Kibana instance
        that handles the request. The report aggregates several monitored
        stats sections, each with its own ``timestamp``, ``value`` and
        ``status``:

            - configuration: effective task manager settings (poll interval,
              capacity, claim strategy, execution thresholds, ...)
            - runtime: polling and task execution performance (drift,
              load, execution duration/result frequency per task type)
            - workload: the number and types of tasks in the system and
              their schedule density
            - capacity_estimation: an estimate of whether the deployed
              Kibana instances can handle the observed workload

        Returns:
            ObjectApiResponse containing the health report with the
            following structure:

            - ``id`` -- UUID of the Kibana instance that produced the report
            - ``timestamp`` -- Time at which the report was generated
            - ``status`` -- Overall health status (``OK``, ``warn`` or
              ``error``)
            - ``last_update`` -- Time at which the stats were last refreshed
            - ``stats`` -- Monitored stats sections (``configuration``,
              ``runtime``, ``workload``, ``capacity_estimation``)

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges to view the
                task manager health.
            TransportError: If unable to connect to Kibana.

        Example:
            >>> # Basic health check
            >>> health = client.task_manager.health()
            >>> print(health.body["status"])
            OK
            >>>
            >>> # Inspect each monitored stats section
            >>> for section, info in health.body["stats"].items():
            ...     print(f"{section}: {info['status']}")
            configuration: OK
            runtime: OK
            workload: OK
            capacity_estimation: OK
            >>>
            >>> # Check polling performance
            >>> polling = health.body["stats"]["runtime"]["value"]["polling"]
            >>> print(polling["last_successful_poll"])
            2025-03-21T21:30:04.455Z
        """
        return self.perform_request(
            "GET",
            "/api/task_manager/_health",
            headers={"accept": "application/json"},
        )
