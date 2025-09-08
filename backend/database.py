import psycopg2
import psycopg2.extras
import json
from typing import Dict, Any, Optional
from contextlib import contextmanager
from config import settings
import logging

logger = logging.getLogger(__name__)


class PostgreSQLAnalyzer:
    """Класс для анализа PostgreSQL запросов"""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or settings.database_url
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для подключения к БД"""
        conn = None
        try:
            conn = psycopg2.connect(self.database_url)
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def explain_query(self, query: str) -> Dict[str, Any]:
        """
        Получает план выполнения запроса без его выполнения
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                try:
                    # Получаем план выполнения в JSON формате
                    explain_query = f"EXPLAIN (ANALYZE false, BUFFERS false, FORMAT JSON) {query}"
                    cursor.execute(explain_query)
                    result = cursor.fetchone()
                    
                    if result and 'QUERY PLAN' in result:
                        # EXPLAIN возвращает результат в формате [{'Plan': {...}}]
                        plan_data = result['QUERY PLAN'][0]  # Первый элемент массива планов
                        if isinstance(plan_data, dict) and 'Plan' in plan_data:
                            return plan_data['Plan']
                        else:
                            return plan_data
                    else:
                        raise Exception("No execution plan returned")
                        
                except Exception as e:
                    logger.error(f"Error explaining query: {e}")
                    raise Exception(f"Query explanation error: {e}")
    
    def analyze_query_performance(self, query: str) -> Dict[str, Any]:
        """
        Анализирует производительность запроса
        """
        plan = self.explain_query(query)
        
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
    
    def get_database_info(self) -> Dict[str, Any]:
        """
        Получает информацию о базе данных
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                try:
                    # Версия PostgreSQL
                    cursor.execute("SELECT version()")
                    version = cursor.fetchone()['version']
                    
                    # Размер базы данных
                    cursor.execute("""
                        SELECT pg_size_pretty(pg_database_size(current_database())) as size
                    """)
                    db_size = cursor.fetchone()['size']
                    
                    # Количество таблиц
                    cursor.execute("""
                        SELECT count(*) as table_count 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                    """)
                    table_count = cursor.fetchone()['table_count']
                    
                    # Количество индексов
                    cursor.execute("""
                        SELECT count(*) as index_count 
                        FROM pg_indexes 
                        WHERE schemaname = 'public'
                    """)
                    index_count = cursor.fetchone()['index_count']
                    
                    return {
                        'version': version,
                        'database_size': db_size,
                        'table_count': table_count,
                        'index_count': index_count
                    }
                    
                except Exception as e:
                    logger.error(f"Error getting database info: {e}")
                    raise Exception(f"Database info error: {e}")
    
    def test_connection(self) -> bool:
        """
        Проверяет подключение к базе данных
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
