"""Integration tests for FleetPoliciesClient against a live Kibana 9.4.3 stack.

These tests exercise the Fleet agent policies, package policies and agentless
policies APIs end-to-end. They create their own agent/package policies (all
prefixed with ``kbnpy-fleet-policies``) and always clean them up. The tests
use the lightweight ``udp`` integration package; if the package was not
installed before the test run, it is uninstalled again afterwards.
"""

import uuid

import pytest

from kibana.exceptions import BadRequestError, NotFoundError

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    is_kibana_available,
)

# Skip all tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)

PREFIX = "kbnpy-fleet-policies"

# Lightweight input-type package used for package policy tests.
TEST_PACKAGE = "udp"


def _unique_name(label: str) -> str:
    """Build a unique, prefixed resource name."""
    return f"{PREFIX}-{label}-{uuid.uuid4().hex[:8]}"


def _udp_inputs() -> dict:
    """Simplified-format inputs for a udp package policy."""
    return {
        "udp-udp": {
            "enabled": True,
            "streams": {
                "udp.udp": {
                    "enabled": True,
                    "vars": {
                        "listen_address": "localhost",
                        "listen_port": 8964,
                        "data_stream.dataset": "kbnpy.fleetpolicies",
                    },
                }
            },
        }
    }


def _delete_agent_policy_quietly(client, agent_policy_id: str) -> None:
    """Best-effort agent policy deletion for fixture/test cleanup."""
    try:
        client.fleet_policies.delete_agent_policy(
            agent_policy_id=agent_policy_id, force=True
        )
    except NotFoundError, BadRequestError:
        pass


