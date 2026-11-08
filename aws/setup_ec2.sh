#!/bin/bash
# ============================================================
# Rodz Tutoring - AWS EC2 Initial Setup Script (Ubuntu)
# ============================================================
# Usage on fresh Ubuntu EC2:
#   curl -fsSL https://raw.githubusercontent.com/YourUsername/rodz-tutoring/main/aws/setup_ec2.sh | bash
#   or run locally: sudo bash setup_ec2.sh
# ============================================================

set -e

echo "============================================================"
echo "    RODZ TUTORING - AWS EC2 SERVER INITIALIZATION"
echo "============================================================"

# Ensure running as root or with sudo
if [ "$EUID" -ne 0 ]; then
  echo "[ERROR] Please run with sudo or as root: sudo bash setup_ec2.sh"
  exit 1
fi

TARGET_USER="${SUDO_USER:-ubuntu}"
TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
APP_DIR="$TARGET_HOME/rodz-tutoring"

echo "[1/6] Updating system packages..."
apt-get update && apt-get upgrade -y
apt-get install -y curl git ufw ca-certificates gnupg lsb-release

echo "[2/6] Installing Docker Engine & Docker Compose plugin..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sh /tmp/get-docker.sh
    rm -f /tmp/get-docker.sh
fi

systemctl enable docker
systemctl start docker

# Add target user to docker group
usermod -aG docker "$TARGET_USER"
echo "[OK] Docker installed. Added $TARGET_USER to docker group."

echo "[3/6] Setting up application directory: $APP_DIR..."
mkdir -p "$APP_DIR/data" "$APP_DIR/media" "$APP_DIR/logs"

# Ensure permissions
chown -R "$TARGET_USER:$TARGET_USER" "$APP_DIR"
chmod -R 775 "$APP_DIR/data" "$APP_DIR/media"

echo "[4/6] Configuring Firewall (UFW)..."
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP Web'
ufw allow 443/tcp comment 'HTTPS Web'
ufw allow 8089/tcp comment 'Rodz Port Optional'
ufw --force enable

echo "[5/6] Creating default environment and docker-compose files..."
if [ ! -f "$APP_DIR/.env.prod" ]; then
    cat << 'EOF' > "$APP_DIR/.env.prod"
# Production Environment Configuration
SECRET_KEY=change-this-to-a-very-secure-random-key-for-rodz-production
DEBUG=False
ALLOWED_HOSTS=*

# Port exposed on AWS Host
HOST_PORT=80

# WhatsApp & Contact Settings
WHATSAPP_PHONE=27745685212
WHATSAPP_DISPLAY_PHONE=+27 74 568 5212
INFO_EMAIL=info@rodztutoring.co.za

# Docker Hub Configuration
DOCKER_REGISTRY=yourdockerhubusername
TAG=latest

# Persistent SQLite path in mounted volume
SQLITE_PATH=/app/data/db.sqlite3
GUNICORN_WORKERS=0
EOF
    chown "$TARGET_USER:$TARGET_USER" "$APP_DIR/.env.prod"
    chmod 600 "$APP_DIR/.env.prod"
    echo "[OK] Created $APP_DIR/.env.prod (please update DOCKER_REGISTRY with your username!)"
fi

echo "[6/6] Creating update.sh and rollback.sh helper scripts..."
cat << 'EOF' > "$APP_DIR/update.sh"
#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "============================================================"
echo "    RODZ TUTORING - PULLING LATEST & RESTARTING"
echo "============================================================"

# Ensure TAG=latest
sed -i 's/^TAG=.*/TAG=latest/' .env.prod 2>/dev/null || true

docker compose -f docker-compose.yml pull web
docker compose -f docker-compose.yml up -d --remove-orphans web
docker image prune -f

echo "============================================================"
echo " Update complete! Current status:"
echo "============================================================"
docker compose ps
EOF

cat << 'EOF' > "$APP_DIR/rollback.sh"
#!/bin/bash
set -e
cd "$(dirname "$0")"

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

echo "[*] Setting TAG=$TARGET_TAG in .env.prod..."
sed -i "s/^TAG=.*/TAG=$TARGET_TAG/" .env.prod

echo "[*] Pulling image for tag $TARGET_TAG..."
docker compose -f docker-compose.yml pull web

echo "[*] Restarting container with version $TARGET_TAG..."
docker compose -f docker-compose.yml up -d --remove-orphans web

echo "============================================================"
echo " Rollback to $TARGET_TAG successful!"
echo "============================================================"
docker compose ps
EOF

chmod +x "$APP_DIR/update.sh" "$APP_DIR/rollback.sh"
chown "$TARGET_USER:$TARGET_USER" "$APP_DIR/update.sh" "$APP_DIR/rollback.sh"

echo ""
echo "============================================================"
echo " AWS EC2 SETUP COMPLETE!"
echo "============================================================"
echo " App Directory: $APP_DIR"
echo " Next Steps:"
echo " 1. Edit $APP_DIR/.env.prod to set your DOCKER_REGISTRY"
echo " 2. Add your GitHub Actions Secrets (AWS_HOST, AWS_USER, AWS_SSH_PRIVATE_KEY)"
echo " 3. Double-click push.bat on your PC to trigger 1-click update!"
echo "============================================================"
