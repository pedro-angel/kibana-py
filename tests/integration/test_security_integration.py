"""Integration tests for SecurityClient / AsyncSecurityClient against live Kibana.

All resources created by these tests are prefixed with ``kbnpy-security-``
and cleaned up via fixtures, so they are safe to run against a shared stack.
"""

import uuid

import pytest

from kibana.exceptions import ConflictError, NotFoundError

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

PREFIX = "kbnpy-security"


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
def created_roles(kibana_client):
    """Track roles created during tests for automatic cleanup."""
    role_names: list[str] = []
    yield role_names

    for role_name in role_names:
        try:
            kibana_client.security.delete_role(name=role_name)
        except NotFoundError:
            pass  # Already deleted by the test itself
        except Exception as e:  # pragma: no cover - cleanup best effort
            print(f"Warning: failed to clean up role {role_name}: {e}")


@pytest.fixture
def unique_role_name():
    """Generate a unique, namespaced role name."""
    return f"{PREFIX}-{uuid.uuid4().hex[:8]}"


class TestSecurityRoleCRUD:
    """Live create/get/update/delete round-trips for roles."""

    def test_create_get_update_delete_role(
        self, kibana_client, created_roles, unique_role_name
    ):
        """Full role lifecycle against the live server."""
        # Create (PUT returns 204 with empty body)
        response = kibana_client.security.create_or_update_role(
            name=unique_role_name,
            description="kibana-py integration test role",
            elasticsearch={
                "cluster": ["monitor"],
                "indices": [
                    {"names": [f"{PREFIX}-*"], "privileges": ["read"]},
                ],
            },
            kibana=[{"base": ["read"], "spaces": ["default"]}],
            metadata={"kbnpy": True},
        )
        created_roles.append(unique_role_name)
        assert response.meta.status == 204

        # Get
        role = kibana_client.security.get_role(name=unique_role_name)
        assert role.body["name"] == unique_role_name
        assert role.body["description"] == "kibana-py integration test role"
        assert role.body["elasticsearch"]["cluster"] == ["monitor"]
        assert role.body["elasticsearch"]["indices"][0]["names"] == [f"{PREFIX}-*"]
        assert role.body["metadata"] == {"kbnpy": True}
        assert role.body["kibana"][0]["base"] == ["read"]
        assert role.body["kibana"][0]["spaces"] == ["default"]

        # Update (same PUT endpoint) and verify the change landed
        kibana_client.security.create_or_update_role(
            name=unique_role_name,
            description="updated by kibana-py",
            elasticsearch={"cluster": []},
        )
        updated = kibana_client.security.get_role(name=unique_role_name)
        assert updated.body["description"] == "updated by kibana-py"
        assert updated.body["elasticsearch"]["cluster"] == []

        # Delete
        delete_response = kibana_client.security.delete_role(name=unique_role_name)
        assert delete_response.meta.status == 204
        with pytest.raises(NotFoundError):
            kibana_client.security.get_role(name=unique_role_name)

    def test_create_only_conflicts_on_existing_role(
        self, kibana_client, created_roles, unique_role_name
    ):
        """createOnly=true must fail with 409 when the role already exists."""
        kibana_client.security.create_or_update_role(
            name=unique_role_name,
            elasticsearch={"cluster": ["monitor"]},
            create_only=True,
        )
        created_roles.append(unique_role_name)

        with pytest.raises(ConflictError):
            kibana_client.security.create_or_update_role(
                name=unique_role_name,
                elasticsearch={},
                create_only=True,
            )

    def test_get_role_not_found(self, kibana_client):
        """Getting a nonexistent role raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.security.get_role(name=f"{PREFIX}-does-not-exist")

    def test_delete_role_not_found(self, kibana_client):
        """Deleting a nonexistent role raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.security.delete_role(name=f"{PREFIX}-does-not-exist")


class TestSecurityGetAllAndQueryRoles:
    """Live listing and querying of roles."""

    def test_get_all_roles_includes_created_role(
        self, kibana_client, created_roles, unique_role_name
    ):
        """get_all_roles returns a list containing our role."""
        kibana_client.security.create_or_update_role(
            name=unique_role_name, elasticsearch={"cluster": []}
        )
        created_roles.append(unique_role_name)

        roles = kibana_client.security.get_all_roles()
        assert isinstance(roles.body, list)
        names = [role["name"] for role in roles.body]
        assert unique_role_name in names
        # Reserved roles are present in the unfiltered listing
        assert "superuser" in names

    def test_get_all_roles_replace_deprecated_privileges(self, kibana_client):
        """The replaceDeprecatedPrivileges query param is accepted live."""
        roles = kibana_client.security.get_all_roles(replace_deprecated_privileges=True)
        assert isinstance(roles.body, list)
        assert len(roles.body) > 0

    def test_query_roles_paging_sorting_and_filters(self, kibana_client, created_roles):
        """query_roles supports query/from/size/sort/filters live."""
        suffix = uuid.uuid4().hex[:8]
        names = [f"{PREFIX}-query-{suffix}-{i}" for i in range(3)]
        for name in names:
            kibana_client.security.create_or_update_role(
                name=name, elasticsearch={"cluster": []}
            )
            created_roles.append(name)

        result = kibana_client.security.query_roles(
            query=f"{PREFIX}-query-{suffix}",
            from_=0,
            size=2,
            sort={"field": "name", "direction": "asc"},
            filters={"showReservedRoles": False},
        )
        assert result.body["total"] == 3
        assert result.body["count"] == 2
        page_names = [role["name"] for role in result.body["roles"]]
        assert page_names == names[:2]  # ascending sort, first page

        # Second page
        page2 = kibana_client.security.query_roles(
            query=f"{PREFIX}-query-{suffix}",
            from_=2,
            size=2,
            sort={"field": "name", "direction": "asc"},
        )
        assert [role["name"] for role in page2.body["roles"]] == names[2:]


