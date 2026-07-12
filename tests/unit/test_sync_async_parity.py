"""Guard: the sync and async client trees must expose the same public API.

Hundreds of methods are hand-duplicated across ``kibana/_sync`` and
``kibana/_async``. This test locks their public method *sets* and *signatures* in
step, so a method (or a parameter) added to one tree but not the other fails CI
immediately. It guards NAME + SIGNATURE parity only -- it cannot catch body/logic
drift (a bugfix landed in one tree but not the other); that would need a
single-source (unasync) generator.
"""

import inspect

import pytest

import kibana._async.client as async_mod
import kibana._sync.client as sync_mod
from kibana import AsyncKibana, Kibana


def _client_pairs():
    """(name, sync_cls, async_cls) for the top-level clients and every sub-client.

    Sub-clients follow the ``X`` / ``AsyncX`` naming convention.
    """
    pairs = [("Kibana", Kibana, AsyncKibana)]
    for name in sorted(dir(sync_mod)):
        obj = getattr(sync_mod, name)
        if inspect.isclass(obj) and name.endswith("Client"):
            twin = getattr(async_mod, "Async" + name, None)
            assert twin is not None, f"sync {name} has no Async{name} twin"
            pairs.append((name, obj, twin))
    return pairs


_PAIRS = _client_pairs()
_IDS = [name for name, _, _ in _PAIRS]


def _public_methods(cls) -> set[str]:
    # inspect.isfunction is True for both `def` and `async def` methods.
    return {
        name
        for name, member in inspect.getmembers(cls, predicate=inspect.isfunction)
        if not name.startswith("_")
    }


def _norm_default(value):
    # The DEFAULT sentinel is a distinct DefaultType instance in each tree, so
    # compare it by kind rather than identity.
    return "<DEFAULT>" if type(value).__name__ == "DefaultType" else value


def _param_shape(func):
    # Name, kind and (sentinel-normalized) default per parameter. Annotations and
    # return types are intentionally ignored: async legitimately differs there.
    return [
        (p.name, p.kind, _norm_default(p.default))
        for p in inspect.signature(func).parameters.values()
    ]


def test_discovered_the_client_pairs():
    # Sanity: we actually found the fleet of sub-clients, not just Kibana.
    assert len(_PAIRS) > 20


@pytest.mark.parametrize("name,sync_cls,async_cls", _PAIRS, ids=_IDS)
def test_public_method_names_match(name, sync_cls, async_cls):
    sync_methods = _public_methods(sync_cls)
    async_methods = _public_methods(async_cls)
    assert sync_methods == async_methods, (
        f"{name}: sync-only={sorted(sync_methods - async_methods)} "
        f"async-only={sorted(async_methods - sync_methods)}"
    )


@pytest.mark.parametrize("name,sync_cls,async_cls", _PAIRS, ids=_IDS)
def test_public_method_signatures_match(name, sync_cls, async_cls):
    for method in sorted(_public_methods(sync_cls) & _public_methods(async_cls)):
        sync_shape = _param_shape(getattr(sync_cls, method))
        async_shape = _param_shape(getattr(async_cls, method))
        assert (
            sync_shape == async_shape
        ), f"{name}.{method} signature drift:\n  sync : {sync_shape}\n  async: {async_shape}"
