"""
HardwareConfig main window.

Assembles the preset list (left) and parameter editor (right)
into a split-pane layout. Provides toolbar actions for settings
and generating Motor_Model.h output.
"""

import os
import json
from typing import Optional

from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QMenuBar,
    QAction,
    QFileDialog,
    QMessageBox,
    QStatusBar,
    QPushButton,
    QLabel,
    QLineEdit,
    QToolBar,
    QSizePolicy,
    QApplication,
)

from ui.styles import app_stylesheet
from ui.preset_list import PresetListPanel
from ui.param_editor import ParamEditorPanel
from core.parser import parse_motor_header
from core.generator import generate_motor_model

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def _load_config() -> dict:
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {}


def _save_config(cfg: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MotorAI — 电机硬件配置")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        self._gmp_root: str = ""
        self._output_path: str = ""
        self._current_params: dict[str, Optional[float]] = {}

        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._apply_style()

        # Restore saved config
        cfg = _load_config()
        gmp_root = cfg.get("gmp_root", "")
        if gmp_root and os.path.isdir(gmp_root):
            self._gmp_root = gmp_root
            self._preset_list.set_gmp_root(gmp_root)
        else:
            self._prompt_gmp_root()

        self._output_path = cfg.get("output_dir", "")

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("文件(&F)")

        set_gmp = QAction("设置 GMP 根目录...", self)
        set_gmp.triggered.connect(self._prompt_gmp_root)
        file_menu.addAction(set_gmp)

        file_menu.addSeparator()

        quit_action = QAction("退出(&Q)", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _build_toolbar(self):
        tb = QToolBar("生成")
        tb.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, tb)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        # Output path display + browse
        path_label = QLabel("输出路径:")
        tb.addWidget(path_label)

        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("选择 Motor_Model.h 输出位置...")
        self._output_edit.setMinimumWidth(320)
        self._output_edit.setMaximumWidth(500)
        self._output_edit.setObjectName("searchBox")
        if self._output_path:
            self._output_edit.setText(self._output_path)
        tb.addWidget(self._output_edit)

        browse_btn = QPushButton("浏览")
        browse_btn.setObjectName("secondaryButton")
        browse_btn.clicked.connect(self._browse_output)
        tb.addWidget(browse_btn)

        tb.addSeparator()

        generate_btn = QPushButton("生成 Motor_Model.h")
        generate_btn.setObjectName("primaryButton")
        generate_btn.clicked.connect(self._generate)
        tb.addWidget(generate_btn)

    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 8, 12, 8)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        # Left: preset list
        self._preset_list = PresetListPanel()
        self._preset_list.preset_selected.connect(self._on_preset_selected)
        splitter.addWidget(self._preset_list)

        # Right: parameter editor
        self._param_editor = ParamEditorPanel()
        self._param_editor.param_changed.connect(self._on_param_changed)
        splitter.addWidget(self._param_editor)

        # Ratio: ~1:3
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([280, 900])

        root_layout.addWidget(splitter)

    def _build_statusbar(self):
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("请选择预设电机，或设置 GMP 根目录。")

    def _apply_style(self):
        self.setStyleSheet(app_stylesheet())

    # ------------------------------------------------------------------
    # Slots — GMP root
    # ------------------------------------------------------------------

    def _prompt_gmp_root(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择 GMP 根目录", self._gmp_root or os.getcwd()
        )
        if path:
            self._gmp_root = path
            self._preset_list.set_gmp_root(path)
            cfg = _load_config()
            cfg["gmp_root"] = path
            _save_config(cfg)
            self._status.showMessage(f"GMP 根目录: {path}")

    # ------------------------------------------------------------------
    # Slots — Output path
    # ------------------------------------------------------------------

    def _browse_output(self):
        default_dir = os.path.dirname(self._output_path) if self._output_path else ""
        if not default_dir or not os.path.isdir(default_dir):
            default_dir = self._gmp_root or os.getcwd()

        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存 Motor_Model.h",
            os.path.join(default_dir, "Motor_Model.h"),
            "Header files (*.h);;All files (*)",
        )
        if path:
            self._output_path = path
            self._output_edit.setText(path)
            cfg = _load_config()
            cfg["output_dir"] = path
            _save_config(cfg)

    # ------------------------------------------------------------------
    # Slots — Preset selection
    # ------------------------------------------------------------------

    def _on_preset_selected(self, filepath: str, params: dict):
        """Load a preset into the editor."""
        self._current_params = dict(params)
        self._param_editor.load_params(params, flux_locked=True)
        name = os.path.splitext(os.path.basename(filepath))[0]
        self._status.showMessage(f"已加载预设: {name}")

    # ------------------------------------------------------------------
    # Slots — Parameter changes
    # ------------------------------------------------------------------

    def _on_param_changed(self, macro: str, value: Optional[float]):
        """Track edits and trigger FLUX recalculation if needed."""
        self._current_params[macro] = value

        # When KV or POLE_PAIRS change, update FLUX if locked
        if macro in ("MOTOR_PARAM_KV", "MOTOR_PARAM_POLE_PAIRS"):
            self._param_editor.on_kv_or_pole_pairs_changed()

    # ------------------------------------------------------------------
    # Slots — Generate
    # ------------------------------------------------------------------

    def _generate(self):
        """Generate Motor_Model.h from current parameters."""
        # Ensure we have an output path
        if not self._output_path:
            self._browse_output()
            if not self._output_path:
                return

        # Collect current params
        params = self._param_editor.get_all_params()
        flux_locked = self._param_editor.is_flux_locked()
        preset_name = self._preset_list.current_preset_name() or ""

        try:
            generate_motor_model(
                params,
                self._output_path,
                preset_name=preset_name,
                flux_locked=flux_locked,
            )
            QMessageBox.information(
                self,
                "生成完成",
                f"Motor_Model.h 已保存至:\n{self._output_path}",
            )
            self._status.showMessage(f"已生成: {self._output_path}")
        except Exception as e:
            QMessageBox.critical(
                self,
                "生成失败",
                f"无法写入文件:\n{e}",
            )

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        cfg = _load_config()
        cfg["gmp_root"] = self._gmp_root
        cfg["output_dir"] = self._output_path
        _save_config(cfg)
        super().closeEvent(event)
