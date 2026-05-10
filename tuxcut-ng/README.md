# TuxCut-NG

![Version](https://img.shields.io/badge/version-1.3.1-blue)
![Python](https://img.shields.io/badge/python-3.11--3.14-green)
![License](https://img.shields.io/badge/license-GPL--3.0-orange)

إعادة كتابة كاملة للبرنامج الأصلي [TuxCut](https://github.com/a-atalla/tuxcut)
مع دعم كامل لأحدث توزيعات Linux.

---

## ✅ التوزيعات المدعومة

| التوزيعة | الإصدار |
|---|---|
| Fedora | 40 / 41 / 42 / 43 / 44 |
| Debian | 11 / 12 / 13 (Trixie) |
| Ubuntu | 22.04 / 24.04 / 26.04 LTS |
| Arch Linux / Manjaro | rolling |
| openSUSE | Leap / Tumbleweed |

---

## التثبيت

### من الحزمة (الأسهل)
```bash
# فيدورا / RHEL
sudo dnf install ./tuxcut-ng-1.3.1-1.noarch.rpm

# ديبيان / أوبونتو
sudo apt install ./tuxcut-ng_1.3.1.deb
```

### من المصدر
```bash
git clone https://github.com/mamii76/Tuxcut
cd Tuxcut
sudo bash install.sh
```

---

## البنية

```
Tuxcut/
├── server/
│   ├── tuxcutd.py        ← daemon يعمل كـ root عبر systemd
│   └── tuxcutd.service   ← وحدة systemd
├── client/
│   └── tuxcut.py         ← واجهة PyQt6 (مستخدم عادي)
├── requirements.txt
└── install.sh
```

الـ daemon يعمل على `127.0.0.1:8013` — الواجهة لا تحتاج root.

---

## المميزات

| الميزة | الوصف |
|---|---|
| **Scan** | مسح الشبكة /24 بـ ARP |
| **Cut** | قطع إنترنت أي جهاز |
| **Resume** | استعادة الاتصال |
| **Protect** | حماية من ARP Spoofing (nftables) |
| **Change MAC** | تغيير MAC عشوائياً |
| **Alias** | أسماء مخصصة للأجهزة |

---

## ما تغيّر عن الأصل

| الأصل | TuxCut-NG |
|---|---|
| wxPython | **PyQt6** (Wayland-native) |
| arptables | **nftables** + fallback |
| ifconfig | **ip link** (iproute2) |
| netifaces | **ip route** |
| Python 3.6-3.12 | **Python 3.11-3.14** |

---

## إلغاء التثبيت

```bash
# RPM
sudo dnf remove tuxcut-ng

# DEB
sudo apt remove tuxcut-ng
```

---

## الترخيص

GPL-3.0

---

> ⚠️ للاستخدام التعليمي وإدارة الشبكات فقط.
> استخدمه على الشبكات التي تملكها أو لديك إذن باختبارها.
