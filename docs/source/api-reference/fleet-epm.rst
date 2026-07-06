FleetEpmClient
==============

Client for the Kibana Fleet Elastic Package Manager (EPM) API.

The Elastic Package Manager APIs browse, install, upgrade, roll back and
uninstall integration packages from the Elastic Package Registry, manage
their Kibana and Elasticsearch assets, create custom integrations, and
inspect the data streams shipped by installed packages.

All Fleet EPM operations are space-aware: every method accepts an optional
``space_id`` to target a specific space.

.. currentmodule:: kibana._sync.client.fleet_epm

.. autoclass:: FleetEpmClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Browsing the Package Registry

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Categories and packages
      categories = client.fleet_epm.get_categories()
      packages = client.fleet_epm.get_packages(category="custom")

      # A single package (latest, or a pinned version)
      pkg = client.fleet_epm.get_package(pkg_name="nginx")
      pinned = client.fleet_epm.get_package(pkg_name="nginx", pkg_version="2.3.1")

      # What is installed on this Kibana
      installed = client.fleet_epm.get_installed_packages(per_page=20)

      # Package content and metadata
      manifest = client.fleet_epm.get_package_file(
          pkg_name="nginx", pkg_version="2.3.1", file_path="manifest.yml"
      )
      stats = client.fleet_epm.get_package_stats(pkg_name="nginx")
      deps = client.fleet_epm.get_package_dependencies(
          pkg_name="nginx", pkg_version="2.3.1"
      )

   .. rubric:: Installing, Upgrading and Uninstalling Packages

   .. code-block:: python

      # Install the latest version from the registry
      client.fleet_epm.install_package(pkg_name="nginx")

      # Install a pinned (older) version — requires force
      client.fleet_epm.install_package(
          pkg_name="nginx", pkg_version="2.3.0", force=True
      )

      # Install from an uploaded archive
      with open("my-package-1.0.0.zip", "rb") as f:
          client.fleet_epm.install_package_by_upload(content=f.read())

      # Update package settings
      client.fleet_epm.update_package(
          pkg_name="nginx", keep_policies_up_to_date=True
      )

      # Roll back to the previously installed version
      client.fleet_epm.rollback_package(pkg_name="nginx")

      # Uninstall
      client.fleet_epm.uninstall_package(pkg_name="nginx")

   .. rubric:: Bulk Operations

   Bulk upgrade, uninstall and rollback are asynchronous: they return a
   ``taskId`` that can be polled with the matching status method.

   .. code-block:: python

      # Bulk install is synchronous
      result = client.fleet_epm.bulk_install_packages(
          packages=["tcp", {"name": "udp", "version": "2.5.1"}]
      )

      # Bulk upgrade + poll the task
      started = client.fleet_epm.bulk_upgrade_packages(packages=["tcp", "udp"])
      status = client.fleet_epm.get_bulk_upgrade_status(
          task_id=started.body["taskId"]
      )

      # Bulk uninstall (name and version are required per package)
      started = client.fleet_epm.bulk_uninstall_packages(
          packages=[{"name": "tcp", "version": "2.3.1"}]
      )
      status = client.fleet_epm.get_bulk_uninstall_status(
          task_id=started.body["taskId"]
      )

   .. rubric:: Custom Integrations

   .. code-block:: python

      # Create a custom integration with generated assets
      client.fleet_epm.create_custom_integration(
          integration_name="my_app",
          datasets=[{"name": "my_app.access", "type": "logs"}],
      )

      # Update its README and categories (bumps the patch version)
      client.fleet_epm.update_custom_integration(
          pkg_name="my_app",
          read_me_data="# My app",
          categories=["custom"],
      )

      # Custom integrations are deleted via the package delete endpoint
      client.fleet_epm.uninstall_package(pkg_name="my_app", force=True)

   .. rubric:: Data Streams and Inputs Templates

   .. code-block:: python

      # Fleet data streams (with sizes and dashboards)
      streams = client.fleet_epm.get_data_streams()

      # EPM data stream names, filtered
      items = client.fleet_epm.find_data_streams(type="logs", dataset_query="nginx")

      # Standalone-agent inputs template for a package
      template = client.fleet_epm.get_inputs_template(
          pkg_name="nginx", pkg_version="2.3.1", format="json"
      )

AsyncFleetEpmClient
-------------------

Asynchronous version of the FleetEpmClient for use with async/await syntax.

.. autoclass:: kibana._async.client.fleet_epm.AsyncFleetEpmClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncFleetEpmClient provides the same methods as FleetEpmClient but
   all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Install a package (async)
              await client.fleet_epm.install_package(pkg_name="tcp")

              # Inspect it
              pkg = await client.fleet_epm.get_package(pkg_name="tcp")
              print(pkg.body["item"]["status"])

              # Uninstall it again
              await client.fleet_epm.uninstall_package(pkg_name="tcp")

      asyncio.run(main())
