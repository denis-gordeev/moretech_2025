# Cache Directory

This directory contains persistent cache files that improve application startup performance.

## Files

- `cache_*.json` - LLM analysis cache files for different models
- `execution_plans.json` - Cached execution plans for common queries
- `rewritten_examples.json` - Collection of rewritten query examples

## Purpose

These cache files are automatically generated during application startup and help:

1. **Reduce startup time** - Pre-cached LLM analyses avoid repeated API calls
2. **Improve response time** - Cached execution plans speed up query analysis
3. **Preserve optimizations** - Rewritten queries are saved for reuse
4. **Enable offline development** - Cached results work without API access

## Maintenance

- Cache files are automatically updated during application startup
- Files are safe to delete - they will be regenerated as needed
- Keep cache files in version control for consistent team development

## Configuration

Cache behavior can be configured through:
- `MAX_CACHE_SIZE` environment variable
- `CACHE_EXPIRY_HOURS` environment variable
- Startup parameters in `main.py`