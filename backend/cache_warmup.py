import json
import asyncio
import logging
from typing import List, Dict, Any
from pathlib import Path
from database import PostgreSQLAnalyzer
from llm_service import LLMAnalyzer
from config import settings

logger = logging.getLogger(__name__)


class CacheWarmupService:
    """Сервис для предварительного кэширования тестовых запросов"""
    
    def __init__(self):
        self.db_analyzer = PostgreSQLAnalyzer()
        self.llm_analyzer = LLMAnalyzer()
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
    
    async def load_test_queries(self) -> List[Dict[str, Any]]:
        """Загружает тестовые запросы из файла"""
        if not self.test_queries_file:
            logger.error("Test queries file not found")
            return []
            
        try:
            with open(self.test_queries_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('test_queries', [])
        except Exception as e:
            logger.error(f"Failed to load test queries: {e}")
            return []
    
    async def warmup_cache(self, max_queries: int = 5) -> Dict[str, Any]:
        """
        Предварительно кэширует тестовые запросы
        """
        logger.info("Starting cache warmup...")
        
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
                query = query_data['query']
                name = query_data['name']
                
                logger.info(f"Processing query {i+1}/{len(queries_to_process)}: {name}")
                
                # Получаем план выполнения
                plan_data = await self.db_analyzer.analyze_query_performance(query)
                
                # Анализируем с помощью LLM (это добавит результат в кэш)
                llm_result = await self.llm_analyzer.analyze_query_with_llm(
                    query, 
                    plan_data['plan_json']
                )
                
                results.append({
                    "name": name,
                    "query": query[:100] + "..." if len(query) > 100 else query,
                    "status": "success",
                    "has_rewritten_query": llm_result.get('rewritten_query') is not None,
                    "recommendations_count": len(llm_result.get('recommendations', []))
                })
                
                processed += 1
                logger.info(f"Successfully cached query: {name}")
                
            except Exception as e:
                logger.error(f"Failed to process query '{name}': {e}")
                errors += 1
                results.append({
                    "name": name,
                    "query": query_data['query'][:100] + "..." if len(query_data['query']) > 100 else query_data['query'],
                    "status": "error",
                    "error": str(e)
                })
        
        # Получаем статистику кэша
        cache_stats = self.llm_analyzer.get_cache_stats()
        
        warmup_result = {
            "status": "completed",
            "processed": processed,
            "errors": errors,
            "total_queries": len(queries_to_process),
            "cache_stats": cache_stats,
            "results": results
        }
        
        logger.info(f"Cache warmup completed: {processed} processed, {errors} errors")
        return warmup_result
    
    async def test_cache_hit(self, query: str) -> Dict[str, Any]:
        """
        Тестирует попадание в кэш для конкретного запроса
        """
        try:
            # Получаем план выполнения
            plan_data = await self.db_analyzer.analyze_query_performance(query)
            
            # Анализируем с помощью LLM
            start_time = asyncio.get_event_loop().time()
            llm_result = await self.llm_analyzer.analyze_query_with_llm(
                query, 
                plan_data['plan_json']
            )
            end_time = asyncio.get_event_loop().time()
            
            return {
                "status": "success",
                "execution_time": end_time - start_time,
                "has_rewritten_query": llm_result.get('rewritten_query') is not None,
                "recommendations_count": len(llm_result.get('recommendations', [])),
                "cache_stats": self.llm_analyzer.get_cache_stats()
            }
            
        except Exception as e:
            logger.error(f"Failed to test cache hit: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
