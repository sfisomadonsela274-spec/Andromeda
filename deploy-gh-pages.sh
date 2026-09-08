#!/usr/bin/env bash
set -e

REPO_URL="$1"
DEFAULT_REPO="https://github.com/sfisomadonsela274-spec/andromeda.git"

echo "======================================================="
echo "   🌌 Andromeda GitHub Pages Deployment (Andromeda.sfi.so)"
echo "======================================================="

# Ensure dist has CNAME
echo "Andromeda.sfi.so" > andromeda/dist/CNAME
echo "Andromeda.sfi.so" > andromeda/CNAME

if [ -z "$REPO_URL" ]; then
    # Check if remote origin exists
    EXISTING_REMOTE=$(git remote get-url origin 2>/dev/null || true)
    if [ -n "$EXISTING_REMOTE" ]; then
        REPO_URL="$EXISTING_REMOTE"
    else
        REPO_URL="$DEFAULT_REPO"
    fi
fi

echo "📦 Target Repository: $REPO_URL"
echo "🌐 Custom Domain:     Andromeda.sfi.so"
echo ""

# Deploy dist folder to gh-pages branch
TEMP_DIR=$(mktemp -d)
echo "📁 Staging distribution files in $TEMP_DIR..."
cp -r andromeda/dist/* "$TEMP_DIR/"

cd "$TEMP_DIR"
git init -b gh-pages
git config user.name "sfisomadonsela274-spec"
git config user.email "sfisomadonsela274@gmail.com"
git add -A
git commit -m "Deploy Andromeda Intelligent Workspace (Andromeda.sfi.so)"

echo "🚀 Pushing directly to gh-pages branch on GitHub..."
git push --force "$REPO_URL" gh-pages:gh-pages

rm -rf "$TEMP_DIR"
echo ""
echo "======================================================="
echo "✅ Successfully deployed to GitHub Pages (gh-pages)!"
echo "🌐 Live Site: https://Andromeda.sfi.so"
echo "======================================================="
