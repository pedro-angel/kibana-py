# Evidence — `release.yml` hardening (#82)

**Date:** 2026-08-01
**Change under test:** three release.yml hardening items filed by the 2026-07-31
adversarial deep review (release-hygiene lens): (1) `publish-pypi` needs `integration`
directly, not just transitively; (2) PyPI publishes *before* the GitHub Release; (3) the
`pypa/gh-action-pypi-publish` pin comment names the immutable tag instead of a moving
branch.
**Base commit:** `9561fb9` (branch `fix/release-hardening-82`, branched from `main`).
**Runner:** local macOS (darwin/arm64), the same machine driving this fix — no CI run
involved for these gates (see the honest residual at the bottom for what a local run
cannot cover).

## 1. Decision 2's precondition: verify no artifact coupling before reordering

Before swapping `publish-pypi` and `publish-github-release`, checked whether either job
consumes the *other's* outputs (as opposed to both independently consuming `build`'s
`dist` artifact). Read `.github/workflows/release.yml` pre-change:

- `publish-github-release` steps: `actions/download-artifact` (name: `dist`, from
  `build`) → `softprops/action-gh-release` (`files: dist/*`). No reference to
  `publish-pypi` anywhere.
- `publish-pypi` steps: `actions/download-artifact` (name: `dist`, from `build`) → `rm -f
  dist/*.json` → `pypa/gh-action-pypi-publish`. No reference to `publish-github-release`
  outputs, job outputs, or artifacts anywhere.

Both jobs download their **own** copy of the same `dist` artifact uploaded once by
`build`; artifact downloads don't share a filesystem across jobs/runners, so one job's
`rm -f dist/*.json` cannot affect the other's copy either. **No coupling found** — the
reorder in decision 2 was safe to make as specified. (Not a BLOCKED condition; recorded
here because the task required verifying it explicitly before proceeding.)

## 2. SHA→tag resolution for the `pypa/gh-action-pypi-publish` pin (decision 3)

Pinned SHA in `release.yml` before this change: `ba38be9e461d3875417946c167d0b5f3d385a247`,
commented `# release/v1` (a branch). Resolved independently via the GitHub API — not
trusted from Dependabot metadata:

```
$ gh api repos/pypa/gh-action-pypi-publish/commits/ba38be9e461d3875417946c167d0b5f3d385a247 --jq '{sha, comment: .commit.message}'
{"comment":"Merge pull request #408 from adisivaprasad/bump-setup-python-v6\n\nBump actions/setup-python from v5.6.0 to v6.2.0 (Node 20 → Node 24)","sha":"ba38be9e461d3875417946c167d0b5f3d385a247"}

$ gh api repos/pypa/gh-action-pypi-publish/tags --paginate --jq '.[] | select(.commit.sha=="ba38be9e461d3875417946c167d0b5f3d385a247") | .name'
v1.14.1

$ gh api repos/pypa/gh-action-pypi-publish/git/refs/tags/v1.14.1
{"ref":"refs/tags/v1.14.1","node_id":"...","url":"...","object":{"sha":"2834a314042ef964da07689278dd1e9d773e8afd","type":"tag","url":"..."}}
```

`v1.14.1` is an **annotated** tag (the ref object type is `tag`, not `commit`), so it must
be peeled one level further — resolved that tag object to the commit it actually points at:

```
$ gh api repos/pypa/gh-action-pypi-publish/git/tags/2834a314042ef964da07689278dd1e9d773e8afd --jq '{tag, object}'
{"tag":"v1.14.1","object":{"sha":"ba38be9e461d3875417946c167d0b5f3d385a247","type":"commit","url":"..."}}
```

**Result: the pinned SHA peels to exactly `v1.14.1` — matches what Dependabot metadata
claimed, and matches the target the task named as the expected default.** No divergence
to report; the pin comment was changed from `# release/v1` to `# v1.14.1` (the SHA
itself is unchanged — only the human-readable comment moved from a moving branch to the
immutable tag it happened to be at).

