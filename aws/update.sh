#!/bin/bash
# ============================================================
# Rodz Tutoring - Standalone Update Script for AWS Host
# ============================================================
set -e
cd "$(dirname "$0")/.."

echo "============================================================"
echo "    RODZ TUTORING - PULLING LATEST & RESTARTING"
echo "============================================================"

# Ensure TAG=latest
sed -i 's/^TAG=.*/TAG=latest/' .env.prod 2>/dev/null || true

COMPOSE_FILE="docker-compose.prod.yml"
[ -f "docker-compose.yml" ] && COMPOSE_FILE="docker-compose.yml"

docker compose -f "$COMPOSE_FILE" pull web
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans web
docker image prune -f

echo "============================================================"
echo " Update complete! Current status:"
echo "============================================================"
docker compose -f "$COMPOSE_FILE" ps
