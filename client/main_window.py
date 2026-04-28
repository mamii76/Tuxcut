"""
TuxCut-NG  —  main_window.py
PyQt6 GUI — works on Wayland (Fedora 43+) and X11 (Debian 12+).
"""

import sys
import os
import shelve
import requests
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QTableWidget, QTableWidgetItem,
    QToolBar, QStatusBar, QMessageBox, QInputDialog,
    QHeaderView, QAbstractItemView, QCheckBox, QLabel,
    QWidget, QHBoxLayout, QSizePolicy, QDialog, QDialogButtonBox,
    QVBoxLayout, QGridLayout, QLineEdit, QGroupBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QIcon, QColor, QFont, QAction, QBrush

SERVER = 'http://127.0.0.1:8013'
APP_DIR = os.path.join(str(Path.home()), '.tuxcut')
os.makedirs(APP_DIR, exist_ok=True)

# ── column indices ──────────────────────────────────────────────────
C_STATUS, C_IP, C_MAC, C_HOST, C_ALIAS = 0, 1, 2, 3, 4


# ────────────────────── Background Threads ──────────────────────────

class ScanThread(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, ip: str):
        super().__init__()
        self.ip = ip

    def run(self):
        try:
            r = requests.get(f'{SERVER}/scan/{self.ip}', timeout=60)
            if r.ok:
                self.done.emit(r.json()['result']['hosts'])
            else:
                self.error.emit(f'HTTP {r.status_code}')
        except Exception as e:
            self.error.emit(str(e))


class ResumeThread(QThread):
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, victim: dict):
        super().__init__()
        self.victim = victim

    def run(self):
        try:
            r = requests.post(f'{SERVER}/resume', json=self.victim, timeout=15)
            if r.ok and r.json()['status'] == 'success':
                self.done.emit(self.victim)
            else:
                self.error.emit('Resume failed')
        except Exception as e:
            self.error.emit(str(e))


