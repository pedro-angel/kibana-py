# Cloud Development Environment

A [Claude Code cloud environment](https://code.claude.com/docs/en/cloud-environments) runs
maintenance work for this package on an Anthropic-hosted VM instead of a maintainer's laptop:
researching what a new Kibana release changed, checking the client against it, and making the
resulting fixes. It runs the full loop — the Elastic stack comes up in Docker inside the session,
so `tests/integration/` executes against a real Kibana rather than a mock.

This page is the environment's definition. It records exactly what to configure, why each
setting is needed, and what the platform will not do for you.

:::{warning}
**Status: partially verified.** Live sessions on 2026-08-20 established that the network
allowlist is enforced (an off-list host is refused with `403` at the proxy), that the
environment variables and resource ceilings match this page, that Docker starts cleanly once
`dockerd` is launched directly, and that image pulls need `docker-auth.elastic.co` on the
allowlist. Not yet demonstrated: that the stack reaches `kibana=available` on 4 vCPUs, and that
`tests/integration/` passes against it. Treat those two as design until a session shows them.
:::

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
        hook["SessionStart hook<br/>starts dockerd"]
        up["./scripts/ci-stack-up.sh<br/>Elasticsearch + Kibana + APM"]
        work["Research, edits, pytest, PR"]
        clone --> hook --> up --> work
    end
    snap -.->|"images already on disk"| up
```

The practical consequence: image pulls are paid once, stack bring-up is paid every session — and
so is starting the Docker daemon itself, which is why `.claude/settings.json` carries a
`SessionStart` hook that runs `scripts/cloud-session-start.sh`.

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
*.elastic.co
*.frame.claudeusercontent.com
```

The wildcard is a finding, not a preference. A live session configured with the five Elastic
hosts named individually could not pull a single image: `docker.elastic.co` answers a pull with
`401` and a bearer challenge pointing at `docker-auth.elastic.co`, a *different* host that the
inventory did not name. The proxy refused the CONNECT, and every pull failed with
`failed to fetch anonymous token ... Forbidden` — while `docker.elastic.co` itself still probed
as perfectly reachable. An explicit list can only name the hosts you already know about, and a
registry's token service is precisely the kind you do not know about until it fails.

If least privilege is worth that maintenance cost, this is the corrected inventory:

```text
docker.elastic.co
docker-auth.elastic.co
epr.elastic.co
artifacts.elastic.co
geoip.elastic.co
www.elastic.co
*.frame.claudeusercontent.com
```

Why each one:

| Host | Needed for |
| :--- | :--- |
| `docker.elastic.co` | Every image in `elastic-start-local/docker-compose.yml`. The Trusted default allowlist carries Docker Hub, not Elastic, so without this entry no stack image can be pulled. |
| `docker-auth.elastic.co` | The registry's token service, and the entry an explicit list forgets. Blocking it fails every pull at authorization while leaving `docker.elastic.co` itself reachable, so the obvious probe reports green. |
| `epr.elastic.co` | The Elastic Package Registry. Kibana's Fleet plugin queries it, and `tests/integration/test_fleet_epm_integration.py` downloads a package zip from it directly. |
| `artifacts.elastic.co` | Fleet agent binary and artifact lookups. |
| `geoip.elastic.co` | Elasticsearch's GeoIP downloader. Blocking it is not fatal, only noisy in the logs. |
| `www.elastic.co` | The Kibana API reference and release notes that the compatibility research reads. |
| `*.frame.claudeusercontent.com` | Only if sessions should read Artifacts; Claude Code fetches artifact content from that host. |

Keeping the default package-manager list is what lets `pip install -e ".[dev,all]"` reach PyPI
and the bootstrap below reach `raw.githubusercontent.com`. It does not make Docker Hub usable:
the default list names `production.cloudflare.docker.com`, while Hub now serves blobs from
`production.cloudfront.docker.com`, which stays blocked. `docker run hello-world` therefore
fails here and is not a valid smoke test. The Elastic stack pulls nothing from Hub.

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

### Forcing a cache rebuild while iterating

The cache is keyed to the **pasted field**, not to what the fetched script contains. Editing
`scripts/cloud-setup.sh` and pushing therefore changes nothing: the field is byte-identical, the
snapshot is reused, and the next session runs the old script's results. Keep a revision marker in
the pasted bootstrap and bump it to force the rebuild:

```bash
#!/bin/bash
# rev: 1
curl -fsSL https://raw.githubusercontent.com/pedro-angel/kibana-py/main/scripts/cloud-setup.sh \
  -o /tmp/cloud-setup.sh && bash /tmp/cloud-setup.sh
```

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
2. `docker pull docker.elastic.co/apm/apm-server:9.5.1` — the authoritative registry probe, and
   the smallest image at about 80 MB. Nothing weaker will do: a `curl` against
   `https://docker.elastic.co/v2/` returns a healthy `401` even when pulls are impossible,
   because the failure happens one host later at the token service. Only a real pull exercises
   resolve, authorize, and blob fetch together.
3. `docker images | grep docker.elastic.co` — the cached images are on disk. Their **absence
   implicates nothing on its own**: if the daemon never started, no pull was ever attempted and
   the registry is simply untested. Step 1's log distinguishes the two cases; step 2 settles the
   registry independently.
4. `curl -sS -o /dev/null -w '%{http_code}\n' https://example.com` — expected to **fail**. A
   success means the environment is on Full network access, not the Custom list, and the
   allowlist proved nothing.
5. `ES_LOCAL_VERSION=9.5.1 ./scripts/ci-stack-up.sh` — exits zero, reports `kibana=available`.
6. `curl -s localhost:5601/api/status | jq -r '.status.overall.level'` — prints `available`.
7. `free -h && df -h /` — headroom under a running stack, against the 16 GB and 30 GB ceilings.
8. `pytest tests/integration/ -q` — the suite runs against the live server. Failures here are
   findings about the *client*, not about the environment; read them, do not fix them in the same
   pass.

The API-key auth tests need a key that `ci-stack-up.sh` mints only under GitHub Actions. Mint one
in the session before step 8, or record that those tests skipped and why:

```bash
export ES_LOCAL_API_KEY=$(curl -s -u elastic:kibana-py-es-dev \
  -XPOST localhost:9200/_security/api_key \
  -H 'Content-Type: application/json' -d '{"name":"kibana-py-cloud"}' | jq -r .encoded)
```

A step-2 failure naming `failed to fetch anonymous token` is a missing `docker-auth.elastic.co`
entry, not a missing `docker.elastic.co` one.

### The Docker daemon, and why nothing starts it

PID 1 on the session VM is a Firecracker init shim, not systemd — `/run/systemd/system` does not
exist. `service docker start` is therefore a silent no-op, and the daemon has to be launched
directly. Nothing about the sandbox prevents it: a live session showed root with every capability
but `cap_sys_resource`, and `dockerd` starting clean in half a second on `overlayfs` with bridge
networking intact.

Two places do this, because the daemon is needed at two different times and neither can cover the
other:

- `scripts/cloud-setup.sh`, at cache-build time, so it can pull images.
- `scripts/cloud-session-start.sh`, wired as a `SessionStart` hook in `.claude/settings.json`, on
  every session. The snapshot carries the images the setup script pulled but not the daemon that
  pulled them, so without this hook every session after the cache is built starts with no daemon
  and `ci-stack-up.sh` fails. The script exits immediately outside a cloud session, so local
  sessions are untouched.

If a daemon still refuses to start, both scripts leave its own error in
`/var/log/kibana-py-dockerd.log` rather than swallowing it. A permissions or cgroup error there
would mean the environment class cannot run nested containers — in which case live verification
moves to the `integration-probe` workflow, which a session can trigger with
`gh workflow run integration-probe.yml` and read back with `gh run download`.