@pytest.fixture(scope="module")
def udp_package_version():
    """Resolve the udp package version; uninstall it after the module if we
    are the ones who caused its installation."""
    client = create_test_kibana_client()
    response = client.perform_request("GET", f"/api/fleet/epm/packages/{TEST_PACKAGE}")
    version = response.body["item"]["version"]
    initially_installed = response.body["item"]["status"] == "installed"

    yield version

    if not initially_installed:
        try:
            client.perform_request(
                "DELETE", f"/api/fleet/epm/packages/{TEST_PACKAGE}/{version}"
            )
        except Exception:
            pass  # another test run may still reference the package
    client.close()


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing."""
    client = create_test_kibana_client()
    yield client
    client.close()


@pytest.fixture
def agent_policy(kibana_client):
    """Create a throwaway agent policy and delete it afterwards."""
    created = kibana_client.fleet_policies.create_agent_policy(
        name=_unique_name("ap"),
        namespace="default",
        description="kibana-py fleet_policies integration test",
        sys_monitoring=False,
    )
    agent_policy_id = created.body["item"]["id"]
    yield agent_policy_id
    _delete_agent_policy_quietly(kibana_client, agent_policy_id)


@pytest.fixture
def package_policy(kibana_client, agent_policy, udp_package_version):
    """Create a throwaway udp package policy and delete it afterwards."""
    created = kibana_client.options(
        request_timeout=120.0
    ).fleet_policies.create_package_policy(
        name=_unique_name("pp"),
        package={"name": TEST_PACKAGE, "version": udp_package_version},
        policy_ids=[agent_policy],
        inputs=_udp_inputs(),
    )
    package_policy_id = created.body["item"]["id"]
    yield package_policy_id
    try:
        kibana_client.fleet_policies.delete_package_policy(
            package_policy_id=package_policy_id, force=True
        )
    except NotFoundError, BadRequestError:
        pass


class TestAgentPolicyCrudIntegration:
    """CRUD round trips for agent policies."""

    def test_create_get_update_list_delete(self, kibana_client):
        """Full lifecycle: create, get, update, list (kuery), delete."""
        name = _unique_name("crud")
        created = kibana_client.fleet_policies.create_agent_policy(
            name=name,
            namespace="default",
            description="initial description",
            inactivity_timeout=600,
            sys_monitoring=False,
        )
        agent_policy_id = created.body["item"]["id"]
        try:
            assert created.body["item"]["name"] == name
            assert created.body["item"]["status"] == "active"
            assert created.body["item"]["inactivity_timeout"] == 600

            fetched = kibana_client.fleet_policies.get_agent_policy(
                agent_policy_id=agent_policy_id
            ).body["item"]
            assert fetched["id"] == agent_policy_id
            assert fetched["description"] == "initial description"

            updated = kibana_client.fleet_policies.update_agent_policy(
                agent_policy_id=agent_policy_id,
                name=name,
                namespace="default",
                description="updated description",
            ).body["item"]
            assert updated["description"] == "updated description"
            assert updated["revision"] == 2

            found = kibana_client.fleet_policies.get_agent_policies(
                kuery=f'ingest-agent-policies.name:"{name}"',
                with_agent_count=True,
                per_page=5,
            ).body
            assert found["total"] == 1
            assert found["items"][0]["id"] == agent_policy_id
        finally:
            deleted = kibana_client.fleet_policies.delete_agent_policy(
                agent_policy_id=agent_policy_id
            )
            assert deleted.body["id"] == agent_policy_id

        with pytest.raises(NotFoundError):
            kibana_client.fleet_policies.get_agent_policy(
                agent_policy_id=agent_policy_id
            )

    def test_get_missing_agent_policy_raises_not_found(self, kibana_client):
        """Getting a nonexistent agent policy raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.fleet_policies.get_agent_policy(
                agent_policy_id=f"{PREFIX}-does-not-exist"
            )

    def test_bulk_get(self, kibana_client, agent_policy):
        """Bulk get returns the requested policies; missing IDs skippable."""
        items = kibana_client.fleet_policies.bulk_get_agent_policies(
            ids=[agent_policy], full=True
        ).body["items"]
        assert len(items) == 1
        assert items[0]["id"] == agent_policy

        items = kibana_client.fleet_policies.bulk_get_agent_policies(
            ids=[agent_policy, f"{PREFIX}-missing"], ignore_missing=True
        ).body["items"]
        assert [item["id"] for item in items] == [agent_policy]

    def test_copy(self, kibana_client, agent_policy):
        """Copying an agent policy creates a new policy with the new name."""
        copy_name = _unique_name("copy")
        copied = kibana_client.fleet_policies.copy_agent_policy(
            agent_policy_id=agent_policy,
            name=copy_name,
            description="copied by kibana-py integration test",
        ).body["item"]
        try:
            assert copied["id"] != agent_policy
            assert copied["name"] == copy_name
        finally:
            _delete_agent_policy_quietly(kibana_client, copied["id"])


class TestAgentPolicyDocumentsIntegration:
    """Download / full / outputs / auto-upgrade status round trips."""

    def test_download_yaml(self, kibana_client, agent_policy):
        """The download endpoint returns the policy as a YAML string."""
        response = kibana_client.fleet_policies.download_agent_policy(
            agent_policy_id=agent_policy
        )
        assert isinstance(response.body, str)
        assert f"id: {agent_policy}" in response.body
        assert "outputs:" in response.body

    def test_get_full_agent_policy(self, kibana_client, agent_policy):
        """The full endpoint returns the compiled policy document as JSON."""
        item = kibana_client.fleet_policies.get_full_agent_policy(
            agent_policy_id=agent_policy
        ).body["item"]
        assert item["id"] == agent_policy
        assert "default" in item["outputs"]
        assert item["outputs"]["default"]["type"] == "elasticsearch"

    def test_get_full_agent_policy_standalone(self, kibana_client, agent_policy):
        """The standalone variant of the full policy is also served."""
        item = kibana_client.fleet_policies.get_full_agent_policy(
            agent_policy_id=agent_policy, standalone=True
        ).body["item"]
        assert "outputs" in item

    def test_outputs_single_and_bulk(self, kibana_client, agent_policy):
        """Outputs endpoints report the default Fleet output."""
        item = kibana_client.fleet_policies.get_agent_policy_outputs(
            agent_policy_id=agent_policy
        ).body["item"]
        assert item["data"]["output"]["id"] == "fleet-default-output"
        assert item["monitoring"]["output"]["id"] == "fleet-default-output"

        items = kibana_client.fleet_policies.get_agent_policies_outputs(
            ids=[agent_policy]
        ).body["items"]
        assert len(items) == 1
        assert items[0]["agentPolicyId"] == agent_policy

    def test_auto_upgrade_agents_status(self, kibana_client, agent_policy):
        """Auto-upgrade status reports zero agents on a stack without agents."""
        status = kibana_client.fleet_policies.get_auto_upgrade_agents_status(
            agent_policy_id=agent_policy
        ).body
        assert status["totalAgents"] == 0
        assert status["currentVersions"] == []


