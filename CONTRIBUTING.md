# Contributing to kibana-py

Thank you for your interest in contributing to kibana-py! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)

## Code of Conduct

This project adopts the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) as its code of conduct. By participating, you are expected to uphold these standards.

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- A running Kibana instance for integration tests (optional but recommended)

### Finding Issues to Work On

- Check the [issue tracker](https://github.com/pedro-angel/kibana-py/issues) for open issues
- Look for issues labeled `good first issue` or `help wanted`
- Feel free to ask questions on issues before starting work

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/kibana-py.git
cd kibana-py

# Add upstream remote
git remote add upstream https://github.com/pedro-angel/kibana-py.git
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

### 3. Install Development Dependencies

```bash
# Install the package in editable mode with development dependencies
pip install -e ".[dev]"

# Verify installation
python -c "import kibana; print(kibana.__version__)"
```

### 4. Set Up Local Kibana (Optional)

For integration testing, you can use the provided local Elastic Stack:

```bash
./local-stack.sh -o start

# The script will create a .env file with credentials
# Integration tests will automatically use these credentials

# To stop:
./local-stack.sh -o stop
```

## Development Workflow

### 1. Create a Branch

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Write your code following the project's coding standards
- Add or update tests as needed
- Update documentation if you're changing functionality
- Keep commits focused and atomic

### 3. Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_base_client.py

# Run with coverage
pytest --cov=kibana --cov-report=term-missing
```

### 4. Format and Lint

```bash
# Format code
black kibana tests
isort kibana tests

# Lint code
ruff check kibana tests

# Type check
mypy kibana
```

Or use nox for all quality checks:

```bash
nox -s format
nox -s lint
```

### 5. Commit Changes

```bash
# Stage your changes
git add .

# Commit with a descriptive message
git commit -m "Add feature: description of your changes"
```

Follow these commit message guidelines:
- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit first line to 72 characters
- Reference issues and pull requests when relevant

### 6. Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Testing

### Unit Tests

Unit tests are located in `tests/unit/` and test individual components in isolation:

```bash
# Run all unit tests
pytest tests/unit/

# Run specific test class
pytest tests/unit/test_base_client.py::TestBaseClientInitialization

# Run specific test
pytest tests/unit/test_base_client.py::TestBaseClientInitialization::test_init_with_transport
```

### Integration Tests

Integration tests are located in `tests/integration/` and test against a real Kibana instance:

```bash
# Set up environment (if not using elastic-start-local)
export KIBANA_URL="http://localhost:5601"
export KIBANA_USERNAME="elastic"
export KIBANA_PASSWORD="your_password"

# Run integration tests
pytest tests/integration/

# Run specific integration test
pytest tests/integration/test_actions_integration.py
```

Integration tests are automatically skipped if `KIBANA_URL` is not set.

### Writing Tests

When adding new functionality:

1. **Write unit tests first** (TDD approach)
2. **Test edge cases** and error conditions
3. **Use fixtures** from `conftest.py` for common setup
4. **Mock external dependencies** in unit tests
5. **Clean up resources** in integration tests

Example test structure:

```python
import pytest
from kibana import Kibana
from kibana.exceptions import NotFoundError

class TestActionsClient:
    def test_get_connector_success(self, mock_transport):
        """Test successful connector retrieval."""
        # Arrange
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"id": "test-id", "name": "Test Connector"},
            meta=ApiResponseMeta(status=200, headers={}, http_version="1.1"),
        )
        client = Kibana(_transport=mock_transport)

        # Act
        result = client.actions.get(id="test-id")

        # Assert
        assert result.body["id"] == "test-id"
        mock_transport.perform_request.assert_called_once()

    def test_get_connector_not_found(self, mock_transport):
        """Test connector not found error."""
        # Arrange
        mock_transport.perform_request.side_effect = NotFoundError(
            message="Not found",
            meta=ApiResponseMeta(status=404, headers={}, http_version="1.1"),
            body={"error": "Not found"},
        )
        client = Kibana(_transport=mock_transport)

        # Act & Assert
        with pytest.raises(NotFoundError):
            client.actions.get(id="non-existent")
```

### Test Coverage

- CI enforces a **≥75% code coverage** floor; aim for **��90%**
- Critical paths should have **100% coverage**
- Run coverage report: `pytest --cov=kibana --cov-report=html`
- View HTML report: `open htmlcov/index.html`

## Code Quality

### Code Style

- **Black** for code formatting (line length: 88)
- **isort** for import sorting (black profile)
- **Type hints** required for all public APIs
- **Docstrings** required for all public functions and classes

### Linting

- **Ruff** for linting (replaces flake8, pylint, etc.)
- **Mypy** for static type checking
- **Pyright** for additional type checking

### Running Quality Checks

```bash
# Format code
black kibana tests
isort kibana tests

# Lint
ruff check kibana tests

# Type check
mypy kibana
pyright kibana

