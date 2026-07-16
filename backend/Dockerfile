FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system deps for bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY . .

# Create data directory for SQLite volume mount
RUN mkdir -p /data

EXPOSE 8005

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/api/health')" || exit 1

CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:8005", "--workers", "1", "--threads", "4", "--worker-class", "uvicorn.workers.UvicornWorker"]
