"""Integration tests for DataViewsClient / AsyncDataViewsClient.

These tests run against a live Kibana + Elasticsearch stack. A tiny
throwaway Elasticsearch index backs the data views and both it and every
data view created here are cleaned up afterwards.
"""

import base64
import json
import os
import urllib.request
import uuid

import pytest

from kibana.exceptions import BadRequestError, NotFoundError

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

RESOURCE_PREFIX = "kbnpy-dataviews"


def _es_request(method: str, path: str, body: dict | None = None) -> None:
    """Perform a minimal Elasticsearch request for test index setup/teardown."""
    es_url = os.getenv("ES_URL") or os.getenv("ES_LOCAL_URL", "http://localhost:9200")
    _, basic_auth, _ = get_integration_test_config()
    request = urllib.request.Request(
        f"{es_url}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    if basic_auth:
        token = base64.b64encode(f"{basic_auth[0]}:{basic_auth[1]}".encode()).decode()
        request.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(request) as response:
        response.read()


@pytest.fixture(scope="module")
def es_index():
    """Create a tiny backing Elasticsearch index; delete it afterwards."""
    index_name = f"{RESOURCE_PREFIX}-idx-{uuid.uuid4().hex[:8]}"
    _es_request(
        "PUT",
        f"/{index_name}",
        {
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "category": {"type": "keyword"},
                    "price": {"type": "double"},
                }
            }
        },
    )
    _es_request(
        "POST",
        f"/{index_name}/_doc?refresh=true",
        {"@timestamp": "2026-07-01T00:00:00Z", "category": "a", "price": 1.5},
    )
    yield index_name
    _es_request("DELETE", f"/{index_name}")


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


def _delete_data_view_quietly(client, view_id: str) -> None:
    try:
        client.data_views.delete(view_id=view_id)
    except NotFoundError:
        pass
    # Kibana auto-sets the default data view when the first one is created.
    # If our deleted view is still recorded as the default, unset it so we
    # don't leave a dangling reference behind on the shared stack.
    try:
        if client.data_views.get_default()["data_view_id"] == view_id:
            client.data_views.set_default(data_view_id=None, force=True)
    except Exception:
        pass


@pytest.fixture
def data_view(kibana_client, es_index):
    """Create a data view over the test index; delete it afterwards."""
    view_id = f"{RESOURCE_PREFIX}-dv-{uuid.uuid4().hex[:8]}"
    response = kibana_client.data_views.create(
        data_view={
            "id": view_id,
            "title": es_index,
            "name": f"{RESOURCE_PREFIX} test view",
            "timeFieldName": "@timestamp",
        }
    )
    assert response["data_view"]["id"] == view_id
    yield view_id
    _delete_data_view_quietly(kibana_client, view_id)


class TestDataViewCrudIntegration:
    """Live tests for data view CRUD."""

    def test_create_get_update_delete(self, kibana_client, es_index):
        view_id = f"{RESOURCE_PREFIX}-crud-{uuid.uuid4().hex[:8]}"
        try:
            created = kibana_client.data_views.create(
                data_view={
                    "id": view_id,
                    "title": es_index,
                    "name": f"{RESOURCE_PREFIX} crud view",
                    "timeFieldName": "@timestamp",
                }
            )
            assert created["data_view"]["title"] == es_index
            assert created["data_view"]["timeFieldName"] == "@timestamp"
            # Fields were resolved from the backing index
            assert "category" in created["data_view"]["fields"]

            fetched = kibana_client.data_views.get(view_id=view_id)
            assert fetched["data_view"]["id"] == view_id
            assert fetched["data_view"]["name"] == f"{RESOURCE_PREFIX} crud view"

            listed = kibana_client.data_views.get_all()
            assert view_id in [view["id"] for view in listed["data_view"]]

            updated = kibana_client.data_views.update(
                view_id=view_id,
                data_view={"name": f"{RESOURCE_PREFIX} crud renamed"},
                refresh_fields=True,
            )
            assert updated["data_view"]["name"] == f"{RESOURCE_PREFIX} crud renamed"
            # Unspecified properties are preserved
            assert updated["data_view"]["timeFieldName"] == "@timestamp"
        finally:
            _delete_data_view_quietly(kibana_client, view_id)

        with pytest.raises(NotFoundError):
            kibana_client.data_views.get(view_id=view_id)

    def test_get_missing_data_view_raises_not_found(self, kibana_client):
        with pytest.raises(NotFoundError):
            kibana_client.data_views.get(
                view_id=f"{RESOURCE_PREFIX}-missing-{uuid.uuid4().hex[:8]}"
            )

    def test_update_fields_metadata(self, kibana_client, data_view):
        response = kibana_client.data_views.update_fields_metadata(
            view_id=data_view,
            fields={"category": {"customLabel": "Category label", "count": 3}},
        )
        assert response.meta.status == 200

        fetched = kibana_client.data_views.get(view_id=data_view)
        field_attrs = fetched["data_view"]["fieldAttrs"]
        assert field_attrs["category"]["customLabel"] == "Category label"
        assert field_attrs["category"]["count"] == 3


