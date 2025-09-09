import asyncpg
import logging
from typing import Dict, Any
from config import settings

logger = logging.getLogger(__name__)


class TableStatsService:
    """Сервис для сбора статистики таблиц"""

    def __init__(self):
        self.table_stats = {}
        self._connection_string = settings.database_url

    async def get_connection(self):
        """Получает подключение к базе данных"""
        return await asyncpg.connect(self._connection_string)

    async def collect_table_statistics(self) -> Dict[str, Any]:
        """
        Собирает статистику по всем таблицам в базе данных
        """
        async with self.get_connection() as conn:
            try:
                # Получаем статистику по таблицам
                table_stats_query = """
                    SELECT
                        schemaname,
                        relname as tablename,
                        n_live_tup as row_count,
                        n_dead_tup as dead_rows,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||relname)) as table_size,
                        pg_total_relation_size(schemaname||'.'||relname) as table_size_bytes,
                        last_vacuum,
                        last_autovacuum,
                        last_analyze,
                        last_autoanalyze
                    FROM pg_stat_user_tables
                    WHERE schemaname = 'public'
                    ORDER BY n_live_tup DESC
                """

                table_rows = await conn.fetch(table_stats_query)

                # Получаем информацию об индексах для каждой таблицы
                index_stats_query = """
                    SELECT
                        schemaname,
                        tablename,
                        indexname,
                        idx_scan as index_scans,
                        idx_tup_read as index_tuples_read,
                        idx_tup_fetch as index_tuples_fetched
                    FROM pg_stat_user_indexes
                    WHERE schemaname = 'public'
                    ORDER BY tablename, idx_scan DESC
                """

                index_rows = await conn.fetch(index_stats_query)

                # Группируем индексы по таблицам
                indexes_by_table = {}
                for row in index_rows:
                    table_name = row["tablename"]
                    if table_name not in indexes_by_table:
                        indexes_by_table[table_name] = []
                    indexes_by_table[table_name].append(
                        {
                            "index_name": row["indexname"],
                            "scans": row["index_scans"],
                            "tuples_read": row["index_tuples_read"],
                            "tuples_fetched": row["index_tuples_fetched"],
                        }
                    )

                # Формируем итоговую статистику
                table_stats = {}
                total_rows = 0
                total_size_bytes = 0

                for row in table_rows:
                    table_name = row["tablename"]
                    row_count = row["row_count"] or 0
                    total_rows += row_count
                    total_size_bytes += row["table_size_bytes"] or 0

                    table_stats[table_name] = {
                        "row_count": row_count,
                        "dead_rows": row["dead_rows"] or 0,
                        "table_size": row["table_size"],
                        "table_size_bytes": row["table_size_bytes"] or 0,
                        "indexes": indexes_by_table.get(table_name, []),
                        "last_vacuum": row["last_vacuum"],
                        "last_autovacuum": row["last_autovacuum"],
                        "last_analyze": row["last_analyze"],
                        "last_autoanalyze": row["last_autoanalyze"],
                    }

                # Добавляем общую статистику
                result = {
                    "tables": table_stats,
                    "summary": {
                        "total_tables": len(table_stats),
                        "total_rows": total_rows,
                        "total_size_bytes": total_size_bytes,
                        "total_size_pretty": self._format_bytes(total_size_bytes),
                    },
                }

                logger.info(f"Collected statistics for {len(table_stats)} tables, total {total_rows} rows")
                return result

            except Exception as e:
                logger.error(f"Error collecting table statistics: {e}")
                return {
                    "tables": {},
                    "summary": {"total_tables": 0, "total_rows": 0, "total_size_bytes": 0, "total_size_pretty": "0 B"},
                }

    def _format_bytes(self, bytes_value: int) -> str:
        """Форматирует размер в байтах в читаемый вид"""
        if bytes_value == 0:
            return "0 B"

        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0

        return f"{bytes_value:.1f} PB"

    def get_table_info_for_llm(self, table_name: str = None) -> Dict[str, Any]:
        """
        Возвращает информацию о таблицах в формате, удобном для LLM
        """
        if not self.table_stats:
            return {}

        if table_name:
            # Возвращаем информацию о конкретной таблице
            table_info = self.table_stats.get("tables", {}).get(table_name)
            if not table_info:
                return {}

            return {
                "table_name": table_name,
                "row_count": table_info["row_count"],
                "table_size": table_info["table_size"],
                "indexes_count": len(table_info["indexes"]),
                "dead_rows_ratio": (table_info["dead_rows"] / max(table_info["row_count"], 1)) * 100,
            }
        else:
            # Возвращаем сводную информацию по всем таблицам
            tables = self.table_stats.get("tables", {})
            summary = self.table_stats.get("summary", {})

            # Создаем краткую сводку по таблицам
            table_summary = []
            for name, info in tables.items():
                table_summary.append(
                    {
                        "name": name,
                        "rows": info["row_count"],
                        "size": info["table_size"],
                        "indexes": len(info["indexes"]),
                    }
                )

            return {
                "total_tables": summary.get("total_tables", 0),
                "total_rows": summary.get("total_rows", 0),
                "total_size": summary.get("total_size_pretty", "0 B"),
                "tables": table_summary,
            }

    def get_table_row_count(self, table_name: str) -> int:
        """Возвращает количество строк в таблице"""
        if not self.table_stats:
            return 0

        table_info = self.table_stats.get("tables", {}).get(table_name)
        return table_info["row_count"] if table_info else 0
