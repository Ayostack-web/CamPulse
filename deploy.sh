#!/bin/bash
set -e

echo "=== Vylix Contabo VPS Deployment ==="

# Update system
echo "[1/6] Updating system..."
sudo apt update && sudo apt upgrade -y

# Install Docker
echo "[2/6] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
    echo "Docker installed. You may need to log out and back in."
fi

# Install Docker Compose
echo "[3/6] Installing Docker Compose..."
if ! command -v docker compose &> /dev/null; then
    sudo apt install -y docker-compose-plugin
fi

# Clone repo
echo "[4/6] Cloning repository..."
if [ ! -d "/opt/vylix" ]; then
    sudo git clone https://github.com/ayostackdev/Vylix.git /opt/vylix
    sudo chown -R $USER:$USER /opt/vylix
else
    cd /opt/vylix && git pull
fi

cd /opt/vylix

# Create .env.production if it doesn't exist
echo "[5/6] Setting up environment..."
if [ ! -f ".env.production" ]; then
    cp .env.production.example .env.production
    echo ">>> Edit /opt/vylix/.env.production with your production values <<<"
    echo ">>> Then run: docker compose -f docker-compose.prod.yml up -d <<<"
    exit 0
fi

# Deploy
echo "[6/6] Starting services..."
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "=== Deployment Complete ==="
echo "API: https://api.vylix.app"
echo "Docs: https://api.vylix.app/docs"
echo ""
echo "View logs: docker compose -f docker-compose.prod.yml logs -f"
echo "Restart: docker compose -f docker-compose.prod.yml restart"
