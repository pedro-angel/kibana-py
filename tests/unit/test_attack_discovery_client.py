"""Unit tests for AttackDiscoveryClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.attack_discovery import AttackDiscoveryClient
from kibana.exceptions import BadRequestError, NotFoundError


def _find_body(**overrides):
    """Kibana 9.4.3 GET /api/attack_discovery/_find response body."""
    body = {
        "connector_names": ["kbnpy connector"],
        "data": [
            {
                "id": "c0c8a8bbb4a6561856a974ee9e461f0c82e673a1f0d83f86c5a8d80fc8de4c4f",
                "connector_name": "kbnpy connector",
                "title": "Suspicious process execution on host-01",
            }
        ],
        "page": 1,
        "per_page": 10,
        "total": 1,
        "unique_alert_ids_count": 0,
    }
    body.update(overrides)
    return body


def _schedule_body(**overrides):
    """Kibana 9.4.3 Attack Discovery schedule response body."""
    body = {
        "id": "b0ab787f-b77b-435f-a4bc-3fd7b82275cb",
        "name": "kbnpy schedule",
        "created_by": "elastic",
        "updated_by": "elastic",
        "created_at": "2026-07-06T22:07:39.001Z",
        "updated_at": "2026-07-06T22:07:39.001Z",
        "enabled": False,
        "params": {
            "alerts_index_pattern": ".alerts-security.alerts-default",
            "api_config": {
                "connectorId": "93ca552a-65a1-41f9-aab2-23875b51caea",
                "actionTypeId": ".gen-ai",
                "name": "kbnpy connector",
            },
            "size": 25,
        },
        "schedule": {"interval": "24h"},
        "actions": [],
    }
    body.update(overrides)
    return body


def _generation_body(status="succeeded", **overrides):
    """Kibana 9.4.3 Attack Discovery generation metadata object."""
    body = {
        "alerts_context_count": 3,
        "connector_id": "93ca552a-65a1-41f9-aab2-23875b51caea",
        "discoveries": 0,
        "end": "2026-07-06T22:33:02.499Z",
        "execution_uuid": "ede89de0-1a41-4fe5-9787-a7303e6836ac",
        "generation_start_time": "2026-07-06T22:31:03.389Z",
        "loading_message": "AI is analyzing up to 25 alerts...",
        "start": "2026-07-06T22:31:03.389Z",
        "status": status,
    }
    body.update(overrides)
    return body


def _mock_ok(mock_transport, body):
    """Set the transport mock to return a 200 ObjectApiResponse with body."""
    mock_transport.perform_request.return_value = ObjectApiResponse(
        body=body,
        meta=Mock(status=200, headers={}),
    )


class TestAttackDiscoveryClientInitialization:
    """Test AttackDiscoveryClient initialization and wiring."""

    def test_initialization(self, mock_transport):
        """Test that AttackDiscoveryClient can be initialized with a parent."""
        client = Kibana(_transport=mock_transport)
        ad_client = AttackDiscoveryClient(client)
        assert ad_client._client is client

    def test_property_returns_client(self, mock_transport):
        """Test that client.attack_discovery returns an AttackDiscoveryClient."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.attack_discovery, AttackDiscoveryClient)

    def test_property_caching(self, mock_transport):
        """Test that the attack_discovery property returns the same instance."""
        client = Kibana(_transport=mock_transport)
        assert client.attack_discovery is client.attack_discovery


