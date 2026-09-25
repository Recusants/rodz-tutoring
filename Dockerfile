FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (curl for healthchecks, gcc/libpq if compiling postgres packages)
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

# Ensure directories for static and media exist
RUN mkdir -p /app/staticfiles /app/media/protected_pdfs

# Run collectstatic with a dummy key for build
RUN SECRET_KEY="build-time-static-collection-key" python manage.py collectstatic --noinput

# Create and switch to non-root user for security
RUN useradd -m rodzuser && chown -R rodzuser:rodzuser /app
USER rodzuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/ || exit 1

# Launch with Gunicorn WSGI server
CMD ["gunicorn", "rodz_project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
