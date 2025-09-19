-- Создание расширения pg_stat_statements
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Создание тестовых таблиц для демонстрации
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

-- Создание индексов для демонстрации
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);

-- Вставка тестовых данных
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