class TestAttackDiscoveryFind:
    """Test AttackDiscoveryClient.find() method."""

    def test_find_no_params(self, mock_transport):
        """Test find without parameters hits the bare _find route."""
        _mock_ok(mock_transport, _find_body())

        client = Kibana(_transport=mock_transport)
        result = client.attack_discovery.find()

        assert result.body["total"] == 1
        assert result.body["data"][0]["connector_name"] == "kbnpy connector"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/attack_discovery/_find"
        assert call_kwargs["headers"]["accept"] == "application/json"

    def test_find_param_encoding(self, mock_transport):
        """Test find encodes bools, lists and @timestamp correctly."""
        _mock_ok(mock_transport, _find_body())

        client = Kibana(_transport=mock_transport)
        client.attack_discovery.find(
            enable_field_rendering=False,
            end="now",
            include_unique_alert_ids=True,
            page=1,
            per_page=10,
            search="powershell",
            shared=False,
            sort_field="@timestamp",
            sort_order="desc",
            start="now-24h",
            status=["open", "acknowledged"],
            with_replacements=True,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/attack_discovery/_find"
            "?enable_field_rendering=false"
            "&end=now"
            "&include_unique_alert_ids=true"
            "&page=1"
            "&per_page=10"
            "&search=powershell"
            "&shared=false"
            "&sort_field=%40timestamp"
            "&sort_order=desc"
            "&start=now-24h"
            "&status=open&status=acknowledged"
            "&with_replacements=true"
        )

    def test_find_id_filters(self, mock_transport):
        """Test find encodes ids/alert_ids/connector_names/scheduled filters."""
        _mock_ok(mock_transport, _find_body())

        client = Kibana(_transport=mock_transport)
        client.attack_discovery.find(
            alert_ids=["alert-1", "alert-2"],
            connector_names=["kbnpy connector"],
            ids=["disc-1"],
            scheduled=True,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/attack_discovery/_find"
            "?alert_ids=alert-1&alert_ids=alert-2"
            "&connector_names=kbnpy+connector"
            "&ids=disc-1"
            "&scheduled=true"
        )

    def test_find_space_scoped(self, mock_transport):
        """Test find builds a space-scoped path with space_id."""
        _mock_ok(mock_transport, _find_body())

        client = Kibana(_transport=mock_transport)
        client.attack_discovery.find(space_id="my-space", validate_spaces=False)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/my-space/api/attack_discovery/_find"


class TestAttackDiscoveryBulkUpdate:
    """Test AttackDiscoveryClient.bulk_update() method."""

    def test_bulk_update_minimal(self, mock_transport):
        """Test bulk_update with only ids."""
        _mock_ok(mock_transport, {"data": []})

        client = Kibana(_transport=mock_transport)
        result = client.attack_discovery.bulk_update(ids=["id-1", "id-2"])

        assert result.body == {"data": []}

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/attack_discovery/_bulk"
        assert call_kwargs["body"] == {"update": {"ids": ["id-1", "id-2"]}}
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_bulk_update_full_body(self, mock_transport):
        """Test bulk_update passes all optional update fields through."""
        _mock_ok(mock_transport, {"data": [{"id": "id-1"}]})

        client = Kibana(_transport=mock_transport)
        client.attack_discovery.bulk_update(
            ids=["id-1"],
            enable_field_rendering=False,
            kibana_alert_workflow_status="acknowledged",
            visibility="shared",
            with_replacements=True,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "update": {
                "ids": ["id-1"],
                "enable_field_rendering": False,
                "kibana_alert_workflow_status": "acknowledged",
                "visibility": "shared",
                "with_replacements": True,
            }
        }


