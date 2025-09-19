import json
import hashlib
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = _BASE_DIR / "cache"

logger = logging.getLogger(__name__)


class ExecutionPlanCache:
    """Кэш для планов выполнения запросов (не зависит от LLM модели)"""

    def __init__(self, cache_dir: Optional[Path] = None):
        self._cache: Dict[str, Any] = {}
        self._cache_max_size = 1000  # Максимальный размер кэша планов
        self._cache_dir = (cache_dir or DEFAULT_CACHE_DIR).resolve()
        self._cache_file = self._cache_dir / "execution_plans.json"
        
        # Создаем директорию если не существует
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Загружаем кэш из файла при инициализации
        self._load_from_file()

    def _create_plan_hash(self, query: str, database_url: str) -> str:
        """
        Создает хэш для запроса и базы данных (без учета LLM модели)
        """
        # Нормализуем database_url, убирая пароли для консистентности
        normalized_db_url = self._normalize_database_url(database_url)
        cache_string = f"{normalized_db_url}|{query}"
        return hashlib.md5(cache_string.encode("utf-8")).hexdigest()

    def _normalize_database_url(self, database_url: str) -> str:
        """
        Нормализует URL базы данных, убирая пароли и другие чувствительные данные
        """
        if "://" in database_url:
            # Заменяем пароль на *** для консистентности
            parts = database_url.split("://")
            if len(parts) == 2:
                protocol = parts[0]
                rest = parts[1]
                if "@" in rest:
                    # Есть аутентификация
                    auth_part, host_part = rest.split("@", 1)
                    if ":" in auth_part:
                        username = auth_part.split(":")[0]
                        normalized_auth = f"{username}:***"
                    else:
                        normalized_auth = auth_part
                    return f"{protocol}://{normalized_auth}@{host_part}"
        return database_url

    def get_plan(self, query: str, database_url: str) -> Optional[Dict[str, Any]]:
        """
        Получает план выполнения из кэша
        """
        plan_hash = self._create_plan_hash(query, database_url)
        if plan_hash in self._cache:
            logger.info(f"Execution plan cache hit for query hash: {plan_hash[:8]}...")
            return self._cache[plan_hash]
        return None

    def set_plan(self, query: str, database_url: str, plan_data: Dict[str, Any]) -> None:
        """
        Сохраняет план выполнения в кэш
        """
        plan_hash = self._create_plan_hash(query, database_url)
        
        # Если кэш переполнен, удаляем самый старый элемент
        if len(self._cache) >= self._cache_max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.info(f"Execution plan cache evicted oldest entry: {oldest_key[:8]}...")

        # Добавляем новый план
        self._cache[plan_hash] = plan_data
        logger.info(f"Execution plan cached: {plan_hash[:8]}... (cache size: {len(self._cache)})")
        
        # Сохраняем в файл
        self._save_to_file()

    def _load_from_file(self) -> None:
        """
        Загружает кэш планов из файла
        """
        try:
            if self._cache_file.exists():
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                logger.info(f"Loaded {len(self._cache)} execution plans from file")
            else:
                logger.info("No execution plan cache file found")
        except Exception as e:
            logger.error(f"Failed to load execution plan cache from file: {e}")
            self._cache = {}

    def _save_to_file(self) -> None:
        """
        Сохраняет кэш планов в файл
        """
        try:
            with open(self._cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(self._cache)} execution plans to file")
        except Exception as e:
            logger.error(f"Failed to save execution plan cache to file: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику кэша планов
        """
        return {
            "cache_size": len(self._cache),
            "cache_max_size": self._cache_max_size,
            "cache_keys": [key[:8] + "..." for key in self._cache.keys()],
            "cache_file": str(self._cache_file)
        }

    def clear_cache(self) -> None:
        """
        Очищает кэш планов
        """
        self._cache.clear()
        self._save_to_file()
        logger.info("Execution plan cache cleared")

    def has_plan(self, query: str, database_url: str) -> bool:
        """
        Проверяет, есть ли план в кэше
        """
        plan_hash = self._create_plan_hash(query, database_url)
        return plan_hash in self._cache

    def save_cache_to_file(self) -> None:
        """
        Сохраняет кэш планов в файл (публичный метод)
        """
        self._save_to_file()

    def load_cache_from_file(self) -> Dict[str, Any]:
        """
        Загружает кэш планов из файла (публичный метод)
        """
        self._load_from_file()
        return self._cache.copy()

    def get_cache_data(self) -> Dict[str, Any]:
        """
        Возвращает копию данных кэша
        """
        return self._cache.copy()

    def load_cache_data(self, cache_data: Dict[str, Any]) -> None:
        """
        Загружает данные кэша из внешнего источника
        """
        if cache_data:
            self._cache.update(cache_data)
            logger.info(f"Loaded {len(cache_data)} execution plans from external cache")
            # Сохраняем в файл
            self._save_to_file()

    async def precompute_execution_plans(self, db_analyzer, test_queries: List[Dict[str, Any]], max_queries: int = 10) -> Dict[str, Any]:
        """
        Предварительно вычисляет планы выполнения для тестовых запросов
        """
        logger.info(f"Pre-computing execution plans for {min(len(test_queries), max_queries)} queries...")
        
        database_url = db_analyzer.database_url
        processed = 0
        errors = 0
        results = []

        for i, query_data in enumerate(test_queries[:max_queries]):
            try:
                query = query_data["query"]
                name = query_data["name"]

                # Проверяем, есть ли уже кэш для этого запроса
                if self.has_plan(query, database_url):
                    logger.info(f"Skipping {name} - execution plan already cached")
                    continue

                logger.info(f"Pre-computing execution plan {i+1}/{min(len(test_queries), max_queries)}: {name}")

                # Получаем план выполнения
                plan_data = await db_analyzer.analyze_query_performance(query)
                
                # Сохраняем план в кэш
                self.set_plan(query, database_url, plan_data)

                results.append({
                    "name": name,
                    "query": query[:100] + "..." if len(query) > 100 else query,
                    "status": "success",
                    "total_cost": plan_data.get("total_cost", 0),
                    "execution_time": plan_data.get("execution_time", 0)
                })

                processed += 1
                logger.info(f"Successfully pre-computed execution plan: {name}")

            except Exception as e:
                logger.error(f"Failed to pre-compute execution plan for '{name}': {e}")
                errors += 1
                results.append({
                    "name": name,
                    "query": query_data["query"][:100] + "..." if len(query_data["query"]) > 100 else query_data["query"],
                    "status": "error",
                    "error": str(e)
                })

        # Сохраняем кэш в файл
        self.save_cache_to_file()

        precompute_result = {
            "status": "completed",
            "processed": processed,
            "errors": errors,
            "total_queries": min(len(test_queries), max_queries),
            "results": results,
            "cache_size": len(self._cache)
        }

        logger.info(f"Execution plan pre-computation completed: {processed} processed, {errors} errors")
        return precompute_result

    async def precompute_for_all_database_profiles(self, profile_manager, test_queries: List[Dict[str, Any]], max_queries_per_db: int = 5) -> Dict[str, Any]:
        """
        Предварительно вычисляет планы выполнения для всех профилей баз данных
        """
        logger.info("Pre-computing execution plans for all database profiles...")
        
        # Получаем все профили баз данных
        all_profiles = profile_manager.list_profiles()
        logger.info(f"Found {len(all_profiles)} database profiles to process")
        
        total_processed = 0
        total_errors = 0
        profile_results = {}
        
        for profile in all_profiles:
            try:
                logger.info(f"Processing database profile: {profile.name} ({profile.host}:{profile.port}/{profile.database})")
                
                # Получаем соединение с базой данных
                connection = profile_manager.get_connection(profile.id)
                if not connection:
                    logger.warning(f"No connection available for profile {profile.name}")
                    profile_results[profile.name] = {
                        "status": "error",
                        "error": "No connection available",
                        "processed": 0,
                        "errors": 0
                    }
                    continue
                
                # Создаем анализатор для этой базы данных
                from database import PostgreSQLAnalyzer
                db_analyzer = PostgreSQLAnalyzer(connection.get_connection_url())
                
                # Проверяем подключение
                connection_ok = await db_analyzer.test_connection()
                if not connection_ok:
                    logger.warning(f"Failed to connect to database {profile.name}")
                    profile_results[profile.name] = {
                        "status": "error",
                        "error": "Failed to connect to database",
                        "processed": 0,
                        "errors": 0
                    }
                    continue
                
                # Предварительно вычисляем планы для этой базы данных
                result = await self.precompute_execution_plans(db_analyzer, test_queries, max_queries_per_db)
                
                profile_results[profile.name] = {
                    "status": result["status"],
                    "processed": result["processed"],
                    "errors": result["errors"],
                    "total_queries": result["total_queries"],
                    "database_url": self._normalize_database_url(db_analyzer.database_url)
                }
                
                total_processed += result["processed"]
                total_errors += result["errors"]
                
                logger.info(f"Completed pre-computation for {profile.name}: {result['processed']} processed, {result['errors']} errors")
                
            except Exception as e:
                logger.error(f"Failed to pre-compute execution plans for profile {profile.name}: {e}")
                profile_results[profile.name] = {
                    "status": "error",
                    "error": str(e),
                    "processed": 0,
                    "errors": 0
                }
                total_errors += 1
        
        # Сохраняем кэш в файл
        self.save_cache_to_file()
        
        overall_result = {
            "status": "completed",
            "total_processed": total_processed,
            "total_errors": total_errors,
            "total_profiles": len(all_profiles),
            "profiles": profile_results,
            "cache_size": len(self._cache)
        }
        
        logger.info(f"All database profiles pre-computation completed: {total_processed} total processed, {total_errors} total errors")
        return overall_result
