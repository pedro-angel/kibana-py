#!/usr/bin/env python3
"""
Space Management Example

This comprehensive example demonstrates all CRUD operations for Kibana Spaces:
1. Creating spaces with various configurations
2. Retrieving space information
3. Updating space properties
4. Listing all spaces
5. Deleting spaces

This example follows production-ready patterns:
- Proper error handling
- Resource cleanup
- Logging and status messages
- Interactive user prompts

Run this example:
    python examples/space_management.py
"""

import logging

from utils import (
    configure_example_telemetry,
    create_kibana_client,
    print_config_info,
    print_telemetry_info,
    setup_telemetry_cleanup,
    should_cleanup,
    should_enable_telemetry,
)

from kibana import Kibana
from kibana.exceptions import ConflictError, NotFoundError

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SpaceManager:
    """Manages Kibana Spaces with comprehensive CRUD operations."""

    def __init__(self, client: Kibana):
        """
        Initialize the SpaceManager.

        :param client: Kibana client instance
        """
        self.client = client
        self.created_spaces = []

    def create_space(
        self,
        space_id: str,
        name: str,
        description: str | None = None,
        color: str | None = None,
        initials: str | None = None,
        disabled_features: list | None = None,
    ) -> dict:
        """
        Create a new Kibana space.

        :param space_id: Unique identifier for the space
        :param name: Display name for the space
        :param description: Optional description
        :param color: Optional hex color code
        :param initials: Optional initials (max 2 characters)
        :param disabled_features: Optional list of features to disable
        :return: Created space data
        """
        try:
            logger.info(
                f"Creating space: {space_id}",
                extra={
                    "space_id": space_id,
                    "space_name": name,
                    "operation": "create_space",
                    "disabled_features": disabled_features or [],
                },
            )

            response = self.client.spaces.create(
                id=space_id,
                name=name,
                description=description,
                color=color,
                initials=initials,
                disabled_features=disabled_features,
            )

            space = response.body
            self.created_spaces.append(space_id)
            logger.info(
                f"✓ Created space: {space['name']} (ID: {space_id})",
                extra={
                    "space_id": space_id,
                    "space_name": space["name"],
                    "operation": "create_space",
                    "status": "success",
                    "color": color,
                    "initials": initials,
                },
            )
            return space

        except ConflictError:
            logger.error(
                f"❌ Space '{space_id}' already exists",
                extra={
                    "space_id": space_id,
                    "space_name": name,
                    "operation": "create_space",
                    "status": "error",
                    "error_type": "ConflictError",
                },
            )
            raise
        except Exception as e:
            logger.error(
                f"❌ Failed to create space: {e}",
                extra={
                    "space_id": space_id,
                    "space_name": name,
                    "operation": "create_space",
                    "status": "error",
                    "error_type": type(e).__name__,
                },
            )
            raise

    def get_space(self, space_id: str) -> dict:
        """
        Retrieve a space by ID.

        :param space_id: Space ID to retrieve
        :return: Space data
        """
        try:
            logger.info(f"Retrieving space: {space_id}")
            response = self.client.spaces.get(id=space_id)
            space = response.body
            logger.info(f"✓ Retrieved space: {space['name']}")
            return space

        except NotFoundError:
            logger.error(f"❌ Space '{space_id}' not found")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to retrieve space: {e}")
            raise

    def list_spaces(self) -> list:
        """
        List all spaces.

        :return: List of all spaces
        """
        try:
            logger.info("Listing all spaces...")
            response = self.client.spaces.get_all()
            spaces = response.body
            logger.info(f"✓ Found {len(spaces)} space(s)")
            return spaces

        except Exception as e:
            logger.error(f"❌ Failed to list spaces: {e}")
            raise

    def update_space(
        self,
        space_id: str,
        name: str | None = None,
        description: str | None = None,
        color: str | None = None,
        initials: str | None = None,
        disabled_features: list | None = None,
    ) -> dict:
        """
        Update a space's properties.

        :param space_id: Space ID to update
        :param name: Optional new name
        :param description: Optional new description
        :param color: Optional new color
        :param initials: Optional new initials
        :param disabled_features: Optional new list of disabled features
        :return: Updated space data
        """
        try:
            logger.info(f"Updating space: {space_id}")

            response = self.client.spaces.update(
                id=space_id,
                name=name,
                description=description,
                color=color,
                initials=initials,
                disabled_features=disabled_features,
            )

            space = response.body
            logger.info(f"✓ Updated space: {space['name']}")
            return space

        except NotFoundError:
            logger.error(f"❌ Space '{space_id}' not found")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to update space: {e}")
            raise

    def delete_space(self, space_id: str) -> None:
        """
        Delete a space.

        :param space_id: Space ID to delete
        """
        try:
            logger.info(f"Deleting space: {space_id}")
            self.client.spaces.delete(id=space_id)

            # Verify deletion
            try:
                self.client.spaces.get(id=space_id)
                logger.error(f"❌ Space '{space_id}' still exists after deletion")
            except NotFoundError:
                logger.info(f"✓ Deleted space: {space_id}")
                if space_id in self.created_spaces:
                    self.created_spaces.remove(space_id)

        except NotFoundError:
            logger.warning(f"⚠ Space '{space_id}' not found (may already be deleted)")
        except Exception as e:
            logger.error(f"❌ Failed to delete space: {e}")
            # Try to verify deletion anyway
            try:
                self.client.spaces.get(id=space_id)
                raise
            except NotFoundError:
                logger.info("✓ Space deleted despite error (confirmed)")
                if space_id in self.created_spaces:
                    self.created_spaces.remove(space_id)

    def cleanup(self) -> None:
        """Clean up all created spaces."""
        if not self.created_spaces:
            logger.info("No spaces to clean up")
            return

        logger.info(f"Cleaning up {len(self.created_spaces)} space(s)...")
        for space_id in list(self.created_spaces):
            try:
                self.delete_space(space_id)
            except Exception as e:
                logger.warning(f"Failed to cleanup space {space_id}: {e}")


