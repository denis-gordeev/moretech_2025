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
