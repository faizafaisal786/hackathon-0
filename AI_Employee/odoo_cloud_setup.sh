#!/bin/bash
# ============================================================
#  Odoo Community Cloud Deployment — Platinum Tier
#  Deploys Odoo 19 on Oracle Cloud Free Tier with:
#   - HTTPS (Let's Encrypt via Certbot)
#   - Daily backups to local folder
#   - Health monitoring (writes to Signals/)
#   - PostgreSQL database
#   - Nginx reverse proxy
# ============================================================
#
#  Usage:
#    chmod +x odoo_cloud_setup.sh
#    ./odoo_cloud_setup.sh              # Full setup
#    ./odoo_cloud_setup.sh --backup     # Manual backup now
#    ./odoo_cloud_setup.sh --health     # Health check only
#    ./odoo_cloud_setup.sh --status     # Show service status
#
#  After setup:
#    Odoo runs at: http://YOUR_VM_IP:8069
#    After HTTPS:  https://YOUR_DOMAIN
#
#  Oracle Cloud Free Tier:
#    VM.Standard.A1.Flex — 2 OCPU, 12 GB RAM (ARM)
#    Public IP: assign in OCI console
#    Open ports: 22 (SSH), 80 (HTTP), 443 (HTTPS), 8069 (Odoo)
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_DIR="$SCRIPT_DIR/AI_Employee_Vault"
SIGNALS_DIR="$VAULT_DIR/Signals"
BACKUP_DIR="$SCRIPT_DIR/odoo_backups"
ODOO_PORT=8069
DOMAIN="${ODOO_DOMAIN:-}"  # Set in .env: ODOO_DOMAIN=odoo.yourdomain.com

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC}   $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }
step() { echo -e "\n${YELLOW}==> $1${NC}"; }

write_signal() {
    local type="$1" message="$2"
    mkdir -p "$SIGNALS_DIR"
    local ts; ts=$(date +%Y%m%d_%H%M%S)
    local iso; iso=$(date -Iseconds)
    cat > "$SIGNALS_DIR/SIGNAL_${ts}_${type}.json" << EOF
{
  "type": "$type",
  "message": "$message",
  "agent": "odoo_cloud_setup",
  "timestamp": "$iso"
}
EOF
}

# ── Step 1: System packages ───────────────────────────────────
install_packages() {
    step "1/6 — Install system packages"

    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        docker.io \
        docker-compose \
        nginx \
        certbot \
        python3-certbot-nginx \
        curl \
        ufw \
        2>/dev/null

    # Add current user to docker group
    sudo usermod -aG docker "$USER" 2>/dev/null || true
    ok "System packages installed"
}

# ── Step 2: Docker + Odoo ─────────────────────────────────────
setup_odoo_docker() {
    step "2/6 — Setup Odoo 19 with Docker"

    mkdir -p "$SCRIPT_DIR/odoo_data/addons"
    mkdir -p "$SCRIPT_DIR/odoo_data/config"
    mkdir -p "$BACKUP_DIR"

    # Odoo config file
    cat > "$SCRIPT_DIR/odoo_data/config/odoo.conf" << 'EOF'
[options]
addons_path = /mnt/extra-addons
data_dir = /var/lib/odoo
db_host = db
db_port = 5432
db_user = odoo
db_password = odoo_secure_password_change_me
xmlrpc_port = 8069
workers = 2
max_cron_threads = 1
logfile = /var/log/odoo/odoo.log
log_level = warn
EOF

    # docker-compose.yml for Odoo + PostgreSQL
    cat > "$SCRIPT_DIR/docker-compose-odoo.yml" << 'EOF'
version: '3.8'

services:
  db:
    image: postgres:15
    container_name: odoo_db
    restart: unless-stopped
    environment:
      POSTGRES_DB: postgres
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo_secure_password_change_me
    volumes:
      - odoo_db_data:/var/lib/postgresql/data
    networks:
      - odoo_net

  odoo:
    image: odoo:17
    container_name: odoo_app
    restart: unless-stopped
    depends_on:
      - db
    ports:
      - "8069:8069"
    environment:
      HOST: db
      USER: odoo
      PASSWORD: odoo_secure_password_change_me
    volumes:
      - odoo_web_data:/var/lib/odoo
      - ./odoo_data/config:/etc/odoo
      - ./odoo_data/addons:/mnt/extra-addons
    networks:
      - odoo_net

volumes:
  odoo_db_data:
  odoo_web_data:

networks:
  odoo_net:
    driver: bridge
EOF

    ok "Docker Compose config created"

    # Start Odoo
    docker compose -f "$SCRIPT_DIR/docker-compose-odoo.yml" up -d
    sleep 10

    # Verify running
    if docker ps | grep -q odoo_app; then
        ok "Odoo is running on port $ODOO_PORT"
        write_signal "ODOO_STARTED" "Odoo 17 started on port $ODOO_PORT"
    else
        fail "Odoo failed to start"
        write_signal "ODOO_START_FAILED" "Docker failed to start Odoo"
    fi
}

