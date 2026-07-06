"""Unit tests for FleetEnrollmentClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse, TextApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.fleet_enrollment import FleetEnrollmentClient
from kibana.exceptions import BadRequestError, NotFoundError

K8S_MANIFEST = (
    "---\n"
    "apiVersion: apps/v1\n"
    "kind: DaemonSet\n"
    "metadata:\n"
    "  name: elastic-agent\n"
    "  namespace: kube-system\n"
)


def _enrollment_key_body(**overrides):
    """Build a representative enrollment API key object."""
    body = {
        "id": "3fd99865-1eac-4916-b9c6-de61517380b2",
        "api_key_id": "9flVOZ8BiXLbCmmN0pqF",
        "api_key": "OWZsVk9aOEJ...Sm1OUFVRWVadw==",
        "name": "kbnpy-key (3fd99865-1eac-4916-b9c6-de61517380b2)",
        "policy_id": "policy-id-1",
        "active": True,
        "created_at": "2026-07-06T21:29:14.551Z",
        "hidden": False,
    }
    body.update(overrides)
    return body


def _uninstall_token_meta(**overrides):
    """Build a representative uninstall token metadata object."""
    body = {
        "id": "9d2d1fb0-f7b9-465a-8dbd-65aec070a7ab",
        "policy_id": "policy-id-1",
        "policy_name": "kbnpy-policy",
        "created_at": "2026-07-06T21:28:58.897Z",
        "namespaces": ["default"],
    }
    body.update(overrides)
    return body


class TestFleetEnrollmentClientInitialization:
    """Test FleetEnrollmentClient initialization."""

    def test_fleet_enrollment_client_initialization(self, mock_transport):
        """Test that FleetEnrollmentClient can be initialized with a parent."""
        client = Kibana(_transport=mock_transport)
        fleet_enrollment_client = FleetEnrollmentClient(client)
        assert fleet_enrollment_client._client is client

    def test_fleet_enrollment_property_returns_client(self, mock_transport):
        """Test that client.fleet_enrollment returns the namespace client."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.fleet_enrollment, FleetEnrollmentClient)

    def test_fleet_enrollment_property_caching(self, mock_transport):
        """Test that the fleet_enrollment property returns the same instance."""
        client = Kibana(_transport=mock_transport)
        assert client.fleet_enrollment is client.fleet_enrollment


