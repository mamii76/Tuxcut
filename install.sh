#!/usr/bin/env bash
# TuxCut-NG installer — Fedora & Debian/Ubuntu
set -e
[[ $EUID -eq 0 ]] || { echo "Run as root: sudo bash install.sh"; exit 1; }

if command -v dnf &>/dev/null; then
    dnf install -y python3 python3-pip nftables net-tools psmisc
elif command -v apt &>/dev/null; then
    apt-get install -y python3 python3-pip nftables net-tools psmisc
fi

pip3 install -r requirements.txt --break-system-packages -q

mkdir -p /opt/tuxcut-ng
cp -r server client requirements.txt /opt/tuxcut-ng/

cp server/tuxcutd.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now tuxcutd

cat > /usr/local/bin/tuxcut <<'EOF'
#!/bin/bash
exec python3 /opt/tuxcut-ng/client/tuxcut.py "$@"
EOF
chmod +x /usr/local/bin/tuxcut

echo "Done. Run: tuxcut"
