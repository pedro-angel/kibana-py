"""Integration tests for FleetEpmClient against a live Kibana instance.

These tests install/uninstall real (lightweight) packages from the Elastic
Package Registry, so they need internet access from the Kibana container:

- ``tcp`` (Custom TCP Logs input package) for the full lifecycle tests
- ``winlog`` (Custom Windows Event Logs input package) for the bulk install
  test

Package-registry packages cannot be name-prefixed; ``tcp``/``winlog`` were
chosen because nothing else on the shared dev stack uses them. Custom
integrations created here use the ``kbnpy_fleet_epm_`` prefix.
"""

import ssl
import time
import urllib.error
import urllib.request
import uuid

import certifi
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

# Lifecycle package: lightweight input package with a pinned older version
# available on the registry (2.3.0) and a newer latest version (2.3.1+).
PKG = "tcp"
PKG_OLD_VERSION = "2.3.0"

# Secondary package for the bulk-install test.
BULK_PKG = "winlog"

TASK_TIMEOUT = 180.0


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
def basic_kibana_client():
    """Create a basic-auth Kibana client.

    The transforms authorization endpoint generates a secondary
    authorization from the caller's credentials; with API-key auth on this
    stack it fails with a 500 ("A valid secondary authorization with
    sufficient `manage_transform` permission is needed"), while basic auth
    works.
    """
    try:
        client = create_test_kibana_client(auth_method="basic")
    except ValueError:
        pytest.skip("Basic auth credentials not available")
    yield client
    client.close()


def _force_uninstall(client, pkg_name: str) -> None:
    """Uninstall a package, ignoring the case where it is not installed."""
    try:
        client.fleet_epm.uninstall_package(pkg_name=pkg_name, force=True)
    except Exception:
        pass


def _wait_for_bulk_task(get_status, task_id: str, timeout: float = TASK_TIMEOUT):
    """Poll a bulk-operation task status until it leaves 'pending'."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = get_status(task_id=task_id).body
        if body.get("status") != "pending":
            return body
        time.sleep(2)
    pytest.fail(f"Bulk task {task_id} still pending after {timeout}s")


class TestFleetEpmDiscovery:
    """Read-only discovery endpoints against the live registry."""

    def test_get_categories(self, kibana_client):
        """Categories come back with ids and counts."""
        result = kibana_client.fleet_epm.get_categories()
        assert result.meta.status == 200
        items = result.body["items"]
        assert len(items) > 0
        assert {"id", "title", "count"} <= set(items[0].keys())

    def test_get_categories_with_prerelease(self, kibana_client):
        """The prerelease query parameter is accepted."""
        result = kibana_client.fleet_epm.get_categories(
            prerelease=True, include_policy_templates=False
        )
        assert len(result.body["items"]) > 0

    def test_get_packages_custom_category(self, kibana_client):
        """The custom category contains the tcp input package."""
        result = kibana_client.fleet_epm.get_packages(category="custom")
        names = [pkg["name"] for pkg in result.body["items"]]
        assert PKG in names

    def test_get_package_latest(self, kibana_client):
        """Fetching a package without a version returns the latest."""
        result = kibana_client.fleet_epm.get_package(pkg_name=PKG)
        item = result.body["item"]
        assert item["name"] == PKG
        assert item["latestVersion"] == item["version"]

    def test_get_package_pinned_version_with_metadata(self, kibana_client):
        """Fetching a pinned version with metadata works."""
        result = kibana_client.fleet_epm.get_package(
            pkg_name=PKG, pkg_version=PKG_OLD_VERSION, full=True, with_metadata=True
        )
        assert result.body["item"]["version"] == PKG_OLD_VERSION
        assert "metadata" in result.body

    def test_get_installed_packages(self, kibana_client):
        """Installed packages listing returns items and a total."""
        result = kibana_client.fleet_epm.get_installed_packages(
            per_page=5, sort_order="asc"
        )
        assert "items" in result.body
        assert "total" in result.body

    def test_get_limited_packages(self, kibana_client):
        """Limited package listing returns an items array."""
        result = kibana_client.fleet_epm.get_limited_packages()
        assert isinstance(result.body["items"], list)

    def test_get_verification_key_id(self, kibana_client):
        """The signature verification key ID is a non-empty string."""
        result = kibana_client.fleet_epm.get_verification_key_id()
        assert isinstance(result.body["id"], str)
        assert len(result.body["id"]) > 0

    def test_get_data_streams(self, kibana_client):
        """Fleet data streams endpoint returns a data_streams array."""
        result = kibana_client.fleet_epm.get_data_streams()
        assert isinstance(result.body["data_streams"], list)

    def test_find_data_streams(self, kibana_client):
        """EPM data streams endpoint returns an items array."""
        result = kibana_client.fleet_epm.find_data_streams(
            type="logs", sort_order="asc"
        )
        assert isinstance(result.body["items"], list)

    def test_get_package_dependencies(self, kibana_client):
        """Dependencies of an input package are an (empty) items array."""
        result = kibana_client.fleet_epm.get_package_dependencies(
            pkg_name=PKG, pkg_version=PKG_OLD_VERSION
        )
        assert isinstance(result.body["items"], list)

    def test_get_inputs_template_json(self, kibana_client):
        """The JSON inputs template contains the package's input type."""
        result = kibana_client.fleet_epm.get_inputs_template(
            pkg_name=PKG, pkg_version=PKG_OLD_VERSION, format="json"
        )
        assert result.body["inputs"][0]["type"] == PKG

    def test_get_inputs_template_yaml(self, kibana_client):
        """The YAML inputs template is returned as raw text."""
        result = kibana_client.fleet_epm.get_inputs_template(
            pkg_name=PKG, pkg_version=PKG_OLD_VERSION, format="yml"
        )
        assert "inputs" in str(result.body)

    def test_get_categories_in_default_space(self, kibana_client):
        """Space-scoped path /s/default/api/... works live."""
        result = kibana_client.fleet_epm.get_categories(space_id="default")
        assert len(result.body["items"]) > 0