class TestPackagePolicyCrudIntegration:
    """CRUD round trips for package policies (udp package)."""

    def test_create_get_update_list_bulk_delete(
        self, kibana_client, agent_policy, udp_package_version
    ):
        """Full lifecycle for a package policy, ending in bulk delete."""
        name = _unique_name("ppcrud")
        created = kibana_client.options(
            request_timeout=120.0
        ).fleet_policies.create_package_policy(
            name=name,
            package={"name": TEST_PACKAGE, "version": udp_package_version},
            policy_ids=[agent_policy],
            inputs=_udp_inputs(),
            description="initial description",
        )
        package_policy_id = created.body["item"]["id"]
        try:
            assert created.body["item"]["name"] == name
            assert created.body["item"]["policy_ids"] == [agent_policy]
            assert created.body["item"]["package"]["name"] == TEST_PACKAGE

            fetched = kibana_client.fleet_policies.get_package_policy(
                package_policy_id=package_policy_id
            ).body["item"]
            assert fetched["id"] == package_policy_id
            assert fetched["description"] == "initial description"

            updated = kibana_client.fleet_policies.update_package_policy(
                package_policy_id=package_policy_id,
                package={"name": TEST_PACKAGE, "version": udp_package_version},
                name=name,
                description="updated description",
            ).body["item"]
            assert updated["description"] == "updated description"

            found = kibana_client.fleet_policies.get_package_policies(
                kuery=f'ingest-package-policies.name:"{name}"'
            ).body
            assert found["total"] == 1
            assert found["items"][0]["id"] == package_policy_id

            items = kibana_client.fleet_policies.bulk_get_package_policies(
                ids=[package_policy_id]
            ).body["items"]
            assert items[0]["id"] == package_policy_id
        finally:
            results = kibana_client.fleet_policies.bulk_delete_package_policies(
                package_policy_ids=[package_policy_id], force=True
            ).body
            assert results[0]["id"] == package_policy_id
            assert results[0]["success"] is True

        with pytest.raises(NotFoundError):
            kibana_client.fleet_policies.get_package_policy(
                package_policy_id=package_policy_id
            )

    def test_delete_single_package_policy(self, kibana_client, package_policy):
        """The DELETE-by-id endpoint removes a package policy."""
        deleted = kibana_client.fleet_policies.delete_package_policy(
            package_policy_id=package_policy, force=True
        )
        assert deleted.body["id"] == package_policy

        with pytest.raises(NotFoundError):
            kibana_client.fleet_policies.get_package_policy(
                package_policy_id=package_policy
            )

    def test_upgrade_and_dry_run(self, kibana_client, package_policy):
        """Upgrade dry run reports a diff; upgrade to the same version works."""
        dry_run = kibana_client.fleet_policies.upgrade_package_policies_dry_run(
            package_policy_ids=[package_policy]
        ).body
        assert len(dry_run) == 1
        assert dry_run[0]["hasErrors"] is False
        assert len(dry_run[0]["diff"]) == 2  # current vs proposed

        results = kibana_client.fleet_policies.upgrade_package_policies(
            package_policy_ids=[package_policy]
        ).body
        assert len(results) == 1
        assert results[0]["id"] == package_policy
        assert results[0]["success"] is True


