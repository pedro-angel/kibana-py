"""Unit tests for AsyncSecurityClient."""

from unittest.mock import AsyncMock, Mock

import pytest
from elastic_transport import ListApiResponse

from kibana._async.client import AsyncKibana
from kibana._async.client.security import AsyncSecurityClient
from kibana.exceptions import ConflictError, NotFoundError


def _role_body(name: str = "my-role") -> dict:
    """A Kibana 9.4.3 role object as returned by the live server."""
    return {
        "name": name,
        "description": "A test role",
        "metadata": {"kbnpy": True},
        "transient_metadata": {"enabled": True},
        "elasticsearch": {
            "cluster": ["monitor"],
            "indices": [
                {
                    "names": ["logs-*"],
                    "privileges": ["read"],
                    "allow_restricted_indices": False,
                }
            ],
            "run_as": [],
        },
        "kibana": [{"base": ["read"], "feature": {}, "spaces": ["default"]}],
    }


class TestAsyncSecurityClientInitialization:
    """Test AsyncSecurityClient initialization and wiring."""

    async def test_security_client_initialization(self, mock_async_transport):
        """Test that AsyncSecurityClient can be initialized with a parent client."""
        client = AsyncKibana(_transport=mock_async_transport)
        security_client = AsyncSecurityClient(client)
        assert security_client._client is client

    async def test_security_property_returns_security_client(
        self, mock_async_transport
    ):
        """Test that client.security returns an AsyncSecurityClient instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.security, AsyncSecurityClient)

    async def test_security_property_caching(self, mock_async_transport):
        """Test that the security attribute returns the same instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert client.security is client.security


