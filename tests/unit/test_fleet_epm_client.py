"""Unit tests for FleetEpmClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.fleet_epm import FleetEpmClient
from kibana.exceptions import BadRequestError, NotFoundError


def _mock_response(mock_transport, body=None, status=200):
    """Install a canned response on the mock transport and return it."""
    response = ObjectApiResponse(
        body=body if body is not None else {},
        meta=Mock(status=status, headers={}),
    )
    mock_transport.perform_request.return_value = response
    return response


def _call_kwargs(mock_transport):
    """Return the kwargs of the last transport call."""
    return mock_transport.perform_request.call_args[1]


class TestFleetEpmClientInitialization:
    """Test FleetEpmClient initialization and wiring."""

    def test_fleet_epm_client_initialization(self, mock_transport):
        """Test that FleetEpmClient can be initialized with a parent client."""
        client = Kibana(_transport=mock_transport)
        fleet_epm_client = FleetEpmClient(client)
        assert fleet_epm_client._client is client

    def test_fleet_epm_property_returns_client(self, mock_transport):
        """Test that client.fleet_epm returns a FleetEpmClient instance."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.fleet_epm, FleetEpmClient)

    def test_fleet_epm_property_caching(self, mock_transport):
        """Test that the fleet_epm property returns the same instance."""
        client = Kibana(_transport=mock_transport)
        assert client.fleet_epm is client.fleet_epm


