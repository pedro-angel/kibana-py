"""Integration tests for FleetEnrollmentClient against a live Kibana instance."""

import uuid

import pytest

from kibana.exceptions import BadRequestError, NotFoundError

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    is_kibana_available,
)

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
async def async_kibana_client():
    """Create an AsyncKibana client for testing with automatic configuration."""
    client = create_test_async_kibana_client(auth_method="auto")
    yield client
    await client.close()


@pytest.fixture
def agent_policy(kibana_client):
    """Create a throwaway agent policy and delete it after the test."""
    name = f"kbnpy-fleet_enrollment-{uuid.uuid4().hex[:12]}"
    created = kibana_client.perform_request(
        "POST",
        "/api/fleet/agent_policies",
        params={"sys_monitoring": False},
        body={
            "name": name,
            "namespace": "default",
            "description": "kibana-py fleet_enrollment integration test policy",
        },
    )
    policy_id = created.body["item"]["id"]
    yield policy_id
    kibana_client.perform_request(
        "POST",
        "/api/fleet/agent_policies/delete",
        body={"agentPolicyId": policy_id},
    )


class TestEnrollmentApiKeysLifecycle:
    """Full lifecycle tests for enrollment API keys."""

    def test_create_get_list_revoke_key(self, kibana_client, agent_policy):
        """Test the full enrollment API key lifecycle."""
        name = f"kbnpy-fleet_enrollment-key-{uuid.uuid4().hex[:8]}"
        created = kibana_client.fleet_enrollment.create_key(
            policy_id=agent_policy, name=name
        )
        assert created.meta.status == 200
        assert created.body["action"] == "created"
        item = created.body["item"]
        key_id = item["id"]
        assert item["policy_id"] == agent_policy
        assert item["active"] is True
        assert item["api_key"]
        assert item["api_key_id"]
        # Kibana appends the key id to the provided name
        assert item["name"].startswith(name)

        try:
            # Get by ID
            fetched = kibana_client.fleet_enrollment.get_key(key_id=key_id)
            assert fetched.body["item"]["id"] == key_id
            assert fetched.body["item"]["policy_id"] == agent_policy

            # List filtered by policy id via kuery
            listed = kibana_client.fleet_enrollment.get_keys(
                per_page=100, kuery=f'policy_id:"{agent_policy}"'
            )
            listed_ids = [key["id"] for key in listed.body["items"]]
            assert key_id in listed_ids
            # Deprecated "list" mirror is still returned by 9.4.3
            assert "list" in listed.body
        finally:
            # Revoke the key (delete = mark inactive)
            deleted = kibana_client.fleet_enrollment.delete_key(key_id=key_id)
            assert deleted.body["action"] == "deleted"

        # A revoked key still exists but is inactive
        revoked = kibana_client.fleet_enrollment.get_key(key_id=key_id)
        assert revoked.body["item"]["active"] is False

    def test_get_missing_key_raises_not_found(self, kibana_client):
        """Test the server's semantic 404 for an unknown enrollment key."""
        missing_id = f"kbnpy-fleet-enrollment-missing-{uuid.uuid4().hex[:8]}"
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.fleet_enrollment.get_key(key_id=missing_id)
        # Assert the server-side message so a routing typo can't pass
        assert "not found" in str(exc_info.value).lower()
        assert missing_id in str(exc_info.value)

    def test_delete_missing_key_raises_not_found(self, kibana_client):
        """Test the server's semantic 404 when revoking an unknown key."""
        missing_id = f"kbnpy-fleet-enrollment-missing-{uuid.uuid4().hex[:8]}"
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.fleet_enrollment.delete_key(key_id=missing_id)
        assert "not found" in str(exc_info.value).lower()
        assert missing_id in str(exc_info.value)


class TestServiceTokensAndLogstashKeys:
    """Live tests for service token and Logstash API key generation."""

    def test_create_service_token(self, kibana_client):
        """Test creating a default Fleet Server service token."""
        token = kibana_client.fleet_enrollment.create_service_token()
        assert token.meta.status == 200
        assert token.body["name"]
        assert token.body["value"]

    def test_create_remote_service_token(self, kibana_client):
        """Test creating a remote Fleet Server service token."""
        token = kibana_client.fleet_enrollment.create_service_token(remote=True)
        assert token.meta.status == 200
        assert token.body["name"]
        assert token.body["value"]

    def test_create_logstash_api_key(self):
        """Test generating a Logstash API key (id:secret format).

        Uses basic auth: Elasticsearch refuses to derive an API key from
        another API key ("creating derived api keys requires an explicit
        role descriptor"), so this endpoint needs a real user session.
        """
        try:
            client = create_test_kibana_client(auth_method="basic")
        except ValueError:
            pytest.skip(
                "requires basic auth credentials; API keys cannot create "
                "derived API keys in Elasticsearch"
            )
        try:
            key = client.fleet_enrollment.create_logstash_api_key()
            assert key.meta.status == 200
            assert ":" in key.body["api_key"]
        finally:
            client.close()


