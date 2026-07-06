#!/usr/bin/env python3
"""
Fleet Elastic Package Manager (EPM) Management Example

This example shows the minimal code needed to:
1. Browse package categories and registry packages
2. Install a lightweight package (Custom TCP Logs) from the registry
3. Inspect the installed package (details, stats, manifest file)
4. Create and update a custom integration
5. Clean up (uninstall everything created here)

The example needs internet access from Kibana to reach the Elastic
Package Registry (https://epr.elastic.co).

Run this example:
    python examples/fleet_epm_management.py
"""

from utils import get_kibana_config

from kibana import Kibana

PKG = "tcp"
CUSTOM_INTEGRATION = "kbnpy_example_app"


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    fleet_epm = client.fleet_epm
    installed_pkg = False
    created_custom = False
    try:
        # 1. Browse categories and the custom-category packages
        categories = fleet_epm.get_categories()
        print(f"Registry has {len(categories.body['items'])} categories")

        custom_packages = fleet_epm.get_packages(category="custom")
        names = [pkg["name"] for pkg in custom_packages.body["items"]]
        print(f"'custom' category packages: {', '.join(names[:5])}, ...")

        # 2. Install the latest Custom TCP Logs package from the registry
        result = fleet_epm.install_package(pkg_name=PKG)
        installed_pkg = True
        print(
            f"Installed {result.body['_meta']['name']} "
            f"({len(result.body['items'])} assets, source: "
            f"{result.body['_meta']['install_source']})"
        )

        # 3. Inspect the installed package
        pkg = fleet_epm.get_package(pkg_name=PKG)
        version = pkg.body["item"]["version"]
        print(f"{PKG} status: {pkg.body['item']['status']} (version {version})")

        stats = fleet_epm.get_package_stats(pkg_name=PKG)
        print(
            f"{PKG} package policies: {stats.body['response']['package_policy_count']}"
        )

        manifest = fleet_epm.get_package_file(
            pkg_name=PKG, pkg_version=version, file_path="manifest.yml"
        )
        print(f"manifest.yml starts with: {manifest.body.splitlines()[0]!r}")

        # 4. Create and update a custom integration
        created = fleet_epm.create_custom_integration(
            integration_name=CUSTOM_INTEGRATION,
            datasets=[{"name": f"{CUSTOM_INTEGRATION}.access", "type": "logs"}],
        )
        created_custom = True
        print(f"Created custom integration ({len(created.body['items'])} assets)")

        updated = fleet_epm.update_custom_integration(
            pkg_name=CUSTOM_INTEGRATION,
            read_me_data="# kbnpy example app\n\nCreated by the kibana-py example.",
            categories=["custom"],
        )
        print(f"Updated custom integration to {updated.body['result']['version']}")
    finally:
        # 5. Clean up
        if created_custom:
            fleet_epm.uninstall_package(pkg_name=CUSTOM_INTEGRATION, force=True)
            print(f"Uninstalled custom integration {CUSTOM_INTEGRATION}")
        if installed_pkg:
            fleet_epm.uninstall_package(pkg_name=PKG, force=True)
            print(f"Uninstalled {PKG}")
        client.close()


if __name__ == "__main__":
    main()
