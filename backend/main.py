"""
PostgreSQL Query Analyzer Backend
Создано командой БОРЖОРА для MoreTech 2025

Основной модуль FastAPI приложения для анализа SQL-запросов PostgreSQL
с использованием LLM и structured output.
"""

import asyncio
import inspect
import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from cache_warmup import CacheWarmupService
from config import settings
from config_analyzer import PostgreSQLConfigAnalyzer
from database import PostgreSQLAnalyzer

# Security module removed - allowing all database connections
from database_profiles import profile_manager
from example_generator import ExampleGenerator
from execution_plan_cache import ExecutionPlanCache
from llm_service import LLMAnalyzer
from log_analyzer import PostgreSQLLogAnalyzer
from models import (
    DatabaseConfig,
    ExecutionPlan,
    ExecutionPlanResponse,
    HealthCheck,
    QueryAnalysis,
    QueryAnalysisRequest,
)
from services.query_analysis import (
    QueryAnalysisError,
    build_execution_plan_model,
    determine_llm_query,
    extract_main_query,
    fetch_execution_plan,
    refined_rewritten_query,
    resolve_analyzer,
    validate_query_text,
)
from table_stats_service import TableStatsService

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание FastAPI приложения
app = FastAPI(
    title=settings.app_name, description="Умный инструмент для анализа SQL-запросов PostgreSQL", version="1.0.0"
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
execution_plan_cache = ExecutionPlanCache()

# Глобальные переменные для хранения данных
table_statistics = {}
rewritten_examples_cache = []


async def run_with_timeout(description: str, awaitable, timeout: float = 5.0) -> bool:
    """Run an awaitable with a timeout, gracefully handling sync results."""
    try:
        if not inspect.isawaitable(awaitable):
            return bool(awaitable)

        return await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("%s timed out after %.1fs", description, timeout)
        return False


async def create_default_database_profiles():
    """Создаёт профили баз данных по умолчанию"""
    try:
        # Парсим URL основной базы данных
        from urllib.parse import urlparse

        parsed_url = urlparse(settings.database_url)

        # Извлекаем компоненты подключения для localhost
        host = parsed_url.hostname or "localhost"
        port = parsed_url.port or 5432
        database = parsed_url.path.lstrip("/") or "query_analyzer"
        username = parsed_url.username or "analyzer_user"
        password = parsed_url.password or "analyzer_pass"

        # Проверяем существующие профили
        existing_profiles = profile_manager.list_profiles()

        # 1. Создаём профиль по умолчанию (localhost)
        default_profile_exists = any(
            profile.name == "Default Database"
            and profile.host == host
            and profile.port == port
            and profile.database == database
            and profile.username == username
            for profile in existing_profiles
        )

        if not default_profile_exists:
            success, result = await profile_manager.create_profile(
                name="Default Database", host=host, port=port, database=database, username=username, password=password
            )

            if success:
                logger.info(f"Created default database profile: {result}")
            else:
                logger.warning(f"Failed to create default database profile: {result}")
        else:
            logger.info("Default database profile already exists")

        # 2. Создаём профиль RNA Central
        rna_central_exists = any(
            profile.name == "RNA Central Database" and profile.host == "hh-pgsql-public.ebi.ac.uk"
            for profile in existing_profiles
        )

        if not rna_central_exists:
            try:
                success, result = await profile_manager.create_profile(
                    name="RNA Central Database",
                    host="hh-pgsql-public.ebi.ac.uk",
                    port=5432,
                    database="pfmegrnargs",
                    username="reader",
                    password="NWDMCE5xdipIjRrp",
                )

                if success:
                    logger.info(f"Created RNA Central database profile: {result}")
                    # Test query chains specifically for this database
                    try:
                        connection = profile_manager.get_connection(result)
                        if connection:
                            PostgreSQLAnalyzer(connection.get_connection_url())
                            # Test a simple query chain to ensure it works
                            test_chain = "SELECT 1 as test; SELECT 2 as test2;"
                            main_query, all_text = extract_main_query(test_chain)
                            logger.info(
                                f"RNA Central DB query chain test - Main: '{main_query[:50]}...', Full: '{all_text[:100]}...'"
                            )
                            if ";" in all_text:
                                logger.info("Query chains are properly detected for RNA Central database")
                            else:
                                logger.warning("Query chains may not be working properly for RNA Central database")
                    except Exception as chain_test_error:
                        logger.warning(f"Could not test query chains for RNA Central database: {chain_test_error}")
                else:
                    logger.warning(f"Failed to create RNA Central database profile: {result}")
            except Exception as rna_error:
                logger.error(f"Error creating RNA Central database profile: {rna_error}")
        else:
            logger.info("RNA Central database profile already exists")
            # Still test query chains for existing profile
            try:
                rna_profile = next(profile for profile in existing_profiles if profile.name == "RNA Central Database")
                connection = profile_manager.get_connection(rna_profile.id)
                if connection:
                    test_chain = "SELECT 1 as test; SELECT 2 as test2;"
                    main_query, all_text = extract_main_query(test_chain)
                    if ";" in all_text:
                        logger.info("Query chains are working correctly for existing RNA Central database profile")
                    else:
                        logger.warning("Query chains may have issues with existing RNA Central database profile")
            except Exception as existing_test_error:
                logger.warning(f"Could not test existing RNA Central profile: {existing_test_error}")

    except Exception as e:
        logger.error(f"Error creating default database profiles: {e}")


async def startup_load_cache():
    """Загружает кэши для всех доступных моделей из файлов при запуске"""
    try:
        logger.info("Loading caches for all models from files...")

        # Загружаем кэши для всех моделей
        cache_stats = await cache_warmup.load_all_caches_into_analyzers()

        total_loaded = sum(count for count in cache_stats.values() if count > 0)
        failed_models = [model for model, count in cache_stats.items() if count == -1]

        logger.info(f"Cache loading completed: {total_loaded} total entries loaded")
        for model_name, count in cache_stats.items():
            if count > 0:
                logger.info(f"  - {model_name}: {count} entries")
            elif count == 0:
                logger.info(f"  - {model_name}: no cache found")
            else:
                logger.warning(f"  - {model_name}: failed to load")

        if failed_models:
            logger.warning(f"Failed to load cache for models: {', '.join(failed_models)}")

        # Также загружаем кэш в основной анализатор для совместимости
        main_model = llm_analyzer.selected_model
        if main_model.name in cache_stats and cache_stats[main_model.name] > 0:
            file_cache = await cache_warmup.load_cache_from_file(main_model.model)
            if file_cache:
                await llm_analyzer.load_cache_from_file(file_cache)
                logger.info(f"Main analyzer cache updated with {len(file_cache)} entries")

    except Exception as e:
        logger.error(f"Failed to load caches: {e}")


async def startup_load_execution_plan_cache():
    """Загружает кэш планов выполнения из файла при запуске"""
    try:
        logger.info("Loading execution plan cache from file...")

        # Загружаем кэш планов выполнения из файла
        execution_plan_cache.load_cache_from_file()
        logger.info(f"Loaded execution plan cache with {len(execution_plan_cache._cache)} entries")

    except Exception as e:
        logger.error(f"Failed to load execution plan cache: {e}")


async def startup_load_rewritten_examples():
    """Загружает переписанные примеры при запуске"""
    try:
        logger.info("Loading rewritten examples at startup...")
        rewritten_examples = await cache_warmup.load_rewritten_examples()

        if rewritten_examples:
            logger.info(f"Loaded {len(rewritten_examples)} rewritten examples from cache")
            # Можно добавить глобальную переменную для хранения переписанных примеров
            global rewritten_examples_cache
            rewritten_examples_cache = rewritten_examples
        else:
            logger.info("No rewritten examples found in cache")
            rewritten_examples_cache = []

    except Exception as e:
        logger.error(f"Failed to load rewritten examples: {e}")
        rewritten_examples_cache = []


async def startup_precompute_execution_plans():
    """Предварительно вычисляет планы выполнения для тестовых запросов"""
    try:
        logger.info("Pre-computing execution plans for test queries...")

        # Загружаем тестовые запросы
        test_queries = await cache_warmup.load_test_queries()
        if not test_queries:
            logger.warning("No test queries found for execution plan pre-computation")
            return

        # Предварительно вычисляем планы выполнения для всех профилей баз данных
        result = await execution_plan_cache.precompute_for_all_database_profiles(
            profile_manager, test_queries, max_queries_per_db=5
        )

        logger.info(
            f"Execution plan pre-computation completed: {result['total_processed']} total processed, {result['total_errors']} total errors across {result['total_profiles']} database profiles"
        )

    except Exception as e:
        logger.error(f"Failed to pre-compute execution plans: {e}")


@app.on_event("startup")
async def startup_event():
    """Событие запуска приложения - предварительное кэширование"""
    logger.info("Application startup - starting cache warmup...")

    # Проверяем подключения
    try:
        db_connected = await run_with_timeout("Database connection test", db_analyzer.test_connection())
        openai_available = await run_with_timeout("LLM connection test", llm_analyzer.test_connection())

        # Создаём профили по умолчанию для баз данных (всегда, если база данных доступна)
        if db_connected:
            await create_default_database_profiles()
        else:
            logger.warning("Database not available - skipping profile creation")

        if db_connected and openai_available:
            # Загружаем кэш для основной модели из файла
            await startup_load_cache()

            # Загружаем кэш планов выполнения
            await startup_load_execution_plan_cache()

            # Загружаем переписанные примеры
            await startup_load_rewritten_examples()

            # Предварительно вычисляем планы выполнения
            await startup_precompute_execution_plans()

            # Запускаем кэширование и генерацию примеров в фоне
            asyncio.create_task(startup_cache_warmup())
            asyncio.create_task(startup_example_generation())
            asyncio.create_task(startup_table_statistics())
        else:
            logger.warning("Skipping LLM-related startup tasks - database or OpenAI not available")

    except Exception as e:
        logger.error(f"Startup cache warmup failed: {e}")


async def startup_cache_warmup():
    """Асинхронная функция для кэширования при запуске"""
    try:
        # Ждем 15 секунд, чтобы приложение полностью запустилось и стабилизировалось
        logger.info("Waiting 15 seconds before starting cache warmup...")
        await asyncio.sleep(15)

        logger.info("Starting background cache warmup for all models with Semaphore(3)...")
        result = await cache_warmup.warmup_cache_for_all_models(
            max_queries=20, max_concurrent=3
        )  # Кэшируем все примеры для всех моделей при запуске с семафором

        logger.info(
            f"Background cache warmup completed: {result['total_processed']} queries cached across {len(result['models'])} models"
        )

    except Exception as e:
        logger.error(f"Background cache warmup failed: {e}")


async def startup_example_generation():
    """Асинхронная функция для работы с примерами при запуске"""
    try:
        # Ждем немного, чтобы приложение полностью запустилось
        await asyncio.sleep(5)

        # Проверяем, есть ли уже загруженные примеры из test_queries.json
        test_queries = await cache_warmup.load_test_queries()
        if test_queries and len(test_queries) >= 10:
            logger.info(f"Using existing examples from test_queries.json: {len(test_queries)} examples available")
            logger.info("Skipping LLM-based example generation - using existing warmup file")
        else:
            logger.info("Few examples available, starting LLM-based example generation from database structure...")

            # Генерируем примеры с помощью LLM на основе структуры БД только если их мало
            all_examples = await example_generator.merge_and_save_examples()

            if all_examples:
                logger.info(f"LLM generated examples completed: {len(all_examples)} total examples")

                # После генерации примеров запускаем дополнительный прогрев кэша для новых примеров
                logger.info("Starting additional cache warmup for newly generated examples...")
                try:
                    # Кэшируем только новые примеры (пропускаем уже закэшированные)
                    additional_result = await cache_warmup.warmup_new_examples(max_queries=5)
                    logger.info(
                        f"Additional cache warmup completed: {additional_result['processed']} new queries cached"
                    )
                except Exception as e:
                    logger.error(f"Additional cache warmup failed: {e}")
            else:
                logger.warning("No examples generated by LLM")

    except Exception as e:
        logger.error(f"Example generation/loading failed: {e}")


async def startup_table_statistics():
    """Асинхронная функция для загрузки статистики таблиц при запуске"""
    try:
        # Ждем немного, чтобы приложение полностью запустилось
        await asyncio.sleep(10)

        logger.info("Loading table statistics...")
        global table_statistics
        table_statistics = await db_analyzer.get_table_statistics()

        if table_statistics["tables"]:
            total_tables = table_statistics["total_tables"]
            total_tuples = table_statistics["total_live_tuples"]
            total_size = table_statistics["total_size_bytes"]

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
        db_connected = await run_with_timeout("Database connection test", db_analyzer.test_connection())
        openai_available = await run_with_timeout("LLM connection test", llm_analyzer.test_connection())

        status = "healthy" if db_connected and openai_available else "unhealthy"

        return HealthCheck(
            status=status, timestamp=datetime.now(), database_connected=db_connected, openai_available=openai_available
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheck(
            status="unhealthy", timestamp=datetime.now(), database_connected=False, openai_available=False
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
                    "is_current": model.name == llm_analyzer.selected_model.name,
                }
                for model in models
            ],
            "current_model": llm_analyzer.selected_model.name,
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
            "model_info": {"name": model.name, "model": model.model, "url": model.url},
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
        validate_query_text(request.query, max_length=settings.max_query_length)

        resolution = resolve_analyzer(
            database_url=request.database_url,
            database_profile_id=getattr(request, "database_profile_id", None),
            default_analyzer=db_analyzer,
            profile_manager=profile_manager,
        )

        main_query, all_queries_text = extract_main_query(request.query)
        plan_data, _ = await fetch_execution_plan(
            analyzer=resolution.analyzer,
            main_query=main_query,
            plan_cache=execution_plan_cache,
        )

        execution_plan_payload = build_execution_plan_model(plan_data)
        execution_plan = ExecutionPlan(**execution_plan_payload)

        logger.info("Running LLM analysis...")
        global table_statistics
        query_for_llm = determine_llm_query(plan_data["plan_json"], all_queries_text)
        llm_result = await llm_analyzer.analyze_query_with_llm(query_for_llm, plan_data["plan_json"], table_statistics)

        rewritten_query = refined_rewritten_query(
            request_query=request.query,
            warnings=llm_result.get("warnings"),
            rewritten_query=llm_result.get("rewritten_query"),
        )

        analysis = QueryAnalysis(
            query=request.query,
            rewritten_query=rewritten_query,
            execution_plan=execution_plan,
            resource_metrics=llm_result["resource_metrics"],
            recommendations=llm_result["recommendations"],
            warnings=llm_result.get("warnings", []),
        )

        logger.info("Analysis completed. Found %s recommendations", len(analysis.recommendations))
        return analysis

    except QueryAnalysisError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/analyze/execution-plan", response_model=ExecutionPlanResponse)
async def analyze_execution_plan(request: QueryAnalysisRequest):
    """
    Возвращает только план выполнения запроса (быстрый ответ)
    """
    try:
        validate_query_text(request.query, max_length=settings.max_query_length)

        resolution = resolve_analyzer(
            database_url=request.database_url,
            database_profile_id=getattr(request, "database_profile_id", None),
            default_analyzer=db_analyzer,
            profile_manager=profile_manager,
        )

        main_query, _ = extract_main_query(request.query)
        plan_data, _ = await fetch_execution_plan(
            analyzer=resolution.analyzer,
            main_query=main_query,
            plan_cache=execution_plan_cache,
        )

        execution_plan_payload = build_execution_plan_model(plan_data)
        execution_plan = ExecutionPlan(**execution_plan_payload)

        return ExecutionPlanResponse(
            query=request.query,
            execution_plan=execution_plan,
            status="execution_plan_ready",
            analysis_timestamp=datetime.now(),
            has_errors=plan_data.get("has_errors", False),
            postgresql_errors=plan_data.get("postgresql_errors", []),
            error_analysis=plan_data.get("error_analysis"),
        )

    except QueryAnalysisError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Execution plan analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Execution plan analysis failed: {str(e)}")


@app.post("/analyze/llm")
async def analyze_with_llm(request: QueryAnalysisRequest):
    """
    Возвращает только LLM анализ запроса (использует кэшированный план выполнения)
    """
    try:
        validate_query_text(request.query, max_length=settings.max_query_length)

        resolution = resolve_analyzer(
            database_url=request.database_url,
            database_profile_id=getattr(request, "database_profile_id", None),
            default_analyzer=db_analyzer,
            profile_manager=profile_manager,
        )

        main_query, all_queries_text = extract_main_query(request.query)
        plan_data, _ = await fetch_execution_plan(
            analyzer=resolution.analyzer,
            main_query=main_query,
            plan_cache=execution_plan_cache,
        )

        logger.info("Running LLM analysis...")
        global table_statistics
        query_for_llm = determine_llm_query(plan_data["plan_json"], all_queries_text)
        llm_result = await llm_analyzer.analyze_query_with_llm(query_for_llm, plan_data["plan_json"], table_statistics)

        rewritten_query = refined_rewritten_query(
            request_query=request.query,
            warnings=llm_result.get("warnings"),
            rewritten_query=llm_result.get("rewritten_query"),
        )

        return {
            "query": request.query,
            "rewritten_query": rewritten_query,
            "resource_metrics": llm_result["resource_metrics"],
            "recommendations": llm_result["recommendations"],
            "warnings": llm_result.get("warnings", []),
            "status": "llm_analysis_ready",
        }

    except QueryAnalysisError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"LLM analysis failed: {str(e)}")


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
            f"postgresql://{config.username}:{config.password}@" f"{config.host}:{config.port}/{config.database}"
        )

        # Database URL validation removed - allowing all connections
        safe_url = database_url.replace("://", "://***:***@") if "://" in database_url else database_url
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
async def get_example_queries(database_profile_id: str = None):
    """Возвращает примеры SQL запросов для тестирования"""
    try:
        # Определяем какую базу данных использовать для генерации примеров
        analyzer = db_analyzer  # По умолчанию используем основную БД

        if database_profile_id:
            # Используем выбранный профиль базы данных
            connection = profile_manager.get_connection(database_profile_id)
            if connection:
                analyzer = PostgreSQLAnalyzer(connection.get_connection_url())
                logger.info(f"Using database profile {database_profile_id} for examples")
            else:
                # Попробуем восстановить соединение для существующего профиля
                profile = profile_manager.get_profile(database_profile_id)
                if profile:
                    logger.info(f"Reconnecting to database profile {database_profile_id}")
                    # Восстанавливаем соединение с паролем по умолчанию
                    if profile.name == "Default Database":
                        success, result = await profile_manager.refresh_connection(database_profile_id, "analyzer_pass")
                    elif profile.name == "RNA Central Database":
                        success, result = await profile_manager.refresh_connection(
                            database_profile_id, "NWDMCE5xdipIjRrp"
                        )
                    else:
                        success = False

                    if success:
                        connection = profile_manager.get_connection(database_profile_id)
                        if connection:
                            analyzer = PostgreSQLAnalyzer(connection.get_connection_url())
                            logger.info(f"Reconnected to database profile {database_profile_id}")
                        else:
                            logger.warning(
                                f"Failed to reconnect to database profile {database_profile_id}, using default"
                            )
                    else:
                        logger.warning(
                            f"Failed to refresh connection for database profile {database_profile_id}, using default"
                        )
                else:
                    logger.warning(f"Database profile {database_profile_id} not found, using default")

        # Загружаем примеры из test_queries.json
        test_queries = await cache_warmup.load_test_queries()

        # Если указан конкретный профиль БД, проверяем нужна ли адаптация
        if database_profile_id:
            # Получаем профиль для проверки
            profile = profile_manager.get_profile(database_profile_id)
            if profile and profile.name == "Default Database":
                # Для Default Database используем стандартные примеры без LLM адаптации
                logger.info(f"Using standard examples for Default Database profile {database_profile_id}")
            else:
                # Для внешних БД (например, RNA Central) адаптируем примеры под их схему
                try:
                    adapted_examples = await example_generator.generate_examples_with_llm_for_database(
                        analyzer, database_profile_id
                    )
                    if adapted_examples:
                        # Заменяем стандартные примеры на адаптированные
                        test_queries = adapted_examples
                        logger.info(
                            f"Adapted {len(adapted_examples)} examples for external database profile {database_profile_id}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to adapt examples for database profile: {e}")
                    # В случае ошибки используем стандартные примеры
        else:
            # Для основной БД используем стандартные примеры
            # Если примеров мало, пытаемся сгенерировать дополнительные с помощью LLM
            if len(test_queries) < 15:
                try:
                    # Генерируем примеры с помощью LLM на основе структуры основной БД
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


