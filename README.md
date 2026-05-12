# TuxCut-NG

![Version](https://img.shields.io/badge/version-1.3.1-blue)
![Python](https://img.shields.io/badge/python-3.11--3.14-green)
![License](https://img.shields.io/badge/license-GPL--3.0-orange)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)

إعادة كتابة كاملة للبرنامج الأصلي [TuxCut](https://github.com/a-atalla/tuxcut) مع دعم كامل لأحدث توزيعات Linux.

> Modern rewrite of [TuxCut](https://github.com/a-atalla/tuxcut) with full support for modern Linux distributions.

---

## ✅ التوزيعات المدعومة / Supported Distros

| التوزيعة / Distro | الإصدار / Version |
|---|---|
| Fedora | 40 / 41 / 42 / 43 / 44 |
| Debian | 11 / 12 / 13 (Trixie) |
| Ubuntu | 22.04 / 24.04 / 26.04 LTS |
| Arch Linux / Manjaro | rolling |
| openSUSE | Leap / Tumbleweed |

---

## 📦 التثبيت / Installation

### من الحزمة — From Package *(الأسهل / Recommended)*

```bash
# فيدورا / Fedora / RHEL
sudo dnf install ./tuxcut-ng-1.3.1-1.noarch.rpm

# ديبيان / أوبونتو — Debian / Ubuntu
sudo apt install ./tuxcut-ng_1.3.1.deb
```

> حمّل الحزم من / Download packages from: [Releases](https://github.com/mamii76/Tuxcut/releases/latest)

### من المصدر — From Source

```bash
git clone https://github.com/mamii76/Tuxcut
cd Tuxcut
sudo bash install.sh
```

---

## ✨ المميزات / Features

| الميزة / Feature | الوصف / Description |
|---|---|
| **Scan** | مسح الشبكة /24 وعرض الأجهزة المتصلة / Scan /24 network for live hosts |
| **Cut** | قطع إنترنت أي جهاز / Disconnect any device from the internet |
| **Resume** | استعادة الاتصال / Restore connection |
| **Protect** | حماية من ARP Spoofing عبر nftables / Block ARP spoofing attacks |
| **Change MAC** | تغيير MAC address عشوائياً / Randomize MAC address |
| **Alias** | أسماء مخصصة للأجهزة / Give friendly names to hosts |

---

## 🔄 ما الذي تغيّر عن الأصل؟ / What changed from original?

| الأصل / Original | TuxCut-NG |
|---|---|
| wxPython | **PyQt6** (Wayland-native) |
| arptables | **nftables** + arptables fallback |
| ifconfig | **ip link** (iproute2) |
| netifaces | **ip route** (no extra dependency) |
| Python 3.6–3.12 | **Python 3.11–3.14** |

---

## 🏗️ البنية / Structure

```
Tuxcut/
├── server/
│   ├── tuxcutd.py        ← daemon (root / systemd)
│   └── tuxcutd.service   ← systemd unit
├── client/
│   └── tuxcut.py         ← PyQt6 GUI (normal user)
├── requirements.txt
└── install.sh
```

الـ daemon يعمل على `127.0.0.1:8013` — الواجهة لا تحتاج صلاحيات root.

> The daemon runs on `127.0.0.1:8013` — the GUI requires no root privileges.

---

## 🗑️ إلغاء التثبيت / Uninstall

```bash
# Fedora / RPM
sudo dnf remove tuxcut-ng

# Debian / Ubuntu / DEB
sudo apt remove tuxcut-ng
```

---

## 📄 الترخيص / License

**GPL-3.0** — مستند إلى [TuxCut](https://github.com/a-atalla/tuxcut) بواسطة a-atalla.

---

> ⚠️ للاستخدام التعليمي وإدارة الشبكات فقط.
> استخدمه على الشبكات التي تملكها أو لديك إذن باختبارها.
>
> *For educational and network administration use only.
> Use only on networks you own or have explicit permission to test.*
