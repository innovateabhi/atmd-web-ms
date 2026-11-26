#!/usr/bin/env bash
# ==============================================================================
# Linux Automated Website Uptime Monitoring System
# Fedora Linux Automated Deployment & Configuration Script
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Ensure root privileges
if [ "$EUID" -ne 0 ]; then
    log_error "This script must be executed with root privileges (sudo)."
    exit 1
fi

INSTALL_DIR="/opt/linux-uptime-monitor"
APP_USER="uptimemon"
LOG_DIR="/var/log/uptime-monitor"

log_info "Initiating Fedora Linux Deployment for Linux Automated Website Uptime Monitor..."

# 1. Update Fedora repositories & install required dependencies using DNF
log_info "Step 1: Installing system packages using DNF..."
dnf check-update || true
dnf install -y \
    python3 \
    python3-devel \
    python3-pip \
    python3-virtualenv \
    gcc \
    nginx \
    firewalld \
    policycoreutils-python-utils \
    git \
    sqlite

log_success "System prerequisites installed."

# 2. Create unprivileged system user
log_info "Step 2: Configuring unprivileged service user (${APP_USER})..."
if ! id -u "$APP_USER" >/dev/null 2>&1; then
    useradd --system --shell /sbin/nologin --comment "Uptime Monitor Service User" "$APP_USER"
    log_success "Created system user: $APP_USER"
else
    log_info "System user $APP_USER already exists."
fi

# 3. Create directories & set permissions
log_info "Step 3: Preparing directories and permissions..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/instance"
mkdir -p "$LOG_DIR"

chown -R "$APP_USER:$APP_USER" "$LOG_DIR"
chmod 755 "$LOG_DIR"

# 4. Copy repository files into installation directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
log_info "Step 4: Syncing project source files into $INSTALL_DIR..."
cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/" || true
cp "$SCRIPT_DIR"/.env.example "$INSTALL_DIR"/.env.example 2>/dev/null || true

# 5. Setup Python Virtual Environment
log_info "Step 5: Setting up Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip setuptools wheel
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
"$INSTALL_DIR/venv/bin/pip" install gunicorn
log_success "Python virtual environment and dependencies configured."

# 6. Configure environment variables
log_info "Step 6: Setting up .env file..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    SECRET_HEX=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    cat <<EOF > "$INSTALL_DIR/.env"
FLASK_APP=run.py
FLASK_ENV=production
SECRET_KEY=$SECRET_HEX
DATABASE_PATH=instance/uptime_monitor.sqlite3
DEFAULT_MONITOR_INTERVAL_SECONDS=60
DEFAULT_REQUEST_TIMEOUT_SECONDS=10
ALLOW_LOCALHOST_MONITORING=false
SMTP_ENABLED=false
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=
SMTP_PASSWORD=
ALERT_EMAIL_RECIPIENT=
ALERT_EMAIL_SENDER=no-reply@uptime-monitor.local
EOF
    log_success "Generated new production .env configuration."
else
    log_info ".env already exists. Preserving existing configuration."
fi

# 7. Initialize SQLite Database & Administrator
log_info "Step 7: Initializing database schema..."
cd "$INSTALL_DIR"
"$INSTALL_DIR/venv/bin/flask" init-db

if [ -z "${ADMIN_PASSWORD:-}" ]; then
    ADMIN_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(12))")
else
    ADMIN_PASS="$ADMIN_PASSWORD"
fi
ADMIN_USER="${ADMIN_USERNAME:-admin}"

log_info "Creating default administrator credentials..."
"$INSTALL_DIR/venv/bin/flask" create-admin --username "$ADMIN_USER" --password "$ADMIN_PASS"
log_success "Admin user created: $ADMIN_USER"

# Correct ownership of installation directory
chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR"
chmod -R 750 "$INSTALL_DIR"
chmod 770 "$INSTALL_DIR/instance"

# 8. Configure SELinux (Preserving SELinux enforcing mode)
log_info "Step 8: Configuring SELinux policies..."
if selinuxenabled 2>/dev/null; then
    log_info "SELinux is active. Permitting Nginx network proxy connections..."
    setsebool -P httpd_can_network_connect 1
    # Allow Nginx to read static assets in /opt
    semanage fcontext -a -t httpd_sys_content_t "$INSTALL_DIR/app/static(/.*)?" 2>/dev/null || true
    restorecon -R "$INSTALL_DIR/app/static" 2>/dev/null || true
    log_success "SELinux policies applied successfully."
else
    log_warn "SELinux is not enforcing. Skipping policy adjustments."
fi

# 9. Configure Firewalld (Preserving Firewalld active status)
log_info "Step 9: Configuring Firewalld for HTTP traffic..."
if systemctl is-active --quiet firewalld; then
    firewall-cmd --permanent --add-service=http
    firewall-cmd --reload
    log_success "Firewalld configured to allow incoming HTTP traffic on port 80."
else
    log_warn "Firewalld is inactive. Starting and enabling firewalld..."
    systemctl enable --now firewalld
    firewall-cmd --permanent --add-service=http
    firewall-cmd --reload
    log_success "Firewalld activated and configured."
fi

# 10. Install Nginx configuration
log_info "Step 10: Installing Nginx reverse proxy configuration..."
cp "$INSTALL_DIR/deployment/nginx/uptime-monitor.conf" /etc/nginx/conf.d/uptime-monitor.conf
# Verify nginx configuration syntax
nginx -t
systemctl enable --now nginx
systemctl reload nginx
log_success "Nginx reverse proxy online."

# 11. Install and activate Systemd services
log_info "Step 11: Registering systemd service units..."
cp "$INSTALL_DIR/deployment/systemd/uptime-monitor.service" /etc/systemd/system/
cp "$INSTALL_DIR/deployment/systemd/uptime-worker.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now uptime-monitor.service
systemctl enable --now uptime-worker.service

log_success "Systemd services uptime-monitor and uptime-worker enabled and started."

# 12. Completion Summary
HOST_IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${GREEN}======================================================================${NC}"
echo -e "${GREEN}  FEDORA DEPLOYMENT COMPLETED SUCCESSFULLY!                           ${NC}"
echo -e "${GREEN}======================================================================${NC}"
echo -e "Access the web console at: ${BLUE}http://${HOST_IP}/${NC}"
echo -e "Administrator Username:   ${YELLOW}${ADMIN_USER}${NC}"
echo -e "Administrator Password:   ${YELLOW}${ADMIN_PASS}${NC}"
echo -e "Services Active:"
echo -e "  - Web App (Gunicorn):    systemctl status uptime-monitor"
echo -e "  - Background Worker:     systemctl status uptime-worker"
echo -e "  - Reverse Proxy (Nginx): systemctl status nginx"
echo -e "Logs available at:         ${LOG_DIR}"
echo -e "${GREEN}======================================================================${NC}"