# Or use nox
nox -s format
nox -s lint
```

### Pre-commit Hooks (Optional)

You can set up pre-commit hooks to automatically run checks:

```bash
pip install pre-commit
pre-commit install
```

## Documentation

Documentation is a critical part of kibana-py. All contributions should include appropriate documentation updates.

### Documentation Structure

The project uses Sphinx for documentation with the following structure:

```
docs/
├── source/
│   ├── conf.py                    # Sphinx configuration
│   ├── index.rst                  # Main documentation index
│   ├── installation.md            # Installation guide
│   ├── quickstart.md              # Quick start guide
│   ├── user-guide/                # User documentation
│   ├── api-reference/             # Auto-generated API docs
│   ├── examples/                  # Example documentation
│   ├── development/               # Developer guides
│   ├── migration-guides/          # Migration guides
│   └── troubleshooting/           # Troubleshooting guides
├── Makefile                       # Build commands (Unix)
├── make.bat                       # Build commands (Windows)
└── requirements.txt               # Documentation dependencies
```

### Building Documentation Locally

To build and view the documentation locally:

```bash
# Install documentation dependencies
pip install -r docs/requirements.txt

# Build HTML documentation
cd docs
make html

# View the documentation
open build/html/index.html  # macOS
# or
xdg-open build/html/index.html  # Linux
# or
start build/html/index.html  # Windows
```

Additional build commands:

```bash
# Check for broken links
make linkcheck

# Clean build artifacts
make clean

# Build with auto-reload (for development)
sphinx-autobuild source build/html
```

### Docstring Standards

**Format**: Google-style docstrings (not reStructuredText)

All public classes, methods, and functions must have comprehensive docstrings following Google style:

```python
def create(
    self,
    *,
    name: str,
    connector_type_id: str,
    config: dict[str, Any],
    secrets: dict[str, Any] | None = None,
    space_id: str | None = None,
) -> ObjectApiResponse[dict[str, Any]]:
    """Create a new connector.

    Creates a connector (action) in Kibana that can be used for alerting
    and automation workflows.

    Args:
        name: Display name for the connector.
        connector_type_id: Type of connector (e.g., ".index", ".webhook").
        config: Connector-specific configuration.
        secrets: Sensitive connector configuration (optional).
        space_id: Space ID for space-scoped operation (optional).

    Returns:
        API response containing the created connector details including
        the connector ID.

    Raises:
        ConflictError: If a connector with the same name already exists.
        BadRequestError: If the configuration is invalid.
        SpaceNotFoundError: If the specified space does not exist.

    Example:
        >>> client = Kibana("http://localhost:5601")
        >>> connector = client.actions.create(
        ...     name="My Webhook",
        ...     connector_type_id=".webhook",
        ...     config={"url": "https://example.com/webhook"}
        ... )
        >>> print(connector.body["id"])
    """
