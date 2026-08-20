# Cloud Development Environment

A [Claude Code cloud environment](https://code.claude.com/docs/en/cloud-environments) runs
maintenance work for this package on an Anthropic-hosted VM instead of a maintainer's laptop:
researching what a new Kibana release changed, checking the client against it, and making the
resulting fixes. It runs the full loop — the Elastic stack comes up in Docker inside the session,
so `tests/integration/` executes against a real Kibana rather than a mock.

This page is the environment's definition. It records exactly what to configure, why each
setting is needed, and what the platform will not do for you.

## What a session can and cannot keep

The setup script runs once per cache generation and the filesystem is snapshotted after it.
Anything on disk survives into later sessions; anything merely *running* does not.

```{mermaid}
flowchart TB
    subgraph cache["Environment cache — built once, reused (~7 days)"]
        setup["scripts/cloud-setup.sh<br/>installs gh, pulls stack images"]
        snap[("Filesystem snapshot<br/>apt packages + Docker images")]
        setup --> snap
    end
    subgraph session["Every session — rebuilt from scratch"]
        clone["Fresh clone of kibana-py"]
        up["./scripts/ci-stack-up.sh<br/>Elasticsearch + Kibana + APM"]
        work["Research, edits, pytest, PR"]
        clone --> up --> work
    end
    snap -.->|"images already on disk"| up
```

The practical consequence: image pulls are paid once, stack bring-up is paid every session.

## Prerequisites

- Claude Code on the web, which needs a Pro, Max, Team, or Enterprise plan with the relevant
  seat. See [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web).
- GitHub access to this repository from your Claude account, through either the Claude GitHub
  App or `/web-setup` in a local terminal. Cloud sessions clone through a proxy that keeps your
  real credential outside the VM.

## Create the environment

Environments are created from the environment selector at `claude.ai/code` — the cloud icon in
the row above the message box. There is no settings page and no URL for it. Select **Add cloud
environment** and fill in the four fields below.

### Name

```text
kibana-py
```

### Network access

Select **Custom**, check **Also include default list of common package managers**, and list:

```text
docker.elastic.co
epr.elastic.co
artifacts.elastic.co
geoip.elastic.co
www.elastic.co
*.frame.claudeusercontent.com
```

Why each one:

| Host | Needed for |
| :--- | :--- |
| `docker.elastic.co` | Every image in `elastic-start-local/docker-compose.yml`. **This is the one that makes or breaks the environment** — the Trusted default allowlist carries Docker Hub, not Elastic, so without this entry no stack image can be pulled. |
| `epr.elastic.co` | The Elastic Package Registry. Kibana's Fleet plugin queries it, and `tests/integration/test_fleet_epm_integration.py` downloads a package zip from it directly. |
| `artifacts.elastic.co` | Fleet agent binary and artifact lookups. |
| `geoip.elastic.co` | Elasticsearch's GeoIP downloader. Blocking it is not fatal, only noisy in the logs. |
| `www.elastic.co` | The Kibana API reference and release notes that the compatibility research reads. |
| `*.frame.claudeusercontent.com` | Only if sessions should read Artifacts; Claude Code fetches artifact content from that host. |

A single `*.elastic.co` line covers the five Elastic hosts if you prefer brevity to an explicit
inventory. Keeping the default package-manager list is what lets `pip install -e ".[dev,all]"`
reach PyPI and the bootstrap below reach `raw.githubusercontent.com`.

### Environment variables

```text
KIBANA_PY_STACK_VERSIONS=9.5.1 9.4.3
KIBANA_PY_PULL_BUDGET=210
```

The leftmost version gets first claim on the pull budget, so put the version you are actively
working against first. Caching two versions is what makes an A/B run possible: the same
integration selection can be executed against both and the results diffed.

Cloud environments have **no secrets store** and every variable is readable by anyone using the
environment. Do not put a token here. In particular, leave `GH_TOKEN` unset — the GitHub proxy
injects credentials on outbound requests, and `gh` works without one.

### Setup script

```bash
#!/bin/bash
curl -fsSL https://raw.githubusercontent.com/pedro-angel/kibana-py/main/scripts/cloud-setup.sh \
  -o /tmp/cloud-setup.sh && bash /tmp/cloud-setup.sh
```

The real script is `scripts/cloud-setup.sh` in this repository, so it is reviewed and versioned
like any other change rather than living only in a dialog box. It installs `gh` and pre-pulls the stack images for each version in
`KIBANA_PY_STACK_VERSIONS`.

Two platform constraints shape that script, and any edit to it must respect them:

- **It must exit zero.** A non-zero exit fails session start, so every step is fail-open — a
  step that cannot run logs why and is skipped.
- **It must finish in roughly five minutes.** Overrunning means no snapshot is built and every
  session re-pulls from scratch. Pulls therefore run against a wall-clock deadline
  (`KIBANA_PY_PULL_BUDGET`) and stop when it expires. Completed layers still cache; whatever was
  missed is pulled on demand inside the session.

## Working in a session

You do not get a shell on the VM. Claude runs every command, so the workflows below are things
you ask for.

### Bring the stack up

```bash
./scripts/ci-stack-up.sh                      # the version pinned in .env.example
ES_LOCAL_VERSION=9.5.1 ./scripts/ci-stack-up.sh   # any other cached version
```

This is the same script the `integration-probe` workflow and the release integration gate call,
so a cloud session and CI provision identically. An `ES_LOCAL_VERSION` already in the
environment overrides the template's pin without editing a tracked file.

### Run the integration suite

```bash
KIBANA_URL=http://localhost:5601 \
KIBANA_USERNAME=elastic \
KIBANA_PASSWORD=kibana-py-es-dev \
  pytest tests/integration/ -q
```

### Compare two stack versions

Bring up one version, run the selection, tear down, bring up the other, run the same selection,
and diff the two JUnit reports. This is the mechanism behind statements like "endpoint X changed
its response envelope in 9.5" — a measured difference rather than a reading of the release notes.

## Limits worth knowing before you rely on it

- **Resources**: approximately 4 vCPUs, 16 GB RAM, 30 GB disk. The stack fits comfortably —
  Elasticsearch takes a 2 GB heap under `ES_LOCAL_JAVA_OPTS` — and this is the same class of
  machine the `integration-probe` workflow already targets on a GitHub runner. Two cached
  version sets consume roughly a third of the disk.
- **Cache lifetime**: the snapshot is rebuilt when the setup script or the allowed-domain list
  changes, and after about seven days. The first session after a rebuild pays the pull cost.
- **Session expiry**: idle sessions are reclaimed. Reopening one provisions a fresh VM with the
  conversation history restored but no running stack.
- **Push scope**: the GitHub proxy permits `git push` only to the session's current working
  branch, and rejects GraphQL operations outside a pinned set for pull-request workflows. Use
  `gh api repos/{owner}/{repo}/...` where a GraphQL-only API would otherwise be needed.
- **Architecture**: sessions are x86_64 Ubuntu 24.04 regardless of your own machine. Results
  from an aarch64 laptop are not a substitute for a run here, and vice versa.

## Verify the environment before trusting it

Run this in the first session of a new environment, and again whenever the setup script or the
allowed-domain list changes — both rebuild the cache. Each step produces an observation, not an
assurance, and the run is captured as an evidence file under `docs/evidence/` like any other
live validation in this repository.

1. `cat /var/log/kibana-py-cloud-setup.log` — the setup script's own transcript, carried in the
   snapshot: which images it cached, what the deadline clipped, and how long it took. This is the
   only place the budget claim can be checked; the script's stdout is gone by session time.
2. `docker images | grep docker.elastic.co` — the cached images are on disk, which proves the
   allowlist and the setup script both worked.
3. `curl -sS -o /dev/null -w '%{http_code}\n' https://example.com` — expected to **fail**. A
   success means the environment is on Full network access, not the Custom list, and the
   allowlist proved nothing.
4. `ES_LOCAL_VERSION=9.5.1 ./scripts/ci-stack-up.sh` — exits zero, reports `kibana=available`.
5. `curl -s localhost:5601/api/status | jq -r '.status.overall.level'` — prints `available`.
6. `free -h && df -h /` — headroom under a running stack, against the 16 GB and 30 GB ceilings.
7. `pytest tests/integration/ -q` — the suite runs against the live server. Failures here are
   findings about the *client*, not about the environment; read them, do not fix them in the same
   pass.

The API-key auth tests need a key that `ci-stack-up.sh` mints only under GitHub Actions. Mint one
in the session before step 7, or record that those tests skipped and why:

```bash
export ES_LOCAL_API_KEY=$(curl -s -u elastic:kibana-py-es-dev \
  -XPOST localhost:9200/_security/api_key \
  -H 'Content-Type: application/json' -d '{"name":"kibana-py-cloud"}' | jq -r .encoded)
```

A failure at step 2 is almost always a missing `docker.elastic.co` entry in the allowed domains.
