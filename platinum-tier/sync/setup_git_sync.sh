#!/bin/bash
# setup_git_sync.sh — Initialize Git-based Vault Sync (Platinum Tier)
# =====================================================================
# Run ONCE on both local machine and cloud VM to set up vault sync.
#
# Usage:
#   chmod +x sync/setup_git_sync.sh
#   ./sync/setup_git_sync.sh
#
# Prerequisites:
#   - GitHub/GitLab repo created (private)
#   - SSH key configured on both machines

set -euo pipefail

VAULT_PATH="${VAULT_PATH:-$(dirname "$(dirname "$(realpath "$0")")")}"
REPO_URL="${VAULT_REPO_URL:-}"

echo "=========================================="
echo "  AI Employee Vault Git Sync Setup"
echo "  Vault: $VAULT_PATH"
echo "=========================================="

if [ -z "$REPO_URL" ]; then
    echo "ERROR: Set VAULT_REPO_URL environment variable first."
    echo "  export VAULT_REPO_URL=git@github.com:youruser/your-vault.git"
    exit 1
fi

cd "$VAULT_PATH"

# Initialize git if not already
if [ ! -d ".git" ]; then
    git init
    echo "Git repository initialized."
fi

# Create .gitignore to exclude secrets
cat > .gitignore << 'GITIGNORE'
# AI Employee — Never sync these files
.env
.env.*
*.key
*.pem
*.p12
credentials.json
token.json
session/
whatsapp_session/
*.pid
__pycache__/
*.pyc
node_modules/
.DS_Store
Thumbs.db
GITIGNORE

echo ".gitignore created."

# Create .gitignore_secrets (secondary safety net)
cat > .gitignore_secrets << 'SECRETS'
# Absolute safety — credentials never leave local machine
.env*
*credentials*
*token*
*session*
*.key
*.pem
SECRETS

# Set up remote
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"
echo "Remote set: $REPO_URL"

# Initial commit
git add .
git commit -m "chore: initial vault setup — $(date '+%Y-%m-%d')" || true

# Set branch and push
git branch -M main
git push -u origin main || git push --set-upstream origin main

echo ""
echo "✓ Vault sync initialized!"
echo ""
echo "Next steps:"
echo "  1. Clone this repo on your cloud VM"
echo "  2. Set VAULT_PATH and VAULT_REPO_URL on the VM"
echo "  3. Add cloud_sync.sh to crontab: */5 * * * * /app/cloud/cloud_sync.sh"
echo "  4. Run local_agent.py on your local machine"
echo ""
echo "Security reminder: .env and credentials are in .gitignore — NEVER commit them."
