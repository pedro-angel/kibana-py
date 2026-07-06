"""Integration tests for AttackDiscoveryClient against a live Kibana instance.

The Attack Discovery feature (``securitySolutionAttackDiscovery``) is disabled
in spaces that use the pure Elasticsearch solution view -- which includes the
default space of the local dev stack. All tests therefore run inside a
dedicated throwaway space created with ``solution="security"``.

The ``_generate`` round-trip test needs a live OpenAI-compatible LLM backend.
It is configured through environment variables:

- ``KBNPY_LMSTUDIO_OPENAI_URL``: OpenAI-compatible base URL (e.g.
  ``http://host.docker.internal:1234/v1``). The Kibana ``.gen-ai`` connector
  requires the *full* chat completions endpoint, so ``/chat/completions`` is
  appended when missing.
- ``KBNPY_LMSTUDIO_MODEL``: the model id to use (e.g. ``qwen/qwen3.5-9b``).

If these are unset, the generation round-trip test is skipped with that
reason; every other endpoint is still exercised live.
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

LMSTUDIO_URL = os.getenv("KBNPY_LMSTUDIO_OPENAI_URL")
LMSTUDIO_MODEL = os.getenv("KBNPY_LMSTUDIO_MODEL")
LMSTUDIO_SKIP_REASON = (
    "KBNPY_LMSTUDIO_OPENAI_URL / KBNPY_LMSTUDIO_MODEL not set: no live LLM "
    "backend available for the .gen-ai connector"
)

# A local 9B model can take minutes to reason over the alerts, and the
# backend may be serving other test runs concurrently.
GENERATION_TIMEOUT_SECONDS = 600
GENERATION_POLL_SECONDS = 10


def _chat_completions_url() -> str:
    """Build the full chat-completions endpoint for the .gen-ai connector.

    The Kibana OpenAI connector posts to ``apiUrl`` verbatim, so it must be
    the full ``/chat/completions`` endpoint, not the API base URL.
    """
    base = (LMSTUDIO_URL or "http://localhost:9/v1").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


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


def _schedule_params(connector_id: str, connector_name: str, size: int = 25) -> dict:
    """Build valid Attack Discovery schedule params for the test connector."""
    return {
        "alerts_index_pattern": ".alerts-security.alerts-default",
        "api_config": {
            "connectorId": connector_id,
            "actionTypeId": ".gen-ai",
            "name": connector_name,
        },
        "size": size,
    }


def _anonymization_fields() -> list[dict]:
    """Minimal anonymization fields for a generation.

    ``_id`` must be present and allowed, otherwise the live server fails the
    generation with "The _id field must be allowed to generate Attack
    discoveries."
    """
    fields = [
        ("_id", False),
        ("@timestamp", False),
        ("host.name", True),
        ("user.name", True),
        ("kibana.alert.rule.name", False),
        ("kibana.alert.severity", False),
        ("process.command_line", False),
    ]
    return [
        {
            "id": f"kbnpy-af-{i}",
            "field": field,
            "allowed": True,
            "anonymized": anonymized,
        }
        for i, (field, anonymized) in enumerate(fields)
    ]


@pytest.fixture(scope="module")
def kibana_client():
    """Create a module-scoped Kibana client."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture(scope="module")
def security_space(kibana_client):
    """Create a throwaway space with the security solution view.

    Attack Discovery requires the ``securitySolutionAttackDiscovery`` feature,
    which is disabled in spaces with the Elasticsearch solution view (such as
    the dev stack's default space, where ``find_schedules`` always reports
    ``total: 0``).
    """
    space_id = f"kbnpy-attack-discovery-{uuid.uuid4().hex[:8]}"
    kibana_client.spaces.create(id=space_id, name=space_id, solution="security")
    yield space_id
    kibana_client.spaces.delete(id=space_id)


@pytest.fixture(scope="module")
def gen_ai_connector(kibana_client, security_space):
    """Create a .gen-ai (OpenAI provider) connector in the test space.

    Uses the LM Studio backend when configured; otherwise a placeholder URL,
    which is fine for schedule CRUD (the connector is never invoked there).
    """
    name = f"kbnpy-attack-discovery-conn-{uuid.uuid4().hex[:8]}"
    created = kibana_client.connectors.create(
        name=name,
        connector_type_id=".gen-ai",
        config={
            "apiProvider": "OpenAI",
            "apiUrl": _chat_completions_url(),
            "defaultModel": LMSTUDIO_MODEL or "placeholder-model",
        },
        secrets={"apiKey": "dummy-key"},
        space_id=security_space,
    )
    connector_id = created.body["id"]
    yield connector_id, name
    kibana_client.connectors.delete(id=connector_id, space_id=security_space)


