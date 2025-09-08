# PostgreSQL Query Analyzer

Умный инструмент для анализа SQL-запросов PostgreSQL с использованием LLM и structured output. Решение создано для конкурса MoreTech.

## 🎯 Описание проекта

PostgreSQL Query Analyzer — это интеллектуальная система для проактивного контроля SQL-запросов к PostgreSQL, которая решает ключевые проблемы:

- **Отсутствие автоматизированных рекомендаций** по оптимизации запросов и структуры БД
- **Невозможность предотвращения критических нагрузок** на этапе разработки
- **Зависимость от экспертных знаний** для устранения проблем производительности

## 🏗️ Архитектура

- **Backend**: Python + FastAPI + SQLAlchemy
- **Frontend**: React.js + Tailwind CSS
- **LLM**: OpenAI GPT-4 с structured output
- **Database**: PostgreSQL 15+ с расширением pg_stat_statements
- **CI/CD**: GitHub Actions с автоматическим тестированием

## ✨ Функциональность

### 🔍 Анализ запросов
- Анализ плана выполнения (EXPLAIN) без выполнения запросов
- Прогнозирование времени выполнения, I/O операций и использования памяти
- Детализация по ключевым метрикам производительности

### 🤖 Интеллектуальные рекомендации
- Генерация рекомендаций по оптимизации с помощью LLM
- Классификация по приоритету (высокий/средний/низкий)
- Оценка потенциального ускорения для каждой рекомендации
- Конкретные шаги реализации

### ⚠️ Предотвращение проблем
- Предупреждение о потенциально опасных операциях в режиме реального времени
- Выявление шаблонов проблемных запросов
- Интеграция с CI/CD для анализа на этапе разработки

## 📁 Структура проекта

```
moretech/
├── backend/                    # Python FastAPI сервис
│   ├── main.py                # Основное приложение
│   ├── models.py              # Pydantic модели
│   ├── database.py            # Работа с PostgreSQL
│   ├── llm_service.py         # Интеграция с OpenAI
│   ├── config.py              # Конфигурация
│   ├── requirements.txt       # Python зависимости
│   ├── Dockerfile             # Docker образ бэкенда
│   └── tests/                 # Тесты
├── frontend/                   # React.js приложение
│   ├── src/
│   │   ├── components/        # React компоненты
│   │   ├── services/          # API сервисы
│   │   └── App.js             # Главный компонент
│   ├── package.json           # Node.js зависимости
│   └── Dockerfile             # Docker образ фронтенда
├── .github/workflows/         # CI/CD конфигурация
├── docker-compose.yml         # Оркестрация сервисов
└── README.md                  # Документация
```

## 🚀 Быстрый старт

### Предварительные требования
- Docker и Docker Compose
- OpenAI API ключ
- **Внешний PostgreSQL сервер** с настройками:
  - Версия PostgreSQL 15+
  - Включенное расширение `pg_stat_statements`
  - Пользователь с правами на чтение (read-only)
  - Доступность по сети для Docker контейнера

### 1. Клонирование и настройка
```bash
git clone <repository-url>
cd moretech
cp env.example .env
```

### 2. Настройка переменных окружения
Отредактируйте файл `.env`:
```env
# OpenAI API ключ (обязательно)
OPENAI_API_KEY=your_openai_api_key_here

# Подключение к внешнему PostgreSQL (обязательно)
DATABASE_URL=postgresql://username:password@your-postgres-host:5432/your_database
```

**Примеры подключения к внешнему PostgreSQL:**
```env
# Локальный PostgreSQL
DATABASE_URL=postgresql://postgres:password@localhost:5432/query_analyzer

# Удаленный PostgreSQL
DATABASE_URL=postgresql://user:pass@192.168.1.100:5432/mydb

# PostgreSQL в облаке
DATABASE_URL=postgresql://user:pass@postgres.example.com:5432/production_db
```

### 3. Запуск через Docker Compose

**Для работы с внешним PostgreSQL (основной режим):**
```bash
docker-compose up -d
```

**Для разработки с локальным PostgreSQL:**
```bash
docker-compose -f docker-compose.dev.yml up -d
```

### 4. Настройка внешнего PostgreSQL

**Автоматическая настройка:**
```bash
# 1. Выполните SQL скрипт на вашем PostgreSQL сервере
psql -h your-postgres-host -U postgres -f scripts/setup-external-db.sql

# 2. Проверьте подключение
make test-db
```

