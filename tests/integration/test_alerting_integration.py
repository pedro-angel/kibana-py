"""Integration tests for AlertingClient (Rules)."""

import pytest

from kibana.exceptions import NotFoundError

from .utils import create_test_kibana_client, is_kibana_available

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
def created_rules(kibana_client):
    """Track rules created during tests for automatic cleanup."""
    rule_ids: list[str] = []
    yield rule_ids

    # Cleanup: Delete all created rules
    if rule_ids:
        for rule_id in rule_ids:
            try:
                kibana_client.alerting.rule.delete(id=rule_id)
            except Exception:
                pass


@pytest.fixture
def rule_config():
    """Shared rule configuration."""
    return {
        "rule_type_id": ".index-threshold",
        "schedule": {"interval": "1m"},
        "params": {
            "index": ["*"],
            "timeField": "@timestamp",
            "aggType": "count",
            "thresholdComparator": ">",
            "timeWindowSize": 5,
            "timeWindowUnit": "m",
            "threshold": [0],
        },
    }


class TestAlertingClientCRUD:
    """Tests for CRUD operations on rules."""

    def test_create_rule(self, kibana_client, created_rules, rule_config):
        """Test creating a rule."""
        rule_name = "Test Rule"

        # We try to create a rule. If the rule type is disabled (license), we skip.
        try:
            response = kibana_client.alerting.rule.create(
                name=rule_name,
                consumer="alerts",
                rule_type_id=rule_config["rule_type_id"],
                schedule=rule_config["schedule"],
                params=rule_config["params"],
            )
        except Exception as e:
            if (
                "license" in str(e).lower()
                or "disabled" in str(e).lower()
                or "forbidden" in str(e).lower()
            ):
                pytest.skip(f"Skipping rule creation due to license/permission: {e}")
            raise

        rule = response.body
        created_rules.append(rule["id"])

        assert rule["name"] == rule_name
        assert rule["enabled"] is True

    def test_get_rule(self, kibana_client, created_rules, rule_config):
        """Test getting a rule."""
        # Create
        try:
            response = kibana_client.alerting.rule.create(
                name="Get Rule Test",
                consumer="alerts",
                rule_type_id=rule_config["rule_type_id"],
                schedule=rule_config["schedule"],
                params=rule_config["params"],
            )
        except Exception as e:
            if (
                "license" in str(e).lower()
                or "disabled" in str(e).lower()
                or "forbidden" in str(e).lower()
            ):
                pytest.skip(f"Skipping rule creation due to license/permission: {e}")
            raise

        rule_id = response.body["id"]
        created_rules.append(rule_id)

        # Get
        params = kibana_client.alerting.rule.get(id=rule_id)
        assert params.body["id"] == rule_id
        assert params.body["name"] == "Get Rule Test"

    def test_update_rule(self, kibana_client, created_rules, rule_config):
        """Test updating a rule."""
        # Create
        try:
            response = kibana_client.alerting.rule.create(
                name="Update Rule Test",
                consumer="alerts",
                rule_type_id=rule_config["rule_type_id"],
                schedule=rule_config["schedule"],
                params=rule_config["params"],
            )
        except Exception as e:
            if (
                "license" in str(e).lower()
                or "disabled" in str(e).lower()
                or "forbidden" in str(e).lower()
            ):
                pytest.skip(f"Skipping rule creation due to license/permission: {e}")
            raise

        rule_id = response.body["id"]
        created_rules.append(rule_id)

        # Update (rule_type_id is immutable and not sent in the PUT body)
        updated = kibana_client.alerting.rule.update(
            id=rule_id,
            name="Updated Rule Name",
            schedule=rule_config["schedule"],
            params=rule_config["params"],
        )

        assert updated.body["name"] == "Updated Rule Name"

        # Verify via get
        got = kibana_client.alerting.rule.get(id=rule_id)
        assert got.body["name"] == "Updated Rule Name"

    def test_delete_rule(self, kibana_client, rule_config):
        """Test deleting a rule."""
        # Create
        try:
            response = kibana_client.alerting.rule.create(
                name="Delete Rule Test",
                consumer="alerts",
                rule_type_id=rule_config["rule_type_id"],
                schedule=rule_config["schedule"],
                params=rule_config["params"],
            )
        except Exception as e:
            if (
                "license" in str(e).lower()
                or "disabled" in str(e).lower()
                or "forbidden" in str(e).lower()
            ):
                pytest.skip(f"Skipping rule creation due to license/permission: {e}")
            raise

        rule_id = response.body["id"]

        # Delete
        kibana_client.alerting.rule.delete(id=rule_id)

        # Verify
        with pytest.raises(NotFoundError):
            kibana_client.alerting.rule.get(id=rule_id)

    def test_find_rules(self, kibana_client, created_rules, rule_config):
        """Test finding rules."""
        # Create typical rule
        try:
            response = kibana_client.alerting.rule.create(
                name="Find Rule Test",
                consumer="alerts",
                rule_type_id=rule_config["rule_type_id"],
                schedule=rule_config["schedule"],
                params=rule_config["params"],
            )
        except Exception as e:
            if (
                "license" in str(e).lower()
                or "disabled" in str(e).lower()
                or "forbidden" in str(e).lower()
            ):
                pytest.skip(f"Skipping rule creation due to license/permission: {e}")
            raise

        rule_id = response.body["id"]
        created_rules.append(rule_id)

        # Find
        found = kibana_client.alerting.rule.find(
            search="Find Rule Test", sort_field="name"
        )
        assert found.body["total"] >= 1

        ids = [r["id"] for r in found.body["data"]]
        assert rule_id in ids