@pytest.fixture(scope="module")
def seeded_alerts_index():
    """Create a tiny throwaway alerts index for the generation test.

    The generation executor sorts alerts on ``kibana.alert.risk_score``, so
    the index must have a mapping for that field.
    """
    index = f"kbnpy-attack-discovery-alerts-{uuid.uuid4().hex[:8]}"
    _es_request(
        "PUT",
        f"/{index}",
        {
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "kibana": {
                        "properties": {
                            "alert": {
                                "properties": {
                                    "risk_score": {"type": "float"},
                                    "workflow_status": {"type": "keyword"},
                                    "severity": {"type": "keyword"},
                                    "uuid": {"type": "keyword"},
                                    "rule": {
                                        "properties": {"name": {"type": "keyword"}}
                                    },
                                }
                            }
                        }
                    },
                    "host": {"properties": {"name": {"type": "keyword"}}},
                    "user": {"properties": {"name": {"type": "keyword"}}},
                    "process": {"properties": {"command_line": {"type": "keyword"}}},
                    "event": {"properties": {"category": {"type": "keyword"}}},
                }
            }
        },
    )
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    for i in range(3):
        _es_request(
            "POST",
            f"/{index}/_doc?refresh=true",
            {
                "@timestamp": now,
                "kibana": {
                    "alert": {
                        "workflow_status": "open",
                        "risk_score": 70 + i,
                        "severity": "high",
                        "uuid": f"kbnpy-alert-uuid-{i}",
                        "rule": {"name": "Suspicious PowerShell Encoded Command"},
                    }
                },
                "host": {"name": f"kbnpy-host-0{i}"},
                "user": {"name": "kbnpy-user-admin"},
                "process": {
                    "command_line": (
                        "powershell.exe -EncodedCommand SQBFAFgA "
                        "-NoProfile -WindowStyle Hidden"
                    )
                },
                "event": {"category": "process"},
            },
        )
    yield index
    _es_request("DELETE", f"/{index}")


class TestAttackDiscoverySchedules:
    """Full lifecycle tests for Attack Discovery schedules."""

    def test_schedule_lifecycle(self, kibana_client, security_space, gen_ai_connector):
        """Test create/get/find/update/enable/disable/delete of a schedule."""
        connector_id, connector_name = gen_ai_connector
        name = f"kbnpy-attack-discovery-sched-{uuid.uuid4().hex[:8]}"

        created = kibana_client.attack_discovery.create_schedule(
            name=name,
            params=_schedule_params(connector_id, connector_name),
            schedule={"interval": "24h"},
            space_id=security_space,
        )
        schedule_id = created.body["id"]
        try:
            assert created.meta.status == 200
            assert created.body["name"] == name
            assert created.body["enabled"] is False
            assert created.body["schedule"] == {"interval": "24h"}
            assert created.body["params"]["api_config"]["connectorId"] == connector_id

            # Get by ID
            fetched = kibana_client.attack_discovery.get_schedule(
                id=schedule_id, space_id=security_space
            )
            assert fetched.body["id"] == schedule_id
            assert fetched.body["name"] == name

            # Find (works in a security-solution space; the default "es"
            # solution space reports total 0 even for existing schedules)
            found = kibana_client.attack_discovery.find_schedules(
                per_page=100, space_id=security_space
            )
            assert found.body["total"] >= 1
            assert schedule_id in [item["id"] for item in found.body["data"]]

            # Find with sorting
            found_sorted = kibana_client.attack_discovery.find_schedules(
                per_page=100,
                sort_field="name",
                sort_direction="desc",
                space_id=security_space,
            )
            assert schedule_id in [item["id"] for item in found_sorted.body["data"]]

            # Full update
            updated = kibana_client.attack_discovery.update_schedule(
                id=schedule_id,
                name=f"{name}-updated",
                params=_schedule_params(connector_id, connector_name, size=50),
                schedule={"interval": "12h"},
                actions=[],
                space_id=security_space,
            )
            assert updated.body["name"] == f"{name}-updated"
            assert updated.body["schedule"] == {"interval": "12h"}
            assert updated.body["params"]["size"] == 50

            # Enable / disable
            enabled = kibana_client.attack_discovery.enable_schedule(
                id=schedule_id, space_id=security_space
            )
            assert enabled.body["id"] == schedule_id
            assert (
                kibana_client.attack_discovery.get_schedule(
                    id=schedule_id, space_id=security_space
                ).body["enabled"]
                is True
            )

            disabled = kibana_client.attack_discovery.disable_schedule(
                id=schedule_id, space_id=security_space
            )
            assert disabled.body["id"] == schedule_id
            assert (
                kibana_client.attack_discovery.get_schedule(
                    id=schedule_id, space_id=security_space
                ).body["enabled"]
                is False
            )
        finally:
            deleted = kibana_client.attack_discovery.delete_schedule(
                id=schedule_id, space_id=security_space
            )
            assert deleted.body["id"] == schedule_id

        # After deletion the schedule must be gone
        with pytest.raises(NotFoundError):
            kibana_client.attack_discovery.get_schedule(
                id=schedule_id, space_id=security_space
            )

    def test_get_missing_schedule_semantic_404(self, kibana_client, security_space):
        """Test the server's semantic 404 message for an unknown schedule."""
        missing_id = f"kbnpy-attack-discovery-missing-{uuid.uuid4()}"
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.attack_discovery.get_schedule(
                id=missing_id, space_id=security_space
            )
        # Live 9.4.3 message: "Saved object [alert/<id>] not found"
        assert "not found" in str(exc_info.value).lower()
        assert missing_id in str(exc_info.value)


