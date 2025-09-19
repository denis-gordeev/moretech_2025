import json
import logging
from typing import List, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field
from database import PostgreSQLAnalyzer
from llm_service import LLMAnalyzer

logger = logging.getLogger(__name__)


class ExampleGenerator:
    """Сервис для генерации примеров SQL запросов с помощью LLM на основе структуры БД"""

    def __init__(self):
        self.db_analyzer = PostgreSQLAnalyzer()
        self.llm_analyzer = LLMAnalyzer()
        # Кэш для адаптированных примеров по профилям БД
        self._adapted_examples_cache = {}

    async def generate_examples_with_llm(self) -> List[Dict[str, Any]]:
        """
        Генерирует примеры SQL запросов с помощью LLM на основе структуры БД и существующих примеров
        """
        try:
            # Получаем структуру БД
            db_structure = await self._get_database_structure()

            # Загружаем существующие примеры
            existing_examples = await self._load_existing_examples()

            # Генерируем новые примеры с помощью LLM
            new_examples = await self._generate_examples_with_llm(db_structure, existing_examples)

            logger.info(f"Generated {len(new_examples)} new examples with LLM")
            return new_examples

        except Exception as e:
            logger.error(f"Failed to generate examples with LLM: {e}")
            return []

    async def generate_examples_with_llm_for_database(self, analyzer: PostgreSQLAnalyzer, database_profile_id: str = None) -> List[Dict[str, Any]]:
        """
        Генерирует примеры SQL запросов с помощью LLM для конкретной базы данных,
        адаптируя существующие примеры под новую схему БД
        """
        try:
            # Создаем ключ кэша на основе URL базы данных
            cache_key = analyzer.database_url
            
            # Проверяем кэш
            if cache_key in self._adapted_examples_cache:
                logger.info(f"Using cached adapted examples for database profile {database_profile_id}")
                return self._adapted_examples_cache[cache_key]

            logger.info(f"Generating new adapted examples for database profile {database_profile_id}")
            
            # Получаем структуру указанной БД
            db_structure = await self._get_database_structure_for_analyzer(analyzer)

            # Загружаем существующие примеры как шаблоны
            template_examples = await self._load_existing_examples()

            # Адаптируем примеры под новую схему БД
            adapted_examples = await self._adapt_examples_to_database_schema(template_examples, db_structure)

            # Сохраняем в кэш
            self._adapted_examples_cache[cache_key] = adapted_examples

            logger.info(f"Adapted {len(adapted_examples)} examples for specific database schema and cached")
            return adapted_examples

        except Exception as e:
            logger.error(f"Failed to adapt examples for database: {e}")
            return []

    async def _get_database_structure(self) -> Dict[str, Any]:
        """Получает подробную структуру базы данных"""
        try:
            async with self.db_analyzer.get_connection() as conn:
                # Получаем информацию о таблицах и их колонках
                tables_query = """
                SELECT
                    t.table_name,
                    t.table_type,
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_default,
                    c.character_maximum_length,
                    CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary_key,
                    CASE WHEN fk.column_name IS NOT NULL THEN true ELSE false END as is_foreign_key,
                    fk.foreign_table_name,
                    fk.foreign_column_name
                FROM information_schema.tables t
                LEFT JOIN information_schema.columns c ON t.table_name = c.table_name
                LEFT JOIN (
                    SELECT ku.table_name, ku.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage ku ON tc.constraint_name = ku.constraint_name
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                ) pk ON c.table_name = pk.table_name AND c.column_name = pk.column_name
                LEFT JOIN (
                    SELECT
                        ku.table_name,
                        ku.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage ku ON tc.constraint_name = ku.constraint_name
                    JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                ) fk ON c.table_name = fk.table_name AND c.column_name = fk.column_name
                WHERE t.table_schema = 'public'
                AND t.table_name IN ('users', 'orders', 'order_items')
                ORDER BY t.table_name, c.ordinal_position
                """

                rows = await conn.fetch(tables_query)

                # Получаем информацию о индексах
                indexes_query = """
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename IN ('users', 'orders', 'order_items')
                ORDER BY tablename, indexname
                """

                index_rows = await conn.fetch(indexes_query)

                # Получаем статистику таблиц
                stats_query = """
                SELECT
                    schemaname,
                    relname as tablename,
                    n_tup_ins,
                    n_tup_upd,
                    n_tup_del,
                    n_live_tup,
                    n_dead_tup
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                AND relname IN ('users', 'orders', 'order_items')
                ORDER BY relname
                """

                stats_rows = await conn.fetch(stats_query)

                # Группируем данные по таблицам
                tables = {}
                for row in rows:
                    table_name = row["table_name"]
                    if table_name not in tables:
                        tables[table_name] = {
                            "table_name": table_name,
                            "table_type": row["table_type"],
                            "columns": [],
                            "indexes": [],
                            "stats": {},
                        }

                    if row["column_name"]:
                        tables[table_name]["columns"].append(
                            {
                                "name": row["column_name"],
                                "type": row["data_type"],
                                "max_length": row["character_maximum_length"],
                                "nullable": row["is_nullable"] == "YES",
                                "default": row["column_default"],
                                "is_primary_key": row["is_primary_key"],
                                "is_foreign_key": row["is_foreign_key"],
                                "foreign_table": row["foreign_table_name"],
                                "foreign_column": row["foreign_column_name"],
                            }
                        )

                # Добавляем индексы
                for row in index_rows:
                    table_name = row["tablename"]
                    if table_name in tables:
                        tables[table_name]["indexes"].append({"name": row["indexname"], "definition": row["indexdef"]})

                # Добавляем статистику
                for row in stats_rows:
                    table_name = row["tablename"]
                    if table_name in tables:
                        tables[table_name]["stats"] = {
                            "inserts": row["n_tup_ins"],
                            "updates": row["n_tup_upd"],
                            "deletes": row["n_tup_del"],
                            "live_tuples": row["n_live_tup"],
                            "dead_tuples": row["n_dead_tup"],
                        }

                return {
                    "tables": list(tables.values()),
                    "total_tables": len(tables),
                    "database_info": await self.db_analyzer.get_database_info(),
                }

        except Exception as e:
            logger.error(f"Failed to get database structure: {e}")
            return {"tables": [], "total_tables": 0, "database_info": {}}

    async def _get_database_structure_for_analyzer(self, analyzer: PostgreSQLAnalyzer) -> Dict[str, Any]:
        """Получает подробную структуру базы данных для указанного анализатора"""
        try:
            async with analyzer.get_connection() as conn:
                # Получаем информацию о таблицах и их колонках
                tables_query = """
                SELECT
                    t.table_name,
                    t.table_type,
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_default,
                    c.character_maximum_length,
                    CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary_key,
                    CASE WHEN fk.column_name IS NOT NULL THEN true ELSE false END as is_foreign_key,
                    fk.foreign_table_name,
                    fk.foreign_column_name
                FROM information_schema.tables t
                LEFT JOIN information_schema.columns c ON t.table_name = c.table_name
                LEFT JOIN (
                    SELECT ku.table_name, ku.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage ku ON tc.constraint_name = ku.constraint_name
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                ) pk ON c.table_name = pk.table_name AND c.column_name = pk.column_name
                LEFT JOIN (
                    SELECT
                        ku.table_name,
                        ku.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage ku ON tc.constraint_name = ku.constraint_name
                    JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                ) fk ON c.table_name = fk.table_name AND c.column_name = fk.column_name
                WHERE t.table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY t.table_name, c.ordinal_position
                LIMIT 20
                """

                rows = await conn.fetch(tables_query)

                # Получаем информацию о индексах
                indexes_query = """
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE schemaname NOT IN ('information_schema', 'pg_catalog')
                ORDER BY tablename, indexname
                LIMIT 20
                """

                index_rows = await conn.fetch(indexes_query)

                # Получаем информацию о ограничениях
                constraints_query = """
                SELECT
                    tc.constraint_name,
                    tc.table_name,
                    tc.constraint_type,
                    kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY tc.table_name, tc.constraint_name
                LIMIT 20
                """

                constraint_rows = await conn.fetch(constraints_query)

                # Структурируем данные
                tables = {}
                for row in rows:
                    table_name = row['table_name']
                    schema_name = row.get('table_schema', 'public')
                    full_table_name = f"{schema_name}.{table_name}" if schema_name != 'public' else table_name
                    
                    if full_table_name not in tables:
                        tables[full_table_name] = {
                            'name': full_table_name,
                            'schema': schema_name,
                            'type': row['table_type'],
                            'columns': []
                        }
                    
                    if row['column_name']:  # Пропускаем строки без колонок
                        tables[full_table_name]['columns'].append({
                            'name': row['column_name'],
                            'type': row['data_type'],
                            'nullable': row['is_nullable'] == 'YES',
                            'default': row['column_default'],
                            'max_length': row['character_maximum_length'],
                            'is_primary_key': row['is_primary_key'],
                            'is_foreign_key': row['is_foreign_key'],
                            'foreign_table': row['foreign_table_name'],
                            'foreign_column': row['foreign_column_name']
                        })

                indexes = [{
                    'schema': row['schemaname'],
                    'table': row['tablename'],
                    'name': row['indexname'],
                    'definition': row['indexdef']
                } for row in index_rows]

                constraints = [{
                    'name': row['constraint_name'],
                    'table': row['table_name'],
                    'type': row['constraint_type'],
                    'column': row['column_name']
                } for row in constraint_rows]

                return {
                    'tables': list(tables.values()),
                    'indexes': indexes,
                    'constraints': constraints,
                    'total_tables': len(tables),
                    'database_info': await analyzer.get_database_info(),
                }

        except Exception as e:
            logger.error(f"Failed to get database structure for analyzer: {e}")
            return {"tables": [], "indexes": [], "constraints": [], "total_tables": 0, "database_info": {}}

    async def _adapt_examples_to_database_schema(self, template_examples: List[Dict[str, Any]], db_structure: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Адаптирует существующие примеры под новую схему базы данных
        """
        try:
            # Создаем промпт для адаптации примеров
            prompt = self._create_adaptation_prompt(template_examples, db_structure)

            # Используем LLM для адаптации примеров
            response = await self.llm_analyzer.client.beta.chat.completions.parse(
                model=self.llm_analyzer.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты эксперт по PostgreSQL и адаптации SQL запросов. "
                            "Твоя задача - адаптировать существующие примеры SQL запросов "
                            "под новую схему базы данных, сохраняя логику и структуру запросов. "
                            "Отвечай ТОЛЬКО в формате JSON. Будь кратким."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format=ExampleGenerationResponse,
                temperature=0.3,  # Низкая температура для более точной адаптации
                max_tokens=2000,  # Ограничиваем размер ответа
            )

            # Получаем структурированный ответ
            try:
                result = response.choices[0].message.parsed
            except Exception as parse_error:
                logger.error(f"Failed to parse LLM response: {parse_error}")
                # Попробуем получить raw content и очистить его
                raw_content = response.choices[0].message.content
                if raw_content:
                    # Удаляем markdown код блоки
                    cleaned_content = raw_content.replace('```json', '').replace('```', '').strip()
                    try:
                        import json
                        parsed_data = json.loads(cleaned_content)
                        if isinstance(parsed_data, list):
                            result = type('Result', (), {'examples': [type('Example', (), ex) for ex in parsed_data]})()
                        else:
                            raise Exception("Invalid JSON structure")
                    except Exception as json_error:
                        logger.error(f"Failed to parse cleaned JSON: {json_error}")
                        return []

            # Преобразуем в нужный формат
            adapted_examples = []
            for example in result.examples:
                adapted_examples.append({
                    "name": example.name,
                    "query": example.query,
                    "description": example.description,
                    "category": getattr(example, 'category', 'adapted'),
                    "difficulty": getattr(example, 'difficulty', 'medium')
                })

            return adapted_examples

        except Exception as e:
            logger.error(f"Failed to adapt examples to database schema: {e}")
            return []

    def _create_adaptation_prompt(self, template_examples: List[Dict[str, Any]], db_structure: Dict[str, Any]) -> str:
        """
        Создает промпт для адаптации примеров под новую схему БД
        """
        # Получаем информацию о таблицах новой БД
        tables_info = []
        for table in db_structure.get('tables', []):
            table_name = table['name']
            table_info = f"Таблица: {table_name}\n"
            table_info += f"  Тип: {table['type']}\n"
            table_info += "  Колонки:\n"
            for column in table.get('columns', []):
                table_info += f"    - {column['name']} ({column['type']})"
                if column.get('is_primary_key'):
                    table_info += " [PRIMARY KEY]"
                if column.get('is_foreign_key'):
                    table_info += f" [FOREIGN KEY -> {column['foreign_table']}.{column['foreign_column']}]"
                table_info += "\n"
            tables_info.append(table_info)
            
        # Добавляем пример использования
        if tables_info:
            tables_info.append("\nПРИМЕР ИСПОЛЬЗОВАНИЯ:")
            tables_info.append("Используй полные имена таблиц: rnacen.table_name")
            tables_info.append("Пример: SELECT * FROM rnacen.auth_permission WHERE name = 'test'")

        # Создаем список шаблонных примеров (берем только 5 самых важных)
        template_list = []
        for i, example in enumerate(template_examples[:5], 1):  # Берем только первые 5 примеров
            # Сокращаем длинные запросы
            query = example['query']
            if len(query) > 200:
                query = query[:200] + "..."
            template_list.append(f"{i}. {example['name']}\n   Запрос: {query}\n   Описание: {example['description']}")

        prompt = f"""
Адаптируй SQL примеры под новую схему БД.

СХЕМА БД:
{chr(10).join(tables_info)}

ШАБЛОНЫ:
{chr(10).join(template_list)}

ЗАДАЧА: 
1. Замени названия таблиц на соответствующие из новой схемы (используй полные имена с схемой, например rnacen.table_name)
2. Замени названия колонок на соответствующие из новой схемы
3. Сохрани логику и структуру запросов
4. Адаптируй описания под предметную область новой БД

ПРАВИЛА МАППИНГА:
- Если в шаблоне есть таблица 'users' -> используй rnacen.auth_permission или rnacen.blog
- Если в шаблоне есть таблица 'orders' -> используй rnacen.ensembl_assembly или rnacen.cpat_results  
- Если в шаблоне есть таблица 'order_items' -> используй rnacen.go_term_annotations или rnacen.ensembl_compara
- Выбирай таблицы с подходящими колонками (id, name, content, etc.)

ВАЖНО: Используй ТОЛЬКО таблицы и колонки из предоставленной схемы БД!

Верни ТОЛЬКО 5 адаптированных примеров в JSON формате. НЕ используй markdown код блоки, только чистый JSON.
"""

        return prompt

    async def _load_existing_examples(self) -> List[Dict[str, Any]]:
        """Загружает существующие примеры запросов"""
        try:
            # Ищем файл test_queries.json в разных возможных местах
            possible_paths = [
                Path(__file__).parent.parent / "test_queries.json",  # ../test_queries.json
                Path("/app/test_queries.json"),  # В контейнере
                Path("test_queries.json"),  # В текущей директории
            ]

            for path in possible_paths:
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        return data.get("test_queries", [])

            logger.warning("No existing examples file found")
            return []

        except Exception as e:
            logger.error(f"Failed to load existing examples: {e}")
            return []

    async def _generate_examples_with_llm(
        self, db_structure: Dict[str, Any], existing_examples: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Генерирует новые примеры запросов с помощью LLM"""
        try:
            # Создаем промпт для LLM
            prompt = self._create_example_generation_prompt(db_structure, existing_examples)

            # Используем LLM для генерации примеров
            response = await self.llm_analyzer.client.beta.chat.completions.parse(
                model=self.llm_analyzer.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты эксперт по PostgreSQL и генерации SQL запросов. "
                            "Твоя задача - создать разнообразные и полезные примеры SQL запросов "
                            "на основе структуры базы данных и существующих примеров. "
                            "Отвечай ТОЛЬКО в формате JSON."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format=ExampleGenerationResponse,
                temperature=0.7,
            )

            # Получаем структурированный ответ
            result = response.choices[0].message.parsed

            # Преобразуем в нужный формат
            examples = []
            for example in result.examples:
                examples.append(
                    {
                        "name": example.name,
                        "query": example.query,
                        "description": example.description,
                        "category": example.category,
                        "difficulty": example.difficulty,
                    }
                )

            return examples

        except Exception as e:
            logger.error(f"Failed to generate examples with LLM: {e}")
            return []

    def _create_example_generation_prompt(
        self, db_structure: Dict[str, Any], existing_examples: List[Dict[str, Any]]
    ) -> str:
        """Создает промпт для генерации примеров"""

        # Формируем описание структуры БД
        db_description = "СТРУКТУРА БАЗЫ ДАННЫХ:\n\n"
        for table in db_structure.get("tables", []):
            db_description += f"Таблица: {table['table_name']}\n"
            db_description += f"Тип: {table['table_type']}\n"
            db_description += "Колонки:\n"

            for column in table["columns"]:
                db_description += f"  - {column['name']} ({column['type']})"
                if column["is_primary_key"]:
                    db_description += " [PRIMARY KEY]"
                if column["is_foreign_key"]:
                    db_description += f" [FOREIGN KEY -> {column['foreign_table']}.{column['foreign_column']}]"
                if not column["nullable"]:
                    db_description += " [NOT NULL]"
                db_description += "\n"

            if table["indexes"]:
                db_description += "Индексы:\n"
                for index in table["indexes"]:
                    db_description += f"  - {index['name']}: {index['definition']}\n"

            if table["stats"]:
                stats = table["stats"]
                db_description += (
                    f"Статистика: {stats.get('live_tuples', 0)} строк, {stats.get('inserts', 0)} вставок\n"
                )

            db_description += "\n"

        # Формируем описание существующих примеров
        existing_description = "СУЩЕСТВУЮЩИЕ ПРИМЕРЫ ЗАПРОСОВ:\n\n"
        for i, example in enumerate(existing_examples[:10], 1):  # Показываем только первые 10
            existing_description += f"{i}. {example['name']}\n"
            existing_description += f"   Запрос: {example['query']}\n"
            existing_description += f"   Описание: {example['description']}\n\n"

        prompt = f"""
{db_description}

{existing_description}

ЗАДАЧА: Создай 15-20 новых разнообразных SQL запросов для этой базы данных,
которые будут полезны для демонстрации возможностей анализатора запросов.

ТРЕБОВАНИЯ:
1. Запросы должны быть разнообразными по сложности (простые, средние, сложные)
2. Включи примеры разных типов: SELECT, JOIN, подзапросы, агрегация, оконные функции
3. Добавь несколько неэффективных запросов для демонстрации оптимизации
4. Используй реальные имена таблиц и колонок из структуры БД
5. Запросы должны быть синтаксически корректными для PostgreSQL
6. Избегай дублирования существующих примеров

КАТЕГОРИИ для разнообразия:
- Простые SELECT запросы
- JOIN запросы (INNER, LEFT, RIGHT)
- Подзапросы (коррелированные и некоррелированные)
- Агрегационные функции (GROUP BY, HAVING)
- Оконные функции (ROW_NUMBER, RANK, etc.)
- Неэффективные запросы (для демонстрации оптимизации)
- Запросы с индексами
- Запросы с сортировкой и ограничениями

Отвечай ТОЛЬКО в формате JSON без дополнительного текста.
"""

        return prompt

    async def merge_and_save_examples(self) -> List[Dict[str, Any]]:
        """
        Объединяет существующие примеры с новыми, сгенерированными LLM, и сохраняет результат
        """
        try:
            # Загружаем существующие примеры
            existing_examples = await self._load_existing_examples()

            # Генерируем новые примеры с помощью LLM
            new_examples = await self.generate_examples_with_llm()

            # Объединяем, избегая дубликатов
            all_examples = existing_examples.copy()
            existing_queries = {ex["query"] for ex in existing_examples}

            for new_example in new_examples:
                if new_example["query"] not in existing_queries:
                    all_examples.append(new_example)
                    existing_queries.add(new_example["query"])

            # Сохраняем обновленный файл
            test_queries_file = Path(__file__).parent.parent / "test_queries.json"
            with open(test_queries_file, "w", encoding="utf-8") as f:
                json.dump({"test_queries": all_examples}, f, ensure_ascii=False, indent=2)

            logger.info(
                f"Merged examples: {len(existing_examples)} existing + "
                f"{len(new_examples)} new = {len(all_examples)} total"
            )
            return all_examples

        except Exception as e:
            logger.error(f"Failed to merge and save examples: {e}")
            return []


# Pydantic модели для структурированного ответа LLM


class ExampleQuery(BaseModel):
    name: str = Field(..., description="Название примера запроса")
    query: str = Field(..., description="SQL запрос")
    description: str = Field(..., description="Описание запроса на русском языке")
    category: str = Field(
        ..., description="Категория запроса (simple, join, subquery, aggregation, window, inefficient)"
    )
    difficulty: str = Field(..., description="Уровень сложности (easy, medium, hard)")


class ExampleGenerationResponse(BaseModel):
    examples: List[ExampleQuery] = Field(..., description="Список сгенерированных примеров запросов")


# Создаем глобальный экземпляр
example_generator = ExampleGenerator()
