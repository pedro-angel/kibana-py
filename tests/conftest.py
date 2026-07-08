"""Pytest configuration and fixtures for kibana-py tests."""

from unittest.mock import AsyncMock, Mock

import pytest
from elastic_transport import (
    ApiResponseMeta,
    AsyncTransport,
    ObjectApiResponse,
    Transport,
)


@pytest.fixture
def mock_transport():
    """Create a mock Transport instance for testing."""
    transport = Mock(spec=Transport)
    transport.perform_request = Mock()
    return transport


@pytest.fixture
def mock_async_transport():
    """Create a mock AsyncTransport instance for testing."""
    transport = Mock(spec=AsyncTransport)
    transport.perform_request = AsyncMock()
    transport.close = AsyncMock()
    return transport


@pytest.fixture
def mock_response():
    """Create a mock API response."""

    def _create_response(body=None, status=200, headers=None):
        if body is None:
            body = {}
        if headers is None:
            headers = {}

        meta = ApiResponseMeta(
            status=status,
            headers=headers,
            http_version="1.1",
            duration=0.1,
            node=None,
        )
        return ObjectApiResponse(body=body, meta=meta)

    return _create_response


# Self-signed certificate/key pair for tests that exercise SSL options.
# Generated once with:
#   openssl req -x509 -newkey rsa:2048 -days 36500 -nodes -subj "/CN=kibana-py-test"
_TEST_TLS_CERT = """-----BEGIN CERTIFICATE-----
MIICsDCCAZgCCQCo6cviuX4qtTANBgkqhkiG9w0BAQsFADAZMRcwFQYDVQQDDA5r
aWJhbmEtcHktdGVzdDAgFw0yNjA3MDMxODI4NTlaGA8yMTI2MDYwOTE4Mjg1OVow
GTEXMBUGA1UEAwwOa2liYW5hLXB5LXRlc3QwggEiMA0GCSqGSIb3DQEBAQUAA4IB
DwAwggEKAoIBAQC+mVdFZbhT/eXqwkBNcAKnX7AuHZ+8XVUPpgQmqVzbUN9Km62J
No2ojZn4fEuGlG/vjVgYT/BmNUAEtHCQ3hMqcQvj9+spLpUTZheYmxnxveWpg2J/
EDIaO5eGdPl68kyT8XkHsjVho88SE5kaa/R2fpk6igMesOn1fTsEZ6LxxbX+GmV7
Psi33Sh+dki6YuygRA3aZscUb+QzJYKhXBvvE57JMV17zUdHkACg+ltXSqHUMbKo
QEdnhgmi06hHRO2RVyr3cyO4w3QSY+Lv1GQo7Sxg35FhYxD0B02NBv9VnXdOuDnb
uifMEN0g0AagcUERK0HWYYXqKsmz3qWqeRCLAgMBAAEwDQYJKoZIhvcNAQELBQAD
ggEBAF/oxlQp+xRcAga1txatjO4p3YrKHKQAR1qO+nPVm8liZCX0ECaftBiIqshR
K36ZqFB6xlOrOMl8eh4ZG7O60AP7xnkoW0gpsUUTIJjrrLcF9kk4u4simKYclloA
8cKO4J0L/BuZ2yvPygg14NK4Vz52KzuBRtodhahR5tv8VbG05NlY40ZcZBv6rpCf
F7OnUIkrIXMH6fjI+0QxCAH9h3CxEmUAgwYgCj3RCyk0HsZ5Z0vD11VQfx672re5
sc7V0jVbqinkLY4GoAVwpbfjHNIRt1B5lhHbmnAm1R03IkBh1288VpGBkfVwFi8r
91rwnVW8ngjF8RjUgkWareXy+YM=
-----END CERTIFICATE-----
"""