# ──────────────────────────── Main Window ───────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('TuxCut-NG')
        self.setMinimumSize(820, 520)

        self._gw:           dict = {}
        self._my:           dict = {}
        self.live_hosts:    list = []
        self.offline_hosts: set  = set()
        self.aliases = shelve.open(os.path.join(APP_DIR, 'aliases.db'))

        self._build_ui()
        self._init()

    # ─────────────────────── UI construction ──────────────────────

    def _build_ui(self):
        # ── toolbar ──
        tb = QToolBar('Main')
        tb.setIconSize(QSize(20, 20))
        tb.setMovable(False)
        self.addToolBar(tb)

        def _act(label, tip, slot):
            a = QAction(label, self)
            a.setToolTip(tip)
            a.triggered.connect(slot)
            tb.addAction(a)
            return a

        _act('🔄  Refresh',      'Scan the network again',           self.on_refresh)
        _act('✂️  Cut',          'Disconnect the selected host',      self.on_cut)
        _act('▶️  Resume',       'Restore the selected host',         self.on_resume)
        tb.addSeparator()
        _act('🎭  Change MAC',   'Randomize this machine\'s MAC',     self.on_change_mac)
        _act('🏷️  Set Alias',    'Give the selected host a nickname', self.on_alias)
        tb.addSeparator()

        # Protection toggle
        self.cb_protect = QCheckBox('🛡️  Protect me')
        self.cb_protect.setToolTip(
            'Block forged ARP packets targeting this machine (nftables/arptables)')
        self.cb_protect.stateChanged.connect(self._on_protect_toggle)
        tb.addWidget(self.cb_protect)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        _act('❌  Exit', 'Exit TuxCut-NG', self.on_exit)

        # ── host table ──
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ['Status', 'IP Address', 'MAC Address', 'Hostname', 'Alias'])

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(C_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(C_IP,     QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(C_MAC,    QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(C_HOST,   QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(C_ALIAS,  QHeaderView.ResizeMode.ResizeToContents)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.setCentralWidget(self.table)

        # ── info bar (gateway / my info) ──
        info_bar = QToolBar('Info')
        info_bar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, info_bar)
        self._lbl_gw = QLabel()
        self._lbl_my = QLabel()
        info_bar.addWidget(QLabel('  Gateway: '))
        info_bar.addWidget(self._lbl_gw)
        info_bar.addSeparator()
        info_bar.addWidget(QLabel('  My Info: '))
        info_bar.addWidget(self._lbl_my)

        # ── status bar ──
        self.status = self.statusBar()
        self.status.showMessage('Starting …')

    # ─────────────────────────── Init ─────────────────────────────

    def _init(self):
        if not self._check_server():
            QMessageBox.critical(
                self, 'TuxCut-NG — Server Not Found',
                'The TuxCut-NG daemon is not running.\n\n'
                'Start it with:\n    sudo systemctl start tuxcutd\n\n'
                'Then relaunch this application.')
            sys.exit(1)

        self._load_gw()
        self._load_my()

        gw = self._gw
        self._lbl_gw.setText(
            f'{gw.get("ip", "?")}  ({gw.get("mac", "?")})'
            f'  [{gw.get("iface", "?")}]')
        my = self._my
        self._lbl_my.setText(
            f'{my.get("ip", "?")}  ({my.get("mac", "?")})')

        self.on_refresh()

    # ─────────────────── Server communication ─────────────────────

    def _get(self, path: str, **kw):
        return requests.get(f'{SERVER}{path}', timeout=kw.pop('timeout', 8), **kw)

    def _post(self, path: str, **kw):
        return requests.post(f'{SERVER}{path}', timeout=kw.pop('timeout', 8), **kw)

    def _check_server(self) -> bool:
        try:
            r = self._get('/status', timeout=4)
            return r.ok and r.json().get('status') == 'success'
        except Exception:
            return False

    def _load_gw(self):
        try:
            r = self._get('/gw', timeout=12)
            d = r.json()
            if d['status'] == 'success':
                self._gw = d['gw']
            else:
                QMessageBox.critical(self, 'Error', d.get('msg', 'No gateway'))
                sys.exit(1)
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))
            sys.exit(1)

    def _load_my(self):
        iface = self._gw.get('iface', '')
        if not iface:
            return
        try:
            r = self._get(f'/my/{iface}', timeout=6)
            d = r.json()
            if d['status'] == 'success':
                self._my = d['my']
        except Exception:
            pass

    # ─────────────────────── Toolbar actions ──────────────────────

    def on_refresh(self):
        ip = self._my.get('ip') or self._gw.get('ip', '')
        if not ip:
            self.status.showMessage('No IP address found')
            return
        self.status.showMessage('Scanning network …')
        self._scan_thread = ScanThread(ip)
        self._scan_thread.done.connect(self._on_scan_done)
        self._scan_thread.error.connect(
            lambda e: self.status.showMessage(f'Scan error: {e}'))
        self._scan_thread.start()

    def _on_scan_done(self, hosts: list):
        self.live_hosts = hosts
        self._fill_table(hosts)
        self.status.showMessage(
            f'✅  Found {len(hosts)} host{"s" if len(hosts) != 1 else ""}')

    def on_cut(self):
        host = self._selected_host()
        if not host:
            self.status.showMessage('⚠️  Select a host first')
            return
        if host['ip'] == self._my.get('ip') or host['ip'] == self._gw.get('ip'):
            QMessageBox.warning(self, 'Warning',
                'You cannot cut your own machine or the gateway.')
            return
        try:
            r = self._post('/cut', json=host)
            if r.ok and r.json()['status'] == 'success':
                self.offline_hosts.add(host['ip'])
                self._refresh_row(host['ip'])
                self.status.showMessage(f'✂️  {host["ip"]} disconnected')
        except Exception as e:
            self.status.showMessage(f'Error: {e}')

    def on_resume(self):
        host = self._selected_host()
        if not host:
            self.status.showMessage('⚠️  Select a host first')
            return
        self.status.showMessage(f'Restoring {host["ip"]} …')
        self._resume_thread = ResumeThread(host)
        self._resume_thread.done.connect(self._on_resume_done)
        self._resume_thread.error.connect(
            lambda e: self.status.showMessage(f'Error: {e}'))
        self._resume_thread.start()

    def _on_resume_done(self, victim: dict):
        self.offline_hosts.discard(victim['ip'])
        self._refresh_row(victim['ip'])
        self.status.showMessage(f'▶️  {victim["ip"]} is back online')

    def on_change_mac(self):
        iface = self._gw.get('iface', '')
        if not iface:
            return
        reply = QMessageBox.question(
            self, 'Change MAC',
            f'Randomize MAC address of interface "{iface}"?\n'
            'Network connection will be briefly interrupted.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            r = self._get(f'/change-mac/{iface}', timeout=12)
            d = r.json()['result']
            if d['status'] == 'success':
                self.status.showMessage(f'🎭  MAC changed → {d["new_mac"]}')
                self._load_my()
                self._lbl_my.setText(
                    f'{self._my.get("ip", "?")}  ({self._my.get("mac", "?")})')
            else:
                self.status.showMessage('⚠️  MAC change failed')
        except Exception as e:
            self.status.showMessage(f'Error: {e}')

    def on_alias(self):
        host = self._selected_host()
        if not host:
            self.status.showMessage('⚠️  Select a host first')
            return
        current = self.aliases.get(host['mac'], '')
        alias, ok = QInputDialog.getText(
            self, 'Set Alias',
            f'Enter alias for  {host["mac"]}:', text=current)
        if ok:
            if alias.strip():
                self.aliases[host['mac']] = alias.strip()
            elif host['mac'] in self.aliases:
                del self.aliases[host['mac']]
            self._fill_table(self.live_hosts)

    def _on_protect_toggle(self, state):
        checked = state == Qt.CheckState.Checked.value
        try:
            if checked:
                r = self._post('/protect', data={
                    'ip':    self._gw.get('ip', ''),
                    'mac':   self._gw.get('mac', ''),
                    'iface': self._gw.get('iface', ''),
                })
                if r.ok and r.json()['status'] == 'success':
                    self.status.showMessage('🛡️  Protection ENABLED')
            else:
                r = self._get('/unprotect')
                if r.ok and r.json()['status'] == 'success':
                    self.status.showMessage('🛡️  Protection DISABLED')
        except Exception as e:
            self.status.showMessage(f'Error: {e}')

    def on_exit(self):
        try:
            self._get('/unprotect', timeout=3)
        except Exception:
            pass
        self.aliases.close()
        self.close()

    # ─────────────────────── Table helpers ────────────────────────

    def _fill_table(self, hosts: list):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for host in hosts:
            self._append_row(host)
        self.table.setSortingEnabled(True)

    def _append_row(self, host: dict):
        row = self.table.rowCount()
        self.table.insertRow(row)
        offline = host['ip'] in self.offline_hosts
        status  = '🔴  Offline' if offline else '🟢  Online'
        alias   = self.aliases.get(host['mac'], '')
        values  = [status, host['ip'], host['mac'], host['hostname'], alias]
        for col, val in enumerate(values):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            if offline:
                item.setForeground(QBrush(QColor('#c0392b')))
            self.table.setItem(row, col, item)

    def _refresh_row(self, ip: str):
        """Update status cell for one host without rebuilding the whole table."""
        for row in range(self.table.rowCount()):
            if self.table.item(row, C_IP) and self.table.item(row, C_IP).text() == ip:
                offline = ip in self.offline_hosts
                status  = '🔴  Offline' if offline else '🟢  Online'
                color   = QColor('#c0392b') if offline else QColor('#27ae60')
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item.setForeground(QBrush(color))
                self.table.item(row, C_STATUS).setText(status)
                break

    def _selected_host(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        def _txt(col): return self.table.item(row, col).text() if self.table.item(row, col) else ''
        return {'ip': _txt(C_IP), 'mac': _txt(C_MAC), 'hostname': _txt(C_HOST)}

    # ─────────────────── Window close override ────────────────────

    def closeEvent(self, event):
        try:
            self.aliases.close()
        except Exception:
            pass
        event.accept()
