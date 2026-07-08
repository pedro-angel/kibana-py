"""Unit tests for StreamsClient."""

import json
from unittest.mock import Mock

import pytest
from elastic_transport import BinaryApiResponse, ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.streams import (
    StreamsClient,
    _build_content_pack_multipart,
    _ensure_zip_response_serializer,
    _ZipContentSerializer,
)
from kibana.exceptions import NotFoundError

ESQL = "FROM logs.ecs.myapp, logs.ecs.myapp.* METADATA _id, _source"


def _ok(body: dict) -> ObjectApiResponse:
    """Build a 200 ObjectApiResponse with the given body."""
    return ObjectApiResponse(body=body, meta=Mock(status=200, headers={}))


def _ack() -> dict:
    return {"acknowledged": True, "result": "updated"}


def _wired_stream_definition() -> dict:
    """A Kibana 9.4.3 wired stream definition (as accepted by upsert)."""
    return {
        "type": "wired",
        "description": "My app logs",
        "ingest": {
            "lifecycle": {"inherit": {}},
            "processing": {"steps": []},
            "settings": {},
            "failure_store": {"inherit": {}},
            "wired": {"fields": {}, "routing": []},
        },
    }


class TestStreamsClientInitialization:
    """Test StreamsClient initialization and wiring."""

    def test_initialization(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        streams_client = StreamsClient(client)
        assert streams_client._client is client

    def test_streams_property_returns_streams_client(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.streams, StreamsClient)

    def test_streams_property_caching(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        assert client.streams is client.streams


class TestStreamsGlobalOperations:
    """Test enable/disable/resync/get_all."""

    def test_enable(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(
            {"acknowledged": True, "result": "created"}
        )
        client = Kibana(_transport=mock_transport)

        result = client.streams.enable()

        assert result.body["acknowledged"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/streams/_enable"
        # The base client injects the kbn-xsrf header on mutating methods
        assert call_kwargs["headers"] == {
            "accept": "application/json",
            "kbn-xsrf": "true",
        }
        assert call_kwargs.get("body") is None

    def test_disable(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(
            {"acknowledged": True, "result": "deleted"}
        )
        client = Kibana(_transport=mock_transport)

        result = client.streams.disable()

        assert result.body["result"] == "deleted"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/streams/_disable"

    def test_resync(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(_ack())
        client = Kibana(_transport=mock_transport)

        result = client.streams.resync()

        assert result.body["acknowledged"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/streams/_resync"

    def test_get_all(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(
            {
                "streams": [
                    {"type": "wired", "name": "logs.ecs", "description": ""},
                    {"type": "wired", "name": "logs.otel", "description": ""},
                ]
            }
        )
        client = Kibana(_transport=mock_transport)

        result = client.streams.get_all()

        assert [s["name"] for s in result.body["streams"]] == [
            "logs.ecs",
            "logs.otel",
        ]
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/streams"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    def test_get_all_space_scoped(self, mock_transport):
        mock_transport.perform_request.return_value = _ok({"streams": []})
        client = Kibana(_transport=mock_transport)

        client.streams.get_all(space_id="marketing", validate_spaces=False)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/streams"


class TestStreamsCrud:
    """Test get/upsert/delete/fork."""

    def test_get(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(
            {
                "stream": {"type": "wired", "name": "logs.ecs"},
                "dashboards": [],
                "rules": [],
                "queries": [],
            }
        )
        client = Kibana(_transport=mock_transport)

        result = client.streams.get(name="logs.ecs")

        assert result.body["stream"]["type"] == "wired"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/streams/logs.ecs"

    def test_get_encodes_name(self, mock_transport):
        mock_transport.perform_request.return_value = _ok({"stream": {}})
        client = Kibana(_transport=mock_transport)

        client.streams.get(name="logs.ecs/odd name")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/streams/logs.ecs%2Fodd%20name"

    def test_upsert_defaults_linked_object_lists(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(
            {"acknowledged": True, "result": "created"}
        )
        client = Kibana(_transport=mock_transport)
        stream = _wired_stream_definition()

        result = client.streams.upsert(name="logs.ecs.myapp", stream=stream)

        assert result.body["result"] == "created"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/streams/logs.ecs.myapp"
        assert call_kwargs["body"] == {
            "stream": stream,
            "dashboards": [],
            "queries": [],
            "rules": [],
        }

    def test_upsert_with_linked_objects(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(_ack())
        client = Kibana(_transport=mock_transport)
        queries = [
            {
                "id": "q1",
                "title": "t",
                "description": "d",
                "esql": {"query": ESQL},
            }
        ]

        client.streams.upsert(
            name="logs.ecs.myapp",
            stream=_wired_stream_definition(),
            dashboards=["dash-1"],
            queries=queries,
            rules=["rule-1"],
        )

        body = mock_transport.perform_request.call_args[1]["body"]
        assert body["dashboards"] == ["dash-1"]
        assert body["queries"] == queries
        assert body["rules"] == ["rule-1"]

    def test_delete(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(
            {"acknowledged": True, "result": "deleted"}
        )
        client = Kibana(_transport=mock_transport)

        result = client.streams.delete(name="logs.ecs.myapp")

        assert result.body["result"] == "deleted"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/streams/logs.ecs.myapp"
        assert call_kwargs.get("body") is None

    def test_fork(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(
            {"acknowledged": True, "result": "created"}
        )
        client = Kibana(_transport=mock_transport)
        where = {"field": "service.name", "eq": "myapp"}

        result = client.streams.fork(
            name="logs.ecs",
            stream_name="logs.ecs.myapp",
            where=where,
            status="enabled",
        )

        assert result.body["result"] == "created"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/streams/logs.ecs/_fork"
        assert call_kwargs["body"] == {
            "stream": {"name": "logs.ecs.myapp"},
            "where": where,
            "status": "enabled",
        }

    def test_fork_omits_status_when_not_given(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(_ack())
        client = Kibana(_transport=mock_transport)

        client.streams.fork(
            name="logs.ecs",
            stream_name="logs.ecs.myapp",
            where={"always": {}},
        )

        body = mock_transport.perform_request.call_args[1]["body"]
        assert "status" not in body


class TestStreamsIngestAndQuerySettings:
    """Test _ingest and _query settings endpoints."""

    def test_get_ingest(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(
            {"ingest": {"lifecycle": {"dsl": {}}}}
        )
        client = Kibana(_transport=mock_transport)

        result = client.streams.get_ingest(name="logs.ecs")

        assert result.body["ingest"]["lifecycle"] == {"dsl": {}}
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/streams/logs.ecs/_ingest"

    def test_update_ingest(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(_ack())
        client = Kibana(_transport=mock_transport)
        ingest = _wired_stream_definition()["ingest"]

        client.streams.update_ingest(name="logs.ecs.myapp", ingest=ingest)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/streams/logs.ecs.myapp/_ingest"
        assert call_kwargs["body"] == {"ingest": ingest}

    def test_get_query_settings(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(
            {"query": {"view": "$.myquerystream", "esql": ESQL}}
        )
        client = Kibana(_transport=mock_transport)

        result = client.streams.get_query_settings(name="myquerystream")

        assert result.body["query"]["esql"] == ESQL
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/streams/myquerystream/_query"

    def test_update_query_settings(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(
            {"acknowledged": True, "result": "created"}
        )
        client = Kibana(_transport=mock_transport)

        result = client.streams.update_query_settings(
            name="myquerystream",
            esql=ESQL,
            field_descriptions={"message": "Log message"},
        )

        assert result.body["result"] == "created"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/streams/myquerystream/_query"
        assert call_kwargs["body"] == {
            "query": {"esql": ESQL},
            "field_descriptions": {"message": "Log message"},
        }

    def test_update_query_settings_omits_field_descriptions(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(_ack())
        client = Kibana(_transport=mock_transport)

        client.streams.update_query_settings(name="myquerystream", esql=ESQL)

        body = mock_transport.perform_request.call_args[1]["body"]
        assert body == {"query": {"esql": ESQL}}


class TestStreamsQueries:
    """Test the stream queries endpoints."""

    def test_get_queries(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(
            {"queries": [{"id": "q1", "title": "t", "esql": {"query": ESQL}}]}
        )
        client = Kibana(_transport=mock_transport)

        result = client.streams.get_queries(name="logs.ecs.myapp")

        assert result.body["queries"][0]["id"] == "q1"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/streams/logs.ecs.myapp/queries"

    def test_bulk_queries(self, mock_transport):
        mock_transport.perform_request.return_value = _ok({"acknowledged": True})
        client = Kibana(_transport=mock_transport)
        operations = [
            {
                "index": {
                    "id": "q1",
                    "title": "t",
                    "description": "d",
                    "esql": {"query": ESQL},
                }
            },
            {"delete": {"id": "q0"}},
        ]

        result = client.streams.bulk_queries(
            name="logs.ecs.myapp", operations=operations
        )

        assert result.body["acknowledged"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/streams/logs.ecs.myapp/queries/_bulk"
        assert call_kwargs["body"] == {"operations": operations}

    def test_upsert_query_full_body(self, mock_transport):
        mock_transport.perform_request.return_value = _ok({"acknowledged": True})
        client = Kibana(_transport=mock_transport)

        client.streams.upsert_query(
            name="logs.ecs.myapp",
            query_id="errors",
            title="Error spike",
            esql=ESQL,
            description="Spikes of error logs",
            severity_score=75,
            evidence=["Errors correlate with outages"],
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/streams/logs.ecs.myapp/queries/errors"
        assert call_kwargs["body"] == {
            "title": "Error spike",
            "esql": {"query": ESQL},
            "description": "Spikes of error logs",
            "severity_score": 75,
            "evidence": ["Errors correlate with outages"],
        }

    def test_upsert_query_minimal_body(self, mock_transport):
        mock_transport.perform_request.return_value = _ok({"acknowledged": True})
        client = Kibana(_transport=mock_transport)

        client.streams.upsert_query(
            name="logs.ecs.myapp",
            query_id="errors",
            title="Error spike",
            esql=ESQL,
        )

        body = mock_transport.perform_request.call_args[1]["body"]
        assert body == {"title": "Error spike", "esql": {"query": ESQL}}

    def test_delete_query(self, mock_transport):
        mock_transport.perform_request.return_value = _ok({"acknowledged": True})
        client = Kibana(_transport=mock_transport)

        result = client.streams.delete_query(name="logs.ecs.myapp", query_id="errors")

        assert result.body["acknowledged"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/streams/logs.ecs.myapp/queries/errors"
        assert call_kwargs.get("body") is None


class TestStreamsSignificantEvents:
    """Test the significant events endpoints."""

    def test_get_significant_events_param_encoding(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(
            {"significant_events": [], "aggregated_occurrences": []}
        )
        client = Kibana(_transport=mock_transport)

        result = client.streams.get_significant_events(
            name="logs.ecs.myapp",
            from_="now-24h",
            to="now",
            bucket_size="1h",
            query="error",
            search_mode="keyword",
        )

        assert result.body["significant_events"] == []
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/streams/logs.ecs.myapp/significant_events"
            "?from=now-24h&to=now&bucketSize=1h&query=error&searchMode=keyword"
        )

    def test_get_significant_events_omits_optional_params(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(
            {"significant_events": [], "aggregated_occurrences": []}
        )
        client = Kibana(_transport=mock_transport)

        client.streams.get_significant_events(
            name="logs.ecs.myapp", from_="now-24h", to="now", bucket_size="1h"
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/streams/logs.ecs.myapp/significant_events"
            "?from=now-24h&to=now&bucketSize=1h"
        )

    def test_generate_significant_events(self, mock_transport):
        mock_transport.perform_request.return_value = _ok({"queries": []})
        client = Kibana(_transport=mock_transport)

        client.streams.generate_significant_events(
            name="logs.ecs.myapp",
            from_="now-24h",
            to="now",
            connector_id="my-connector",
            sample_docs_size=100,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/streams/logs.ecs.myapp/significant_events/_generate"
            "?from=now-24h&to=now&connectorId=my-connector&sampleDocsSize=100"
        )
        assert call_kwargs.get("body") is None

    def test_preview_significant_events(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(
            {"occurrences": [], "change_points": {"type": {}}}
        )
        client = Kibana(_transport=mock_transport)

        result = client.streams.preview_significant_events(
            name="logs.ecs.myapp",
            from_="now-24h",
            to="now",
            bucket_size="1h",
            esql=ESQL,
        )

        assert result.body["occurrences"] == []
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/streams/logs.ecs.myapp/significant_events/_preview"
            "?from=now-24h&to=now&bucketSize=1h"
        )
        assert call_kwargs["body"] == {"query": {"esql": {"query": ESQL}}}


class TestStreamsContentPacks:
    """Test the content export/import endpoints."""

    def test_export_content(self, mock_transport):
        mock_transport.perform_request.return_value = BinaryApiResponse(
            body=b"PK\x03\x04zipbytes",
            meta=Mock(status=200, headers={"content-type": "application/zip"}),
        )
        client = Kibana(_transport=mock_transport)

        result = client.streams.export_content(
            name="logs.ecs.myapp",
            content_name="myapp-pack",
            description="My app content",
            version="1.0.0",
        )

        assert bytes(result.body).startswith(b"PK")
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/streams/logs.ecs.myapp/content/export"
        # The base client merges in kbn-xsrf/content-type for JSON bodies
        assert call_kwargs["headers"]["accept"] == "application/zip"
        assert call_kwargs["body"] == {
            "name": "myapp-pack",
            "description": "My app content",
            "version": "1.0.0",
            "include": {"objects": {"all": {}}},
        }

    def test_export_content_custom_include(self, mock_transport):
        mock_transport.perform_request.return_value = _ok({})
        client = Kibana(_transport=mock_transport)
        include = {"objects": {"queries": [{"id": "q1"}]}}

        client.streams.export_content(
            name="logs.ecs.myapp",
            content_name="myapp-pack",
            description="d",
            version="1.0.0",
            include=include,
        )

        body = mock_transport.perform_request.call_args[1]["body"]
        assert body["include"] == include

    def test_import_content_multipart_body(self, mock_transport):
        mock_transport.perform_request.return_value = _ok(
            {"acknowledged": True, "result": {"created": [], "updated": []}}
        )
        client = Kibana(_transport=mock_transport)

        result = client.streams.import_content(
            name="logs.ecs.myapp",
            content=b"PK\x03\x04zipbytes",
            filename="my-pack.zip",
        )

        assert result.body["acknowledged"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/streams/logs.ecs.myapp/content/import"

        content_type = call_kwargs["headers"]["content-type"]
        assert content_type.startswith("multipart/form-data; boundary=")
        assert call_kwargs["headers"]["accept"] == "application/json"

        body = call_kwargs["body"]
        boundary = content_type.split("boundary=")[1]
        assert isinstance(body, bytes)
        assert body.startswith(f"--{boundary}\r\n".encode())
        assert body.endswith(f"--{boundary}--\r\n".encode())
        assert b'name="include"' in body
        assert json.dumps({"objects": {"all": {}}}).encode() in body
        assert b'name="content"; filename="my-pack.zip"' in body
        assert b"Content-Type: application/zip" in body
        assert b"PK\x03\x04zipbytes" in body

    def test_build_content_pack_multipart_helper(self):
        include = {"objects": {"all": {}}}
        body, content_type = _build_content_pack_multipart(
            include, b"zipbytes", "pack.zip"
        )

        boundary = content_type.split("boundary=")[1]
        assert content_type.startswith("multipart/form-data; boundary=")
        assert body.count(f"--{boundary}".encode()) == 3
        assert b"zipbytes\r\n" in body


class TestStreamsAttachments:
    """Test the stream attachments endpoints."""

    def test_get_attachments_no_filters(self, mock_transport):
        mock_transport.perform_request.return_value = _ok({"attachments": []})
        client = Kibana(_transport=mock_transport)

        result = client.streams.get_attachments(name="logs.ecs.myapp")

        assert result.body["attachments"] == []
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/streams/logs.ecs.myapp/attachments"

    def test_get_attachments_list_params_repeat_keys(self, mock_transport):
        mock_transport.perform_request.return_value = _ok({"attachments": []})
        client = Kibana(_transport=mock_transport)

        client.streams.get_attachments(
            name="logs.ecs.myapp",
            query="latency",
            attachment_types=["dashboard", "rule"],
            tags=["prod"],
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/streams/logs.ecs.myapp/attachments"
            "?query=latency&attachmentTypes=dashboard&attachmentTypes=rule"
            "&tags=prod"
        )

    def test_bulk_attachments(self, mock_transport):
        mock_transport.perform_request.return_value = _ok({"acknowledged": True})
        client = Kibana(_transport=mock_transport)
        operations = [
            {"index": {"id": "dash-1", "type": "dashboard"}},
            {"delete": {"id": "rule-1", "type": "rule"}},
        ]

        result = client.streams.bulk_attachments(
            name="logs.ecs.myapp", operations=operations
        )

        assert result.body["acknowledged"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/streams/logs.ecs.myapp/attachments/_bulk"
        )
        assert call_kwargs["body"] == {"operations": operations}

    def test_link_attachment(self, mock_transport):
        mock_transport.perform_request.return_value = _ok({"acknowledged": True})
        client = Kibana(_transport=mock_transport)

        result = client.streams.link_attachment(
            name="logs.ecs.myapp",
            attachment_type="dashboard",
            attachment_id="dash-1",
        )

        assert result.body["acknowledged"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == (
            "/api/streams/logs.ecs.myapp/attachments/dashboard/dash-1"
        )
        assert call_kwargs.get("body") is None

    def test_unlink_attachment(self, mock_transport):
        mock_transport.perform_request.return_value = _ok({"acknowledged": True})
        client = Kibana(_transport=mock_transport)

        result = client.streams.unlink_attachment(
            name="logs.ecs.myapp",
            attachment_type="dashboard",
            attachment_id="dash-1",
        )

        assert result.body["acknowledged"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == (
            "/api/streams/logs.ecs.myapp/attachments/dashboard/dash-1"
        )


class TestZipSerializerRegistration:
    """Test the application/zip response serializer helper."""

    def test_zip_serializer_roundtrip(self):
        serializer = _ZipContentSerializer()
        assert serializer.loads(b"PK\x03\x04") == b"PK\x03\x04"
        assert serializer.dumps(b"PK\x03\x04") == b"PK\x03\x04"

    def test_zip_serializer_dumps_rejects_non_bytes(self):
        from elastic_transport import SerializationError

        with pytest.raises(SerializationError):
            _ZipContentSerializer().dumps({"not": "bytes"})

    def test_ensure_zip_response_serializer_registers_once(self):
        class FakeCollection:
            def __init__(self):
                self.serializers = {}

        class FakeTransport:
            def __init__(self):
                self.serializers = FakeCollection()

        class FakeClient:
            def __init__(self):
                self._transport = FakeTransport()

        fake = FakeClient()
        _ensure_zip_response_serializer(fake)
        registered = fake._transport.serializers.serializers["application/zip"]
        assert isinstance(registered, _ZipContentSerializer)

        # Idempotent: a second call keeps the same instance
        _ensure_zip_response_serializer(fake)
        assert fake._transport.serializers.serializers["application/zip"] is registered

    def test_ensure_zip_response_serializer_tolerates_missing_transport(self):
        class NoTransportClient:
            pass

        # Must not raise even if the client has no transport attribute
        _ensure_zip_response_serializer(NoTransportClient())


class TestStreamsErrorHandling:
    """Test error mapping for the streams namespace."""

    def test_get_not_found_error(self, mock_transport):
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Cannot find stream logs.nope",
                "attributes": {},
            },
            meta=Mock(status=404, headers={}),
        )
        client = Kibana(_transport=mock_transport)

        with pytest.raises(NotFoundError):
            client.streams.get(name="logs.nope")

    def test_upsert_bad_request_error(self, mock_transport):
        from kibana.exceptions import BadRequestError

        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 400,
                "error": "Bad Request",
                "message": 'Invalid input: expected "wired"',
            },
            meta=Mock(status=400, headers={}),
        )
        client = Kibana(_transport=mock_transport)

        with pytest.raises(BadRequestError):
            client.streams.upsert(
                name="logs.ecs.myapp", stream={"description": "missing type"}
            )
