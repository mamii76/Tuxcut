"""
TuxCut-NG  —  tuxcut.py
Client entry point. Run as a normal user (NOT root).
"""

import sys
import os

# Allow importing main_window from the same directory
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from main_window import MainWindow


def main():
    # HiDPI support (Wayland / Fedora 43)
    os.environ.setdefault('QT_AUTO_SCREEN_SCALE_FACTOR', '1')

    app = QApplication(sys.argv)
    app.setApplicationName('TuxCut-NG')
    app.setApplicationVersion('1.0')
    app.setOrganizationName('TuxCut-NG')

    # Basic stylesheet — works on both Wayland and X11
    app.setStyleSheet("""
        QMainWindow {
            background-color: #1e1e2e;
        }
        QToolBar {
            background-color: #2a2a3e;
            border: none;
            padding: 4px 6px;
            spacing: 6px;
        }
        QToolBar QToolButton {
            background-color: #3a3a5c;
            color: #cdd6f4;
            border: 1px solid #585b70;
            border-radius: 5px;
            padding: 4px 10px;
            font-size: 13px;
        }
        QToolBar QToolButton:hover {
            background-color: #89b4fa;
            color: #1e1e2e;
        }
        QToolBar QToolButton:pressed {
            background-color: #74c7ec;
        }
        QCheckBox {
            color: #cdd6f4;
            font-size: 13px;
            padding: 0 6px;
        }
        QCheckBox::indicator:checked {
            background-color: #a6e3a1;
            border-radius: 3px;
        }
        QTableWidget {
            background-color: #181825;
            alternate-background-color: #1e1e2e;
            color: #cdd6f4;
            gridline-color: #313244;
            font-size: 13px;
            border: none;
        }
        QHeaderView::section {
            background-color: #313244;
            color: #89dceb;
            font-weight: bold;
            padding: 6px;
            border: none;
            border-bottom: 1px solid #585b70;
        }
        QTableWidget::item:selected {
            background-color: #89b4fa;
            color: #1e1e2e;
        }
        QStatusBar {
            background-color: #2a2a3e;
            color: #a6e3a1;
            font-size: 12px;
        }
        QLabel {
            color: #cdd6f4;
            font-size: 12px;
        }
        QMessageBox {
            background-color: #1e1e2e;
            color: #cdd6f4;
        }
        QPushButton {
            background-color: #3a3a5c;
            color: #cdd6f4;
            border: 1px solid #585b70;
            border-radius: 5px;
            padding: 5px 14px;
        }
        QPushButton:hover { background-color: #89b4fa; color: #1e1e2e; }
        QInputDialog { background-color: #1e1e2e; color: #cdd6f4; }
        QLineEdit {
            background-color: #313244;
            color: #cdd6f4;
            border: 1px solid #585b70;
            border-radius: 4px;
            padding: 4px;
        }
    """)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
