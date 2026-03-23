#!/bin/bash
# ============================================================
#  Cloud Sync — Platinum Tier
#  Vault Git Sync between Oracle Cloud VM and Local Machine
# ============================================================
#
#  Runs every 30 seconds on the Oracle Cloud VM.
#  Pulls latest from remote (local machine pushes changes),
#  then pushes cloud agent output back.
#
#  Safety rules:
#    - NEVER syncs .env or any file with credentials
#    - NEVER force-pushes to main
#    - Creates a SIGNAL if sync fails 3 times in a row
#    - Logs every sync operation to Logs/sync_YYYY-MM-DD.json
#
#  Usage:
#    chmod +x cloud_sync.sh
#    ./cloud_sync.sh              # Single sync
#    ./cloud_sync.sh --loop       # Continuous (30s interval)
#    ./cloud_sync.sh --loop 60    # Custom interval (seconds)
#    ./cloud_sync.sh --status     # Show sync status only
#
#  Install as systemd service: see cloud_setup.sh
# ============================================================

set -e

# ── Config ────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_DIR="$SCRIPT_DIR/AI_Employee_Vault"
LOG_DIR="$VAULT_DIR/Logs"
SIGNALS_DIR="$VAULT_DIR/Signals"
INTERVAL=30
MAX_FAILURES=3

# Track consecutive failures
FAIL_COUNT=0

# ── Helpers ───────────────────────────────────────────────────

log_event() {
    local event="$1"
    local details="$2"
    local success="${3:-true}"

    mkdir -p "$LOG_DIR"
    local today
    today=$(date +%Y-%m-%d)
    local log_file="$LOG_DIR/sync_$today.json"
    local timestamp
    timestamp=$(date -Iseconds)

    # Read existing entries
    local entries="[]"
    if [ -f "$log_file" ]; then
        entries=$(cat "$log_file" 2>/dev/null || echo "[]")
    fi

    # Append new entry (using python for valid JSON)
    python3 -c "
import json, sys
entries = json.loads(sys.argv[1])
entries.append({
    'event': sys.argv[2],
    'details': sys.argv[3],
    'success': sys.argv[4] == 'true',
    'timestamp': sys.argv[5],
})
print(json.dumps(entries, indent=2, ensure_ascii=False))
" "$entries" "$event" "$details" "$success" "$timestamp" > "$log_file.tmp" \
    && mv "$log_file.tmp" "$log_file" 2>/dev/null || true
}

write_signal() {
    local signal_type="$1"
    local message="$2"

    mkdir -p "$SIGNALS_DIR"
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local ts_iso
    ts_iso=$(date -Iseconds)
    local filename="SIGNAL_${timestamp}_${signal_type}.json"

    python3 -c "
import json
data = {
    'type': '$signal_type',
    'message': '''$message''',
    'agent': 'cloud_sync',
    'timestamp': '$ts_iso',
}
print(json.dumps(data, indent=2))
" > "$SIGNALS_DIR/$filename"
    echo "  [Sync] Signal written: $filename"
}

check_gitignore() {
    # Ensure .env is in .gitignore so we never accidentally commit credentials
    local gitignore="$SCRIPT_DIR/.gitignore"
    local must_ignore=(".env" "*.env" "__pycache__" "*.pyc" "*.pem" "*.key" "*_credentials*" "*token*")

    if [ ! -f "$gitignore" ]; then
        touch "$gitignore"
    fi

    for pattern in "${must_ignore[@]}"; do
        if ! grep -qF "$pattern" "$gitignore" 2>/dev/null; then
            echo "$pattern" >> "$gitignore"
            echo "  [Sync] Added to .gitignore: $pattern"
        fi
    done
}

# ── Sync Logic ────────────────────────────────────────────────

