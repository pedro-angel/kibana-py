# Release Process

This guide provides step-by-step instructions for publishing kibana-py releases to PyPI.

## Prerequisites

Before you can publish a release, ensure you have:

1. **PyPI Account**: Register at https://pypi.org
2. **TestPyPI Account** (recommended): Register at https://test.pypi.org
3. **API Tokens**: Generate API tokens for both PyPI and TestPyPI
4. **Maintainer Access**: You must be a maintainer of the kibana-py project
5. **Required Tools**:
   ```bash
   pip install build twine
   ```

## Version Numbering

kibana-py follows [Semantic Versioning](https://semver.org/) (SemVer):

- **MAJOR.MINOR.PATCH** (e.g., 1.2.3)
- **MAJOR**: Breaking changes (incompatible API changes)
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Pre-release Versions

For pre-releases, use:
- **Alpha**: `0.1.0a1`, `0.1.0a2`, ...
- **Beta**: `0.1.0b1`, `0.1.0b2`, ...
- **Release Candidate**: `0.1.0rc1`, `0.1.0rc2`, ...

## Release Checklist

Use this checklist for every release:

### Pre-Release
- [ ] `make check` passes locally (pre-commit, lint, dependency audit, SAST, unit tests)
- [ ] `make test-python-matrix` passes locally (multi-Python unit test matrix via nox; missing local interpreters are skipped)
- [ ] Documentation is up to date
- [ ] Integration tests pass locally against a live stack (`make test-integration`) — **required**; CI does not run them (they need a Docker Elastic Stack)
- [ ] CHANGELOG.md is updated with release notes
- [ ] Version number is updated in `kibana/_version.py`

### Build and Test
- [ ] Old builds cleaned
- [ ] Package built successfully
- [ ] Build artifacts verified
- [ ] Uploaded to TestPyPI
- [ ] Installed from TestPyPI successfully
- [ ] Basic functionality tested

### Publication
- [ ] Uploaded to PyPI
- [ ] Installation from PyPI verified
- [ ] PyPI page displays correctly

### Post-Release
- [ ] Git tag created and pushed
- [ ] GitHub release created
- [ ] Documentation updated
- [ ] Release announced

## Step-by-Step Release Process

### Step 1: Pre-Publication Checks

#### Update Version Number

Edit `kibana/_version.py`:

```python
# kibana/_version.py
__versionstr__ = "0.2.0"  # Update to new version
```

#### Update CHANGELOG.md

Add release notes for the new version:

```markdown
## [0.2.0] - 2024-01-15

### Added
- New feature X
- Support for Y

### Changed
- Improved Z

### Fixed
- Bug fix for A
```

#### Run All Tests

```bash
# Set up or refresh local environment
make setup

# Optional quick feedback while iterating
make pre-commit

# Run local CI-equivalent checks
make check

# Run required multi-Python matrix before release
make test-python-matrix
```

If some Python versions are not installed locally, nox skips them. The CI matrix remains the source of truth for full version coverage.

Run the integration suite against a live local stack. This is **required** before a
release: it is the only gate that exercises real API/client behavior end-to-end. CI
does not run integration tests (they need a Docker Elastic Stack), so a green CI run is
not sufficient on its own.

```bash
make test-integration
```

#### Verify Documentation

```bash
# Build documentation
cd docs
make html

# Check for warnings or errors
# View documentation locally
open build/html/index.html
```

#### Test Examples

Run a few key examples to ensure they work:

```bash
cd examples
python simple_status.py
python simple_space.py
```

### Step 2: Clean and Build

#### Clean Previous Builds

```bash
# Remove old distribution files
rm -rf dist/ build/ *.egg-info
```

#### Build Distribution Packages

```bash
# Build and validate source distribution and wheel
make build
```

**Expected Output**:
```
Successfully built kibana_py-0.2.0.tar.gz and kibana_py-0.2.0-py3-none-any.whl
```

#### Verify Build Artifacts

```bash
ls -lh dist/
# Should show:
# kibana_py-0.2.0-py3-none-any.whl
# kibana_py-0.2.0.tar.gz
```

#### Inspect Package Contents

```bash
# Inspect wheel contents
python -m zipfile -l dist/kibana_py-0.2.0-py3-none-any.whl

# Inspect tarball contents
tar -tzf dist/kibana_py-0.2.0.tar.gz
```

Verify the package doesn't contain:
- Sensitive credentials
- Private keys
- Internal documentation
- Test data with sensitive information

### Step 3: Test on TestPyPI

#### Configure TestPyPI Credentials

Create or edit `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR_PYPI_TOKEN_HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR_TESTPYPI_TOKEN_HERE
```

Set appropriate permissions:

```bash
chmod 600 ~/.pypirc
```

#### Upload to TestPyPI

```bash
twine upload --repository testpypi dist/*
```

**Expected Output**:
```
Uploading distributions to https://test.pypi.org/legacy/
Uploading kibana_py-0.2.0-py3-none-any.whl
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 45.0/45.0 kB
Uploading kibana_py-0.2.0.tar.gz
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 175.0/175.0 kB

View at:
https://test.pypi.org/project/kibana-py/0.2.0/
```

#### Test Installation from TestPyPI

```bash
# Create clean test environment
python3.13 -m venv /tmp/test_pypi_install
source /tmp/test_pypi_install/bin/activate

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    kibana-py

# Test basic functionality
python -c "from kibana import Kibana; print('✓ Installation successful')"

# Test imports
python -c "from kibana import AsyncKibana; print('✓ Async client available')"

# Clean up
deactivate
rm -rf /tmp/test_pypi_install
```

**Note**: The `--extra-index-url` is needed because dependencies (like elastic-transport) are on PyPI, not TestPyPI.

### Step 4: Publish to PyPI

#### Final Verification

Before publishing to PyPI, verify:
- [ ] TestPyPI installation worked correctly
- [ ] All tests passed
- [ ] Documentation is correct
- [ ] Version number is correct

#### Upload to PyPI

```bash
twine upload dist/*
```

**Expected Output**:
```
Uploading distributions to https://upload.pypi.org/legacy/
Uploading kibana_py-0.2.0-py3-none-any.whl
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 45.0/45.0 kB
Uploading kibana_py-0.2.0.tar.gz
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 175.0/175.0 kB

View at:
https://pypi.org/project/kibana-py/0.2.0/
```

#### Verify Publication

1. **Check PyPI Page**: Visit https://pypi.org/project/kibana-py/
2. **Verify Metadata**: Check that all information displays correctly
3. **Test Installation**:
   ```bash
   # Create clean environment
   python3.13 -m venv /tmp/test_pypi_prod
   source /tmp/test_pypi_prod/bin/activate

   # Install from PyPI
   pip install kibana-py

   # Test functionality
   python -c "from kibana import Kibana; print('✓ Success')"

   # Clean up
   deactivate
   rm -rf /tmp/test_pypi_prod
   ```

### Step 5: Post-Publication Tasks

#### Tag the Release in Git

```bash
# Create annotated tag
git tag -a v0.2.0 -m "Release version 0.2.0"

# Push tag to remote
git push origin v0.2.0
```

#### Create GitHub Release

1. Go to repository on GitHub
2. Click "Releases" → "Create a new release"
3. Select tag: `v0.2.0`
4. Release title: `v0.2.0`
5. Description: Copy from CHANGELOG.md
6. Optionally attach distribution files:
   - `kibana_py-0.2.0-py3-none-any.whl`
   - `kibana_py-0.2.0.tar.gz`
7. Click "Publish release"

#### Update Documentation

- [ ] Verify ReadTheDocs builds the new version
- [ ] Check that version selector shows new version
- [ ] Update any external documentation links

#### Announce Release

Consider announcing through:
- GitHub Discussions
- Project mailing list
- Social media (if applicable)
- Community forums
- Blog post (for major releases)

## Troubleshooting

### Upload Fails with "File already exists"

PyPI does not allow re-uploading the same version. You must:
1. Increment the version number in `kibana/_version.py`
2. Rebuild the package: `make build`
3. Upload the new version

### Authentication Errors

- Verify API token is correct in `~/.pypirc`
- Ensure token has upload permissions
- Check token hasn't expired
- Verify you're using `__token__` as username

### Package Not Found After Upload

- Wait a few minutes for PyPI to index the package
- Clear pip cache: `pip cache purge`
- Try installing with `--no-cache-dir`:
  ```bash
  pip install --no-cache-dir kibana-py
  ```

### Dependencies Not Installing

- Verify dependencies are correctly specified in `pyproject.toml`
- Check that dependency versions are available on PyPI
- Test in clean environment
- Check for version conflicts

### Build Fails

- Ensure `build` package is installed: `pip install build`
- Check `pyproject.toml` for syntax errors
- Verify all required files are included
- Check that `MANIFEST.in` is correct (if used)

## Security Considerations

### Protect API Tokens

- **Never commit** API tokens to version control
- Store tokens securely (e.g., password manager)
- Use environment variables or `~/.pypirc` with restricted permissions
- Rotate tokens periodically
- Use separate tokens for TestPyPI and PyPI

### Verify Package Contents

Before uploading, always verify the package doesn't contain:
- Sensitive credentials or API keys
- Private keys or certificates
- Internal documentation
- Test data with sensitive information
- Development configuration files

### Two-Factor Authentication

Enable 2FA on your PyPI account for additional security.

## Quick Reference Commands

```bash
# Clean and build
rm -rf dist/ build/ *.egg-info
make build

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*

# Create and push git tag
git tag -a v0.2.0 -m "Release version 0.2.0"
git push origin v0.2.0

# Test installation
pip install kibana-py
python -c "from kibana import Kibana; print('✓ Success')"
```

## Automation Considerations

### GitHub Actions Workflow (already configured)

Releases are automated via the repository's release workflow:

```yaml
name: Release

on:
  push:
    tags:
      - v*.*.*

jobs:
  validate:
    runs-on: ubuntu-26.04
    steps:
      - checks tag/version/changelog consistency

  build:
    runs-on: ubuntu-26.04
    steps:
      - builds wheel + sdist
      - runs twine check

  release:
    runs-on: ubuntu-26.04
    steps:
      - creates GitHub Release and uploads artifacts

  publish:
    runs-on: ubuntu-26.04
    permissions:
      id-token: write
    steps:
      - publishes to PyPI via trusted publishing (OIDC)
```

### Version Bumping

Consider using tools like:
- `bump2version` for automated version bumping
- `commitizen` for conventional commits and changelog generation

## Additional Resources

- [PyPI Documentation](https://packaging.python.org/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [Semantic Versioning](https://semver.org/)
- [Python Packaging Guide](https://packaging.python.org/tutorials/packaging-projects/)
- [PEP 440 - Version Identification](https://www.python.org/dev/peps/pep-0440/)

## Support

If you encounter issues during the release process:
- Check the troubleshooting section above
- Review PyPI documentation
- Ask in the project's GitHub Discussions
- Contact project maintainers

---

**Last Updated**: April 2026
