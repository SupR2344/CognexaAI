# ==============================================================================
# Cognexa AI - Project Automation Makefile
# ==============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash

# Configuration Variables
PYTHON := python
PIP := pip
VENV_DIR := venv
BACKEND_DIR := backend
FRONTEND_DIR := frontend
SCRIPTS_DIR := scripts
DOCKER_COMPOSE := docker compose

# Colors for terminal output
COLOR_RESET   := \033[0m
COLOR_BOLD    := \033[1m
COLOR_INFO    := \033[36m
COLOR_SUCCESS := \033[32m
COLOR_WARNING := \033[33m

.PHONY: help setup dev-backend dev-frontend dev docker-up docker-down docker-logs db-init db-seed test test-backend lint format clean

# ------------------------------------------------------------------------------
# Help & Documentation
# ------------------------------------------------------------------------------
help: ## Show this help menu
	@echo -e "$(COLOR_BOLD)Cognexa AI - Developer Command Center$(COLOR_RESET)"
	@echo -e "Usage: make [target]"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(COLOR_INFO)%-16s$(COLOR_RESET) %s\n", $$1, $$2}'

# ------------------------------------------------------------------------------
# Environment Setup
# ------------------------------------------------------------------------------
setup: ## Create Python virtual environment and install backend & frontend dependencies
	@echo -e "$(COLOR_INFO)[*] Setting up Python virtual environment...$(COLOR_RESET)"
	$(PYTHON) -m venv $(VENV_DIR)
	@echo -e "$(COLOR_INFO)[*] Upgrading pip and installing backend dependencies...$(COLOR_RESET)"
	./$(VENV_DIR)/bin/pip install --upgrade pip setuptools wheel || $(PIP) install --upgrade pip setuptools wheel
	./$(VENV_DIR)/bin/pip install -r $(BACKEND_DIR)/requirements.txt || $(PIP) install -r $(BACKEND_DIR)/requirements.txt
	@echo -e "$(COLOR_INFO)[*] Installing frontend Node.js packages...$(COLOR_RESET)"
	cd $(FRONTEND_DIR) && npm install
	@if [ ! -f .env ]; then cp .env.example .env && echo -e "$(COLOR_SUCCESS)[+] Created .env from .env.example$(COLOR_RESET)"; fi
	@echo -e "$(COLOR_SUCCESS)[+] Setup complete!$(COLOR_RESET)"

# ------------------------------------------------------------------------------
# Development Mode
# ------------------------------------------------------------------------------
dev-backend: ## Run FastAPI server in local development mode with hot-reload
	@echo -e "$(COLOR_INFO)[*] Starting FastAPI Backend on http://localhost:8000 ...$(COLOR_RESET)"
	cd $(BACKEND_DIR) && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-frontend: ## Run Next.js frontend in development mode
	@echo -e "$(COLOR_INFO)[*] Starting Next.js Frontend on http://localhost:3000 ...$(COLOR_RESET)"
	cd $(FRONTEND_DIR) && npm run dev

dev: ## Run both backend and frontend concurrently
	@echo -e "$(COLOR_INFO)[*] Starting Cognexa AI Full Stack in development mode...$(COLOR_RESET)"
	@make -j2 dev-backend dev-frontend

# ------------------------------------------------------------------------------
# Docker Infrastructure
# ------------------------------------------------------------------------------
docker-up: ## Build and start all services via Docker Compose
	@echo -e "$(COLOR_INFO)[*] Starting all Cognexa services in background...$(COLOR_RESET)"
	$(DOCKER_COMPOSE) up -d --build
	@echo -e "$(COLOR_SUCCESS)[+] Services active: Frontend: http://localhost:3000 | Backend: http://localhost:8000$(COLOR_RESET)"

docker-down: ## Stop and remove all Docker containers and networks
	@echo -e "$(COLOR_WARNING)[*] Stopping all Cognexa containers...$(COLOR_RESET)"
	$(DOCKER_COMPOSE) down

docker-logs: ## Follow live logs from all running containers
	$(DOCKER_COMPOSE) logs -f

# ------------------------------------------------------------------------------
# Database Operations
# ------------------------------------------------------------------------------
db-init: ## Execute PostgreSQL schema initialization script (pgvector & tables)
	@echo -e "$(COLOR_INFO)[*] Initializing PostgreSQL database schema...$(COLOR_RESET)"
	@if $(DOCKER_COMPOSE) ps postgres | grep -q "Up"; then \
		$(DOCKER_COMPOSE) exec -T postgres psql -U cognexa -d cognexa_db -f /docker-entrypoint-initdb.d/01_init_db.sql; \
	else \
		psql "$${DATABASE_URL:-postgresql://cognexa:cognexa123@localhost:5432/cognexa_db}" -f $(SCRIPTS_DIR)/init_db.sql; \
	fi
	@echo -e "$(COLOR_SUCCESS)[+] Database schema initialized successfully!$(COLOR_RESET)"

db-seed: ## Populate database with sample test user, memories, conversations, and tasks
	@echo -e "$(COLOR_INFO)[*] Seeding sample data into PostgreSQL...$(COLOR_RESET)"
	$(PYTHON) $(SCRIPTS_DIR)/seed_data.py
	@echo -e "$(COLOR_SUCCESS)[+] Database seed finished!$(COLOR_RESET)"

# ------------------------------------------------------------------------------
# Testing & Code Quality
# ------------------------------------------------------------------------------
test: ## Run backend unit and integration test suite
	@echo -e "$(COLOR_INFO)[*] Running backend test suite with pytest...$(COLOR_RESET)"
	cd $(BACKEND_DIR) && pytest -v --disable-warnings

test-backend: test

lint: ## Run ruff / flake8 linting checks
	@echo -e "$(COLOR_INFO)[*] Linting backend codebase...$(COLOR_RESET)"
	cd $(BACKEND_DIR) && ruff check . || flake8 .
	@echo -e "$(COLOR_INFO)[*] Linting frontend codebase...$(COLOR_RESET)"
	cd $(FRONTEND_DIR) && npm run lint

format: ## Automatically format Python and TypeScript files
	@echo -e "$(COLOR_INFO)[*] Formatting Python code...$(COLOR_RESET)"
	cd $(BACKEND_DIR) && black . && ruff check --fix .
	@echo -e "$(COLOR_INFO)[*] Formatting Frontend code...$(COLOR_RESET)"
	cd $(FRONTEND_DIR) && npm run format || npx prettier --write .

# ------------------------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------------------------
clean: ## Remove temporary build files, caches, and test artifacts
	@echo -e "$(COLOR_INFO)[*] Cleaning temporary files and caches...$(COLOR_RESET)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf $(FRONTEND_DIR)/.next $(FRONTEND_DIR)/out $(FRONTEND_DIR)/node_modules/.cache 2>/dev/null || true
	@echo -e "$(COLOR_SUCCESS)[+] Clean completed!$(COLOR_RESET)"
