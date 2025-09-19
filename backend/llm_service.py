import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

import openai

from config import LLMModel, settings
from models import LLMAnalysisResponse, OptimizationRecommendation, PriorityLevel, ResourceMetrics

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    """Сервис для анализа SQL запросов с помощью LLM"""

    def __init__(self, selected_model: Optional[LLMModel] = None):
        self.selected_model = selected_model or settings.get_model_by_index(0)
        if not self.selected_model:
            raise ValueError("No LLM model available")
        self.client = openai.AsyncOpenAI(api_key=self.selected_model.api_key, base_url=self.selected_model.url)
        self.model = self.selected_model.model
        self._cache: Dict[str, Any] = {}
        self._cache_max_size = 10000  # Максимальный размер кэша
        self._session = None

    def _create_query_hash(self, query: str, execution_plan: Dict[str, Any]) -> str:
        """
        Создает хэш для запроса, плана выполнения и модели для кэширования
        """
        # Создаем строку для хэширования из запроса, ключевых параметров плана и модели
        plan_summary = {
            "total_cost": execution_plan.get("Total Cost", 0),
            "execution_time": execution_plan.get("Actual Total Time", 0),
            "rows": execution_plan.get("Actual Rows", 0),
            "node_type": execution_plan.get("Node Type", ""),
        }

        # Включаем модель в хэш для разделения кэша по моделям
        cache_string = f"{self.model}|{query}|{json.dumps(plan_summary, sort_keys=True)}"
        return hashlib.md5(cache_string.encode("utf-8")).hexdigest()

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
            "cache_keys": [key[:8] + "..." for key in self._cache.keys()],
        }

    def clear_cache(self) -> None:
        """
        Очищает кэш
        """
        self._cache.clear()
        logger.info("Cache cleared")

    async def load_cache_from_file(self, cache_data: Dict[str, Any]) -> None:
        """
        Загружает кэш из внешнего источника (например, из файла)
        """
        if cache_data:
            self._cache.update(cache_data)
            logger.info(f"Loaded {len(cache_data)} entries from external cache")

    def switch_model(self, model: LLMModel) -> None:
        """
        Переключает на другую модель
        """
        self.selected_model = model
        self.client = openai.AsyncOpenAI(api_key=model.api_key, base_url=model.url)
        self.model = model.model
        logger.info(f"Switched to model: {model.name} ({model.model})")

    async def analyze_query_with_llm(
        self, query: str, execution_plan: Dict[str, Any], table_statistics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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
            prompt = self._create_analysis_prompt(context, table_statistics)

            # Добавляем инструкции по структуре ответа
            structured_prompt = (
                prompt
                + """

ВАЖНО: Поле "rewritten_query" должно содержать оптимизированную версию SQL запроса
ТОЛЬКО если есть серьезные проблемы с производительностью или структурой запроса.

Переписывай запрос ТОЛЬКО в следующих случаях:
- Есть предупреждения (warnings) о проблемах с запросом
- Запрос содержит неэффективные конструкции
- Есть явные проблемы с производительностью

Примеры случаев, когда НУЖНО переписать запрос:
- Неявный JOIN (через запятую) → явный JOIN
- Подзапросы, которые можно заменить на JOIN
- NOT IN → NOT EXISTS или LEFT JOIN
- Неэффективные конструкции WHERE
- Отсутствие LIMIT в запросах с большим результатом
- Неоптимальные индексы для WHERE условий

Если запрос уже оптимален или нет серьезных проблем, укажи null в поле "rewritten_query".

Все тексты должны быть на русском языке.
"""
            )

            # Используем структурированный вывод с Pydantic для всех моделей
            response = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты эксперт по оптимизации PostgreSQL. Анализируй SQL запросы и "
                            "предоставляй детальные рекомендации по улучшению производительности на русском языке."
                        ),
                    },
                    {"role": "user", "content": structured_prompt},
                ],
                response_format=LLMAnalysisResponse,
                temperature=0.1,
                timeout=30.0,  # 30 секунд таймаут
            )
            # Получаем структурированный ответ
            analysis_result = response.choices[0].message.parsed
            logger.info(f"LLM structured response received: {type(analysis_result)}")

            # Проверяем, что ответ был успешно распарсен
            if analysis_result is None:
                logger.error("LLM response parsing failed - received None")
                # Возвращаем базовый результат в случае ошибки парсинга
                return {
                    "rewritten_query": None,
                    "resource_metrics": ResourceMetrics(
                        cpu_usage=0, memory_usage=0, disk_io=0, network_io=0, estimated_cost=0
                    ),
                    "recommendations": [],
                    "warnings": ["Не удалось проанализировать запрос с помощью LLM"],
                }

            # Преобразуем в наши модели
            recommendations = []
            for rec in analysis_result.recommendations:
                # Обрабатываем estimated_speedup - может быть числом или строкой
                estimated_speedup = rec.estimated_speedup
                if estimated_speedup is not None:
                    try:
                        # Если это строка с диапазоном (например, "50-70"), берем среднее значение
                        if isinstance(estimated_speedup, str) and "-" in estimated_speedup:
                            parts = estimated_speedup.split("-")
                            if len(parts) == 2:
                                estimated_speedup = (float(parts[0]) + float(parts[1])) / 2
                        else:
                            estimated_speedup = float(estimated_speedup)
                    except (ValueError, TypeError):
                        estimated_speedup = None

                recommendations.append(
                    OptimizationRecommendation(
                        type=rec.type,
                        priority=PriorityLevel(rec.priority),
                        title=rec.title,
                        description=rec.description,
                        potential_improvement=rec.potential_improvement,
                        implementation=rec.implementation,
                        estimated_speedup=estimated_speedup,
                    )
                )

            # Обрабатываем метрики ресурсов, заменяя null на 0
            resource_metrics_data = analysis_result.resource_metrics.dict()
            for key in resource_metrics_data:
                if resource_metrics_data[key] is None:
                    resource_metrics_data[key] = 0

            resource_metrics = ResourceMetrics(**resource_metrics_data)

            result = {
                "rewritten_query": analysis_result.rewritten_query,
                "resource_metrics": resource_metrics,
                "recommendations": recommendations,
                "warnings": analysis_result.warnings,
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
            "plan_nodes": self._extract_plan_nodes(execution_plan),
        }

    def _extract_plan_nodes(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Извлекает узлы плана выполнения для анализа
        """
        nodes = []

        def extract_nodes_recursive(node, level=0):
            nodes.append(
                {
                    "level": level,
                    "node_type": node.get("Node Type", ""),
                    "cost": node.get("Total Cost", 0),
                    "rows": node.get("Plan Rows", 0),
                    "width": node.get("Plan Width", 0),
                    "relation_name": node.get("Relation Name", ""),
                    "index_name": node.get("Index Name", ""),
                    "join_type": node.get("Join Type", ""),
                    "condition": node.get("Hash Cond", "") or node.get("Index Cond", ""),
                }
            )

            for child in node.get("Plans", []):
                extract_nodes_recursive(child, level + 1)

        extract_nodes_recursive(plan)
        return nodes

    def _create_analysis_prompt(
        self, context: Dict[str, Any], table_statistics: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Создает промпт для анализа запроса
        """
        # Проверяем, является ли запрос цепочкой
        queries = [q.strip() for q in context["query"].split(";") if q.strip()]
        is_chain = len(queries) > 1

        if is_chain:
            query_description = """
ЦЕПОЧКА SQL ЗАПРОСОВ ({} запросов):
{}

ПРИМЕЧАНИЕ: Это цепочка из {} связанных запросов.
Анализируй их как единую логическую последовательность и давай рекомендации
по оптимизации всей цепочки в целом.
""".format(
                len(queries), context["query"], len(queries)
            )
        else:
            query_description = """
SQL ЗАПРОС:
{}
""".format(
                context["query"]
            )

        # Определяем тип запроса для адаптации анализа
        query_type = context["execution_plan"].get("Query Type", "SELECT")

        # Формируем информацию о статистике таблиц
        table_stats_info = ""
        if table_statistics and table_statistics.get("tables"):
            table_stats_info = "\n\nСТАТИСТИКА ТАБЛИЦ В БАЗЕ ДАННЫХ:\n"
            for table_name, stats in table_statistics["tables"].items():
                table_stats_info += (
                    f"- {table_name}: {stats['live_tuples']:,} строк, "
                    f"размер {stats.get('size_pretty', 'неизвестно')}\n"
                )

            total_tuples = table_statistics.get("total_live_tuples", 0)
            total_size = table_statistics.get("total_size_bytes", 0)
            table_stats_info += (
                f"\nОБЩАЯ СТАТИСТИКА: {total_tuples:,} строк в "
                f"{table_statistics.get('total_tables', 0)} таблицах, "
                f"общий размер {total_size / (1024*1024):.1f} MB"
            )

        return """
Проанализируй следующий SQL запрос и его план выполнения:

{}

ТИП ЗАПРОСА: {}

ПЛАН ВЫПОЛНЕНИЯ (для основного запроса):
- Общая стоимость: {}
- Время выполнения: {} мс
- Количество строк: {}

УЗЛЫ ПЛАНА:
{}{}

ПРИМЕРЫ АНАЛИЗА (для справки):

Пример 1 - Простой SELECT:
Запрос: SELECT * FROM users WHERE email = 'john@example.com'
Рекомендации:
- Проверка полноты индекса: Индекс idx_users_email уже используется, но для максимальной производительности убедитесь, что он покрывающий (covering index)
- Обновление статистики таблицы: Статистика показывает только 3 строки в таблице users, но размер 56kB указывает на возможное несоответствие. Обновите статистику для более точного планирования
Предупреждения:
- Внимание: Размер таблицы users (56kB) не соответствует заявленному количеству строк (3). Возможно устаревшая статистика
- Предупреждение: SELECT * может возвращать избыточные данные. Рекомендуется явно указывать необходимые столбцы

Пример 2 - JOIN с агрегацией:
Запрос: SELECT u.name, COUNT(o.id) as order_count, SUM(o.total_amount) as total_spent FROM users u LEFT JOIN orders o ON u.id = o.user_id WHERE u.is_active = true GROUP BY u.id, u.name ORDER BY total_spent DESC
Рекомендации:
- Создание индекса для users.is_active: Добавить индекс на поле is_active таблицы users для ускорения фильтрации активных пользователей
- Создание индекса для orders.user_id: Добавить индекс на поле user_id таблицы orders для оптимизации JOIN операции
Предупреждения:
- Потенциальная проблема с оценкой количества строк: план показывает 85 строк для users, но статистика указывает только 3 строки
- Отсутствие индексов приводит к полному сканированию таблиц (Seq Scan)

Пример 3 - Сложный подзапрос:
Запрос: SELECT * FROM users WHERE id IN (SELECT user_id FROM orders WHERE total_amount > (SELECT AVG(total_amount) FROM orders))
Рекомендации:
- Создание индекса для orders.total_amount: Добавить индекс на поле total_amount таблицы orders для ускорения вычисления среднего значения
- Создание индекса для orders.user_id: Добавить индекс на поле user_id таблицы orders для ускорения JOIN операций
Предупреждения:
- Использование последовательного сканирования (Seq Scan) вместо индексного сканирования
- Множественные полные сканирования таблицы orders (690 и 230 строк)

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
   {}
   {}

3. ПРЕДУПРЕЖДЕНИЯ:
   - Выяви потенциально опасные операции
   - Отметь проблемы с производительностью
   - Укажи на возможные блокировки
   {}
   {}

Будь конкретным и практичным в рекомендациях. Фокусируйся на реальных улучшениях производительности.
""".format(
            query_description,
            query_type,
            context["total_cost"],
            context["execution_time"],
            context["rows"],
            json.dumps(context["plan_nodes"], indent=2, ensure_ascii=False),
            table_stats_info,
            "- Учитывай взаимосвязь между запросами в цепочке" if is_chain else "",
            "- Для DML запросов (INSERT/UPDATE/DELETE) обрати внимание на блокировки и производительность записи"
            if query_type in ["INSERT", "UPDATE", "DELETE"]
            else "",
            "- Обрати внимание на дублирование операций в цепочке" if is_chain else "",
            "- Для DML запросов предупреди о потенциальных блокировках таблиц"
            if query_type in ["INSERT", "UPDATE", "DELETE"]
            else "",
        )

    async def test_connection(self) -> bool:
        """
        Проверяет доступность OpenAI API
        """
        try:
            await self.client.beta.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": "Test"}], max_tokens=1
            )
            return True
        except Exception as e:
            logger.error(f"OpenAI API test failed: {e}")
            return False