class TestAttackDiscoveryGenerate:
    """Test AttackDiscoveryClient.generate() method."""

    def test_generate_minimal(self, mock_transport):
        """Test generate with required parameters and camelCase mapping."""
        _mock_ok(
            mock_transport, {"execution_uuid": "edd26039-0990-4d9f-9829-2a1fcacb77b5"}
        )

        client = Kibana(_transport=mock_transport)
        anonymization_fields = [
            {"id": "f1", "field": "_id", "allowed": True, "anonymized": False},
        ]
        api_config = {"actionTypeId": ".gen-ai", "connectorId": "conn-1"}
        result = client.attack_discovery.generate(
            alerts_index_pattern=".alerts-security.alerts-default",
            anonymization_fields=anonymization_fields,
            api_config=api_config,
            size=25,
        )

        assert result.body["execution_uuid"] == "edd26039-0990-4d9f-9829-2a1fcacb77b5"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/attack_discovery/_generate"
        assert call_kwargs["body"] == {
            "alertsIndexPattern": ".alerts-security.alerts-default",
            "anonymizationFields": anonymization_fields,
            "apiConfig": api_config,
            "size": 25,
            "subAction": "invokeAI",
        }

    def test_generate_full_body(self, mock_transport):
        """Test generate maps all optional snake_case args to camelCase."""
        _mock_ok(mock_transport, {"execution_uuid": "uuid-1"})

        client = Kibana(_transport=mock_transport)
        client.attack_discovery.generate(
            alerts_index_pattern=".alerts-security.alerts-default",
            anonymization_fields=[],
            api_config={"actionTypeId": ".gen-ai", "connectorId": "conn-1"},
            size=100,
            sub_action="invokeStream",
            connector_name="kbnpy connector",
            end="now",
            filter={"bool": {"must": []}},
            model="gpt-4",
            replacements={"anon-1": "host-01"},
            start="now-24h",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "alertsIndexPattern": ".alerts-security.alerts-default",
            "anonymizationFields": [],
            "apiConfig": {"actionTypeId": ".gen-ai", "connectorId": "conn-1"},
            "size": 100,
            "subAction": "invokeStream",
            "connectorName": "kbnpy connector",
            "end": "now",
            "filter": {"bool": {"must": []}},
            "model": "gpt-4",
            "replacements": {"anon-1": "host-01"},
            "start": "now-24h",
        }

    def test_generate_space_scoped(self, mock_transport):
        """Test generate builds a space-scoped path with space_id."""
        _mock_ok(mock_transport, {"execution_uuid": "uuid-1"})

        client = Kibana(_transport=mock_transport)
        client.attack_discovery.generate(
            alerts_index_pattern=".alerts-security.alerts-space1",
            anonymization_fields=[],
            api_config={"actionTypeId": ".gen-ai", "connectorId": "conn-1"},
            size=10,
            space_id="space1",
            validate_spaces=False,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/space1/api/attack_discovery/_generate"


class TestAttackDiscoveryGenerations:
    """Test the generations methods."""

    def test_get_generations(self, mock_transport):
        """Test get_generations with query parameters."""
        _mock_ok(mock_transport, {"generations": [_generation_body()]})

        client = Kibana(_transport=mock_transport)
        result = client.attack_discovery.get_generations(
            end="now", size=50, start="now-24h"
        )

        assert result.body["generations"][0]["status"] == "succeeded"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/attack_discovery/generations?end=now&size=50&start=now-24h"
        )

    def test_get_generations_no_params(self, mock_transport):
        """Test get_generations without parameters."""
        _mock_ok(mock_transport, {"generations": []})

        client = Kibana(_transport=mock_transport)
        client.attack_discovery.get_generations()

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/attack_discovery/generations"

    def test_get_generation(self, mock_transport):
        """Test get_generation encodes the UUID path and query params."""
        _mock_ok(mock_transport, {"generation": _generation_body(status="started")})

        client = Kibana(_transport=mock_transport)
        result = client.attack_discovery.get_generation(
            execution_uuid="ede89de0-1a41-4fe5-9787-a7303e6836ac",
            enable_field_rendering=True,
            with_replacements=False,
        )

        assert result.body["generation"]["status"] == "started"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/attack_discovery/generations/ede89de0-1a41-4fe5-9787-a7303e6836ac"
            "?enable_field_rendering=true&with_replacements=false"
        )

    def test_get_generation_quotes_path(self, mock_transport):
        """Test get_generation URL-encodes special chars in the UUID."""
        _mock_ok(mock_transport, {"generation": _generation_body()})

        client = Kibana(_transport=mock_transport)
        client.attack_discovery.get_generation(execution_uuid="a/b c")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/attack_discovery/generations/a%2Fb%20c"

    def test_dismiss_generation(self, mock_transport):
        """Test dismiss_generation posts to the _dismiss route."""
        _mock_ok(mock_transport, _generation_body(status="dismissed"))

        client = Kibana(_transport=mock_transport)
        result = client.attack_discovery.dismiss_generation(
            execution_uuid="ede89de0-1a41-4fe5-9787-a7303e6836ac"
        )

        assert result.body["status"] == "dismissed"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/attack_discovery/generations/"
            "ede89de0-1a41-4fe5-9787-a7303e6836ac/_dismiss"
        )
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"


