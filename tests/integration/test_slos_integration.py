"""Integration tests for SlosClient against a live Kibana 9.x instance.

Requires a Platinum-level (or trial) license for the SLO APIs. Backing data
is a tiny throwaway Elasticsearch index with ``@timestamp`` and ``status``
fields; SLOs are ``sli.kql.custom`` indicators over that index.
"""

import base64
import json
import os
import time
import urllib.request
import uuid

import pytest

from kibana.exceptions import NotFoundError

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    get_integration_test_config,
    is_kibana_available,
)

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)

ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
PREFIX = "kbnpy-slos"


def _es_request(method: str, path: str, body: dict | None = None) -> None:
    """Perform a raw request against Elasticsearch with basic auth."""
    _, basic_auth, _ = get_integration_test_config()
    if basic_auth is None:
        basic_auth = ("elastic", "kibana-py-es-dev")
    token = base64.b64encode(f"{basic_auth[0]}:{basic_auth[1]}".encode()).decode()
    request = urllib.request.Request(
        f"{ES_URL}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        response.read()


@pytest.fixture(scope="module")
def es_index():
    """Create a tiny throwaway ES index backing the SLO indicators."""
    index = f"{PREFIX}-idx-{uuid.uuid4().hex[:8]}"
    _es_request(
        "PUT",
        f"/{index}",
        {
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "status": {"type": "keyword"},
                }
            }
        },
    )
    now_ms = int(time.time() * 1000)
    for i, status in enumerate(["ok", "ok", "error"]):
        _es_request(
            "POST",
            f"/{index}/_doc?refresh=true",
            {"@timestamp": now_ms - i * 60_000, "status": status},
        )
    yield index
    try:
        _es_request("DELETE", f"/{index}")
    except Exception:
        pass


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


def _slo_payload(es_index: str, name: str) -> dict:
    """Build kwargs for slos.create() over the throwaway index."""
    return {
        "name": name,
        "description": "kibana-py SLO integration test",
        "indicator": {
            "type": "sli.kql.custom",
            "params": {
                "index": es_index,
                "good": "status: ok",
                "total": "",
                "timestampField": "@timestamp",
            },
        },
        "time_window": {"duration": "7d", "type": "rolling"},
        "budgeting_method": "occurrences",
        "objective": {"target": 0.99},
        "tags": ["kbnpy"],
    }


def _cleanup_slo(client, slo_id: str) -> None:
    """Best-effort SLO deletion for fixture finalizers."""
    try:
        client.slos.delete(slo_id=slo_id)
    except NotFoundError:
        pass
    except Exception:
        pass


@pytest.fixture
def slo(kibana_client, es_index):
    """Create a throwaway SLO and delete it after the test."""
    name = f"{PREFIX}-{uuid.uuid4().hex[:8]}"
    response = kibana_client.slos.create(**_slo_payload(es_index, name))
    slo_id = response.body["id"]
    yield {"id": slo_id, "name": name}
    _cleanup_slo(kibana_client, slo_id)


class TestSlosCrudIntegration:
    """CRUD lifecycle against the live SLO API."""

    def test_create_get_delete(self, kibana_client, es_index):
        name = f"{PREFIX}-crud-{uuid.uuid4().hex[:8]}"
        created = kibana_client.slos.create(**_slo_payload(es_index, name))
        slo_id = created.body["id"]
        try:
            fetched = kibana_client.slos.get(slo_id=slo_id)
            assert fetched.body["id"] == slo_id
            assert fetched.body["name"] == name
            assert fetched.body["budgetingMethod"] == "occurrences"
            assert fetched.body["timeWindow"] == {
                "duration": "7d",
                "type": "rolling",
            }
            assert fetched.body["objective"] == {"target": 0.99}
            assert fetched.body["enabled"] is True
            assert fetched.body["tags"] == ["kbnpy"]
            assert "summary" in fetched.body
        finally:
            kibana_client.slos.delete(slo_id=slo_id)

        with pytest.raises(NotFoundError):
            kibana_client.slos.get(slo_id=slo_id)

    def test_create_with_custom_id(self, kibana_client, es_index):
        custom_id = f"{PREFIX}-{uuid.uuid4().hex[:12]}"
        name = f"{PREFIX}-custom-id-{uuid.uuid4().hex[:8]}"
        created = kibana_client.slos.create(
            id=custom_id, **_slo_payload(es_index, name)
        )
        try:
            assert created.body["id"] == custom_id
        finally:
            _cleanup_slo(kibana_client, custom_id)

    def test_update(self, kibana_client, slo):
        updated = kibana_client.slos.update(
            slo_id=slo["id"],
            description="updated by kibana-py",
            tags=["kbnpy", "updated"],
        )
        assert updated.body["description"] == "updated by kibana-py"
        assert sorted(updated.body["tags"]) == ["kbnpy", "updated"]

        fetched = kibana_client.slos.get(slo_id=slo["id"])
        assert fetched.body["description"] == "updated by kibana-py"
        # Untouched fields must be preserved by the partial update
        assert fetched.body["name"] == slo["name"]

    def test_get_missing_slo_raises_not_found(self, kibana_client):
        with pytest.raises(NotFoundError):
            kibana_client.slos.get(slo_id=f"{PREFIX}-does-not-exist")


