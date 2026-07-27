# Practenture Backend - Production Dockerfile
# Multi-stage build for minimal image size

# ---- Stage 1: Build ----
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

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
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PRACTENTURE_DB_PATH=/data/bizsim.db \
    PRACTENTURE_JWT_SECRET=${PRACTENTURE_JWT_SECRET} \
    PRACTENTURE_OWNER_USERNAME=${PRACTENTURE_OWNER_USERNAME:-owner} \
    PRACTENTURE_OWNER_PASSWORD=${PRACTENTURE_OWNER_PASSWORD} \
    PRACTENTURE_PROFESSOR_USERNAME=${PRACTENTURE_PROFESSOR_USERNAME:-professor} \
    PRACTENTURE_PROFESSOR_PASSWORD=${PRACTENTURE_PROFESSOR_PASSWORD} \
    PRACTENTURE_JWT_EXPIRY_HOURS=${PRACTENTURE_JWT_EXPIRY_HOURS:-24} \
    PRACTENTURE_APPLE_AUDIENCE=${PRACTENTURE_APPLE_AUDIENCE} \
    PRACTENTURE_GOOGLE_AUDIENCE=${PRACTENTURE_GOOGLE_AUDIENCE} \
    PRACTENTURE_CORS_ORIGINS=${PRACTENTURE_CORS_ORIGINS:-*}

# Create data directory for SQLite (persistent volume)
RUN mkdir -p /data

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Start with gunicorn (production WSGI server)
CMD ["gunicorn", "main:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "1", \
     "--threads", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
