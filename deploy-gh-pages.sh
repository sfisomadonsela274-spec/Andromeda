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
    EXISTING_REMOTE=$(git remote get-url origin 2>/dev/null || true)
    if [ -n "$EXISTING_REMOTE" ]; then
        REPO_URL="$EXISTING_REMOTE"
    else
        REPO_URL="$DEFAULT_REPO"
    fi
fi

echo "📦 Target Repository: $REPO_URL"
echo "🌐 Native URL:        https://sfisomadonsela274-spec.github.io/Andromeda/"
echo ""

# Build latest frontend distribution
echo "🔨 Building latest frontend distribution with Vite..."
(cd andromeda && npm run build)

# Deploy dist folder to gh-pages branch
TEMP_DIR=$(mktemp -d)
echo "📁 Staging distribution files in $TEMP_DIR..."
cp -r andromeda/dist/* "$TEMP_DIR/"
[ -f public_url.txt ] && cp public_url.txt "$TEMP_DIR/public_url.txt"
rm -f "$TEMP_DIR/CNAME"

cd "$TEMP_DIR"
git init -b gh-pages
git config user.name "sfisomadonsela274-spec"
git config user.email "sfisomadonsela274@gmail.com"
git add -A
git commit -m "Deploy Andromeda Intelligent Workspace (sfisomadonsela274-spec.github.io/Andromeda)"

echo "🚀 Pushing directly to gh-pages branch on GitHub..."
git push --force "$REPO_URL" gh-pages:gh-pages

rm -rf "$TEMP_DIR"
echo ""
echo "======================================================="
echo "✅ Successfully deployed to GitHub Pages (gh-pages)!"
echo "🌐 Live Site: https://sfisomadonsela274-spec.github.io/Andromeda/"
echo "======================================================="
