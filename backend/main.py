from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List
import logging
from datetime import datetime

from models import (
    QueryAnalysisRequest, 
    QueryAnalysis, 
    ExecutionPlan, 
    HealthCheck,
    DatabaseConfig
)
from database import PostgreSQLAnalyzer
from llm_service import LLMAnalyzer
from config import settings

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание FastAPI приложения
app = FastAPI(
    title=settings.app_name,
    description="Умный инструмент для анализа SQL-запросов PostgreSQL",
    version="1.0.0"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация сервисов
db_analyzer = PostgreSQLAnalyzer()
llm_analyzer = LLMAnalyzer()


@app.get("/", response_model=dict)
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "PostgreSQL Query Analyzer API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Проверка здоровья сервиса"""
    try:
        db_connected = db_analyzer.test_connection()
        openai_available = llm_analyzer.test_connection()
        
        status = "healthy" if db_connected and openai_available else "unhealthy"
        
        return HealthCheck(
            status=status,
            timestamp=datetime.now(),
            database_connected=db_connected,
            openai_available=openai_available
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheck(
            status="unhealthy",
            timestamp=datetime.now(),
            database_connected=False,
            openai_available=False
        )


@app.post("/analyze", response_model=QueryAnalysis)
async def analyze_query(request: QueryAnalysisRequest):
    """
    Анализирует SQL запрос и возвращает рекомендации по оптимизации
    """
    try:
        # Валидация запроса
        if len(request.query.strip()) == 0:
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        if len(request.query) > settings.max_query_length:
            raise HTTPException(
                status_code=400, 
                detail=f"Query too long. Maximum length is {settings.max_query_length} characters"
            )
        
        # Используем переданный URL БД или дефолтный
        analyzer = db_analyzer
        if request.database_url:
            analyzer = PostgreSQLAnalyzer(request.database_url)
        
        # Проверяем, является ли запрос цепочкой (содержит точку с запятой)
        queries = [q.strip() for q in request.query.split(';') if q.strip()]
        
        if len(queries) > 1:
            logger.info(f"Analyzing query chain with {len(queries)} queries...")
            # Для цепочки запросов анализируем первый запрос как основной
            main_query = queries[0]
            all_queries_text = request.query
        else:
            logger.info(f"Analyzing single query: {request.query[:100]}...")
            main_query = request.query
            all_queries_text = request.query
        
        # Получаем план выполнения для основного запроса
        plan_data = analyzer.analyze_query_performance(main_query)
        
        # Создаем объект плана выполнения
        execution_plan = ExecutionPlan(
            total_cost=plan_data['total_cost'],
            execution_time=plan_data['execution_time'],
            rows=plan_data['rows'],
            width=plan_data['width'],
            plan_json=plan_data['plan_json']
        )
        
        # Анализируем с помощью LLM (передаем всю цепочку для контекста)
        logger.info("Running LLM analysis...")
        llm_result = llm_analyzer.analyze_query_with_llm(
            all_queries_text, 
            plan_data['plan_json']
        )
        
        # Создаем результат анализа
        analysis = QueryAnalysis(
            query=request.query,
            rewritten_query=llm_result.get('rewritten_query'),
            execution_plan=execution_plan,
            resource_metrics=llm_result['resource_metrics'],
            recommendations=llm_result['recommendations'],
            warnings=llm_result['warnings']
        )
        
        logger.info(f"Analysis completed. Found {len(analysis.recommendations)} recommendations")
        return analysis
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/database/info")
async def get_database_info():
    """Получает информацию о подключенной базе данных"""
    try:
        info = db_analyzer.get_database_info()
        return info
    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get database info: {str(e)}")


@app.post("/database/test")
async def test_database_connection(config: DatabaseConfig):
    """Тестирует подключение к указанной базе данных"""
    try:
        database_url = f"postgresql://{config.username}:{config.password}@{config.host}:{config.port}/{config.database}"
        test_analyzer = PostgreSQLAnalyzer(database_url)
        
        is_connected = test_analyzer.test_connection()
        
        if is_connected:
            return {"status": "success", "message": "Database connection successful"}
        else:
            return {"status": "error", "message": "Database connection failed"}
            
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")


@app.get("/examples")
async def get_example_queries():
    """Возвращает примеры SQL запросов для тестирования"""
    return {
        "examples": [
            {
                "name": "Simple SELECT",
                "query": "SELECT * FROM users WHERE email = 'john@example.com'",
                "description": "Простой запрос с фильтрацией"
            },
            {
                "name": "JOIN with aggregation",
                "query": """
                SELECT u.name, COUNT(o.id) as order_count, SUM(o.total_amount) as total_spent
                FROM users u
                LEFT JOIN orders o ON u.id = o.user_id
                WHERE u.is_active = true
                GROUP BY u.id, u.name
                ORDER BY total_spent DESC
                """,
                "description": "Запрос с JOIN и агрегацией"
            },
            {
                "name": "Complex subquery",
                "query": """
                SELECT * FROM users 
                WHERE id IN (
                    SELECT user_id FROM orders 
                    WHERE total_amount > (
                        SELECT AVG(total_amount) FROM orders
                    )
                )
                """,
                "description": "Запрос с подзапросом"
            },
            {
                "name": "Window function",
                "query": """
                SELECT 
                    name,
                    total_amount,
                    ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY total_amount DESC) as rank
                FROM orders o
                JOIN users u ON o.user_id = u.id
                """,
                "description": "Запрос с оконными функциями"
            },
            {
                "name": "Цепочка: Анализ пользователя",
                "query": """
                SELECT * FROM users WHERE email = 'john@example.com';
                SELECT COUNT(*) as order_count FROM orders WHERE user_id = (SELECT id FROM users WHERE email = 'john@example.com');
                SELECT o.total_amount, oi.product_name FROM orders o 
                JOIN order_items oi ON o.id = oi.order_id 
                WHERE o.user_id = (SELECT id FROM users WHERE email = 'john@example.com')
                ORDER BY o.created_at DESC;
                """,
                "description": "Цепочка запросов для анализа конкретного пользователя"
            },
            {
                "name": "Цепочка: Отчет по продажам",
                "query": """
                SELECT DATE(created_at) as date, COUNT(*) as orders_count, SUM(total_amount) as total_revenue 
                FROM orders 
                WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE(created_at) 
                ORDER BY date;
                SELECT u.name, COUNT(o.id) as user_orders, SUM(o.total_amount) as user_spent
                FROM users u
                LEFT JOIN orders o ON u.id = o.user_id
                WHERE o.created_at >= CURRENT_DATE - INTERVAL '7 days' OR o.created_at IS NULL
                GROUP BY u.id, u.name
                HAVING COUNT(o.id) > 0
                ORDER BY user_spent DESC
                LIMIT 10;
                """,
                "description": "Цепочка запросов для создания отчета по продажам за неделю"
            },
            {
                "name": "Цепочка: Оптимизация индексов",
                "query": """
                EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM users WHERE name LIKE '%John%';
                EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM orders WHERE user_id = 1 AND total_amount > 100;
                EXPLAIN (ANALYZE, BUFFERS) SELECT u.name, o.total_amount FROM users u 
                JOIN orders o ON u.id = o.user_id 
                WHERE u.is_active = true AND o.status = 'completed';
                """,
                "description": "Цепочка EXPLAIN запросов для анализа производительности"
            },
            {
                "name": "Цепочка: Анализ производительности",
                "query": """
                SELECT schemaname, tablename, attname, n_distinct, correlation 
                FROM pg_stats 
                WHERE tablename IN ('users', 'orders', 'order_items')
                ORDER BY tablename, attname;
                SELECT indexname, tablename, indexdef 
                FROM pg_indexes 
                WHERE schemaname = 'public' 
                AND tablename IN ('users', 'orders', 'order_items');
                SELECT relname, n_tup_ins, n_tup_upd, n_tup_del, n_live_tup, n_dead_tup
                FROM pg_stat_user_tables 
                WHERE relname IN ('users', 'orders', 'order_items');
                """,
                "description": "Цепочка запросов для анализа статистики таблиц и индексов"
            }
        ]
    }


@app.get("/cache/stats")
async def get_cache_stats():
    """Возвращает статистику кэша LLM"""
    try:
        stats = llm_analyzer.get_cache_stats()
        return {
            "status": "success",
            "cache_stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")


@app.post("/cache/clear")
async def clear_cache():
    """Очищает кэш LLM"""
    try:
        llm_analyzer.clear_cache()
        return {
            "status": "success",
            "message": "Cache cleared successfully"
        }
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