class TestFleetEpmPackageLifecycle:
    """Full install / update / upgrade / rollback / uninstall lifecycle."""

    def test_install_upgrade_rollback_uninstall(
        self, kibana_client, basic_kibana_client
    ):
        """Install a pinned version, upgrade, roll back, bulk-uninstall."""
        fleet_epm = kibana_client.fleet_epm
        try:
            # Install a pinned outdated version (requires force).
            installed = fleet_epm.install_package(
                pkg_name=PKG, pkg_version=PKG_OLD_VERSION, force=True
            )
            assert installed.body["_meta"]["install_source"] == "registry"
            assert installed.body["_meta"]["name"] == PKG

            pkg = fleet_epm.get_package(pkg_name=PKG)
            assert pkg.body["item"]["status"] == "installed"
            assert pkg.body["item"]["installationInfo"]["version"] == PKG_OLD_VERSION

            # Update package settings.
            updated = fleet_epm.update_package(
                pkg_name=PKG, keep_policies_up_to_date=True
            )
            assert updated.body["item"]["name"] == PKG
            # Restore the setting to its default (False).
            fleet_epm.update_package(pkg_name=PKG, keep_policies_up_to_date=False)

            # Stats: no policies use the package.
            stats = fleet_epm.get_package_stats(pkg_name=PKG)
            assert stats.body["response"]["package_policy_count"] == 0

            # Package files are served from the installed archive.
            manifest = fleet_epm.get_package_file(
                pkg_name=PKG, pkg_version=PKG_OLD_VERSION, file_path="manifest.yml"
            )
            assert manifest.meta.status == 200
            assert f"name: {PKG}" in manifest.body

            # No pending policy upgrade review exists for the installed pkg.
            with pytest.raises(NotFoundError, match="No pending upgrade review for"):
                fleet_epm.review_upgrade(
                    pkg_name=PKG, action="accept", target_version="99.0.0"
                )

            # Transforms authorization. With an empty transform list the
            # endpoint re-authorizes any pending fleet-managed transforms;
            # the tcp input package ships none, but concurrent activity on a
            # shared stack may surface other pending transforms, so only the
            # response shape is asserted. Requires basic auth: see the
            # basic_kibana_client fixture.
            authorized = basic_kibana_client.fleet_epm.authorize_transforms(
                pkg_name=PKG, pkg_version=PKG_OLD_VERSION, transforms=[]
            )
            assert authorized.meta.status == 200
            results = list(authorized.body)
            assert all("transformId" in item for item in results)

            # (Re-)install Kibana assets and rule assets.
            kibana_assets = fleet_epm.install_kibana_assets(
                pkg_name=PKG, pkg_version=PKG_OLD_VERSION
            )
            assert kibana_assets.body["success"] is True

            rule_assets = fleet_epm.install_rule_assets(
                pkg_name=PKG, pkg_version=PKG_OLD_VERSION
            )
            assert rule_assets.body["success"] is True

            # Deleting Kibana assets in the install space is rejected.
            with pytest.raises(
                BadRequestError, match="Impossible to delete kibana assets"
            ):
                fleet_epm.delete_kibana_assets(
                    pkg_name=PKG, pkg_version=PKG_OLD_VERSION
                )

            # Bulk upgrade to the latest version (async task).
            started = fleet_epm.bulk_upgrade_packages(packages=[PKG])
            task_id = started.body["taskId"]
            status = _wait_for_bulk_task(fleet_epm.get_bulk_upgrade_status, task_id)
            assert status["status"] == "success"
            assert status["results"][0] == {"name": PKG, "success": True}

            latest_version = fleet_epm.get_package(pkg_name=PKG).body["item"][
                "installationInfo"
            ]["version"]
            assert latest_version != PKG_OLD_VERSION

            # Single-package rollback to the previous version.
            rolled_back = fleet_epm.rollback_package(pkg_name=PKG)
            assert rolled_back.body["success"] is True
            assert rolled_back.body["version"] == PKG_OLD_VERSION

            # Upgrade again, then bulk rollback (async task).
            started = fleet_epm.bulk_upgrade_packages(packages=[PKG])
            status = _wait_for_bulk_task(
                fleet_epm.get_bulk_upgrade_status, started.body["taskId"]
            )
            assert status["status"] == "success"

            started = fleet_epm.bulk_rollback_packages(packages=[PKG])
            status = _wait_for_bulk_task(
                fleet_epm.get_bulk_rollback_status, started.body["taskId"]
            )
            assert status["status"] == "success"
            assert status["results"][0] == {"name": PKG, "success": True}

            # Bulk uninstall (async task).
            started = fleet_epm.bulk_uninstall_packages(
                packages=[{"name": PKG, "version": PKG_OLD_VERSION}]
            )
            status = _wait_for_bulk_task(
                fleet_epm.get_bulk_uninstall_status, started.body["taskId"]
            )
            assert status["status"] == "success"

            pkg = fleet_epm.get_package(pkg_name=PKG)
            assert pkg.body["item"]["status"] == "not_installed"
        finally:
            _force_uninstall(kibana_client, PKG)

    def test_install_package_by_upload(self, kibana_client):
        """Upload a real registry archive to the upload-install endpoint."""
        fleet_epm = kibana_client.fleet_epm
        latest = fleet_epm.get_package(pkg_name=PKG).body["item"]["latestVersion"]
        url = f"https://epr.elastic.co/epr/{PKG}/{PKG}-{latest}.zip"
        try:
            context = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(url, timeout=60, context=context) as response:
                archive = response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            pytest.skip(f"Could not download {url} from the package registry: {exc}")

        try:
            result = fleet_epm.install_package_by_upload(
                content=archive, content_type="application/zip"
            )
            assert result.body["_meta"]["install_source"] == "upload"
            assert result.body["_meta"]["name"] == PKG

            pkg = fleet_epm.get_package(pkg_name=PKG)
            assert pkg.body["item"]["status"] == "installed"

            uninstalled = fleet_epm.uninstall_package(pkg_name=PKG)
            assert isinstance(uninstalled.body["items"], list)
        finally:
            _force_uninstall(kibana_client, PKG)