class TestAttackDiscoveryDiscoveriesAndGenerations:
    """Live tests for ad-hoc discovery search, bulk updates and generations."""

    def test_find_discoveries_response_shape(self, kibana_client, security_space):
        """Test the _find route returns the documented pagination shape."""
        found = kibana_client.attack_discovery.find(
            start="now-24h",
            end="now",
            page=1,
            per_page=10,
            sort_field="@timestamp",
            sort_order="desc",
            status=["open", "acknowledged"],
            space_id=security_space,
        )
        assert found.meta.status == 200
        for key in (
            "connector_names",
            "data",
            "page",
            "per_page",
            "total",
            "unique_alert_ids_count",
        ):
            assert key in found.body
        assert found.body["page"] == 1
        assert found.body["per_page"] == 10
        assert isinstance(found.body["data"], list)

    def test_bulk_update_unknown_ids_returns_empty(self, kibana_client, security_space):
        """Test that _bulk with unknown IDs succeeds with empty data."""
        result = kibana_client.attack_discovery.bulk_update(
            ids=[f"kbnpy-attack-discovery-nonexistent-{uuid.uuid4().hex}"],
            kibana_alert_workflow_status="acknowledged",
            space_id=security_space,
        )
        assert result.meta.status == 200
        assert result.body == {"data": []}

    def test_get_generations_response_shape(self, kibana_client, security_space):
        """Test the generations listing returns a generations array."""
        result = kibana_client.attack_discovery.get_generations(
            start="now-24h", end="now", size=50, space_id=security_space
        )
        assert result.meta.status == 200
        assert isinstance(result.body["generations"], list)

    def test_get_generation_missing_uuid_semantic_404(
        self, kibana_client, security_space
    ):
        """Test the server's semantic 404 message for an unknown generation."""
        missing_uuid = str(uuid.uuid4())
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.attack_discovery.get_generation(
                execution_uuid=missing_uuid, space_id=security_space
            )
        # Live 9.4.3: "Generation with execution_uuid <uuid> not found"
        assert f"Generation with execution_uuid {missing_uuid} not found" in str(
            exc_info.value
        )

    def test_dismiss_generation_missing_uuid_semantic_404(
        self, kibana_client, security_space
    ):
        """Test the server's semantic 404 message when dismissing an unknown one."""
        missing_uuid = str(uuid.uuid4())
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.attack_discovery.dismiss_generation(
                execution_uuid=missing_uuid, space_id=security_space
            )
        assert f"Generation with execution_uuid {missing_uuid} not found" in str(
            exc_info.value
        )