class TestFleetEnrollmentGetKeys:
    """Test FleetEnrollmentClient.get_keys() method."""

    def test_get_keys_no_params(self, mock_transport):
        """Test listing enrollment API keys without any parameters."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "items": [_enrollment_key_body()],
                "list": [_enrollment_key_body()],
                "total": 1,
                "page": 1,
                "perPage": 20,
            },
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_enrollment.get_keys()

        assert result.body["total"] == 1
        assert result.body["items"][0]["policy_id"] == "policy-id-1"

        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/enrollment_api_keys"
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs.get("body") is None

    def test_get_keys_param_encoding(self, mock_transport):
        """Test that page/perPage/kuery are encoded as query params."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"items": [], "list": [], "total": 0, "page": 2, "perPage": 5},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_enrollment.get_keys(
            page=2, per_page=5, kuery='policy_id:"policy-id-1"'
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/fleet/enrollment_api_keys"
            "?page=2&perPage=5&kuery=policy_id%3A%22policy-id-1%22"
        )

    def test_get_keys_in_space(self, mock_transport):
        """Test that space_id builds a /s/<space>/api/... path."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"items": [], "list": [], "total": 0, "page": 1, "perPage": 20},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_enrollment.get_keys(space_id="marketing", validate_spaces=False)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/fleet/enrollment_api_keys"


class TestFleetEnrollmentCreateKey:
    """Test FleetEnrollmentClient.create_key() method."""

    def test_create_key_minimal(self, mock_transport):
        """Test creating an enrollment API key with only a policy_id."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"item": _enrollment_key_body(), "action": "created"},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_enrollment.create_key(policy_id="policy-id-1")

        assert result.body["action"] == "created"
        assert result.body["item"]["active"] is True

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/enrollment_api_keys"
        assert call_kwargs["body"] == {"policy_id": "policy-id-1"}
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_create_key_full_body(self, mock_transport):
        """Test creating an enrollment API key with name and expiration."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"item": _enrollment_key_body(), "action": "created"},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_enrollment.create_key(
            policy_id="policy-id-1",
            name="kbnpy-key",
            expiration="2027-01-01T00:00:00.000Z",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "policy_id": "policy-id-1",
            "name": "kbnpy-key",
            "expiration": "2027-01-01T00:00:00.000Z",
        }

    def test_create_key_bad_request_error(self, mock_transport):
        """Test that a 400 (e.g. unknown policy) maps to BadRequestError."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 400,
                "error": "Bad Request",
                "message": 'Agent policy "missing" not found',
            },
            meta=Mock(status=400, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(BadRequestError):
            client.fleet_enrollment.create_key(policy_id="missing")


class TestFleetEnrollmentGetKey:
    """Test FleetEnrollmentClient.get_key() method."""

    def test_get_key(self, mock_transport):
        """Test getting an enrollment API key by ID."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"item": _enrollment_key_body()},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_enrollment.get_key(
            key_id="3fd99865-1eac-4916-b9c6-de61517380b2"
        )

        assert result.body["item"]["api_key_id"] == "9flVOZ8BiXLbCmmN0pqF"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/fleet/enrollment_api_keys/3fd99865-1eac-4916-b9c6-de61517380b2"
        )

    def test_get_key_url_encodes_id(self, mock_transport):
        """Test that the key ID is URL-encoded in the path."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"item": _enrollment_key_body()},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_enrollment.get_key(key_id="key id/1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/fleet/enrollment_api_keys/key%20id%2F1"

    def test_get_key_not_found_error(self, mock_transport):
        """Test that a missing enrollment API key maps to NotFoundError."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Enrollment api key missing-id not found",
            },
            meta=Mock(status=404, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(NotFoundError):
            client.fleet_enrollment.get_key(key_id="missing-id")


class TestFleetEnrollmentDeleteKey:
    """Test FleetEnrollmentClient.delete_key() method."""

    def test_delete_key(self, mock_transport):
        """Test revoking an enrollment API key by ID."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"action": "deleted"},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_enrollment.delete_key(key_id="key-id-1")

        assert result.body["action"] == "deleted"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/fleet/enrollment_api_keys/key-id-1"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_delete_key_in_space(self, mock_transport):
        """Test revoking an enrollment API key in a specific space."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"action": "deleted"},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_enrollment.delete_key(
            key_id="key-id-1", space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/s/marketing/api/fleet/enrollment_api_keys/key-id-1"
        )


class TestFleetEnrollmentServiceTokens:
    """Test FleetEnrollmentClient.create_service_token() method."""

    def test_create_service_token_default(self, mock_transport):
        """Test creating a service token without a body."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"name": "token-1783373404497", "value": "AAEAAWVsYXN0aWMv..."},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_enrollment.create_service_token()

        assert result.body["name"] == "token-1783373404497"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/service_tokens"
        assert call_kwargs.get("body") is None
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_create_service_token_remote(self, mock_transport):
        """Test creating a remote Fleet Server service token."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"name": "token-1783373404725", "value": "AAEAAWVsYXN0aWMv..."},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_enrollment.create_service_token(remote=True)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {"remote": True}
        assert call_kwargs["headers"]["content-type"] == "application/json"


class TestFleetEnrollmentLogstashApiKeys:
    """Test FleetEnrollmentClient.create_logstash_api_key() method."""

    def test_create_logstash_api_key(self, mock_transport):
        """Test generating a Logstash API key."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"api_key": "CPlWOZ8BiXLbCmmNnptN:-Ax9P3cYCxxoMDMQIAGUxA"},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_enrollment.create_logstash_api_key()

        assert ":" in result.body["api_key"]

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/fleet/logstash_api_keys"
        assert call_kwargs.get("body") is None
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"


class TestFleetEnrollmentUninstallTokens:
    """Test uninstall token methods."""

    def test_get_uninstall_tokens_no_params(self, mock_transport):
        """Test listing uninstall token metadata."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "items": [_uninstall_token_meta()],
                "total": 1,
                "page": 1,
                "perPage": 20,
            },
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_enrollment.get_uninstall_tokens()

        assert result.body["items"][0]["policy_id"] == "policy-id-1"
        # Metadata listing must not include decrypted token values
        assert "token" not in result.body["items"][0]

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/uninstall_tokens"

    def test_get_uninstall_tokens_param_encoding(self, mock_transport):
        """Test policyId/perPage/page query param encoding."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"items": [], "total": 0, "page": 2, "perPage": 5},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_enrollment.get_uninstall_tokens(
            policy_id="policy-id-1", per_page=5, page=2
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/fleet/uninstall_tokens?policyId=policy-id-1&perPage=5&page=2"
        )

    def test_get_uninstall_tokens_search_param(self, mock_transport):
        """Test the search query param encoding."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"items": [], "total": 0, "page": 1, "perPage": 20},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_enrollment.get_uninstall_tokens(search="abc123")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/fleet/uninstall_tokens?search=abc123"

    def test_get_uninstall_token(self, mock_transport):
        """Test getting one decrypted uninstall token by ID."""
        item = _uninstall_token_meta(token="9ad10301a5bcb6a309b6de24d782aa45")
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"item": item},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_enrollment.get_uninstall_token(
            uninstall_token_id="9d2d1fb0-f7b9-465a-8dbd-65aec070a7ab"
        )

        assert result.body["item"]["token"] == "9ad10301a5bcb6a309b6de24d782aa45"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/fleet/uninstall_tokens/9d2d1fb0-f7b9-465a-8dbd-65aec070a7ab"
        )

    def test_get_uninstall_token_not_found_error(self, mock_transport):
        """Test that a missing uninstall token maps to NotFoundError."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Uninstall Token not found with id missing-id",
            },
            meta=Mock(status=404, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(NotFoundError):
            client.fleet_enrollment.get_uninstall_token(uninstall_token_id="missing-id")


class TestFleetEnrollmentMessageSigning:
    """Test FleetEnrollmentClient.rotate_message_signing_key_pair() method."""

    def test_rotate_key_pair_acknowledged(self, mock_transport):
        """Test rotating the message signing key pair with acknowledge=True."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"message": "Key pair rotated successfully."},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_enrollment.rotate_message_signing_key_pair(
            acknowledge=True
        )

        assert result.body["message"] == "Key pair rotated successfully."

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/fleet/message_signing_service/rotate_key_pair?acknowledge=true"
        )
        assert call_kwargs.get("body") is None
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_rotate_key_pair_without_acknowledge(self, mock_transport):
        """Test that an unacknowledged rotation maps to BadRequestError."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 400,
                "error": "Bad Request",
                "message": (
                    "[request query]: Warning: this API will cause a key pair "
                    "to rotate ... acknowledge=true in the request parameters."
                ),
            },
            meta=Mock(status=400, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(BadRequestError):
            client.fleet_enrollment.rotate_message_signing_key_pair()

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/fleet/message_signing_service/rotate_key_pair"
        )


