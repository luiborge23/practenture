# BizSimAI Backend - Production Dockerfile
# Multi-stage build for minimal image size

# ---- Stage 1: Build ----
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: Production ----
FROM python:3.11-slim AS production

# Add non-root user
RUN groupadd -r bizsim && useradd -r -g bizsim bizsim

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY backend/ ./backend/

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BIZSIMAI_DB_PATH=/data/bizsim.db \
    BIZSIMAI_JWT_SECRET=${BIZSIMAI_JWT_SECRET} \
    BIZSIMAI_OWNER_USERNAME=${BIZSIMAI_OWNER_USERNAME:-owner} \
    BIZSIMAI_OWNER_PASSWORD=${BIZSIMAI_OWNER_PASSWORD} \
    BIZSIMAI_PROFESSOR_USERNAME=${BIZSIMAI_PROFESSOR_USERNAME:-professor} \
    BIZSIMAI_PROFESSOR_PASSWORD=${BIZSIMAI_PROFESSOR_PASSWORD} \
    BIZSIMAI_JWT_EXPIRY_HOURS=${BIZSIMAI_JWT_EXPIRY_HOURS:-24} \
    BIZSIMAI_APPLE_AUDIENCE=${BIZSIMAI_APPLE_AUDIENCE} \
    BIZSIMAI_GOOGLE_AUDIENCE=${BIZSIMAI_GOOGLE_AUDIENCE} \
    BIZSIMAI_CORS_ORIGINS=${BIZSIMAI_CORS_ORIGINS:-*}

# Create data directory for SQLite (persistent volume)
RUN mkdir -p /data

# Expose port
EXPOSE 8005

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/api/health')" || exit 1

# Start with gunicorn (production WSGI server)
CMD ["gunicorn", "backend.main:app", \
     "--bind", "0.0.0.0:8005", \
     "--workers", "1", \
     "--threads", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
