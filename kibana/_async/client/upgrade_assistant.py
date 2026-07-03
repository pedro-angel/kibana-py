"""Async Kibana Upgrade Assistant API client."""

from typing import Any

from elastic_transport import ObjectApiResponse

from .utils import AsyncNamespaceClient


class AsyncUpgradeAssistantClient(AsyncNamespaceClient):
    """Async client for the Kibana Upgrade Assistant API.

    The Upgrade Assistant helps you prepare a cluster for a major version
    upgrade by reporting deprecation issues that must be resolved first.

    Note:
        The Upgrade Assistant API is in **Technical Preview** in Kibana 9.4;
        it may change or be removed in a future release. It is not
        space-scoped.

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>> status = await client.upgrade_assistant.status()
        >>> status.body["readyForUpgrade"]
        True
    """

    async def status(self) -> ObjectApiResponse[Any]:
        """Get the upgrade readiness status.

        Check the status of your cluster: whether it is ready for an upgrade
        and, if not, which deprecation issues remain to be resolved.

        Note:
            Technical Preview in Kibana 9.4.

        Returns:
            ObjectApiResponse whose body includes:
                - ``readyForUpgrade`` (bool): Whether the cluster is ready to
                  be upgraded.
                - ``details`` (str): Human-readable summary of the readiness
                  state (when ready or when issues remain).
                - ``recentEsDeprecationLogs`` (dict): Recent Elasticsearch
                  deprecation log entries (``count`` and ``logs``).
                - ``kibanaApiDeprecations`` (list): Deprecated Kibana API
                  usage detected on this cluster.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            TransportError: If unable to connect to Kibana.

        Example:
            >>> response = await client.upgrade_assistant.status()
            >>> if response.body["readyForUpgrade"]:
            ...     print("Cluster is ready for upgrade")
            ... else:
            ...     print(response.body.get("details", "Issues remain"))
            Cluster is ready for upgrade
        """
        return await self.perform_request(
            "GET",
            "/api/upgrade_assistant/status",
            headers={"accept": "application/json"},
        )
