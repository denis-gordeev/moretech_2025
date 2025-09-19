#!/usr/bin/env python3
"""
Standalone script to run comprehensive analysis of all query examples
across all LLM models with semaphore(10) concurrency control.
"""

import asyncio
import json
import time
from typing import Any, Dict, List

import aiohttp

API_BASE = "http://193.246.150.25:8000"


async def fetch_database_profiles(session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """Получает все профили баз данных"""
    async with session.get(f"{API_BASE}/database/profiles") as response:
        if response.status == 200:
            data = await response.json()
            return data.get("profiles", [])
        else:
            print(f"Failed to fetch database profiles: {response.status}")
            return []


async def fetch_models(session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """Получает все доступные LLM модели"""
    async with session.get(f"{API_BASE}/models") as response:
        if response.status == 200:
            data = await response.json()
            return data.get("models", [])
        else:
            print(f"Failed to fetch models: {response.status}")
            return []


async def fetch_examples(session: aiohttp.ClientSession, database_profile_id: str = None) -> List[Dict[str, Any]]:
    """Получает примеры запросов"""
    url = f"{API_BASE}/examples"
    if database_profile_id:
        url += f"?database_profile_id={database_profile_id}"

    async with session.get(url) as response:
        if response.status == 200:
            data = await response.json()
            return data.get("examples", [])
        else:
            print(f"Failed to fetch examples: {response.status}")
            return []


async def analyze_single_query(
    session: aiohttp.ClientSession, database_profile_id: str, model_name: str, query: str, semaphore: asyncio.Semaphore
) -> Dict[str, Any]:
    """Анализирует один запрос с одной моделью"""
    async with semaphore:
        try:
            # Сначала получаем план выполнения
            plan_payload = {"query": query, "database_profile_id": database_profile_id}

            async with session.post(f"{API_BASE}/analyze/execution-plan", json=plan_payload) as plan_response:
                if plan_response.status != 200:
                    error_text = await plan_response.text()
                    print(f"Failed to get execution plan for model {model_name}: {plan_response.status} - {error_text}")
                    return None

                plan_data = await plan_response.json()

            # Затем запускаем LLM анализ
            llm_payload = {"query": query, "database_profile_id": database_profile_id, "model_name": model_name}

            async with session.post(f"{API_BASE}/analyze/llm", json=llm_payload) as llm_response:
                if llm_response.status != 200:
                    error_text = await llm_response.text()
                    print(f"Failed LLM analysis for model {model_name}: {llm_response.status} - {error_text}")
                    return None

                llm_data = await llm_response.json()

            # Получаем database_url из профиля
            async with session.get(f"{API_BASE}/database/profiles") as profiles_response:
                if profiles_response.status == 200:
                    profiles_data = await profiles_response.json()
                    target_profile = None
                    for profile in profiles_data.get("profiles", []):
                        if profile["id"] == database_profile_id:
                            target_profile = profile
                            break

                    database_url = (
                        f"postgresql://{target_profile['username']}:***@{target_profile['host']}:{target_profile['port']}/{target_profile['database']}"
                        if target_profile
                        else "unknown"
                    )
                else:
                    database_url = "unknown"

            result = {
                "database_url": database_url,
                "llm_model": model_name,
                "query": query,
                "explain_result": plan_data,
                "llm_response": llm_data,
            }

            print(f"✓ Successfully analyzed query with model {model_name}")
            return result

        except Exception as e:
            print(f"✗ Error analyzing query with model {model_name}: {e}")
            return None


async def main():
    """Основная функция для запуска комплексного анализа"""
    print("🚀 Starting comprehensive analysis...")

    async with aiohttp.ClientSession() as session:
        # Получаем все необходимые данные
        print("📋 Fetching database profiles...")
        profiles = await fetch_database_profiles(session)
        if not profiles:
            print("❌ No database profiles found")
            return

        # Используем первый профиль
        first_profile = profiles[0]
        print(f"📊 Using database profile: {first_profile['name']} ({first_profile['id']})")

        print("🤖 Fetching available models...")
        models = await fetch_models(session)
        if not models:
            print("❌ No models found")
            return

        print(f"📝 Found {len(models)} models:")
        for model in models:
            print(f"  - {model['name']}")

        print("📑 Fetching query examples...")
        examples = await fetch_examples(session, first_profile["id"])
        if not examples:
            print("❌ No examples found")
            return

        print(f"📊 Found {len(examples)} query examples")

        # Создаем задачи для всех комбинаций
        total_tasks = len(models) * len(examples)
        print(f"🔄 Starting {total_tasks} analysis tasks with semaphore(10)...")

        semaphore = asyncio.Semaphore(10)
        tasks = []

        for model in models:
            for example in examples:
                task = analyze_single_query(
                    session=session,
                    database_profile_id=first_profile["id"],
                    model_name=model["name"],
                    query=example["query"],
                    semaphore=semaphore,
                )
                tasks.append(task)

        # Запускаем все задачи
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        # Обрабатываем результаты
        successful_results = []
        failed_count = 0

        for result in results:
            if isinstance(result, Exception):
                print(f"❌ Task failed with exception: {result}")
                failed_count += 1
            elif result is None:
                failed_count += 1
            else:
                successful_results.append(result)

        # Выводим статистику
        print(f"\n📈 Analysis completed in {end_time - start_time:.2f} seconds")
        print(f"✅ Successful: {len(successful_results)}")
        print(f"❌ Failed: {failed_count}")
        print(f"📊 Total: {len(results)}")

        # Сохраняем результаты в файл
        output_file = f"comprehensive_analysis_results_{int(time.time())}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "metadata": {
                        "timestamp": time.time(),
                        "duration_seconds": end_time - start_time,
                        "database_profile": first_profile,
                        "total_models": len(models),
                        "total_examples": len(examples),
                        "total_tasks": total_tasks,
                        "successful_results": len(successful_results),
                        "failed_results": failed_count,
                    },
                    "results": successful_results,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        print(f"💾 Results saved to: {output_file}")

        # Показываем несколько примеров результатов
        if successful_results:
            print(f"\n📋 Sample results:")
            for i, result in enumerate(successful_results[:3]):
                print(f"  {i+1}. Model: {result['llm_model']}")
                print(f"     Query: {result['query'][:60]}...")
                if "analysis" in result.get("llm_response", {}):
                    analysis = result["llm_response"]["analysis"]
                    print(f"     Analysis: {analysis[:100]}...")
                print()


if __name__ == "__main__":
    asyncio.run(main())
