"""Pytest configuration for integration tests.

Loads elastic-start-local/.env variables into os.environ before test collection
so that skipif decorators and fixtures see the correct values.
"""

# Import examples.utils via importlib to avoid name collision with integration utils.
# Importing it triggers load_local_env() which injects elastic-start-local/.env into os.environ.
import base64
import importlib.util as _ilu
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_examples_utils_path = Path(__file__).parent.parent.parent / "examples" / "utils.py"
_spec = _ilu.spec_from_file_location("examples_utils", _examples_utils_path)
_examples_utils = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_examples_utils)


def flush_telemetry(timeout_ms: int = 5000) -> None:
    """Force-flush all active OTel providers (traces and logs).

    Use this instead of time.sleep() after generating spans or logs
    to ensure they are exported before assertions run.
    """
    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush(timeout_ms)
    except Exception:
        pass

    try:
        from opentelemetry._logs import get_logger_provider

        provider = get_logger_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush(timeout_ms)
    except Exception:
        pass


@pytest.fixture
def otel_endpoint():
    """Get OTLP exporter endpoint from environment."""
    return os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:8200")


@pytest.fixture
def otel_auth_token():
    """Get OTLP authentication token from environment."""
    return os.getenv("ELASTIC_APM_SECRET_TOKEN", "")


_ELSER_INFERENCE_ID = ".elser-2-elasticsearch"


@pytest.fixture
def elser_ready():
    """Skip the test when the ELSER-2 model cannot run inference on this stack.

    On a memory-constrained Elasticsearch the pytorch inference process crashes
    (``inference_exception: Exception when running inference id
    [.elser-2-elasticsearch]``), so ELSER-dependent tests fail deterministically on
    hardware that simply cannot host the model. Probe the inference endpoint once
    and ``pytest.skip`` on failure -- the same "skip when the dependency isn't
    available" posture the suite already uses for a missing Kibana. See #28.

    The skip reason carries the real error (status + body), so an unexpected cause
    (wrong path, auth) is visible in the report rather than silently disabling the
    test everywhere. #28
    """
    es_url = os.getenv("ES_URL") or os.getenv("ES_LOCAL_URL", "http://localhost:9200")
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("ES_LOCAL_API_KEY") or os.getenv("KIBANA_API_KEY")
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"
    else:
        user = os.getenv("KIBANA_USERNAME", "elastic")
        password = os.getenv("ES_LOCAL_PASSWORD") or os.getenv("KIBANA_PASSWORD", "")
        creds = base64.b64encode(f"{user}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {creds}"
    request = urllib.request.Request(
        f"{es_url}/_inference/sparse_embedding/{_ELSER_INFERENCE_ID}",
        method="POST",
        data=json.dumps({"input": "kibana-py elser readiness probe"}).encode(),
        headers=headers,
    )
    try:
        # First inference may load/allocate the model, so allow generous time; a
        # stack that cannot host ELSER fails fast or stalls -> skip either way.
        with urllib.request.urlopen(request, timeout=90) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        pytest.skip(
            f"ELSER-2 inference unavailable on this stack (HTTP {exc.code}): "
            f"{detail[:300]}"
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        pytest.skip(f"ELSER-2 inference probe failed/timed out on this stack: {exc}")
