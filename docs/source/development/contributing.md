# Contributing to kibana-py

Thank you for your interest in contributing to kibana-py! This guide provides everything you need to know to contribute effectively.

## Code of Conduct

This project adopts the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) as its code of conduct. By participating, you are expected to uphold these standards.

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
python -m venv .venv

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

See {doc}`testing` for detailed testing guidelines.

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

## Code Quality Standards

### Code Style

- **Black** for code formatting (line length: 88)
- **isort** for import sorting (black profile)
- **Type hints** required for all public APIs
- **Docstrings** required for all public functions and classes

### Linting

- **Ruff** for linting (replaces flake8, pylint, etc.)
- **Mypy** for static type checking (strict mode)
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

## Documentation Guidelines

### Docstring Format

Use Google-style docstrings for consistency with the documentation system:

```python
def create(
    self,
    *,
    name: str,
    connector_type_id: str,
    config: dict[str, Any],
    secrets: dict[str, Any] | None = None,
) -> ObjectApiResponse[dict[str, Any]]:
    """Create a new action connector.

    Creates a connector (action) in Kibana that can be used for alerting
    and automation workflows.

    Args:
        name: Display name for the connector.
        connector_type_id: Type of connector (e.g., ".index", ".webhook").
        config: Connector-specific configuration.
        secrets: Sensitive connector configuration (optional).

    Returns:
        API response containing the created connector details including
        the connector ID.

    Raises:
        ConflictError: If a connector with the same name already exists.
        BadRequestError: If the configuration is invalid.

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

### Documentation Requirements

When adding or changing functionality:

1. **Update docstrings** in the code with comprehensive descriptions
2. **Update user guide** if adding new features or changing behavior
3. **Add examples** to demonstrate usage patterns
4. **Update API reference** if changing method signatures
5. **Update CHANGELOG.md** with your changes

### Building Documentation Locally

```bash
# Install documentation dependencies
pip install -r docs/requirements.txt

# Build HTML documentation
cd docs
make html

# View documentation
open build/html/index.html  # macOS
# or
xdg-open build/html/index.html  # Linux
```

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

- [ ] Tests pass locally (`pytest`)
- [ ] Code is formatted (`black`, `isort`)
- [ ] Code passes linting (`ruff`, `mypy`)
- [ ] Documentation is updated
- [ ] Docstrings follow Google style
- [ ] CHANGELOG.md is updated
- [ ] Commit messages are clear and descriptive
- [ ] Branch is up to date with main

## Review Process

### What to Expect

- Initial review within 1-2 business days
- Constructive feedback on code, tests, and documentation
- Requests for changes or clarifications
- Approval once all feedback is addressed

### Review Guidelines

When reviewing others' contributions:

- Be respectful and constructive
- Focus on code quality, not personal preferences
- Suggest improvements with examples
- Approve when standards are met

## Getting Help

- **Questions**: Open a discussion on GitHub
- **Bugs**: Open an issue with reproduction steps
- **Features**: Open an issue to discuss before implementing
- **Chat**: Join the Elastic community Slack

## Additional Resources

- {doc}`testing` - Comprehensive testing guide
- {doc}`adding-space-support` - Adding space support to new clients
- {doc}`architecture` - Project architecture overview
- [Python Packaging Guide](https://packaging.python.org/)
- [pytest Documentation](https://docs.pytest.org/)
- [Type Hints (PEP 484)](https://www.python.org/dev/peps/pep-0484/)
- [Kibana API Documentation](https://www.elastic.co/guide/en/kibana/current/api.html)

## License

By contributing to kibana-py, you agree that your contributions will be licensed under the Apache License 2.0.

---

Thank you for contributing to kibana-py! 🎉
