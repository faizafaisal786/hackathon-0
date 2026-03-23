#!/bin/bash
# ============================================
# STEP 3: Cloud Git Sync (runs on Cloud VM)
# Auto-commits and pushes vault changes
# Pulls human approvals from local
# ============================================

VAULT_DIR="/home/ai-employee/vault"
SYNC_INTERVAL=30  # seconds

echo "╔═══════════════════════════════════════╗"
echo "║   GIT SYNC SERVICE — Cloud VM        ║"
echo "║   Interval: ${SYNC_INTERVAL}s                     ║"
echo "╚═══════════════════════════════════════╝"

cd "$VAULT_DIR"

sync_vault() {
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    # Pull latest changes (human approvals from local)
    git pull --rebase origin main 2>/dev/null

    # Check for local changes
    if [ -n "$(git status --porcelain)" ]; then
        git add -A
        git commit -m "AI Employee auto-sync: $TIMESTAMP"
        git push origin main

        echo "[$TIMESTAMP] SYNCED — changes pushed"
    else
        echo "[$TIMESTAMP] No changes"
    fi
}

# Main loop
while true; do
    sync_vault
    sleep $SYNC_INTERVAL
done
