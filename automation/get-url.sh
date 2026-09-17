#!/usr/bin/env bash
set -e

RUNTIME_DIR="/home/sfiso/andromeda-runtime"
TUNNEL_FILE="$RUNTIME_DIR/public_url.txt"
USB_FILE="/media/sfiso/USB STICK/Projects/ai-agent/public_url.txt"

echo "======================================================="
echo "   🌌 Andromeda 24/7 Automated URL Fetcher"
echo "======================================================="

URL=""
if [ -s "$TUNNEL_FILE" ]; then
    URL=$(cat "$TUNNEL_FILE" | tr -d ' \n\r')
fi

if [ -z "$URL" ] || [ "$URL" = "null" ]; then
    URL=$(docker logs cloudflared 2>&1 | grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' | tail -n 1)
    if [ -n "$URL" ]; then
        echo "$URL" > "$TUNNEL_FILE"
    fi
fi

if [ -n "$URL" ]; then
    if [ -d "/media/sfiso/USB STICK/Projects/ai-agent" ]; then
        echo "$URL" > "$USB_FILE" 2>/dev/null || true
    fi
    echo "🟢 Status: 24/7 Online"
    echo "🔗 Public HTTPS URL: $URL"
    echo "📍 Local Ingress:    http://localhost:80"
    echo "📊 Phoenix Tracing:  http://localhost:6006"
    echo "======================================================="
else
    echo "🟡 Status: Tunnel is initializing. Please re-run in 5 seconds."
    echo "======================================================="
fi
