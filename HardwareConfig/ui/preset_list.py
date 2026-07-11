"""
Left panel: motor preset browser.

Scans <GMP_ROOT>/ctl/component/hardware_preset/pmsm_motor/*.h
and presents a searchable, selectable list.
"""

import os
from typing import Optional

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QFrame,
)

from core.parser import parse_motor_header, extract_preset_name, extract_brief_info


class PresetListItem:
    """Data container for one preset entry in the list."""

    def __init__(self, name: str, filepath: str, brief: str):
        self.name = name
        self.filepath = filepath
        self.brief = brief


class PresetListPanel(QWidget):
    """Left sidebar panel showing available motor presets."""

    preset_selected = pyqtSignal(str, dict)  # filepath, parsed_params

    def __init__(self, parent=None):
        super().__init__(parent)
        self._presets: list[PresetListItem] = []
        self._parsed_cache: dict[str, dict] = {}  # filepath → params
        self._gmp_root: str = ""
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Title
        title = QLabel("预设电机")
        title.setObjectName("sectionHeader")
        layout.addWidget(title)

        # Search box
        self._search = QLineEdit()
        self._search.setObjectName("searchBox")
        self._search.setPlaceholderText("搜索电机型号...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search)

        # Preset list
        self._list = QListWidget()
        self._list.setObjectName("presetList")
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list)

        # Status hint
        self._status = QLabel("")
        self._status.setObjectName("emptyPlaceholder")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_gmp_root(self, path: str):
        """Set GMP root and reload the preset list."""
        self._gmp_root = path
        self._parsed_cache.clear()
        self._load_presets()

    def current_preset_name(self) -> Optional[str]:
        """Return the name of the currently selected preset, if any."""
        item = self._list.currentItem()
        if item is None:
            return None
        idx = self._list.currentRow()
        if 0 <= idx < len(self._presets):
            return self._presets[idx].name
        return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _preset_dir(self) -> str:
        return os.path.join(
            self._gmp_root, "ctl", "component", "hardware_preset", "pmsm_motor"
        )

    def _load_presets(self):
        """Scan the preset directory and populate the list."""
        self._presets.clear()
        self._list.clear()

        preset_dir = self._preset_dir()
        if not os.path.isdir(preset_dir):
            self._status.setText(f"未找到预设目录:\n{preset_dir}\n\n请在菜单栏设置 GMP 根目录。")
            return

        headers = sorted(
            [
                f
                for f in os.listdir(preset_dir)
                if f.endswith(".h") and not f.startswith("_")
            ]
        )

        if not headers:
            self._status.setText(f"预设目录为空:\n{preset_dir}")
            return

        for h in headers:
            filepath = os.path.join(preset_dir, h)
            name = extract_preset_name(filepath)
            try:
                params = parse_motor_header(filepath)
                self._parsed_cache[filepath] = params
                brief = extract_brief_info(params)
            except Exception:
                brief = ""
                self._parsed_cache[filepath] = {}

            self._presets.append(PresetListItem(name, filepath, brief))

        self._populate_list(self._presets)
        self._status.setText(f"共 {len(self._presets)} 个预设电机")

    def _populate_list(self, presets: list[PresetListItem]):
        """Fill the QListWidget with preset items."""
        self._list.blockSignals(True)
        self._list.clear()
        for p in presets:
            display = p.name
            if p.brief:
                display = f"{p.name}\n  {p.brief}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, p.filepath)
            self._list.addItem(item)
        self._list.blockSignals(False)

        if presets:
            self._list.setCurrentRow(0)

    def _on_search_changed(self, text: str):
        """Filter the list based on search text."""
        q = text.strip().lower()
        if not q:
            self._populate_list(self._presets)
            return
        filtered = [p for p in self._presets if q in p.name.lower()]
        self._populate_list(filtered)

    def _on_item_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Handle preset selection."""
        if current is None:
            return
        filepath = current.data(Qt.UserRole)
        params = self._parsed_cache.get(filepath, {})
        self.preset_selected.emit(filepath, params)
