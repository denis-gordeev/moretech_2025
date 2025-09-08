import psycopg2
import psycopg2.extras
import asyncpg
import json
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
                if query_type in ['SELECT', 'WITH']:
                    # Для SELECT и WITH используем обычный EXPLAIN
                    explain_query = f"EXPLAIN (ANALYZE false, BUFFERS false, FORMAT JSON) {query}"
                elif query_type in ['INSERT', 'UPDATE', 'DELETE']:
                    # Для DML запросов используем EXPLAIN с оберткой в транзакцию
                    explain_query = f"EXPLAIN (ANALYZE false, BUFFERS false, FORMAT JSON) {query}"
                else:
                    # Для других типов (CREATE, DROP, ALTER) возвращаем базовую информацию
                    return {
                        'Node Type': 'Utility',
                        'Total Cost': 0,
                        'Plan Rows': 0,
                        'Plan Width': 0,
                        'Query Type': query_type,
                        'Description': f'Utility command: {query_type}'
                    }
                
                result = await conn.fetchrow(explain_query)
                logger.info(f"EXPLAIN result: {result}")
                
                if result and 'QUERY PLAN' in result:
                    # EXPLAIN возвращает результат как строку JSON, нужно распарсить
                    query_plan_json = result['QUERY PLAN']
                    logger.info(f"Query plan JSON: {query_plan_json}")
                    
                    # Парсим JSON строку
                    import json
                    plan_array = json.loads(query_plan_json)
                    logger.info(f"Parsed plan array: {plan_array}")
                    
                    if plan_array and len(plan_array) > 0:
                        plan_data = plan_array[0]  # Первый элемент массива планов
                        logger.info(f"Plan data: {plan_data}, type: {type(plan_data)}")
                        
                        if isinstance(plan_data, dict) and 'Plan' in plan_data:
                            plan = dict(plan_data['Plan'])
                            plan['Query Type'] = query_type
                            return plan
                        elif isinstance(plan_data, dict):
                            plan_data_copy = dict(plan_data)
                            plan_data_copy['Query Type'] = query_type
                            return plan_data_copy
                        else:
                            # Если plan_data не является словарем, возвращаем базовую информацию
                            logger.warning(f"Plan data is not a dict: {plan_data}")
                            return {
                                'Node Type': 'Unknown',
                                'Total Cost': 0,
                                'Plan Rows': 0,
                                'Plan Width': 0,
                                'Query Type': query_type,
                                'Description': f'Query type: {query_type}'
                            }
                    else:
                        logger.warning("Empty plan array")
                        return {
                            'Node Type': 'Unknown',
                            'Total Cost': 0,
                            'Plan Rows': 0,
                            'Plan Width': 0,
                            'Query Type': query_type,
                            'Description': f'Query type: {query_type}'
                        }
                else:
                    raise Exception("No execution plan returned")
                    
            except Exception as e:
                logger.error(f"Error explaining query: {e}")
                raise Exception(f"Query explanation error: {e}")
    
    def _get_query_type(self, query: str) -> str:
        """
        Определяет тип SQL запроса
        """
        query_upper = query.strip().upper()
        
        if query_upper.startswith('SELECT') or query_upper.startswith('WITH'):
            return 'SELECT'
        elif query_upper.startswith('INSERT'):
            return 'INSERT'
        elif query_upper.startswith('UPDATE'):
            return 'UPDATE'
        elif query_upper.startswith('DELETE'):
            return 'DELETE'
        elif query_upper.startswith('CREATE'):
            return 'CREATE'
        elif query_upper.startswith('DROP'):
            return 'DROP'
        elif query_upper.startswith('ALTER'):
            return 'ALTER'
        elif query_upper.startswith('EXPLAIN'):
            return 'EXPLAIN'
        else:
            return 'UNKNOWN'
    
    async def analyze_query_performance(self, query: str) -> Dict[str, Any]:
        """
        Анализирует производительность запроса
        """
        plan = await self.explain_query(query)
        
        # Извлекаем метрики из плана выполнения
        total_cost = plan.get('Total Cost', 0)
        execution_time = plan.get('Actual Total Time', 0)  # В мс
        rows = plan.get('Actual Rows', 0)
        width = plan.get('Plan Width', 0)
        
        # Анализируем узлы плана для подсчета I/O операций
        io_operations = self._count_io_operations(plan)
        
        return {
            'total_cost': total_cost,
            'execution_time': execution_time,
            'rows': rows,
            'width': width,
            'io_operations': io_operations,
            'plan_json': plan
        }
    
    def _count_io_operations(self, plan: Dict[str, Any]) -> int:
        """
        Подсчитывает количество I/O операций в плане
        """
        io_count = 0
        
        def count_io_recursive(node):
            nonlocal io_count
            
            node_type = node.get('Node Type', '')
            
            # Подсчитываем различные типы I/O операций
            if 'Seq Scan' in node_type:
                io_count += 1
            elif 'Index Scan' in node_type:
                io_count += 1
            elif 'Index Only Scan' in node_type:
                io_count += 1
            elif 'Bitmap' in node_type:
                io_count += 1
            elif 'Sort' in node_type:
                io_count += 1
            elif 'Hash' in node_type:
                io_count += 1
            
            # Рекурсивно обрабатываем дочерние узлы
            for child in node.get('Plans', []):
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
                version = version_result['version']
                
                # Размер базы данных
                size_result = await conn.fetchrow("""
                    SELECT pg_size_pretty(pg_database_size(current_database())) as size
                """)
                db_size = size_result['size']
                
                # Количество таблиц
                table_result = await conn.fetchrow("""
                    SELECT count(*) as table_count 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                table_count = table_result['table_count']
                
                # Количество индексов
                index_result = await conn.fetchrow("""
                    SELECT count(*) as index_count 
                    FROM pg_indexes 
                    WHERE schemaname = 'public'
                """)
                index_count = index_result['index_count']
                
                return {
                    'version': version,
                    'database_size': db_size,
                    'table_count': table_count,
                    'index_count': index_count
                }
                
            except Exception as e:
                logger.error(f"Error getting database info: {e}")
                raise Exception(f"Database info error: {e}")
    
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
