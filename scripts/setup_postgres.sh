#!/bin/bash

# PostgreSQL Setup Script for Remote Server
# This script sets up PostgreSQL from scratch with all required databases and users

set -e

echo "Starting PostgreSQL setup..."

# Database configuration
DB_NAME="query_analyzer"
DB_USER="analyzer_user"
DB_PASSWORD="analyzer_pass"
POSTGRES_USER="postgres"

# Function to execute SQL commands
execute_sql() {
    local sql="$1"
    echo "Executing: $sql"
    psql -h localhost -U $POSTGRES_USER -c "$sql"
}

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h localhost -U $POSTGRES_USER; do
    echo "PostgreSQL is not ready yet, waiting..."
    sleep 2
done

echo "PostgreSQL is ready!"

# Drop database and user if they exist (for clean setup)
echo "Cleaning up existing database and user..."
execute_sql "DROP DATABASE IF EXISTS $DB_NAME;" || true
execute_sql "DROP USER IF EXISTS $DB_USER;" || true

# Create user
echo "Creating user $DB_USER..."
execute_sql "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"

# Create database
echo "Creating database $DB_NAME..."
execute_sql "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

# Grant privileges
echo "Granting privileges..."
execute_sql "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

# Connect to the new database and set up extensions and tables
echo "Setting up database extensions and tables..."
psql -h localhost -U $POSTGRES_USER -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"

# Create test tables
echo "Creating test tables..."
psql -h localhost -U $POSTGRES_USER -d $DB_NAME << 'EOF'
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
EOF

# Grant additional privileges on tables
echo "Granting table privileges..."
psql -h localhost -U $POSTGRES_USER -d $DB_NAME -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;"
psql -h localhost -U $POSTGRES_USER -d $DB_NAME -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;"

echo "PostgreSQL setup completed successfully!"
echo "Database: $DB_NAME"
echo "User: $DB_USER"
echo "Connection string: postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"

# Test connection
echo "Testing connection..."
psql -h localhost -U $DB_USER -d $DB_NAME -c "SELECT 'Connection successful!' as status;"

echo "Setup complete!"