class TestSlosFindIntegration:
    """find() and find_definitions() against the live SLO API."""

    def test_find_by_kql_query(self, kibana_client, slo):
        response = kibana_client.slos.find(
            kql_query=f'slo.name:"{slo["name"]}"', per_page=10
        )
        assert response.body["total"] >= 1
        names = [result["name"] for result in response.body["results"]]
        assert slo["name"] in names
        found = next(r for r in response.body["results"] if r["name"] == slo["name"])
        assert "summary" in found

    def test_find_pagination_shape(self, kibana_client, slo):
        response = kibana_client.slos.find(page=1, per_page=1)
        assert response.body["page"] == 1
        assert response.body["perPage"] == 1
        assert len(response.body["results"]) <= 1

    def test_find_definitions(self, kibana_client, slo):
        response = kibana_client.slos.find_definitions(search=slo["name"], per_page=10)
        assert response.body["total"] >= 1
        ids = [result["id"] for result in response.body["results"]]
        assert slo["id"] in ids
        # Definitions do not include computed summaries
        assert "summary" not in response.body["results"][0]

    def test_find_definitions_include_outdated_only(self, kibana_client, slo):
        response = kibana_client.slos.find_definitions(
            search=slo["name"], include_outdated_only=True
        )
        # A freshly created SLO is not outdated
        ids = [result["id"] for result in response.body["results"]]
        assert slo["id"] not in ids


class TestSlosLifecycleIntegration:
    """enable/disable/reset against the live SLO API."""

    def test_disable_and_enable(self, kibana_client, slo):
        kibana_client.slos.disable(slo_id=slo["id"])
        assert kibana_client.slos.get(slo_id=slo["id"]).body["enabled"] is False

        kibana_client.slos.enable(slo_id=slo["id"])
        assert kibana_client.slos.get(slo_id=slo["id"]).body["enabled"] is True

    def test_reset(self, kibana_client, slo):
        response = kibana_client.slos.reset(slo_id=slo["id"])
        assert response.body["id"] == slo["id"]
        assert response.body["name"] == slo["name"]


class TestSlosBulkIntegration:
    """Bulk endpoints against the live SLO API."""

    def test_delete_instances(self, kibana_client, slo):
        # Deleting rollup data of a non-existing instance id is a valid no-op
        response = kibana_client.slos.delete_instances(
            instances=[{"sloId": slo["id"], "instanceId": f"{PREFIX}-noop"}]
        )
        assert response.meta.status == 204

    def test_bulk_purge_rollup(self, kibana_client, slo):
        # NOTE: live Kibana 9.4.3 expects purgeType "fixed_age" (snake_case),
        # not the "fixed-age" documented in the OpenAPI spec.
        response = kibana_client.slos.bulk_purge_rollup(
            slo_ids=[slo["id"]],
            purge_policy={"purgeType": "fixed_age", "age": "30d"},
        )
        assert "taskId" in response.body

    def test_bulk_delete_and_status(self, kibana_client, es_index):
        name = f"{PREFIX}-bulk-{uuid.uuid4().hex[:8]}"
        created = kibana_client.slos.create(**_slo_payload(es_index, name))
        slo_id = created.body["id"]

        try:
            response = kibana_client.slos.bulk_delete(slo_ids=[slo_id])
            task_id = response.body["taskId"]
            assert task_id

            deadline = time.time() + 60
            status = None
            while time.time() < deadline:
                status = kibana_client.slos.bulk_delete_status(task_id=task_id)
                if status.body.get("isDone"):
                    break
                time.sleep(2)

            assert status is not None
            assert status.body["isDone"] is True
            results = {r["id"]: r for r in status.body.get("results", [])}
            assert results[slo_id]["success"] is True

            with pytest.raises(NotFoundError):
                kibana_client.slos.get(slo_id=slo_id)
        finally:
            _cleanup_slo(kibana_client, slo_id)


class TestAsyncSlosIntegration:
    """Async round-trip against the live SLO API."""

    async def test_async_crud_round_trip(self, es_index):
        client = create_test_async_kibana_client(auth_method="auto")
        name = f"{PREFIX}-async-{uuid.uuid4().hex[:8]}"
        slo_id = None
        try:
            created = await client.slos.create(**_slo_payload(es_index, name))
            slo_id = created.body["id"]

            fetched = await client.slos.get(slo_id=slo_id)
            assert fetched.body["name"] == name

            found = await client.slos.find(kql_query=f'slo.name:"{name}"')
            assert slo_id in [r["id"] for r in found.body["results"]]

            definitions = await client.slos.find_definitions(search=name)
            assert slo_id in [r["id"] for r in definitions.body["results"]]

            await client.slos.disable(slo_id=slo_id)
            fetched = await client.slos.get(slo_id=slo_id)
            assert fetched.body["enabled"] is False

            await client.slos.delete(slo_id=slo_id)
            with pytest.raises(NotFoundError):
                await client.slos.get(slo_id=slo_id)
            slo_id = None
        finally:
            if slo_id is not None:
                try:
                    await client.slos.delete(slo_id=slo_id)
                except Exception:
                    pass
            await client.close()
