# TuxCut-NG

![Version](https://img.shields.io/badge/version-1.3.1-blue)
![Python](https://img.shields.io/badge/python-3.11--3.14-green)
![License](https://img.shields.io/badge/license-GPL--3.0-orange)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)

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

## 📦 التثبيت

### من الحزمة (الأسهل — نقرة واحدة)

```bash
# فيدورا / RHEL / AlmaLinux
sudo dnf install ./tuxcut-ng-1.3.1-1.noarch.rpm

# ديبيان / أوبونتو / Mint
sudo apt install ./tuxcut-ng_1.3.1.deb
```

> الحزم متاحة في [Releases](https://github.com/mamii76/Tuxcut/releases/latest)

### من المصدر

```bash
git clone https://github.com/mamii76/Tuxcut
cd Tuxcut
sudo bash install.sh
```

---

## 🚀 التشغيل

بعد التثبيت ابحث عن **TuxCut-NG** في قائمة التطبيقات، أو شغّله من الطرفية:

```bash
tuxcut
```

---

## ✨ المميزات

| الميزة | الوصف |
|---|---|
| **Scan** | مسح الشبكة /24 وعرض جميع الأجهزة المتصلة |
| **Cut** | قطع إنترنت أي جهاز عبر ARP Spoofing |
| **Resume** | استعادة الاتصال لأي جهاز مقطوع |
| **Protect** | حماية جهازك من هجمات ARP Spoofing |
| **Change MAC** | تغيير MAC address عشوائياً |
| **Alias** | إعطاء أسماء مخصصة للأجهزة |

---

## 🔄 ما الذي تغيّر عن البرنامج الأصلي؟

| البرنامج الأصلي | TuxCut-NG |
|---|---|
| wxPython | **PyQt6** (Wayland-native) |
| arptables | **nftables** + fallback |
| ifconfig | **ip link** (iproute2) |
| netifaces | **ip route** (بدون تبعيات) |
| Python 3.6–3.12 | **Python 3.11–3.14** |
| Fedora 43+ ❌ | ✅ |
| Ubuntu 26.04 ❌ | ✅ |
| Debian 13 ❌ | ✅ |

---

## 🏗️ البنية

```
Tuxcut/
├── server/
│   ├── tuxcutd.py        ← daemon يعمل كـ root عبر systemd
│   └── tuxcutd.service   ← وحدة systemd
├── client/
│   └── tuxcut.py         ← واجهة PyQt6 (لا تحتاج root)
├── requirements.txt
└── install.sh
```

الـ daemon يعمل على `127.0.0.1:8013` — الواجهة تتصل به محلياً.

---

## 🗑️ إلغاء التثبيت

```bash
# RPM
sudo dnf remove tuxcut-ng

# DEB
sudo apt remove tuxcut-ng
```

---

## 📋 متطلبات التشغيل

- Linux kernel ≥ 4.2
- Python ≥ 3.11
- nftables أو arptables
- iproute2

---

## 📜 سجل الإصدارات

| الإصدار | التغييرات |
|---|---|
| v1.3.1 | إعادة كتابة كاملة — يعمل بشكل صحيح ✅ |
| v1.3.0 | إضافة أيقونات SVG |
| v1.2.1 | تثبيت تلقائي للمتطلبات |
| v1.2.0 | دعم Ubuntu 26.04 و Debian 13 |
| v1.1.0 | إصلاح أخطاء التشغيل |
| v1.0.0 | الإصدار الأول |

---

## ⚠️ تنبيه

للاستخدام التعليمي وإدارة الشبكات فقط.
استخدمه على الشبكات التي تملكها أو لديك إذن باختبارها.

---

## 📄 الترخيص

GPL-3.0 — مستند إلى [TuxCut](https://github.com/a-atalla/tuxcut) بواسطة a-atalla
