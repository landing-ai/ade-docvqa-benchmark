#!/bin/bash

# GitHub Repository Force Push Script
# This will WIPE the remote repository and upload the clean local version

echo "========================================"
echo "GitHub Force Push - Repository Wipe"
echo "========================================"
echo ""

# Check if remote exists
if git remote | grep -q "origin"; then
    echo "✓ Remote 'origin' already configured"
    REMOTE_URL=$(git remote get-url origin)
    echo "  URL: $REMOTE_URL"
else
    echo "⚠️  Remote 'origin' not configured"
    echo ""
    echo "Please provide your GitHub repository URL:"
    echo "Format: https://github.com/USERNAME/REPO.git"
    echo "   or: git@github.com:USERNAME/REPO.git"
    echo ""
    read -p "Repository URL: " REPO_URL

    if [ -z "$REPO_URL" ]; then
        echo "❌ No URL provided. Exiting."
        exit 1
    fi

    echo ""
    echo "Adding remote..."
    git remote add origin "$REPO_URL"
    echo "✓ Remote added"
fi

echo ""
echo "========================================"
echo "⚠️  WARNING: DESTRUCTIVE OPERATION"
echo "========================================"
echo "This will FORCE PUSH and WIPE all content"
echo "in the remote repository, replacing it with"
echo "the clean local version."
echo ""
echo "Local commit:"
git log -1 --oneline
echo ""
echo "Files to upload: 2,607 files (1.1 GB)"
echo "  ✓ 1,286 images"
echo "  ✓ 1,286 parsed JSONs"
echo "  ✓ Main files (README, gallery, evaluate.py, etc.)"
echo "  ✓ Extra materials"
echo ""

read -p "Continue with force push? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Aborted."
    exit 1
fi

echo ""
echo "Pushing to GitHub..."
echo ""

git push -u origin main --force

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "✅ SUCCESS!"
    echo "========================================"
    echo "Repository has been wiped and uploaded"
    echo ""
    git remote get-url origin
    echo ""
else
    echo ""
    echo "========================================"
    echo "❌ PUSH FAILED"
    echo "========================================"
    echo "Please check:"
    echo "  1. Repository URL is correct"
    echo "  2. You have push access"
    echo "  3. Authentication is configured"
    echo ""
fi
