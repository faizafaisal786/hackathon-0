#!/bin/bash
# ============================================
# STEP 1: Initialize Git Repo for Vault Sync
# Run this ONCE on your local machine
# ============================================

VAULT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$VAULT_DIR"

# Initialize git
git init

# Create .gitignore
cat > .gitignore << 'GITIGNORE'
# Obsidian internal
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/cache

# System files
.DS_Store
Thumbs.db
desktop.ini
nul

# Sensitive
credentials.json
gmail_token.pickle
*.pickle
.env

# Node
node_modules/
GITIGNORE

# Initial commit
git add -A
git commit -m "Initial vault setup for AI Employee System"

echo ""
echo "================================================"
echo "  Git repo initialized!"
echo "  Now create a PRIVATE repo on GitHub and run:"
echo ""
echo "  git remote add origin git@github.com:YOUR_USER/ai-employee-vault.git"
echo "  git push -u origin main"
echo "================================================"
