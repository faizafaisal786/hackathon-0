#!/usr/bin/env bash
# setup_git_sync.sh — One-time Git vault sync setup for Platinum Tier
# =====================================================================
# Run this ONCE on both local and cloud machines to configure vault sync.
#
# Usage:
#   chmod +x cloud/setup_git_sync.sh
#   ./cloud/setup_git_sync.sh <git-remote-url>
#
# Example:
#   ./cloud/setup_git_sync.sh git@github.com:yourname/ai-vault.git

set -euo pipefail

REMOTE="${1:-}"
VAULT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Platinum Tier: Vault Git Sync Setup ==="
echo "Vault: $VAULT_ROOT"

if [ -z "$REMOTE" ]; then
    echo "ERROR: No remote URL provided."
    echo "Usage: $0 <git-remote-url>"
    exit 1
fi

cd "$VAULT_ROOT"

# ── Initialize git if not already ────────────────────────────────────────────
if [ ! -d ".git" ]; then
    git init
    echo "Git repository initialized."
fi

# ── Create .gitignore ─────────────────────────────────────────────────────────
cat > .gitignore << 'EOF'
# Secrets — never commit these
.env
*.env
credentials.json
token.json
*.key
*.pem
*.pfx

# WhatsApp/Playwright sessions
sessions/
.playwright/

# Python cache
__pycache__/
*.pyc
*.pyo
.pytest_cache/

# Node
node_modules/

# OS
.DS_Store
Thumbs.db
desktop.ini

# Temporary files
*.tmp
*.part
*.crdownload
EOF

echo ".gitignore created."

# ── Configure remote ──────────────────────────────────────────────────────────
if git remote get-url origin &>/dev/null; then
    git remote set-url origin "$REMOTE"
    echo "Remote updated: $REMOTE"
else
    git remote add origin "$REMOTE"
    echo "Remote added: $REMOTE"
fi

# ── Initial commit ────────────────────────────────────────────────────────────
git add --all
git commit -m "chore: initial vault setup — Platinum Tier AI Employee" 2>/dev/null || echo "Nothing to commit."

# ── Set branch and push ───────────────────────────────────────────────────────
git branch -M main
git push -u origin main

echo ""
echo "=== Setup complete! ==="
echo "Both local and cloud agents can now sync via: git pull --rebase / git push"
echo ""
echo "Next steps:"
echo "  1. On cloud VM: git clone $REMOTE && pip install -r requirements.txt"
echo "  2. Copy .env to cloud VM and fill in secrets"
echo "  3. Run: python cloud/cloud_agent.py"
