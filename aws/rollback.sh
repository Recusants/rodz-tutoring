#!/bin/bash
# ============================================================
# Rodz Tutoring - Standalone Rollback Script for AWS Host
# ============================================================
set -e
cd "$(dirname "$0")/.."

echo "============================================================"
echo "    RODZ TUTORING - ROLLBACK VERSION"
echo "============================================================"

TARGET_TAG="$1"
if [ -z "$TARGET_TAG" ]; then
    read -p "Enter version tag to rollback to (e.g. v1.0.0): " TARGET_TAG
fi

if [ -z "$TARGET_TAG" ]; then
    echo "[ERROR] No version specified. Rollback aborted."
    exit 1
fi

COMPOSE_FILE="docker-compose.prod.yml"
[ -f "docker-compose.yml" ] && COMPOSE_FILE="docker-compose.yml"

echo "[*] Setting TAG=$TARGET_TAG in .env.prod..."
sed -i "s/^TAG=.*/TAG=$TARGET_TAG/" .env.prod

echo "[*] Pulling image for tag $TARGET_TAG..."
docker compose -f "$COMPOSE_FILE" pull web

echo "[*] Restarting container with version $TARGET_TAG..."
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans web

echo "============================================================"
echo " Rollback to $TARGET_TAG successful!"
echo "============================================================"
docker compose -f "$COMPOSE_FILE" ps