class TestFleetEpmBulkInstallAndAssets:
    """Synchronous bulk install plus asset lookups."""

    def test_bulk_install_and_bulk_get_assets(self, kibana_client):
        """Bulk-install a package and resolve one of its assets."""
        fleet_epm = kibana_client.fleet_epm
        try:
            result = fleet_epm.bulk_install_packages(packages=[BULK_PKG])
            items = result.body["items"]
            assert len(items) == 1
            assert items[0]["name"] == BULK_PKG
            assert "error" not in items[0]

            pkg = fleet_epm.get_package(pkg_name=BULK_PKG)
            assert pkg.body["item"]["status"] == "installed"

            # The input package ships a logs-<pkg>.generic index template.
            assets = fleet_epm.bulk_get_assets(
                asset_ids=[{"id": f"logs-{BULK_PKG}.generic", "type": "index_template"}]
            )
            asset = assets.body["items"][0]
            assert asset["id"] == f"logs-{BULK_PKG}.generic"
            assert asset["type"] == "index_template"
            assert "appLink" in asset
        finally:
            _force_uninstall(kibana_client, BULK_PKG)


class TestFleetEpmCustomIntegrations:
    """Custom integration create/update/delete round trip."""

    def test_custom_integration_lifecycle(self, kibana_client):
        """Create, update and delete a custom integration."""
        fleet_epm = kibana_client.fleet_epm
        name = f"kbnpy_fleet_epm_{uuid.uuid4().hex[:8]}"
        try:
            created = fleet_epm.create_custom_integration(
                integration_name=name,
                datasets=[{"name": f"{name}.access", "type": "logs"}],
            )
            assert created.body["_meta"]["install_source"] == "custom"
            assert created.body["_meta"]["name"] == name
            assert any(
                item["type"] == "index_template" for item in created.body["items"]
            )

            updated = fleet_epm.update_custom_integration(
                pkg_name=name,
                read_me_data=f"# {name}\n\nkibana-py integration test readme.",
                categories=["custom"],
            )
            assert updated.body["id"] == name
            assert updated.body["result"]["version"] == "1.0.1"

            # Delete via the package delete endpoint. Once deleted, the
            # custom package is gone entirely (it never existed in the
            # registry), so a subsequent get 404s.
            deleted = fleet_epm.uninstall_package(pkg_name=name, force=True)
            assert isinstance(deleted.body["items"], list)

            with pytest.raises(
                NotFoundError, match="package not installed or found in registry"
            ):
                fleet_epm.get_package(pkg_name=name, prerelease=True)
        finally:
            _force_uninstall(kibana_client, name)


