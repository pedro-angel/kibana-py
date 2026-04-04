# Publishing Guide for kibana-py

Step-by-step guide to release a new version of `kibana-py` to PyPI.

## How releases work

1. You bump the version, update the changelog, and push a git tag.
2. A GitHub Actions workflow automatically builds, validates, and publishes to PyPI.
3. No manual upload is needed — the workflow uses [trusted publishing](https://docs.pypi.org/trusted-publishers/) (OIDC), so there are no long-lived API tokens.

### Key files

| File | Purpose |
|------|---------|
| `kibana/_version.py` | Single source of truth for the version string |
| `CHANGELOG.md` | Release notes (the workflow validates an entry exists) |
| `.github/workflows/release.yml` | Automated build + publish pipeline |

## Prerequisites (one-time setup)

Before your first release, ensure:

1. **PyPI project exists** and is configured for [trusted publishing](https://docs.pypi.org/trusted-publishers/adding-a-publisher/) from this GitHub repository. In PyPI project settings → Publishing, add:
   - Owner: your GitHub username or organization
   - Repository: `kibana-py`
   - Workflow: `release.yml`
   - Environment: `release`

2. **GitHub environment** named `release` exists in the repository settings (Settings → Environments). This is referenced by the workflow's `environment: release` field.

3. **You have push access** to `main` and permission to create tags.

## Release process

### Step 1: Decide the new version

Follow [Semantic Versioning](https://semver.org/):
- **Patch** (0.1.1): bug fixes only
- **Minor** (0.2.0): new features, backwards-compatible
- **Major** (1.0.0): breaking API changes

### Step 2: Update the version

Edit `kibana/_version.py`:
```python
__versionstr__ = "0.2.0"  # ← your new version
```

### Step 3: Update the changelog

Add a section at the top of `CHANGELOG.md` (under `## [Unreleased]`):
```markdown
## [0.2.0] - 2026-04-01

### Added
- New feature X

### Fixed
- Bug Y
```

Update the links at the bottom of the file:
```markdown
[Unreleased]: https://github.com/pedro-angel/kibana-py/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.2.0
[0.1.0]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.1.0
```

### Step 4: Run local checks

```bash
# Unit tests with coverage
make test

# Lint and type check
make lint

# Build the package and check it
rm -rf dist/ build/ *.egg-info
python -m build
python -m twine check dist/*
```

Optionally, run integration tests if you changed client logic:
```bash
make test-integration
```

### Step 5: Inspect the built artifacts

```bash
# List wheel contents — should contain only kibana/ package files
python -m zipfile -l dist/kibana_py-*.whl

# Verify py.typed is included
python -m zipfile -l dist/kibana_py-*.whl | grep py.typed

# Verify no test/docs/examples leaked in
python -m zipfile -l dist/kibana_py-*.whl | grep -E "tests/|docs/|examples/"
# ↑ should return nothing
```

### Step 6: Commit and push

```bash
git add kibana/_version.py CHANGELOG.md
git commit -m "Release v0.2.0"
git push origin main
```

### Step 7: Tag and push the tag

```bash
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0
```

This triggers the release workflow.

### Step 8: Monitor the workflow

Go to **Actions** → **Release** in the GitHub repository. The workflow will:

1. **Validate** — checks that:
   - the tagged commit is reachable from `origin/main`
   - the tag matches `kibana/_version.py`
   - `CHANGELOG.md` has an entry for this version
2. **Build** — runs `python -m build`, `twine check`, verifies wheel contents (`kibana/py.typed` present and no `tests/`, `docs/`, or `examples/` paths), and generates an SBOM
3. **GitHub Release** — creates a GitHub Release with auto-generated notes and attaches the wheel, sdist, and SBOM
4. **Publish to PyPI** — uploads to PyPI via trusted publishing

If any step fails, the release is aborted. Fix the issue and re-tag.

### Step 9: Verify the release

```bash
# Install from PyPI in a clean environment
python -m venv /tmp/kibana-release-check
source /tmp/kibana-release-check/bin/activate
pip install kibana-py
python -c "from kibana import __versionstr__; print(__versionstr__)"
# Should print: 0.2.0

# Install with optional dependencies
pip install "kibana-py[async,observability]"

# Quick smoke test (requires running Kibana)
python -c "
from kibana import Kibana
client = Kibana('http://localhost:5601', basic_auth=('elastic', 'espassword'))
print(client.status.get_status().meta.status)
client.close()
"

deactivate
rm -rf /tmp/kibana-release-check
```

Also check:
- [PyPI project page](https://pypi.org/project/kibana-py/) — metadata, links, and description render correctly
- [GitHub Releases](https://github.com/pedro-angel/kibana-py/releases) — assets (wheel, sdist, SBOM) are attached

## Troubleshooting

### "Tag does not match kibana/_version.py"
The tag you pushed (e.g., `v0.2.0`) must exactly match the version in `kibana/_version.py` (e.g., `"0.2.0"`). Fix the version file or delete and recreate the tag.

### "Tagged commit is not reachable from origin/main"
Releases must be tagged from commits that are in `main` history.

If you tagged the wrong commit:
```bash
git tag -d v0.2.0
git push origin --delete v0.2.0
```

Then create the tag from the correct commit on `main`:
```bash
git checkout main
git pull --ff-only
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0
```

### "Changelog entry not found"
The workflow greps for `## [0.2.0]` in `CHANGELOG.md`. Make sure the version header exists exactly as `## [X.Y.Z]`.

### "Publish to PyPI failed"
- Verify the `release` environment exists in GitHub repository settings
- Verify trusted publishing is configured in PyPI project settings
- Check that the workflow has `id-token: write` permission

### "How do I delete a bad tag?"
```bash
git tag -d v0.2.0              # delete locally
git push origin --delete v0.2.0 # delete remote
```
Fix the issue, then re-tag and push.

### "Can I test with TestPyPI first?"
Yes. Build locally and upload manually:
```bash
python -m build
python -m twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ kibana-py
```
You'll need a [TestPyPI account](https://test.pypi.org/) and API token for this.

## Security notes

- The release uses OIDC trusted publishing — no long-lived PyPI tokens exist
- Never commit credentials or API tokens to the repository
- Keep dependencies updated via Dependabot (configured in `.github/dependabot.yml`)

---

**Last Updated**: 2026-04-04
**Release Line**: 0.x
