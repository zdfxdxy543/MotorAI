"""
MotorAI HardwareConfig — 电机硬件配置工具

Standalone application for browsing motor presets,
editing motor parameters, and generating Motor_Model.h.
"""

import sys
import os

# Ensure the HardwareConfig package root is on sys.path so that
# `from core.xxx` and `from ui.xxx` resolve correctly.
_PKG_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from app import MainWindow


def main():
    # High-DPI support
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("MotorAI HardwareConfig")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
