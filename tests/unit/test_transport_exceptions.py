"""Transport-layer exceptions from elastic_transport are translated to the
kibana.exceptions equivalents, so users can catch the documented kibana types."""

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
