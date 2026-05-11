#!/usr/bin/env python3
"""TuxCut-NG v1.3.1 — Client (run as normal user)"""

import sys, os, json, logging
from pathlib import Path
import requests
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

SERVER      = 'http://127.0.0.1:8013'
APP_DIR     = os.path.join(str(Path.home()), '.tuxcut')
ALIASES_FILE = os.path.join(APP_DIR, 'aliases.json')
Path(APP_DIR).mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('tuxcut-client')
fh = logging.FileHandler(os.path.join(APP_DIR, 'tuxcut.log'))
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)

def load_aliases():
    try:
        return json.load(open(ALIASES_FILE, encoding='utf-8'))
    except Exception:
        return {}

def save_aliases(d):
    with open(ALIASES_FILE, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False)

# ── SVG Icons (مدمجة — لا ملفات خارجية) ──────────────────────────────

def svg_icon(svg):
    px = QPixmap()
    px.loadFromData(svg.encode())
    return QIcon(px)

ICO_APP = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<polygon points="32,2 60,16 60,42 32,62 4,42 4,16" fill="#2c3e50"/>
<polygon points="32,8 54,20 54,40 32,56 10,40 10,20" fill="#2980b9"/>
<text x="32" y="43" text-anchor="middle" font-size="26"
  fill="white" font-family="sans-serif" font-weight="bold">T</text></svg>'''

ICO_REFRESH = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<circle cx="16" cy="16" r="14" fill="#27ae60"/>
<text x="16" y="22" text-anchor="middle" font-size="20"
  fill="white" font-family="sans-serif">&#8635;</text></svg>'''

ICO_CUT = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<circle cx="16" cy="16" r="14" fill="#c0392b"/>
<text x="16" y="22" text-anchor="middle" font-size="16"
  fill="white" font-family="sans-serif">&#9986;</text></svg>'''

ICO_RESUME = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<circle cx="16" cy="16" r="14" fill="#2980b9"/>
<text x="17" y="22" text-anchor="middle" font-size="16"
  fill="white" font-family="sans-serif">&#9658;</text></svg>'''

ICO_MAC = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<circle cx="16" cy="16" r="14" fill="#8e44ad"/>
<text x="16" y="21" text-anchor="middle" font-size="11"
  fill="white" font-family="sans-serif" font-weight="bold">MAC</text></svg>'''

ICO_ALIAS = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<circle cx="16" cy="16" r="14" fill="#e67e22"/>
<text x="16" y="22" text-anchor="middle" font-size="15"
  fill="white" font-family="sans-serif" font-weight="bold">A</text></svg>'''

ICO_EXIT = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<circle cx="16" cy="16" r="14" fill="#7f8c8d"/>
<text x="16" y="22" text-anchor="middle" font-size="16"
  fill="white" font-family="sans-serif">&#10005;</text></svg>'''

ICO_ONLINE = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">
<circle cx="8" cy="8" r="6" fill="#27ae60"/></svg>'''

ICO_OFFLINE = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">
<circle cx="8" cy="8" r="6" fill="#c0392b"/></svg>'''

def mk_icon(data):
    px = QPixmap()
    px.loadFromData(data)
    return QIcon(px)


# ── Background worker ──────────────────────────────────────────────────

class Worker(QThread):
    done  = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
    def run(self):
        try:
            self.done.emit(self.fn())
        except Exception as e:
            self.error.emit(str(e))


