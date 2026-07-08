# Release Process

kibana-py releases are **automated**. Pushing a version tag (`vX.Y.Z`) to GitHub runs
the release workflow, which validates the tag, builds the distribution, creates the
GitHub Release, and publishes to PyPI. You do **not** run `twine upload` or create the
GitHub Release by hand — doing so collides with the workflow.

The canonical definition of the pipeline is
[`.github/workflows/release.yml`](https://github.com/pedro-angel/kibana-py/blob/main/.github/workflows/release.yml);
this page explains how to drive it.

## How a release runs

A single action — pushing an annotated `vX.Y.Z` tag whose commit is on `main` — triggers
the whole pipeline:

```text
  git push origin vX.Y.Z
          │
          ▼
  ┌───────────────────┐   tag on main? tag == _version.py? CHANGELOG entry exists?
  │  validate-release │───────────────────────────────────────────────┐ (fails fast)
  └─────────┬─────────┘                                                │
            ▼                                                          │
  ┌───────────────────┐   python -m build → twine check →             │
  │       build       │   wheel-content guard → SBOM → upload artifact │
  └─────────┬─────────┘                                                │
            ▼                                                          │
  ┌───────────────────────┐   softprops/action-gh-release             │
  │ publish-github-release │   (generated notes + dist/* attached)     │
  └─────────┬─────────────┘                                            │
            ▼                                                          │
  ┌───────────────────┐   PyPI trusted publishing (OIDC, no token)    │
  │    publish-pypi   │◄──────────────────────────────────────────────┘
  └───────────────────┘
```

Jobs, in order (source of truth: `release.yml`):

| Job | Runs after | Permissions | What it does |
|-----|-----------|-------------|--------------|
| `validate-release` | tag push | `contents: read` | Fails the release unless: the tagged commit is reachable from `origin/main`; the tag equals `v` + `__versionstr__` in `kibana/_version.py`; and `CHANGELOG.md` has a `## [X.Y.Z]` heading. |
| `build` | `validate-release` | `contents: read` | Installs `.[build]`, runs `python -m build`, `twine check`, a wheel-content guard (must contain `kibana/py.typed`; must **not** contain `tests/`, `docs/`, `examples/`), generates a CycloneDX SBOM, and uploads the `dist` artifact. |
| `publish-github-release` | `build` | `contents: write` | Downloads `dist`, creates the GitHub Release for the tag with auto-generated notes and attaches every `dist/*` file (wheel, sdist, SBOM). |
| `publish-pypi` | `build` + `publish-github-release` | `contents: read`, `id-token: write` | Downloads `dist`, removes `*.json` (the SBOM is not a PyPI artifact), and publishes the wheel + sdist to PyPI via **OIDC trusted publishing** — no API token. |

## One-time setup

These are configured once for the project, not per release.

### PyPI trusted publishing (OIDC)

`publish-pypi` authenticates to PyPI with a short-lived OIDC token (`id-token: write`),
so **no PyPI API token or `~/.pypirc` is involved in a release**. This requires a
one-time *trusted publisher* registered on PyPI for the project:

- Project: `kibana-py`
- Owner / repository: `pedro-angel/kibana-py`
- Workflow filename: `release.yml`
- Environment: none (the `environment: release` line in `release.yml` is commented out)

Register it under **PyPI → the project → Settings → Publishing** (for a brand-new
project, add a *pending* publisher first). See the
[PyPI trusted publishing guide](https://docs.pypi.org/trusted-publishers/).

:::{note}
If you want a deployment-gate (manual approval before publish), uncomment
`# environment: release` in `release.yml`, create a GitHub Environment named `release`
with the desired protection rules, and add that environment name to the trusted
publisher on PyPI.
:::

### Read the Docs

Documentation is built by Read the Docs from
[`.readthedocs.yaml`](https://github.com/pedro-angel/kibana-py/blob/main/.readthedocs.yaml)
(Ubuntu 24.04, Python 3.14, install `.[docs]`, `fail_on_warning: true`, builds HTML +
PDF + ePub). RTD builds on each push/tag via its webhook. `latest` tracks `main`;
`stable` tracks the highest non-prerelease tag.

One-time setup is an RTD project
[imported from the GitHub repo](https://docs.readthedocs.io/en/stable/intro/import-guide.html)
by a maintainer with admin access to the RTD account that owns `kibana-py`. After the
first tag, confirm in the RTD dashboard that the new version built and is activated, and
that `stable` points at it.

### Local tools

For local checks you only need the dev environment:

```bash
make setup PYTHON=python3.14   # requires-python is >=3.14
```

Watching the release run also uses the [`gh` CLI](https://cli.github.com/)
(`gh auth login` with repo access) — optional; the GitHub **Actions** tab works too.

A PyPI/TestPyPI **API token** is needed *only* for the optional manual dry-run
([below](#optional-local-dry-run-to-testpypi)) — never for an automated release.

## Pre-release checklist

- [ ] `make check` passes (pre-commit, lint, dependency audit, SAST, unit tests)
- [ ] `make test-python-matrix` passes (multi-Python unit matrix via nox; missing interpreters are skipped)
- [ ] `make test-integration` passes locally against a live stack — **required**; CI does not run it (needs a Docker Elastic Stack)
- [ ] Documentation builds clean: `make docs` (HTML with `-W` + linkcheck, matching RTD's `fail_on_warning`)
- [ ] Version bumped in `kibana/_version.py`
- [ ] `CHANGELOG.md` updated (entry **and** reference links)

## Step by step

Set a shell variable for the version; it is used from Step 4 onward to keep the tag and
verification commands consistent:

```bash
VERSION=X.Y.Z   # the version you are releasing
```

### 1. Bump the version

The version lives in **one** place — `kibana/_version.py`:

```python
# kibana/_version.py
__versionstr__ = "X.Y.Z"
```

`pyproject.toml` declares `dynamic = ["version"]` and reads this file via
`[tool.hatch.version]`, so **do not** edit a version in `pyproject.toml` — there isn't
one. `validate-release` reads the same file, so the tag must equal `v$VERSION`.

### 2. Update the changelog

Add a dated entry (the workflow checks the `## [X.Y.Z]` heading exists):

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- ...

### Fixed
- ...
```

Also update the reference-link footer at the bottom of `CHANGELOG.md`: add the
`[X.Y.Z]` compare/tag link and re-base the `[Unreleased]` compare range on `vX.Y.Z`.

### 3. Land the release commit on `main`

`validate-release` runs `git merge-base --is-ancestor <tagged-commit> origin/main` and
**fails the release** if the tag is not on `main`. Land the version + changelog change on
`main` first through the normal
[contribution workflow](https://github.com/pedro-angel/kibana-py/blob/main/CONTRIBUTING.md)
(branch → PR → merge). Then check out `main` and confirm the commit you are about to tag:

```bash
git checkout main && git pull
git log -1 --oneline    # confirm this is your version-bump + changelog commit
```

### 4. Tag and push — this publishes

```bash
git tag -a "v$VERSION" -m "Release $VERSION"
git push origin "v$VERSION"
```

That tag push is the release. Watch it run and confirm every job is green — with the
[`gh` CLI](https://cli.github.com/) (authenticated), or from the repository's
**Actions → Release** tab:

```bash
gh run watch "$(gh run list --workflow release.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
```

### 5. Verify

- **PyPI:** the package page shows the new version, and a clean install works:

  ```bash
  python3.14 -m venv /tmp/verify && /tmp/verify/bin/pip install "kibana-py==$VERSION"
  /tmp/verify/bin/python -c "from kibana import Kibana, AsyncKibana; print('ok')"
  rm -rf /tmp/verify
  ```

- **GitHub Release:** a release for `vX.Y.Z` exists with generated notes and the wheel,
  sdist, and `sbom.cdx.json` attached.
- **Read the Docs:** the tagged version built successfully and is activated; the version
  selector shows it and `stable` points at it.

## If a job fails

| Symptom | Cause | Fix |
|---------|-------|-----|
| `validate-release`: "not reachable from origin/main" | Tag is on a branch not merged to `main` | Merge to `main`, delete the tag (`git push --delete origin vX.Y.Z`), re-tag the `main` commit. |
| `validate-release`: "Tag … does not match" | Tag ≠ `v` + `__versionstr__` | Fix `kibana/_version.py` or the tag so they agree. |
| `validate-release`: changelog grep fails | No `## [X.Y.Z]` heading | Add the changelog entry, re-tag. |
| `build`: wheel-content guard fails | sdist/wheel packaging changed | Check `[tool.hatch.build.targets.*]` include/exclude in `pyproject.toml` (this project uses hatchling — there is no `MANIFEST.in`). |
| `publish-pypi`: auth / "not a trusted publisher" | Trusted publisher not registered | Complete the [PyPI trusted publisher setup](#pypi-trusted-publishing-oidc). |

**Recovering a failed run.** If a job fails *before* the PyPI upload, fix the cause and
re-run the failed jobs from the **Actions** tab — or delete and re-push the tag
(`git push --delete origin "v$VERSION"` then re-tag `main`), which re-runs the pipeline
from `validate-release`. Re-running `publish-github-release` is safe: it updates the
existing release for the tag rather than erroring. Re-running `publish-pypi` succeeds
only if that version was never uploaded — PyPI refuses to replace an existing version, so
if it already published you must bump to a new version.
| `publish-pypi`: "File already exists" | This version was already uploaded (e.g. a manual `twine upload`) | You cannot re-publish a version. Bump to a new version; never manually upload a version you intend to release via the workflow. |

## Optional: local dry-run to TestPyPI

:::{warning}
This is an **optional local sanity check**, not a release step. Production publishing is
automated (see [How a release runs](#how-a-release-runs)). Nothing here is required to
ship a release.
:::

To exercise packaging end-to-end before tagging, build locally and upload to TestPyPI
using a TestPyPI API token in `~/.pypirc`. The **`--repository testpypi`** flag is what
keeps this off production PyPI — without it, `twine upload` targets real PyPI:

```bash
rm -rf dist/                                 # avoid uploading stale builds
make build                                   # python -m build + twine check
twine upload --repository testpypi dist/*
python3.14 -m venv /tmp/testpypi \
  && /tmp/testpypi/bin/pip install \
       --index-url https://test.pypi.org/simple/ \
       --extra-index-url https://pypi.org/simple/ kibana-py
rm -rf /tmp/testpypi
```

## Appendix: emergency manual publish (fallback only)

:::{warning}
Use this **only** if automated OIDC publishing is unavailable. Do **not** run it and also
push the tag — the workflow would try to publish the same version and fail with "File
already exists". Pick one path.
:::

With a PyPI API token in `~/.pypirc`:

```bash
rm -rf dist/
make build
twine upload dist/*          # NOTE: no --repository flag = production PyPI
```

Then create the GitHub Release and tag by hand to match. Prefer fixing the automated
path over relying on this.

## References

- [`.github/workflows/release.yml`](https://github.com/pedro-angel/kibana-py/blob/main/.github/workflows/release.yml) — the pipeline (source of truth)
- [PyPI trusted publishers](https://docs.pypi.org/trusted-publishers/)
- [Semantic Versioning](https://semver.org/) · [PEP 440](https://peps.python.org/pep-0440/)
- [Python Packaging Guide](https://packaging.python.org/)
