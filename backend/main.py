from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
from datetime import datetime

from models import QueryAnalysisRequest, QueryAnalysis, ExecutionPlan, HealthCheck, DatabaseConfig
from database import PostgreSQLAnalyzer
from llm_service import LLMAnalyzer
from log_analyzer import PostgreSQLLogAnalyzer
from config_analyzer import PostgreSQLConfigAnalyzer
from cache_warmup import CacheWarmupService
from example_generator import ExampleGenerator
from table_stats_service import TableStatsService
from config import settings
from security import validate_database_url, sanitize_db_url_for_logging, is_safe_query
from database_profiles import profile_manager, DatabaseProfile

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
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация сервисов
db_analyzer = PostgreSQLAnalyzer()
llm_analyzer = LLMAnalyzer()
log_analyzer = PostgreSQLLogAnalyzer()
config_analyzer = PostgreSQLConfigAnalyzer()
cache_warmup = CacheWarmupService()
example_generator = ExampleGenerator()
table_stats_service = TableStatsService()

# Глобальная переменная для хранения статистики таблиц
table_statistics = {}


async def create_default_database_profile():
    """Создаёт профиль базы данных по умолчанию на основе настроек приложения"""
    try:
        # Парсим URL основной базы данных
        from urllib.parse import urlparse
        parsed_url = urlparse(settings.database_url)
        
        # Извлекаем компоненты подключения
        host = parsed_url.hostname or "localhost"
        port = parsed_url.port or 5432
        database = parsed_url.path.lstrip('/') or "query_analyzer"
        username = parsed_url.username or "analyzer_user"
        password = parsed_url.password or "analyzer_pass"
        
        # Проверяем, есть ли уже профиль по умолчанию
        existing_profiles = profile_manager.list_profiles()
        default_profile_exists = any(
            profile.name == "Default Database" and 
            profile.host == host and 
            profile.port == port and 
            profile.database == database and 
            profile.username == username
            for profile in existing_profiles
        )
        
        if not default_profile_exists:
            # Создаём профиль по умолчанию
            success, result = await profile_manager.create_profile(
                name="Default Database",
                host=host,
                port=port,
                database=database,
                username=username,
                password=password
            )
            
            if success:
                logger.info(f"Created default database profile: {result}")
            else:
                logger.warning(f"Failed to create default database profile: {result}")
        else:
            logger.info("Default database profile already exists")
            
    except Exception as e:
        logger.error(f"Error creating default database profile: {e}")


@app.on_event("startup")
async def startup_event():
    """Событие запуска приложения - предварительное кэширование"""
    logger.info("Application startup - starting cache warmup...")

    # Проверяем подключения
    try:
        db_connected = await db_analyzer.test_connection()
        openai_available = await llm_analyzer.test_connection()

        if db_connected and openai_available:
            # Создаём профиль по умолчанию для основной базы данных
            await create_default_database_profile()
            
            # Запускаем кэширование и генерацию примеров в фоне
            asyncio.create_task(startup_cache_warmup())
            asyncio.create_task(startup_example_generation())
            asyncio.create_task(startup_table_statistics())
        else:
            logger.warning("Skipping startup tasks - database or OpenAI not available")

    except Exception as e:
        logger.error(f"Startup cache warmup failed: {e}")


async def startup_cache_warmup():
    """Асинхронная функция для кэширования при запуске"""
    try:
        # Ждем немного, чтобы приложение полностью запустилось
        await asyncio.sleep(2)

        logger.info("Starting background cache warmup...")
        result = await cache_warmup.warmup_cache(max_queries=20)  # Кэшируем все примеры при запуске

        logger.info(f"Background cache warmup completed: {result['processed']} queries cached")

    except Exception as e:
        logger.error(f"Background cache warmup failed: {e}")


async def startup_example_generation():
    """Асинхронная функция для генерации примеров с помощью LLM при запуске"""
    try:
        # Ждем немного, чтобы приложение полностью запустилось
        await asyncio.sleep(3)

        logger.info("Starting LLM-based example generation from database structure...")

        # Генерируем примеры с помощью LLM на основе структуры БД
        all_examples = await example_generator.merge_and_save_examples()

        if all_examples:
            logger.info(f"LLM generated examples completed: {len(all_examples)} total examples")

            # После генерации примеров запускаем дополнительный прогрев кэша для новых примеров
            logger.info("Starting additional cache warmup for newly generated examples...")
            try:
                # Кэшируем только новые примеры (пропускаем уже закэшированные)
                additional_result = await cache_warmup.warmup_new_examples(max_queries=5)
                logger.info(f"Additional cache warmup completed: {additional_result['processed']} new queries cached")
            except Exception as e:
                logger.error(f"Additional cache warmup failed: {e}")
        else:
            logger.warning("No examples generated by LLM")

    except Exception as e:
        logger.error(f"LLM example generation failed: {e}")


