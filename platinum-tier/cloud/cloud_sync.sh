#!/bin/bash
# cloud_sync.sh — Git-based Vault Sync (Cloud Side)
# ==================================================
# Runs on cloud VM to sync the Obsidian vault via Git.
# Only syncs safe files — never credentials or secrets.
#
# Setup:
#   chmod +x cloud/cloud_sync.sh
#   Add to crontab: */5 * * * * /app/cloud/cloud_sync.sh >> /app/Logs/sync.log 2>&1

set -euo pipefail

VAULT_PATH="${VAULT_PATH:-$(dirname "$(dirname "$(realpath "$0")")")}"
GIT_REMOTE="${GIT_REMOTE:-origin}"
BRANCH="${GIT_BRANCH:-main}"
LOG_DATE=$(date +%Y-%m-%d)
LOG_FILE="$VAULT_PATH/Logs/sync_${LOG_DATE}.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [CLOUD-SYNC] $*" | tee -a "$LOG_FILE"
}

log "Starting vault sync..."

cd "$VAULT_PATH"

# Ensure git repo is initialized
if [ ! -d ".git" ]; then
    log "ERROR: Not a git repository: $VAULT_PATH"
    exit 1
fi

# Configure git to ignore secrets (safety net)
git config core.excludesFile .gitignore_secrets 2>/dev/null || true

# Pull latest changes from remote
if git pull --rebase "$GIT_REMOTE" "$BRANCH" 2>&1 | tee -a "$LOG_FILE"; then
    log "Pull successful."
else
    log "WARNING: Pull failed or had conflicts. Continuing..."
fi

# Stage only safe file types
git add \
    "*.md" \
    "Logs/*.json" \
    "Updates/" \
    "Needs_Action/**/*.md" \
    "Plans/**/*.md" \
    "Pending_Approval/*.md" \
    "Done/*.md" \
    "Briefings/*.md" \
    2>/dev/null || true

# Check if there's anything to commit
if ! git diff --cached --quiet; then
    COMMIT_MSG="sync: cloud agent update $(date '+%Y-%m-%d %H:%M')"
    git commit -m "$COMMIT_MSG" | tee -a "$LOG_FILE"
    git push "$GIT_REMOTE" "$BRANCH" | tee -a "$LOG_FILE"
    log "Pushed changes to remote."
else
    log "No changes to push."
fi

log "Vault sync complete."
