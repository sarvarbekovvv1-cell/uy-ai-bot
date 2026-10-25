# UyAI

AI-powered Real Estate Telegram Platform.

UyAI is a modern digital real-estate management platform designed to streamline property sales, rentals, comparative property valuation, broker workflows, and lead operations.

---

## Current Development Phase

> **Current Phase: Phase 1 — Foundation**
>
> **Notice:** Business functionality (property search, AI valuations, amoCRM synchronization, Mini App, maps, HR testing, analytics, Kaizen continuous improvement, and payments) is intentionally **NOT** implemented in this phase.
>
> Phase 1 strictly delivers the architectural, technical, database, and operational foundation.

---

## Requirements

- Python 3.12+ (tested on Python 3.13)
- Docker & Docker Compose (for local PostgreSQL container)
- Git

---

## Project Structure

```
uyai/
├── app/
│   ├── __init__.py          # Package initialization
│   ├── main.py              # FastAPI application & lifespan management
│   ├── config.py            # Centralized settings via pydantic-settings
│   ├── logging.py           # Structured logging with sensitive data sanitization
│   ├── database/
│   │   ├── __init__.py
│   │   ├── base.py          # SQLAlchemy 2.0 DeclarativeBase
│   │   └── session.py       # Async engine & sessionmaker (asyncpg)
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── main.py          # Telegram bot CLI runner
│   │   ├── dispatcher.py    # aiogram 3.x Dispatcher factory
│   │   └── handlers/
│   │       ├── __init__.py
│   │       └── start.py     # Foundation /start command handler
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py  # API route aggregation
│   │       └── health.py    # /health and /health/db endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   └── exceptions.py    # Domain exception hierarchy
│   ├── models/              # Reserved for future SQLAlchemy models
│   ├── schemas/             # Reserved for future Pydantic schemas
│   ├── services/            # Reserved for future business services
│   ├── repositories/        # Reserved for future data repositories
│   └── utils/               # Common helper utilities
├── migrations/              # Alembic database migrations
│   ├── env.py               # Async migration runner connected to Base.metadata
│   └── script.py.mako       # Migration template
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures and AsyncClient setup
│   ├── test_config.py       # Configuration tests
│   ├── test_health.py       # API & database connectivity tests
│   └── test_bot.py          # Bot dispatcher & handler tests
├── .env.example             # Example environment configuration
├── .gitignore               # Ignored files (secrets, venv, cache)
├── alembic.ini              # Alembic migration configuration
├── docker-compose.yml       # Local PostgreSQL service definition
├── Makefile                 # Development task shortcuts
├── pyproject.toml           # Project dependencies & Ruff/pytest configuration
└── README.md                # Project documentation
```

---

## Local Setup

### 1. Virtual Environment Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -e ".[dev]"
```

Or using the Makefile:

```bash
make install
```

### 2. Environment Configuration

Copy the example configuration to `.env`:

```bash
cp .env.example .env
```

Adjust variables in `.env` as appropriate. Note that `BOT_TOKEN` is optional for local foundation development and tests, but required in `production`.

### 3. Starting PostgreSQL (Local Development)

Start the local PostgreSQL container via Docker Compose:

```bash
make db-up
# or: docker compose up -d postgres
```

To stop the database:

```bash
make db-down
# or: docker compose down
```

### 4. Running Alembic Database Migrations

To inspect migration state or generate new revisions:

```bash
.venv/bin/alembic current
.venv/bin/alembic revision --autogenerate -m "initial_schema"
.venv/bin/alembic upgrade head
```

### 5. Running the FastAPI Application

Start the FastAPI backend with hot reloading:

```bash
make dev
# or: .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Endpoints available:
- `GET /`: `{"name": "UyAI", "status": "running"}`
- `GET /health`: `{"status": "ok"}`
- `GET /health/db`: `{"status": "ok", "database": "connected"}`

Interactive API documentation is accessible at `http://localhost:8000/docs`.

### 6. Running the Telegram Bot

Set `BOT_TOKEN` in `.env`, then run:

```bash
make bot
# or: .venv/bin/python -m app.bot.main
```

### 7. Running Automated Tests

Run the test suite with pytest:

```bash
make test
# or: .venv/bin/pytest -q
```

All foundation tests execute without network dependencies or external database instances.

### 8. Code Quality & Linting

Run Ruff checks:

```bash
make lint
# or: .venv/bin/ruff check .
```
