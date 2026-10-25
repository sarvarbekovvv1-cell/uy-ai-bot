.PHONY: install dev api bot test lint db-up db-down help

PYTHON ?= .venv/bin/python
UVICORN ?= .venv/bin/uvicorn
PYTEST ?= .venv/bin/pytest
RUFF ?= .venv/bin/ruff

help:
	@echo "UyAI Development Commands:"
	@echo "  make install  - Install project dependencies"
	@echo "  make dev      - Run FastAPI in reload mode"
	@echo "  make api      - Run FastAPI server"
	@echo "  make bot      - Run Telegram bot polling"
	@echo "  make test     - Run test suite"
	@echo "  make lint     - Run ruff linter"
	@echo "  make db-up    - Start local PostgreSQL via Docker Compose"
	@echo "  make db-down  - Stop local PostgreSQL container"

install:
	$(PYTHON) -m pip install -e ".[dev]"

dev:
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8000 --reload

api:
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8000

bot:
	$(PYTHON) -m app.bot.main

test:
	$(PYTEST) -q

lint:
	$(RUFF) check .

db-up:
	docker compose up -d postgres

db-down:
	docker compose down
