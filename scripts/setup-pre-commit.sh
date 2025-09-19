#!/bin/bash

# Setup script for pre-commit hooks and code quality tools
# This script installs and configures all the code quality tools

set -e

echo "🚀 Setting up pre-commit hooks and code quality tools..."

# Check if we're in the correct directory
if [ ! -f "pyproject.toml" ] || [ ! -f ".pre-commit-config.yaml" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is required but not found"
    exit 1
fi

# Check if pip is available
if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
    echo "❌ Error: pip is required but not found"
    exit 1
fi

# Use pip3 if pip is not available
PIP_CMD="pip"
if ! command -v pip &> /dev/null; then
    PIP_CMD="pip3"
fi

echo "📦 Installing/upgrading required packages..."

# Install pre-commit and code quality tools
$PIP_CMD install --upgrade pre-commit black flake8 mypy isort autoflake pyupgrade bandit

# Install additional flake8 plugins
$PIP_CMD install --upgrade flake8-docstrings flake8-import-order flake8-bugbear

# Install type stubs for mypy
$PIP_CMD install --upgrade types-requests types-PyYAML types-python-dateutil

echo "🔧 Installing pre-commit hooks..."

# Install pre-commit hooks
pre-commit install

# Install pre-commit hook for commit messages (optional)
pre-commit install --hook-type commit-msg || echo "⚠️  Commit message hooks not installed (optional)"

echo "🎨 Running initial code formatting..."

# Run autoflake to remove unused imports
echo "  - Removing unused imports..."
find backend -name "*.py" -type f -exec autoflake --in-place --remove-all-unused-imports --remove-unused-variables {} \; || echo "⚠️  autoflake completed with warnings"

# Run pyupgrade to upgrade syntax
echo "  - Upgrading Python syntax..."
find backend -name "*.py" -type f -exec pyupgrade --py38-plus {} \; || echo "⚠️  pyupgrade completed with warnings"

# Format code with black
echo "  - Formatting code with black..."
black --line-length 120 backend/ || echo "⚠️  black completed with warnings"

# Sort imports with isort
echo "  - Sorting imports with isort..."
isort --profile black --line-length 120 backend/ || echo "⚠️  isort completed with warnings"

echo "🔍 Running initial code quality checks..."

# Run flake8 linting
echo "  - Running flake8..."
if flake8 backend/; then
    echo "    ✅ flake8 checks passed"
else
    echo "    ⚠️  flake8 found issues (will be fixed by pre-commit)"
fi

# Run mypy type checking (less strict for initial setup)
echo "  - Running mypy..."
if mypy backend/ --config-file pyproject.toml --ignore-missing-imports; then
    echo "    ✅ mypy checks passed"
else
    echo "    ⚠️  mypy found issues (will be fixed by pre-commit)"
fi

# Run bandit security check
echo "  - Running bandit security check..."
if bandit -r backend/ -x backend/tests/ --format json > /dev/null 2>&1; then
    echo "    ✅ bandit security checks passed"
else
    echo "    ⚠️  bandit found potential security issues (review manually)"
fi

echo "✅ Pre-commit setup complete!"
echo ""
echo "📋 What was configured:"
echo "  • Pre-commit hooks that run on each commit"
echo "  • Black code formatter (120 character line length)"
echo "  • flake8 linting with additional plugins"
echo "  • MyPy type checking"
echo "  • isort import sorting"
echo "  • autoflake unused import removal"
echo "  • pyupgrade syntax modernization"
echo "  • bandit security scanning"
echo ""
echo "🎯 How to use:"
echo "  • Code will be automatically formatted and checked on each commit"
echo "  • Run 'make format' to format code manually"
echo "  • Run 'make lint' to run all linting tools"
echo "  • Run 'make pre-commit-run' to run pre-commit on all files"
echo "  • Run 'make check-code' for comprehensive quality checks"
echo ""
echo "🚀 You're all set! Happy coding!"
