# Code Quality Setup

This document describes the code quality tools and pre-commit hooks configured for the PostgreSQL Query Analyzer project.

## Overview

The project uses several tools to maintain code quality:

- **Black**: Code formatter with 120 character line length
- **flake8**: Linting with additional plugins for docstrings, import order, and bug detection
- **MyPy**: Static type checking
- **isort**: Import sorting compatible with Black
- **autoflake**: Removes unused imports and variables
- **pyupgrade**: Upgrades Python syntax to modern patterns
- **bandit**: Security vulnerability scanning
- **pre-commit**: Automated hooks that run before each commit

## Quick Setup

### Option 1: Using the Setup Script (Recommended)
```bash
# Run the automated setup script
./scripts/setup-pre-commit.sh
```

### Option 2: Manual Setup
```bash
# Install development dependencies
make install-dev

# Or install pre-commit manually
pip install pre-commit
pre-commit install

# Run initial formatting
make format
```

## Available Commands

### Code Formatting
```bash
make format              # Format code with black and sort imports with isort
```

### Linting
```bash
make lint               # Run flake8, mypy, and bandit
make lint-fix           # Auto-fix issues where possible
```

### Pre-commit
```bash
make pre-commit-run     # Run pre-commit on all files
make pre-commit-install # Install pre-commit hooks
```

### Comprehensive Check
```bash
make check-code         # Run formatting, linting, and tests
```

## Configuration Files

### pyproject.toml
Contains configuration for:
- Black (line length: 120)
- MyPy type checking settings
- isort import sorting
- pytest and coverage settings

### .pre-commit-config.yaml
Defines the pre-commit hooks that run automatically:
- Black formatting
- isort import sorting
- flake8 linting
- MyPy type checking
- Security scanning with bandit
- General code quality checks

### setup.cfg
Additional configuration for:
- flake8 rules and exclusions
- MyPy module-specific settings
- Test and coverage configuration

## Code Quality Rules

### Line Length
- Maximum line length: **120 characters**
- Enforced by Black and flake8

### Import Sorting
- Imports are sorted using isort with Black profile
- Standard library imports first, then third-party, then local imports

### Type Hints
- Type hints are required for public functions and methods
- MyPy enforces strict type checking with some exceptions for tests

### Security
- Bandit scans for common security vulnerabilities
- Excludes test files from security scanning

## Pre-commit Hooks

The following hooks run automatically on each commit:

1. **trailing-whitespace**: Removes trailing whitespace
2. **end-of-file-fixer**: Ensures files end with newline
3. **check-yaml/json/toml**: Validates file formats
4. **check-added-large-files**: Prevents large files from being committed
5. **autoflake**: Removes unused imports and variables
6. **pyupgrade**: Upgrades Python syntax
7. **isort**: Sorts imports
8. **black**: Formats code
9. **flake8**: Lints code
10. **mypy**: Type checking
11. **bandit**: Security scanning

## Bypassing Hooks (Not Recommended)

If you need to bypass pre-commit hooks (e.g., for urgent fixes):

```bash
git commit --no-verify -m "Emergency fix"
```

**Note**: This should be used sparingly and the code should be cleaned up in a follow-up commit.

## IDE Integration

### VS Code
Install these extensions for better integration:
- Python (ms-python.python)
- Black Formatter (ms-python.black-formatter)
- Flake8 (ms-python.flake8)
- MyPy Type Checker (ms-python.mypy-type-checker)

Add to your VS Code settings.json:
```json
{
    "python.formatting.provider": "black",
    "python.formatting.blackArgs": ["--line-length", "120"],
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.mypyEnabled": true,
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    }
}
```

### PyCharm
1. Install Black formatter plugin
2. Configure Black with line length 120
3. Enable flake8 and MyPy in the inspections
4. Set up format on save

## Troubleshooting

### Pre-commit hooks failing
If pre-commit hooks fail:
1. Run `make lint-fix` to auto-fix issues
2. Review and fix any remaining issues manually
3. Run `make check-code` to verify everything is working

### MyPy errors
- Add type hints to resolve type checking errors
- Use `# type: ignore` comments sparingly for third-party library issues
- Update type stubs if needed

### Flake8 errors
- Most formatting issues are auto-fixed by Black
- Review docstring requirements (can be disabled for specific files if needed)
- Check import order and unused imports

### Performance
If pre-commit hooks are slow:
- Pre-commit caches environments, so first run is slower
- Consider running `pre-commit run --all-files` periodically instead of on every commit

## Contributing

When contributing to the project:
1. Run `./scripts/setup-pre-commit.sh` after cloning
2. Ensure all pre-commit hooks pass before submitting PRs
3. Run `make check-code` before pushing changes
4. Follow the established code style and quality standards

## Updating Tools

To update code quality tools:
1. Update versions in `backend/requirements.txt`
2. Update versions in `.pre-commit-config.yaml`
3. Run `pre-commit autoupdate` to update pre-commit hooks
4. Test the updates with `make check-code`