class TestFleetEpmSemanticErrors:
    """Live semantic-error coverage for endpoints needing extra setup."""

    def test_get_package_not_found(self, kibana_client):
        """Unknown packages yield a 404 with the registry message."""
        with pytest.raises(
            NotFoundError, match="package not installed or found in registry"
        ):
            kibana_client.fleet_epm.get_package(pkg_name="kbnpy_no_such_pkg")

    def test_review_upgrade_package_not_installed(self, kibana_client):
        """review_upgrade 404s with a precise message for uninstalled pkgs."""
        with pytest.raises(
            NotFoundError, match="Error while reviewing upgrade: tcp is not installed"
        ):
            kibana_client.fleet_epm.review_upgrade(
                pkg_name=PKG, action="accept", target_version="99.0.0"
            )

    def test_rollback_package_not_installed(self, kibana_client):
        """rollback 400s naming the package when it was never installed."""
        with pytest.raises(
            BadRequestError, match=f"Failed to roll back package {BULK_PKG}"
        ):
            kibana_client.fleet_epm.rollback_package(pkg_name=BULK_PKG)

    def test_delete_datastream_assets_unknown_policy(self, kibana_client):
        """datastream_assets 404s naming the unknown package policy."""
        with pytest.raises(
            NotFoundError, match="Package policy with id kbnpy-bogus not found"
        ):
            kibana_client.fleet_epm.delete_datastream_assets(
                pkg_name=PKG,
                pkg_version=PKG_OLD_VERSION,
                package_policy_id="kbnpy-bogus",
            )

    def test_authorize_transforms_package_not_installed(self, basic_kibana_client):
        """transforms/authorize 404s when the package is not installed."""
        with pytest.raises(NotFoundError, match="not found"):
            basic_kibana_client.fleet_epm.authorize_transforms(
                pkg_name=PKG, pkg_version=PKG_OLD_VERSION, transforms=[]
            )


class TestAsyncFleetEpm:
    """Async client round trips against the live stack."""

    @pytest.mark.asyncio
    async def test_async_discovery(self, async_kibana_client):
        """Async discovery endpoints respond."""
        categories = await async_kibana_client.fleet_epm.get_categories()
        assert len(categories.body["items"]) > 0

        key = await async_kibana_client.fleet_epm.get_verification_key_id()
        assert isinstance(key.body["id"], str)

    @pytest.mark.asyncio
    async def test_async_custom_integration_round_trip(self, async_kibana_client):
        """Async create/update/delete round trip for a custom integration."""
        fleet_epm = async_kibana_client.fleet_epm
        name = f"kbnpy_fleet_epm_a{uuid.uuid4().hex[:8]}"
        try:
            created = await fleet_epm.create_custom_integration(
                integration_name=name,
                datasets=[{"name": f"{name}.events", "type": "logs"}],
            )
            assert created.body["_meta"]["install_source"] == "custom"

            updated = await fleet_epm.update_custom_integration(
                pkg_name=name, read_me_data="# async readme"
            )
            assert updated.body["result"]["version"] == "1.0.1"

            deleted = await fleet_epm.uninstall_package(pkg_name=name, force=True)
            assert isinstance(deleted.body["items"], list)
        finally:
            try:
                await fleet_epm.uninstall_package(pkg_name=name, force=True)
            except Exception:
                pass