class TestAttackDiscoverySchedules:
    """Test the schedules methods."""

    def test_create_schedule_minimal(self, mock_transport):
        """Test create_schedule with only the required properties."""
        _mock_ok(mock_transport, _schedule_body())

        client = Kibana(_transport=mock_transport)
        params = {
            "alerts_index_pattern": ".alerts-security.alerts-default",
            "api_config": {
                "connectorId": "conn-1",
                "actionTypeId": ".gen-ai",
                "name": "kbnpy connector",
            },
            "size": 25,
        }
        result = client.attack_discovery.create_schedule(
            name="kbnpy schedule",
            params=params,
            schedule={"interval": "24h"},
        )

        assert result.body["id"] == "b0ab787f-b77b-435f-a4bc-3fd7b82275cb"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/attack_discovery/schedules"
        assert call_kwargs["body"] == {
            "name": "kbnpy schedule",
            "params": params,
            "schedule": {"interval": "24h"},
        }
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_create_schedule_with_options(self, mock_transport):
        """Test create_schedule passes enabled and actions through."""
        _mock_ok(mock_transport, _schedule_body(enabled=True))

        client = Kibana(_transport=mock_transport)
        client.attack_discovery.create_schedule(
            name="kbnpy schedule",
            params={"alerts_index_pattern": "x", "api_config": {}, "size": 1},
            schedule={"interval": "1h"},
            actions=[{"id": "action-1", "group": "default", "params": {}}],
            enabled=True,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"]["enabled"] is True
        assert call_kwargs["body"]["actions"] == [
            {"id": "action-1", "group": "default", "params": {}}
        ]

    def test_get_schedule(self, mock_transport):
        """Test get_schedule builds the schedule path."""
        _mock_ok(mock_transport, _schedule_body())

        client = Kibana(_transport=mock_transport)
        result = client.attack_discovery.get_schedule(
            id="b0ab787f-b77b-435f-a4bc-3fd7b82275cb"
        )

        assert result.body["name"] == "kbnpy schedule"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/attack_discovery/schedules/b0ab787f-b77b-435f-a4bc-3fd7b82275cb"
        )

    def test_update_schedule(self, mock_transport):
        """Test update_schedule sends the full update body via PUT."""
        _mock_ok(mock_transport, _schedule_body(name="renamed"))

        client = Kibana(_transport=mock_transport)
        params = {
            "alerts_index_pattern": ".alerts-security.alerts-default",
            "api_config": {
                "connectorId": "conn-1",
                "actionTypeId": ".gen-ai",
                "name": "kbnpy connector",
            },
            "size": 50,
        }
        result = client.attack_discovery.update_schedule(
            id="b0ab787f-b77b-435f-a4bc-3fd7b82275cb",
            name="renamed",
            params=params,
            schedule={"interval": "12h"},
            actions=[],
        )

        assert result.body["name"] == "renamed"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == (
            "/api/attack_discovery/schedules/b0ab787f-b77b-435f-a4bc-3fd7b82275cb"
        )
        assert call_kwargs["body"] == {
            "name": "renamed",
            "params": params,
            "schedule": {"interval": "12h"},
            "actions": [],
        }

    def test_delete_schedule(self, mock_transport):
        """Test delete_schedule issues a DELETE on the schedule path."""
        _mock_ok(mock_transport, {"id": "b0ab787f-b77b-435f-a4bc-3fd7b82275cb"})

        client = Kibana(_transport=mock_transport)
        result = client.attack_discovery.delete_schedule(
            id="b0ab787f-b77b-435f-a4bc-3fd7b82275cb"
        )

        assert result.body["id"] == "b0ab787f-b77b-435f-a4bc-3fd7b82275cb"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == (
            "/api/attack_discovery/schedules/b0ab787f-b77b-435f-a4bc-3fd7b82275cb"
        )

    def test_enable_schedule(self, mock_transport):
        """Test enable_schedule posts to the _enable route."""
        _mock_ok(mock_transport, {"id": "sched-1"})

        client = Kibana(_transport=mock_transport)
        client.attack_discovery.enable_schedule(id="sched-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/attack_discovery/schedules/sched-1/_enable"
        )

    def test_disable_schedule(self, mock_transport):
        """Test disable_schedule posts to the _disable route."""
        _mock_ok(mock_transport, {"id": "sched-1"})

        client = Kibana(_transport=mock_transport)
        client.attack_discovery.disable_schedule(id="sched-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/attack_discovery/schedules/sched-1/_disable"
        )

    def test_find_schedules(self, mock_transport):
        """Test find_schedules with pagination and sorting params."""
        _mock_ok(
            mock_transport,
            {"page": 1, "per_page": 10, "total": 1, "data": [_schedule_body()]},
        )

        client = Kibana(_transport=mock_transport)
        result = client.attack_discovery.find_schedules(
            page=0, per_page=10, sort_direction="desc", sort_field="name"
        )

        assert result.body["total"] == 1

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/attack_discovery/schedules/_find"
            "?page=0&per_page=10&sort_direction=desc&sort_field=name"
        )

    def test_find_schedules_no_params(self, mock_transport):
        """Test find_schedules without parameters."""
        _mock_ok(mock_transport, {"page": 1, "per_page": 10, "total": 0, "data": []})

        client = Kibana(_transport=mock_transport)
        client.attack_discovery.find_schedules()

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/attack_discovery/schedules/_find"

    def test_schedule_space_scoped(self, mock_transport):
        """Test schedule methods build space-scoped paths."""
        _mock_ok(mock_transport, _schedule_body())

        client = Kibana(_transport=mock_transport)
        client.attack_discovery.get_schedule(
            id="sched-1", space_id="my-space", validate_spaces=False
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/s/my-space/api/attack_discovery/schedules/sched-1"
        )


