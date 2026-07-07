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
Package Registry (https://epr.elastic.co); if that access is unavailable,
Kibana rejects the registry calls and the example reports the rejection
instead of crashing. "tcp" is a real shared registry package (not
namespaced to this example), so it is only installed -- and later
uninstalled -- when it wasn't already present before this example ran.

Run this example:
    python examples/fleet_epm_management.py
"""

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import ApiError, NotFoundError

PKG = "tcp"


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    fleet_epm = client.fleet_epm
    prefix = resource_prefix(__file__)  # "kbnpy-fleet-epm"
    custom_integration = f"{prefix.replace('-', '_')}_app"
    installed_pkg = False
    created_custom = False
    created: list[tuple[str, str]] = []
    try:
        # Idempotent start: clear only THIS example's own custom integration
        # from a prior run. get_package() 404s if it was never installed;
        # uninstall_package() itself returns 400 (not 404) for "not
        # installed", so we check status first rather than blindly
        # uninstalling. The shared "tcp" package's pre-existing state is
        # checked separately below rather than blindly reinstalled.
        try:
            existing_integration = fleet_epm.get_package(pkg_name=custom_integration)
            if existing_integration.body["item"]["status"] == "installed":
                fleet_epm.uninstall_package(pkg_name=custom_integration, force=True)
        except NotFoundError:
            pass

        # 1. Browse categories and the custom-category packages. This is the
        # first call that actually needs Kibana -> EPR internet access;
        # report and stop gracefully rather than crash if it's unreachable.
        try:
            categories = fleet_epm.get_categories()
        except ApiError as exc:
            print(f"EPR unreachable (needs Kibana -> EPR internet access): {exc}")
            return
        print(f"Registry has {len(categories.body['items'])} categories")

        custom_packages = fleet_epm.get_packages(category="custom")
        names = [pkg["name"] for pkg in custom_packages.body["items"]]
        print(f"'custom' category packages: {', '.join(names[:5])}, ...")

        # 2. Install the Custom TCP Logs package from the registry -- but
        # only if it isn't already installed. "tcp" is a real shared
        # registry package, so a pre-existing install belongs to the user,
        # not to this example, and must not be torn down on cleanup.
        try:
            existing = fleet_epm.get_package(pkg_name=PKG)
            already_installed = existing.body["item"]["status"] == "installed"
        except NotFoundError:
            already_installed = False

        if already_installed:
            print(f"{PKG} already installed; leaving it alone")
        else:
            result = fleet_epm.install_package(pkg_name=PKG)
            installed_pkg = True
            created.append(("fleet package", PKG))
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

        # 4. Create and update a custom integration, namespaced to this example
        created_integration = fleet_epm.create_custom_integration(
            integration_name=custom_integration,
            datasets=[{"name": f"{custom_integration}.access", "type": "logs"}],
        )
        created_custom = True
        created.append(("fleet custom integration", custom_integration))
        print(
            f"Created custom integration ({len(created_integration.body['items'])} assets)"
        )

        updated = fleet_epm.update_custom_integration(
            pkg_name=custom_integration,
            read_me_data=f"# {custom_integration}\n\nCreated by the kibana-py example.",
            categories=["custom"],
        )
        print(f"Updated custom integration to {updated.body['result']['version']}")
    finally:
        # 5. Clean up: custom integration first (it may reference/depend on
        # the base package), then the base package -- but only if this run
        # was the one that installed it.
        if should_cleanup():
            if created_custom:
                try:
                    fleet_epm.uninstall_package(pkg_name=custom_integration, force=True)
                    print(f"Uninstalled custom integration {custom_integration}")
                except NotFoundError:
                    pass
            if installed_pkg:
                fleet_epm.uninstall_package(pkg_name=PKG, force=True)
                print(f"Uninstalled {PKG}")
        else:
            print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
