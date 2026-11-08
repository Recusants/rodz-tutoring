# syntax=docker/dockerfile:1.4
FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (curl for healthchecks, build-essential for compiling C packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/

# Ensure directories for static, media, data, and logs exist
RUN mkdir -p /app/staticfiles /app/media/protected_pdfs /app/data /app/logs

# BUILD_HASH is injected at build time (e.g. git commit sha)
ARG BUILD_HASH=unknown
ENV APP_BUILD_HASH=${BUILD_HASH}

# Run collectstatic with a dummy key for build-time caching
RUN SECRET_KEY="build-time-static-collection-key" python manage.py collectstatic --noinput

# Normalize entrypoint line endings and make executable
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Create non-root user for security and grant permissions
RUN useradd -m rodzuser && chown -R rodzuser:rodzuser /app && chmod -R 775 /app/data /app/media
USER rodzuser

EXPOSE 8089

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8089/ || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]

# Launch with Gunicorn WSGI server
CMD ["gunicorn", "rodz_project.wsgi:application", "--bind", "0.0.0.0:8089", "--timeout", "120"]
