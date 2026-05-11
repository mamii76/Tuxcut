#!/usr/bin/env bash
set -e
[[ $EUID -eq 0 ]] || { echo "Run as root: sudo bash install.sh"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[TuxCut-NG] Installing system packages..."
if command -v dnf &>/dev/null; then
    dnf install -y python3 python3-pip nftables net-tools psmisc libpcap python3-PyQt6 -q
elif command -v apt-get &>/dev/null; then
    apt-get install -y python3 python3-pip nftables net-tools psmisc libpcap-dev python3-pyqt6 -q
fi

echo "[TuxCut-NG] Installing Python packages..."
pip3 install scapy bottle apscheduler setproctitle requests \
    --break-system-packages -q 2>/dev/null || \
pip3 install scapy bottle apscheduler setproctitle requests -q

echo "[TuxCut-NG] Copying files..."
mkdir -p /opt/tuxcut-ng
cp -r "$SCRIPT_DIR/server" "$SCRIPT_DIR/client" /opt/tuxcut-ng/

echo "[TuxCut-NG] Setting up service..."
cp "$SCRIPT_DIR/server/tuxcutd.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable tuxcutd
systemctl start  tuxcutd

echo "[TuxCut-NG] Creating launcher..."
cat > /usr/local/bin/tuxcut << 'EOF'
#!/bin/bash
exec python3 /opt/tuxcut-ng/client/tuxcut.py "$@"
EOF
chmod +x /usr/local/bin/tuxcut

cat > /usr/share/applications/tuxcut-ng.desktop << 'EOF'
[Desktop Entry]
Version=1.0
Name=TuxCut-NG
Comment=ARP Network Management Tool
Exec=tuxcut
Icon=network-wireless
Terminal=false
Type=Application
Categories=Network;Security;System;
Keywords=network;arp;cut;security;
EOF

echo "[TuxCut-NG] Done! Run: tuxcut"
