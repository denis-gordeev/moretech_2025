import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class PostgreSQLLogAnalyzer:
    """Анализатор логов PostgreSQL для выявления паттернов и проблем"""

    def __init__(self, log_directory: Optional[str] = None):
        self.log_directory = log_directory or "/var/log/postgresql"
        self.log_patterns = {
            "slow_query": re.compile(r"LOG:\s+duration:\s+(\d+\.\d+)\s+ms\s+statement:\s+(.+)", re.IGNORECASE),
            "error": re.compile(r"ERROR:\s+(.+)", re.IGNORECASE),
            "connection": re.compile(r"LOG:\s+connection\s+(?:received|authorized):\s+(.+)", re.IGNORECASE),
            "checkpoint": re.compile(r"LOG:\s+checkpoint\s+(.+)", re.IGNORECASE),
            "deadlock": re.compile(r"ERROR:\s+deadlock\s+detected", re.IGNORECASE),
            "lock_timeout": re.compile(
                r"ERROR:\s+canceling\s+statement\s+because\s+of\s+lock\s+timeout", re.IGNORECASE
            ),
        }

    async def analyze_logs(self, hours_back: int = 24) -> Dict[str, Any]:
        """
        Анализирует логи PostgreSQL за указанный период
        """
        try:
            log_files = await self._find_log_files()
            if not log_files:
                logger.warning("No PostgreSQL log files found")
                return self._empty_analysis()

            analysis_results = {
                "slow_queries": [],
                "errors": [],
                "connection_issues": [],
                "deadlocks": [],
                "lock_timeouts": [],
                "checkpoints": [],
                "summary": {},
            }

            cutoff_time = datetime.now() - timedelta(hours=hours_back)

            for log_file in log_files:
                await self._analyze_log_file(log_file, cutoff_time, analysis_results)

            # Генерируем сводку
            analysis_results["summary"] = self._generate_summary(analysis_results)

            return analysis_results

        except Exception as e:
            logger.error(f"Error analyzing logs: {e}")
            return self._empty_analysis()

    async def _find_log_files(self) -> List[Path]:
        """Находит файлы логов PostgreSQL"""
        log_files = []
        log_dir = Path(self.log_directory)

        if not log_dir.exists():
            logger.warning(f"Log directory {self.log_directory} does not exist")
            return log_files

        # Ищем файлы логов PostgreSQL
        for pattern in ["postgresql-*.log", "postgresql.log", "*.log"]:
            log_files.extend(log_dir.glob(pattern))

        return sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)

    async def _analyze_log_file(self, log_file: Path, cutoff_time: datetime, results: Dict[str, Any]):
        """Анализирует отдельный файл лога"""
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        # Парсим временную метку
                        timestamp = self._extract_timestamp(line)
                        if timestamp and timestamp < cutoff_time:
                            continue

                        # Анализируем строку на предмет различных паттернов
                        self._analyze_line(line, timestamp, results)

                    except Exception as e:
                        logger.debug(f"Error parsing line {line_num} in {log_file}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Error reading log file {log_file}: {e}")

    def _extract_timestamp(self, line: str) -> Optional[datetime]:
        """Извлекает временную метку из строки лога"""
        # Паттерн для временной метки PostgreSQL
        timestamp_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)")
        match = timestamp_pattern.search(line)

        if match:
            try:
                timestamp_str = match.group(1)
                # Пробуем разные форматы
                for fmt in ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        return datetime.strptime(timestamp_str, fmt)
                    except ValueError:
                        continue
            except Exception:
                pass

        return None

    def _analyze_line(self, line: str, timestamp: Optional[datetime], results: Dict[str, Any]):
        """Анализирует строку лога на предмет различных паттернов"""

        # Медленные запросы
        slow_match = self.log_patterns["slow_query"].search(line)
        if slow_match:
            duration = float(slow_match.group(1))
            statement = slow_match.group(2).strip()

            # Фильтруем только действительно медленные запросы (>100ms)
            if duration > 100:
                results["slow_queries"].append(
                    {
                        "timestamp": timestamp.isoformat() if timestamp else None,
                        "duration_ms": duration,
                        "statement": statement[:500],  # Ограничиваем длину
                        "severity": "high" if duration > 1000 else "medium",
                    }
                )

        # Ошибки
        error_match = self.log_patterns["error"].search(line)
        if error_match:
            error_msg = error_match.group(1).strip()
            results["errors"].append(
                {
                    "timestamp": timestamp.isoformat() if timestamp else None,
                    "message": error_msg[:500],
                    "type": self._classify_error(error_msg),
                }
            )

        # Дедлоки
        if self.log_patterns["deadlock"].search(line):
            results["deadlocks"].append(
                {"timestamp": timestamp.isoformat() if timestamp else None, "message": "Deadlock detected"}
            )

        # Таймауты блокировок
        if self.log_patterns["lock_timeout"].search(line):
            results["lock_timeouts"].append(
                {"timestamp": timestamp.isoformat() if timestamp else None, "message": "Lock timeout detected"}
            )

        # Проблемы с подключениями
        conn_match = self.log_patterns["connection"].search(line)
        if conn_match:
            conn_info = conn_match.group(1).strip()
            if "failed" in conn_info.lower() or "rejected" in conn_info.lower():
                results["connection_issues"].append(
                    {"timestamp": timestamp.isoformat() if timestamp else None, "message": conn_info[:500]}
                )

        # Чекпоинты
        checkpoint_match = self.log_patterns["checkpoint"].search(line)
        if checkpoint_match:
            checkpoint_info = checkpoint_match.group(1).strip()
            results["checkpoints"].append(
                {"timestamp": timestamp.isoformat() if timestamp else None, "message": checkpoint_info[:500]}
            )

    def _classify_error(self, error_msg: str) -> str:
        """Классифицирует тип ошибки"""
        error_lower = error_msg.lower()

        if "connection" in error_lower:
            return "connection"
        elif "permission" in error_lower or "access" in error_lower:
            return "permission"
        elif "syntax" in error_lower:
            return "syntax"
        elif "constraint" in error_lower:
            return "constraint"
        elif "timeout" in error_lower:
            return "timeout"
        else:
            return "other"

    def _generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Генерирует сводку анализа"""
        summary = {
            "total_slow_queries": len(results["slow_queries"]),
            "total_errors": len(results["errors"]),
            "total_deadlocks": len(results["deadlocks"]),
            "total_lock_timeouts": len(results["lock_timeouts"]),
            "total_connection_issues": len(results["connection_issues"]),
            "total_checkpoints": len(results["checkpoints"]),
            "slowest_query_duration": 0,
            "error_types": {},
            "recommendations": [],
        }

        # Находим самый медленный запрос
        if results["slow_queries"]:
            summary["slowest_query_duration"] = max(q["duration_ms"] for q in results["slow_queries"])

        # Подсчитываем типы ошибок
        for error in results["errors"]:
            error_type = error["type"]
            summary["error_types"][error_type] = summary["error_types"].get(error_type, 0) + 1

        # Генерируем рекомендации
        summary["recommendations"] = self._generate_recommendations(results)

        return summary

    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Генерирует рекомендации на основе анализа логов"""
        recommendations = []

        if results["slow_queries"]:
            slow_count = len(results["slow_queries"])
            if slow_count > 10:
                recommendations.append(
                    f"Обнаружено {slow_count} медленных запросов. Рекомендуется провести анализ производительности."
                )

        if results["deadlocks"]:
            recommendations.append(
                f"Обнаружено {len(results['deadlocks'])} дедлоков. Проверьте порядок блокировок в транзакциях."
            )

        if results["lock_timeouts"]:
            recommendations.append(
                f"Обнаружено {len(results['lock_timeouts'])} таймаутов блокировок. Рассмотрите увеличение lock_timeout."
            )

        if results["connection_issues"]:
            recommendations.append(
                f"Обнаружено {len(results['connection_issues'])} проблем с подключениями. "
                f"Проверьте настройки подключений."
            )

        return recommendations

    def _empty_analysis(self) -> Dict[str, Any]:
        """Возвращает пустой результат анализа"""
        return {
            "slow_queries": [],
            "errors": [],
            "connection_issues": [],
            "deadlocks": [],
            "lock_timeouts": [],
            "checkpoints": [],
            "summary": {
                "total_slow_queries": 0,
                "total_errors": 0,
                "total_deadlocks": 0,
                "total_lock_timeouts": 0,
                "total_connection_issues": 0,
                "total_checkpoints": 0,
                "slowest_query_duration": 0,
                "error_types": {},
                "recommendations": [],
            },
        }