class TestUninstallTokens:
    """Live tests for uninstall token metadata and decrypted tokens."""

    def test_get_uninstall_tokens_and_decrypt_one(self, kibana_client, agent_policy):
        """Test listing uninstall tokens and decrypting the policy's token."""
        # Creating an agent policy generates an uninstall token for it
        tokens = kibana_client.fleet_enrollment.get_uninstall_tokens(
            policy_id=agent_policy, per_page=20
        )
        assert tokens.meta.status == 200
        items = tokens.body["items"]
        assert len(items) >= 1
        meta = items[0]
        assert meta["policy_id"] == agent_policy
        # Metadata listing must not expose the decrypted token value
        assert "token" not in meta

        # Fetch the decrypted token by ID
        decrypted = kibana_client.fleet_enrollment.get_uninstall_token(
            uninstall_token_id=meta["id"]
        )
        assert decrypted.body["item"]["id"] == meta["id"]
        assert decrypted.body["item"]["policy_id"] == agent_policy
        assert decrypted.body["item"]["token"]

    def test_policy_id_and_search_are_mutually_exclusive(self, kibana_client):
        """Test the server's semantic 400 for conflicting query params."""
        with pytest.raises(BadRequestError) as exc_info:
            kibana_client.fleet_enrollment.get_uninstall_tokens(
                policy_id="abc", search="def"
            )
        assert "cannot be used at the same time" in str(exc_info.value)

    def test_get_missing_uninstall_token_raises_not_found(self, kibana_client):
        """Test the server's semantic 404 for an unknown uninstall token."""
        missing_id = f"kbnpy-fleet-enrollment-missing-{uuid.uuid4().hex[:8]}"
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.fleet_enrollment.get_uninstall_token(
                uninstall_token_id=missing_id
            )
        assert "uninstall token not found" in str(exc_info.value).lower()


class TestMessageSigningService:
    """Live tests for the message signing key pair rotation."""

    def test_rotate_without_acknowledge_is_rejected(self, kibana_client):
        """Test that rotation without acknowledge=true is rejected with 400."""
        with pytest.raises(BadRequestError) as exc_info:
            kibana_client.fleet_enrollment.rotate_message_signing_key_pair()
        assert "acknowledge=true" in str(exc_info.value)

    def test_rotate_key_pair_acknowledged(self, kibana_client):
        """Test rotating the message signing key pair (no agents enrolled)."""
        result = kibana_client.fleet_enrollment.rotate_message_signing_key_pair(
            acknowledge=True
        )
        assert result.meta.status == 200
        assert result.body["message"] == "Key pair rotated successfully."


class TestKubernetesManifests:
    """Live tests for the Kubernetes agent manifest endpoints."""

    def test_get_kubernetes_manifest(self, kibana_client):
        """Test getting the manifest as JSON with placeholder substitution."""
        fleet_url = "https://fleet.example.com:8220"
        token = f"kbnpy-fleet-enrollment-{uuid.uuid4().hex[:8]}"
        manifest = kibana_client.fleet_enrollment.get_kubernetes_manifest(
            fleet_server=fleet_url, enrol_token=token
        )
        assert manifest.meta.status == 200
        yaml_text = manifest.body["item"]
        assert "kind: DaemonSet" in yaml_text
        assert fleet_url in yaml_text
        assert token in yaml_text

    def test_download_kubernetes_manifest(self, kibana_client):
        """Test downloading the manifest as a raw YAML document."""
        manifest = kibana_client.fleet_enrollment.download_kubernetes_manifest()
        assert manifest.meta.status == 200
        assert isinstance(manifest.body, str)
        assert "kind: DaemonSet" in manifest.body


class TestAsyncFleetEnrollment:
    """Async round-trip tests for the Fleet enrollment API."""

    @pytest.mark.asyncio
    async def test_async_key_lifecycle_and_tokens(
        self, async_kibana_client, agent_policy
    ):
        """Test the enrollment key lifecycle and token reads with async client."""
        name = f"kbnpy-fleet_enrollment-async-{uuid.uuid4().hex[:8]}"
        created = await async_kibana_client.fleet_enrollment.create_key(
            policy_id=agent_policy, name=name
        )
        key_id = created.body["item"]["id"]
        try:
            assert created.body["action"] == "created"
            assert created.body["item"]["active"] is True

            fetched = await async_kibana_client.fleet_enrollment.get_key(key_id=key_id)
            assert fetched.body["item"]["id"] == key_id

            listed = await async_kibana_client.fleet_enrollment.get_keys(
                per_page=100, kuery=f'policy_id:"{agent_policy}"'
            )
            assert key_id in [key["id"] for key in listed.body["items"]]

            tokens = await async_kibana_client.fleet_enrollment.get_uninstall_tokens(
                policy_id=agent_policy
            )
            assert len(tokens.body["items"]) >= 1

            manifest = (
                await async_kibana_client.fleet_enrollment.get_kubernetes_manifest()
            )
            assert "kind: DaemonSet" in manifest.body["item"]
        finally:
            deleted = await async_kibana_client.fleet_enrollment.delete_key(
                key_id=key_id
            )
            assert deleted.body["action"] == "deleted"
