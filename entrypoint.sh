#!/bin/bash
# entrypoint.sh — Rodz Tutoring Platform
# Automated database migrations and smart static file handling on container startup

set -e

echo "========================================"
echo "  Rodz Tutoring Platform - Starting"
echo "========================================"

# Ensure data, media, static, and logs directories exist
mkdir -p /app/data /app/media/protected_pdfs /app/staticfiles /app/logs

# Generate a fingerprint using the build-time git SHA
CURRENT_HASH="${APP_BUILD_HASH:-$(stat -c %Y /app/manage.py 2>/dev/null || echo "unknown")}"
MARKER_FILE="/app/staticfiles/.image_hash"

NEEDS_SETUP=false
if [ ! -f "$MARKER_FILE" ]; then
    NEEDS_SETUP=true
    echo "[INFO] First boot detected — running migrations and static collection."
elif [ "$(cat $MARKER_FILE 2>/dev/null)" != "$CURRENT_HASH" ]; then
    NEEDS_SETUP=true
    echo "[INFO] New image version detected (${CURRENT_HASH}) — running migrations and static collection."
else
    echo "[OK] Same image as last boot — fast startup."
fi

echo "Running database migrations..."
python manage.py migrate --noinput
echo "[OK] Database migrations up to date!"

if [ "$NEEDS_SETUP" = true ]; then
    if [ "$DEBUG" = "True" ] || [ "$DEBUG" = "true" ] || [ "$DEBUG" = "1" ]; then
        echo "Dev mode: skipping static file collection"
    else
        echo "Collecting static files..."
        python manage.py collectstatic --noinput
        echo "[OK] Static files collected!"
    fi

    if [ "${AUTO_SEED:-True}" = "True" ] || [ "${AUTO_SEED:-True}" = "true" ] || [ "${AUTO_SEED:-True}" = "1" ]; then
        echo "Seeding Rodz Tutoring database (idempotent)..."
        python manage.py seed_rodz
        echo "[OK] Database seeding complete!"
    fi

    mkdir -p /app/staticfiles
    echo "$CURRENT_HASH" > "$MARKER_FILE"
fi

echo ""
echo "  Rodz Tutoring Platform is ready!"
echo "========================================"

# Dynamic Gunicorn workers (2 * cores + 1, capped at 4, or GUNICORN_WORKERS env)
if [ "${GUNICORN_WORKERS:-0}" -gt 0 ] 2>/dev/null; then
    WORKERS="$GUNICORN_WORKERS"
else
    WORKERS=$(python -c "import os; print(min((os.cpu_count() or 1) * 2 + 1, 4))")
fi

if [ "$1" = "gunicorn" ]; then
    echo "[INFO] Starting Gunicorn with $WORKERS workers on port 8089..."
    exec "$@" --workers "$WORKERS"
else
    exec "$@"
fi