Also confirmed the branch has since moved past this commit (expected — branches move,
which is exactly why the old comment couldn't be verified strictly):

```
$ gh api repos/pypa/gh-action-pypi-publish/git/refs/heads/release/v1
{"ref":"refs/heads/release/v1","object":{"sha":"dc37677b2e1c63e2034f94d8a5b11f265b73ba33","type":"commit"}}
```
(`dc37677b...` ≠ the pinned `ba38be9e...` — the branch has advanced to a newer commit,
which the old `# release/v1` comment could never flag as stale.)

## 3. Decision 2's rationale: the 0.1.x-era incident, verified against real CI history

The task required stating the *actual* state the repo hit in the 0.1.x era, not an
assumed one. Checked GitHub Releases currently live vs. tags that were once tagged:

```
$ git tag -l "v0.1.*"
v0.1.0
v0.1.1
v0.1.9

$ gh release list --limit 30
v0.4.2  Latest  v0.4.2  2026-07-15T21:16:40Z
v0.4.1          v0.4.1  2026-07-12T22:12:25Z
v0.4.0          v0.4.0  2026-07-11T12:16:01Z
v0.3.1          v0.3.1  2026-07-08T12:56:46Z
v0.1.9          v0.1.9  2026-04-04T22:06:49Z
v0.1.1          v0.1.1  2026-04-04T11:21:23Z
v0.1.0          v0.1.0  2026-04-04T11:14:05Z
```

Only `v0.1.0`, `v0.1.1`, `v0.1.9` have releases today, yet commit history shows version
bumps for `v0.1.2` through `v0.1.8` on 2026-04-04. Checked the actual `release.yml` CI
runs for those tags:

```
$ gh run list --workflow=release.yml --limit 50 --json databaseId,displayTitle,status,conclusion,createdAt,headBranch
```
| Run ID | Tag | Conclusion |
|---|---|---|
| 23984507706 | v0.1.3 | failure |
| 23986462600 | v0.1.4 | failure |
| 23986812115 | v0.1.5 | failure |
| 23987828382 | v0.1.6 | failure |
| 23988018813 | v0.1.7 | failure |
| 23988284507 | v0.1.8 | failure |
| 23988568093 | v0.1.9 | success |

Per-job breakdown for each failing run (`gh run view <id> --json jobs -q '.jobs[] |
{name, conclusion}'`), all six were the **identical pattern**:

```
=== run 23984507706 (v0.1.3) ===
{"conclusion":"success","name":"Validate release tag and changelog"}
{"conclusion":"failure","name":"Publish to PyPI"}
{"conclusion":"success","name":"Publish GitHub Release"}
{"conclusion":"success","name":"Build distribution"}

=== run 23986462600 (v0.1.4) ===
{"conclusion":"success","name":"Validate release tag and changelog"}
{"conclusion":"success","name":"Build distribution"}
{"conclusion":"success","name":"Publish GitHub Release"}
{"conclusion":"failure","name":"Publish to PyPI"}

=== run 23986812115 (v0.1.5) ===
{"conclusion":"success","name":"Validate release tag and changelog"}
{"conclusion":"success","name":"Build distribution"}
{"conclusion":"success","name":"Publish GitHub Release"}
{"conclusion":"failure","name":"Publish to PyPI"}

=== run 23987828382 (v0.1.6) ===
{"conclusion":"success","name":"Validate release tag and changelog"}
{"conclusion":"success","name":"Build distribution"}
{"conclusion":"success","name":"Publish GitHub Release"}
{"conclusion":"failure","name":"Publish to PyPI"}

=== run 23988018813 (v0.1.7) ===
{"conclusion":"success","name":"Validate release tag and changelog"}
{"conclusion":"success","name":"Build distribution"}
{"conclusion":"failure","name":"Publish to PyPI"}
{"conclusion":"success","name":"Publish GitHub Release"}

=== run 23988284507 (v0.1.8) ===
{"conclusion":"success","name":"Validate release tag and changelog"}
{"conclusion":"success","name":"Build distribution"}
{"conclusion":"success","name":"Publish GitHub Release"}
{"conclusion":"failure","name":"Publish to PyPI"}
```

**This is the concrete state, not a hypothetical:** six times in a row, `publish-github-release`
succeeded — creating a real public tag + GitHub Release with `dist/*` attached — while
`publish-pypi` failed in the same run, i.e. exactly "a public tag + GH release with no
PyPI package." (The underlying job logs themselves have since expired past GitHub's
retention window — `HTTP 410` on `gh run view --log-failed` — so the specific PyPI-side
error message from April 2026 could not be recovered; the job-conclusion pattern across
all six runs is what's cited, not a fabricated log excerpt.) Those five releases
(`v0.1.3`–`v0.1.8`) no longer appear in `gh release list` — they were evidently deleted
once `v0.1.9` published clean. This is the incident cited in `release.yml`'s new comment,
`CHANGELOG.md`, `release-process.md`, and `PUBLISHING_GUIDE.md`.

## 4. Gate: `actionlint`

```
$ which actionlint && actionlint --version
/opt/homebrew/bin/actionlint
1.7.12
built with go1.26.3 compiler for darwin/arm64

$ actionlint -color .github/workflows/release.yml
(no output)
$ echo $?
0
```

Clean — zero findings against the post-change workflow.

## 5. Gate: pin-comment control, run strictly (no longer skipped)

The repo's `check-pin-comments-match` hook (from `pedro-angel/git-controls-starter`,
manual stage — network-dependent, run explicitly, exactly as `checks.yml` CI does) peels
every `# <ref>` comment and, for a **tag** comment, fails if the peeled SHA disagrees; for
a **branch** comment it only emits a `note:` (cannot be verified strictly) and passes.
Before this change, the `pypa/gh-action-pypi-publish` line hit the branch path (`note:
... names a BRANCH`) — the exact "skip" the task said to close.