# ── Step 3: Nginx reverse proxy ───────────────────────────────
setup_nginx() {
    step "3/6 — Nginx reverse proxy"

    local server_name="${DOMAIN:-_}"

    sudo tee /etc/nginx/sites-available/odoo << EOF
upstream odoo {
    server 127.0.0.1:$ODOO_PORT;
}

server {
    listen 80;
    server_name $server_name;

    # Security headers
    add_header X-Frame-Options SAMEORIGIN;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # Proxy to Odoo
    location / {
        proxy_pass http://odoo;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;

        # Timeouts
        proxy_connect_timeout  720s;
        proxy_send_timeout     720s;
        proxy_read_timeout     720s;
        send_timeout           720s;
    }

    # Static files
    location ~* /web/static/ {
        proxy_cache_valid 200 90m;
        proxy_buffering    on;
        expires 864000;
        proxy_pass http://odoo;
    }

    client_max_body_size 200m;
}
EOF

    sudo ln -sf /etc/nginx/sites-available/odoo /etc/nginx/sites-enabled/odoo
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo nginx -t && sudo systemctl reload nginx
    ok "Nginx configured"
}

# ── Step 4: HTTPS with Let's Encrypt ─────────────────────────
setup_https() {
    step "4/6 — HTTPS (Let's Encrypt)"

    if [ -z "$DOMAIN" ]; then
        warn "ODOO_DOMAIN not set in .env — skipping HTTPS"
        warn "Set ODOO_DOMAIN=odoo.yourdomain.com and re-run"
        warn "Then run: sudo certbot --nginx -d \$ODOO_DOMAIN"
        return
    fi

    local email="${ADMIN_EMAIL:-admin@$DOMAIN}"

    sudo certbot --nginx \
        -d "$DOMAIN" \
        --email "$email" \
        --agree-tos \
        --non-interactive \
        --redirect

    ok "HTTPS enabled for $DOMAIN"

    # Auto-renewal cron
    echo "0 12 * * * root certbot renew --quiet" | sudo tee /etc/cron.d/certbot-renew
    ok "Certificate auto-renewal configured"
}

# ── Step 5: Backup system ─────────────────────────────────────
setup_backups() {
    step "5/6 — Daily backup system"

    mkdir -p "$BACKUP_DIR"

    # Backup script
    cat > "$SCRIPT_DIR/odoo_backup.sh" << 'BACKUP_EOF'
#!/bin/bash
BACKUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/odoo_backups"
SIGNALS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/AI_Employee_Vault/Signals"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/odoo_backup_$TIMESTAMP.tar.gz"

mkdir -p "$BACKUP_DIR"

echo "  [Backup] Starting Odoo backup..."

# Dump PostgreSQL
docker exec odoo_db pg_dumpall -U odoo > "$BACKUP_DIR/db_$TIMESTAMP.sql" 2>/dev/null

# Backup filestore
docker run --rm \
    --volumes-from odoo_app \
    -v "$BACKUP_DIR:/backup" \
    alpine \
    tar czf "/backup/filestore_$TIMESTAMP.tar.gz" /var/lib/odoo 2>/dev/null || true

# Combine into single backup
tar czf "$BACKUP_FILE" \
    "$BACKUP_DIR/db_$TIMESTAMP.sql" \
    "$BACKUP_DIR/filestore_$TIMESTAMP.tar.gz" 2>/dev/null || true

# Cleanup temp files
rm -f "$BACKUP_DIR/db_$TIMESTAMP.sql" "$BACKUP_DIR/filestore_$TIMESTAMP.tar.gz"

# Keep only last 7 backups
ls -t "$BACKUP_DIR"/odoo_backup_*.tar.gz 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true

BACKUP_SIZE=$(du -sh "$BACKUP_FILE" 2>/dev/null | cut -f1)
echo "  [Backup] Done: $BACKUP_FILE ($BACKUP_SIZE)"

# Write signal
mkdir -p "$SIGNALS_DIR"
cat > "$SIGNALS_DIR/SIGNAL_$(date +%Y%m%d_%H%M%S)_ODOO_BACKUP.json" << EOF
{
  "type": "ODOO_BACKUP",
  "message": "Odoo backup completed: $BACKUP_FILE ($BACKUP_SIZE)",
  "agent": "odoo_backup",
  "timestamp": "$(date -Iseconds)"
}
EOF
BACKUP_EOF

    chmod +x "$SCRIPT_DIR/odoo_backup.sh"

    # Daily backup cron (2am)
    (crontab -l 2>/dev/null; echo "0 2 * * * $SCRIPT_DIR/odoo_backup.sh >> $SCRIPT_DIR/odoo_backups/backup.log 2>&1") | crontab -
    ok "Daily backup at 2am configured"
    ok "Backups stored in: $BACKUP_DIR"
}

