# ==============================================================================
# Cognexa AI Backend - Production Root Dockerfile for Cloud (Render / Railway)
# ==============================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH="/app/backend"

WORKDIR /app

# Install system dependencies required for build & runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt ./
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copy backend application source
COPY backend/ ./backend/

WORKDIR /app/backend

# Ensure exports and uploads runtime directories exist
RUN mkdir -p exports uploads

EXPOSE 10000

# Start FastAPI server on dynamic $PORT (defaults to 10000 on Render)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
