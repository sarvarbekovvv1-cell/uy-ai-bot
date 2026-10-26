# UyAI

AI-powered Real Estate Telegram Platform.

UyAI is a modern digital real-estate management platform designed to streamline property sales, rentals, comparative property valuation, broker workflows, and lead operations.

---

---

## Telegram Mini App + Interactive Map (Phase 9)

UyAI includes a high-performance Telegram Mini App with an interactive Leaflet property map.

### Architecture
- **Backend**: FastAPI endpoints mounted under `/api/miniapp/v1/` (`/me`, `/properties`, `/properties/{id}`, `/map/properties`, `/favorites`, `/viewing-request`, `/broker-contact`).
- **Cryptographic Authentication**: Every request verifies the official Telegram WebApp `initData` signature (`HMAC-SHA256` with `WebAppData` key, constant-time `hmac.compare_digest`, freshness check within `TELEGRAM_INIT_DATA_MAX_AGE_SECONDS`). The frontend never sends unverified user IDs.
- **Frontend**: Lightweight React 18 + TypeScript + Vite + Leaflet stack located in `miniapp/` with Telegram WebApp SDK integration, auto-dark/light theme support, and responsive mobile-first UI.
- **Privacy & Safety**: Exposes strictly `APPROVED` listings. Media is served securely via cached backend proxy without exposing Telegram bot tokens.

### Configuration
```env
MINIAPP_URL=https://app.uyai.uz
MINIAPP_ALLOWED_ORIGINS=["https://app.uyai.uz","http://localhost:5173"]
TELEGRAM_INIT_DATA_MAX_AGE_SECONDS=86400
MINIAPP_DEV_AUTH_ENABLED=false
```

### Running Frontend Locally
```bash
cd miniapp
npm install
npm run dev
```
For production build:
```bash
cd miniapp
npm run build
```

---

## Admin / Manager Panel (Phase 11)

UyAI includes a dedicated, production-grade Staff Admin and Manager Panel located in `admin/`.