class TestFleetEnrollmentKubernetes:
    """Test Kubernetes manifest methods."""

    def test_get_kubernetes_manifest(self, mock_transport):
        """Test getting the Kubernetes manifest as JSON."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"item": K8S_MANIFEST},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_enrollment.get_kubernetes_manifest()

        assert result.body["item"].startswith("---")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/kubernetes"
        assert call_kwargs["headers"]["accept"] == "application/json"

    def test_get_kubernetes_manifest_param_encoding(self, mock_transport):
        """Test that fleetServer/enrolToken/download params are encoded."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"item": K8S_MANIFEST},
            meta=Mock(status=200, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_enrollment.get_kubernetes_manifest(
            download=False,
            fleet_server="https://fleet.example.com:8220",
            enrol_token="token-abc",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/fleet/kubernetes?download=false"
            "&fleetServer=https%3A%2F%2Ffleet.example.com%3A8220"
            "&enrolToken=token-abc"
        )

    def test_download_kubernetes_manifest(self, mock_transport):
        """Test downloading the Kubernetes manifest as raw YAML text."""
        mock_transport.perform_request.return_value = TextApiResponse(
            body=K8S_MANIFEST,
            meta=Mock(status=200, headers={"content-type": "text/x-yaml"}),
        )

        client = Kibana(_transport=mock_transport)
        result = client.fleet_enrollment.download_kubernetes_manifest()

        assert isinstance(result.body, str)
        assert result.body.startswith("---")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/fleet/kubernetes/download"
        assert call_kwargs["headers"]["accept"] == "text/x-yaml"

    def test_download_kubernetes_manifest_in_space(self, mock_transport):
        """Test downloading the manifest from a specific space."""
        mock_transport.perform_request.return_value = TextApiResponse(
            body=K8S_MANIFEST,
            meta=Mock(status=200, headers={"content-type": "text/x-yaml"}),
        )

        client = Kibana(_transport=mock_transport)
        client.fleet_enrollment.download_kubernetes_manifest(
            download=True, space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/s/marketing/api/fleet/kubernetes/download?download=true"
        )
