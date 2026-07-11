"""Deprecated ActionsClient alias for the Connectors API client."""

from __future__ import annotations

from kibana._sync.client.connectors import ConnectorsClient


class ActionsClient(ConnectorsClient):
    """Deprecated alias for :class:`ConnectorsClient`.

    .. deprecated::
        Kibana renamed "actions" to "connectors"; the REST API lives under
        ``/api/actions`` but the canonical client namespace is now
        ``client.connectors``. ``client.actions`` remains as a thin
        backwards-compatible alias and will be removed in a future release.
        Use ``client.connectors`` instead.

    All methods are inherited unchanged from :class:`ConnectorsClient`; see
    that class for full documentation.

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>> # Prefer this:
        >>> client.connectors.list_types()
        >>> # Deprecated, but still works:
        >>> client.actions.list_types()
    """
