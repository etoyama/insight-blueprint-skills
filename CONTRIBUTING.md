# Contributing to insight-blueprint

Thank you for your interest in contributing! This guide covers everything you need to get started.

## Getting Started

### Prerequisites

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** -- Package manager (do not use pip directly)

### Setup

```bash
git clone https://github.com/etoyama/insight-blueprint-skills.git
cd insight-blueprint-skills

# Install all dependencies (--all-extras is REQUIRED for dev tools: ruff, ty, pytest, poe)
uv sync --all-extras

# Set up pre-commit hooks (runs lint, typecheck, and tests before each commit)
uv run pre-commit install
```

> **Note**: `uv sync` without `--all-extras` will NOT install development tools.
> Always use `uv sync --all-extras` to get the full development environment.

### Common Commands

```bash
poe lint            # Lint and format check (ruff)
poe format          # Auto-fix lint issues and format
poe typecheck       # Type check (ty)
poe test            # Run tests (pytest)
poe all             # Run lint + typecheck + test
poe ci              # Run the full CI pipeline locally (lint + typecheck + test)
```

## Code Style

### Language Policy

- **Code** (variables, functions, comments, docstrings): English
- **Documentation**: English preferred, Japanese acceptable for user-facing docs

### Naming Conventions

| Element | Style | Example |
|---------|-------|---------|
| Variables / Functions | `snake_case` | `user_count`, `calculate_total()` |
| Classes | `PascalCase` | `AnalysisDesign` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES` |

### Core Principles

- **Simplicity first** -- Readable code over clever code. Avoid over-abstraction.
- **Single responsibility** -- One function does one thing. Target 200-400 lines per file (max 800).
- **Early return** -- Use guard clauses to avoid deep nesting.
- **Immutability** -- Create new objects instead of mutating existing ones.
- **No magic numbers** -- Define constants with meaningful names.

### Type Hints

All functions must have type annotations:

```python
def call_api(
    endpoint: str,
    params: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    ...
```

### Linting and Formatting

We use [ruff](https://docs.astral.sh/ruff/) for both linting and formatting. Configuration is in `pyproject.toml`.

```bash
# Check for issues
poe lint

# Auto-fix and format
poe format
```

## Testing

### Running Tests

```bash
poe test                                        # All tests
uv run pytest tests/test_specific.py -v         # Specific file
uv run pytest tests/test_specific.py::test_fn   # Specific test
uv run pytest --cov=src --cov-report=term-missing  # With coverage
```

### Writing Tests

We follow the **AAA pattern** (Arrange / Act / Assert):

```python
def test_create_design_with_valid_data_returns_design():
    # Arrange
    data = {"title": "Analysis A", "hypothesis": "X causes Y"}

    # Act
    design = create_design(data)

    # Assert
    assert design.title == "Analysis A"
    assert design.hypothesis == "X causes Y"
```

**Naming convention**: `test_{target}_{condition}_{expected_result}`

### Test Coverage

- **Target**: 80% or higher
- **Test categories**: Happy path, boundary values, error cases, edge cases
- **Speed**: Unit tests should run in < 100ms each
- **Mocking**: Mock external dependencies (APIs, databases). Use `conftest.py` for shared fixtures.

## Security Checklist

Before submitting code, verify:

- [ ] No hardcoded API keys, passwords, or secrets
- [ ] Sensitive values come from environment variables
- [ ] `.env` files are not committed
- [ ] External input is validated (use Pydantic models)
- [ ] Error messages shown to users don't expose internal details
- [ ] Logs don't contain sensitive information

## Pull Request Process

### Branch Naming

```
feat/<short-description>    # New features
fix/<short-description>     # Bug fixes
docs/<short-description>    # Documentation changes
refactor/<short-description> # Code refactoring
```

### Before Submitting

1. Ensure all checks pass:
   ```bash
   poe all
   ```
2. Write or update tests for your changes
3. Keep commits focused -- one logical change per commit
4. Use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages:
   ```
   feat: add catalog search filtering
   fix: handle empty hypothesis in validation
   docs: update installation instructions
   ```

### Review Process

1. Open a pull request against `main`
2. Fill in the PR description with what changed and why
3. CI must pass before merging
4. At least one approval is required

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
