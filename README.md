# TuxCut-NG

**Next-Generation ARP network tool for Linux** — rewrite of the original
[TuxCut](https://github.com/a-atalla/tuxcut) with full compatibility for
modern distributions.

## What's new vs original TuxCut

| Feature | Original TuxCut | TuxCut-NG |
|---|---|---|
| GUI toolkit | wxPython | **PyQt6** (Wayland-native) |
| Firewall | arptables (legacy) | **nftables** + arptables fallback |
| MAC change | ifconfig | **ip link** (iproute2) |
| Hostname lookup | nslookup | **socket** (no dependency) |
| Gateway info | netifaces | **ip route** (no dependency) |
| Python | 3.6–3.12 | **3.11–3.14** |
| Fedora 43 | ❌ | ✅ |
| Debian 12 | partial | ✅ |
| Ubuntu 22/24 | partial | ✅ |

---

## Architecture

```
tuxcut-ng/
├── server/
│   ├── tuxcutd.py        # Bottle REST daemon (runs as root)
│   ├── utils.py          # Network utilities, ARP, nftables
│   └── tuxcutd.service   # systemd unit
├── client/
│   ├── tuxcut.py         # Entry point (runs as normal user)
│   └── main_window.py    # PyQt6 GUI
├── requirements.txt
└── install.sh            # Installer for Fedora + Debian
```

The daemon (`tuxcutd`) exposes a local REST API on `127.0.0.1:8013`.
The GUI talks to it via HTTP — **no root required for the GUI**.

---

## Installation

```bash
git clone https://github.com/you/tuxcut-ng
cd tuxcut-ng
sudo bash install.sh
```

### Manual (run from source)

```bash
# 1. Install Python dependencies
pip install -r requirements.txt --break-system-packages

# 2. Start the daemon (root required)
sudo python3 server/tuxcutd.py

# 3. Launch the GUI (normal user)
python3 client/tuxcut.py
```

### Fedora 43

```bash
sudo dnf install python3-PyQt6 nftables net-tools libpcap
pip install scapy bottle apscheduler setproctitle requests --break-system-packages
```

### Debian 12 / Ubuntu 24

```bash
sudo apt install python3-pyqt6 nftables net-tools libpcap-dev
pip install scapy bottle apscheduler setproctitle requests --break-system-packages
```

---

## Features

- **Scan** — ARP-scan the entire /24 subnet and list all live hosts
- **Cut** — Disconnect any host from the internet via ARP spoofing
- **Resume** — Restore a cut host's connectivity
- **Protect** — Block forged ARP packets targeting this machine
  (nftables on modern kernels, arptables fallback)
- **Change MAC** — Randomize this machine's MAC address (`ip link`)
- **Aliases** — Give friendly names to hosts (stored locally)

---

## How it works

```
Cut host flow:
  Attacker  ──ARP reply──▶  Victim   "Gateway is at MY_MAC"
  Attacker  ──ARP reply──▶  Gateway  "Victim is at MY_MAC"
  → victim's packets go to us, we drop them (ip_forward=0)

Restore flow:
  Attacker  ──ARP reply──▶  Victim   "Gateway is at GW_MAC"  (×10)
  Attacker  ──ARP reply──▶  Gateway  "Victim is at VICTIM_MAC" (×10)

Protection flow:
  nftables: drop all ARP input EXCEPT from real gateway IP+MAC
  ip neigh:  pin gateway's MAC as permanent in ARP cache
```

---

## Uninstall

```bash
sudo bash install.sh --remove
```

---

## Requirements

- Linux kernel ≥ 4.2 (nftables ARP support)
- Python ≥ 3.11
- Root for the daemon
- nftables **or** arptables
- iproute2 (`ip` command)

---

## License

MIT
