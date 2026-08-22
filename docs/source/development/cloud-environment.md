# Cloud Development Environment

A [Claude Code cloud environment](https://code.claude.com/docs/en/cloud-environments) runs
maintenance work for this package on an Anthropic-hosted VM instead of a maintainer's laptop:
researching what a new Kibana release changed, checking the client against it, and making the
resulting fixes. It runs the full loop — the Elastic stack comes up in Docker inside the session,
so `tests/integration/` executes against a real Kibana rather than a mock.

This page is the environment's definition. It records exactly what to configure, why each
setting is needed, and what the platform will not do for you.

:::{note}
**Status: verified end to end.** A live session on 2026-08-20 ran the verification list below on
both pinned stack versions and captured the result in
`docs/evidence/cloud-environment-battle-test.md`. Established: the network allowlist is enforced
(an off-list host is refused with `403` at the proxy); the environment variables and resource
ceilings match this page, with the disk figure corrected below; Docker starts cleanly once
`dockerd` is launched directly; image pulls need `docker-auth.elastic.co`; **the stack reaches
`kibana=available` on 4 vCPUs** (70s on 9.5.1, 66s on 9.4.3, from cached images); and
**`tests/integration/` runs to completion against it** — 751 tests collected on each version.

The suite does not come out green, and is not expected to: its failures are compatibility
findings about the client plus the CA-trust constraint below, not environment faults. Two
constraints that run surfaced are documented below: `memlock: -1` cannot be granted here (see
"The Docker daemon"), and the stack containers do not trust the agent proxy's CA.
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

#### If sessions build the docs

`make docs` runs Sphinx `linkcheck`, which resolves every external link in
`docs/source/`. Those hosts have nothing to do with the stack, so add them only if you
intend to run the docs build in a session:

```text
cli.github.com
docs.pytest.org
docs.pypi.org
docs.readthedocs.com
www.jaegertracing.io
```

| Host | Needed for |
| :--- | :--- |
| `cli.github.com` | The `gh` CLI link in the release process page. |
| `docs.pytest.org` | The pytest link in the contributing page. |
| `docs.pypi.org` | The trusted-publishing link in the release process page. **Listed for completeness — an entry for it does not take effect here**, see below. |
| `docs.readthedocs.com` | Where the release-process page's `docs.readthedocs.io` import-guide link actually lands. Allowing the `.io` host does **not** cover it — see below. |
| `www.jaegertracing.io` | A tracing-backend link in the observability user guide. |

**The allowlist applies to the redirect target, and this is the `docker-auth.elastic.co`
lesson a second time.** The documentation links `docs.readthedocs.io`; that answers `302`
and the link resolves at `docs.readthedocs.com`. Allowing the host that appears in the
source — whether named outright or covered by a `*.readthedocs.io` wildcard — leaves the
link refused, because the host that gets refused is the one at the end of the redirect.

The failure says so, and it is worth reading the *host* in the error rather than the URL
in the message: `linkcheck` reported the `.io` URL as broken while naming
`host='docs.readthedocs.com'` as what it could not reach. Measured 2026-08-22:

```
$ curl -sSL -o /dev/null -w '%{url_effective}\n' \
    https://docs.readthedocs.io/en/stable/intro/import-guide.html
https://docs.readthedocs.com/platform/stable/intro/add-project.html
```

An explicit list can only name the hosts you already know about, and a redirect target is
another kind you do not know about until it fails. A denial is legible when you look for
it — the proxy says so in a header rather than failing obscurely:

```
HTTP/2 403
x-deny-reason: host_not_allowed
Host not in allowlist: docs.pypi.org. Add this host to your network egress settings.
```

#### What the allowlist cannot fix

Two `linkcheck` failures survive a correct allowlist, for different reasons.

**`docs.pypi.org` cannot be allowed.** An entry for it — bare or as `*.pypi.org` — is
accepted by the settings UI and has no effect; the host still answers `403` with
`x-deny-reason: host_not_allowed`. This is not a propagation delay: hosts added in the same
edit began answering immediately, and `blog.pypi.org` is refused with the wildcard in place
while `test.pypi.org` answers, which is what a built-in PyPI default would look like. The
proxy already special-cases `pypi.org` in its bypass list (`noProxy`), the likeliest cause.
Measured 2026-08-22:

| Host | Result |
| :--- | :--- |
| `pypi.org` | 200 — in the proxy's bypass list |
| `test.pypi.org` | 200 — a platform default, not your entry |
| `docs.pypi.org` | **403** `host_not_allowed` |
| `blog.pypi.org` | **403** `host_not_allowed` |

**The GitHub Discussions link is a different control entirely**, and widening the network
list will never clear it either. `docs/source/development/index.md` links the repository's GitHub
Discussions, and the session's **GitHub credential proxy** — a different control, the one
that keeps your real token outside the VM — refuses it:

```
$ curl -sS https://github.com/pedro-angel/kibana-py/discussions
{"message":"This GitHub API path is not available: sessions are bound to their configured
 repositories. Use repository-scoped endpoints (repos/{owner}/{repo}/...)."}
```

The link is genuinely valid — the repository has Discussions enabled (`has_discussions:
true` from the repository API) — so this is a sandbox artifact, not a broken link. The
refusal is narrow, and worth knowing precisely before assuming a whole class of URL is
unreachable. Measured against `github.com/pedro-angel/kibana-py`:

| Path | Result |
| :--- | :--- |
| `/`, `/tree/main`, `/blob/main/README.md` | 200 |
| `/issues`, `/pulls`, `/releases`, `/issues/new/choose` | 200 / 302 |
| `/discussions`, `/wiki` | **403** from the credential proxy |

Only those two segments are refused.

`docs/source/conf.py` therefore adds both cases — those two GitHub paths and
`docs.pypi.org` — to `linkcheck_ignore` **when, and only when, `CLAUDE_CODE_REMOTE` is
`true`** — the same variable `scripts/cloud-session-start.sh`
gates on. CI and a maintainer's machine check the links exactly as before, so the gate is not
weakened where it can run; it is relaxed only where it provably cannot. The build announces
the skip rather than applying it silently:

```
conf.py: CLAUDE_CODE_REMOTE=true -- linkcheck is skipping 2 pattern(s) this
environment's GitHub credential proxy refuses (see development/cloud-environment.md)
```

Verified in both directions on 2026-08-22: with the variable set, `linkcheck` reports **zero**
broken links; with it unset, the same build reports both. The `docs.pypi.org` link in
particular has never been observed to resolve *from here at all*, so the scoping is what
keeps the exemption honest — if that link is dead, CI is what will say so. If you add a documentation
link to a GitHub path in that set, expect it to be checked everywhere except here.

Keeping the default package-manager list is what lets `pip install -e ".[dev,all]"` reach PyPI
and the bootstrap below reach `raw.githubusercontent.com`. It does not make Docker Hub usable:
the default list names `production.cloudflare.docker.com`, while Hub now serves blobs from
`production.cloudfront.docker.com`, which stays blocked. `docker run hello-world` therefore
fails here and is not a valid smoke test. The Elastic stack pulls nothing from Hub.

### Environment variables

```text
KIBANA_PY_STACK_VERSIONS=9.5.2 9.4.5
KIBANA_PY_PULL_BUDGET=210
ES_LOCAL_MEMLOCK=8388608
```

These are the supported pins. They are declared once, in `kibana/_compat.py`, and only
mirrored here -- `make versions` fails if the two disagree, so this block cannot quietly
go stale. The policy behind the set, and the procedure for moving it forward, are in
{doc}`version-support`.

The leftmost version gets first claim on the pull budget, so put the version you are actively
working against first. Caching two versions is what makes an A/B run possible: the same
integration selection can be executed against both and the results diffed.

`ES_LOCAL_MEMLOCK` is what makes the stack startable here at all. The session VM drops
`CAP_SYS_RESOURCE` and pins the `RLIMIT_MEMLOCK` hard limit at 8 MiB, so the unlimited
`memlock: {soft: -1, hard: -1}` that `elastic-start-local/docker-compose.yml` inherits from the
upstream `start-local` template is refused by `runc` and every container dies during init, in
under a second. The compose file reads the limit as `${ES_LOCAL_MEMLOCK:--1}`, so setting this
variable to the VM's own hard limit caps the request to something grantable. It is safe to cap:
the compose file never sets `bootstrap.memory_lock=true`, so Elasticsearch never locks its heap.
The `-1` default is deliberate and keeps GitHub runners, which do grant `CAP_SYS_RESOURCE`,
unchanged.

It belongs **here and not in `elastic-start-local/.env.example`**. `ci-stack-up.sh` sources that
template into its own shell, so any value written there would overwrite the one inherited from
the environment — the same collision `ES_LOCAL_VERSION` has to work around by capturing its
override before the sourcing.

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

- **Resources**: 4 vCPUs and 15 GiB RAM, with **about 21 GiB of writable disk** — measured, not
  quoted: `df` reports a 252 G root filesystem, but writable space is a fixed per-session
  allowance and the "Size" column is not headroom. The stack fits comfortably — Elasticsearch
  takes a 2 GB heap under `ES_LOCAL_JAVA_OPTS`, and the three containers together peaked near
  4.4 GiB with 10 GiB still available mid-suite. Two cached version sets are about 10 GB of
  images, so budget roughly half the writable allowance for them. The suite is latency-bound
  rather than CPU-bound; 4 vCPUs are not the constraint.
- **Container egress is intercepted; VM egress is not.** The VM's own processes reach the
  internet through an explicit `CONNECT` proxy (`HTTPS_PROXY`) and are handed the origin's real
  certificate, so ordinary CA bundles validate. Containers cannot reach that proxy — it listens
  on the VM's loopback — so their traffic is transparently re-terminated by an egress gateway
  presenting `Anthropic — Egress Gateway SDS Issuing CA (production)`. Anything inside the stack
  therefore fails HTTPS with `self-signed certificate in certificate chain` / `PKIX path
  building failed`, even where the same URL returns `200` from the VM.

  Read the symptom carefully: a host the egress policy actually *rejects* fails with `403` on
  `CONNECT`, never with a certificate error. A certificate error means the host was allowed.

  **Kibana is fixed.** `elastic-start-local/docker-compose.proxy-ca.yml` mounts the CA and sets
  `NODE_EXTRA_CA_CERTS`; `ci-stack-up.sh` overlays it only when the CA file exists, so CI, where
  nothing intercepts egress, is unaffected. Override the path with `KIBANA_PY_PROXY_CA`. This
  clears every Fleet/EPM failure — verified on 9.5.1, where the 21 registry-blocked tests in
  `test_fleet_epm_integration.py`, `test_fleet_policies_integration.py` and
  `test_entity_analytics_integration.py` went from failing to **54 passed**.

  **Elasticsearch is not fixed**, deliberately. Its outbound calls (the
  `.elser-2-elasticsearch` inference path) still fail, because the JVM reads its own truststore
  rather than the OS one: a PEM is not enough, the CA has to be imported into the bundled JDK's
  `cacerts` with `keytool`, which means an init step inside the container. No integration test
  depends on that path, so the cost is not yet worth paying. If you need it, import the CA into
  `/usr/share/elasticsearch/jdk/lib/security/cacerts` (default password `changeit`) and mount
  the result, or point `ES_JAVA_OPTS` at a truststore you build yourself.
- **Cache lifetime**: the snapshot is rebuilt when the setup script or the allowed-domain list
  changes, and after about seven days. The first session after a rebuild pays the pull cost.
- **Session expiry**: idle sessions are reclaimed. Reopening one provisions a fresh VM with the
  conversation history restored but no running stack.
- **Push scope**: the GitHub proxy permits `git push` only to the session's current working
  branch, and rejects GraphQL operations outside a pinned set for pull-request workflows. Use
  `gh api repos/{owner}/{repo}/...` where a GraphQL-only API would otherwise be needed.
- **Architecture**: sessions are x86_64 Ubuntu 24.04 regardless of your own machine. Results
  from an aarch64 laptop are not a substitute for a run here, and vice versa.
- **No IPv6, at all.** The Firecracker kernel is built without it: there is no
  `/proc/sys/net/ipv6`, no `/proc/net/if_inet6`, and `socket(AF_INET6, …)` raises
  `OSError: [Errno 97] Address family not supported by protocol`. It cannot be switched on.
  One unit test needs a real IPv6 loopback listener
  (`test_validate_apm_connectivity_reaches_ipv6_only_listener`, the regression test for #83)
  and therefore skips here — which makes **`make dod` report `unit_green` NO-GO in this
  environment**, because the gate rejects any skip in the unit suite. That is the gate
  working: a unit test that skips has an environmental dependency. The test runs and passes
  wherever IPv6 loopback exists, including GitHub runners.
- **`make dod` also reports `docs_strict` NO-GO here**, and only the external-link pass is at
  fault — the strict HTML build (`sphinx-build -W`) passes. Most of it is the allowlist and is
  fixable by naming the hosts under *Network access* → *If sessions build the docs*: that took
  a measured run from six broken links to one. The one that remains is the GitHub Discussions
  link, refused by the credential proxy rather than the egress policy, which no network setting
  clears — see *What the allowlist cannot fix* in the same section.
  Read a `linkcheck` failure here as a question about the environment before assuming it is a
  question about the documentation.

  Both NO-GOs are properties of this sandbox, not of the repository, and both are visible in
  the gate's own per-criterion logs under `/tmp/dod-kibana-py/`. Neither can be cleared from
  inside a session; the corresponding CI jobs are where those two criteria actually certify.

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
7. `free -h && df -h /` — headroom under a running stack, against the ~15 GiB RAM and ~21 GiB
   writable-disk figures above. Sample it while the suite runs; idle numbers prove nothing.
8. `python3 -m pytest tests/integration/ -q` — the suite runs against the live server. Failures
   here are findings about the *client*, not about the environment; read them, do not fix them in
   the same pass.

Step 8 has two prerequisites this VM imposes, both of which fail the whole suite before a single
test runs:

- Install with `pip install -e ".[dev,all]" --ignore-installed`. Without the flag pip aborts
  trying to uninstall Debian's distribution-managed `packaging` 24.0.
- Invoke pytest as `python3 -m pytest`, not `pytest`. The `pytest` on `PATH` is a uv-isolated
  shim that cannot import the package under test.

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
directly. Nothing about the sandbox prevents the daemon itself: a live session showed `dockerd`
starting clean in half a second on `overlayfs` with bridge networking intact.

The one capability root does *not* have is `cap_sys_resource`, and that has a concrete
consequence worth knowing before you hit it. The hard `RLIMIT_MEMLOCK` is pinned at 8 MiB, while
`elastic-start-local/docker-compose.yml` asks Elasticsearch for `memlock: {soft: -1, hard: -1}`.
Raising it needs the dropped capability, so `ci-stack-up.sh` dies in under a second with a
message that names neither memlock nor the capability:

```
runc create failed: unable to start container process: error during container init:
error setting rlimits for ready process: error setting rlimit type 8: operation not permitted
```

`rlimit type 8` is `RLIMIT_MEMLOCK`. Cap the value to the VM's hard limit to get past it —
Elasticsearch never locks its heap here anyway, because the compose file does not set
`bootstrap.memory_lock=true`, so the unlimited request is unused. Do not hard-code 8 MiB in the
tracked file: GitHub runners do grant `CAP_SYS_RESOURCE`, where `-1` is correct.

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
