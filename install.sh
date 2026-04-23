#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  TuxCut-NG Installer
#  Supports: Fedora 40-43+  |  Debian 11/12+  |  Ubuntu 22.04+
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

INSTALL_DIR="/opt/tuxcut-ng"
SERVICE_FILE="/etc/systemd/system/tuxcutd.service"
BIN_CLIENT="/usr/local/bin/tuxcut"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✔]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✘]${NC} $*"; exit 1; }

# ── Root check ────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || error "Run this script as root: sudo bash install.sh"

# ── Detect distro ─────────────────────────────────────────────────
detect_distro() {
    if [[ -f /etc/fedora-release ]]; then
        echo "fedora"
    elif [[ -f /etc/debian_version ]]; then
        echo "debian"
    elif grep -qi ubuntu /etc/os-release 2>/dev/null; then
        echo "debian"   # Ubuntu uses apt
    else
        error "Unsupported distribution. Supported: Fedora, Debian, Ubuntu."
    fi
}

DISTRO=$(detect_distro)
info "Detected: $DISTRO"

# ── Install system packages ───────────────────────────────────────
install_system_packages() {
    info "Installing system packages …"
    case "$DISTRO" in
        fedora)
            dnf install -y \
                python3 python3-pip \
                python3-PyQt6 \
                nftables \
                net-tools \
                bind-utils \
                libpcap \
                libpcap-devel \
                gcc \
                python3-devel
            ;;
        debian)
            export DEBIAN_FRONTEND=noninteractive
            apt-get update -q
            apt-get install -y \
                python3 python3-pip \
                python3-pyqt6 \
                nftables \
                net-tools \
                dnsutils \
                libpcap-dev \
                gcc \
                python3-dev
            ;;
    esac
    info "System packages installed."
}

# ── Install Python packages ───────────────────────────────────────
install_python_packages() {
    info "Installing Python packages …"
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Try with --break-system-packages (Python 3.11+)
    if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
        pip3 install -r "$SCRIPT_DIR/requirements.txt" --break-system-packages --quiet
    else
        pip3 install -r "$SCRIPT_DIR/requirements.txt" --quiet
    fi
    info "Python packages installed."
}

# ── Copy files ────────────────────────────────────────────────────
install_files() {
    info "Installing TuxCut-NG to $INSTALL_DIR …"
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    mkdir -p "$INSTALL_DIR"
    cp -r "$SCRIPT_DIR/server" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/client" "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/server/tuxcutd.py"
    chmod +x "$INSTALL_DIR/client/tuxcut.py"

    # Client launcher
    cat > "$BIN_CLIENT" <<'EOF'
#!/usr/bin/env bash
exec python3 /opt/tuxcut-ng/client/tuxcut.py "$@"
EOF
    chmod +x "$BIN_CLIENT"
    info "Files installed."
}

# ── Systemd service ───────────────────────────────────────────────
install_service() {
    info "Installing systemd service …"
    cp "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/server/tuxcutd.service" \
       "$SERVICE_FILE"
    systemctl daemon-reload
    systemctl enable tuxcutd
    systemctl start  tuxcutd

    sleep 1
    if systemctl is-active --quiet tuxcutd; then
        info "tuxcutd service is running."
    else
        warn "Service started but status check failed. Run: systemctl status tuxcutd"
    fi
}

# ── .desktop entry ────────────────────────────────────────────────
install_desktop_entry() {
    DESKTOP_DIR="/usr/share/applications"
    mkdir -p "$DESKTOP_DIR"
    cat > "$DESKTOP_DIR/tuxcut-ng.desktop" <<EOF
[Desktop Entry]
Version=1.0
Name=TuxCut-NG
Comment=ARP network management tool
Exec=tuxcut
Icon=network-wireless
Terminal=false
Type=Application
Categories=Network;Security;
EOF
    info "Desktop entry created."
}

# ── Uninstall (--remove flag) ─────────────────────────────────────
uninstall() {
    info "Uninstalling TuxCut-NG …"
    systemctl stop    tuxcutd 2>/dev/null || true
    systemctl disable tuxcutd 2>/dev/null || true
    rm -f  "$SERVICE_FILE"
    rm -rf "$INSTALL_DIR"
    rm -f  "$BIN_CLIENT"
    rm -f  /usr/share/applications/tuxcut-ng.desktop
    systemctl daemon-reload
    info "TuxCut-NG removed."
    exit 0
}

# ── Main ──────────────────────────────────────────────────────────
[[ "${1:-}" == "--remove" ]] && uninstall

echo ""
echo "  ████████╗██╗   ██╗██╗  ██╗ ██████╗██╗   ██╗████████╗"
echo "     ██╔══╝██║   ██║╚██╗██╔╝██╔════╝██║   ██║╚══██╔══╝"
echo "     ██║   ██║   ██║ ╚███╔╝ ██║     ██║   ██║   ██║   "
echo "     ██║   ██║   ██║ ██╔██╗ ██║     ██║   ██║   ██║   "
echo "     ██║   ╚██████╔╝██╔╝ ██╗╚██████╗╚██████╔╝   ██║   "
echo "     ╚═╝    ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═════╝    ╚═╝   "
echo "                  NG — Next Generation"
echo ""

install_system_packages
install_python_packages
install_files
install_service
install_desktop_entry

echo ""
info "═══════════════════════════════════════════════════════"
info " Installation complete!"
info " Start the GUI:    tuxcut"
info " Service control:  systemctl {start|stop|status} tuxcutd"
info " Uninstall:        sudo bash install.sh --remove"
info "═══════════════════════════════════════════════════════"
echo ""
