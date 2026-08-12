FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements-nlp.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-nlp.txt \
    && python -m spacy download en_core_web_sm || true

COPY backend/app ./app
COPY backend/data ./data

ENV PYTHONUNBUFFERED=1
ENV DOCS_DIR=./data/docs
ENV CHROMA_PERSIST_DIR=./chroma_data
ENV DATABASE_URL=sqlite+aiosqlite:///./sentinelai.db
ENV CORS_ORIGINS=*
ENV PORT=8000

EXPOSE 8000

# Render injects $PORT — bind to it for free-tier web services
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
