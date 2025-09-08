import json
import asyncio
import logging
from typing import List, Dict, Any
from pathlib import Path
from database import PostgreSQLAnalyzer
from llm_service import LLMAnalyzer
from config import settings

logger = logging.getLogger(__name__)


class ExampleGenerator:
    """Сервис для генерации примеров SQL запросов с помощью LLM на основе структуры БД"""
    
    def __init__(self):
        self.db_analyzer = PostgreSQLAnalyzer()
        self.llm_analyzer = LLMAnalyzer()
    
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
                    tablename,
                    n_tup_ins,
                    n_tup_upd,
                    n_tup_del,
                    n_live_tup,
                    n_dead_tup
                FROM pg_stat_user_tables 
                WHERE schemaname = 'public'
                AND tablename IN ('users', 'orders', 'order_items')
                ORDER BY tablename
                """
                
                stats_rows = await conn.fetch(stats_query)
                
                # Группируем данные по таблицам
                tables = {}
                for row in rows:
                    table_name = row['table_name']
                    if table_name not in tables:
                        tables[table_name] = {
                            'table_name': table_name,
                            'table_type': row['table_type'],
                            'columns': [],
                            'indexes': [],
                            'stats': {}
                        }
                    
                    if row['column_name']:
                        tables[table_name]['columns'].append({
                            'name': row['column_name'],
                            'type': row['data_type'],
                            'max_length': row['character_maximum_length'],
                            'nullable': row['is_nullable'] == 'YES',
                            'default': row['column_default'],
                            'is_primary_key': row['is_primary_key'],
                            'is_foreign_key': row['is_foreign_key'],
                            'foreign_table': row['foreign_table_name'],
                            'foreign_column': row['foreign_column_name']
                        })
                
                # Добавляем индексы
                for row in index_rows:
                    table_name = row['tablename']
                    if table_name in tables:
                        tables[table_name]['indexes'].append({
                            'name': row['indexname'],
                            'definition': row['indexdef']
                        })
                
                # Добавляем статистику
                for row in stats_rows:
                    table_name = row['tablename']
                    if table_name in tables:
                        tables[table_name]['stats'] = {
                            'inserts': row['n_tup_ins'],
                            'updates': row['n_tup_upd'],
                            'deletes': row['n_tup_del'],
                            'live_tuples': row['n_live_tup'],
                            'dead_tuples': row['n_dead_tup']
                        }
                
                return {
                    'tables': list(tables.values()),
                    'total_tables': len(tables),
                    'database_info': await self.db_analyzer.get_database_info()
                }
                
        except Exception as e:
            logger.error(f"Failed to get database structure: {e}")
            return {'tables': [], 'total_tables': 0, 'database_info': {}}
    
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
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        return data.get('test_queries', [])
            
            logger.warning("No existing examples file found")
            return []
            
        except Exception as e:
            logger.error(f"Failed to load existing examples: {e}")
            return []
    
    async def _generate_examples_with_llm(self, db_structure: Dict[str, Any], existing_examples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
                        "content": "Ты эксперт по PostgreSQL и генерации SQL запросов. Твоя задача - создать разнообразные и полезные примеры SQL запросов на основе структуры базы данных и существующих примеров. Отвечай ТОЛЬКО в формате JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format=ExampleGenerationResponse,
                temperature=0.7
            )
            
            # Получаем структурированный ответ
            result = response.choices[0].message.parsed
            
            # Преобразуем в нужный формат
            examples = []
            for example in result.examples:
                examples.append({
                    "name": example.name,
                    "query": example.query,
                    "description": example.description,
                    "category": example.category,
                    "difficulty": example.difficulty
                })
            
            return examples
            
        except Exception as e:
            logger.error(f"Failed to generate examples with LLM: {e}")
            return []
    
    def _create_example_generation_prompt(self, db_structure: Dict[str, Any], existing_examples: List[Dict[str, Any]]) -> str:
        """Создает промпт для генерации примеров"""
        
        # Формируем описание структуры БД
        db_description = "СТРУКТУРА БАЗЫ ДАННЫХ:\n\n"
        for table in db_structure.get('tables', []):
            db_description += f"Таблица: {table['table_name']}\n"
            db_description += f"Тип: {table['table_type']}\n"
            db_description += "Колонки:\n"
            
            for column in table['columns']:
                db_description += f"  - {column['name']} ({column['type']})"
                if column['is_primary_key']:
                    db_description += " [PRIMARY KEY]"
                if column['is_foreign_key']:
                    db_description += f" [FOREIGN KEY -> {column['foreign_table']}.{column['foreign_column']}]"
                if not column['nullable']:
                    db_description += " [NOT NULL]"
                db_description += "\n"
            
            if table['indexes']:
                db_description += "Индексы:\n"
                for index in table['indexes']:
                    db_description += f"  - {index['name']}: {index['definition']}\n"
            
            if table['stats']:
                stats = table['stats']
                db_description += f"Статистика: {stats.get('live_tuples', 0)} строк, {stats.get('inserts', 0)} вставок\n"
            
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

ЗАДАЧА: Создай 15-20 новых разнообразных SQL запросов для этой базы данных, которые будут полезны для демонстрации возможностей анализатора запросов.

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
            existing_queries = {ex['query'] for ex in existing_examples}
            
            for new_example in new_examples:
                if new_example['query'] not in existing_queries:
                    all_examples.append(new_example)
                    existing_queries.add(new_example['query'])
            
            # Сохраняем обновленный файл
            test_queries_file = Path(__file__).parent.parent / "test_queries.json"
            with open(test_queries_file, 'w', encoding='utf-8') as f:
                json.dump({"test_queries": all_examples}, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Merged examples: {len(existing_examples)} existing + {len(new_examples)} new = {len(all_examples)} total")
            return all_examples
            
        except Exception as e:
            logger.error(f"Failed to merge and save examples: {e}")
            return []


# Pydantic модели для структурированного ответа LLM
from pydantic import BaseModel, Field
from typing import List

class ExampleQuery(BaseModel):
    name: str = Field(..., description="Название примера запроса")
    query: str = Field(..., description="SQL запрос")
    description: str = Field(..., description="Описание запроса на русском языке")
    category: str = Field(..., description="Категория запроса (simple, join, subquery, aggregation, window, inefficient)")
    difficulty: str = Field(..., description="Уровень сложности (easy, medium, hard)")

class ExampleGenerationResponse(BaseModel):
    examples: List[ExampleQuery] = Field(..., description="Список сгенерированных примеров запросов")


# Создаем глобальный экземпляр
example_generator = ExampleGenerator()
