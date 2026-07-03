"""Unit tests for AsyncSlosClient."""

from urllib.parse import parse_qs, urlsplit

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client.slos import AsyncSlosClient
from kibana.exceptions import NotFoundError

SLO_ID = "8853df00-ae2e-11ed-90af-09bb6422b258"


def _call_kwargs(mock_async_transport) -> dict:
    """Return the kwargs of the single transport.perform_request call."""
    mock_async_transport.perform_request.assert_called_once()
    return mock_async_transport.perform_request.call_args[1]


def _target_parts(mock_async_transport) -> tuple[str, dict]:
    """Return (path, query-params-dict) of the transport call target."""
    kwargs = _call_kwargs(mock_async_transport)
    parts = urlsplit(kwargs["target"])
    return parts.path, parse_qs(parts.query)


class TestAsyncSlosClientInitialization:
    """Test AsyncSlosClient initialization and wiring."""

    async def test_initialization(self, mock_async_transport):
        client = AsyncKibana(_transport=mock_async_transport)
        slos_client = AsyncSlosClient(client)
        assert slos_client._client is client

    async def test_slos_property_returns_slos_client(self, mock_async_transport):
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.slos, AsyncSlosClient)
        assert client.slos is client.slos


class TestAsyncSlosClientFind:
    """Test AsyncSlosClient.find()."""

    async def test_find_defaults(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"page": 1, "perPage": 25, "total": 0, "results": []}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.slos.find()

        assert result.body["results"] == []
        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/observability/slos"
        assert "body" not in kwargs

    async def test_find_with_all_params(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"results": []}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.slos.find(
            kql_query="slo.name:kbnpy*",
            size=10,
            search_after=["a", "b"],
            page=2,
            per_page=50,
            sort_by="status",
            sort_direction="desc",
            hide_stale=True,
        )

        path, query = _target_parts(mock_async_transport)
        assert path == "/api/observability/slos"
        assert query["kqlQuery"] == ["slo.name:kbnpy*"]
        assert query["size"] == ["10"]
        assert query["searchAfter"] == ["a", "b"]  # list -> repeated keys
        assert query["page"] == ["2"]
        assert query["perPage"] == ["50"]
        assert query["sortBy"] == ["status"]
        assert query["sortDirection"] == ["desc"]
        assert query["hideStale"] == ["true"]  # bool -> "true"

    async def test_find_with_space_id(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"results": []}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.slos.find(space_id="team-a", validate_spaces=False)

        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["target"] == "/s/team-a/api/observability/slos"


class TestAsyncSlosClientCreate:
    """Test AsyncSlosClient.create()."""

    async def test_create_minimal(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": SLO_ID}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        indicator = {
            "type": "sli.kql.custom",
            "params": {
                "index": "my-index",
                "good": "status: ok",
                "total": "",
                "timestampField": "@timestamp",
            },
        }
        result = await client.slos.create(
            name="my-slo",
            description="desc",
            indicator=indicator,
            time_window={"duration": "7d", "type": "rolling"},
            budgeting_method="occurrences",
            objective={"target": 0.99},
        )

        assert result.body["id"] == SLO_ID
        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/observability/slos"
        assert kwargs["body"] == {
            "name": "my-slo",
            "description": "desc",
            "indicator": indicator,
            "timeWindow": {"duration": "7d", "type": "rolling"},
            "budgetingMethod": "occurrences",
            "objective": {"target": 0.99},
        }

    async def test_create_with_optional_fields(
        self, mock_async_transport, mock_response
    ):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "custom-slo-id"}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.slos.create(
            name="my-slo",
            description="desc",
            indicator={"type": "sli.kql.custom", "params": {}},
            time_window={"duration": "30d", "type": "rolling"},
            budgeting_method="timeslices",
            objective={
                "target": 0.95,
                "timesliceTarget": 0.95,
                "timesliceWindow": "5m",
            },
            id="custom-slo-id",
            settings={"syncDelay": "5m", "frequency": "5m"},
            group_by=["service.name", "service.environment"],
            tags=["kbnpy", "test"],
            artifacts={"dashboards": [{"id": "dash-1"}]},
        )

        body = _call_kwargs(mock_async_transport)["body"]
        assert body["id"] == "custom-slo-id"
        assert body["settings"] == {"syncDelay": "5m", "frequency": "5m"}
        assert body["groupBy"] == ["service.name", "service.environment"]
        assert body["tags"] == ["kbnpy", "test"]
        assert body["artifacts"] == {"dashboards": [{"id": "dash-1"}]}


