#!/bin/bash
# ============================================
# STEP 2: Cloud VM Setup Script
# Run this on your Cloud VM (Ubuntu/Debian)
# Supports: AWS EC2, GCP, Azure, DigitalOcean
# ============================================

set -e

echo "╔═══════════════════════════════════════╗"
echo "║   CLOUD VM SETUP — AI Employee       ║"
echo "╚═══════════════════════════════════════╝"

# --- System Update ---
echo "[1/7] Updating system..."
sudo apt update && sudo apt upgrade -y

# --- Install Dependencies ---
echo "[2/7] Installing dependencies..."
sudo apt install -y git python3 python3-pip python3-venv

# --- Create AI Employee User ---
echo "[3/7] Creating ai-employee user..."
sudo useradd -m -s /bin/bash ai-employee 2>/dev/null || echo "User already exists"

# --- Clone Vault ---
echo "[4/7] Cloning vault repo..."
sudo -u ai-employee bash -c '
    cd /home/ai-employee
    git clone git@github.com:YOUR_USER/ai-employee-vault.git vault
'

# --- Python Environment ---
echo "[5/7] Setting up Python environment..."
sudo -u ai-employee bash -c '
    cd /home/ai-employee
    python3 -m venv venv
    source venv/bin/activate
    pip install watchdog google-auth-oauthlib google-auth-httplib2 google-api-python-client
'

# --- Copy Service Files ---
echo "[6/7] Installing systemd services..."

# Gmail Watcher Service
sudo tee /etc/systemd/system/ai-gmail-watcher.service > /dev/null << 'SERVICE'
[Unit]
Description=AI Employee Gmail Watcher
After=network.target

[Service]
Type=simple
User=ai-employee
WorkingDirectory=/home/ai-employee/vault
ExecStart=/home/ai-employee/venv/bin/python gmail_watcher.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
SERVICE

# Filesystem Watcher Service
sudo tee /etc/systemd/system/ai-fs-watcher.service > /dev/null << 'SERVICE'
[Unit]
Description=AI Employee Filesystem Watcher
After=network.target

[Service]
Type=simple
User=ai-employee
WorkingDirectory=/home/ai-employee/vault
ExecStart=/home/ai-employee/venv/bin/python filesystem_watcher.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

# Git Sync Service
sudo tee /etc/systemd/system/ai-git-sync.service > /dev/null << 'SERVICE'
[Unit]
Description=AI Employee Git Sync
After=network.target

[Service]
Type=simple
User=ai-employee
WorkingDirectory=/home/ai-employee/vault
ExecStart=/bin/bash /home/ai-employee/vault/cloud_sync.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

# Ralph Loop Service
sudo tee /etc/systemd/system/ai-ralph-loop.service > /dev/null << 'SERVICE'
[Unit]
Description=AI Employee Ralph Wiggum Loop
After=network.target ai-gmail-watcher.service

[Service]
Type=simple
User=ai-employee
WorkingDirectory=/home/ai-employee/vault
ExecStart=/home/ai-employee/venv/bin/python ralph_loop.py
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
SERVICE

# --- Enable & Start Services ---
echo "[7/7] Enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable ai-gmail-watcher ai-fs-watcher ai-git-sync ai-ralph-loop
sudo systemctl start ai-gmail-watcher ai-fs-watcher ai-git-sync ai-ralph-loop

echo ""
echo "╔═══════════════════════════════════════╗"
echo "║   SETUP COMPLETE!                    ║"
echo "║                                       ║"
echo "║   Services running:                   ║"
echo "║   - ai-gmail-watcher                  ║"
echo "║   - ai-fs-watcher                     ║"
echo "║   - ai-git-sync                       ║"
echo "║   - ai-ralph-loop                     ║"
echo "║                                       ║"
echo "║   Check status:                       ║"
echo "║   sudo systemctl status ai-*          ║"
echo "╚═══════════════════════════════════════╝"