class TestPackageDiscovery:
    """Tests for category/package listing methods."""

    def test_get_categories(self, mock_transport):
        """Test GET /api/fleet/epm/categories without params."""
        _mock_response(mock_transport, {"items": [{"id": "custom", "count": 3}]})
        client = Kibana(_transport=mock_transport)

        result = client.fleet_epm.get_categories()

        assert result.body["items"][0]["id"] == "custom"
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/fleet/epm/categories"
        assert kwargs["headers"]["accept"] == "application/json"

    def test_get_categories_with_params(self, mock_transport):
        """Test category query params are encoded as lowercase booleans."""
        _mock_response(mock_transport, {"items": []})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.get_categories(prerelease=True, include_policy_templates=False)

        kwargs = _call_kwargs(mock_transport)
        assert (
            kwargs["target"]
            == "/api/fleet/epm/categories?prerelease=true&include_policy_templates=false"
        )

    def test_get_packages_with_params(self, mock_transport):
        """Test GET /api/fleet/epm/packages with all query params."""
        _mock_response(mock_transport, {"items": []})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.get_packages(
            category="custom",
            prerelease=False,
            exclude_install_status=True,
            with_package_policies_count=True,
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == (
            "/api/fleet/epm/packages?category=custom&prerelease=false"
            "&excludeInstallStatus=true&withPackagePoliciesCount=true"
        )

    def test_get_installed_packages(self, mock_transport):
        """Test GET /api/fleet/epm/packages/installed with params."""
        _mock_response(mock_transport, {"items": [], "total": 0})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.get_installed_packages(
            data_stream_type="logs",
            show_only_active_data_streams=False,
            name_query="tcp",
            per_page=10,
            sort_order="asc",
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == (
            "/api/fleet/epm/packages/installed?dataStreamType=logs"
            "&showOnlyActiveDataStreams=false&nameQuery=tcp&perPage=10"
            "&sortOrder=asc"
        )

    def test_get_limited_packages(self, mock_transport):
        """Test GET /api/fleet/epm/packages/limited."""
        _mock_response(mock_transport, {"items": []})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.get_limited_packages()

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/fleet/epm/packages/limited"

    def test_get_package_latest(self, mock_transport):
        """Test GET /api/fleet/epm/packages/{pkgName} (no version)."""
        _mock_response(mock_transport, {"item": {"name": "tcp", "version": "2.3.1"}})
        client = Kibana(_transport=mock_transport)

        result = client.fleet_epm.get_package(pkg_name="tcp")

        assert result.body["item"]["name"] == "tcp"
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/fleet/epm/packages/tcp"

    def test_get_package_with_version_and_params(self, mock_transport):
        """Test GET /api/fleet/epm/packages/{pkgName}/{pkgVersion} with params."""
        _mock_response(mock_transport, {"item": {"name": "tcp"}})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.get_package(
            pkg_name="tcp",
            pkg_version="2.3.1",
            ignore_unverified=True,
            prerelease=False,
            full=True,
            with_metadata=True,
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["target"] == (
            "/api/fleet/epm/packages/tcp/2.3.1?ignoreUnverified=true"
            "&prerelease=false&full=true&withMetadata=true"
        )

    def test_get_package_stats(self, mock_transport):
        """Test GET /api/fleet/epm/packages/{pkgName}/stats."""
        _mock_response(mock_transport, {"response": {"package_policy_count": 0}})
        client = Kibana(_transport=mock_transport)

        result = client.fleet_epm.get_package_stats(pkg_name="tcp")

        assert result.body["response"]["package_policy_count"] == 0
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/fleet/epm/packages/tcp/stats"

    def test_get_package_file_preserves_slashes(self, mock_transport):
        """Test GET package file path keeps slashes but quotes segments."""
        _mock_response(mock_transport, {})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.get_package_file(
            pkg_name="tcp", pkg_version="2.3.1", file_path="docs/README.md"
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/fleet/epm/packages/tcp/2.3.1/docs/README.md"

    def test_get_package_dependencies(self, mock_transport):
        """Test GET /api/fleet/epm/packages/{pkgName}/{pkgVersion}/dependencies."""
        _mock_response(mock_transport, {"items": []})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.get_package_dependencies(pkg_name="tcp", pkg_version="2.3.1")

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/fleet/epm/packages/tcp/2.3.1/dependencies"

    def test_get_verification_key_id(self, mock_transport):
        """Test GET /api/fleet/epm/verification_key_id."""
        _mock_response(mock_transport, {"id": "d27d666cd88e42b4"})
        client = Kibana(_transport=mock_transport)

        result = client.fleet_epm.get_verification_key_id()

        assert result.body["id"] == "d27d666cd88e42b4"
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/fleet/epm/verification_key_id"


class TestInstallUpdateUninstall:
    """Tests for install/update/uninstall/rollback methods."""

    def test_install_package_latest_no_body(self, mock_transport):
        """Test POST install without version or body options."""
        _mock_response(mock_transport, {"items": [], "_meta": {"name": "tcp"}})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.install_package(pkg_name="tcp")

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/fleet/epm/packages/tcp"
        assert "body" not in kwargs
        assert kwargs["headers"]["kbn-xsrf"] == "true"

    def test_install_package_with_version_body_and_params(self, mock_transport):
        """Test POST install with pinned version, body and query params."""
        _mock_response(mock_transport, {"items": []})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.install_package(
            pkg_name="tcp",
            pkg_version="2.3.0",
            force=True,
            ignore_constraints=True,
            prerelease=False,
            ignore_mapping_update_errors=True,
            skip_data_stream_rollover=False,
            skip_dependency_check=True,
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["target"] == (
            "/api/fleet/epm/packages/tcp/2.3.0?prerelease=false"
            "&ignoreMappingUpdateErrors=true&skipDataStreamRollover=false"
            "&skipDependencyCheck=true"
        )
        assert kwargs["body"] == {"force": True, "ignore_constraints": True}

    def test_install_package_by_upload(self, mock_transport):
        """Test POST /api/fleet/epm/packages raw archive upload."""
        _mock_response(
            mock_transport, {"items": [], "_meta": {"install_source": "upload"}}
        )
        client = Kibana(_transport=mock_transport)
        archive = b"PK\x03\x04fake-zip-bytes"

        result = client.fleet_epm.install_package_by_upload(
            content=archive,
            content_type="application/zip",
            ignore_mapping_update_errors=False,
            skip_data_stream_rollover=True,
        )

        assert result.body["_meta"]["install_source"] == "upload"
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == (
            "/api/fleet/epm/packages?ignoreMappingUpdateErrors=false"
            "&skipDataStreamRollover=true"
        )
        assert kwargs["body"] == archive
        assert kwargs["headers"]["content-type"] == "application/zip"

    def test_install_package_by_upload_registers_raw_serializer(self, mock_transport):
        """Test that uploads register a pass-through serializer for the mimetype."""
        from elastic_transport import SerializerCollection

        from kibana.serializer import DEFAULT_SERIALIZERS

        _mock_response(mock_transport, {"items": []})
        mock_transport.serializers = SerializerCollection(DEFAULT_SERIALIZERS)
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.install_package_by_upload(content=b"PK\x03\x04fake")

        serializer = mock_transport.serializers.get_serializer("application/zip")
        assert serializer.dumps(b"PK\x03\x04fake") == b"PK\x03\x04fake"

    def test_install_package_by_upload_gzip_content_type(self, mock_transport):
        """Test that the upload content type can be overridden to gzip."""
        _mock_response(mock_transport, {"items": []})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.install_package_by_upload(
            content=b"\x1f\x8bfake", content_type="application/gzip"
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["target"] == "/api/fleet/epm/packages"
        assert kwargs["headers"]["content-type"] == "application/gzip"

    def test_update_package(self, mock_transport):
        """Test PUT /api/fleet/epm/packages/{pkgName} settings update."""
        _mock_response(mock_transport, {"item": {"keepPoliciesUpToDate": True}})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.update_package(
            pkg_name="tcp",
            keep_policies_up_to_date=True,
            namespace_customization_enabled_for=["default"],
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "PUT"
        assert kwargs["target"] == "/api/fleet/epm/packages/tcp"
        assert kwargs["body"] == {
            "keepPoliciesUpToDate": True,
            "namespace_customization_enabled_for": ["default"],
        }

    def test_update_package_with_version(self, mock_transport):
        """Test PUT /api/fleet/epm/packages/{pkgName}/{pkgVersion}."""
        _mock_response(mock_transport, {"item": {}})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.update_package(
            pkg_name="tcp", pkg_version="2.3.1", keep_policies_up_to_date=False
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["target"] == "/api/fleet/epm/packages/tcp/2.3.1"
        assert kwargs["body"] == {"keepPoliciesUpToDate": False}

    def test_uninstall_package(self, mock_transport):
        """Test DELETE /api/fleet/epm/packages/{pkgName} with force."""
        _mock_response(mock_transport, {"items": []})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.uninstall_package(pkg_name="tcp", force=True)

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "DELETE"
        assert kwargs["target"] == "/api/fleet/epm/packages/tcp?force=true"

    def test_uninstall_package_with_version(self, mock_transport):
        """Test DELETE /api/fleet/epm/packages/{pkgName}/{pkgVersion}."""
        _mock_response(mock_transport, {"items": []})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.uninstall_package(pkg_name="tcp", pkg_version="2.3.1")

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["target"] == "/api/fleet/epm/packages/tcp/2.3.1"

    def test_rollback_package(self, mock_transport):
        """Test POST /api/fleet/epm/packages/{pkgName}/rollback."""
        _mock_response(mock_transport, {"version": "2.3.0", "success": True})
        client = Kibana(_transport=mock_transport)

        result = client.fleet_epm.rollback_package(pkg_name="tcp")

        assert result.body["success"] is True
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/fleet/epm/packages/tcp/rollback"
        assert "body" not in kwargs

    def test_review_upgrade(self, mock_transport):
        """Test POST /api/fleet/epm/packages/{pkgName}/review_upgrade."""
        _mock_response(mock_transport, {})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.review_upgrade(
            pkg_name="tcp", action="accept", target_version="2.3.1"
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/fleet/epm/packages/tcp/review_upgrade"
        assert kwargs["body"] == {"action": "accept", "target_version": "2.3.1"}

    def test_pkg_name_is_url_encoded(self, mock_transport):
        """Test that package names are URL-encoded in paths."""
        _mock_response(mock_transport, {"item": {}})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.get_package(pkg_name="weird pkg/name")

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["target"] == "/api/fleet/epm/packages/weird%20pkg%2Fname"


class TestBulkOperations:
    """Tests for bulk install/upgrade/uninstall/rollback and task statuses."""

    def test_bulk_install_packages(self, mock_transport):
        """Test POST /api/fleet/epm/packages/_bulk passes packages through."""
        _mock_response(mock_transport, {"items": []})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.bulk_install_packages(
            packages=["tcp", {"name": "udp", "version": "2.5.1"}],
            force=True,
            prerelease=True,
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/fleet/epm/packages/_bulk?prerelease=true"
        assert kwargs["body"] == {
            "packages": ["tcp", {"name": "udp", "version": "2.5.1"}],
            "force": True,
        }

    def test_bulk_upgrade_packages_normalizes_strings(self, mock_transport):
        """Test bulk upgrade converts name strings to {"name": ...} dicts."""
        _mock_response(mock_transport, {"taskId": "t-1"})
        client = Kibana(_transport=mock_transport)

        result = client.fleet_epm.bulk_upgrade_packages(
            packages=["tcp", {"name": "udp", "version": "2.5.1"}],
            force=False,
            prerelease=False,
            upgrade_package_policies=True,
        )

        assert result.body["taskId"] == "t-1"
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/fleet/epm/packages/_bulk_upgrade"
        assert kwargs["body"] == {
            "packages": [{"name": "tcp"}, {"name": "udp", "version": "2.5.1"}],
            "force": False,
            "prerelease": False,
            "upgrade_package_policies": True,
        }

    def test_get_bulk_upgrade_status(self, mock_transport):
        """Test GET /api/fleet/epm/packages/_bulk_upgrade/{taskId}."""
        _mock_response(mock_transport, {"status": "success"})
        client = Kibana(_transport=mock_transport)

        result = client.fleet_epm.get_bulk_upgrade_status(task_id="t-1")

        assert result.body["status"] == "success"
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/fleet/epm/packages/_bulk_upgrade/t-1"

    def test_bulk_uninstall_packages(self, mock_transport):
        """Test POST /api/fleet/epm/packages/_bulk_uninstall body shape."""
        _mock_response(mock_transport, {"taskId": "t-2"})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.bulk_uninstall_packages(
            packages=[{"name": "tcp", "version": "2.3.1"}], force=True
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/fleet/epm/packages/_bulk_uninstall"
        assert kwargs["body"] == {
            "packages": [{"name": "tcp", "version": "2.3.1"}],
            "force": True,
        }

    def test_get_bulk_uninstall_status(self, mock_transport):
        """Test GET /api/fleet/epm/packages/_bulk_uninstall/{taskId}."""
        _mock_response(mock_transport, {"status": "pending"})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.get_bulk_uninstall_status(task_id="t-2")

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/fleet/epm/packages/_bulk_uninstall/t-2"

    def test_bulk_rollback_packages_normalizes_strings(self, mock_transport):
        """Test POST /api/fleet/epm/packages/_bulk_rollback body shape."""
        _mock_response(mock_transport, {"taskId": "t-3"})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.bulk_rollback_packages(packages=["tcp"])

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/fleet/epm/packages/_bulk_rollback"
        assert kwargs["body"] == {"packages": [{"name": "tcp"}]}

    def test_get_bulk_rollback_status(self, mock_transport):
        """Test GET /api/fleet/epm/packages/_bulk_rollback/{taskId}."""
        _mock_response(mock_transport, {"status": "success", "results": []})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.get_bulk_rollback_status(task_id="t-3")

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/fleet/epm/packages/_bulk_rollback/t-3"


class TestAssets:
    """Tests for asset-level methods."""

    def test_bulk_get_assets(self, mock_transport):
        """Test POST /api/fleet/epm/bulk_assets body shape."""
        _mock_response(mock_transport, {"items": []})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.bulk_get_assets(
            asset_ids=[{"id": "logs-tcp.generic", "type": "index_template"}]
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/fleet/epm/bulk_assets"
        assert kwargs["body"] == {
            "assetIds": [{"id": "logs-tcp.generic", "type": "index_template"}]
        }

    def test_install_kibana_assets(self, mock_transport):
        """Test POST kibana_assets with force and space_ids body."""
        _mock_response(mock_transport, {"success": True})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.install_kibana_assets(
            pkg_name="tcp", pkg_version="2.3.1", force=True, space_ids=["default"]
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/fleet/epm/packages/tcp/2.3.1/kibana_assets"
        assert kwargs["body"] == {"force": True, "space_ids": ["default"]}

    def test_install_kibana_assets_no_body(self, mock_transport):
        """Test POST kibana_assets omits the body when no options given."""
        _mock_response(mock_transport, {"success": True})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.install_kibana_assets(pkg_name="tcp", pkg_version="2.3.1")

        kwargs = _call_kwargs(mock_transport)
        assert "body" not in kwargs

    def test_delete_kibana_assets(self, mock_transport):
        """Test DELETE kibana_assets."""
        _mock_response(mock_transport, {"success": True})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.delete_kibana_assets(pkg_name="tcp", pkg_version="2.3.1")

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "DELETE"
        assert kwargs["target"] == "/api/fleet/epm/packages/tcp/2.3.1/kibana_assets"

    def test_install_rule_assets(self, mock_transport):
        """Test POST rule_assets with force body."""
        _mock_response(mock_transport, {"success": True})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.install_rule_assets(
            pkg_name="tcp", pkg_version="2.3.1", force=True
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/fleet/epm/packages/tcp/2.3.1/rule_assets"
        assert kwargs["body"] == {"force": True}

    def test_delete_datastream_assets(self, mock_transport):
        """Test DELETE datastream_assets requires packagePolicyId param."""
        _mock_response(mock_transport, {"success": True})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.delete_datastream_assets(
            pkg_name="tcp", pkg_version="2.3.1", package_policy_id="pp-1"
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "DELETE"
        assert kwargs["target"] == (
            "/api/fleet/epm/packages/tcp/2.3.1/datastream_assets"
            "?packagePolicyId=pp-1"
        )

    def test_authorize_transforms_normalizes_strings(self, mock_transport):
        """Test POST transforms/authorize converts ID strings to dicts."""
        _mock_response(mock_transport, {})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.authorize_transforms(
            pkg_name="ti_util",
            pkg_version="1.1.0",
            transforms=["transform-1", {"transformId": "transform-2"}],
            prerelease=True,
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == (
            "/api/fleet/epm/packages/ti_util/1.1.0/transforms/authorize"
            "?prerelease=true"
        )
        assert kwargs["body"] == {
            "transforms": [
                {"transformId": "transform-1"},
                {"transformId": "transform-2"},
            ]
        }


class TestCustomIntegrations:
    """Tests for custom integration methods."""

    def test_create_custom_integration(self, mock_transport):
        """Test POST /api/fleet/epm/custom_integrations body shape."""
        _mock_response(
            mock_transport, {"items": [], "_meta": {"install_source": "custom"}}
        )
        client = Kibana(_transport=mock_transport)

        result = client.fleet_epm.create_custom_integration(
            integration_name="my_app",
            datasets=[{"name": "my_app.access", "type": "logs"}],
            force=True,
        )

        assert result.body["_meta"]["install_source"] == "custom"
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/fleet/epm/custom_integrations"
        assert kwargs["body"] == {
            "integrationName": "my_app",
            "datasets": [{"name": "my_app.access", "type": "logs"}],
            "force": True,
        }

    def test_update_custom_integration(self, mock_transport):
        """Test PUT /api/fleet/epm/custom_integrations/{pkgName} body shape."""
        _mock_response(mock_transport, {"id": "my_app", "result": {"version": "1.0.1"}})
        client = Kibana(_transport=mock_transport)

        result = client.fleet_epm.update_custom_integration(
            pkg_name="my_app",
            read_me_data="# My app",
            categories=["custom"],
        )

        assert result.body["result"]["version"] == "1.0.1"
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "PUT"
        assert kwargs["target"] == "/api/fleet/epm/custom_integrations/my_app"
        assert kwargs["body"] == {
            "readMeData": "# My app",
            "categories": ["custom"],
        }


class TestDataStreamsAndTemplates:
    """Tests for data stream listing and inputs templates."""

    def test_get_data_streams(self, mock_transport):
        """Test GET /api/fleet/data_streams."""
        _mock_response(mock_transport, {"data_streams": []})
        client = Kibana(_transport=mock_transport)

        result = client.fleet_epm.get_data_streams()

        assert result.body["data_streams"] == []
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/fleet/data_streams"

    def test_find_data_streams(self, mock_transport):
        """Test GET /api/fleet/epm/data_streams with all params."""
        _mock_response(mock_transport, {"items": []})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.find_data_streams(
            type="logs",
            dataset_query="tcp",
            sort_order="desc",
            uncategorised_only=True,
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == (
            "/api/fleet/epm/data_streams?type=logs&datasetQuery=tcp"
            "&sortOrder=desc&uncategorisedOnly=true"
        )

    def test_get_inputs_template(self, mock_transport):
        """Test GET /api/fleet/epm/templates/{pkgName}/{pkgVersion}/inputs."""
        _mock_response(mock_transport, {"inputs": []})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.get_inputs_template(
            pkg_name="tcp",
            pkg_version="2.3.1",
            format="json",
            prerelease=False,
            ignore_unverified=True,
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == (
            "/api/fleet/epm/templates/tcp/2.3.1/inputs?format=json"
            "&prerelease=false&ignoreUnverified=true"
        )


class TestSpaceScoping:
    """Test that space_id builds /s/<space>/... paths."""

    def test_get_package_in_space(self, mock_transport):
        """Test GET package in a specific space (validation disabled)."""
        _mock_response(mock_transport, {"item": {}})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.get_package(
            pkg_name="tcp", space_id="marketing", validate_spaces=False
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["target"] == "/s/marketing/api/fleet/epm/packages/tcp"

    def test_install_package_in_space(self, mock_transport):
        """Test POST install in a specific space (validation disabled)."""
        _mock_response(mock_transport, {"items": []})
        client = Kibana(_transport=mock_transport)

        client.fleet_epm.install_package(
            pkg_name="tcp",
            pkg_version="2.3.1",
            space_id="marketing",
            validate_spaces=False,
        )

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["target"] == "/s/marketing/api/fleet/epm/packages/tcp/2.3.1"


class TestErrorHandling:
    """Test error mapping for Fleet EPM responses."""

    def test_get_package_not_found(self, mock_transport):
        """Test that a 404 response raises NotFoundError."""
        _mock_response(
            mock_transport,
            {"statusCode": 404, "error": "Not Found", "message": "Not Found"},
            status=404,
        )
        client = Kibana(_transport=mock_transport)

        with pytest.raises(NotFoundError):
            client.fleet_epm.get_package(pkg_name="does-not-exist")

    def test_install_package_bad_request(self, mock_transport):
        """Test that a 400 response raises BadRequestError with the message."""
        _mock_response(
            mock_transport,
            {
                "statusCode": 400,
                "error": "Bad Request",
                "message": "tcp-2.3.0 is out-of-date and cannot be installed or updated",
            },
            status=400,
        )
        client = Kibana(_transport=mock_transport)

        with pytest.raises(BadRequestError, match="out-of-date"):
            client.fleet_epm.install_package(pkg_name="tcp", pkg_version="2.3.0")
