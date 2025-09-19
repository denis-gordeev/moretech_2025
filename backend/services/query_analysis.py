"""Utilities that encapsulate the shared query-analysis workflow logic."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Any

from database import PostgreSQLAnalyzer
from database_profiles import DatabaseProfileManager
from execution_plan_cache import ExecutionPlanCache

logger = logging.getLogger(__name__)


class QueryAnalysisError(Exception):
    """Base exception that carries an HTTP status code."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class QueryValidationError(QueryAnalysisError):
    """Raised when the incoming SQL query does not meet basic requirements."""


class DatabaseProfileError(QueryAnalysisError):
    """Raised when a referenced database profile is missing or invalid."""


@dataclass
class AnalyzerResolution:
    """Result of resolving which analyzer should be used for a request."""

    analyzer: PostgreSQLAnalyzer
    description: str


def validate_query_text(query: str, *, max_length: int) -> str:
    """Return the stripped query or raise if it is empty or too large."""
    stripped = query.strip()
    if not stripped:
        raise QueryValidationError("Query cannot be empty")
    if len(query) > max_length:
        raise QueryValidationError(f"Query too long. Maximum length is {max_length} characters")
    return stripped


def mask_database_url(url: str) -> str:
    """Hide credentials in a database URL so it can be safely logged."""
    if "://" not in url:
        return url

    protocol, remainder = url.split("://", 1)
    if "@" not in remainder:
        return f"{protocol}://***"

    auth_part, host_part = remainder.split("@", 1)
    if ":" in auth_part:
        username = auth_part.split(":", 1)[0]
        return f"{protocol}://{username}:***@{host_part}"

    return f"{protocol}://***@{host_part}"


def resolve_analyzer(
    *,
    database_url: Optional[str],
    database_profile_id: Optional[str],
    default_analyzer: PostgreSQLAnalyzer,
    profile_manager: DatabaseProfileManager,
) -> AnalyzerResolution:
    """Pick an analyzer instance for the request and describe its source."""
    if database_url:
        logger.info("Using custom database: %s", mask_database_url(database_url))
        return AnalyzerResolution(PostgreSQLAnalyzer(database_url), "custom-url")

    if database_profile_id:
        connection = profile_manager.get_connection(database_profile_id)
        if not connection:
            raise DatabaseProfileError("Database profile not found or connection expired")

        profile_manager.update_last_used(database_profile_id)
        logger.info("Using database profile %s", database_profile_id)
        return AnalyzerResolution(PostgreSQLAnalyzer(connection.get_connection_url()), "profile")

    return AnalyzerResolution(default_analyzer, "default")


def extract_main_query(query: str) -> Tuple[str, str]:
    """Return (main_query, original_text) for single queries or chains."""
    parts = [part.strip() for part in query.split(";") if part.strip()]
    if not parts:
        # The caller already validated the query, but guard against edge cases.
        raise QueryValidationError("Query cannot be empty")

    if len(parts) > 1:
        logger.info("Analyzing query chain with %s statements", len(parts))
        return parts[0], query

    logger.info("Analyzing single query: %s", query[:100])
    return query, query


async def fetch_execution_plan(
    *,
    analyzer: PostgreSQLAnalyzer,
    main_query: str,
    plan_cache: ExecutionPlanCache,
) -> Tuple[Dict[str, Any], bool]:
    """Return execution-plan payload and a flag indicating cache hit."""
    database_url = analyzer.database_url
    cached_plan = plan_cache.get_plan(main_query, database_url)
    if cached_plan:
        logger.info("Using cached execution plan")
        return cached_plan, True

    logger.info("Generating new execution plan")
    plan_data = await analyzer.analyze_query_performance(main_query)
    plan_cache.set_plan(main_query, database_url, plan_data)
    return plan_data, False


def determine_llm_query(plan_json: Dict[str, Any], fallback: str) -> str:
    """Pick which SQL string should be provided to the LLM."""
    if "Converted Query" in plan_json:
        original = plan_json.get("Converted From", fallback)
        logger.info("LLM will analyze original query: %s", original[:100])
        return original

    logger.info("LLM will analyze query: %s", fallback[:100])
    return fallback


def refined_rewritten_query(
    *,
    request_query: str,
    warnings: Optional[list],
    rewritten_query: Optional[str],
) -> Optional[str]:
    """Hide rewritten query when it provides no actionable value."""
    if not rewritten_query:
        return None

    cleaned_source = request_query.strip()
    cleaned_rewritten = rewritten_query.strip()

    if cleaned_rewritten == cleaned_source:
        logger.info("Rewritten query is identical to original, hiding from frontend")
        return None

    if not warnings:
        logger.info("No warnings found, hiding rewritten query from frontend")
        return None

    logger.info("Showing rewritten query due to %s warnings", len(warnings))
    return rewritten_query


def build_execution_plan_model(plan_data: Dict[str, Any]) -> Dict[str, Any]:
    """Minimal helper so callers do not reach into plan payload directly."""
    return {
        "total_cost": plan_data["total_cost"],
        "execution_time": plan_data["execution_time"],
        "rows": plan_data["rows"],
        "width": plan_data["width"],
        "plan_json": plan_data["plan_json"],
    }
