"""Unit tests for CasesClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.cases import DEFAULT_CASE_CONNECTOR, CasesClient
from kibana.exceptions import NotFoundError


def _response(body=None, status=200):
    return ObjectApiResponse(
        body=body if body is not None else {},
        meta=Mock(status=status, headers={}),
    )


@pytest.fixture
def client(mock_transport):
    mock_transport.perform_request.return_value = _response({})
    return Kibana(_transport=mock_transport)


def _call_kwargs(mock_transport):
    return mock_transport.perform_request.call_args[1]


class TestCasesClientInitialization:
    def test_initialization(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        cases_client = CasesClient(client)
        assert cases_client._client is client

    def test_cases_property_returns_cases_client(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.cases, CasesClient)


class TestCasesCreate:
    def test_create_with_defaults(self, client, mock_transport):
        client.cases.create(title="My case", description="A description")

        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/cases"
        assert kwargs["headers"]["accept"] == "application/json"
        assert kwargs["headers"]["kbn-xsrf"] == "true"
        assert kwargs["body"] == {
            "title": "My case",
            "description": "A description",
            "owner": "cases",
            "tags": [],
            "connector": DEFAULT_CASE_CONNECTOR,
            "settings": {"syncAlerts": False},
        }

    def test_create_with_all_options(self, client, mock_transport):
        client.cases.create(
            title="My case",
            description="A description",
            owner="observability",
            tags=["tag-1"],
            connector={"id": "c1", "name": "jira", "type": ".jira", "fields": None},
            settings={"syncAlerts": True},
            assignees=[{"uid": "u_1"}],
            category="ops",
            custom_fields=[{"key": "k", "type": "text", "value": "v"}],
            severity="high",
        )

        body = _call_kwargs(mock_transport)["body"]
        assert body["owner"] == "observability"
        assert body["tags"] == ["tag-1"]
        assert body["connector"]["type"] == ".jira"
        assert body["settings"] == {"syncAlerts": True}
        assert body["assignees"] == [{"uid": "u_1"}]
        assert body["category"] == "ops"
        assert body["customFields"] == [{"key": "k", "type": "text", "value": "v"}]
        assert body["severity"] == "high"

    def test_create_space_scoped(self, client, mock_transport):
        client.cases.create(
            title="t",
            description="d",
            space_id="marketing",
            validate_spaces=False,
        )
        assert _call_kwargs(mock_transport)["target"] == "/s/marketing/api/cases"


class TestCasesGet:
    def test_get(self, client, mock_transport):
        client.cases.get(case_id="abc-123")
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/cases/abc-123"
        assert kwargs["headers"] == {"accept": "application/json"}

    def test_get_quotes_path_params(self, client, mock_transport):
        client.cases.get(case_id="a b/c")
        assert _call_kwargs(mock_transport)["target"] == "/api/cases/a%20b%2Fc"

    def test_get_not_found(self, client, mock_transport):
        mock_transport.perform_request.return_value = _response(
            {"statusCode": 404, "error": "Not Found", "message": "case not found"},
            status=404,
        )
        with pytest.raises(NotFoundError):
            client.cases.get(case_id="missing")


class TestCasesUpdate:
    def test_update_single_case(self, client, mock_transport):
        client.cases.update(
            id="abc",
            version="WzEsMV0=",
            status="closed",
            title="New title",
            close_reason="resolved",
            custom_fields=[{"key": "k", "type": "text", "value": "v"}],
        )
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "PATCH"
        assert kwargs["target"] == "/api/cases"
        assert kwargs["body"] == {
            "cases": [
                {
                    "id": "abc",
                    "version": "WzEsMV0=",
                    "closeReason": "resolved",
                    "customFields": [{"key": "k", "type": "text", "value": "v"}],
                    "status": "closed",
                    "title": "New title",
                }
            ]
        }

    def test_update_bulk(self, client, mock_transport):
        updates = [
            {"id": "a", "version": "v1", "status": "closed"},
            {"id": "b", "version": "v2", "severity": "low"},
        ]
        client.cases.update(cases=updates)
        assert _call_kwargs(mock_transport)["body"] == {"cases": updates}

    def test_update_requires_id_and_version(self, client):
        with pytest.raises(ValueError, match="id.*version"):
            client.cases.update(status="closed")

    def test_update_rejects_mixed_forms(self, client):
        with pytest.raises(ValueError, match="not both"):
            client.cases.update(id="a", cases=[{"id": "a", "version": "v"}])


class TestCasesDelete:
    def test_delete_encodes_ids_as_json_array(self, client, mock_transport):
        client.cases.delete(ids=["id-1", "id-2"])
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "DELETE"
        # The cases API expects a JSON-array string: ids=["id-1","id-2"]
        assert kwargs["target"] == "/api/cases?ids=%5B%22id-1%22%2C%22id-2%22%5D"

    def test_delete_accepts_single_id_string(self, client, mock_transport):
        client.cases.delete(ids="only-one")
        assert (
            _call_kwargs(mock_transport)["target"]
            == "/api/cases?ids=%5B%22only-one%22%5D"
        )


class TestCasesFind:
    def test_find_all_params(self, client, mock_transport):
        client.cases.find(
            assignees="none",
            category="ops",
            default_search_operator="AND",
            from_="now-1d",
            owner="cases",
            page=2,
            per_page=50,
            reporters="elastic",
            search="login",
            search_fields=["title", "description"],
            severity="high",
            sort_field="updatedAt",
            sort_order="asc",
            status="open",
            tags=["one", "two"],
            to="now",
        )
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        target = kwargs["target"]
        assert target.startswith("/api/cases/_find?")
        assert "assignees=none" in target
        assert "category=ops" in target
        assert "defaultSearchOperator=AND" in target
        assert "from=now-1d" in target
        assert "owner=cases" in target
        assert "page=2" in target
        assert "perPage=50" in target
        assert "reporters=elastic" in target
        assert "search=login" in target
        assert "searchFields=title&searchFields=description" in target
        assert "severity=high" in target
        assert "sortField=updatedAt" in target
        assert "sortOrder=asc" in target
        assert "status=open" in target
        assert "tags=one&tags=two" in target
        assert "to=now" in target

    def test_find_without_params(self, client, mock_transport):
        client.cases.find()
        assert _call_kwargs(mock_transport)["target"] == "/api/cases/_find"


class TestCasesAlerts:
    def test_get_alerts(self, client, mock_transport):
        client.cases.get_alerts(case_id="abc")
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/cases/abc/alerts"

    def test_get_cases_by_alert(self, client, mock_transport):
        client.cases.get_cases_by_alert(alert_id="alert-1", owner="securitySolution")
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/cases/alerts/alert-1?owner=securitySolution"


class TestCasesComments:
    def test_add_comment_user(self, client, mock_transport):
        client.cases.add_comment(case_id="abc", comment="hello")
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/cases/abc/comments"
        assert kwargs["body"] == {
            "type": "user",
            "owner": "cases",
            "comment": "hello",
        }

    def test_add_comment_alert(self, client, mock_transport):
        client.cases.add_comment(
            case_id="abc",
            type="alert",
            owner="securitySolution",
            alert_id=["a1"],
            index=["idx-1"],
            rule={"id": "r1", "name": "rule"},
        )
        body = _call_kwargs(mock_transport)["body"]
        assert body == {
            "type": "alert",
            "owner": "securitySolution",
            "alertId": ["a1"],
            "index": ["idx-1"],
            "rule": {"id": "r1", "name": "rule"},
        }

    def test_update_comment(self, client, mock_transport):
        client.cases.update_comment(
            case_id="abc", id="c1", version="v1", comment="edited"
        )
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "PATCH"
        assert kwargs["target"] == "/api/cases/abc/comments"
        assert kwargs["body"] == {
            "id": "c1",
            "version": "v1",
            "type": "user",
            "owner": "cases",
            "comment": "edited",
        }

    def test_get_comment(self, client, mock_transport):
        client.cases.get_comment(case_id="abc", comment_id="c1")
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/cases/abc/comments/c1"

    def test_get_comments(self, client, mock_transport):
        client.cases.get_comments(case_id="abc", page=1, per_page=10, sort_order="asc")
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert (
            kwargs["target"]
            == "/api/cases/abc/comments/_find?page=1&perPage=10&sortOrder=asc"
        )

    def test_delete_comment(self, client, mock_transport):
        client.cases.delete_comment(case_id="abc", comment_id="c1")
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "DELETE"
        assert kwargs["target"] == "/api/cases/abc/comments/c1"

    def test_delete_all_comments(self, client, mock_transport):
        client.cases.delete_all_comments(case_id="abc")
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "DELETE"
        assert kwargs["target"] == "/api/cases/abc/comments"


class TestCasesUserActions:
    def test_find_user_actions(self, client, mock_transport):
        client.cases.find_user_actions(
            case_id="abc", page=1, per_page=5, sort_order="desc", types=["status"]
        )
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        target = kwargs["target"]
        assert target.startswith("/api/cases/abc/user_actions/_find?")
        assert "types=status" in target
        assert "perPage=5" in target


class TestCasesPush:
    def test_push(self, client, mock_transport):
        client.cases.push(case_id="abc", connector_id="conn-1")
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/cases/abc/connector/conn-1/_push"
        assert kwargs.get("body") is None


class TestCasesFiles:
    def test_add_file_builds_multipart_body(self, client, mock_transport):
        client.cases.add_file(case_id="abc", file=b"file-bytes", filename="notes.txt")
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/cases/abc/files"

        content_type = kwargs["headers"]["content-type"]
        assert content_type.startswith("multipart/form-data; boundary=")
        boundary = content_type.split("boundary=", 1)[1]

        body = kwargs["body"]
        assert isinstance(body, bytes)
        assert f"--{boundary}\r\n".encode() in body
        assert f"--{boundary}--\r\n".encode() in body
        assert b'Content-Disposition: form-data; name="filename"' in body
        assert (
            b'Content-Disposition: form-data; name="file"; filename="notes.txt"' in body
        )
        assert b"Content-Type: text/plain" in body
        assert b"file-bytes" in body

    def test_add_file_accepts_str_and_mime_type(self, client, mock_transport):
        client.cases.add_file(
            case_id="abc",
            file="text content",
            filename="data.json",
            mime_type="application/json",
        )
        body = _call_kwargs(mock_transport)["body"]
        assert b"Content-Type: application/json" in body
        assert b"text content" in body


class TestCasesConfiguration:
    def test_get_configuration(self, client, mock_transport):
        client.cases.get_configuration(owner="cases")
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/cases/configure?owner=cases"

    def test_create_configuration_defaults(self, client, mock_transport):
        client.cases.create_configuration(closure_type="close-by-user")
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "POST"
        assert kwargs["target"] == "/api/cases/configure"
        assert kwargs["body"] == {
            "closure_type": "close-by-user",
            "connector": DEFAULT_CASE_CONNECTOR,
            "owner": "cases",
        }

    def test_create_configuration_with_options(self, client, mock_transport):
        client.cases.create_configuration(
            closure_type="close-by-pushing",
            connector={"id": "c1", "name": "jira", "type": ".jira", "fields": None},
            owner="observability",
            custom_fields=[
                {"key": "k", "label": "K", "type": "text", "required": False}
            ],
            templates=[],
        )
        body = _call_kwargs(mock_transport)["body"]
        assert body["closure_type"] == "close-by-pushing"
        assert body["connector"]["id"] == "c1"
        assert body["owner"] == "observability"
        assert body["customFields"][0]["key"] == "k"
        assert body["templates"] == []

    def test_update_configuration(self, client, mock_transport):
        client.cases.update_configuration(
            configuration_id="cfg-1",
            version="v1",
            closure_type="close-by-pushing",
        )
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "PATCH"
        assert kwargs["target"] == "/api/cases/configure/cfg-1"
        assert kwargs["body"] == {
            "version": "v1",
            "closure_type": "close-by-pushing",
        }

    def test_find_connectors(self, client, mock_transport):
        client.cases.find_connectors()
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/cases/configure/connectors/_find"


class TestCasesTagsAndReporters:
    def test_get_tags(self, client, mock_transport):
        client.cases.get_tags(owner="cases")
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert kwargs["target"] == "/api/cases/tags?owner=cases"

    def test_get_tags_no_owner(self, client, mock_transport):
        client.cases.get_tags()
        assert _call_kwargs(mock_transport)["target"] == "/api/cases/tags"

    def test_get_reporters(self, client, mock_transport):
        client.cases.get_reporters(owner=["cases", "observability"])
        kwargs = _call_kwargs(mock_transport)
        assert kwargs["method"] == "GET"
        assert (
            kwargs["target"] == "/api/cases/reporters?owner=cases&owner=observability"
        )