class TestAgentlessPoliciesIntegration:
    """Agentless policies on a self-managed stack (feature unavailable)."""

    def test_create_agentless_policy_rejected_on_self_managed(
        self, kibana_client, udp_package_version
    ):
        """Self-managed deployments reject agentless policy creation (400).

        Asserting the exact server message proves the request reached the
        real /api/fleet/agentless_policies handler.
        """
        with pytest.raises(BadRequestError) as excinfo:
            kibana_client.fleet_policies.create_agentless_policy(
                name=_unique_name("agentless"),
                package={"name": TEST_PACKAGE, "version": udp_package_version},
            )
        assert "agentless" in str(excinfo.value)
        assert "serverless and cloud environments" in str(excinfo.value)

    def test_delete_agentless_policy_unknown_id_is_idempotent(self, kibana_client):
        """Live 9.4.3 responds 200 with the echoed id for unknown policies."""
        policy_id = _unique_name("agentless-del")
        response = kibana_client.fleet_policies.delete_agentless_policy(
            policy_id=policy_id
        )
        assert response.meta.status == 200
        assert response.body["id"] == policy_id


class TestAsyncFleetPoliciesIntegration:
    """Async round-trip integration tests for the Fleet policies API."""

    async def test_async_agent_and_package_policy_lifecycle(self, udp_package_version):
        """Create, read, download and delete policies with the async client."""
        client = create_test_async_kibana_client()
        agent_policy_id = None
        try:
            created = (
                await client.fleet_policies.create_agent_policy(
                    name=_unique_name("async-ap"),
                    namespace="default",
                    sys_monitoring=False,
                )
            ).body["item"]
            agent_policy_id = created["id"]

            fetched = (
                await client.fleet_policies.get_agent_policy(
                    agent_policy_id=agent_policy_id
                )
            ).body["item"]
            assert fetched["id"] == agent_policy_id

            items = (
                await client.fleet_policies.bulk_get_agent_policies(
                    ids=[agent_policy_id]
                )
            ).body["items"]
            assert items[0]["id"] == agent_policy_id

            yaml_doc = (
                await client.fleet_policies.download_agent_policy(
                    agent_policy_id=agent_policy_id
                )
            ).body
            assert f"id: {agent_policy_id}" in yaml_doc

            pkg = (
                await client.options(
                    request_timeout=120.0
                ).fleet_policies.create_package_policy(
                    name=_unique_name("async-pp"),
                    package={"name": TEST_PACKAGE, "version": udp_package_version},
                    policy_ids=[agent_policy_id],
                    inputs=_udp_inputs(),
                )
            ).body["item"]

            deleted = (
                await client.fleet_policies.delete_package_policy(
                    package_policy_id=pkg["id"], force=True
                )
            ).body
            assert deleted["id"] == pkg["id"]
        finally:
            if agent_policy_id is not None:
                try:
                    await client.fleet_policies.delete_agent_policy(
                        agent_policy_id=agent_policy_id, force=True
                    )
                except NotFoundError, BadRequestError:
                    pass
            await client.close()


class TestFleetPoliciesClientProperties:
    """Test FleetPoliciesClient wiring on the main client."""

    def test_fleet_policies_client_accessible(self, kibana_client):
        """The fleet_policies namespace is accessible from the main client."""
        from kibana._sync.client.fleet_policies import FleetPoliciesClient

        assert hasattr(kibana_client, "fleet_policies")
        assert isinstance(kibana_client.fleet_policies, FleetPoliciesClient)

    def test_fleet_policies_client_caching(self, kibana_client):
        """The fleet_policies client instance is cached."""
        assert kibana_client.fleet_policies is kibana_client.fleet_policies
