# ==============================================================================
# Cognexa AI Backend - Multi-Stage Dockerfile
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build Dependencies
# ------------------------------------------------------------------------------
FROM python:3.11-slim as builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install build-time system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# ------------------------------------------------------------------------------
# Stage 2: Runtime Production Container
# ------------------------------------------------------------------------------
FROM python:3.11-slim as runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app"

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application source code
COPY . /app

# Ensure runtime directories exist and set up user (UID 1000 for Hugging Face Spaces compatibility)
RUN mkdir -p /app/exports /app/uploads && \
    addgroup --system --gid 1000 cognexa && \
    adduser --system --uid 1000 --ingroup cognexa cognexa && \
    chown -R cognexa:cognexa /app

USER cognexa

# Expose ports (7860 for Hugging Face Spaces, 8000 for standard Docker)
EXPOSE 7860
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-7860}/health || exit 1

# Launch FastAPI server (defaults to 7860 for Hugging Face Spaces, or dynamic $PORT)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
