# TuxCut-NG

![Version](https://img.shields.io/badge/version-1.4.3-blue)
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
sudo dnf install ./tuxcut-ng-1.4.3-1.noarch.rpm

# ديبيان / أوبونتو — Debian / Ubuntu
sudo apt install ./tuxcut-ng_1.4.3.deb
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
| **Scan** | مسح الشبكة /24 وعرض الأجهزة / Scan /24 network for live hosts |
| **Cut** | قطع إنترنت أي جهاز / Disconnect any device |
| **Resume** | استعادة الاتصال / Restore connection |
| **Protect** | حماية من ARP Spoofing (nftables) / Block ARP spoofing |
| **Change MAC** | تغيير MAC عشوائياً / Randomize MAC address |
| **Alias** | أسماء مخصصة للأجهزة / Custom host names |
| **Dark/Light Mode** | وضع داكن وفاتح / Theme toggle with preference saving |

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
│   └── tuxcut.py         ← PyQt6 GUI (auto requests root)
├── requirements.txt
└── install.sh
```

الـ daemon يعمل على `127.0.0.1:8013` — الواجهة تطلب صلاحية root تلقائياً.

> The daemon runs on `127.0.0.1:8013` — the GUI auto-requests root via sudo.

---

## 🗑️ إلغاء التثبيت / Uninstall

```bash
# Fedora / RPM
sudo dnf remove tuxcut-ng

# Debian / Ubuntu / DEB
sudo apt remove tuxcut-ng
```

---

## 📋 سجل الإصدارات / Changelog

| الإصدار | التغييرات |
|---|---|
| **v1.4.3** | إصلاحات أمنية: تطهير المدخلات، تحقق من IP/MAC/iface، إصلاح generate_mac ✅ |
| v1.4.2 | إصلاح Wayland مع sudo، real-time IP، أيقونة المقص |
| v1.4.1 | إصلاح المسح بالـ iface الصحيح، الـ MAC الأصلي |
| v1.4.0 | وضع داكن/فاتح، تشغيل تلقائي للخادم |
| v1.3.1 | إعادة كتابة كاملة |

---

## 📄 الترخيص / License

**GPL-3.0** — مستند إلى [TuxCut](https://github.com/a-atalla/tuxcut) بواسطة a-atalla.

---

> ⚠️ للاستخدام التعليمي وإدارة الشبكات فقط.
> استخدمه على الشبكات التي تملكها أو لديك إذن باختبارها.
>
> *For educational and network administration use only.
> Use only on networks you own or have explicit permission to test.*