@app.get("/cache/execution-plans/stats")
async def get_execution_plan_cache_stats():
    """Возвращает статистику кэша планов выполнения"""
    try:
        stats = execution_plan_cache.get_cache_stats()
        return {"status": "success", "execution_plan_cache_stats": stats}
    except Exception as e:
        logger.error(f"Failed to get execution plan cache stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get execution plan cache stats: {str(e)}")


@app.post("/cache/clear")
async def clear_cache():
    """Очищает кэш LLM"""
    try:
        llm_analyzer.clear_cache()
        return {"status": "success", "message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@app.post("/cache/execution-plans/clear")
async def clear_execution_plan_cache():
    """Очищает кэш планов выполнения"""
    try:
        execution_plan_cache.clear_cache()
        return {"status": "success", "message": "Execution plan cache cleared"}
    except Exception as e:
        logger.error(f"Failed to clear execution plan cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear execution plan cache: {str(e)}")


@app.post("/cache/execution-plans/precompute")
async def precompute_execution_plans(max_queries: int = 10):
    """Предварительно вычисляет планы выполнения для тестовых запросов"""
    try:
        # Загружаем тестовые запросы
        test_queries = await cache_warmup.load_test_queries()
        if not test_queries:
            return {"status": "no_queries", "message": "No test queries found"}

        # Предварительно вычисляем планы выполнения
        result = await execution_plan_cache.precompute_execution_plans(db_analyzer, test_queries, max_queries)

        return {"status": "success", "precompute_result": result}
    except Exception as e:
        logger.error(f"Execution plan pre-computation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Execution plan pre-computation failed: {str(e)}")


@app.post("/cache/execution-plans/precompute-all-databases")
async def precompute_execution_plans_all_databases(max_queries_per_db: int = 5):
    """Предварительно вычисляет планы выполнения для всех профилей баз данных"""
    try:
        # Загружаем тестовые запросы
        test_queries = await cache_warmup.load_test_queries()
        if not test_queries:
            return {"status": "no_queries", "message": "No test queries found"}

        # Предварительно вычисляем планы выполнения для всех профилей баз данных
        result = await execution_plan_cache.precompute_for_all_database_profiles(
            profile_manager, test_queries, max_queries_per_db
        )

        return {"status": "success", "precompute_result": result}
    except Exception as e:
        logger.error(f"All databases execution plan pre-computation failed: {e}")
        raise HTTPException(status_code=500, detail=f"All databases execution plan pre-computation failed: {str(e)}")


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

        return {"status": "success", "statistics": table_statistics, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Failed to get table statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get table statistics: {str(e)}")


@app.post("/cache/warmup")
async def warmup_cache(max_queries: int = 5):
    """Предварительно кэширует тестовые запросы для первой модели"""
    try:
        result = await cache_warmup.warmup_cache(max_queries)
        return {"status": "success", "warmup_result": result}
    except Exception as e:
        logger.error(f"Cache warmup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cache warmup failed: {str(e)}")


@app.post("/cache/warmup/all-models")
async def warmup_cache_all_models(max_queries: int = 5):
    """Предварительно кэширует тестовые запросы для всех доступных моделей"""
    try:
        result = await cache_warmup.warmup_cache_for_all_models(max_queries)
        return {"status": "success", "warmup_result": result}
    except Exception as e:
        logger.error(f"All models cache warmup failed: {e}")
        raise HTTPException(status_code=500, detail=f"All models cache warmup failed: {str(e)}")


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
async def create_database_profile(name: str, host: str, port: int, database: str, username: str, password: str):
    """Create a new database profile"""
    try:
        success, result = await profile_manager.create_profile(
            name=name, host=host, port=port, database=database, username=username, password=password
        )

        if success:
            profile = profile_manager.get_profile(result)
            return {
                "status": "success",
                "profile_id": result,
                "profile": profile.dict() if profile else None,
                "message": "Database profile created successfully",
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
        return {"status": "success", "profiles": [profile.dict() for profile in profiles], "count": len(profiles)}
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

        return {"status": "success", "profile_id": profile_id, "database_info": info}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get database info for profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get database info: {str(e)}")


@app.post("/database/profiles/default")
async def create_or_refresh_default_profiles():
    """Create or refresh the default database profiles"""
    try:
        await create_default_database_profiles()

        # Найдём созданные профили по умолчанию
        profiles = profile_manager.list_profiles()
        default_profile = next((p for p in profiles if p.name == "Default Database"), None)
        rna_central_profile = next((p for p in profiles if p.name == "RNA Central Database"), None)

        return {
            "status": "success",
            "message": "Default database profiles created/refreshed successfully",
            "profiles": {
                "default": default_profile.dict() if default_profile else None,
                "rna_central": rna_central_profile.dict() if rna_central_profile else None,
            },
        }

    except Exception as e:
        logger.error(f"Failed to create/refresh default profiles: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create default profiles: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
