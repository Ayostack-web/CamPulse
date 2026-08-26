FROM python:3.11-slim AS base
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    ghostscript \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

FROM base AS deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM deps AS api-run
COPY app/ app/
COPY db/ db/
EXPOSE 4000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4000"]
FROM base AS worker
# Worker needs full deps for document parsing (pytesseract, easyocr, docling).
# The lean requirements file skips these, causing silent degradation.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
CMD ["celery", "-A", "app.core.celery_app.celery_app", "worker", "--loglevel=info", "--concurrency=2"]

# Lean production target (no torch, easyocr, docling, transformers)
# This is the DEFAULT target — Docker builds this when no target is specified
FROM base AS lean-deps
COPY requirements-lean.txt .
RUN pip install --no-cache-dir -r requirements-lean.txt

FROM lean-deps AS api-lean
COPY app/ app/
COPY db/ db/
COPY alembic.ini .
COPY migrations/ migrations/
EXPOSE 4000
# NOTE: migrations are NOT run at boot — racing replicas would run alembic
# concurrently. Run them as a one-shot deploy step instead:
#   docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
CMD uvicorn app.main:app --host 0.0.0.0 --port 4000 --workers "${WEB_CONCURRENCY:-2}"