def main():
    """Run the space management example."""
    # Print configuration information
    print_config_info()

    # Configure telemetry with production-ready error handling
    try:
        telemetry_enabled = should_enable_telemetry()
        traces_configured, logs_configured = configure_example_telemetry(
            enabled=telemetry_enabled,
            logs_enabled=telemetry_enabled,  # Enable log forwarding when telemetry is enabled
        )
        print_telemetry_info()

        # Set up automatic telemetry cleanup
        setup_telemetry_cleanup()

        if traces_configured or logs_configured:
            logger.info(
                "Space management example started",
                extra={
                    "traces_enabled": traces_configured,
                    "logs_enabled": logs_configured,
                    "example": "space_management",
                },
            )
    except Exception as e:
        logger.warning(
            f"Telemetry configuration failed: {e}",
            extra={
                "error_type": "telemetry_config_error",
                "example": "space_management",
            },
        )
        print("⚠️  Continuing without telemetry...")

    # Initialize Kibana client
    client = create_kibana_client()
    manager = SpaceManager(client)

    try:
        print("\n" + "=" * 80)
        print("KIBANA SPACE MANAGEMENT EXAMPLE")
        print("=" * 80 + "\n")

        # 1. List existing spaces
        print("1️⃣  Listing existing spaces...")
        spaces = manager.list_spaces()
        print(f"   Found {len(spaces)} existing space(s):")
        for space in spaces:
            print(f"   - {space['name']} (ID: {space['id']})")

        # 2. Create a new space
        print("\n2️⃣  Creating a new space...")
        manager.create_space(
            space_id="marketing-team",
            name="Marketing Team",
            description="Space for marketing team's dashboards and reports",
            color="#FF6B6B",
            initials="MK",
            disabled_features=["dev_tools", "advancedSettings"],
        )
        print("   Space URL: http://localhost:5601/s/marketing-team/app/home")

        # 3. Retrieve the space
        print("\n3️⃣  Retrieving the created space...")
        retrieved_space = manager.get_space("marketing-team")
        print(f"   Name: {retrieved_space['name']}")
        print(f"   Description: {retrieved_space.get('description', 'N/A')}")
        print(f"   Color: {retrieved_space.get('color', 'N/A')}")
        print(
            f"   Disabled features: {', '.join(retrieved_space.get('disabledFeatures', [])) or 'None'}"
        )

        # 4. Update the space
        print("\n4️⃣  Updating the space...")
        updated_space = manager.update_space(
            space_id="marketing-team",
            name="Marketing & Sales Team",
            description="Updated: Combined marketing and sales team space",
            color="#4ECDC4",
        )
        print(f"   New name: {updated_space['name']}")
        print(f"   New description: {updated_space.get('description', 'N/A')}")
        print(f"   New color: {updated_space.get('color', 'N/A')}")

        # 5. Create another space
        print("\n5️⃣  Creating another space...")
        manager.create_space(
            space_id="engineering-team",
            name="Engineering Team",
            description="Space for engineering team",
            color="#95E1D3",
            initials="EN",
        )

        # 6. List all spaces again
        print("\n6️⃣  Listing all spaces (including new ones)...")
        all_spaces = manager.list_spaces()
        print(f"   Total spaces: {len(all_spaces)}")
        for space in all_spaces:
            marker = "🆕" if space["id"] in manager.created_spaces else "  "
            print(f"   {marker} {space['name']} (ID: {space['id']})")

        # 7. Demonstrate error handling
        print("\n7️⃣  Demonstrating error handling...")
        try:
            manager.get_space("nonexistent-space")
        except NotFoundError:
            print("   ✓ Correctly handled NotFoundError for nonexistent space")

        try:
            manager.create_space(
                space_id="marketing-team",
                name="Duplicate Space",
            )
        except ConflictError:
            print("   ✓ Correctly handled ConflictError for duplicate space")

        # Success message
        print("\n" + "=" * 80)
        print("🎉 EXAMPLE COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print(f"\nCreated {len(manager.created_spaces)} space(s) during this example:")
        for space_id in manager.created_spaces:
            print(f"  - {space_id}")
            print(f"    URL: http://localhost:5601/s/{space_id}/app/home")

        # Ask about cleanup
        print("\n" + "=" * 80)
        if should_cleanup("Delete the created spaces? (y/N): "):
            manager.cleanup()
            print("✓ Cleanup complete")
        else:
            print("✓ Spaces kept. You can delete them later from Kibana UI.")

    except Exception as e:
        logger.error(f"❌ Example failed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()
