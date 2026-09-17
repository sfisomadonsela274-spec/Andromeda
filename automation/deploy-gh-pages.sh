#!/usr/bin/env bash
set -e

REPO_URL="$1"
DEFAULT_REPO="https://github.com/sfisomadonsela274-spec/Andromeda.git"

echo "======================================================="
echo "   🌌 Andromeda GitHub Pages Deployment"
echo "======================================================="

# Ensure clean state without CNAME for native github.io hosting
rm -f andromeda/dist/CNAME
rm -f andromeda/CNAME

if [ -z "$REPO_URL" ]; then
    if [ -d ".git" ]; then
        REPO_URL=$(git remote get-url origin 2>/dev/null || true)
    elif [ -d "/media/sfiso/USB STICK/Projects/ai-agent/.git" ]; then
        REPO_URL=$(git -C "/media/sfiso/USB STICK/Projects/ai-agent" remote get-url origin 2>/dev/null || true)
    fi
    if [ -z "$REPO_URL" ]; then
        REPO_URL="$DEFAULT_REPO"
    fi
fi

# Mask PAT token in display for safety
DISPLAY_REPO=$(echo "$REPO_URL" | sed -E 's/:[^@]+@/:***@/')
echo "📦 Target Repository: $DISPLAY_REPO"
echo "🌐 Native URL:        https://sfisomadonsela274-spec.github.io/Andromeda/"
echo ""

# Build frontend if environment allows, otherwise use pre-built dist
if [ -x andromeda/node_modules/.bin/vite ] || command -v vite >/dev/null 2>&1; then
    echo "🔨 Building latest frontend distribution with Vite..."
    (cd andromeda && npm run build) || echo "⚠️ Warning: Vite build had warnings, proceeding with distribution."
elif [ -d "/media/sfiso/USB STICK/Projects/ai-agent/andromeda/dist" ] && [ ! -d "andromeda/dist" ]; then
    echo "📦 Copying pre-built dist from USB repository..."
    mkdir -p andromeda
    cp -r "/media/sfiso/USB STICK/Projects/ai-agent/andromeda/dist" andromeda/
fi

# Deploy dist folder to gh-pages branch
TEMP_DIR=$(mktemp -d)
echo "📁 Staging distribution files in $TEMP_DIR..."
cp -r andromeda/dist/* "$TEMP_DIR/"

# Read active tunnel URL
TUNNEL_URL=""
if [ -s public_url.txt ]; then
    TUNNEL_URL=$(tr -d ' \n\r' < public_url.txt)
elif [ -s /home/sfiso/andromeda-runtime/public_url.txt ]; then
    TUNNEL_URL=$(tr -d ' \n\r' < /home/sfiso/andromeda-runtime/public_url.txt)
elif [ -s "/media/sfiso/USB STICK/Projects/ai-agent/public_url.txt" ]; then
    TUNNEL_URL=$(tr -d ' \n\r' < "/media/sfiso/USB STICK/Projects/ai-agent/public_url.txt")
fi

if [ -n "$TUNNEL_URL" ]; then
    echo "🔗 Active Tunnel Endpoint: $TUNNEL_URL"
    echo "$TUNNEL_URL" > "$TEMP_DIR/public_url.txt"
    # Ensure staged HTML files embed the fresh URL directly
    sed -i -E "s|https://[a-zA-Z0-9-]+\.trycloudflare\.com|$TUNNEL_URL|g" "$TEMP_DIR/index.html" 2>/dev/null || true
    sed -i -E "s|https://[a-zA-Z0-9-]+\.trycloudflare\.com|$TUNNEL_URL|g" "$TEMP_DIR/landing.html" 2>/dev/null || true
fi

rm -f "$TEMP_DIR/CNAME"

cd "$TEMP_DIR"
git init -b gh-pages
git config user.name "sfisomadonsela274-spec"
git config user.email "sfisomadonsela274@gmail.com"
git add -A
git commit -m "Deploy Andromeda Intelligent Workspace (Edge: $TUNNEL_URL)"

echo "🚀 Pushing directly to gh-pages branch on GitHub..."
git push --force "$REPO_URL" gh-pages:gh-pages

rm -rf "$TEMP_DIR"
echo ""
echo "======================================================="
echo "✅ Successfully deployed to GitHub Pages (gh-pages)!"
echo "🌐 Live Site: https://sfisomadonsela274-spec.github.io/Andromeda/"
echo "======================================================="