class TestSecurityBulkRoles:
    """Live bulk create/update of roles."""

    def test_bulk_create_then_update_roles(self, kibana_client, created_roles):
        """bulk_create_or_update_roles reports created then updated names."""
        suffix = uuid.uuid4().hex[:8]
        name_a = f"{PREFIX}-bulk-{suffix}-a"
        name_b = f"{PREFIX}-bulk-{suffix}-b"

        result = kibana_client.security.bulk_create_or_update_roles(
            roles={
                name_a: {"elasticsearch": {"cluster": ["monitor"]}},
                name_b: {
                    "elasticsearch": {},
                    "kibana": [{"base": ["read"], "spaces": ["*"]}],
                },
            }
        )
        created_roles.extend([name_a, name_b])
        assert sorted(result.body["created"]) == [name_a, name_b]

        # Same call again is an update
        result2 = kibana_client.security.bulk_create_or_update_roles(
            roles={name_a: {"elasticsearch": {"cluster": []}}}
        )
        assert result2.body.get("updated") == [name_a]

        # Verify the roles actually exist
        role_b = kibana_client.security.get_role(name=name_b)
        assert role_b.body["kibana"][0]["spaces"] == ["*"]

    def test_bulk_roles_reports_per_role_errors(self, kibana_client, created_roles):
        """Invalid definitions are reported in the errors section."""
        suffix = uuid.uuid4().hex[:8]
        good = f"{PREFIX}-bulkerr-{suffix}-good"
        bad = f"{PREFIX}-bulkerr-{suffix}-bad"

        result = kibana_client.security.bulk_create_or_update_roles(
            roles={
                good: {"elasticsearch": {"cluster": []}},
                # Invalid: unknown Elasticsearch cluster privilege
                bad: {
                    "elasticsearch": {"cluster": ["kbnpy_not_a_privilege"]},
                },
            }
        )
        created_roles.append(good)
        assert good in result.body.get("created", [])
        errors = result.body.get("errors", {})
        assert bad in errors
        assert errors[bad]["type"] == "action_request_validation_exception"


class TestSecurityInvalidateSessions:
    """Live session invalidation.

    Uses ``match="query"`` with a filter that targets a user that does not
    exist, so no real sessions on the shared stack are ever invalidated.
    ``match="all"`` is intentionally NOT exercised against the live server.
    """

    def test_invalidate_sessions_query_no_match(self, kibana_client):
        """A narrow query invalidates zero sessions and returns a total."""
        result = kibana_client.security.invalidate_sessions(
            match="query",
            query={
                "provider": {"type": "basic"},
                "username": f"{PREFIX}-no-such-user-{uuid.uuid4().hex[:8]}",
            },
        )
        assert result.body == {"total": 0}


class TestAsyncSecurityIntegration:
    """Async client round-trips against the live server."""

    async def test_async_role_lifecycle(self, unique_role_name):
        """Async create/get/query/delete round-trip."""
        client = create_test_async_kibana_client(auth_method="auto")
        try:
            response = await client.security.create_or_update_role(
                name=unique_role_name,
                description="kibana-py async integration test role",
                elasticsearch={"cluster": ["monitor"]},
                kibana=[{"base": ["read"], "spaces": ["default"]}],
            )
            assert response.meta.status == 204

            try:
                role = await client.security.get_role(name=unique_role_name)
                assert role.body["name"] == unique_role_name
                assert role.body["elasticsearch"]["cluster"] == ["monitor"]

                all_roles = await client.security.get_all_roles()
                assert unique_role_name in [r["name"] for r in all_roles.body]

                queried = await client.security.query_roles(
                    query=unique_role_name, size=5
                )
                assert queried.body["total"] == 1

                invalidated = await client.security.invalidate_sessions(
                    match="query",
                    query={
                        "provider": {"type": "basic"},
                        "username": f"{PREFIX}-no-such-user",
                    },
                )
                assert invalidated.body == {"total": 0}
            finally:
                await client.security.delete_role(name=unique_role_name)

            with pytest.raises(NotFoundError):
                await client.security.get_role(name=unique_role_name)
        finally:
            await client.close()
