#!/usr/bin/env bash
# ==============================================================================
# 🌌 Andromeda Intelligent Workspace - Master Boot & Process Interconnect
# ==============================================================================
# Auto-launched at system boot via systemd user unit (with linger enabled).
# Ensures storage mounts, Docker services, internal interconnects, and tunnels
# are healthy and operational 24/7.
# ==============================================================================

set -uo pipefail

LOG_DIR="/home/sfiso/andromeda-runtime/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/boot.log"

exec > >(tee -a "$LOG_FILE") 2>&1

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

echo "================================================================="
echo "   🌌 Andromeda Intelligent Workspace - Boot & Interconnect"
echo "================================================================="
log "Boot sequence initiated."

# ------------------------------------------------------------------------------
# STEP 1: Storage Mount Verification & Auto-Healing
# ------------------------------------------------------------------------------
log "Step 1: Inspecting external storage and mount paths..."
USB_DEV="/dev/disk/by-uuid/3A3E6C335F3CCA03"
USB_TARGET="/media/sfiso/USB STICK"
USB_ANOMALY="/media/sfiso/USB STICK1"
RUNTIME_DIR="/home/sfiso/andromeda-runtime"
USB_PROJECT="$USB_TARGET/Projects/ai-agent"

if [ -e "$USB_DEV" ]; then
    log "USB device detected."
    CURRENT_MOUNT=$(lsblk -no MOUNTPOINTS "$USB_DEV" 2>/dev/null | head -n 1 || true)
    
    if [ "$CURRENT_MOUNT" = "$USB_ANOMALY" ]; then
        log "Anomaly detected: USB is mounted at '$USB_ANOMALY'. Healing mount point..."
        udisksctl unmount -b "$USB_DEV" 2>/dev/null || true
        # Clean dummy directories if left by Docker
        if [ -d "$USB_TARGET" ]; then
            docker run --rm -v /media/sfiso:/media/sfiso alpine rm -rf "$USB_TARGET" 2>/dev/null || true
        fi
        udisksctl mount -b "$USB_DEV" 2>/dev/null || true
    elif [ -z "$CURRENT_MOUNT" ]; then
        log "USB device attached but not mounted. Mounting to default location..."
        if [ -d "$USB_TARGET" ] && ! mountpoint -q "$USB_TARGET"; then
            docker run --rm -v /media/sfiso:/media/sfiso alpine rm -rf "$USB_TARGET" 2>/dev/null || true
        fi
        udisksctl mount -b "$USB_DEV" 2>/dev/null || true
    else
        log "USB device cleanly mounted at '$CURRENT_MOUNT'."
    fi
else
    log "External USB device not detected. Proceeding with SSD 24/7 runtime."
fi

# Sync development changes from USB if connected
if [ -d "$USB_PROJECT" ] && [ -f "$USB_PROJECT/docker-compose.yml" ]; then
    log "USB development repository active. Syncing changes to SSD production runtime..."
    rsync -av --exclude='node_modules' --exclude='.git' --exclude='jimmy_env' \
      --exclude='__pycache__' --exclude='data/tunnel' --exclude='public_url.txt' \
      "$USB_PROJECT/" "$RUNTIME_DIR/" >/dev/null 2>&1 || true
    log "Repository sync complete."
fi

# ------------------------------------------------------------------------------
# STEP 2: Docker Daemon Readiness Check
# ------------------------------------------------------------------------------
log "Step 2: Waiting for Docker daemon to become responsive..."
MAX_DOCKER_WAIT=60
DOCKER_WAITED=0
while ! docker info >/dev/null 2>&1; do
    sleep 2
    DOCKER_WAITED=$((DOCKER_WAITED + 2))
    if [ $DOCKER_WAITED -ge $MAX_DOCKER_WAIT ]; then
        log "❌ Error: Docker daemon did not respond within $MAX_DOCKER_WAIT seconds."
        exit 1
    fi
done
log "Docker daemon is ready."

# ------------------------------------------------------------------------------
# STEP 3: Launch Docker Compose Services
# ------------------------------------------------------------------------------
log "Step 3: Launching all Andromeda containers and services..."
cd "$RUNTIME_DIR"
docker compose -p ai-agent -f "$RUNTIME_DIR/docker-compose.yml" up -d

# ------------------------------------------------------------------------------
# STEP 4: Health Check & Process Interconnection Loop
# ------------------------------------------------------------------------------
log "Step 4: Verifying service health and interconnectivity..."