class TestRuntimeFieldIntegration:
    """Live tests for the runtime field lifecycle."""

    def test_runtime_field_lifecycle(self, kibana_client, data_view):
        field_name = "kbnpy_rt_field"

        created = kibana_client.data_views.create_runtime_field(
            view_id=data_view,
            name=field_name,
            runtime_field={"type": "keyword", "script": {"source": "emit('one')"}},
        )
        assert created["fields"][0]["name"] == field_name
        assert created["fields"][0]["runtimeField"]["type"] == "keyword"

        # POST create fails when the field already exists
        with pytest.raises(BadRequestError):
            kibana_client.data_views.create_runtime_field(
                view_id=data_view,
                name=field_name,
                runtime_field={"type": "keyword", "script": {"source": "emit('x')"}},
            )

        # PUT is an upsert and replaces the definition
        upserted = kibana_client.data_views.create_or_update_runtime_field(
            view_id=data_view,
            name=field_name,
            runtime_field={"type": "keyword", "script": {"source": "emit('two')"}},
        )
        assert (
            upserted["fields"][0]["runtimeField"]["script"]["source"] == "emit('two')"
        )

        # POST on the named endpoint updates the existing field
        updated = kibana_client.data_views.update_runtime_field(
            view_id=data_view,
            name=field_name,
            runtime_field={"script": {"source": "emit('three')"}},
        )
        assert (
            updated["fields"][0]["runtimeField"]["script"]["source"] == "emit('three')"
        )

        fetched = kibana_client.data_views.get_runtime_field(
            view_id=data_view, name=field_name
        )
        assert (
            fetched["fields"][0]["runtimeField"]["script"]["source"] == "emit('three')"
        )

        kibana_client.data_views.delete_runtime_field(
            view_id=data_view, name=field_name
        )
        with pytest.raises(NotFoundError):
            kibana_client.data_views.get_runtime_field(
                view_id=data_view, name=field_name
            )


class TestDefaultDataViewIntegration:
    """Live tests for the default data view; always restores the prior value."""

    def test_get_and_set_default(self, kibana_client, data_view):
        original = kibana_client.data_views.get_default()["data_view_id"]
        try:
            ack = kibana_client.data_views.set_default(
                data_view_id=data_view, force=True
            )
            assert ack["acknowledged"] is True

            current = kibana_client.data_views.get_default()
            assert current["data_view_id"] == data_view
        finally:
            # Restore the previous default ("" means it was unset)
            kibana_client.data_views.set_default(
                data_view_id=original or None, force=True
            )
        restored = kibana_client.data_views.get_default()["data_view_id"]
        assert restored == original


class TestSwapReferencesIntegration:
    """Live tests for swap_references and preview_swap_references."""

    def test_preview_and_swap_with_delete(self, kibana_client, es_index, data_view):
        from_view_id = f"{RESOURCE_PREFIX}-swapfrom-{uuid.uuid4().hex[:8]}"
        try:
            kibana_client.data_views.create(
                data_view={
                    "id": from_view_id,
                    "title": es_index,
                    "name": f"{RESOURCE_PREFIX} swap-from view",
                    # Distinct title not required; ids are what get swapped
                    "allowNoIndex": True,
                },
                override=True,
            )

            preview = kibana_client.data_views.preview_swap_references(
                from_id=from_view_id, to_id=data_view
            )
            assert preview["result"] == []

            swap = kibana_client.data_views.swap_references(
                from_id=from_view_id, to_id=data_view, delete=True
            )
            assert swap["result"] == []
            assert swap["deleteStatus"]["deletePerformed"] is True

            # The from-view was deleted because nothing referenced it anymore
            with pytest.raises(NotFoundError):
                kibana_client.data_views.get(view_id=from_view_id)
        finally:
            _delete_data_view_quietly(kibana_client, from_view_id)


class TestAsyncDataViewsIntegration:
    """Async round-trip against the live stack."""

    async def test_async_data_view_and_runtime_field_round_trip(self, es_index):
        client = create_test_async_kibana_client(auth_method="auto")
        view_id = f"{RESOURCE_PREFIX}-async-{uuid.uuid4().hex[:8]}"
        field_name = "kbnpy_async_rt"
        try:
            created = await client.data_views.create(
                data_view={
                    "id": view_id,
                    "title": es_index,
                    "name": f"{RESOURCE_PREFIX} async view",
                    "timeFieldName": "@timestamp",
                }
            )
            assert created["data_view"]["id"] == view_id

            fetched = await client.data_views.get(view_id=view_id)
            assert fetched["data_view"]["title"] == es_index

            listed = await client.data_views.get_all()
            assert view_id in [view["id"] for view in listed["data_view"]]

            await client.data_views.create_or_update_runtime_field(
                view_id=view_id,
                name=field_name,
                runtime_field={
                    "type": "keyword",
                    "script": {"source": "emit('async')"},
                },
            )
            rt = await client.data_views.get_runtime_field(
                view_id=view_id, name=field_name
            )
            assert rt["fields"][0]["runtimeField"]["script"]["source"] == (
                "emit('async')"
            )
            await client.data_views.delete_runtime_field(
                view_id=view_id, name=field_name
            )
        finally:
            try:
                await client.data_views.delete(view_id=view_id)
            except NotFoundError:
                pass
            await client.close()

        # Verify deletion (and default cleanup) with a fresh sync client
        sync_client = create_test_kibana_client(auth_method="auto")
        try:
            with pytest.raises(NotFoundError):
                sync_client.data_views.get(view_id=view_id)
            _delete_data_view_quietly(sync_client, view_id)
        finally:
            sync_client.close()
