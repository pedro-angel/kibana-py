"""Transport-layer exceptions from elastic_transport are translated to the
kibana.exceptions equivalents, so users can catch the documented kibana types."""

import contextlib
import logging
from unittest.mock import AsyncMock, Mock

import pytest
from elastic_transport import ConnectionError as ETConnectionError
from elastic_transport import ConnectionTimeout as ETConnectionTimeout
from elastic_transport import SerializationError as ETSerializationError
from elastic_transport import TlsError as ETTlsError
from elastic_transport import TransportError as ETTransportError

from kibana.exceptions import (
    ConnectionError,
    ConnectionTimeout,
    SerializationError,
    SSLError,
    TransportError,
    translate_transport_errors,
)

# (elastic_transport exception, expected kibana.exceptions type). Order matters:
# ET ConnectionTimeout subclasses TransportError directly (NOT ConnectionError),
# and ET TlsError subclasses ConnectionError -- so these assert the mapping picks
# the most specific kibana type, not a broader ancestor.
CASES = [
    (ETConnectionTimeout, ConnectionTimeout),
    (ETTlsError, SSLError),
    (ETConnectionError, ConnectionError),
    (ETSerializationError, SerializationError),
    (ETTransportError, TransportError),
]


@pytest.mark.parametrize("et_exc, kbn_exc", CASES)
def test_helper_translates_exact_type_and_preserves_cause(et_exc, kbn_exc):
    source = et_exc("boom")
    with pytest.raises(kbn_exc) as excinfo:
        with translate_transport_errors():
            raise source
    # Exact type (not just a broader ancestor) and the ET error chained as cause.
    assert type(excinfo.value) is kbn_exc
    assert excinfo.value.__cause__ is source
    # The ET exception's message is carried through faithfully (its str() may be a
    # fixed class message for the connection family, or the passed text otherwise),
    # and exposed via the .message attribute the docs use.
    assert str(excinfo.value) == str(source)
    assert excinfo.value.message == str(source)


def test_helper_passes_through_non_transport_errors():
    # A non-transport error is not swallowed or translated.
    with pytest.raises(ValueError):
        with translate_transport_errors():
            raise ValueError("unrelated")


@pytest.mark.parametrize("et_exc, kbn_exc", CASES)
def test_sync_client_translates_transport_error(mock_transport, et_exc, kbn_exc):
    from kibana._sync.client._base import BaseClient

    mock_transport.perform_request.side_effect = et_exc("boom")
    client = BaseClient(_transport=mock_transport)

    with pytest.raises(kbn_exc) as excinfo:
        client.perform_request("GET", "/api/status")
    assert type(excinfo.value) is kbn_exc
    assert isinstance(excinfo.value.__cause__, et_exc)


@pytest.mark.asyncio
@pytest.mark.parametrize("et_exc, kbn_exc", CASES)
async def test_async_client_translates_transport_error(
    mock_async_transport, et_exc, kbn_exc
):
    from kibana._async.client._base import AsyncBaseClient

    mock_async_transport.perform_request.side_effect = et_exc("boom")
    client = AsyncBaseClient(_transport=mock_async_transport)

    with pytest.raises(kbn_exc) as excinfo:
        await client.perform_request("GET", "/api/status")
    assert type(excinfo.value) is kbn_exc
    assert isinstance(excinfo.value.__cause__, et_exc)


# close() must translate transport-layer close failures through the SAME
# translate_transport_errors() helper the request path uses -- issue #84. Before
# this fix, close() caught bare Exception and only logged a WARNING, so a real
# close failure (leaked connection/socket) was invisible to the caller.
#
# A round-2 code-quality review caught a regression the round-1 fix introduced:
# pre-fix, EVERY close failure logged a WARNING unconditionally (even though it
# then swallowed the exception); post-fix (round 1), a caller that suppresses the
# now-raised error gets total silence -- no log at all. These tests also pin that
# the WARNING is logged (same message shape as the pre-fix swallow) immediately
# before the translated error is re-raised, so visibility survives a suppress.
@pytest.mark.parametrize("et_exc, kbn_exc", CASES)
def test_sync_client_close_translates_transport_error(et_exc, kbn_exc, caplog):
    from kibana import Kibana

    client = Kibana(hosts="http://localhost:5601")
    source = et_exc("boom")
    client._transport.close = Mock(side_effect=source)

    with caplog.at_level(logging.WARNING, logger="kibana"):
        with pytest.raises(kbn_exc) as excinfo:
            client.close()
    # Exact type, cause preserved, and the .message attribute the docs use.
    assert type(excinfo.value) is kbn_exc
    assert excinfo.value.__cause__ is source
    assert excinfo.value.message == str(source)
    # Visibility survives even for a caller who suppresses the raise (#84 round 2).
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "Error closing Kibana client" in warnings[0].message
    assert str(excinfo.value) in warnings[0].message


@pytest.mark.asyncio
@pytest.mark.parametrize("et_exc, kbn_exc", CASES)
async def test_async_client_close_translates_transport_error(et_exc, kbn_exc, caplog):
    from kibana import AsyncKibana

    client = AsyncKibana(hosts="http://localhost:5601")
    source = et_exc("boom")
    client._transport.close = AsyncMock(side_effect=source)

    with caplog.at_level(logging.WARNING, logger="kibana"):
        with pytest.raises(kbn_exc) as excinfo:
            await client.close()
    assert type(excinfo.value) is kbn_exc
    assert excinfo.value.__cause__ is source
    assert excinfo.value.message == str(source)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "Error closing AsyncKibana client" in warnings[0].message
    assert str(excinfo.value) in warnings[0].message


