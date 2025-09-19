from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class PriorityLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class QueryAnalysisRequest(BaseModel):
    query: str = Field(..., description="SQL запрос для анализа")
    database_url: Optional[str] = Field(None, description="URL базы данных (опционально)")
    database_profile_id: Optional[str] = Field(None, description="ID профиля базы данных (опционально)")


class ExecutionPlan(BaseModel):
    """Модель плана выполнения запроса"""

    total_cost: float = Field(..., description="Общая стоимость запроса")
    execution_time: float = Field(..., description="Ожидаемое время выполнения в мс")
    rows: int = Field(..., description="Количество строк")
    width: int = Field(..., description="Средняя ширина строки")
    plan_json: Dict[str, Any] = Field(..., description="JSON план выполнения")


class ResourceMetrics(BaseModel):
    """Метрики ресурсоемкости"""

    cpu_usage: float = Field(..., description="Ожидаемое использование CPU")
    memory_usage: float = Field(..., description="Ожидаемое использование памяти в MB")
    io_operations: int = Field(..., description="Количество I/O операций")
    disk_reads: int = Field(..., description="Количество чтений с диска")
    disk_writes: int = Field(..., description="Количество записей на диск")
    # Дополнительные поля для расширенного анализа
    disk_io: Optional[float] = Field(None, description="Общий объем дисковых операций в MB")
    network_io: Optional[float] = Field(None, description="Объем сетевого трафика в KB")
    execution_time: Optional[float] = Field(None, description="Ожидаемое время выполнения в мс")
    rows_processed: Optional[int] = Field(None, description="Количество обработанных строк")
    index_usage: Optional[float] = Field(None, description="Процент использования индексов")
    cache_hit_ratio: Optional[float] = Field(None, description="Процент попаданий в кэш")
    lock_contention: Optional[float] = Field(None, description="Уровень конкуренции за блокировки")


class OptimizationRecommendation(BaseModel):
    """Рекомендация по оптимизации"""

    type: str = Field(..., description="Тип рекомендации (index, query_rewrite, config, etc.)")
    priority: PriorityLevel = Field(..., description="Приоритет рекомендации")
    title: str = Field(..., description="Заголовок рекомендации")
    description: str = Field(..., description="Подробное описание")
    potential_improvement: str = Field(..., description="Потенциальное улучшение")
    implementation: str = Field(..., description="Как реализовать")
    estimated_speedup: Optional[float] = Field(None, description="Ожидаемое ускорение в %")


class QueryAnalysis(BaseModel):
    """Результат анализа запроса"""

    query: str = Field(..., description="Исходный запрос")
    rewritten_query: Optional[str] = Field(None, description="Оптимизированная версия запроса (если требуется)")
    execution_plan: ExecutionPlan = Field(..., description="План выполнения")
    resource_metrics: ResourceMetrics = Field(..., description="Метрики ресурсов")
    recommendations: List[OptimizationRecommendation] = Field(..., description="Рекомендации")
    warnings: List[str] = Field(default_factory=list, description="Предупреждения")
    analysis_timestamp: datetime = Field(default_factory=datetime.now, description="Время анализа")


class DatabaseConfig(BaseModel):
    """Конфигурация базы данных"""

    host: str
    port: int = 5432
    database: str
    username: str
    password: str


class HealthCheck(BaseModel):
    """Статус здоровья сервиса"""

    status: str
    timestamp: datetime
    database_connected: bool
    openai_available: bool


# Модели для ответа LLM
class LLMResourceMetrics(BaseModel):
    """Метрики ресурсоемкости от LLM"""

    cpu_usage: float = Field(..., description="Ожидаемое использование CPU (0-100)")
    memory_usage: float = Field(..., description="Ожидаемое использование памяти в MB")
    io_operations: int = Field(..., description="Количество I/O операций")
    disk_reads: int = Field(..., description="Количество чтений с диска")
    disk_writes: int = Field(..., description="Количество записей на диск")
    # Дополнительные поля для расширенного анализа
    disk_io: Optional[float] = Field(
        None, description="Общий объем дисковых операций в MB (сумма disk_reads + disk_writes)"
    )
    network_io: Optional[float] = Field(None, description="Объем сетевого трафика в KB (для распределенных запросов)")
    execution_time: Optional[float] = Field(
        None, description="Ожидаемое время выполнения в мс (на основе плана выполнения)"
    )
    rows_processed: Optional[int] = Field(None, description="Количество обработанных строк (из плана выполнения)")
    index_usage: Optional[float] = Field(
        None, description="Процент использования индексов (0-100, на основе анализа плана)"
    )
    cache_hit_ratio: Optional[float] = Field(
        None, description="Процент попаданий в кэш буферов (0-100, на основе статистики)"
    )
    lock_contention: Optional[float] = Field(
        None, description="Уровень конкуренции за блокировки (0-100, для DML операций)"
    )


class LLMOptimizationRecommendation(BaseModel):
    """Рекомендация по оптимизации от LLM"""

    type: str = Field(..., description="Тип рекомендации на русском языке")
    priority: str = Field(..., description="Приоритет: high, medium или low")
    title: str = Field(..., description="Заголовок рекомендации на русском языке")
    description: str = Field(..., description="Подробное описание на русском языке")
    potential_improvement: str = Field(..., description="Потенциальное улучшение на русском языке")
    implementation: str = Field(..., description="Как реализовать на русском языке")
    estimated_speedup: Optional[float] = Field(None, description="Ожидаемое ускорение в процентах")


class LLMAnalysisResponse(BaseModel):
    """Ответ от LLM для анализа запроса"""

    rewritten_query: Optional[str] = Field(None, description="Оптимизированная версия запроса или null")
    resource_metrics: LLMResourceMetrics = Field(..., description="Метрики ресурсов")
    recommendations: List[LLMOptimizationRecommendation] = Field(..., description="Список рекомендаций")
    warnings: List[str] = Field(default_factory=list, description="Список предупреждений на русском языке")