class TestAsyncSlosClientGet:
    """Test AsyncSlosClient.get()."""

    async def test_get(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": SLO_ID, "name": "my-slo", "enabled": True}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.slos.get(slo_id=SLO_ID)

        assert result.body["name"] == "my-slo"
        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == f"/api/observability/slos/{SLO_ID}"

    async def test_get_with_instance_id(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(body={})
        client = AsyncKibana(_transport=mock_async_transport)

        await client.slos.get(slo_id=SLO_ID, instance_id="my-service")

        path, query = _target_parts(mock_async_transport)
        assert path == f"/api/observability/slos/{SLO_ID}"
        assert query["instanceId"] == ["my-service"]

    async def test_get_url_encodes_slo_id(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(body={})
        client = AsyncKibana(_transport=mock_async_transport)

        await client.slos.get(slo_id="my slo/id")

        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["target"] == "/api/observability/slos/my%20slo%2Fid"


class TestAsyncSlosClientUpdate:
    """Test AsyncSlosClient.update()."""

    async def test_update_partial(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": SLO_ID, "description": "new desc"}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.slos.update(
            slo_id=SLO_ID, description="new desc", tags=["prod"]
        )

        assert result.body["description"] == "new desc"
        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["method"] == "PUT"
        assert kwargs["target"] == f"/api/observability/slos/{SLO_ID}"
        assert kwargs["body"] == {"description": "new desc", "tags": ["prod"]}

    async def test_update_camel_case_fields(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(body={})
        client = AsyncKibana(_transport=mock_async_transport)

        await client.slos.update(
            slo_id=SLO_ID,
            time_window={"duration": "30d", "type": "rolling"},
            budgeting_method="occurrences",
            group_by="service.name",
        )

        body = _call_kwargs(mock_async_transport)["body"]
        assert body == {
            "timeWindow": {"duration": "30d", "type": "rolling"},
            "budgetingMethod": "occurrences",
            "groupBy": "service.name",
        }


class TestAsyncSlosClientDelete:
    """Test AsyncSlosClient.delete()."""

    async def test_delete(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(status=204)
        client = AsyncKibana(_transport=mock_async_transport)

        await client.slos.delete(slo_id=SLO_ID)

        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["method"] == "DELETE"
        assert kwargs["target"] == f"/api/observability/slos/{SLO_ID}"
        assert "body" not in kwargs


class TestAsyncSlosClientEnableDisableReset:
    """Test enable(), disable() and reset()."""

    async def test_enable(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(status=204)
        client = AsyncKibana(_transport=mock_async_transport)

        await client.slos.enable(slo_id=SLO_ID)

        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == f"/api/observability/slos/{SLO_ID}/enable"

    async def test_disable(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(status=204)
        client = AsyncKibana(_transport=mock_async_transport)

        await client.slos.disable(slo_id=SLO_ID)

        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == f"/api/observability/slos/{SLO_ID}/disable"

    async def test_reset(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": SLO_ID, "version": 2}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.slos.reset(slo_id=SLO_ID)

        assert result.body["version"] == 2
        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == f"/api/observability/slos/{SLO_ID}/_reset"

    async def test_enable_with_space_id(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(status=204)
        client = AsyncKibana(_transport=mock_async_transport)

        await client.slos.enable(
            slo_id=SLO_ID, space_id="team-b", validate_spaces=False
        )

        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["target"] == f"/s/team-b/api/observability/slos/{SLO_ID}/enable"


class TestAsyncSlosClientDeleteInstances:
    """Test AsyncSlosClient.delete_instances()."""

    async def test_delete_instances(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(status=204)
        client = AsyncKibana(_transport=mock_async_transport)

        await client.slos.delete_instances(
            instances=[{"sloId": SLO_ID, "instanceId": "my-service"}]
        )

        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/observability/slos/_delete_instances"
        assert kwargs["body"] == {
            "list": [{"sloId": SLO_ID, "instanceId": "my-service"}]
        }


class TestAsyncSlosClientBulkDelete:
    """Test bulk_delete() and bulk_delete_status()."""

    async def test_bulk_delete(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"taskId": "task-123"}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.slos.bulk_delete(slo_ids=[SLO_ID, "other-slo"])

        assert result.body["taskId"] == "task-123"
        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/observability/slos/_bulk_delete"
        assert kwargs["body"] == {"list": [SLO_ID, "other-slo"]}

    async def test_bulk_delete_status(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"isDone": True, "results": [{"id": SLO_ID, "success": True}]}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.slos.bulk_delete_status(task_id="task-123")

        assert result.body["isDone"] is True
        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/observability/slos/_bulk_delete/task-123"

    async def test_bulk_delete_status_url_encodes_task_id(
        self, mock_async_transport, mock_response
    ):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"isDone": False}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.slos.bulk_delete_status(task_id="node:12345")

        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["target"] == "/api/observability/slos/_bulk_delete/node%3A12345"


class TestAsyncSlosClientBulkPurgeRollup:
    """Test AsyncSlosClient.bulk_purge_rollup()."""

    async def test_bulk_purge_rollup(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"taskId": "es-task:1"}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.slos.bulk_purge_rollup(
            slo_ids=[SLO_ID],
            purge_policy={"purgeType": "fixed_age", "age": "30d"},
        )

        assert result.body["taskId"] == "es-task:1"
        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/observability/slos/_bulk_purge_rollup"
        assert kwargs["body"] == {
            "list": [SLO_ID],
            "purgePolicy": {"purgeType": "fixed_age", "age": "30d"},
        }


class TestAsyncSlosClientFindDefinitions:
    """Test AsyncSlosClient.find_definitions()."""

    async def test_find_definitions_defaults(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"page": 1, "perPage": 100, "total": 0, "results": []}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.slos.find_definitions()

        assert result.body["total"] == 0
        kwargs = _call_kwargs(mock_async_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/observability/slos/_definitions"

    async def test_find_definitions_with_params(
        self, mock_async_transport, mock_response
    ):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"results": []}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.slos.find_definitions(
            include_outdated_only=False,
            include_health=True,
            tags="prod",
            search="my-service*",
            page=1,
            per_page=10,
        )

        path, query = _target_parts(mock_async_transport)
        assert path == "/api/observability/slos/_definitions"
        assert query["includeOutdatedOnly"] == ["false"]
        assert query["includeHealth"] == ["true"]
        assert query["tags"] == ["prod"]
        assert query["search"] == ["my-service*"]
        assert query["page"] == ["1"]
        assert query["perPage"] == ["10"]


class TestAsyncSlosClientErrorHandling:
    """Test AsyncSlosClient error mapping."""

    async def test_get_not_found(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": f"SLO [{SLO_ID}] not found",
            },
            status=404,
        )
        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(NotFoundError):
            await client.slos.get(slo_id=SLO_ID)