class TestAttackDiscoveryErrorHandling:
    """Test AttackDiscoveryClient error mapping."""

    def test_get_generation_not_found(self, mock_transport):
        """Test that an unknown execution UUID maps to NotFoundError."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "message": (
                    "Generation with execution_uuid "
                    "2e13f386-46cf-4d65-9e2b-68609e132ba5 not found"
                ),
                "status_code": 404,
            },
            meta=Mock(status=404, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(NotFoundError):
            client.attack_discovery.get_generation(
                execution_uuid="2e13f386-46cf-4d65-9e2b-68609e132ba5"
            )

    def test_get_schedule_not_found(self, mock_transport):
        """Test that an unknown schedule id maps to NotFoundError."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "message": {
                    "success": False,
                    "error": "Saved object [alert/missing] not found",
                },
                "status_code": 404,
            },
            meta=Mock(status=404, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(NotFoundError):
            client.attack_discovery.get_schedule(id="missing")

    def test_generate_bad_request(self, mock_transport):
        """Test that an invalid generation config maps to BadRequestError."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "status_code": 400,
                "error": "Bad Request",
                "message": "Invalid request parameters.",
            },
            meta=Mock(status=400, headers={}),
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(BadRequestError):
            client.attack_discovery.generate(
                alerts_index_pattern="",
                anonymization_fields=[],
                api_config={},
                size=0,
            )