# ── Main Window ────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('TuxCut-NG')
        self.setWindowIcon(mk_icon(ICO_APP))
        self.resize(820, 500)
        self._gw           = {}
        self._my           = {}
        self.live_hosts    = []
        self._offline_ips  = []
        self.aliases       = load_aliases()
        self._threads      = []

        self._build_ui()

        # تحقق من الخادم
        if not self._server_ok():
            QMessageBox.critical(
                self, 'TuxCut Server stopped',
                'Use "systemctl start tuxcutd" then restart the application')
            sys.exit(1)

        self._load_gw()
        self._load_my(self._gw.get('iface', ''))
        self._update_title()
        self.trigger_thread()

    # ── بناء الواجهة ────────────────────────────────────────────────

    def _build_ui(self):
        tb = self.addToolBar('Main')
        tb.setMovable(False)
        tb.setIconSize(QSize(32, 32))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        def add_action(icon_data, tooltip, slot):
            a = QAction(mk_icon(icon_data), tooltip, self)
            a.setToolTip(tooltip)
            a.triggered.connect(slot)
            tb.addAction(a)
            return a

        add_action(ICO_REFRESH, 'Refresh',           self.on_refresh)
        add_action(ICO_CUT,     'Cut',               self.on_cut)
        add_action(ICO_RESUME,  'Resume',            self.on_resume)
        tb.addSeparator()
        add_action(ICO_MAC,     'Change MAC Address', self.on_change_mac)
        add_action(ICO_ALIAS,   'Give an alias',      self.on_give_alias)
        tb.addSeparator()

        self.cb_protection = QCheckBox('Protection')
        self.cb_protection.setToolTip('Enable/Disable ARP spoofing protection')
        self.cb_protection.stateChanged.connect(self.toggle_protection)
        tb.addWidget(self.cb_protection)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        add_action(ICO_EXIT, 'Exit', self.on_exit)

        # جدول الأجهزة — نفس أعمدة البرنامج الأصلي
        self.hosts_view = QTableWidget(0, 5)
        self.hosts_view.setHorizontalHeaderLabels(
            ['', 'IP Address', 'MAC Address', 'Hostname', 'Alias'])
        hdr = self.hosts_view.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.hosts_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.hosts_view.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.hosts_view.verticalHeader().setVisible(False)
        self.hosts_view.setAlternatingRowColors(True)
        self.hosts_view.setShowGrid(False)
        self.hosts_view.setIconSize(QSize(14, 14))
        self.setCentralWidget(self.hosts_view)
        self.statusBar().showMessage('Ready')

    # ── تواصل مع الخادم ──────────────────────────────────────────────

    def _server_ok(self):
        try:
            r = requests.get(f'{SERVER}/status', timeout=3)
            return r.ok and r.json()['status'] == 'success'
        except Exception:
            return False

    def _load_gw(self):
        try:
            r = requests.get(f'{SERVER}/gw', timeout=10)
            d = r.json()
            if d['status'] == 'success':
                self._gw = d['gw']
            else:
                QMessageBox.critical(self, 'Error', d.get('msg', ''))
                sys.exit(1)
        except Exception as e:
            logger.error(e, exc_info=True)

    def _load_my(self, iface):
        try:
            r = requests.get(f'{SERVER}/my/{iface}', timeout=5)
            if r.json()['status'] == 'success':
                self._my = r.json()['my']
        except Exception as e:
            logger.error(e, exc_info=True)

    def _update_title(self):
        self.setWindowTitle(
            f'TuxCut-NG  —  '
            f'My IP: {self._my.get("ip", "")}  |  '
            f'GW: {self._gw.get("ip", "")}  [{self._gw.get("iface", "")}]')

    # ── الأزرار ───────────────────────────────────────────────────────

    def trigger_thread(self):
        self.statusBar().showMessage('Refreshing hosts list ...')
        ip = self._my.get('ip', self._gw.get('ip', ''))
        t = Worker(lambda: requests.get(
            f'{SERVER}/scan/{ip}', timeout=60
        ).json()['result']['hosts'])
        t.done.connect(self.fill_hosts_view)
        t.error.connect(lambda e: self.statusBar().showMessage(f'Error: {e}'))
        self._run(t)

    def on_refresh(self, _=None):
        self.trigger_thread()

    def on_cut(self, _=None):
        row = self.hosts_view.currentRow()
        if row < 0:
            self.statusBar().showMessage('please select a victim to cut')
            return
        victim = self._row_to_host(row)
        if victim['ip'] in (self._my.get('ip'), self._gw.get('ip')):
            QMessageBox.warning(self, 'Warning',
                                'Cannot cut yourself or the gateway.')
            return
        try:
            r = requests.post(f'{SERVER}/cut', json=victim, timeout=5)
            if r.ok and r.json()['status'] == 'success':
                if victim['ip'] not in self._offline_ips:
                    self._offline_ips.append(victim['ip'])
                self.hosts_view.item(row, 0).setIcon(mk_icon(ICO_OFFLINE))
                for col in range(1, 5):
                    item = self.hosts_view.item(row, col)
                    if item:
                        item.setForeground(QColor('#c0392b'))
                self.statusBar().showMessage(
                    f'{victim["ip"]} is now offline')
        except Exception as e:
            self.statusBar().showMessage(f'Error: {e}')

    def on_resume(self, _=None):
        row = self.hosts_view.currentRow()
        if row < 0:
            self.statusBar().showMessage('please select a victim to resume')
            return
        victim = self._row_to_host(row)
        self.statusBar().showMessage(f'Resuming {victim["ip"]} ...')
        t = Worker(lambda: requests.post(
            f'{SERVER}/resume', json=victim, timeout=15))
        def _done(_):
            if victim['ip'] in self._offline_ips:
                self._offline_ips.remove(victim['ip'])
            self.hosts_view.item(row, 0).setIcon(mk_icon(ICO_ONLINE))
            for col in range(1, 5):
                item = self.hosts_view.item(row, col)
                if item:
                    item.setForeground(QColor('#000000'))
            self.statusBar().showMessage(f'{victim["ip"]} is back online')
        t.done.connect(_done)
        t.error.connect(lambda e: self.statusBar().showMessage(f'Error: {e}'))
        self._run(t)

    def on_change_mac(self, _=None):
        iface = self._gw.get('iface', '')
        if not iface:
            return
        try:
            r = requests.get(f'{SERVER}/change-mac/{iface}', timeout=10)
            result = r.json().get('result', {})
            if result.get('status') == 'success':
                new_mac = result.get('new_mac', '')
                self._my['mac'] = new_mac
                self._update_title()
                self.statusBar().showMessage(f'MAC changed to {new_mac}')
            else:
                self.statusBar().showMessage("Couldn't change MAC")
        except Exception as e:
            self.statusBar().showMessage(f'Error: {e}')

    def on_give_alias(self, _=None):
        row = self.hosts_view.currentRow()
        if row < 0:
            QMessageBox.critical(self, 'No Computer selected',
                                 'Please select a computer from the list')
            return
        victim = self._row_to_host(row)
        alias, ok = QInputDialog.getText(
            self, 'Give Alias',
            f'Enter an alias for the computer with MAC "{victim["mac"]}" !',
            text=self.aliases.get(victim['mac'], ''))
        if ok:
            if alias.strip():
                self.aliases[victim['mac']] = alias.strip()
            else:
                self.aliases.pop(victim['mac'], None)
            save_aliases(self.aliases)
            self.trigger_thread()

    def toggle_protection(self, state):
        if state == Qt.CheckState.Checked.value:
            self._protect()
        else:
            self._unprotect()

    def _protect(self):
        try:
            requests.post(f'{SERVER}/protect', data={
                'ip':    self._gw.get('ip', ''),
                'mac':   self._gw.get('mac', ''),
                'iface': self._gw.get('iface', ''),
            }, timeout=5)
            self.statusBar().showMessage('Protection Enabled')
        except Exception as e:
            logger.error(e, exc_info=True)

    def _unprotect(self):
        try:
            requests.get(f'{SERVER}/unprotect', timeout=5)
            self.statusBar().showMessage('Protection Disabled')
        except Exception as e:
            logger.error(e, exc_info=True)

    def on_exit(self, _=None):
        self._unprotect()
        save_aliases(self.aliases)
        self.close()

    # ── جدول الأجهزة ─────────────────────────────────────────────────

    def fill_hosts_view(self, hosts):
        self.live_hosts = hosts
        self.hosts_view.setRowCount(0)
        ico_on  = mk_icon(ICO_ONLINE)
        ico_off = mk_icon(ICO_OFFLINE)
        for host in hosts:
            row = self.hosts_view.rowCount()
            self.hosts_view.insertRow(row)
            cut = host['ip'] in self._offline_ips

            item0 = QTableWidgetItem()
            item0.setIcon(ico_off if cut else ico_on)
            self.hosts_view.setItem(row, 0, item0)

            for col, val in enumerate([
                host['ip'], host['mac'], host['hostname'],
                self.aliases.get(host['mac'], '')
            ], start=1):
                item = QTableWidgetItem(val)
                if cut:
                    item.setForeground(QColor('#c0392b'))
                self.hosts_view.setItem(row, col, item)

        self.statusBar().showMessage('Ready')

    def _row_to_host(self, row):
        def txt(col):
            i = self.hosts_view.item(row, col)
            return i.text() if i else ''
        return {'ip': txt(1), 'mac': txt(2), 'hostname': txt(3)}

    def _run(self, t):
        self._threads.append(t)
        t.finished.connect(
            lambda: self._threads.remove(t) if t in self._threads else None)
        t.start()

    def closeEvent(self, e):
        self._unprotect()
        save_aliases(self.aliases)
        e.accept()


# ── Entry point ───────────────────────────────────────────────────────

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName('TuxCut-NG')
    app.setWindowIcon(mk_icon(ICO_APP))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
