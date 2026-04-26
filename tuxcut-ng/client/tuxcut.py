#!/usr/bin/env python3
"""TuxCut-NG client — run as normal user."""

import sys, os, json
import requests
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

SERVER = 'http://127.0.0.1:8013'
ALIASES_FILE = os.path.expanduser('~/.tuxcut_aliases.json')

def load_aliases():
    try:
        return json.load(open(ALIASES_FILE))
    except Exception:
        return {}

def save_aliases(d):
    json.dump(d, open(ALIASES_FILE, 'w'))


# ── Background thread for slow operations ─────────────────────────────
class Worker(QThread):
    result = pyqtSignal(object)
    error  = pyqtSignal(str)
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
    def run(self):
        try:
            self.result.emit(self.fn())
        except Exception as e:
            self.error.emit(str(e))


# ── Main Window ───────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('TuxCut-NG')
        self.resize(800, 480)
        self.gw      = {}
        self.my      = {}
        self.hosts   = []
        self.cut_ips = set()
        self.aliases = load_aliases()
        self._threads = []   # keep references alive

        self._build_ui()
        self._start()

    # ─── UI ────────────────────────────────────────────────────────────
    def _build_ui(self):
        tb = self.addToolBar('tools')
        tb.setMovable(False)
        for label, slot in [
            ('🔄 Refresh',    self.do_refresh),
            ('✂️ Cut',        self.do_cut),
            ('▶️ Resume',     self.do_resume),
            ('🎭 Change MAC', self.do_change_mac),
            ('🏷️ Alias',     self.do_alias),
        ]:
            a = QAction(label, self)
            a.triggered.connect(slot)
            tb.addAction(a)
        tb.addSeparator()
        self.chk_protect = QCheckBox('🛡️ Protect me')
        self.chk_protect.stateChanged.connect(self.do_protect)
        tb.addWidget(self.chk_protect)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ['Status', 'IP', 'MAC', 'Hostname', 'Alias'])
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.setCentralWidget(self.table)

        self.statusBar().showMessage('Starting …')

    # ─── Init ──────────────────────────────────────────────────────────
    def _start(self):
        try:
            r = requests.get(f'{SERVER}/status', timeout=3)
            assert r.json()['status'] == 'success'
        except Exception:
            QMessageBox.critical(self, 'Error',
                'Daemon not running.\n\nStart it:\n  sudo python3 server/tuxcutd.py')
            sys.exit(1)

        self.gw = requests.get(f'{SERVER}/gw', timeout=10).json().get('gw', {})
        iface   = self.gw.get('iface', '')
        if iface:
            self.my = requests.get(f'{SERVER}/my/{iface}', timeout=5).json().get('my', {})

        self.setWindowTitle(
            f'TuxCut-NG  —  '
            f'My: {self.my.get("ip","")} ({self.my.get("mac","")})  |  '
            f'GW: {self.gw.get("ip","")} ({self.gw.get("mac","")})')
        self.do_refresh()

    # ─── Actions ───────────────────────────────────────────────────────
    def do_refresh(self):
        gw_ip = self.gw.get('ip', '')
        if not gw_ip:
            return
        self.statusBar().showMessage('Scanning …')
        t = Worker(lambda: requests.get(
            f'{SERVER}/scan/{gw_ip}', timeout=60).json()['result']['hosts'])
        t.result.connect(self._on_scan_done)
        t.error.connect(lambda e: self.statusBar().showMessage(f'Error: {e}'))
        self._run(t)

    def _on_scan_done(self, hosts):
        self.hosts = hosts
        self._fill_table()
        self.statusBar().showMessage(f'Found {len(hosts)} hosts')

    def do_cut(self):
        host = self._selected()
        if not host:
            return
        if host['ip'] in (self.my.get('ip'), self.gw.get('ip')):
            QMessageBox.warning(self, 'Warning', 'Cannot cut yourself or the gateway.')
            return
        requests.post(f'{SERVER}/cut', json=host, timeout=5)
        self.cut_ips.add(host['ip'])
        self._fill_table()
        self.statusBar().showMessage(f'✂️ {host["ip"]} cut')

    def do_resume(self):
        host = self._selected()
        if not host:
            return
        self.statusBar().showMessage(f'Resuming {host["ip"]} …')
        t = Worker(lambda: requests.post(f'{SERVER}/resume', json=host, timeout=15))
        t.result.connect(lambda _: self._resumed(host))
        t.error.connect(lambda e: self.statusBar().showMessage(f'Error: {e}'))
        self._run(t)

    def _resumed(self, host):
        self.cut_ips.discard(host['ip'])
        self._fill_table()
        self.statusBar().showMessage(f'▶️ {host["ip"]} resumed')

    def do_change_mac(self):
        iface = self.gw.get('iface', '')
        if not iface:
            return
        if QMessageBox.question(self, 'Change MAC',
                f'Randomize MAC of "{iface}"?') != QMessageBox.StandardButton.Yes:
            return
        r = requests.get(f'{SERVER}/change-mac/{iface}', timeout=10).json()['result']
        if r['status'] == 'success':
            self.my['mac'] = r['new_mac']
            self.statusBar().showMessage(f'New MAC: {r["new_mac"]}')
        else:
            self.statusBar().showMessage('MAC change failed')

    def do_alias(self):
        host = self._selected()
        if not host:
            return
        alias, ok = QInputDialog.getText(
            self, 'Alias', f'Alias for {host["mac"]}:',
            text=self.aliases.get(host['mac'], ''))
        if ok:
            if alias.strip():
                self.aliases[host['mac']] = alias.strip()
            else:
                self.aliases.pop(host['mac'], None)
            save_aliases(self.aliases)
            self._fill_table()

    def do_protect(self, state):
        if state == Qt.CheckState.Checked.value:
            requests.post(f'{SERVER}/protect', data={
                'ip': self.gw.get('ip', ''),
                'mac': self.gw.get('mac', ''),
                'iface': self.gw.get('iface', ''),
            }, timeout=5)
            self.statusBar().showMessage('🛡️ Protection ON')
        else:
            requests.get(f'{SERVER}/unprotect', timeout=5)
            self.statusBar().showMessage('🛡️ Protection OFF')

    # ─── Table ─────────────────────────────────────────────────────────
    def _fill_table(self):
        self.table.setRowCount(0)
        for h in self.hosts:
            row = self.table.rowCount()
            self.table.insertRow(row)
            cut = h['ip'] in self.cut_ips
            for col, val in enumerate([
                '🔴 Offline' if cut else '🟢 Online',
                h['ip'], h['mac'], h['hostname'],
                self.aliases.get(h['mac'], ''),
            ]):
                item = QTableWidgetItem(val)
                if cut:
                    item.setForeground(QColor('#c0392b'))
                self.table.setItem(row, col, item)

    def _selected(self):
        row = self.table.currentRow()
        if row < 0:
            self.statusBar().showMessage('Select a host first')
            return None
        g = lambda c: (self.table.item(row, c) or QTableWidgetItem('')).text()
        return {'ip': g(1), 'mac': g(2), 'hostname': g(3)}

    def _run(self, thread):
        self._threads.append(thread)
        thread.finished.connect(lambda: self._threads.remove(thread)
                                if thread in self._threads else None)
        thread.start()

    def closeEvent(self, e):
        try: requests.get(f'{SERVER}/unprotect', timeout=2)
        except Exception: pass
        e.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName('TuxCut-NG')
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