class TestAsyncSecurityClientGetAllRoles:
    """Test AsyncSecurityClient.get_all_roles()."""

    async def test_get_all_roles(self, mock_async_transport):
        """Test retrieving all roles without parameters."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=ListApiResponse(
                body=[_role_body("role-a"), _role_body("role-b")],
                meta=Mock(status=200, headers={}),
            )
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.security.get_all_roles()

        assert [r["name"] for r in result.body] == ["role-a", "role-b"]
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/security/role"
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert "body" not in call_kwargs

    async def test_get_all_roles_with_replace_deprecated_privileges(
        self, mock_async_transport, mock_response
    ):
        """Test that the boolean query parameter is encoded as true/false."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={})
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.security.get_all_roles(replace_deprecated_privileges=True)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == "/api/security/role?replaceDeprecatedPrivileges=true"
        )

    async def test_get_all_roles_replace_deprecated_privileges_false(
        self, mock_async_transport, mock_response
    ):
        """Test that False is encoded (not dropped) in the query string."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={})
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.security.get_all_roles(replace_deprecated_privileges=False)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == "/api/security/role?replaceDeprecatedPrivileges=false"
        )


class TestAsyncSecurityClientGetRole:
    """Test AsyncSecurityClient.get_role()."""

    async def test_get_role(self, mock_async_transport, mock_response):
        """Test retrieving a single role by name."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body=_role_body("my-role"))
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.security.get_role(name="my-role")

        assert result.body["name"] == "my-role"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/security/role/my-role"

    async def test_get_role_url_encodes_name(self, mock_async_transport, mock_response):
        """Test that role names are URL-encoded in the path."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={})
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.security.get_role(name="my role/admin")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/security/role/my%20role%2Fadmin"

    async def test_get_role_with_replace_deprecated_privileges(
        self, mock_async_transport, mock_response
    ):
        """Test the replaceDeprecatedPrivileges query parameter."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={})
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.security.get_role(
            name="my-role", replace_deprecated_privileges=True
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == "/api/security/role/my-role?replaceDeprecatedPrivileges=true"
        )

    async def test_get_role_empty_name_raises_value_error(self, mock_async_transport):
        """Test that an empty name raises ValueError before any request."""
        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(ValueError, match="name"):
            await client.security.get_role(name="")
        mock_async_transport.perform_request.assert_not_called()

    async def test_get_role_not_found(self, mock_async_transport, mock_response):
        """Test 404 mapping to NotFoundError."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "statusCode": 404,
                    "error": "Not Found",
                    "message": "Role not found",
                },
                status=404,
            )
        )
        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(NotFoundError):
            await client.security.get_role(name="missing-role")


class TestAsyncSecurityClientCreateOrUpdateRole:
    """Test AsyncSecurityClient.create_or_update_role()."""

    async def test_create_or_update_role_minimal(
        self, mock_async_transport, mock_response
    ):
        """Test the minimal body contains only elasticsearch privileges."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={})
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.security.create_or_update_role(
            name="my-role",
            elasticsearch={"cluster": ["monitor"]},
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/security/role/my-role"
        assert call_kwargs["body"] == {"elasticsearch": {"cluster": ["monitor"]}}
        # CSRF and content-type headers are injected by the base client
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs["headers"]["content-type"] == "application/json"

    async def test_create_or_update_role_full_body(
        self, mock_async_transport, mock_response
    ):
        """Test that all optional body fields are passed through."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={})
        )
        client = AsyncKibana(_transport=mock_async_transport)

        kibana_privileges = [{"base": ["read"], "spaces": ["default"]}]
        await client.security.create_or_update_role(
            name="my-role",
            elasticsearch={"cluster": [], "run_as": []},
            description="A test role",
            kibana=kibana_privileges,
            metadata={"version": 1},
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "elasticsearch": {"cluster": [], "run_as": []},
            "description": "A test role",
            "kibana": kibana_privileges,
            "metadata": {"version": 1},
        }

    async def test_create_or_update_role_create_only(
        self, mock_async_transport, mock_response
    ):
        """Test that create_only maps to the createOnly query parameter."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={})
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.security.create_or_update_role(
            name="my-role", elasticsearch={}, create_only=True
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/security/role/my-role?createOnly=true"

    async def test_create_or_update_role_conflict(
        self, mock_async_transport, mock_response
    ):
        """Test 409 mapping to ConflictError (create_only on existing role)."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "statusCode": 409,
                    "error": "Conflict",
                    "message": "Role already exists and cannot be created: my-role",
                },
                status=409,
            )
        )
        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(ConflictError):
            await client.security.create_or_update_role(
                name="my-role", elasticsearch={}, create_only=True
            )

    async def test_create_or_update_role_empty_name_raises_value_error(
        self, mock_async_transport
    ):
        """Test that an empty name raises ValueError before any request."""
        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(ValueError, match="name"):
            await client.security.create_or_update_role(name="", elasticsearch={})
        mock_async_transport.perform_request.assert_not_called()


class TestAsyncSecurityClientDeleteRole:
    """Test AsyncSecurityClient.delete_role()."""

    async def test_delete_role(self, mock_async_transport, mock_response):
        """Test deleting a role by name."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={})
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.security.delete_role(name="my-role")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/security/role/my-role"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert "body" not in call_kwargs

    async def test_delete_role_url_encodes_name(
        self, mock_async_transport, mock_response
    ):
        """Test that role names are URL-encoded in the delete path."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={})
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.security.delete_role(name="a role")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/security/role/a%20role"

    async def test_delete_role_empty_name_raises_value_error(
        self, mock_async_transport
    ):
        """Test that an empty name raises ValueError before any request."""
        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(ValueError, match="name"):
            await client.security.delete_role(name="")
        mock_async_transport.perform_request.assert_not_called()


class TestAsyncSecurityClientBulkCreateOrUpdateRoles:
    """Test AsyncSecurityClient.bulk_create_or_update_roles()."""

    async def test_bulk_create_or_update_roles(
        self, mock_async_transport, mock_response
    ):
        """Test the bulk roles body wrapping."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"created": ["role-a", "role-b"]})
        )
        client = AsyncKibana(_transport=mock_async_transport)

        roles = {
            "role-a": {"elasticsearch": {"cluster": ["monitor"]}},
            "role-b": {
                "elasticsearch": {},
                "kibana": [{"base": ["read"], "spaces": ["*"]}],
            },
        }
        result = await client.security.bulk_create_or_update_roles(roles=roles)

        assert result.body["created"] == ["role-a", "role-b"]
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/security/roles"
        assert call_kwargs["body"] == {"roles": roles}


class TestAsyncSecurityClientQueryRoles:
    """Test AsyncSecurityClient.query_roles()."""

    async def test_query_roles_empty(self, mock_async_transport, mock_response):
        """Test that a query without arguments sends an empty object body."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"roles": [], "count": 0, "total": 0})
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.security.query_roles()

        assert result.body["total"] == 0
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/security/role/_query"
        assert call_kwargs["body"] == {}

    async def test_query_roles_all_parameters(
        self, mock_async_transport, mock_response
    ):
        """Test that from_ maps to 'from' and all fields are passed through."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={"roles": [_role_body()], "count": 1, "total": 1}
            )
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.security.query_roles(
            query="kbnpy",
            from_=10,
            size=25,
            sort={"field": "name", "direction": "desc"},
            filters={"showReservedRoles": False},
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "query": "kbnpy",
            "from": 10,
            "size": 25,
            "sort": {"field": "name", "direction": "desc"},
            "filters": {"showReservedRoles": False},
        }


class TestAsyncSecurityClientInvalidateSessions:
    """Test AsyncSecurityClient.invalidate_sessions()."""

    async def test_invalidate_sessions_match_all(
        self, mock_async_transport, mock_response
    ):
        """Test invalidating all sessions."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"total": 3})
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.security.invalidate_sessions(match="all")

        assert result.body["total"] == 3
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/security/session/_invalidate"
        assert call_kwargs["body"] == {"match": "all"}
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    async def test_invalidate_sessions_match_query(
        self, mock_async_transport, mock_response
    ):
        """Test invalidating sessions matching a provider/username query."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"total": 0})
        )
        client = AsyncKibana(_transport=mock_async_transport)

        query = {"provider": {"type": "basic"}, "username": "some-user"}
        result = await client.security.invalidate_sessions(match="query", query=query)

        assert result.body["total"] == 0
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {"match": "query", "query": query}
