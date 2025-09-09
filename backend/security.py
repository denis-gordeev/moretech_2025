"""
Модуль безопасности для PostgreSQL Query Analyzer
"""
import ipaddress
import logging
from urllib.parse import urlparse
from typing import Set

logger = logging.getLogger(__name__)

# Разрешённые хосты для подключения
ALLOWED_HOSTS: Set[str] = {
    "localhost",
    "127.0.0.1",
    # Add your trusted database hosts here:
    # "db.company.com",
    # "postgres.aws.region.rds.amazonaws.com", 
    # "your-cloud-db.digitalocean.com",
}

# Запрещённые IP сети (RFC 1918 + другие приватные)
BLOCKED_NETWORKS = [
    "10.0.0.0/8",        # RFC 1918 - Private networks
    "172.16.0.0/12",     # RFC 1918 - Private networks
    "192.168.0.0/16",    # RFC 1918 - Private networks
    "169.254.0.0/16",    # RFC 3927 - Link-local
    "224.0.0.0/4",       # RFC 3171 - Multicast
    "240.0.0.0/4",       # RFC 1112 - Reserved
    "127.0.0.0/8",       # Loopback (кроме localhost который в whitelist)
]

# Разрешённые порты для PostgreSQL
ALLOWED_PORTS: Set[int] = {5432, 5433, 5434}


def validate_database_url(url: str) -> tuple:
    """
    Валидирует URL базы данных на предмет безопасности

    Args:
        url: Строка подключения к БД
        
    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    try:
        parsed = urlparse(url)
        
        # Проверка схемы
        if parsed.scheme not in ["postgresql", "postgres"]:
            return False, "Only PostgreSQL connections are allowed"
            
        # Проверка наличия хоста
        if not parsed.hostname:
            return False, "Host is required in database URL"
            
        host = parsed.hostname
        port = parsed.port or 5432
        
        # Проверка порта
        if port not in ALLOWED_PORTS:
            return False, f"Port {port} is not allowed. Allowed ports: {sorted(ALLOWED_PORTS)}"
        
        # Проверка разрешённых хостов
        if host in ALLOWED_HOSTS:
            return True, ""
            
        # Проверка на запрещённые IP сети
        try:
            ip = ipaddress.ip_address(host)
            for network_str in BLOCKED_NETWORKS:
                network = ipaddress.ip_network(network_str)
                if ip in network:
                    return False, f"Access to private network {network} is not allowed"
        except ValueError:
            # Не IP адрес - это доменное имя
            # Для доменных имён дополнительная проверка
            if not _is_allowed_domain(host):
                return False, f"Domain {host} is not in allowed list"
        return True, ""
        
    except Exception as e:
        logger.error(f"Error validating database URL: {e}")
        return False, f"Invalid database URL format: {str(e)}"


def _is_allowed_domain(domain: str) -> bool:
    """
    Проверяет, разрешён ли домен для подключения

    Args:
        domain: Доменное имя
        
    Returns:
        bool: True если домен разрешён
    """
    # Простая проверка - можно расширить для поддоменов
    # Например: *.example.com

    # Пока запрещаем все домены, кроме явно разрешённых
    return domain in ALLOWED_HOSTS


def sanitize_db_url_for_logging(url: str) -> str:
    """
    Удаляет пароль из URL для безопасного логирования

    Args:
        url: Строка подключения к БД
        
    Returns:
        str: Строка подключения без пароля
    """
    try:
        parsed = urlparse(url)
        
        # Заменяем пароль на ***
        if parsed.password:
            sanitized = url.replace(f":{parsed.password}@", ":***@")
        else:
            sanitized = url
            
        return sanitized
        
    except Exception:
        return "invalid_url"


def get_connection_limits() -> dict:
    """
    Возвращает лимиты для подключений к БД

    Returns:
        dict: Словарь с лимитами
    """
    return {
        "connection_timeout": 10,      # секунд
        "query_timeout": 30,           # секунд
        "max_connections": 5,          # одновременных подключений на пользователя
        "max_queries_per_minute": 20   # запросов в минуту
    }


def is_safe_query(query: str) -> tuple:
    """
    Базовая проверка безопасности SQL запроса
    
    ВНИМАНИЕ: Эта проверка отключена по умолчанию в настройках,
    так как для анализа мы переписываем UPDATE/DELETE запросы в SELECT.
    Включите enable_sql_security_check в config.py для активации.

    Args:
        query: SQL запрос
        
    Returns:
        tuple: (is_safe: bool, warning_message: str)
    """
    query_lower = query.lower().strip()

    # Запрещённые команды
    dangerous_commands = [
        "drop", "delete", "truncate", "insert", "update", 
        "create", "alter", "grant", "revoke", "copy"
    ]

    # Проверяем первое слово запроса
    first_word = query_lower.split()[0] if query_lower.split() else ""

    if first_word in dangerous_commands:
        return False, f"Command '{first_word.upper()}' is not allowed for security reasons"
        
    # Дополнительные проверки
    suspicious_patterns = [
        "pg_sleep", "pg_terminate_backend", "pg_cancel_backend",
        "information_schema", "pg_catalog", "pg_stat_activity"
    ]

    for pattern in suspicious_patterns:
        if pattern in query_lower:
            return False, f"Pattern '{pattern}' is potentially dangerous"

    return True, ""
