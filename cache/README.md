# LLM Cache Directory

This directory contains persistent cache files for LLM query analysis results.

## File Structure

- `cache_<model_hash>.json` - Cache files for specific models
- `cache_sample.json` - Example cache file format
- `README.md` - This documentation

## Cache File Format

Each cache file contains a JSON object where:
- **Keys**: MD5 hashes of `model_name|query|execution_plan_summary`
- **Values**: LLM analysis results including:
  - `rewritten_query`: Optimized SQL query (or null)
  - `resource_metrics`: CPU, memory, disk I/O estimates
  - `recommendations`: Array of optimization recommendations
  - `warnings`: Array of performance warnings

## Model Hash Mapping

- `cache_827b9586.json` - deepseek/deepseek-chat-v3.1
- `cache_4f51dd04.json` - qwen/qwen3-32b
- `cache_1347aa4b.json` - z-ai/glm-4.5
- etc.

## Benefits

1. **Faster Startup**: Pre-cached results load instantly
2. **Reduced API Costs**: Avoid redundant LLM calls
3. **Consistent Results**: Same query+model = same analysis
4. **Offline Capability**: Works without LLM API for cached queries

## Cache Management

- **Max Size**: 10,000 entries per model
- **LRU Eviction**: Oldest entries removed when full
- **Auto-Save**: Cache saved to files after each analysis
- **Auto-Load**: Cache loaded from files at startup

## Manual Cache Operations

```bash
# Warm up cache for all models
curl -X POST "http://localhost:8000/cache/warmup/all-models?max_queries=20"

# Check cache statistics
curl -X GET "http://localhost:8000/cache/stats"

# Clear cache
curl -X POST "http://localhost:8000/cache/clear"
```
