-- Скрипт для настройки внешнего PostgreSQL для PostgreSQL Query Analyzer
-- Выполните этот скрипт на вашем PostgreSQL сервере

-- 1. Создание базы данных (если не существует)
-- CREATE DATABASE query_analyzer;

-- 2. Подключение к базе данных query_analyzer
\c query_analyzer;

-- 3. Создание пользователя с правами на чтение
-- CREATE USER analyzer_user WITH PASSWORD 'your_secure_password';

-- 4. Предоставление прав на базу данных
GRANT CONNECT ON DATABASE query_analyzer TO analyzer_user;
GRANT USAGE ON SCHEMA public TO analyzer_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analyzer_user;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO analyzer_user;

-- 5. Предоставление прав на будущие таблицы
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO analyzer_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO analyzer_user;

-- 6. Включение расширения pg_stat_statements (если не включено)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 7. Создание тестовых таблиц для демонстрации (опционально)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    total_amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    product_name VARCHAR(200) NOT NULL,
    quantity INTEGER NOT NULL,
    price DECIMAL(10,2) NOT NULL
);

-- 8. Создание индексов для демонстрации
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);

-- 9. Вставка тестовых данных (опционально)
INSERT INTO users (name, email) VALUES 
    ('John Doe', 'john@example.com'),
    ('Jane Smith', 'jane@example.com'),
    ('Bob Johnson', 'bob@example.com')
ON CONFLICT (email) DO NOTHING;

INSERT INTO orders (user_id, total_amount, status) VALUES 
    (1, 99.99, 'completed'),
    (2, 149.50, 'pending'),
    (1, 75.25, 'completed')
ON CONFLICT DO NOTHING;

INSERT INTO order_items (order_id, product_name, quantity, price) VALUES 
    (1, 'Laptop', 1, 99.99),
    (2, 'Mouse', 2, 25.00),
    (2, 'Keyboard', 1, 99.50),
    (3, 'Monitor', 1, 75.25)
ON CONFLICT DO NOTHING;

-- 10. Проверка настроек
SELECT 'Database setup completed successfully!' as status;

-- Проверка расширения pg_stat_statements
SELECT * FROM pg_extension WHERE extname = 'pg_stat_statements';

-- Проверка прав пользователя
SELECT 
    schemaname,
    tablename,
    has_table_privilege('analyzer_user', schemaname||'.'||tablename, 'SELECT') as can_select
FROM pg_tables 
WHERE schemaname = 'public';
