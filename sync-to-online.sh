#!/usr/bin/env bash
set -e

SRC_DIR="/media/sfiso/USB STICK/Projects/ai-agent"
DEST_DIR="/home/sfiso/andromeda-runtime"

echo "======================================================="
echo "   🌌 Syncing USB Development to 24/7 Online Runtime"
echo "======================================================="

if [ ! -d "$SRC_DIR" ]; then
    echo "❌ Error: USB drive not detected at $SRC_DIR."
    echo "   Ensure your USB stick is plugged in."
    exit 1
fi

echo "📦 1. Syncing backend and frontend code to internal SSD..."
rsync -av --exclude='node_modules' --exclude='.git' --exclude='jimmy_env' \
  --exclude='__pycache__' --exclude='data/tunnel' --exclude='public_url.txt' \
  "$SRC_DIR/" "$DEST_DIR/"

echo "🚀 2. Performing zero-downtime rolling build of backend and frontend..."
docker compose -f "$DEST_DIR/docker-compose.yml" up -d --build --no-deps andromeda-backend andromeda-frontend

echo "✅ 3. Sync and reload complete! GPU models and traces preserved."
"$DEST_DIR/get-url.sh"