```

**Docstring Requirements**:

- **Summary line**: One-line summary of what the function/method does
- **Extended description**: Additional details about behavior (optional but recommended)
- **Args**: Document all parameters with types and descriptions
  - Use `param_name: Description.` format
  - Mark optional parameters clearly
  - Include default values if relevant
- **Returns**: Describe the return value and its structure
- **Raises**: List all exceptions that can be raised
- **Example**: Include usage examples for complex methods

### Documentation Style Guidelines

#### Markdown Formatting

**Headings**:
- Use ATX-style headers (`#`, `##`, `###`)
- One H1 per page (page title)
- Logical hierarchy (don't skip levels)
- Descriptive, action-oriented titles

**Code Blocks**:
```python
# Always specify language
# Use consistent indentation (4 spaces)
# Include comments for clarity
from kibana import Kibana

client = Kibana("http://localhost:5601")
```

**Lists**:
- Use `-` for unordered lists
- Use `1.` for ordered lists
- Consistent indentation (2 spaces for nested items)
- Blank line before and after lists

**Links**:
```markdown
# Internal links (to other docs)
See the {doc}`user-guide/authentication` for details.

# External links
See the [Kibana API documentation](https://www.elastic.co/guide/en/kibana/current/api.html)
for more information.
```

**Admonitions** (notes, warnings, tips):
```markdown
:::{note}
This is a note with important information.
:::

:::{warning}
This is a warning about potential issues.
:::

:::{tip}
This is a helpful tip for users.
:::
```

#### Cross-References

Use Sphinx cross-reference syntax for maintainable links:

```markdown
# Link to other documentation pages
See {doc}`user-guide/authentication` for details.

# Link to specific sections
See {ref}`authentication-api-key` for API key setup.

# Link to API documentation
See {class}`kibana.Kibana` for the main client class.
See {meth}`kibana.ActionsClient.create` for creating connectors.
```

### Documentation Coverage Requirements

- **90% minimum docstring coverage** for the codebase
- **100% coverage required** for all public APIs
- Check coverage with: `interrogate -v kibana/`

### Documentation Review Process

When submitting a pull request with code changes:

1. **Update API documentation**:
   - Add/update docstrings for new/changed methods
   - Follow Google-style format
   - Include examples for complex functionality

2. **Update user guide** (if applicable):
   - Add new sections for new features
   - Update existing sections for changed behavior
   - Include code examples and use cases

3. **Update examples** (if applicable):
   - Add new example files for new features
   - Update existing examples if behavior changes
   - Document examples in `docs/source/examples/`

4. **Update API reference** (if needed):
   - Add new RST files for new client classes
   - Update existing RST files for new methods

5. **Build and test documentation**:
   ```bash
   cd docs
   make clean html
   make linkcheck
   ```

6. **Check for warnings**:
   - Fix all Sphinx warnings
   - Ensure all cross-references work
   - Verify code examples are correct

### Documentation Checklist for Pull Requests

- [ ] All new/changed public APIs have Google-style docstrings
- [ ] Docstrings include Args, Returns, Raises, and Example sections
- [ ] User guide updated for new features or changed behavior
- [ ] Examples added or updated if applicable
- [ ] Documentation builds without errors: `make html`
- [ ] No broken links: `make linkcheck`
- [ ] Docstring coverage meets 90% threshold
- [ ] CHANGELOG.md updated with user-facing changes

### Common Documentation Tasks

#### Adding a New API Client

When adding a new API client (e.g., `AlertsClient`):

1. Add comprehensive docstrings to all methods
2. Create `docs/source/api-reference/alerts.rst`:
   ```rst
   Alerts Client
   =============

   .. autoclass:: kibana.AlertsClient
      :members:
      :inherited-members:
      :show-inheritance:
   ```
3. Add to `docs/source/api-reference/index.rst`
4. Create user guide section: `docs/source/user-guide/alerts.md`
5. Add examples: `docs/source/examples/alerts/`

#### Adding a New Feature

When adding a new feature to an existing client:

1. Update method docstrings with new parameters/behavior
2. Update relevant user guide section
3. Add example demonstrating the feature
4. Update API reference if needed (usually automatic)

#### Fixing a Bug

When fixing a bug:

1. Update docstrings if behavior changes
2. Add troubleshooting entry if relevant
3. Update examples if they were affected
4. Document the fix in CHANGELOG.md

### Style Guide Reference

For detailed style guidelines, see:
- [Sphinx Documentation](https://www.sphinx-doc.org/)
- [MyST Parser](https://myst-parser.readthedocs.io/)
- [Google Python Style Guide - Docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)

## Submitting Changes

### Pull Request Process

1. **Update your branch** with the latest upstream changes:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Ensure all tests pass** and code quality checks succeed

3. **Create a pull request** with:
   - Clear title describing the change
   - Description of what changed and why
   - Reference to related issues
   - Screenshots/examples if applicable

4. **Respond to review feedback** promptly

5. **Squash commits** if requested before merging

### Pull Request Checklist

**Code Quality**:
- [ ] Tests pass locally (`pytest`)
- [ ] Code is formatted (`black`, `isort`)
- [ ] Code passes linting (`ruff`, `mypy`)
- [ ] Commit messages are clear and descriptive
- [ ] Branch is up to date with main

**Documentation** (see [Documentation](#documentation) section for details):
- [ ] All new/changed public APIs have Google-style docstrings
- [ ] Docstrings include Args, Returns, Raises, and Example sections
- [ ] User guide updated for new features or changed behavior
- [ ] Examples added or updated if applicable
- [ ] Documentation builds without errors (`cd docs && make html`)
- [ ] No broken links (`cd docs && make linkcheck`)
- [ ] Docstring coverage meets 90% threshold
- [ ] CHANGELOG.md is updated with user-facing changes

## Release Process

Releases are maintainer-managed and cut from protected `main` using tags in `vX.Y.Z` format.

Before creating a release tag:

1. Ensure changelog entries are finalized for the target version.
2. Ensure unit, integration, lint, type, security, and docs checks are green.
3. Ensure `kibana/_version.py` matches the release tag.

Branch protection should require successful checks from test and docs workflows (plus any active security checks configured in GitHub settings).

Releases are managed by project maintainers. The process is:

1. Update version in `kibana/_version.py`
2. Update CHANGELOG.md with release notes
3. Create a git tag: `git tag v0.1.0`
4. Push tag: `git push upstream v0.1.0`
5. Build and publish to PyPI:
   ```bash
   python -m build
   twine upload dist/*
   ```

## Getting Help

- **Questions**: Open a discussion on GitHub
- **Bugs**: Open an issue with reproduction steps
- **Features**: Open an issue to discuss before implementing
- **Chat**: Open a [GitHub Discussion](https://github.com/pedro-angel/kibana-py/discussions)

## Additional Resources

- [Python Packaging Guide](https://packaging.python.org/)
- [pytest Documentation](https://docs.pytest.org/)
- [Type Hints (PEP 484)](https://www.python.org/dev/peps/pep-0484/)
- [Kibana API Documentation](https://www.elastic.co/guide/en/kibana/current/api.html)

## License

By contributing to kibana-py, you agree that your contributions will be licensed under the Apache License 2.0.

---

Thank you for contributing to kibana-py! 🎉