def test_sync_client_close_propagates_non_transport_error():
    """A non-transport error out of transport.close() is not swallowed or
    translated -- same convention translate_transport_errors() already applies
    on the request path (test_helper_passes_through_non_transport_errors)."""
    from kibana import Kibana

    client = Kibana(hosts="http://localhost:5601")
    client._transport.close = Mock(side_effect=RuntimeError("disk full"))

    with pytest.raises(RuntimeError, match="disk full"):
        client.close()


@pytest.mark.asyncio
async def test_async_client_close_propagates_non_transport_error():
    from kibana import AsyncKibana

    client = AsyncKibana(hosts="http://localhost:5601")
    client._transport.close = AsyncMock(side_effect=RuntimeError("disk full"))

    with pytest.raises(RuntimeError, match="disk full"):
        await client.close()


# The exact best-effort-close recipe documented on Kibana.close()'s /
# AsyncKibana.close()'s docstrings, CHANGELOG.md, and
# docs/evidence/close-translation-84.md. Keep this tuple in lockstep with what's
# documented in those three places -- this test exists specifically because a
# spec review caught `contextlib.suppress(TransportError)` alone documented as
# the recipe, which does NOT cover `SerializationError` (it subclasses
# `KibanaException` directly, not `TransportError` -- see the MRO assertion
# below). A pre-fix-round run of this test with only `(TransportError,)` here
# fails exactly one of the five parametrized cases (SerializationError) --
# that failure is what should have caught the doc bug before it shipped.
DOCUMENTED_CLOSE_SUPPRESS_RECIPE = (TransportError, SerializationError)


def test_serialization_error_does_not_subclass_transport_error():
    """Ground the recipe's premise: SerializationError is NOT a TransportError,
    so a suppress recipe naming only TransportError silently misses it."""
    assert not issubclass(SerializationError, TransportError)


@pytest.mark.parametrize("et_exc, kbn_exc", CASES)
def test_documented_close_suppress_recipe_covers_every_mapped_type_sync(
    et_exc, kbn_exc
):
    """Pins that the exact documented recipe suppresses all 5 mapped types a
    transport-layer close failure can now raise -- not just some of them."""
    from kibana import Kibana

    client = Kibana(hosts="http://localhost:5601")
    client._transport.close = Mock(side_effect=et_exc("boom"))

    with contextlib.suppress(*DOCUMENTED_CLOSE_SUPPRESS_RECIPE):
        client.close()
    # If the recipe didn't cover kbn_exc, it would have escaped the `with`
    # block above and failed this test with an unhandled exception.


@pytest.mark.asyncio
@pytest.mark.parametrize("et_exc, kbn_exc", CASES)
async def test_documented_close_suppress_recipe_covers_every_mapped_type_async(
    et_exc, kbn_exc
):
    from kibana import AsyncKibana

    client = AsyncKibana(hosts="http://localhost:5601")
    client._transport.close = AsyncMock(side_effect=et_exc("boom"))

    with contextlib.suppress(*DOCUMENTED_CLOSE_SUPPRESS_RECIPE):
        await client.close()


# Characterization tests, not a fix -- #84 round-2 code-quality review.
# elastic_transport.Transport.close() (and AsyncTransport.close()) is a bare
# `for node in pool: node.close()` loop with no per-node try/except. If an
# earlier node's close() raises, the loop aborts and every node after it is
# never closed -- retrying or suppressing this method's raised error does NOT
# reclaim those unreached nodes, because nothing resumes the loop past the
# failing node. This is real, observed elastic_transport behavior (upstream,
# not introduced by this fix's translation), documented as a caveat in both
# close() docstrings. These tests PASS today: they pin current reality so a
# future elastic_transport upgrade that changes this can't silently
# invalidate the documented caveat without a test failing -- they are not a
# RED-then-GREEN pair, since there is nothing in kibana-py to fix here.
def test_multi_node_close_failure_aborts_pool_loop_retry_does_not_help_sync():
    from kibana import Kibana

    client = Kibana(hosts=["http://localhost:5601", "http://localhost:5602"])
    nodes = list(client._transport.node_pool.all())
    assert len(nodes) == 2
    node0, node1 = nodes
    node0.close = Mock(side_effect=ETConnectionError("node0 down"))
    node1.close = Mock()

    for _ in range(3):
        with contextlib.suppress(TransportError, SerializationError):
            client.close()

    assert node0.close.call_count == 3
    # node1 is never reached, even after 3 retries with the documented
    # suppress recipe applied -- the pool-close loop aborts at node0 every
    # time, before node1's turn ever comes up.
    assert node1.close.call_count == 0


@pytest.mark.asyncio
async def test_multi_node_close_failure_aborts_pool_loop_retry_does_not_help_async():
    from kibana import AsyncKibana

    client = AsyncKibana(hosts=["http://localhost:5601", "http://localhost:5602"])
    nodes = list(client._transport.node_pool.all())
    assert len(nodes) == 2
    node0, node1 = nodes
    node0.close = AsyncMock(side_effect=ETConnectionError("node0 down"))
    node1.close = AsyncMock()

    for _ in range(3):
        with contextlib.suppress(TransportError, SerializationError):
            await client.close()

    assert node0.close.call_count == 3
    assert node1.close.call_count == 0