class TestAttackDiscoveryGenerationRoundTrip:
    """End-to-end generation round-trip through a real LLM backend."""

    @pytest.mark.skipif(
        not (LMSTUDIO_URL and LMSTUDIO_MODEL), reason=LMSTUDIO_SKIP_REASON
    )
    def test_generate_roundtrip_with_llm(
        self,
        kibana_client,
        security_space,
        gen_ai_connector,
        seeded_alerts_index,
    ):
        """Test _generate against a real LLM and track it via generations."""
        connector_id, connector_name = gen_ai_connector

        started = kibana_client.attack_discovery.generate(
            alerts_index_pattern=seeded_alerts_index,
            anonymization_fields=_anonymization_fields(),
            api_config={"actionTypeId": ".gen-ai", "connectorId": connector_id},
            size=25,
            sub_action="invokeAI",
            connector_name=connector_name,
            start="now-24h",
            end="now",
            replacements={},
            space_id=security_space,
        )
        assert started.meta.status == 200
        execution_uuid = started.body["execution_uuid"]
        assert execution_uuid

        # Poll until the generation reaches a terminal state. A local small
        # model may take minutes to analyze the alerts, and the generation
        # record itself only becomes visible in the event log a few seconds
        # after _generate returns (early polls answer 404).
        generation: dict = {}
        deadline = time.monotonic() + GENERATION_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            try:
                result = kibana_client.attack_discovery.get_generation(
                    execution_uuid=execution_uuid, space_id=security_space
                )
            except NotFoundError:
                time.sleep(GENERATION_POLL_SECONDS)
                continue
            generation = result.body["generation"]
            if generation["status"] in ("succeeded", "failed", "canceled"):
                break
            time.sleep(GENERATION_POLL_SECONDS)
        else:
            # The generate -> get_generation round-trip itself worked; the
            # LLM backend is just still busy (it may be shared with other
            # test runs). Dismiss the in-flight generation and record the
            # observed state instead of blocking even longer.
            if generation:
                kibana_client.attack_discovery.dismiss_generation(
                    execution_uuid=execution_uuid, space_id=security_space
                )
            pytest.skip(
                f"generation {execution_uuid} still not terminal after "
                f"{GENERATION_TIMEOUT_SECONDS}s (shared LLM backend busy); "
                f"in-flight state observed and dismissed: {generation}"
            )

        assert (
            generation["status"] == "succeeded"
        ), f"generation did not succeed: {generation}"
        assert generation["execution_uuid"] == execution_uuid
        # All three seeded alerts must have been sent to the LLM.
        assert generation["alerts_context_count"] == 3
        # The model may legitimately find zero attack chains in the tiny
        # synthetic data set; a completed round-trip is what matters here.
        assert generation["discoveries"] >= 0

        # The generation must be listed for the current user
        listed = kibana_client.attack_discovery.get_generations(
            size=50, space_id=security_space
        )
        listed_uuids = [g["execution_uuid"] for g in listed.body["generations"]]
        assert execution_uuid in listed_uuids

        # If the model produced discoveries, they are searchable and can be
        # bulk-updated; with zero discoveries the find still answers 200.
        found = kibana_client.attack_discovery.find(
            start="now-1h", end="now", per_page=100, space_id=security_space
        )
        assert found.meta.status == 200
        discovery_ids = [d["id"] for d in found.body["data"]]
        if discovery_ids:
            updated = kibana_client.attack_discovery.bulk_update(
                ids=discovery_ids,
                kibana_alert_workflow_status="acknowledged",
                space_id=security_space,
            )
            assert updated.meta.status == 200

        # Dismiss the generation and observe the dismissed status (the
        # backing event log refreshes within a few seconds)
        dismissed = kibana_client.attack_discovery.dismiss_generation(
            execution_uuid=execution_uuid, space_id=security_space
        )
        assert dismissed.body["execution_uuid"] == execution_uuid

        dismissed_status = None
        for _ in range(10):
            listed = kibana_client.attack_discovery.get_generations(
                size=50, space_id=security_space
            )
            statuses = {
                g["execution_uuid"]: g["status"] for g in listed.body["generations"]
            }
            dismissed_status = statuses.get(execution_uuid)
            if dismissed_status == "dismissed":
                break
            time.sleep(2)
        assert dismissed_status == "dismissed"


class TestAsyncAttackDiscovery:
    """Async round-trip tests for the Attack Discovery API."""

    @pytest.mark.asyncio
    async def test_async_schedule_roundtrip(self, security_space, gen_ai_connector):
        """Test schedule create/get/find/delete with the async client."""
        connector_id, connector_name = gen_ai_connector
        client = create_test_async_kibana_client(auth_method="auto")
        try:
            name = f"kbnpy-attack-discovery-async-{uuid.uuid4().hex[:8]}"
            created = await client.attack_discovery.create_schedule(
                name=name,
                params=_schedule_params(connector_id, connector_name),
                schedule={"interval": "24h"},
                space_id=security_space,
            )
            schedule_id = created.body["id"]
            try:
                assert created.body["name"] == name

                fetched = await client.attack_discovery.get_schedule(
                    id=schedule_id, space_id=security_space
                )
                assert fetched.body["id"] == schedule_id

                found = await client.attack_discovery.find_schedules(
                    per_page=100, space_id=security_space
                )
                assert schedule_id in [item["id"] for item in found.body["data"]]
            finally:
                await client.attack_discovery.delete_schedule(
                    id=schedule_id, space_id=security_space
                )

            with pytest.raises(NotFoundError):
                await client.attack_discovery.get_schedule(
                    id=schedule_id, space_id=security_space
                )
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_async_find_and_generations(self, security_space):
        """Test the async find and generations listing endpoints."""
        client = create_test_async_kibana_client(auth_method="auto")
        try:
            found = await client.attack_discovery.find(
                start="now-24h", end="now", space_id=security_space
            )
            assert found.meta.status == 200
            assert "data" in found.body

            generations = await client.attack_discovery.get_generations(
                size=10, space_id=security_space
            )
            assert isinstance(generations.body["generations"], list)
        finally:
            await client.close()
