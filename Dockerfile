# =============================================================================
# UyAI Multi-Stage Production Dockerfile
# =============================================================================

# Stage 1: Dependency Builder
FROM python:3.13-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

# Stage 2: Production Runtime
FROM python:3.13-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create unprivileged non-root user and persistent media directory
RUN useradd -u 1000 -m -s /bin/bash appuser && \
    mkdir -p /var/lib/uyai/media && \
    chown -R appuser:appuser /app /var/lib/uyai/media

# Copy application source, migrations, scripts, and configuration
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser migrations/ ./migrations/
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser alembic.ini pyproject.toml README.md ./

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
