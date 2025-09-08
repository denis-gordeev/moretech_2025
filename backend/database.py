import json
import asyncpg
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from config import settings
import logging

logger = logging.getLogger(__name__)


class PostgreSQLAnalyzer:
    """Класс для анализа PostgreSQL запросов"""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or settings.database_url

    @asynccontextmanager
    async def get_connection(self):
        """Асинхронный контекстный менеджер для подключения к БД"""
        conn = None
        try:
            conn = await asyncpg.connect(self.database_url)
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                await conn.close()

    async def explain_query(self, query: str) -> Dict[str, Any]:
        """
        Получает план выполнения запроса без его выполнения
        Поддерживает все типы запросов: SELECT, INSERT, UPDATE, DELETE
        """
        async with self.get_connection() as conn:
            try:
                # Определяем тип запроса
                query_type = self._get_query_type(query)

                # Для разных типов запросов используем разные подходы
                select_query = query  # Инициализируем переменную
                if query_type in ["SELECT", "WITH"]:
                    # Для SELECT и WITH используем обычный EXPLAIN
                    explain_query = f"EXPLAIN (ANALYZE false, BUFFERS false, FORMAT JSON) {query}"
                elif query_type in ["INSERT", "UPDATE", "DELETE"]:
                    # Для DML запросов сначала пытаемся конвертировать в SELECT
                    logger.info(f"Converting DML query to SELECT for analysis: {query_type} (v2)")
                    select_query = self._convert_dml_to_select(query)
                    
                    if select_query != query:  # Если конвертация прошла успешно
                        logger.info(f"Using converted SELECT query for EXPLAIN: {select_query}")
                        explain_query = f"EXPLAIN (ANALYZE false, BUFFERS false, FORMAT JSON) {select_query}"
                    else:
                        # Если конвертация не удалась, используем оригинальный запрос
                        explain_query = f"EXPLAIN (ANALYZE false, BUFFERS false, FORMAT JSON) {query}"
                else:
                    # Для других типов (CREATE, DROP, ALTER) возвращаем базовую информацию
                    return {
                        "Node Type": "Utility",
                        "Total Cost": 0,
                        "Plan Rows": 0,
                        "Plan Width": 0,
                        "Query Type": query_type,
                        "Description": f"Utility command: {query_type}",
                    }

                result = await conn.fetchrow(explain_query)
                logger.info(f"EXPLAIN result: {result}")

                if result and "QUERY PLAN" in result:
                    # EXPLAIN возвращает результат как строку JSON, нужно распарсить
                    query_plan_json = result["QUERY PLAN"]
                    logger.info(f"Query plan JSON: {query_plan_json}")

                    # Парсим JSON строку

                    plan_array = json.loads(query_plan_json)
                    logger.info(f"Parsed plan array: {plan_array}")

                    if plan_array and len(plan_array) > 0:
                        plan_data = plan_array[0]  # Первый элемент массива планов
                        logger.info(f"Plan data: {plan_data}, type: {type(plan_data)}")

                        if isinstance(plan_data, dict) and "Plan" in plan_data:
                            plan = dict(plan_data["Plan"])
                            plan["Query Type"] = query_type
                            
                            # Если это был конвертированный DML запрос, добавляем информацию
                            if query_type in ["INSERT", "UPDATE", "DELETE"] and select_query != query:
                                plan["Original Query Type"] = query_type
                                plan["Converted From"] = query[:100] + "..." if len(query) > 100 else query
                                plan["Converted Query"] = select_query
                                plan["Note"] = f"Plan generated from SELECT equivalent of {query_type} query"
                            
                            return plan
                        elif isinstance(plan_data, dict):
                            plan_data_copy = dict(plan_data)
                            plan_data_copy["Query Type"] = query_type
                            
                            # Если это был конвертированный DML запрос, добавляем информацию
                            if query_type in ["INSERT", "UPDATE", "DELETE"] and select_query != query:
                                plan_data_copy["Original Query Type"] = query_type
                                plan_data_copy["Converted From"] = query[:100] + "..." if len(query) > 100 else query
                                plan_data_copy["Converted Query"] = select_query
                                plan_data_copy["Note"] = f"Plan generated from SELECT equivalent of {query_type} query"
                            
                            return plan_data_copy
                        else:
                            # Если plan_data не является словарем, возвращаем базовую информацию
                            logger.warning(f"Plan data is not a dict: {plan_data}")
                            return {
                                "Node Type": "Unknown",
                                "Total Cost": 0,
                                "Plan Rows": 0,
                                "Plan Width": 0,
                                "Query Type": query_type,
                                "Description": f"Query type: {query_type}",
                            }
                    else:
                        logger.warning("Empty plan array")
                        return {
                            "Node Type": "Unknown",
                            "Total Cost": 0,
                            "Plan Rows": 0,
                            "Plan Width": 0,
                            "Query Type": query_type,
                            "Description": f"Query type: {query_type}",
                        }
                else:
                    raise Exception("No execution plan returned")

            except Exception as e:
                logger.error(f"Error explaining query: {e}")
                # Для DML запросов пытаемся конвертировать в SELECT и повторить EXPLAIN
                query_type = self._get_query_type(query)
                if query_type in ["INSERT", "UPDATE", "DELETE"]:
                    logger.info(f"Attempting to convert DML query to SELECT for analysis: {query_type}")
                    try:
                        # Конвертируем DML в SELECT
                        select_query = self._convert_dml_to_select(query)
                        
                        if select_query != query:  # Если конвертация прошла успешно
                            logger.info(f"Retrying EXPLAIN with converted SELECT query")
                            # Повторяем EXPLAIN с конвертированным запросом
                            return await self._explain_select_query(select_query, query_type, original_query=query)
                        else:
                            logger.warning(f"Failed to convert DML query, returning basic info: {e}")
                            return self._create_dml_plan_info(query_type, query)
                    except Exception as conversion_error:
                        logger.warning(f"DML conversion failed, returning basic info: {conversion_error}")
                        return self._create_dml_plan_info(query_type, query)
                else:
                    raise Exception(f"Query explanation error: {e}")

    def _create_dml_plan_info(self, query_type: str, query: str) -> Dict[str, Any]:
        """
        Создает базовую информацию о плане для DML запросов без EXPLAIN
        """
        # Извлекаем имя таблицы из запроса для анализа
        table_name = self._extract_table_name_from_dml(query)

        return {
            "Node Type": f"{query_type}",
            "Total Cost": 1.0,  # Базовая стоимость
            "Plan Rows": 1,     # Предполагаем 1 строку
            "Plan Width": 0,
            "Query Type": query_type,
            "Relation Name": table_name,
            "Description": f"DML operation on table: {table_name}",
            "Note": "Plan generated without EXPLAIN due to read-only permissions"
        }

    def _extract_table_name_from_dml(self, query: str) -> str:
        """
        Извлекает имя таблицы из DML запроса
        """
        query_upper = query.upper().strip()

        if query_upper.startswith("UPDATE"):
            # UPDATE table_name SET ...
            parts = query_upper.split()
            if len(parts) > 1:
                return parts[1]
        elif query_upper.startswith("INSERT"):
            # INSERT INTO table_name ...
            parts = query_upper.split()
            if len(parts) > 2 and parts[1] == "INTO":
                return parts[2]
        elif query_upper.startswith("DELETE"):
            # DELETE FROM table_name ...
            parts = query_upper.split()
            if len(parts) > 2 and parts[1] == "FROM":
                return parts[2]

        return "unknown_table"

    def _convert_dml_to_select(self, query: str) -> str:
        """
        Конвертирует DML запрос в SELECT-эквивалент для анализа плана выполнения
        """
        import re
        
        query_upper = query.upper().strip()
        query_lower = query.lower().strip()
        
        try:
            if query_upper.startswith("UPDATE"):
                return self._convert_update_to_select(query)
            elif query_upper.startswith("DELETE"):
                return self._convert_delete_to_select(query)
            elif query_upper.startswith("INSERT"):
                return self._convert_insert_to_select(query)
            else:
                return query  # Возвращаем оригинальный запрос, если это не DML
        except Exception as e:
            logger.warning(f"Failed to convert DML to SELECT: {e}")
            return query

    def _convert_update_to_select(self, query: str) -> str:
        """
        Конвертирует UPDATE запрос в SELECT для анализа плана
        UPDATE table SET col1=val1, col2=val2 WHERE condition
        -> SELECT * FROM table WHERE condition
        """
        import re
        
        # Извлекаем имя таблицы (может быть с алиасом)
        table_match = re.search(r'UPDATE\s+(\w+)(?:\s+\w+)?', query, re.IGNORECASE)
        if not table_match:
            return query
            
        table_name = table_match.group(1)
        
        # Извлекаем WHERE условие (более сложный regex для обработки подзапросов)
        where_match = re.search(r'WHERE\s+(.+?)(?:\s+ORDER\s+BY|\s+LIMIT|$)', query, re.IGNORECASE | re.DOTALL)
        where_clause = where_match.group(1).strip() if where_match else "1=1"
        
        # Создаем SELECT запрос
        select_query = f"SELECT * FROM {table_name} WHERE {where_clause}"
        
        logger.info(f"Converted UPDATE to SELECT: {select_query}")
        return select_query

    def _convert_delete_to_select(self, query: str) -> str:
        """
        Конвертирует DELETE запрос в SELECT для анализа плана
        DELETE FROM table WHERE condition
        -> SELECT * FROM table WHERE condition
        """
        import re
        
        # Извлекаем имя таблицы
        table_match = re.search(r'DELETE\s+FROM\s+(\w+)', query, re.IGNORECASE)
        if not table_match:
            return query
            
        table_name = table_match.group(1)
        
        # Извлекаем WHERE условие
        where_match = re.search(r'WHERE\s+(.+?)(?:\s+ORDER\s+BY|\s+LIMIT|$)', query, re.IGNORECASE | re.DOTALL)
        where_clause = where_match.group(1).strip() if where_match else "1=1"
        
        # Создаем SELECT запрос
        select_query = f"SELECT * FROM {table_name} WHERE {where_clause}"
        
        logger.info(f"Converted DELETE to SELECT: {select_query}")
        return select_query

    def _convert_insert_to_select(self, query: str) -> str:
        """
        Конвертирует INSERT запрос в SELECT для анализа плана
        INSERT INTO table (col1, col2) VALUES (val1, val2)
        -> SELECT * FROM table WHERE 1=0 (пустой результат, но показывает структуру)
        
        INSERT INTO table SELECT ... FROM other_table
        -> SELECT ... FROM other_table (анализируем подзапрос)
        """
        import re
        
        # Проверяем, есть ли подзапрос SELECT
        select_match = re.search(r'INSERT\s+INTO\s+\w+.*?SELECT\s+(.+?)(?:\s+ORDER\s+BY|\s+LIMIT|$)', query, re.IGNORECASE | re.DOTALL)
        if select_match:
            # Это INSERT ... SELECT, анализируем подзапрос
            select_part = select_match.group(1).strip()
            select_query = f"SELECT {select_part}"
            logger.info(f"Converted INSERT...SELECT to SELECT: {select_query}")
            return select_query
        
        # Для INSERT ... VALUES создаем запрос, который покажет структуру таблицы
        table_match = re.search(r'INSERT\s+INTO\s+(\w+)', query, re.IGNORECASE)
        if table_match:
            table_name = table_match.group(1)
            select_query = f"SELECT * FROM {table_name} WHERE 1=0"  # Пустой результат, но показывает план
            logger.info(f"Converted INSERT...VALUES to SELECT: {select_query}")
            return select_query
            
        return query

    async def _explain_select_query(self, select_query: str, original_query_type: str, original_query: str = None) -> Dict[str, Any]:
        """
        Выполняет EXPLAIN для конвертированного SELECT запроса
        """
        try:
            async with self.get_connection() as conn:
                # Выполняем EXPLAIN для SELECT запроса
                explain_query = f"EXPLAIN (FORMAT JSON) {select_query}"
                result = await conn.fetchval(explain_query)
                
                if result:
                    plan_array = result
                    if isinstance(plan_array, list) and len(plan_array) > 0:
                        plan_data = plan_array[0]
                        if "Plan" in plan_data:
                            plan = plan_data["Plan"]
                            
                            # Добавляем информацию о том, что это конвертированный запрос
                            plan["Original Query Type"] = original_query_type
                            plan["Converted From"] = original_query[:100] + "..." if original_query and len(original_query) > 100 else original_query
                            plan["Note"] = f"Plan generated from SELECT equivalent of {original_query_type} query"
                            
                            return {
                                "Node Type": plan.get("Node Type", "Unknown"),
                                "Total Cost": plan.get("Total Cost", 0),
                                "Plan Rows": plan.get("Plan Rows", 0),
                                "Plan Width": plan.get("Plan Width", 0),
                                "Query Type": original_query_type,
                                "Original Query": original_query,
                                "Converted Query": select_query,
                                "Plan": plan,
                                "Description": f"Converted {original_query_type} to SELECT for analysis"
                            }
                
                # Если не удалось получить план, возвращаем базовую информацию
                return self._create_dml_plan_info(original_query_type, original_query or select_query)
                
        except Exception as e:
            logger.error(f"Error explaining converted SELECT query: {e}")
            return self._create_dml_plan_info(original_query_type, original_query or select_query)

    def _get_query_type(self, query: str) -> str:
        """
        Определяет тип SQL запроса
        """
        query_upper = query.strip().upper()

        if query_upper.startswith("SELECT") or query_upper.startswith("WITH"):
            return "SELECT"
        elif query_upper.startswith("INSERT"):
            return "INSERT"
        elif query_upper.startswith("UPDATE"):
            return "UPDATE"
        elif query_upper.startswith("DELETE"):
            return "DELETE"
        elif query_upper.startswith("CREATE"):
            return "CREATE"
        elif query_upper.startswith("DROP"):
            return "DROP"
        elif query_upper.startswith("ALTER"):
            return "ALTER"
        elif query_upper.startswith("EXPLAIN"):
            return "EXPLAIN"
        else:
            return "UNKNOWN"

    async def analyze_query_performance(self, query: str) -> Dict[str, Any]:
        """
        Анализирует производительность запроса
        """
        plan = await self.explain_query(query)

        # Извлекаем метрики из плана выполнения
        total_cost = plan.get("Total Cost", 0)
        execution_time = plan.get("Actual Total Time", 0)  # В мс
        rows = plan.get("Actual Rows", 0)
        width = plan.get("Plan Width", 0)

        # Анализируем узлы плана для подсчета I/O операций
        io_operations = self._count_io_operations(plan)

        return {
            "total_cost": total_cost,
            "execution_time": execution_time,
            "rows": rows,
            "width": width,
            "io_operations": io_operations,
            "plan_json": plan,
        }

    def _count_io_operations(self, plan: Dict[str, Any]) -> int:
        """
        Подсчитывает количество I/O операций в плане
        """
        io_count = 0

        def count_io_recursive(node):
            nonlocal io_count

            node_type = node.get("Node Type", "")

            # Подсчитываем различные типы I/O операций
            if "Seq Scan" in node_type:
                io_count += 1
            elif "Index Scan" in node_type:
                io_count += 1
            elif "Index Only Scan" in node_type:
                io_count += 1
            elif "Bitmap" in node_type:
                io_count += 1
            elif "Sort" in node_type:
                io_count += 1
            elif "Hash" in node_type:
                io_count += 1

            # Рекурсивно обрабатываем дочерние узлы
            for child in node.get("Plans", []):
                count_io_recursive(child)

        count_io_recursive(plan)
        return io_count

    async def get_database_info(self) -> Dict[str, Any]:
        """
        Получает информацию о базе данных
        """
        async with self.get_connection() as conn:
            try:
                # Версия PostgreSQL
                version_result = await conn.fetchrow("SELECT version()")
                version = version_result["version"]

                # Размер базы данных
                size_result = await conn.fetchrow(
                    """
                    SELECT pg_size_pretty(pg_database_size(current_database())) as size
                """
                )
                db_size = size_result["size"]

                # Количество таблиц
                table_result = await conn.fetchrow(
                    """
                    SELECT count(*) as table_count
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                """
                )
                table_count = table_result["table_count"]

                # Количество индексов
                index_result = await conn.fetchrow(
                    """
                    SELECT count(*) as index_count
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                """
                )
                index_count = index_result["index_count"]

                return {
                    "version": version,
                    "database_size": db_size,
                    "table_count": table_count,
                    "index_count": index_count,
                }

            except Exception as e:
                logger.error(f"Error getting database info: {e}")
                raise Exception(f"Database info error: {e}")

    async def get_table_statistics(self) -> Dict[str, Any]:
        """
        Получает статистику по всем таблицам в базе данных
        """
        try:
            async with self.get_connection() as conn:
                # Получаем информацию о размерах таблиц и количестве строк
                query = """
                SELECT
                    schemaname,
                    relname as tablename,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes,
                    n_live_tup as live_tuples,
                    n_dead_tup as dead_tuples,
                    last_vacuum,
                    last_autovacuum,
                    last_analyze,
                    last_autoanalyze
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                ORDER BY n_live_tup DESC
                """

                rows = await conn.fetch(query)

                # Получаем размеры таблиц
                size_query = """
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size_pretty,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                """

                size_rows = await conn.fetch(size_query)

                # Объединяем данные
                table_stats = {}
                for row in rows:
                    table_name = row['tablename']
                    table_stats[table_name] = {
                        'inserts': row['inserts'],
                        'updates': row['updates'],
                        'deletes': row['deletes'],
                        'live_tuples': row['live_tuples'],
                        'dead_tuples': row['dead_tuples'],
                        'last_vacuum': row['last_vacuum'],
                        'last_autovacuum': row['last_autovacuum'],
                        'last_analyze': row['last_analyze'],
                        'last_autoanalyze': row['last_autoanalyze']
                    }

                # Добавляем размеры таблиц
                for row in size_rows:
                    table_name = row['tablename']
                    if table_name in table_stats:
                        table_stats[table_name]['size_pretty'] = row['size_pretty']
                        table_stats[table_name]['size_bytes'] = row['size_bytes']

                return {
                    'tables': table_stats,
                    'total_tables': len(table_stats),
                    'total_live_tuples': sum(stats['live_tuples'] for stats in table_stats.values()),
                    'total_size_bytes': sum(stats.get('size_bytes', 0) for stats in table_stats.values())
                }

        except Exception as e:
            logger.error(f"Failed to get table statistics: {e}")
            return {'tables': {}, 'total_tables': 0, 'total_live_tuples': 0, 'total_size_bytes': 0}

    async def test_connection(self) -> bool:
        """
        Проверяет подключение к базе данных
        """
        try:
            async with self.get_connection() as conn:
                await conn.fetchval("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
