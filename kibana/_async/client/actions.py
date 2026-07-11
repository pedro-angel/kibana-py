"""Deprecated AsyncActionsClient alias for the async Connectors API client."""

from __future__ import annotations

from kibana._async.client.connectors import AsyncConnectorsClient


class AsyncActionsClient(AsyncConnectorsClient):
    """Deprecated alias for :class:`AsyncConnectorsClient`.

    .. deprecated::
        Kibana renamed "actions" to "connectors"; the REST API lives under
        ``/api/actions`` but the canonical client namespace is now
        ``client.connectors``. ``client.actions`` remains as a thin
        backwards-compatible alias and will be removed in a future release.
        Use ``client.connectors`` instead.

    All methods are inherited unchanged from :class:`AsyncConnectorsClient`;
    see that class for full documentation.

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>> # Prefer this:
        >>> await client.connectors.list_types()
        >>> # Deprecated, but still works:
        >>> await client.actions.list_types()
    """
