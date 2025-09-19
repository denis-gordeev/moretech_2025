import json
import asyncio
import logging
import hashlib
from typing import List, Dict, Any
from pathlib import Path
from database import PostgreSQLAnalyzer
from llm_service import LLMAnalyzer
from execution_plan_cache import ExecutionPlanCache
from config import settings

logger = logging.getLogger(__name__)


class CacheWarmupService:
    """Сервис для предварительного кэширования тестовых запросов"""

    def __init__(self):
        self.db_analyzer = PostgreSQLAnalyzer()
        # Используем только первую модель для warmup
        first_model = settings.get_model_by_index(0)
        if not first_model:
            raise ValueError("No LLM model available for warmup")
        self.llm_analyzer = LLMAnalyzer(selected_model=first_model)
        self.execution_plan_cache = ExecutionPlanCache()
        logger.info(f"Cache warmup using model: {first_model.name} ({first_model.model})")
        
        # Ищем файл test_queries.json в разных возможных местах
        possible_paths = [
            Path(__file__).parent.parent / "test_queries.json",  # ../test_queries.json
            Path("/app/test_queries.json"),  # В контейнере
            Path("test_queries.json"),  # В текущей директории
        ]

        self.test_queries_file = None
        for path in possible_paths:
            if path.exists():
                self.test_queries_file = path
                break
        
        # Cache directory for persistent storage
        # Try different paths for different environments
        possible_cache_paths = [
            Path("/app/cache"),  # Docker container path
            Path(__file__).parent.parent / "cache",  # Local development path
            Path("cache"),  # Current directory
        ]
        
        self.cache_dir = None
        for path in possible_cache_paths:
            if path.exists() or path.parent.exists():
                self.cache_dir = path
                break
        
        if not self.cache_dir:
            # Create cache directory in the most appropriate location
            self.cache_dir = Path("/app/cache") if Path("/app").exists() else Path(__file__).parent.parent / "cache"
        
        self.cache_dir.mkdir(exist_ok=True)
        logger.info(f"Cache directory: {self.cache_dir}")

    async def load_test_queries(self) -> List[Dict[str, Any]]:
        """Загружает тестовые запросы из файла"""
        if not self.test_queries_file:
            logger.error("Test queries file not found")
            return []

        try:
            with open(self.test_queries_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("test_queries", [])
        except Exception as e:
            logger.error(f"Failed to load test queries: {e}")
            return []

    def _get_cache_file_path(self, model_name: str) -> Path:
        """Получает путь к файлу кэша для конкретной модели"""
        # Создаем безопасное имя файла из названия модели
        safe_model_name = hashlib.md5(model_name.encode()).hexdigest()[:8]
        return self.cache_dir / f"cache_{safe_model_name}.json"

    def _create_cache_key(self, model_name: str, query: str, execution_plan: Dict[str, Any]) -> str:
        """Создает ключ кэша для модели, запроса и плана выполнения"""
        plan_summary = {
            "total_cost": execution_plan.get("Total Cost", 0),
            "execution_time": execution_plan.get("Actual Total Time", 0),
            "rows": execution_plan.get("Actual Rows", 0),
            "node_type": execution_plan.get("Node Type", ""),
        }
        cache_string = f"{model_name}|{query}|{json.dumps(plan_summary, sort_keys=True)}"
        return hashlib.md5(cache_string.encode("utf-8")).hexdigest()

    async def save_cache_to_file(self, model_name: str, cache_data: Dict[str, Any]) -> bool:
        """Сохраняет кэш в файл"""
        try:
            cache_file = self._get_cache_file_path(model_name)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Cache saved to file: {cache_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save cache to file: {e}")
            return False

    async def load_cache_from_file(self, model_name: str) -> Dict[str, Any]:
        """Загружает кэш из файла"""
        try:
            cache_file = self._get_cache_file_path(model_name)
            if not cache_file.exists():
                logger.info(f"Cache file not found: {cache_file}")
                return {}
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            logger.info(f"Cache loaded from file: {cache_file} ({len(cache_data)} entries)")
            return cache_data
        except Exception as e:
            logger.error(f"Failed to load cache from file: {e}")
            return {}

    async def save_rewritten_example(self, name: str, original_query: str, rewritten_query: str) -> bool:
        """Сохраняет переписанный пример запроса в файл"""
        try:
            rewritten_file = self.cache_dir / "rewritten_examples.json"
            
            # Загружаем существующие переписанные примеры
            rewritten_examples = []
            if rewritten_file.exists():
                with open(rewritten_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    rewritten_examples = data.get("rewritten_examples", [])
            
            # Проверяем, есть ли уже такой пример
            existing_example = next((ex for ex in rewritten_examples if ex["name"] == name), None)
            
            if existing_example:
                existing_example["original_query"] = original_query
                existing_example["rewritten_query"] = rewritten_query
                existing_example["updated_at"] = f"{asyncio.get_event_loop().time()}"
                logger.info(f"Updated rewritten example: {name}")
            else:
                rewritten_examples.append({
                    "name": name,
                    "original_query": original_query,
                    "rewritten_query": rewritten_query,
                    "created_at": f"{asyncio.get_event_loop().time()}"
                })
                logger.info(f"Added new rewritten example: {name}")
            
            # Сохраняем обновленный файл
            with open(rewritten_file, 'w', encoding='utf-8') as f:
                json.dump({"rewritten_examples": rewritten_examples}, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save rewritten example: {e}")
            return False

    async def load_rewritten_examples(self) -> List[Dict[str, Any]]:
        """Загружает переписанные примеры из файла"""
        try:
            rewritten_file = self.cache_dir / "rewritten_examples.json"
            if not rewritten_file.exists():
                logger.info("Rewritten examples file not found")
                return []
            
            with open(rewritten_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                examples = data.get("rewritten_examples", [])
            
            logger.info(f"Loaded {len(examples)} rewritten examples")
            return examples
            
        except Exception as e:
            logger.error(f"Failed to load rewritten examples: {e}")
            return []

    async def warmup_cache_for_all_models(self, max_queries: int = 5, max_concurrent: int = 3) -> Dict[str, Any]:
        """Кэширует примеры для всех доступных моделей с ограничением параллельности"""
        logger.info("Starting cache warmup for ALL models with async semaphore...")
        
        # Получаем все доступные модели
        all_models = settings.get_available_models()
        logger.info(f"Found {len(all_models)} models to warmup")
        
        # Загружаем тестовые запросы
        test_queries = await self.load_test_queries()
        if not test_queries:
            logger.warning("No test queries found for warmup")
            return {"status": "no_queries", "processed": 0, "errors": 0}

        # Ограничиваем количество запросов для кэширования
        queries_to_process = test_queries[:max_queries]
        
        # Создаем семафор для ограничения параллельности
        semaphore = asyncio.Semaphore(max_concurrent)
        
        total_processed = 0
        total_errors = 0
        model_results = {}

        async def warmup_model(model):
            """Прогрев кэша для одной модели"""
            async with semaphore:
                try:
                    logger.info(f"Warming up cache for model: {model.name} ({model.model})")
                    
                    # Создаем анализатор для этой модели
                    model_analyzer = LLMAnalyzer(selected_model=model)
                    
                    # Загружаем существующий кэш из файла
                    file_cache = await self.load_cache_from_file(model.model)
                    if file_cache:
                        # Загружаем кэш в анализатор
                        model_analyzer._cache.update(file_cache)
                        logger.info(f"Loaded {len(file_cache)} entries from file cache for {model.name}")
                    
                    model_processed = 0
                    model_errors = 0
                    
                    # Создаем семафор для запросов внутри модели тоже
                    query_semaphore = asyncio.Semaphore(2)
                    
                    async def process_query(i, query_data):
                        """Обрабатывает один запрос"""
                        async with query_semaphore:
                            try:
                                query = query_data["query"]
                                name = query_data["name"]
                                
                                # Проверяем, есть ли уже кэш для этого запроса
                                cache_key = self._create_cache_key(model.model, query, {})
                                if cache_key in model_analyzer._cache:
                                    logger.info(f"Skipping {name} - already cached for {model.name}")
                                    return 0, 0
                                
                                logger.info(f"Processing query {i+1}/{len(queries_to_process)} for {model.name}: {name}")
                                
                                # Получаем план выполнения (с кэшированием)
                                database_url = self.db_analyzer.database_url
                                cached_plan = self.execution_plan_cache.get_plan(query, database_url)
                                if cached_plan:
                                    logger.info(f"Using cached execution plan for {name}")
                                    plan_data = cached_plan
                                else:
                                    logger.info(f"Generating new execution plan for {name}")
                                    plan_data = await self.db_analyzer.analyze_query_performance(query)
                                    # Сохраняем план в кэш
                                    self.execution_plan_cache.set_plan(query, database_url, plan_data)
                                
                                # Анализируем с помощью LLM (это добавит результат в кэш)
                                llm_result = await model_analyzer.analyze_query_with_llm(query, plan_data["plan_json"])
                                
                                # Сохраняем переписанный запрос, если есть
                                if llm_result.get("rewritten_query"):
                                    await self.save_rewritten_example(name, query, llm_result["rewritten_query"])
                                
                                logger.info(f"Successfully cached query for {model.name}: {name}")
                                return 1, 0
                                
                            except Exception as e:
                                logger.error(f"Failed to process query '{name}' for {model.name}: {e}")
                                return 0, 1
                    
                    # Запускаем обработку всех запросов параллельно для модели
                    tasks = [process_query(i, query_data) for i, query_data in enumerate(queries_to_process)]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    for result in results:
                        if isinstance(result, Exception):
                            model_errors += 1
                        else:
                            processed, errors = result
                            model_processed += processed
                            model_errors += errors
                    
                    # Сохраняем кэш в файл
                    await self.save_cache_to_file(model.model, model_analyzer._cache)
                    
                    logger.info(f"Model {model.name} warmup completed: {model_processed} processed, {model_errors} errors")
                    
                    return {
                        "model": model.name,
                        "processed": model_processed,
                        "errors": model_errors,
                        "cache_size": len(model_analyzer._cache)
                    }
                    
                except Exception as e:
                    logger.error(f"Failed to warmup model {model.name}: {e}")
                    return {
                        "model": model.name,
                        "processed": 0,
                        "errors": 1,
                        "cache_size": 0
                    }

        # Запускаем прогрев всех моделей параллельно
        model_tasks = [warmup_model(model) for model in all_models]
        model_results_list = await asyncio.gather(*model_tasks, return_exceptions=True)
        
        # Собираем результаты
        for result in model_results_list:
            if isinstance(result, Exception):
                logger.error(f"Model warmup task failed: {result}")
                total_errors += 1
            else:
                model_results[result["model"]] = {
                    "processed": result["processed"],
                    "errors": result["errors"],
                    "cache_size": result["cache_size"]
                }
                total_processed += result["processed"]
                total_errors += result["errors"]

        warmup_result = {
            "status": "completed",
            "total_processed": total_processed,
            "total_errors": total_errors,
            "total_queries": len(queries_to_process),
            "models": model_results,
        }

        logger.info(f"All models cache warmup completed: {total_processed} total processed, {total_errors} total errors")
        return warmup_result

    async def warmup_cache(self, max_queries: int = 5) -> Dict[str, Any]:
        """
        Предварительно кэширует тестовые запросы для первой модели
        """
        logger.info(f"Starting cache warmup for model: {self.llm_analyzer.model}...")

        # Загружаем тестовые запросы
        test_queries = await self.load_test_queries()
        if not test_queries:
            logger.warning("No test queries found for warmup")
            return {"status": "no_queries", "processed": 0, "errors": 0}

        # Ограничиваем количество запросов для кэширования
        queries_to_process = test_queries[:max_queries]

        processed = 0
        errors = 0
        results = []

        for i, query_data in enumerate(queries_to_process):
            try:
                query = query_data["query"]
                name = query_data["name"]

                logger.info(f"Processing query {i+1}/{len(queries_to_process)}: {name}")

                # Получаем план выполнения (с кэшированием)
                database_url = self.db_analyzer.database_url
                cached_plan = self.execution_plan_cache.get_plan(query, database_url)
                if cached_plan:
                    logger.info(f"Using cached execution plan for {name}")
                    plan_data = cached_plan
                else:
                    logger.info(f"Generating new execution plan for {name}")
                    plan_data = await self.db_analyzer.analyze_query_performance(query)
                    # Сохраняем план в кэш
                    self.execution_plan_cache.set_plan(query, database_url, plan_data)

                # Анализируем с помощью LLM (это добавит результат в кэш)
                llm_result = await self.llm_analyzer.analyze_query_with_llm(query, plan_data["plan_json"])

                results.append(
                    {
                        "name": name,
                        "query": query[:100] + "..." if len(query) > 100 else query,
                        "status": "success",
                        "has_rewritten_query": llm_result.get("rewritten_query") is not None,
                        "recommendations_count": len(llm_result.get("recommendations", [])),
                    }
                )

                processed += 1
                logger.info(f"Successfully cached query: {name}")

            except Exception as e:
                logger.error(f"Failed to process query '{name}': {e}")
                errors += 1
                results.append(
                    {
                        "name": name,
                        "query": (
                            query_data["query"][:100] + "..." if len(query_data["query"]) > 100 else query_data["query"]
                        ),
                        "status": "error",
                        "error": str(e),
                    }
                )

        # Получаем статистику кэша
        cache_stats = self.llm_analyzer.get_cache_stats()

        warmup_result = {
            "status": "completed",
            "processed": processed,
            "errors": errors,
            "total_queries": len(queries_to_process),
            "cache_stats": cache_stats,
            "results": results,
        }

        logger.info(f"Cache warmup completed for model {self.llm_analyzer.model}: {processed} processed, {errors} errors")
        return warmup_result

    async def warmup_new_examples(self, max_queries: int = 5) -> Dict[str, Any]:
        """
        Кэширует только новые примеры (пропускает уже закэшированные)
        """
        logger.info(f"Starting cache warmup for new examples using model: {self.llm_analyzer.model}...")

        # Загружаем тестовые запросы
        test_queries = await self.load_test_queries()
        if not test_queries:
            logger.warning("No test queries found for warmup")
            return {"status": "no_queries", "processed": 0, "errors": 0}

        # Получаем статистику кэша, чтобы понять, какие запросы уже закэшированы
        cache_stats = self.llm_analyzer.get_cache_stats()
        current_cache_size = cache_stats.get("size", 0)

        # Если кэш пустой, кэшируем первые запросы
        if current_cache_size == 0:
            logger.info("Cache is empty, using regular warmup")
            return await self.warmup_cache(max_queries)

        # Иначе кэшируем запросы, начиная с позиции после уже закэшированных
        start_index = min(current_cache_size, len(test_queries))
        queries_to_process = test_queries[start_index:start_index + max_queries]

        if not queries_to_process:
            logger.info("No new queries to cache")
            return {"status": "no_new_queries", "processed": 0, "errors": 0}

        processed = 0
        errors = 0
        results = []

        for i, query_data in enumerate(queries_to_process):
            try:
                query = query_data["query"]
                name = query_data["name"]

                logger.info(f"Processing new query {i+1}/{len(queries_to_process)}: {name}")

                # Получаем план выполнения
                plan_data = await self.db_analyzer.analyze_query_performance(query)

                # Анализируем с помощью LLM (это добавит результат в кэш)
                llm_result = await self.llm_analyzer.analyze_query_with_llm(query, plan_data["plan_json"])

                results.append(
                    {
                        "name": name,
                        "query": query[:100] + "..." if len(query) > 100 else query,
                        "status": "success",
                        "has_rewritten_query": llm_result.get("rewritten_query") is not None,
                        "recommendations_count": len(llm_result.get("recommendations", [])),
                    }
                )

                processed += 1
                logger.info(f"Successfully cached new query: {name}")

            except Exception as e:
                logger.error(f"Failed to process new query '{name}': {e}")
                errors += 1
                results.append(
                    {
                        "name": name,
                        "query": (
                            query_data["query"][:100] + "..." if len(query_data["query"]) > 100 else query_data["query"]
                        ),
                        "status": "error",
                        "error": str(e),
                    }
                )

        # Получаем обновленную статистику кэша
        updated_cache_stats = self.llm_analyzer.get_cache_stats()

        warmup_result = {
            "status": "completed",
            "processed": processed,
            "errors": errors,
            "total_queries": len(queries_to_process),
            "cache_stats": updated_cache_stats,
            "results": results,
        }

        logger.info(f"New examples cache warmup completed for model {self.llm_analyzer.model}: {processed} processed, {errors} errors")
        return warmup_result

    async def test_cache_hit(self, query: str) -> Dict[str, Any]:
        """
        Тестирует попадание в кэш для конкретного запроса (использует первую модель)
        """
        try:
            # Получаем план выполнения
            plan_data = await self.db_analyzer.analyze_query_performance(query)

            # Анализируем с помощью LLM
            start_time = asyncio.get_event_loop().time()
            llm_result = await self.llm_analyzer.analyze_query_with_llm(query, plan_data["plan_json"])
            end_time = asyncio.get_event_loop().time()

            return {
                "status": "success",
                "execution_time": end_time - start_time,
                "has_rewritten_query": llm_result.get("rewritten_query") is not None,
                "recommendations_count": len(llm_result.get("recommendations", [])),
                "cache_stats": self.llm_analyzer.get_cache_stats(),
            }

        except Exception as e:
            logger.error(f"Failed to test cache hit for model {self.llm_analyzer.model}: {e}")
            return {"status": "error", "error": str(e)}
