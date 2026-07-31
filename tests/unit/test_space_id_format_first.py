"""A malformed ``space_id`` fails fast -- before any request, before any cache use.

Covers #74: the async tree validated space *existence* before space *format*, so
``await client.slos.get(slo_id="x", space_id="Bad Space!")`` issued a real
``GET /api/spaces/space/Bad%20Space%21``, raised ``SpaceNotFoundError`` instead of
``InvalidSpaceIdError``, and negative-cached the malformed key -- while the same
sync call raised ``InvalidSpaceIdError`` with zero requests. Four async namespaces
(connectors, data_views, ml, saved_objects) built the path *before* validating and
so happened to match sync; the other 28 did not.

The contract these tests pin, identically for both trees and every namespace:

1. a malformed id raises :class:`InvalidSpaceIdError` (never ``SpaceNotFoundError``);
2. with **zero** HTTP requests -- the transport double counts them;
3. and **zero** cache traffic -- the shared cache (#73) stays empty, so a malformed
   id is never negative-cached.

``Kibana.space()`` / ``AsyncKibana.space()`` are held to the same contract: their
docstrings promise ``InvalidSpaceIdError`` for a bad format, and
``_validate_space_on_creation`` now seeds the shared cache, so the format check has
to precede that too.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from elastic_transport import (
    ApiResponseMeta,
    AsyncTransport,
    ObjectApiResponse,
    Transport,
)

from kibana import AsyncKibana, Kibana
from kibana.exceptions import InvalidSpaceIdError

BAD_SPACE = "Bad Space!"


def _response(body=None, status=200):
    meta = ApiResponseMeta(
        status=status, headers={}, http_version="1.1", duration=0.0, node=None
    )
    return ObjectApiResponse(body={} if body is None else body, meta=meta)


def _sync_client():
    """A sync client whose transport double counts every request it is handed."""
    transport = Mock(spec=Transport)
    transport.perform_request = Mock(side_effect=lambda **_kw: _response())
    return Kibana(_transport=transport), transport


def _async_client():
    """An async client whose transport double counts every request it is handed."""
    transport = Mock(spec=AsyncTransport)
    transport.perform_request = AsyncMock(side_effect=lambda **_kw: _response())
    return AsyncKibana(_transport=transport), transport


def _assert_untouched(transport, client):
    """No request went out and the shared space cache learned nothing."""
    assert transport.perform_request.call_args_list == [], (
        "a malformed space id must not reach the wire, but these requests went out: "
        f"{transport.perform_request.call_args_list}"
    )
    cache = client._space_validation_cache
    assert cache.entries == {}, f"malformed id was cached: {cache.entries}"
    assert cache.timestamps == {}


# One representative method per namespace. connectors/data_views/ml/saved_objects
# are the four that used to build the path before validating; slos and timeline
# are controls from the 28 that used the tree-wide order.
_CALLS = {
    "connectors": lambda c, space: c.connectors.get(id="x", space_id=space),
    "data_views": lambda c, space: c.data_views.get_all(space_id=space),
    "ml": lambda c, space: c.ml.sync(space_id=space),
    "saved_objects": lambda c, space: c.saved_objects.get(
        type="dashboard", id="x", space_id=space
    ),
    "slos": lambda c, space: c.slos.get(slo_id="x", space_id=space),
    "timeline": lambda c, space: c.timeline.get_all(space_id=space),
}


@pytest.mark.parametrize("namespace", sorted(_CALLS))
def test_sync_namespace_rejects_a_malformed_space_id_without_touching_anything(
    namespace,
):
    client, transport = _sync_client()

    with pytest.raises(InvalidSpaceIdError):
        _CALLS[namespace](client, BAD_SPACE)

    _assert_untouched(transport, client)


@pytest.mark.asyncio
@pytest.mark.parametrize("namespace", sorted(_CALLS))
async def test_async_namespace_rejects_a_malformed_space_id_without_touching_anything(
    namespace,
):
    client, transport = _async_client()

    with pytest.raises(InvalidSpaceIdError):
        await _CALLS[namespace](client, BAD_SPACE)

    _assert_untouched(transport, client)


@pytest.mark.parametrize("namespace", sorted(_CALLS))
def test_sync_namespace_rejects_a_malformed_default_space_id(namespace):
    """The default space id is held to the same contract as an explicit one."""
    client, transport = _sync_client()

    namespace_client = getattr(client, namespace)
    namespace_client._default_space_id = BAD_SPACE

    with pytest.raises(InvalidSpaceIdError):
        _CALLS[namespace](client, None)

    _assert_untouched(transport, client)


@pytest.mark.asyncio
@pytest.mark.parametrize("namespace", sorted(_CALLS))
async def test_async_namespace_rejects_a_malformed_default_space_id(namespace):
    client, transport = _async_client()

    namespace_client = getattr(client, namespace)
    namespace_client._default_space_id = BAD_SPACE

    with pytest.raises(InvalidSpaceIdError):
        await _CALLS[namespace](client, None)

    _assert_untouched(transport, client)


@pytest.mark.parametrize("validate", [True, False])
def test_sync_space_rejects_a_malformed_id(validate):
    """``Kibana.space()`` keeps its documented ``InvalidSpaceIdError`` promise."""
    client, transport = _sync_client()

    with pytest.raises(InvalidSpaceIdError):
        client.space(BAD_SPACE, validate=validate)

    _assert_untouched(transport, client)


@pytest.mark.asyncio
@pytest.mark.parametrize("validate", [True, False])
async def test_async_space_rejects_a_malformed_id(validate):
    """``AsyncKibana.space()`` keeps the same promise, and never seeds the cache."""
    client, transport = _async_client()

    with pytest.raises(InvalidSpaceIdError):
        await client.space(BAD_SPACE, validate=validate)

    _assert_untouched(transport, client)
