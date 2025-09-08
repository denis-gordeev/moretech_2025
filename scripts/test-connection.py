#!/usr/bin/env python3
"""
Скрипт для проверки подключения к внешнему PostgreSQL
Использование: python scripts/test-connection.py
"""

import os
import sys
import psycopg2
from urllib.parse import urlparse

def test_database_connection():
    """Тестирует подключение к базе данных"""
    
    # Получаем URL базы данных из переменной окружения
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ Ошибка: DATABASE_URL не установлена в переменных окружения")
        print("Установите переменную окружения:")
        print("export DATABASE_URL='postgresql://user:password@host:port/database'")
        return False
    
    try:
        # Парсим URL
        parsed = urlparse(database_url)
        print(f"🔗 Подключение к: {parsed.hostname}:{parsed.port}/{parsed.path[1:]}")
        
        # Подключаемся к базе данных
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Проверяем версию PostgreSQL
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"✅ PostgreSQL версия: {version}")
        
        # Проверяем расширение pg_stat_statements
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
            )
        """)
        has_extension = cursor.fetchone()[0]
        
        if has_extension:
            print("✅ Расширение pg_stat_statements установлено")
        else:
            print("⚠️  Предупреждение: Расширение pg_stat_statements не установлено")
            print("   Для полной функциональности установите расширение:")
            print("   CREATE EXTENSION IF NOT EXISTS pg_stat_statements;")
        
        # Проверяем права пользователя
        cursor.execute("""
            SELECT 
                current_user,
                current_database(),
                has_database_privilege(current_user, current_database(), 'CONNECT') as can_connect
        """)
        user_info = cursor.fetchone()
        print(f"✅ Пользователь: {user_info[0]}")
        print(f"✅ База данных: {user_info[1]}")
        print(f"✅ Права на подключение: {'Да' if user_info[2] else 'Нет'}")
        
        # Проверяем таблицы
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        table_count = cursor.fetchone()[0]
        print(f"✅ Количество таблиц в public схеме: {table_count}")
        
        # Тестируем EXPLAIN
        try:
            cursor.execute("EXPLAIN (FORMAT JSON) SELECT 1")
            explain_result = cursor.fetchone()[0]
            print("✅ EXPLAIN работает корректно")
        except Exception as e:
            print(f"❌ Ошибка при тестировании EXPLAIN: {e}")
            return False
        
        cursor.close()
        conn.close()
        
        print("\n🎉 Все проверки пройдены успешно!")
        print("База данных готова для работы с PostgreSQL Query Analyzer")
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

def main():
    """Основная функция"""
    print("🔍 Проверка подключения к PostgreSQL...")
    print("=" * 50)
    
    success = test_database_connection()
    
    if success:
        print("\n✅ Готово! Можно запускать приложение:")
        print("docker-compose up -d")
        sys.exit(0)
    else:
        print("\n❌ Проверьте настройки подключения к базе данных")
        sys.exit(1)

if __name__ == "__main__":
    main()