_TEST_TLS_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQC+mVdFZbhT/eXq
wkBNcAKnX7AuHZ+8XVUPpgQmqVzbUN9Km62JNo2ojZn4fEuGlG/vjVgYT/BmNUAE
tHCQ3hMqcQvj9+spLpUTZheYmxnxveWpg2J/EDIaO5eGdPl68kyT8XkHsjVho88S
E5kaa/R2fpk6igMesOn1fTsEZ6LxxbX+GmV7Psi33Sh+dki6YuygRA3aZscUb+Qz
JYKhXBvvE57JMV17zUdHkACg+ltXSqHUMbKoQEdnhgmi06hHRO2RVyr3cyO4w3QS
Y+Lv1GQo7Sxg35FhYxD0B02NBv9VnXdOuDnbuifMEN0g0AagcUERK0HWYYXqKsmz
3qWqeRCLAgMBAAECggEACNRZsqFPtLRiXkm5aNzzgoVwR/KfX76DHkJ2lsPpxU8t
yOsFUwHv9gr5QwWfChD+Tn6hwh6R6Go3GQCy5kMjaCfsgRcPEc1Sop9sIGmu/f/q
D7xCZ9h8ObLhBh2NISDwYzogfTbIOkm4YgH+abbukD61In0aP+W6MOEoRr/2UHTf
rJox6poLIcm/oYkSoAIdu6XuJGOO0HSsewd+FBUUPtZ5DqTdYOwqcUq5fpt5tWDd
xpO+ArNN7bwjhB4NV1sWtccvMf7OyRakAfvenc3ldP1f1TmNbMhmNTW6aUFFnsd+
IwIwTeJDZ9WC+7g2YIJ8stV5u0qiWpZmvV5Sh/GA4QKBgQD3WPEpGD1wmXKkSLPa
7IvVzo8lirkuC3HtDpCwM6opu7CIowN1URdasVH6j0mFCAMVDvtExpnFslSVPCn8
zKXFj3XG8Bg095VuT+P2+v3jovUATVgDpghVxP0wyftJeTqOpBsJnUisPUU+oo9z
pWz4zyptXqud+G06XCpcsx2QDQKBgQDFRDPREAlK+pbrJH+h/gJzwuT9BwSvS3sE
/yUWQkGaLRYxtmApHMBu/l1+XixB1PcCh7LWkkcAcIzA8X4Jdom7ql0Xs+BumD94
DAnSLnh2KVB4wiB1QBdb7vXoOyVwYCvaoHfOwx4QdhieugUI+D7ePRkRHUl/nrRX
X19MJeZk9wKBgQC3dVfB9EG134qhgW8tRN/e4ItZ/A+nsEN64Z+9oURoGdcxMT+i
Z1gcI4M7hcWxDyVCHE+QToHFmaSU4AAAikW2R9bCjFhYCP7jyAu8p6NikP6Jj9Rl
OGPcQfTNmDJy56DgJaYMNoWtgvB2KZqe2yb9UKMWZe6Ch710WOHuycd2jQKBgQDE
MeILUxS7AuJo+gMK/VQ5CCSxV3KcWcj/njennLwceC0zwjx/hz4I5mncThNcYlBN
ruL6r794O3hySXzeMowoHve5pEhaFohBgE+gQGHEu7ByejjIBLd20wK2N2U0ECJt
rd2awcq7+ojgDQkG88erRz8QG33HNPQOVie015j+3wKBgQDzaxSBNZS1M/3orGgB
fQQIREh6QR2SqwOHpAtCGB32ieSBTpXEc2OJES8ij8wxlcGtDfclEU2HYOoIDUGD
NZ1aqQlW5CvAhEyu4TkznHvFtJAhQQ+T1qy0gSj8i8BsCpTljjL2VwRnOpTBoCnY
7euh2mpBbQ41aFecyDw6iUx4qQ==
-----END PRIVATE KEY-----
"""


@pytest.fixture
def tls_files(tmp_path):
    """Write a valid self-signed cert/key pair to disk and return their paths.

    Returns a (cert_path, key_path) tuple of strings. Use for ca_certs /
    client_cert / client_key options, which elastic-transport loads eagerly.
    """
    cert_path = tmp_path / "test-cert.pem"
    key_path = tmp_path / "test-key.pem"
    cert_path.write_text(_TEST_TLS_CERT)
    key_path.write_text(_TEST_TLS_KEY)
    return str(cert_path), str(key_path)
