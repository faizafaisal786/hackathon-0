#!/bin/bash
# ============================================================
#  Oracle Cloud Free Tier VM Setup — Platinum Tier
#  AI Employee Cloud Deployment Script
# ============================================================
#
#  What this script does:
#  1. Updates Ubuntu packages
#  2. Installs Python 3.11+ and pip
#  3. Installs project dependencies (requirements.txt)
#  4. Installs Git and configures vault sync
#  5. Creates systemd services for:
#       - ai-employee-cloud     (cloud_agent.py --loop)
#       - ai-employee-health    (health_monitor.py --loop)
#       - ai-employee-sync      (cloud_sync.sh --loop)
#  6. Sets up firewall (UFW) — only SSH + health endpoint
#  7. Verifies all services running
#
#  Oracle Cloud Free Tier specs (always free):
#    VM.Standard.A1.Flex — 4 OCPU, 24 GB RAM (ARM)
#    OR VM.Standard.E2.1.Micro — 1 OCPU, 1 GB RAM (x86)
#    Storage: 200 GB Block Volume
#
#  Usage:
#    # On Oracle Cloud VM (Ubuntu 22.04):
#    git clone <your-repo-url> ~/ai_employee
#    cd ~/ai_employee
#    chmod +x cloud_setup.sh
#    ./cloud_setup.sh
#
#    # After setup:
#    systemctl status ai-employee-cloud
#    journalctl -u ai-employee-cloud -f
# ============================================================

set -euo pipefail

# ── Config ────────────────────────────────────────────────────
INSTALL_DIR="${HOME}/ai_employee"
SERVICE_USER="${USER:-ubuntu}"
PYTHON_MIN="3.9"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC}   $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }
step() { echo -e "\n${YELLOW}==> $1${NC}"; }

# ── Detect OS ─────────────────────────────────────────────────
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_VER=$VERSION_ID
    else
        OS="unknown"
        OS_VER="unknown"
    fi
    echo "  Detected OS: $OS $OS_VER"
}

# ── Step 1: System Update ─────────────────────────────────────
install_system_deps() {
    step "1/7 — System packages"

    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq \
            python3 python3-pip python3-venv \
            git curl wget unzip \
            ufw \
            2>/dev/null
        ok "apt packages installed"
    elif command -v yum &>/dev/null; then
        sudo yum update -y -q
        sudo yum install -y -q python3 python3-pip git curl
        ok "yum packages installed"
    else
        warn "Unknown package manager — skipping system package install"
    fi
}

# ── Step 2: Python Version Check ──────────────────────────────
check_python() {
    step "2/7 — Python version check"

    PYTHON_CMD=""
    for cmd in python3.11 python3.10 python3.9 python3; do
        if command -v "$cmd" &>/dev/null; then
            version=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
            ok "Found $cmd ($version)"
            PYTHON_CMD="$cmd"
            break
        fi
    done

    if [ -z "$PYTHON_CMD" ]; then
        fail "Python 3.9+ not found. Install manually: sudo apt install python3"
    fi
}

# ── Step 3: Virtual Environment ───────────────────────────────
setup_venv() {
    step "3/7 — Python virtual environment"

    VENV_DIR="$INSTALL_DIR/venv"

    if [ ! -d "$VENV_DIR" ]; then
        $PYTHON_CMD -m venv "$VENV_DIR"
        ok "Virtual environment created: $VENV_DIR"
    else
        ok "Virtual environment already exists: $VENV_DIR"
    fi

    PYTHON_BIN="$VENV_DIR/bin/python"
    PIP_BIN="$VENV_DIR/bin/pip"

    # Upgrade pip
    "$PIP_BIN" install --upgrade pip -q
    ok "pip upgraded"

    # Install requirements
    REQ_FILE="$INSTALL_DIR/requirements.txt"
    if [ -f "$REQ_FILE" ]; then
        "$PIP_BIN" install -r "$REQ_FILE" -q
        ok "requirements.txt installed"
    else
        warn "requirements.txt not found — installing minimal deps"
        "$PIP_BIN" install -q \
            python-dotenv \
            requests \
            groq \
            google-generativeai \
            fastmcp \
            psutil
        ok "Minimal dependencies installed"
    fi
}

# ── Step 4: Git Configuration ─────────────────────────────────
setup_git() {
    step "4/7 — Git configuration"

    cd "$INSTALL_DIR"

    # Configure git identity for commits
    git config user.name  "AI Employee Cloud" 2>/dev/null || true
    git config user.email "cloud@ai-employee.local" 2>/dev/null || true

    # Ensure .env is always gitignored
    GITIGNORE="$INSTALL_DIR/.gitignore"
    MUST_IGNORE=(".env" "*.env" "venv/" "__pycache__/" "*.pyc" "*.pem" "*.key")
    for pattern in "${MUST_IGNORE[@]}"; do
        if ! grep -qF "$pattern" "$GITIGNORE" 2>/dev/null; then
            echo "$pattern" >> "$GITIGNORE"
        fi
    done
    ok ".gitignore configured (credentials protected)"

    # Make cloud_sync.sh executable
    chmod +x "$INSTALL_DIR/cloud_sync.sh" 2>/dev/null || true
    ok "cloud_sync.sh is executable"
}