do_sync() {
    cd "$SCRIPT_DIR" || return 1

    # Safety: ensure credentials never sync
    check_gitignore

    # 1. Stage only safe files (never .env, never tokens)
    git add \
        AI_Employee_Vault/Inbox/ \
        AI_Employee_Vault/Needs_Action/ \
        AI_Employee_Vault/In_Progress/ \
        AI_Employee_Vault/Plans/ \
        AI_Employee_Vault/Pending_Approval/ \
        AI_Employee_Vault/Approved/ \
        AI_Employee_Vault/Done/ \
        AI_Employee_Vault/Rejected/ \
        AI_Employee_Vault/Updates/ \
        AI_Employee_Vault/Signals/ \
        AI_Employee_Vault/Logs/ \
        AI_Employee_Vault/Briefings/ \
        2>/dev/null || true

    # 2. Pull latest changes from remote
    local pull_output
    pull_output=$(git pull --rebase origin main 2>&1)
    local pull_exit=$?

    if [ $pull_exit -ne 0 ]; then
        echo "  [Sync] Pull failed: $pull_output"
        log_event "PULL_FAILED" "$pull_output" "false"
        return 1
    fi

    # 3. Commit and push if there are new cloud outputs
    local status_output
    status_output=$(git status --short 2>/dev/null | grep -v "^\?\?" | head -20)

    if [ -n "$status_output" ]; then
        local timestamp
        timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        git commit -m "Cloud agent sync: $timestamp [skip ci]" \
            --author="AI Employee Cloud <cloud@ai-employee.local>" \
            2>/dev/null || true

        git push origin main 2>/dev/null
        local push_exit=$?

        if [ $push_exit -ne 0 ]; then
            echo "  [Sync] Push failed"
            log_event "PUSH_FAILED" "exit=$push_exit" "false"
            return 1
        fi

        echo "  [Sync] Pushed cloud updates at $timestamp"
        log_event "SYNC_PUSHED" "files changed" "true"
    else
        echo "  [Sync] Nothing to push — vault up to date"
        log_event "SYNC_NOOP" "no changes" "true"
    fi

    return 0
}

show_status() {
    cd "$SCRIPT_DIR" || return

    echo "============================================================"
    echo "  CLOUD SYNC STATUS"
    echo "============================================================"
    echo "  Script dir: $SCRIPT_DIR"
    echo "  Vault dir:  $VAULT_DIR"
    echo ""

    # Git remote
    local remote
    remote=$(git remote get-url origin 2>/dev/null || echo "(not configured)")
    echo "  Remote: $remote"

    # Last commit
    local last_commit
    last_commit=$(git log --oneline -1 2>/dev/null || echo "(no commits)")
    echo "  Last commit: $last_commit"

    # Untracked / modified
    local changed
    changed=$(git status --short 2>/dev/null | wc -l)
    echo "  Pending changes: $changed file(s)"

    # .gitignore check
    if grep -q "\.env" .gitignore 2>/dev/null; then
        echo "  .gitignore: .env protected [OK]"
    else
        echo "  .gitignore: WARNING — .env not in .gitignore!"
    fi

    echo "============================================================"
}

# ── Main ──────────────────────────────────────────────────────

case "${1:-}" in
    --status)
        show_status
        exit 0
        ;;

    --loop)
        INTERVAL="${2:-30}"
        echo "============================================================"
        echo "  CLOUD SYNC — Continuous Mode"
        echo "  Interval: ${INTERVAL}s"
        echo "  Vault:    $VAULT_DIR"
        echo "  Press Ctrl+C to stop"
        echo "============================================================"

        log_event "SYNC_START" "interval=${INTERVAL}s"

        while true; do
            echo ""
            echo "  [$(date '+%H:%M:%S')] Syncing vault..."

            if do_sync; then
                FAIL_COUNT=0
            else
                FAIL_COUNT=$((FAIL_COUNT + 1))
                echo "  [Sync] Failure count: $FAIL_COUNT / $MAX_FAILURES"

                if [ "$FAIL_COUNT" -ge "$MAX_FAILURES" ]; then
                    write_signal "SYNC_FAILED" "Vault sync failed $FAIL_COUNT times in a row. Manual intervention required."
                    FAIL_COUNT=0  # Reset to avoid signal spam
                fi
            fi

            echo "  Next sync in ${INTERVAL}s..."
            sleep "$INTERVAL"
        done
        ;;

    *)
        # Single sync
        echo "  [Cloud Sync] Single sync..."
        do_sync && echo "  [Cloud Sync] Done." || echo "  [Cloud Sync] Sync failed."
        ;;
esac
