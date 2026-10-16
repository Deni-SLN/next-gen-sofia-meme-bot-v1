# Next Gent Sofia Trade v1 API image (Phase 7: containerised, reproducible).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # `services` makes `worker` importable, `services/api` makes `app`
    # importable - the same two roots uvicorn gets from --app-dir. Without
    # this the worker container could not import its own package.
    PYTHONPATH=/app/services:/app/services/api

WORKDIR /app

# Dependencies first so the layer caches across source edits.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install \
        "fastapi>=0.115.0" \
        "uvicorn[standard]>=0.30.0" \
        "sqlalchemy>=2.0.35" \
        "alembic>=1.13.0" \
        "pydantic>=2.9.0" \
        "pydantic-settings>=2.5.0" \
        "httpx>=0.27.0" \
        "python-dateutil>=2.9.0" \
        "psycopg[binary]>=3.2.0"

COPY alembic.ini ./
COPY migrations ./migrations
COPY services ./services

# Run as a non-root user.
RUN useradd --create-home --uid 10001 sofia && mkdir -p /app/data && chown -R sofia:sofia /app
USER sofia

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "services/api"]