**Ручная настройка:**
```sql
-- 1. Создайте базу данных (если нужно)
CREATE DATABASE query_analyzer;

-- 2. Создайте пользователя с правами на чтение
CREATE USER analyzer_user WITH PASSWORD 'your_password';

-- 3. Предоставьте права на базу данных
GRANT CONNECT ON DATABASE query_analyzer TO analyzer_user;
GRANT USAGE ON SCHEMA public TO analyzer_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analyzer_user;

-- 4. Включите расширение pg_stat_statements
-- В postgresql.conf:
-- shared_preload_libraries = 'pg_stat_statements'
-- pg_stat_statements.track = all
-- pg_stat_statements.max = 10000

-- 5. Перезапустите PostgreSQL и выполните:
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

### 5. Доступ к приложению
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 🔧 Разработка

### Локальная разработка бэкенда
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

pip install -r requirements.txt
uvicorn main:app --reload
```

### Локальная разработка фронтенда
```bash
cd frontend
npm install
npm start
```

### Запуск тестов
```bash
# Бэкенд тесты
cd backend
pytest

# Фронтенд тесты
cd frontend
npm test
```

## 📊 API Endpoints

### Основные эндпоинты
- `POST /analyze` - Анализ SQL запроса
- `GET /health` - Проверка состояния системы
- `GET /database/info` - Информация о базе данных
- `GET /examples` - Примеры SQL запросов

### Пример запроса анализа
```bash
curl -X POST "http://localhost:8000/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SELECT * FROM users WHERE email = \"test@example.com\""
  }'
```

## 🛡️ Безопасность

- Все запросы анализируются без выполнения
- Поддержка только чтения (read-only) для PostgreSQL
- Валидация входных данных
- CORS настройки для безопасности

## 🧪 Тестирование

Проект включает комплексное тестирование:
- Unit тесты для бэкенда (pytest)
- Component тесты для фронтенда (Jest)
- Интеграционные тесты
- Security scanning (Trivy)

## 📈 CI/CD

Автоматизированный pipeline включает:
- Автоматическое тестирование при push/PR
- Сборка Docker образов
- Security scanning
- Деплой в registry

## 🔍 Использование

### 1. Ввод SQL запроса
Введите SQL запрос в текстовое поле или выберите из примеров.

### 2. Анализ
Нажмите "Анализировать запрос" для получения:
- Плана выполнения
- Метрик ресурсов
- Рекомендаций по оптимизации
- Предупреждений

### 3. Изучение результатов
- **План выполнения**: детальная информация о том, как PostgreSQL выполнит запрос
- **Метрики ресурсов**: прогноз использования CPU, памяти и I/O
- **Рекомендации**: конкретные предложения по улучшению с приоритетами
- **Предупреждения**: потенциальные проблемы и риски

## 🎯 Соответствие требованиям

✅ **Анализ без выполнения**: Использует EXPLAIN для анализа планов  
✅ **LLM + Structured Output**: OpenAI GPT-4 с JSON Schema  
✅ **Vanilla PostgreSQL**: Только pg_stat_statements расширение  
✅ **PostgreSQL 15+**: Поддержка современных версий  
✅ **Read-only доступ**: Безопасный анализ без изменения данных  
✅ **CI/CD интеграция**: GitHub Actions pipeline  
✅ **Современный UI**: React.js с Tailwind CSS  

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📄 Лицензия

Проект создан для конкурса MoreTech.

## 🆘 Поддержка

### Проверка подключения к базе данных
```bash
# Проверка подключения к внешнему PostgreSQL
make test-db

# Проверка здоровья сервисов
make health

# Просмотр логов
make logs
```

### Частые проблемы

**1. Ошибка подключения к PostgreSQL:**
```bash
# Проверьте настройки в .env файле
cat .env | grep DATABASE_URL

# Убедитесь, что PostgreSQL доступен
telnet your-postgres-host 5432
```

**2. Расширение pg_stat_statements не найдено:**
```sql
-- Подключитесь к PostgreSQL как суперпользователь
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

**3. Недостаточно прав пользователя:**
```sql
-- Предоставьте необходимые права
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analyzer_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO analyzer_user;
```

**4. Проблемы с Docker сетью:**
```bash
# Для локального PostgreSQL используйте host.docker.internal
DATABASE_URL=postgresql://user:pass@host.docker.internal:5432/db

# Для удаленного PostgreSQL убедитесь в доступности порта
```

### Логи и отладка
```bash
# Логи бэкенда
docker-compose logs -f backend

# Логи фронтенда  
docker-compose logs -f frontend

# Логи базы данных (только для dev режима)
docker-compose -f docker-compose.dev.yml logs -f postgres
```

При возникновении проблем:
1. Проверьте статус системы в разделе "Статус"
2. Убедитесь в корректности OpenAI API ключа
3. Проверьте подключение к PostgreSQL с помощью `make test-db`
4. Обратитесь к логам Docker контейнеров

---

**Создано для MoreTech 2024** 🚀
