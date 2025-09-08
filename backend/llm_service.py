import openai
from typing import List, Dict, Any
from models import OptimizationRecommendation, PriorityLevel, ResourceMetrics
from config import settings
import json
import logging
import hashlib
from functools import lru_cache

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    """Сервис для анализа SQL запросов с помощью LLM"""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self._cache = {}
        self._cache_max_size = 100  # Максимальный размер кэша
    
    def _create_query_hash(self, query: str, execution_plan: Dict[str, Any]) -> str:
        """
        Создает хэш для запроса и плана выполнения для кэширования
        """
        # Создаем строку для хэширования из запроса и ключевых параметров плана
        plan_summary = {
            'total_cost': execution_plan.get('Total Cost', 0),
            'execution_time': execution_plan.get('Actual Total Time', 0),
            'rows': execution_plan.get('Actual Rows', 0),
            'node_type': execution_plan.get('Node Type', '')
        }
        
        cache_string = f"{query}|{json.dumps(plan_summary, sort_keys=True)}"
        return hashlib.md5(cache_string.encode('utf-8')).hexdigest()
    
    def _add_to_cache(self, query_hash: str, result: Dict[str, Any]) -> None:
        """
        Добавляет результат в кэш с LRU логикой
        """
        # Если кэш переполнен, удаляем самый старый элемент
        if len(self._cache) >= self._cache_max_size:
            # Удаляем первый (самый старый) элемент
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.info(f"Cache evicted oldest entry: {oldest_key[:8]}...")
        
        # Добавляем новый результат
        self._cache[query_hash] = result
        logger.info(f"Added to cache: {query_hash[:8]}... (cache size: {len(self._cache)})")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику кэша
        """
        return {
            "cache_size": len(self._cache),
            "cache_max_size": self._cache_max_size,
            "cache_keys": [key[:8] + "..." for key in self._cache.keys()]
        }
    
    def clear_cache(self) -> None:
        """
        Очищает кэш
        """
        self._cache.clear()
        logger.info("Cache cleared")
    
    def analyze_query_with_llm(self, query: str, execution_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Анализирует SQL запрос с помощью LLM и возвращает структурированный результат
        """
        try:
            # Создаем хэш для кэширования
            query_hash = self._create_query_hash(query, execution_plan)
            
            # Проверяем кэш
            if query_hash in self._cache:
                logger.info(f"Cache hit for query hash: {query_hash[:8]}...")
                return self._cache[query_hash]
            
            logger.info(f"Cache miss for query hash: {query_hash[:8]}..., calling LLM...")
            
            # Подготавливаем контекст для LLM
            context = self._prepare_analysis_context(query, execution_plan)
            
            # Создаем промпт для анализа
            prompt = self._create_analysis_prompt(context)
            
            # Вызываем LLM с обычным JSON response
            json_prompt = prompt + """

Отвечай ТОЛЬКО в формате JSON без дополнительного текста. Все тексты должны быть на русском языке:

{
  "rewritten_query": "оптимизированная_версия_запроса_или_null_если_не_требуется",
  "resource_metrics": {
    "cpu_usage": число_от_0_до_100,
    "memory_usage": число_в_МБ,
    "io_operations": целое_число,
    "disk_reads": целое_число,
    "disk_writes": целое_число
  },
  "recommendations": [
    {
      "type": "тип_рекомендации_на_русском",
      "priority": "high|medium|low",
      "title": "заголовок_на_русском",
      "description": "подробное_описание_на_русском",
      "potential_improvement": "потенциальное_улучшение_на_русском",
      "implementation": "как_реализовать_на_русском",
      "estimated_speedup": число_в_процентах
    }
  ],
  "warnings": ["предупреждение_на_русском_1", "предупреждение_на_русском_2"]
}

ВАЖНО: Поле "rewritten_query" должно содержать оптимизированную версию SQL запроса, если это необходимо для улучшения производительности. 
Примеры случаев, когда нужно переписать запрос:
- Неявный JOIN (через запятую) → явный JOIN
- Подзапросы, которые можно заменить на JOIN
- Неэффективные конструкции WHERE
- Отсутствие LIMIT в запросах с большим результатом
Если запрос уже оптимален или переписывание не требуется, укажи null.
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты эксперт по оптимизации PostgreSQL. Анализируй SQL запросы и предоставляй детальные рекомендации по улучшению производительности на русском языке. Отвечай ТОЛЬКО в формате JSON без дополнительного текста."
                    },
                    {
                        "role": "user",
                        "content": json_prompt
                    }
                ],
                temperature=0.1
            )
            
            # Парсим ответ
            content = response.choices[0].message.content
            logger.info(f"LLM response content: {content}")
            
            # Очищаем ответ от возможных markdown блоков
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            analysis_result = json.loads(content)
            
            # Преобразуем в наши модели
            recommendations = []
            for rec in analysis_result["recommendations"]:
                # Обрабатываем estimated_speedup - может быть числом или строкой
                estimated_speedup = rec.get("estimated_speedup")
                if estimated_speedup is not None:
                    try:
                        # Если это строка с диапазоном (например, "50-70"), берем среднее значение
                        if isinstance(estimated_speedup, str) and '-' in estimated_speedup:
                            parts = estimated_speedup.split('-')
                            if len(parts) == 2:
                                estimated_speedup = (float(parts[0]) + float(parts[1])) / 2
                        else:
                            estimated_speedup = float(estimated_speedup)
                    except (ValueError, TypeError):
                        estimated_speedup = None
                
                recommendations.append(OptimizationRecommendation(
                    type=rec["type"],
                    priority=PriorityLevel(rec["priority"]),
                    title=rec["title"],
                    description=rec["description"],
                    potential_improvement=rec["potential_improvement"],
                    implementation=rec["implementation"],
                    estimated_speedup=estimated_speedup
                ))
            
            # Обрабатываем метрики ресурсов, заменяя null на 0
            resource_metrics_data = analysis_result["resource_metrics"]
            for key in resource_metrics_data:
                if resource_metrics_data[key] is None:
                    resource_metrics_data[key] = 0
            
            resource_metrics = ResourceMetrics(**resource_metrics_data)
            
            result = {
                "rewritten_query": analysis_result.get("rewritten_query"),
                "resource_metrics": resource_metrics,
                "recommendations": recommendations,
                "warnings": analysis_result["warnings"]
            }
            
            # Сохраняем результат в кэш
            self._add_to_cache(query_hash, result)
            
            return result
            
        except Exception as e:
            logger.error(f"LLM analysis error: {e}")
            raise
    
    def _prepare_analysis_context(self, query: str, execution_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Подготавливает контекст для анализа LLM
        """
        return {
            "query": query,
            "execution_plan": execution_plan,
            "total_cost": execution_plan.get("Total Cost", 0),
            "execution_time": execution_plan.get("Actual Total Time", 0),
            "rows": execution_plan.get("Actual Rows", 0),
            "plan_nodes": self._extract_plan_nodes(execution_plan)
        }
    
    def _extract_plan_nodes(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Извлекает узлы плана выполнения для анализа
        """
        nodes = []
        
        def extract_nodes_recursive(node, level=0):
            nodes.append({
                "level": level,
                "node_type": node.get("Node Type", ""),
                "cost": node.get("Total Cost", 0),
                "rows": node.get("Plan Rows", 0),
                "width": node.get("Plan Width", 0),
                "relation_name": node.get("Relation Name", ""),
                "index_name": node.get("Index Name", ""),
                "join_type": node.get("Join Type", ""),
                "condition": node.get("Hash Cond", "") or node.get("Index Cond", "")
            })
            
            for child in node.get("Plans", []):
                extract_nodes_recursive(child, level + 1)
        
        extract_nodes_recursive(plan)
        return nodes
    
    def _create_analysis_prompt(self, context: Dict[str, Any]) -> str:
        """
        Создает промпт для анализа запроса
        """
        # Проверяем, является ли запрос цепочкой
        queries = [q.strip() for q in context['query'].split(';') if q.strip()]
        is_chain = len(queries) > 1
        
        if is_chain:
            query_description = f"""
ЦЕПОЧКА SQL ЗАПРОСОВ ({len(queries)} запросов):
{context['query']}

ПРИМЕЧАНИЕ: Это цепочка из {len(queries)} связанных запросов. 
Анализируй их как единую логическую последовательность и давай рекомендации 
по оптимизации всей цепочки в целом.
"""
        else:
            query_description = f"""
SQL ЗАПРОС:
{context['query']}
"""
        
        return f"""
Проанализируй следующий SQL запрос и его план выполнения:

{query_description}

ПЛАН ВЫПОЛНЕНИЯ (для основного запроса):
- Общая стоимость: {context['total_cost']}
- Время выполнения: {context['execution_time']} мс
- Количество строк: {context['rows']}

УЗЛЫ ПЛАНА:
{json.dumps(context['plan_nodes'], indent=2, ensure_ascii=False)}

Пожалуйста, проанализируй:

1. РЕСУРСОЕМКОСТЬ:
   - Оцени использование CPU (0-100%)
   - Оцени использование памяти в MB
   - Подсчитай количество I/O операций
   - Оцени количество чтений и записей на диск

2. РЕКОМЕНДАЦИИ ПО ОПТИМИЗАЦИИ:
   - Предложи конкретные улучшения с приоритетом (high/medium/low)
   - Включи рекомендации по индексам, переписыванию запроса, настройке БД
   - Оцени потенциальное ускорение для каждой рекомендации
   - Предоставь конкретные шаги реализации
   {"- Учитывай взаимосвязь между запросами в цепочке" if is_chain else ""}

3. ПРЕДУПРЕЖДЕНИЯ:
   - Выяви потенциально опасные операции
   - Отметь проблемы с производительностью
   - Укажи на возможные блокировки
   {"- Обрати внимание на дублирование операций в цепочке" if is_chain else ""}

Будь конкретным и практичным в рекомендациях. Фокусируйся на реальных улучшениях производительности.
"""
    
    def test_connection(self) -> bool:
        """
        Проверяет доступность OpenAI API
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=1
            )
            return True
        except Exception as e:
            logger.error(f"OpenAI API test failed: {e}")
            return False