# ── Step 6: Health monitoring ─────────────────────────────────
setup_health_monitoring() {
    step "6/6 — Odoo health monitoring"

    cat > "$SCRIPT_DIR/odoo_health.sh" << 'HEALTH_EOF'
#!/bin/bash
SIGNALS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/AI_Employee_Vault/Signals"
ODOO_URL="http://localhost:8069/web/health"

mkdir -p "$SIGNALS_DIR"

# Check if Odoo responds
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$ODOO_URL" 2>/dev/null)

if [ "$HTTP_CODE" = "200" ]; then
    echo "  [Odoo Health] OK (HTTP $HTTP_CODE)"
else
    echo "  [Odoo Health] FAIL (HTTP $HTTP_CODE)"
    cat > "$SIGNALS_DIR/SIGNAL_$(date +%Y%m%d_%H%M%S)_ODOO_DOWN.json" << EOF
{
  "type": "ODOO_DOWN",
  "message": "Odoo health check failed (HTTP $HTTP_CODE). Check: docker ps",
  "agent": "odoo_health",
  "timestamp": "$(date -Iseconds)"
}
EOF
    # Try to restart
    docker restart odoo_app 2>/dev/null && echo "  [Odoo Health] Restart attempted"
fi
HEALTH_EOF

    chmod +x "$SCRIPT_DIR/odoo_health.sh"

    # Health check every 5 minutes
    (crontab -l 2>/dev/null; echo "*/5 * * * * $SCRIPT_DIR/odoo_health.sh >> /tmp/odoo_health.log 2>&1") | crontab -
    ok "Odoo health check every 5 minutes"
}

# ── Backup command ─────────────────────────────────────────────
do_backup() {
    echo "  [Manual Backup] Running now..."
    bash "$SCRIPT_DIR/odoo_backup.sh"
}

# ── Health check command ───────────────────────────────────────
do_health() {
    echo "  [Odoo Health Check]"
    if docker ps | grep -q odoo_app; then
        echo "  Container: RUNNING"
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://localhost:$ODOO_PORT/web/health" 2>/dev/null)
        echo "  HTTP:      $HTTP_CODE"
    else
        echo "  Container: NOT RUNNING"
        echo "  Run: docker compose -f docker-compose-odoo.yml up -d"
    fi
}

# ── Status command ─────────────────────────────────────────────
do_status() {
    echo "============================================================"
    echo "  ODOO CLOUD STATUS"
    echo "============================================================"
    docker ps --filter "name=odoo" --format "  {{.Names}}: {{.Status}}" 2>/dev/null || echo "  Docker not running"
    echo ""
    echo "  Backup dir: $BACKUP_DIR"
    ls "$BACKUP_DIR"/*.tar.gz 2>/dev/null | tail -3 | while read f; do
        echo "    $(basename $f) ($(du -sh "$f" | cut -f1))"
    done
    echo "  Domain: ${DOMAIN:-not configured}"
    echo "============================================================"
}

# ── Main ──────────────────────────────────────────────────────
case "${1:-}" in
    --backup)  do_backup  ;;
    --health)  do_health  ;;
    --status)  do_status  ;;
    *)
        echo "============================================================"
        echo "  ODOO COMMUNITY — Cloud Deployment (Platinum Tier)"
        echo "  Oracle Cloud Free Tier | Docker | Nginx | HTTPS | Backups"
        echo "============================================================"
        install_packages
        setup_odoo_docker
        setup_nginx
        setup_https
        setup_backups
        setup_health_monitoring

        echo ""
        echo "============================================================"
        echo "  ODOO SETUP COMPLETE"
        echo "============================================================"
        echo ""
        echo "  Access Odoo at: http://$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_IP'):$ODOO_PORT"
        [ -n "$DOMAIN" ] && echo "  HTTPS:          https://$DOMAIN"
        echo ""
        echo "  First run: Create Odoo database at /web/database/manager"
        echo "  MCP integration: python odoo_mcp.py (connects via JSON-RPC)"
        echo ""
        echo "  Backups: Daily at 2am -> $BACKUP_DIR"
        echo "  Health:  Every 5 min -> Signals/ on failure"
        echo "============================================================"
        ;;
esac
