#!/usr/bin/env python3
"""
Script to add successful comprehensive analysis results to the warmup cache files.
This will allow the results to be reused in future cache warmup operations.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict


def create_query_hash(query: str, execution_plan: Dict[str, Any], model_name: str) -> str:
    """
    Creates a hash for the query, execution plan, and model for caching
    (matches the logic in LLMAnalyzer._create_query_hash)
    """
    # Create plan summary similar to LLMAnalyzer
    plan_summary = {
        "total_cost": execution_plan.get("Total Cost", 0),
        "execution_time": execution_plan.get("Actual Total Time", 0),
        "rows": execution_plan.get("Actual Rows", 0),
        "node_type": execution_plan.get("Node Type", ""),
    }

    # Include model in hash for separation by models
    cache_string = f"{model_name}|{query}|{json.dumps(plan_summary, sort_keys=True)}"
    return hashlib.md5(cache_string.encode("utf-8")).hexdigest()


def get_model_cache_filename(model_name: str) -> str:
    """
    Gets the cache filename for a model (matches cache_warmup.py logic)
    Uses MD5 hash of model identifier like the original CacheWarmupService
    """
    # Map model names to their identifiers (based on actual API response)
    model_mapping = {
        "Основная модель": "qwen/qwen3-32b",
        "Модель 1": "z-ai/glm-4.5",
        "Модель 2": "x-ai/grok-code-fast-1",
        "Модель 3": "qwen/qwen3-next-80b-a3b-thinking",
        "Модель 4": "qwen/qwen3-4b:free",
        "Модель 5": "deepseek/deepseek-chat-v3.1",
        "Модель 7": "qwen/qwen3-32b",
    }

    model_id = model_mapping.get(model_name, model_name.lower().replace(" ", "_"))
    # Use MD5 hash like CacheWarmupService._get_cache_file_path
    safe_model_name = hashlib.md5(model_id.encode()).hexdigest()[:8]
    return f"cache_{safe_model_name}.json"


def load_existing_cache(cache_file_path: Path) -> Dict[str, Any]:
    """Loads existing cache from file"""
    if cache_file_path.exists():
        try:
            with open(cache_file_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load existing cache from {cache_file_path}: {e}")
    return {}


def save_cache(cache_file_path: Path, cache_data: Dict[str, Any]) -> bool:
    """Saves cache to file"""
    try:
        # Ensure directory exists
        cache_file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(cache_file_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving cache to {cache_file_path}: {e}")
        return False


def process_results_and_update_caches(results_file: str, cache_dir: str = "backend/cache"):
    """
    Processes the comprehensive analysis results and adds them to model cache files
    """
    print(f"📥 Loading results from {results_file}...")

    try:
        with open(results_file, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading results file: {e}")
        return

    results = data.get("results", [])
    metadata = data.get("metadata", {})

    print(f"📊 Found {len(results)} successful results to process")
    print(f"🕒 Original analysis took {metadata.get('duration_seconds', 0):.2f} seconds")

    # Group results by model
    results_by_model = {}
    for result in results:
        model_name = result["llm_model"]
        if model_name not in results_by_model:
            results_by_model[model_name] = []
        results_by_model[model_name].append(result)

    # Process each model's results
    cache_dir_path = Path(cache_dir)
    total_added = 0

    for model_name, model_results in results_by_model.items():
        print(f"\n🤖 Processing model: {model_name} ({len(model_results)} results)")

        # Get cache file path
        cache_filename = get_model_cache_filename(model_name)
        cache_file_path = cache_dir_path / cache_filename

        # Load existing cache
        existing_cache = load_existing_cache(cache_file_path)
        cache_size_before = len(existing_cache)

        # Add new results to cache
        added_count = 0
        skipped_count = 0

        for result in model_results:
            try:
                query = result["query"]
                explain_result = result["explain_result"]
                llm_response = result["llm_response"]

                # Extract execution plan from explain_result
                if "execution_plan" in explain_result:
                    plan_json = explain_result["execution_plan"]
                elif "plan_json" in explain_result:
                    plan_json = explain_result["plan_json"]
                else:
                    print(f"⚠️ Could not find execution plan in result, skipping")
                    skipped_count += 1
                    continue

                # Create cache key (hash)
                cache_key = create_query_hash(query, plan_json, model_name)

                # Check if already exists
                if cache_key in existing_cache:
                    skipped_count += 1
                    continue

                # Add to cache
                existing_cache[cache_key] = llm_response
                added_count += 1

            except Exception as e:
                print(f"⚠️ Error processing result: {e}")
                skipped_count += 1
                continue

        # Save updated cache
        if added_count > 0:
            if save_cache(cache_file_path, existing_cache):
                print(f"✅ Updated cache file: {cache_file_path}")
                print(f"   📈 Before: {cache_size_before} entries")
                print(f"   📈 After: {len(existing_cache)} entries")
                print(f"   ➕ Added: {added_count} new entries")
                print(f"   ⏭️ Skipped: {skipped_count} (duplicates or errors)")
                total_added += added_count
            else:
                print(f"❌ Failed to save cache file: {cache_file_path}")
        else:
            print(f"ℹ️ No new entries to add (all {skipped_count} were duplicates or errors)")

    print(f"\n🎉 Cache update completed!")
    print(f"📊 Total entries added across all models: {total_added}")

    # Show updated cache statistics
    print(f"\n📋 Updated cache file sizes:")
    for model_name in results_by_model.keys():
        cache_filename = get_model_cache_filename(model_name)
        cache_file_path = cache_dir_path / cache_filename
        if cache_file_path.exists():
            try:
                with open(cache_file_path, encoding="utf-8") as f:
                    cache_data = json.load(f)
                print(f"   {model_name}: {len(cache_data)} entries ({cache_filename})")
            except:
                print(f"   {model_name}: Error reading cache file")


def main():
    """Main function"""
    import glob

    print("🔍 Looking for comprehensive analysis results files...")

    # Find the most recent results file
    results_files = glob.glob("comprehensive_analysis_results_*.json")
    if not results_files:
        print("❌ No comprehensive analysis results files found!")
        print("   Expected files matching pattern: comprehensive_analysis_results_*.json")
        return

    # Use the most recent file
    latest_file = max(results_files, key=os.path.getctime)
    print(f"📁 Using latest results file: {latest_file}")

    # Process the results and update caches
    process_results_and_update_caches(latest_file)


if __name__ == "__main__":
    main()
