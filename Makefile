.PHONY: help build up down logs test clean install

# Default target
help: ## Show this help message
	@echo "PostgreSQL Query Analyzer - Available commands:"
	@echo ""
	@echo "Container engine: $(COMPOSE_CMD)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

check-engine: ## Check available container engine
	@echo "Checking container engines..."
	@if command -v docker >/dev/null 2>&1; then echo "✅ Docker: $(docker --version)"; else echo "❌ Docker: not found"; fi
	@if command -v docker-compose >/dev/null 2>&1; then echo "✅ Docker Compose: $(docker-compose --version)"; else echo "❌ Docker Compose: not found"; fi
	@if command -v podman >/dev/null 2>&1; then echo "✅ Podman: $(podman --version)"; else echo "❌ Podman: not found"; fi
	@if command -v podman-compose >/dev/null 2>&1; then echo "✅ Podman Compose: $(podman-compose --version)"; else echo "❌ Podman Compose: not found"; fi
	@echo ""
	@echo "Selected compose command: $(COMPOSE_CMD)"

# Development commands
install: ## Install dependencies for both backend and frontend
	@echo "Installing backend dependencies..."
	cd backend && pip install -r requirements.txt
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

# Container engine detection
# Check if podman-compose is available, otherwise use docker-compose
ifeq ($(shell which podman-compose >/dev/null 2>&1 && echo "podman-compose"),podman-compose)
    COMPOSE_CMD = podman-compose
    DEV_COMPOSE_FILE = docker-compose.podman.yml
else
    COMPOSE_CMD = docker-compose
    DEV_COMPOSE_FILE = docker-compose.dev.yml
endif

# Docker/Podman commands
build: ## Build Docker/Podman images
	$(COMPOSE_CMD) build

up: ## Start all services (with external PostgreSQL)
	$(COMPOSE_CMD) up -d

up-dev: ## Start all services with local PostgreSQL for development
	$(COMPOSE_CMD) -f $(DEV_COMPOSE_FILE) up -d

down: ## Stop all services
	$(COMPOSE_CMD) down

down-dev: ## Stop development services
	$(COMPOSE_CMD) -f $(DEV_COMPOSE_FILE) down

logs: ## Show logs from all services
	$(COMPOSE_CMD) logs -f

logs-backend: ## Show backend logs
	$(COMPOSE_CMD) logs -f backend

logs-frontend: ## Show frontend logs
	$(COMPOSE_CMD) logs -f frontend

logs-db: ## Show database logs
	$(COMPOSE_CMD) logs -f postgres

# Testing commands
test: ## Run all tests
	@echo "Running backend tests..."
	cd backend && python -m pytest tests/ -v
	@echo "Running frontend tests..."
	cd frontend && npm test -- --watchAll=false

test-backend: ## Run backend tests only
	cd backend && python -m pytest tests/ -v

test-frontend: ## Run frontend tests only
	cd frontend && npm test -- --watchAll=false

# Development commands
dev-backend: ## Start backend in development mode
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start frontend in development mode
	cd frontend && npm start

# Database commands
db-reset: ## Reset database (WARNING: This will delete all data)
	$(COMPOSE_CMD) -f $(DEV_COMPOSE_FILE) down -v
	$(COMPOSE_CMD) -f $(DEV_COMPOSE_FILE) up -d postgres
	sleep 10
	$(COMPOSE_CMD) -f $(DEV_COMPOSE_FILE) up -d

db-shell: ## Connect to database shell
	$(COMPOSE_CMD) -f $(DEV_COMPOSE_FILE) exec postgres psql -U analyzer_user -d query_analyzer

# Utility commands
clean: ## Clean up Docker/Podman containers and volumes
	$(COMPOSE_CMD) down -v --remove-orphans
	@if command -v docker >/dev/null 2>&1; then docker system prune -f; fi
	@if command -v podman >/dev/null 2>&1; then podman system prune -f; fi

status: ## Show status of all services
	$(COMPOSE_CMD) ps

# Health check
health: ## Check health of all services
	@echo "Checking backend health..."
	curl -f http://localhost:8000/health || echo "Backend is not healthy"
	@echo "Checking frontend..."
	curl -f http://localhost:3000 || echo "Frontend is not healthy"

# Database connection test
test-db: ## Test connection to external PostgreSQL database
	@echo "Testing database connection..."
	python scripts/test-connection.py

# Setup commands
setup: install build up ## Complete setup (install, build, and start with external PostgreSQL)
	@echo "Setup complete! Services are starting..."
	@echo "Frontend: http://localhost:3000"
	@echo "Backend: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs"
	@echo ""
	@echo "Make sure to configure DATABASE_URL in .env file for external PostgreSQL"

setup-dev: install build up-dev ## Complete setup for development (with local PostgreSQL)
	@echo "Development setup complete! Services are starting..."
	@echo "Frontend: http://localhost:3000"
	@echo "Backend: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs"
	@echo "Local PostgreSQL: localhost:5432"

# Production commands
prod-build: ## Build production images
	$(COMPOSE_CMD) -f docker-compose.yml -f docker-compose.prod.yml build

prod-up: ## Start production services
	$(COMPOSE_CMD) -f docker-compose.yml -f docker-compose.prod.yml up -d

# Documentation
docs: ## Generate API documentation
	@echo "API documentation available at: http://localhost:8000/docs"