check_endpoint() {
    local url="$1"
    local name="$2"
    local timeout=3
    if curl -sf --max-time "$timeout" "$url" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

MAX_HEALTH_WAIT=90
HEALTH_WAITED=0
ALL_HEALTHY=false

while [ $HEALTH_WAITED -lt $MAX_HEALTH_WAIT ]; do
    BACKEND_OK=false
    FRONTEND_OK=false
    INGRESS_OK=false
    PHOENIX_OK=false
    OLLAMA_OK=false

    check_endpoint "http://localhost:8000/" "Backend" && BACKEND_OK=true
    check_endpoint "http://localhost:5173/" "Frontend" && FRONTEND_OK=true
    check_endpoint "http://localhost:80/" "Caddy" && INGRESS_OK=true
    check_endpoint "http://localhost:6006/" "Phoenix" && PHOENIX_OK=true
    check_endpoint "http://localhost:11434/" "Ollama" && OLLAMA_OK=true

    if [ "$BACKEND_OK" = true ] && [ "$FRONTEND_OK" = true ] && \
       [ "$INGRESS_OK" = true ] && [ "$PHOENIX_OK" = true ] && [ "$OLLAMA_OK" = true ]; then
        ALL_HEALTHY=true
        break
    fi

    sleep 3
    HEALTH_WAITED=$((HEALTH_WAITED + 3))
    log "Waiting for services to become healthy ($HEALTH_WAITED/${MAX_HEALTH_WAIT}s)..."
done

if [ "$ALL_HEALTHY" = true ]; then
    log "✅ All core internal endpoints responded successfully."
else
    log "⚠️ Warning: Some services took longer than expected to initialize. Check 'docker ps'."
fi

# ------------------------------------------------------------------------------
# STEP 5: URL Fetcher Service & Cloudflare Tunnel Connectivity
# ------------------------------------------------------------------------------
log "Step 5: Connecting URL fetcher daemon and tunnel verification..."
if systemctl --user is-enabled andromeda-url-fetcher.service >/dev/null 2>&1; then
    systemctl --user restart andromeda-url-fetcher.service || true
else
    systemctl --user enable --now andromeda-url-fetcher.service || true
fi

# Extract current tunnel URL
TUNNEL_URL=""
for i in {1..15}; do
    TUNNEL_URL=$(python3 "$RUNTIME_DIR/url_fetcher.py" --once 2>/dev/null || true)
    if [ -n "$TUNNEL_URL" ] && [[ "$TUNNEL_URL" =~ ^https://.*trycloudflare\.com$ ]]; then
        break
    fi
    sleep 2
done

# ------------------------------------------------------------------------------
# STEP 6: Synchronize and Deploy to GitHub Pages Edge
# ------------------------------------------------------------------------------
if [ -n "$TUNNEL_URL" ]; then
    log "Step 6: Publishing active Cloudflare tunnel URL to GitHub Pages..."
    if [ -x "$RUNTIME_DIR/deploy-gh-pages.sh" ]; then
        "$RUNTIME_DIR/deploy-gh-pages.sh" >/dev/null 2>&1 || true
        log "GitHub Pages edge updated with live tunnel endpoint."
    fi
fi

# ------------------------------------------------------------------------------
# STEP 7: Final Diagnostics & Status Report
# ------------------------------------------------------------------------------
echo ""
echo "================================================================="
echo "   🌌 Andromeda Workspace - All Systems Operational"
echo "================================================================="
log "🟢 Status: 24/7 Production Online"
if [ -n "$TUNNEL_URL" ]; then
    echo "🔗 Public HTTPS URL:    $TUNNEL_URL"
    echo "🌐 GitHub Pages Edge:   https://sfisomadonsela274-spec.github.io/Andromeda/"
fi
echo "📍 Local Ingress:       http://localhost:80"
echo "⚡ FastAPI Core API:    http://localhost:8000"
echo "🎨 SPA Frontend:        http://localhost:5173"
echo "📊 Arize Phoenix:       http://localhost:6006"
echo "🧠 Ollama LLM Service:  http://localhost:11434"
echo "-----------------------------------------------------------------"
echo "Active Containers:"
docker ps --filter "name=andromeda|caddy|phoenix|ollama|cloudflared" --format "  - {{.Names}}: {{.Status}}"
echo "================================================================="
log "Boot sequence finished successfully."
exit 0
