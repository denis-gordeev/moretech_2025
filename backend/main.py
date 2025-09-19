"""
PostgreSQL Query Analyzer Backend
Создано командой БОРЖОРА для MoreTech 2025

Основной модуль FastAPI приложения для анализа SQL-запросов PostgreSQL
с использованием LLM и structured output.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
from datetime import datetime

from models import QueryAnalysisRequest, QueryAnalysis, ExecutionPlan, HealthCheck, DatabaseConfig, ExecutionPlanResponse
from database import PostgreSQLAnalyzer
from llm_service import LLMAnalyzer
from log_analyzer import PostgreSQLLogAnalyzer
from config_analyzer import PostgreSQLConfigAnalyzer
from cache_warmup import CacheWarmupService
from example_generator import ExampleGenerator
from table_stats_service import TableStatsService
from config import settings
# Security module removed - allowing all database connections
from database_profiles import profile_manager, DatabaseProfile
from execution_plan_cache import ExecutionPlanCache

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
execution_plan_cache = ExecutionPlanCache()

# Глобальная переменная для хранения статистики таблиц
table_statistics = {}


async def create_default_database_profiles():
    """Создаёт профили баз данных по умолчанию"""
    try:
        # Парсим URL основной базы данных
        from urllib.parse import urlparse
        parsed_url = urlparse(settings.database_url)
        
        # Извлекаем компоненты подключения для localhost
        host = parsed_url.hostname or "localhost"
        port = parsed_url.port or 5432
        database = parsed_url.path.lstrip('/') or "query_analyzer"
        username = parsed_url.username or "analyzer_user"
        password = parsed_url.password or "analyzer_pass"
        
        # Проверяем существующие профили
        existing_profiles = profile_manager.list_profiles()
        
        # 1. Создаём профиль по умолчанию (localhost)
        default_profile_exists = any(
            profile.name == "Default Database" and 
            profile.host == host and 
            profile.port == port and 
            profile.database == database and 
            profile.username == username
            for profile in existing_profiles
        )
        
        if not default_profile_exists:
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
        
        # 2. Создаём профиль RNA Central
        rna_central_exists = any(
            profile.name == "RNA Central Database" and 
            profile.host == "hh-pgsql-public.ebi.ac.uk"
            for profile in existing_profiles
        )
        
        if not rna_central_exists:
            success, result = await profile_manager.create_profile(
                name="RNA Central Database",
                host="hh-pgsql-public.ebi.ac.uk",
                port=5432,
                database="pfmegrnargs",
                username="reader",
                password="NWDMCE5xdipIjRrp"
            )
            
            if success:
                logger.info(f"Created RNA Central database profile: {result}")
            else:
                logger.warning(f"Failed to create RNA Central database profile: {result}")
        else:
            logger.info("RNA Central database profile already exists")
            
    except Exception as e:
        logger.error(f"Error creating default database profiles: {e}")


async def startup_load_cache():
    """Загружает кэш для основной модели из файла при запуске"""
    try:
        logger.info("Loading cache for main model from file...")
        
        # Получаем основную модель
        main_model = llm_analyzer.selected_model
        
        # Загружаем кэш из файла
        file_cache = await cache_warmup.load_cache_from_file(main_model.model)
        if file_cache:
            # Загружаем кэш в основной анализатор
            await llm_analyzer.load_cache_from_file(file_cache)
            logger.info(f"Loaded {len(file_cache)} cache entries for main model: {main_model.name}")
        else:
            logger.info("No cache file found for main model")
            
    except Exception as e:
        logger.error(f"Failed to load cache for main model: {e}")


async def startup_load_execution_plan_cache():
    """Загружает кэш планов выполнения из файла при запуске"""
    try:
        logger.info("Loading execution plan cache from file...")
        
        # Загружаем кэш планов выполнения из файла
        execution_plan_cache.load_cache_from_file()
        logger.info(f"Loaded execution plan cache with {len(execution_plan_cache._cache)} entries")
            
    except Exception as e:
        logger.error(f"Failed to load execution plan cache: {e}")


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
        
        logger.info(f"Execution plan pre-computation completed: {result['total_processed']} total processed, {result['total_errors']} total errors across {result['total_profiles']} database profiles")
            
    except Exception as e:
        logger.error(f"Failed to pre-compute execution plans: {e}")


@app.on_event("startup")
async def startup_event():
    """Событие запуска приложения - предварительное кэширование"""
    logger.info("Application startup - starting cache warmup...")

    # Проверяем подключения
    try:
        db_connected = await db_analyzer.test_connection()
        openai_available = await llm_analyzer.test_connection()

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

        logger.info("Starting background cache warmup for all models...")
        result = await cache_warmup.warmup_cache_for_all_models(max_queries=20)  # Кэшируем все примеры для всех моделей при запуске

        logger.info(f"Background cache warmup completed: {result['total_processed']} queries cached across {len(result['models'])} models")

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
                    logger.info(f"Additional cache warmup completed: {additional_result['processed']} new queries cached")
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

        # SQL security check removed - allowing all queries

        # Используем переданный URL БД или дефолтный
        analyzer = db_analyzer
        if request.database_url:
            # Database URL validation removed - allowing all connections
            safe_url = request.database_url.replace("://", "://***:***@") if "://" in request.database_url else request.database_url
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

        # Получаем план выполнения для основного запроса (с кэшированием)
        database_url = analyzer.database_url
        
        # Проверяем кэш планов выполнения
        cached_plan = execution_plan_cache.get_plan(main_query, database_url)
        if cached_plan:
            logger.info("Using cached execution plan")
            plan_data = cached_plan
        else:
            logger.info("Generating new execution plan")
            plan_data = await analyzer.analyze_query_performance(main_query)
            # Сохраняем план в кэш
            execution_plan_cache.set_plan(main_query, database_url, plan_data)

        # Создаем объект плана выполнения
        execution_plan = ExecutionPlan(
            total_cost=plan_data["total_cost"],
            execution_time=plan_data["execution_time"],
            rows=plan_data["rows"],
            width=plan_data["width"],
            plan_json=plan_data["plan_json"],
        )

        # Анализируем с помощью LLM (передаем только оригинальный запрос)
        logger.info("Running LLM analysis...")
        global table_statistics
        
        # LLM всегда получает оригинальный запрос для правильного контекста
        query_for_llm = all_queries_text
        if "Converted Query" in plan_data["plan_json"]:
            original_query = plan_data["plan_json"].get("Converted From", all_queries_text)
            query_for_llm = original_query
            logger.info(f"LLM will analyze original query: {original_query[:100]}...")
        else:
            logger.info(f"LLM will analyze query: {query_for_llm[:100]}...")
        
        llm_result = await llm_analyzer.analyze_query_with_llm(
            query_for_llm, plan_data["plan_json"], table_statistics
        )

        # Проверяем, нужно ли показывать rewritten_query
        rewritten_query = llm_result.get("rewritten_query")
        warnings = llm_result.get("warnings", [])
        
        # Показываем переписанный запрос только если:
        # 1. Есть предупреждения (warnings)
        # 2. Переписанный запрос отличается от оригинального
        if rewritten_query and rewritten_query.strip() == request.query.strip():
            # Если переписанный запрос совпадает с оригинальным, не показываем его
            rewritten_query = None
            logger.info("Rewritten query is identical to original, hiding from frontend")
        elif rewritten_query and not warnings:
            # Если нет предупреждений, не показываем переписанный запрос
            rewritten_query = None
            logger.info("No warnings found, hiding rewritten query from frontend")
        elif rewritten_query and warnings:
            logger.info(f"Showing rewritten query due to {len(warnings)} warnings")
        
        # Создаем результат анализа
        analysis = QueryAnalysis(
            query=request.query,
            rewritten_query=rewritten_query,
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


@app.post("/analyze/execution-plan", response_model=ExecutionPlanResponse)
async def analyze_execution_plan(request: QueryAnalysisRequest):
    """
    Возвращает только план выполнения запроса (быстрый ответ)
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
            safe_url = request.database_url.replace("://", "://***:***@") if "://" in request.database_url else request.database_url
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

        # Получаем план выполнения для основного запроса (с кэшированием)
        database_url = analyzer.database_url
        
        # Проверяем кэш планов выполнения
        cached_plan = execution_plan_cache.get_plan(main_query, database_url)
        if cached_plan:
            logger.info("Using cached execution plan")
            plan_data = cached_plan
        else:
            logger.info("Generating new execution plan")
            plan_data = await analyzer.analyze_query_performance(main_query)
            # Сохраняем план в кэш
            execution_plan_cache.set_plan(main_query, database_url, plan_data)

        # Создаем объект плана выполнения
        execution_plan = ExecutionPlan(
            total_cost=plan_data["total_cost"],
            execution_time=plan_data["execution_time"],
            rows=plan_data["rows"],
            width=plan_data["width"],
            plan_json=plan_data["plan_json"],
        )

        # Возвращаем только план выполнения
        return ExecutionPlanResponse(
            query=request.query,
            execution_plan=execution_plan,
            status="execution_plan_ready",
            analysis_timestamp=datetime.now(),
            has_errors=plan_data.get("has_errors", False),
            postgresql_errors=plan_data.get("postgresql_errors", []),
            error_analysis=None  # Можно добавить анализ ошибок от LLM позже
        )

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
            safe_url = request.database_url.replace("://", "://***:***@") if "://" in request.database_url else request.database_url
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

        # Получаем план выполнения (должен быть уже в кэше)
        database_url = analyzer.database_url
        cached_plan = execution_plan_cache.get_plan(main_query, database_url)
        
        if not cached_plan:
            # Если план не в кэше, генерируем его
            logger.info("Execution plan not in cache, generating...")
            plan_data = await analyzer.analyze_query_performance(main_query)
            execution_plan_cache.set_plan(main_query, database_url, plan_data)
        else:
            logger.info("Using cached execution plan for LLM analysis")
            plan_data = cached_plan

        # Анализируем с помощью LLM
        logger.info("Running LLM analysis...")
        global table_statistics
        
        # LLM всегда получает оригинальный запрос для правильного контекста
        query_for_llm = all_queries_text
        if "Converted Query" in plan_data["plan_json"]:
            original_query = plan_data["plan_json"].get("Converted From", all_queries_text)
            query_for_llm = original_query
            logger.info(f"LLM will analyze original query: {original_query[:100]}...")
        else:
            logger.info(f"LLM will analyze query: {query_for_llm[:100]}...")
        
        llm_result = await llm_analyzer.analyze_query_with_llm(
            query_for_llm, plan_data["plan_json"], table_statistics
        )

        # Проверяем, нужно ли показывать rewritten_query
        rewritten_query = llm_result.get("rewritten_query")
        warnings = llm_result.get("warnings", [])
        
        # Показываем переписанный запрос только если:
        # 1. Есть предупреждения (warnings)
        # 2. Переписанный запрос отличается от оригинального
        if rewritten_query and rewritten_query.strip() == request.query.strip():
            # Если переписанный запрос совпадает с оригинальным, не показываем его
            rewritten_query = None
            logger.info("Rewritten query is identical to original, hiding from frontend")
        elif rewritten_query and not warnings:
            # Если нет предупреждений, не показываем переписанный запрос
            rewritten_query = None
            logger.info("No warnings found, hiding rewritten query from frontend")
        elif rewritten_query and warnings:
            logger.info(f"Showing rewritten query due to {len(warnings)} warnings")

        # Возвращаем только LLM анализ
        return {
            "query": request.query,
            "rewritten_query": rewritten_query,
            "resource_metrics": llm_result["resource_metrics"],
            "recommendations": llm_result["recommendations"],
            "warnings": llm_result["warnings"],
            "status": "llm_analysis_ready"
        }

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
            f"postgresql://{config.username}:{config.password}@"
            f"{config.host}:{config.port}/{config.database}"
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
                        success, result = await profile_manager.refresh_connection(database_profile_id, "NWDMCE5xdipIjRrp")
                    else:
                        success = False
                    
                    if success:
                        connection = profile_manager.get_connection(database_profile_id)
                        if connection:
                            analyzer = PostgreSQLAnalyzer(connection.get_connection_url())
                            logger.info(f"Reconnected to database profile {database_profile_id}")
                        else:
                            logger.warning(f"Failed to reconnect to database profile {database_profile_id}, using default")
                    else:
                        logger.warning(f"Failed to refresh connection for database profile {database_profile_id}, using default")
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
                    adapted_examples = await example_generator.generate_examples_with_llm_for_database(analyzer, database_profile_id)
                    if adapted_examples:
                        # Заменяем стандартные примеры на адаптированные
                        test_queries = adapted_examples
                        logger.info(f"Adapted {len(adapted_examples)} examples for external database profile {database_profile_id}")
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
        result = await execution_plan_cache.precompute_execution_plans(
            db_analyzer, test_queries, max_queries
        )
        
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
async def create_or_refresh_default_profiles():
    """Create or refresh the default database profiles"""
    try:
        await create_default_database_profiles()
        
        # Найдём созданные профили по умолчанию
        profiles = profile_manager.list_profiles()
        default_profile = next(
            (p for p in profiles if p.name == "Default Database"), 
            None
        )
        rna_central_profile = next(
            (p for p in profiles if p.name == "RNA Central Database"), 
            None
        )
        
        return {
            "status": "success",
            "message": "Default database profiles created/refreshed successfully",
            "profiles": {
                "default": default_profile.dict() if default_profile else None,
                "rna_central": rna_central_profile.dict() if rna_central_profile else None
            }
        }
            
    except Exception as e:
        logger.error(f"Failed to create/refresh default profiles: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create default profiles: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