async def startup_table_statistics():
    """Асинхронная функция для загрузки статистики таблиц при запуске"""
    try:
        # Ждем немного, чтобы приложение полностью запустилось
        await asyncio.sleep(1)

        logger.info("Loading table statistics...")
        global table_statistics
        table_statistics = await db_analyzer.get_table_statistics()

        if table_statistics['tables']:
            total_tables = table_statistics['total_tables']
            total_tuples = table_statistics['total_live_tuples']
            total_size = table_statistics['total_size_bytes']

            logger.info(
                f"Table statistics loaded: {total_tables} tables, "
                f"{total_tuples:,} total rows, "
                f"{total_size / (1024*1024):.1f} MB total size"
            )
        else:
            logger.warning("No table statistics loaded")

    except Exception as e:
        logger.error(f"Failed to load table statistics: {e}")
        table_statistics = {}


@app.get("/", response_model=dict)
async def root():
    """Корневой эндпоинт"""
    return {"message": "PostgreSQL Query Analyzer API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Проверка здоровья сервиса"""
    try:
        db_connected = await db_analyzer.test_connection()
        openai_available = await llm_analyzer.test_connection()

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


@app.get("/models")
async def get_available_models():
    """Получить список доступных LLM моделей"""
    try:
        models = settings.get_available_models()
        return {
            "models": [
                {
                    "name": model.name,
                    "model": model.model,
                    "url": model.url,
                    "is_current": model.name == llm_analyzer.selected_model.name
                }
                for model in models
            ],
            "current_model": llm_analyzer.selected_model.name
        }
    except Exception as e:
        logger.error(f"Failed to get models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/models/switch")
async def switch_model(model_name: str):
    """Переключить на другую LLM модель"""
    try:
        model = settings.get_model_by_name(model_name)
        if not model:
            raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")

        llm_analyzer.switch_model(model)
        logger.info(f"Switched to model: {model.name}")

        return {
            "message": f"Successfully switched to {model.name}",
            "current_model": model.name,
            "model_info": {
                "name": model.name,
                "model": model.model,
                "url": model.url
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to switch model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

        # Проверка безопасности SQL запроса
        query_safe, query_warning = is_safe_query(request.query)
        if not query_safe:
            raise HTTPException(
                status_code=400, detail=f"Security check failed: {query_warning}"
            )

        # Используем переданный URL БД или дефолтный
        analyzer = db_analyzer
        if request.database_url:
            # Валидация пользовательского URL БД
            url_valid, url_error = validate_database_url(request.database_url)
            if not url_valid:
                raise HTTPException(
                    status_code=400, detail=f"Invalid database URL: {url_error}"
                )

            # Безопасное логирование
            safe_url = sanitize_db_url_for_logging(request.database_url)
            logger.info(f"Using custom database: {safe_url}")
            analyzer = PostgreSQLAnalyzer(request.database_url)
        elif hasattr(request, 'database_profile_id') and request.database_profile_id:
            # Использование профиля базы данных
            connection = profile_manager.get_connection(request.database_profile_id)
            if not connection:
                raise HTTPException(
                    status_code=400, 
                    detail="Database profile not found or connection expired"
                )
            
            profile_manager.update_last_used(request.database_profile_id)
            analyzer = PostgreSQLAnalyzer(connection.get_connection_url())

        # Проверяем, является ли запрос цепочкой (содержит точку с запятой)
        queries = [q.strip() for q in request.query.split(";") if q.strip()]

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
        plan_data = await analyzer.analyze_query_performance(main_query)

        # Создаем объект плана выполнения
        execution_plan = ExecutionPlan(
            total_cost=plan_data["total_cost"],
            execution_time=plan_data["execution_time"],
            rows=plan_data["rows"],
            width=plan_data["width"],
            plan_json=plan_data["plan_json"],
        )

        # Анализируем с помощью LLM (передаем всю цепочку для контекста)
        logger.info("Running LLM analysis...")
        global table_statistics
        llm_result = await llm_analyzer.analyze_query_with_llm(
            all_queries_text, plan_data["plan_json"], table_statistics
        )

        # Создаем результат анализа
        analysis = QueryAnalysis(
            query=request.query,
            rewritten_query=llm_result.get("rewritten_query"),
            execution_plan=execution_plan,
            resource_metrics=llm_result["resource_metrics"],
            recommendations=llm_result["recommendations"],
            warnings=llm_result["warnings"],
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
        info = await db_analyzer.get_database_info()
        return info
    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get database info: {str(e)}")


@app.post("/database/test")
async def test_database_connection(config: DatabaseConfig):
    """Тестирует подключение к указанной базе данных"""
    try:
        database_url = (
            f"postgresql://{config.username}:{config.password}@"
            f"{config.host}:{config.port}/{config.database}"
        )

        # Валидация URL перед подключением
        url_valid, url_error = validate_database_url(database_url)
        if not url_valid:
            return {
                "status": "error",
                "message": f"Invalid connection parameters: {url_error}"
            }

        # Безопасное логирование
        safe_url = sanitize_db_url_for_logging(database_url)
        logger.info(f"Testing database connection: {safe_url}")
        test_analyzer = PostgreSQLAnalyzer(database_url)
        is_connected = await test_analyzer.test_connection()

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
    try:
        # Загружаем примеры из test_queries.json
        test_queries = await cache_warmup.load_test_queries()

        # Если примеров мало, пытаемся сгенерировать дополнительные с помощью LLM
        if len(test_queries) < 15:
            try:
                # Генерируем примеры с помощью LLM на основе структуры БД
                new_examples = await example_generator.generate_examples_with_llm()
                # Добавляем только уникальные примеры
                existing_queries = {q["query"] for q in test_queries}
                for new_example in new_examples:
                    if new_example["query"] not in existing_queries:
                        test_queries.append(new_example)
                        existing_queries.add(new_example["query"])
            except Exception as e:
                logger.warning(f"Failed to generate additional examples with LLM: {e}")

        # Добавляем дополнительные примеры цепочек запросов
        chain_examples = [
            {
                "name": "Цепочка: Анализ пользователя",
                "query": """
                SELECT * FROM users WHERE email = 'john@example.com';
                SELECT COUNT(*) as order_count FROM orders
                WHERE user_id = (SELECT id FROM users WHERE email = 'john@example.com');
                SELECT o.total_amount, oi.product_name FROM orders o
                JOIN order_items oi ON o.id = oi.order_id
                WHERE o.user_id = (SELECT id FROM users WHERE email = 'john@example.com')
                ORDER BY o.created_at DESC;
                """,
                "description": "Цепочка запросов для анализа конкретного пользователя",
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
                "description": "Цепочка запросов для создания отчета по продажам за неделю",
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
                "description": "Цепочка EXPLAIN запросов для анализа производительности",
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
                "description": "Цепочка запросов для анализа статистики таблиц и индексов",
            },
        ]

        # Объединяем все примеры
        all_examples = test_queries + chain_examples

        return {"examples": all_examples}

    except Exception as e:
        logger.error(f"Failed to load examples: {e}")
        # Возвращаем базовые примеры в случае ошибки
        return {
            "examples": [
                {
                    "name": "Simple SELECT",
                    "query": "SELECT * FROM users WHERE email = 'john@example.com'",
                    "description": "Простой запрос с фильтрацией",
                }
            ]
        }


@app.get("/cache/stats")
async def get_cache_stats():
    """Возвращает статистику кэша LLM"""
    try:
        stats = llm_analyzer.get_cache_stats()
        return {"status": "success", "cache_stats": stats}
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")


@app.post("/cache/clear")
async def clear_cache():
    """Очищает кэш LLM"""
    try:
        llm_analyzer.clear_cache()
        return {"status": "success", "message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@app.get("/logs/analyze")
async def analyze_logs(hours_back: int = 24):
    """Анализирует логи PostgreSQL"""
    try:
        analysis = await log_analyzer.analyze_logs(hours_back)
        return {"status": "success", "analysis": analysis}
    except Exception as e:
        logger.error(f"Failed to analyze logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze logs: {str(e)}")


@app.get("/config/analyze")
async def analyze_configuration():
    """Анализирует конфигурацию PostgreSQL"""
    try:
        analysis = await config_analyzer.get_configuration_analysis()
        return {"status": "success", "analysis": analysis}
    except Exception as e:
        logger.error(f"Failed to analyze configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze configuration: {str(e)}")


@app.get("/health/full")
async def full_health_check():
    """Полная проверка здоровья системы включая логи и конфигурацию"""
    try:
        # Базовая проверка здоровья
        db_connected = await db_analyzer.test_connection()
        openai_available = await llm_analyzer.test_connection()

        # Анализ конфигурации
        config_analysis = await config_analyzer.get_configuration_analysis()

        # Анализ логов за последний час
        log_analysis = await log_analyzer.analyze_logs(1)

        # Определяем общий статус
        overall_status = "healthy"
        if not db_connected or not openai_available:
            overall_status = "unhealthy"
        elif config_analysis["analysis"]["overall_health"] != "good":
            overall_status = "degraded"
        elif log_analysis["summary"]["total_errors"] > 10:
            overall_status = "degraded"

        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "database_connected": db_connected,
            "openai_available": openai_available,
            "configuration_health": config_analysis["analysis"]["overall_health"],
            "recent_errors": log_analysis["summary"]["total_errors"],
            "configuration_issues": config_analysis["analysis"]["total_issues"],
            "recommendations": {
                "config": config_analysis["recommendations"][:3],  # Топ-3 рекомендации
                "logs": log_analysis["summary"]["recommendations"][:3],
            },
        }
    except Exception as e:
        logger.error(f"Full health check failed: {e}")
        return {"status": "unhealthy", "timestamp": datetime.now().isoformat(), "error": str(e)}


@app.get("/tables/statistics")
async def get_table_statistics():
    """Возвращает статистику таблиц базы данных"""
    try:
        global table_statistics
        if not table_statistics:
            # Если статистика не загружена, загружаем её
            table_statistics = await db_analyzer.get_table_statistics()

        return {
            "status": "success",
            "statistics": table_statistics,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get table statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get table statistics: {str(e)}")


@app.post("/cache/warmup")
async def warmup_cache(max_queries: int = 5):
    """Предварительно кэширует тестовые запросы"""
    try:
        result = await cache_warmup.warmup_cache(max_queries)
        return {"status": "success", "warmup_result": result}
    except Exception as e:
        logger.error(f"Cache warmup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cache warmup failed: {str(e)}")


@app.post("/cache/test")
async def test_cache_hit(request: QueryAnalysisRequest):
    """Тестирует попадание в кэш для конкретного запроса"""
    try:
        result = await cache_warmup.test_cache_hit(request.query)
        return {"status": "success", "test_result": result}
    except Exception as e:
        logger.error(f"Cache test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cache test failed: {str(e)}")


# === DATABASE PROFILES API ===

@app.post("/database/profiles")
async def create_database_profile(
    name: str,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str
):
    """Create a new database profile"""
    try:
        success, result = await profile_manager.create_profile(
            name=name, host=host, port=port, 
            database=database, username=username, password=password
        )
        
        if success:
            profile = profile_manager.get_profile(result)
            return {
                "status": "success",
                "profile_id": result,
                "profile": profile.dict() if profile else None,
                "message": "Database profile created successfully"
            }
        else:
            return {"status": "error", "message": result}
            
    except Exception as e:
        logger.error(f"Failed to create database profile: {e}")
        raise HTTPException(status_code=500, detail=f"Profile creation failed: {str(e)}")


@app.get("/database/profiles")
async def list_database_profiles():
    """List all database profiles"""
    try:
        profiles = profile_manager.list_profiles()
        return {
            "status": "success",
            "profiles": [profile.dict() for profile in profiles],
            "count": len(profiles)
        }
    except Exception as e:
        logger.error(f"Failed to list profiles: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list profiles: {str(e)}")


@app.post("/database/profiles/{profile_id}/connect")
async def connect_to_profile(profile_id: str, password: str):
    """Connect to a database profile"""
    try:
        success, message = await profile_manager.refresh_connection(profile_id, password)
        
        if success:
            return {"status": "success", "message": message}
        else:
            return {"status": "error", "message": message}
            
    except Exception as e:
        logger.error(f"Failed to connect to profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")


@app.delete("/database/profiles/{profile_id}")
async def delete_database_profile(profile_id: str):
    """Delete a database profile"""
    try:
        success = profile_manager.delete_profile(profile_id)
        
        if success:
            return {"status": "success", "message": "Profile deleted successfully"}
        else:
            return {"status": "error", "message": "Profile not found"}
            
    except Exception as e:
        logger.error(f"Failed to delete profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@app.get("/database/profiles/{profile_id}/info")
async def get_profile_database_info(profile_id: str):
    """Get database info for a specific profile"""
    try:
        connection = profile_manager.get_connection(profile_id)
        if not connection:
            raise HTTPException(status_code=404, detail="Profile not found or not connected")
        
        analyzer = PostgreSQLAnalyzer(connection.get_connection_url())
        info = await analyzer.get_database_info()
        
        profile_manager.update_last_used(profile_id)
        
        return {
            "status": "success",
            "profile_id": profile_id,
            "database_info": info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get database info for profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get database info: {str(e)}")


@app.post("/database/profiles/default")
async def create_or_refresh_default_profile():
    """Create or refresh the default database profile"""
    try:
        await create_default_database_profile()
        
        # Найдём созданный профиль по умолчанию
        profiles = profile_manager.list_profiles()
        default_profile = next(
            (p for p in profiles if p.name == "Default Database"), 
            None
        )
        
        if default_profile:
            return {
                "status": "success",
                "message": "Default database profile created/refreshed successfully",
                "profile": default_profile.dict()
            }
        else:
            return {
                "status": "error",
                "message": "Failed to create default database profile"
            }
            
    except Exception as e:
        logger.error(f"Failed to create/refresh default profile: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create default profile: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