### Architecture
- **Backend**: FastAPI endpoints mounted under `/api/admin/v1/` (`/auth`, `/dashboard`, `/properties`, `/users`, `/brokers`, `/leads`, `/viewings`, `/crm`, `/audit`).
- **Staff Security & Authentication**:
  - OWASP-compliant `scrypt` password hashing (`N=16384, r=8, p=1`, 32-byte salt).
  - Secure `HttpOnly`, `SameSite=Lax` session cookies with server-side token hashing (`admin_sessions`).
  - Cryptographic `X-CSRF-Token` validation on all mutating HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`).
  - Anti-brute-force account lockout after 5 consecutive failed login attempts.
  - Strict vertical RBAC matrix with default-deny for customer accounts (`buyer`, `tenant`, `property_owner`).
  - Horizontal lead isolation: standard brokers are strictly restricted to their assigned leads, while managers (`head_broker`, `superadmin`) manage the full pipeline.
  - Immutable administrative audit trail (`admin_audit_events`) logging all staff actions (logins, moderations, lead transitions, viewings, role changes).
- **Frontend**: Clean React 18 + TypeScript + Vite single-page application in `admin/` with role-aware navigation, metrics dashboard, property moderation, lead stage pipeline, CRM outbox monitoring/retry, and user role controls.

### Configuration
```env
ADMIN_URL=https://admin.uyai.uz
ADMIN_ALLOWED_ORIGINS=["https://admin.uyai.uz","http://localhost:5174"]
ADMIN_SESSION_MAX_AGE_SECONDS=43200
ADMIN_SESSION_COOKIE_NAME=uyai_admin_session
ADMIN_SESSION_COOKIE_SECURE=false
ADMIN_SESSION_SECRET=your_super_secret_session_key
```

### Staff Bootstrapping CLI
To initialize or update the initial superadmin or staff account:
```bash
.venv/bin/python scripts/bootstrap_admin.py --telegram-id 123456789 --username admin --password "StrongPassword123!" --role superadmin
```

### Running Admin Frontend Locally
```bash
cd admin
npm install
npm run dev
```
For production build:
```bash
cd admin
npm run build
```

---

## Kaizen / PDCA Intelligence System & Admin Property Creation (Phase 12)

UyAI includes a continuous operational improvement system (**Kaizen / PDCA**) and **unified property creation from the Admin Panel**.

### Key Capabilities
- **Deterministic KPI Engine**: Calculates real-time lead funnel conversion rates, first-contact response times (mean, median, p90), viewing completion/cancellation rates, property moderation queues, and amoCRM outbox reliability without hallucination or metric fabrication.
- **PDCA Cycle Lifecycle**: Full state machine management (`draft` -> `planned` -> `active` -> `checking` -> `completed` / `cancelled`) with automatic baseline KPI snapshots, delta/progress tracking, and immutable audit logs.
- **Kaizen Recommendations Engine**: Rule-based heuristics combined with optional Gemini AI insights providing structured, explainable management suggestions with accept/dismiss actions.
- **Admin Property Creation**: Single source of truth listing creation reusing canonical `Property`, `PropertyMedia`, and `PropertyService` domain models, supporting multi-image upload with magic-byte validation and auto-approval permissions.

For detailed documentation, see [KAIZEN_PDCA.md](file:///Users/a0000/Desktop/uy%20ai%20bot/docs/KAIZEN_PDCA.md).

---

## Current Development Phase

> **Current Phase: Phase 12 — Kaizen / PDCA Intelligence System + Admin Property Creation**
>
> **Notice:** Kaizen continuous operational improvement engine, deterministic KPI analytics, PDCA lifecycle management, Gemini AI management recommendations, and unified Admin property creation implemented and verified.
> Phase 13 (final deployment & production hardening) is intentionally NOT started in this phase.


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

---

## AI Broker Integration (Phase 7)

UyAI features a natural-language AI Broker powered by Google's official `google-genai` SDK and grounded on UyAI's database.

### Environment Configuration

To enable the AI Broker locally:

```env
GEMINI_API_KEY=your_actual_google_gemini_api_key_here
GEMINI_MODEL=gemini-3.6-flash
AI_BROKER_ENABLED=true
AI_REQUEST_TIMEOUT_SECONDS=15.0
AI_MAX_HISTORY_MESSAGES=6
AI_MAX_SEARCH_RESULTS=5
```

If `AI_BROKER_ENABLED=false`, the bot provides a localized notice that AI Broker is temporarily unavailable, and all core functions continue operating normally.

### Architectural & Security Principles

1. **Database as the Sole Source of Truth**:
   The LLM (Gemini) is only used for intent extraction and grounded phrasing. It **never** invents properties, prices, or contact information. Properties are fetched directly from the database, and only `approved` listings are returned.
2. **Strict PII Protection**:
   Context built for the LLM contains only public property attributes (title, price, rooms, area, district, etc.). Owner user IDs, phone numbers, customer details, Telegram IDs, and internal broker notes are strictly excluded.
3. **Prompt Injection & Hallucination Defense**:
   User input is treated as untrusted. Prompt injection attacks (e.g. attempting to dump users or override policies) are safely classified without database dumps.
4. **Deterministic Testing Double**:
   All automated unit, integration, and E2E tests run against `FakeLLMProvider`. No real Gemini API calls or API keys are required during test suite execution.

### Known Limitations

---

## amoCRM Integration (Phase 10)

UyAI integrates with amoCRM asynchronously and safely using a **Transactional Outbox** pattern.

### Architectural Principles

1. **Transactional Outbox & Failure Isolation**:
   Customer operations (viewing requests, broker contact, AI broker inquiries) write to internal tables (`viewing_requests`, `leads`) and enqueue an outbox event (`crm_sync_events`) in the **same database transaction**. The internal transaction commits completely regardless of whether amoCRM is online, slow, or rate-limited.
2. **Provider Abstraction**:
   Business logic interacts with `AmoCRMProviderProtocol`. Automated test suites execute against `FakeAmoCRMProvider` without needing a real amoCRM account or network access.
3. **Deterministic Entity Linking**:
   `crm_entity_links` stores 1-to-1 mappings between UyAI entities (`User`, `Lead`) and amoCRM objects (`Contact`, `Lead`). This prevents duplicate records upon retries or cross-flow operations (Telegram + Mini App + AI Broker).
4. **Data Minimization & PII Protection**:
   Only public property attributes and customer contact names/phones are synchronized. Property owner contact information, customer authentication material, Telegram initData, and Gemini conversation histories are strictly excluded.
5. **Bidirectional Webhook with Loop Prevention**:
   Incoming webhooks at `POST /api/integrations/amocrm/webhook` update internal lead stages without re-enqueuing outbound events back to amoCRM (`enqueue_crm=False`), preventing infinite loops.
6. **Token Security**:
   Tokens are stored in environment variables and local gitignored runtime cache (`.cache/amocrm_tokens.json`). Single-flight lock (`asyncio.Lock`) prevents concurrent token refresh storms.

### Environment Configuration

```env
AMOCRM_ENABLED=false
AMOCRM_BASE_URL=https://your-agency.amocrm.ru
AMOCRM_CLIENT_ID=your_client_id
AMOCRM_CLIENT_SECRET=your_client_secret
AMOCRM_REDIRECT_URI=https://your-agency.amocrm.ru
AMOCRM_ACCESS_TOKEN=
AMOCRM_REFRESH_TOKEN=your_refresh_token
AMOCRM_PIPELINE_ID=1234567
AMOCRM_DEFAULT_RESPONSIBLE_USER_ID=
AMOCRM_REQUEST_TIMEOUT_SECONDS=10.0
AMOCRM_MAX_RETRIES=5
AMOCRM_WEBHOOK_SECRET=your_unguessable_webhook_secret
AMOCRM_STAGE_MAPPING_JSON={"new": 101, "contacted": 102, "qualified": 103, "viewing_scheduled": 104, "negotiation": 105, "won": 142, "lost": 143}
AMOCRM_BROKER_MAPPING_JSON={"2": 99991, "3": 99992}
```

### Operational Commands

```bash
# Check current outbox queue status
python3 scripts/process_crm_outbox.py --status

# Process a batch of pending events
python3 scripts/process_crm_outbox.py --process --batch-size 20

# Reset dead/failed events to pending for retry
python3 scripts/process_crm_outbox.py --retry-failed
```

### Known Limitations

- Real-time conversational context is bounded to the recent turns in active Telegram FSM state (`AIBrokerStates.chatting`).
- Complex legal or tax inquiries produce non-authoritative general guidance with explicit disclaimers and recommendations to consult a licensed human broker.