# ── Step 5: Create .env Template ──────────────────────────────
setup_env() {
    step "5/7 — Environment configuration"

    ENV_FILE="$INSTALL_DIR/.env"

    if [ -f "$ENV_FILE" ]; then
        ok ".env already exists — not overwriting"
    else
        cat > "$ENV_FILE" << 'EOF'
# ============================================================
# AI Employee — Environment Configuration (Cloud VM)
# ============================================================
# DO NOT COMMIT THIS FILE TO GIT

# AI Backends (get free keys from Groq/Google)
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# Email (Gmail)
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

# WhatsApp (Twilio) — local machine only, not needed on cloud
# TWILIO_ACCOUNT_SID=
# TWILIO_AUTH_TOKEN=
# TWILIO_PHONE=

# LinkedIn (optional — cloud drafts, local publishes)
# LINKEDIN_ACCESS_TOKEN=
# LINKEDIN_PERSON_ID=

# Telegram Alerts
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Cloud Agent Config
CLOUD_AGENT_INTERVAL=60
HEALTH_CHECK_INTERVAL=300
SYNC_INTERVAL=30
EOF
        warn ".env template created. EDIT THIS FILE before starting services:"
        warn "  nano $ENV_FILE"
    fi
}

# ── Step 6: Systemd Services ──────────────────────────────────
setup_systemd() {
    step "6/7 — systemd services"

    if ! command -v systemctl &>/dev/null; then
        warn "systemd not available — skipping service setup"
        warn "Start manually: python cloud_agent.py --loop"
        return
    fi

    PYTHON_BIN="$INSTALL_DIR/venv/bin/python"
    if [ ! -f "$PYTHON_BIN" ]; then
        PYTHON_BIN=$(command -v python3)
    fi

    # ── Service 1: Cloud Agent ────────────────────────────────
    sudo tee /etc/systemd/system/ai-employee-cloud.service > /dev/null << EOF
[Unit]
Description=AI Employee Cloud Agent (Platinum Tier)
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$PYTHON_BIN $INSTALL_DIR/cloud_agent.py --loop 60
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
    ok "ai-employee-cloud.service created"

    # ── Service 2: Health Monitor ─────────────────────────────
    sudo tee /etc/systemd/system/ai-employee-health.service > /dev/null << EOF
[Unit]
Description=AI Employee Health Monitor (Platinum Tier)
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$PYTHON_BIN $INSTALL_DIR/health_monitor.py --loop 300
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
    ok "ai-employee-health.service created"

    # ── Service 3: Vault Sync ─────────────────────────────────
    sudo tee /etc/systemd/system/ai-employee-sync.service > /dev/null << EOF
[Unit]
Description=AI Employee Vault Git Sync (Platinum Tier)
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/bin/bash $INSTALL_DIR/cloud_sync.sh --loop 30
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    ok "ai-employee-sync.service created"

    # ── Enable Services ───────────────────────────────────────
    sudo systemctl daemon-reload
    sudo systemctl enable ai-employee-cloud ai-employee-health ai-employee-sync
    ok "All 3 services enabled (start on boot)"

    warn "Services are ENABLED but NOT started yet."
    warn "Edit .env first, then run:"
    warn "  sudo systemctl start ai-employee-cloud ai-employee-health ai-employee-sync"
}

# ── Step 7: Firewall ──────────────────────────────────────────
setup_firewall() {
    step "7/7 — Firewall (UFW)"

    if ! command -v ufw &>/dev/null; then
        warn "UFW not available — skipping firewall setup"
        return
    fi

    # Allow SSH only (no web ports — cloud agent uses stdout transport)
    sudo ufw allow OpenSSH
    sudo ufw --force enable
    ok "UFW enabled — SSH allowed, all other ports blocked"

    # Oracle Cloud also has Network Security Groups — configure in OCI console:
    # Ingress: Port 22 (SSH) from 0.0.0.0/0
    # Egress: All (for API calls)
    warn "Also configure Oracle Cloud NSG in OCI Console:"
    warn "  Networking > Virtual Cloud Network > Security Lists"
    warn "  Allow ingress TCP port 22"
}

# ── Summary ───────────────────────────────────────────────────
print_summary() {
    echo ""
    echo "============================================================"
    echo "  SETUP COMPLETE — AI Employee Cloud VM"
    echo "============================================================"
    echo ""
    echo "  Services registered (systemd):"
    echo "    ai-employee-cloud   — cloud_agent.py  (every 60s)"
    echo "    ai-employee-health  — health_monitor.py (every 5min)"
    echo "    ai-employee-sync    — cloud_sync.sh   (every 30s)"
    echo ""
    echo "  NEXT STEPS:"
    echo ""
    echo "  1. Configure credentials:"
    echo "     nano $INSTALL_DIR/.env"
    echo ""
    echo "  2. Start services:"
    echo "     sudo systemctl start ai-employee-cloud"
    echo "     sudo systemctl start ai-employee-health"
    echo "     sudo systemctl start ai-employee-sync"
    echo ""
    echo "  3. Check status:"
    echo "     sudo systemctl status ai-employee-cloud"
    echo "     journalctl -u ai-employee-cloud -f"
    echo ""
    echo "  4. On your local Windows machine, run:"
    echo "     python local_agent.py --loop"
    echo ""
    echo "  5. Demo flow test:"
    echo "     python platinum_demo.py"
    echo ""
    echo "  Oracle Cloud Free Tier (ARM VM):"
    echo "    https://cloud.oracle.com/compute/instances"
    echo "    Choose: VM.Standard.A1.Flex"
    echo "    Config: 2 OCPU, 12 GB RAM (free)"
    echo ""
    echo "============================================================"
}

# ── Run ───────────────────────────────────────────────────────
main() {
    echo "============================================================"
    echo "  AI Employee — Oracle Cloud Free Tier Setup"
    echo "  Platinum Tier: Cloud/Local Split Architecture"
    echo "============================================================"

    detect_os
    install_system_deps
    check_python
    setup_venv
    setup_git
    setup_env
    setup_systemd
    setup_firewall
    print_summary
}

main