```
$ pre-commit run check-pin-comments-match --hook-stage manual --all-files --verbose
every pin's # comment still dereferences to its SHA (network; run at CI/manual stage).......................Passed
- hook id: check-pin-comments-match
- duration: 4.0s

ok: every verifiable pin comment dereferences to its SHA
```

Passing, and — the point of the gate — the script's own per-line stdout contains **no**
`note: ... names a BRANCH` line for `pypa/gh-action-pypi-publish` anymore (it did before
this change, when the comment still said `release/v1`). Every SHA-pinned action's comment
in `release.yml` is now either a verified tag or, for the two that never carried a version
comment at all (n/a to this check), untouched. The one previously-exempt line is now
verified strictly, which is what "no longer skips this pin" means concretely.

## 6. Gate: full pre-commit suite

```
$ pre-commit run --all-files --show-diff-on-failure
trim trailing whitespace..............................................................Passed
fix end of files......................................................................Passed
check yaml.............................................................................Passed
check toml.............................................................................Passed
check for added large files...........................................................Passed
mixed line ending......................................................................Passed
check for merge conflicts..............................................................Passed
check for case conflicts...............................................................Passed
detect private key.....................................................................Passed
black..................................................................................Passed
isort...................................................................................Passed
ruff check..............................................................................Passed
no secret-looking file is tracked by git...............................................Passed
every Action is SHA-pinned, one pin per action repo-wide...............................Passed
no private identifier (hostname, internal name) enters the repo.......................Passed
$ echo $?
0
```

All default-stage hooks pass (matches `checks.yml`'s `pre-commit run --all-files` step;
the manual-stage hooks — `check-pin-comments-match`, `check-diagrams-rendered` — are
covered separately, §5 above and not re-run here since this change doesn't touch built
docs).

`check-commit-trailer` (`stages: [commit-msg]`) is exercised at actual commit time, not by
`--all-files`; its result is confirmed by the commit created for this change succeeding
(a failing trailer check would have blocked the commit outright).

No `yamllint` gate exists in this repo's toolchain (not in `.pre-commit-config.yaml`, not
installed, not referenced by any workflow) — `check-yaml` (pre-commit-hooks, ran above,
passed) is this repo's actual YAML-syntax gate and is what's reported here instead of an
unused tool.

## 7. Gate: job-graph sanity — exact `needs:` edges, all 5 jobs

Direct YAML parse (not `gh workflow view`, which only reflects the version already merged
to `main` and can't see this branch's uncommitted graph):

```
$ python3 - <<'EOF'
import yaml
with open(".github/workflows/release.yml") as f:
    doc = yaml.safe_load(f)
jobs = doc["jobs"]
print(f"Total jobs: {len(jobs)}")
for name, spec in jobs.items():
    needs = spec.get("needs")
    needs_list = [] if needs is None else ([needs] if isinstance(needs, str) else list(needs))
    print(f"  {name}: needs={needs_list}")
EOF
Total jobs: 5
  validate-release: needs=[]
  build: needs=['validate-release']
  integration: needs=['validate-release']
  publish-pypi: needs=['build', 'integration']
  publish-github-release: needs=['build', 'integration', 'publish-pypi']
```

An assertion against the exact expected edge set (`validate-release: []`; `build:
[validate-release]`; `integration: [validate-release]`; `publish-pypi: [build,
integration]`; `publish-github-release: [build, integration, publish-pypi]`) over the
same parsed structure passed with `ASSERTION PASSED: all 5 jobs present with exact
expected needs: edges`.

This is the full edge list requested by the task:
- `validate-release` → (none; triggered by tag push)
- `build` → `validate-release`
- `integration` → `validate-release`
- `publish-pypi` → `build`, `integration`
- `publish-github-release` → `build`, `integration`, `publish-pypi`

## Honest residual (mandatory, not fabricated)

**The reordered pipeline cannot be fully battle-tested without a real tag push.** Every
gate above (actionlint, the pin-comment control, the full pre-commit suite, the direct
YAML edge-set assertion) is static verification against the workflow file as text — none
of it executes the actual GitHub Actions runners, the real OIDC token exchange with PyPI,
or the real `softprops/action-gh-release` call. **First live validation of this exact
graph is the next real release** (the next `vX.Y.Z` tag push). What bounds the risk until
then: the graph is fail-closed by construction (`needs:` is a hard GitHub Actions gate —
`publish-github-release` structurally cannot start if `publish-pypi` fails or is
skipped), `actionlint` confirms the workflow is syntactically and semantically valid
GitHub Actions YAML, and the direct edge-set assertion confirms the graph is exactly what
was specified — but none of that is a substitute for watching a real tagged run go green
end to end. No dry-run claim is made here because none was performed; this residual is
recorded exactly as the task required, not paved over.
