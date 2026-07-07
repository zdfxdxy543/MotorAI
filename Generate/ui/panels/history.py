"""History panel — recent projects list + selected project info.

History is persisted in a single JSON file.  On refresh, entries whose project
JSON no longer exists on disk are removed automatically.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import Qt

import core.paths  # ensures repository roots are on sys.path
from core.paths import MOTORAI_ROOT
from styles.theme import current_theme

HISTORY_FILE = MOTORAI_ROOT / "Generate" / "ui" / "history.json"


# ── history storage ──────────────────────────────────────────────────

def load_history() -> list[dict]:
    """Return list of history entries, removing any whose project no longer exists."""
    if not HISTORY_FILE.exists():
        return []

    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return []

    entries = data.get("entries") if isinstance(data, dict) else []
    if not isinstance(entries, list):
        return []

    valid: list[dict] = []
    changed = False
    for entry in entries:
        if not isinstance(entry, dict):
            changed = True
            continue
        path_str = entry.get("path")
        if not isinstance(path_str, str) or not path_str.strip():
            changed = True
            continue
        if not Path(path_str).exists():
            changed = True
            continue
        valid.append(entry)

    if changed:
        _save_entries(valid)

    return valid


def _save_entries(entries: list[dict]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_to_history(json_path: Path | str) -> None:
    """Add or update a project in the history file."""
    json_path = Path(json_path).expanduser().resolve()
    if not json_path.exists():
        return

    entries = load_history()
    path_str = str(json_path)

    # Try to read the project name from the JSON.
    name = json_path.parent.name
    try:
        data = json.loads(json_path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            name = data.get("project_name") or name
    except Exception:
        pass

    # Update existing or append new.
    for entry in entries:
        if entry.get("path") == path_str:
            entry["name"] = name
            entry["last_opened"] = time.time()
            _save_entries(entries)
            return

    entries.append({"name": name, "path": path_str, "last_opened": time.time()})
    _save_entries(entries)


# ── panel widget ─────────────────────────────────────────────────────

class HistoryPanel(QWidget):
    """Left sidebar: project list (top) + project details (bottom)."""

    def __init__(
        self,
        on_project_selected: Callable[[Path], None] | None = None,
        on_project_opened: Callable[[Path], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._on_project_selected = on_project_selected
        self._on_project_opened = on_project_opened

        t = current_theme()

        # ── project list ──────────────────────────────────────────
        self.project_list = QListWidget()
        self.project_list.setFrameShape(QFrame.NoFrame)
        self.project_list.itemClicked.connect(self._on_item_clicked)
        self.project_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.project_list.setStyleSheet(
            f"QListWidget{{background:{t.surface};border:none;}}"
            f"QListWidget::item{{padding:6px 8px;border-bottom:1px solid {t.border};}}"
            f"QListWidget::item:selected{{background:{t.selection};color:{t.text_strong};}}"
            f"QListWidget::item:hover{{background:{t.panel_hover};}}"
        )

        list_header = QWidget()
        list_header_layout = QHBoxLayout(list_header)
        list_header_layout.setContentsMargins(8, 4, 8, 4)
        title_label = QLabel("历史工程")  # 历史工程
        title_label.setStyleSheet(f'font-size:12pt;font-weight:700;color:{t.text_strong};')
        list_header_layout.addWidget(title_label)

        # ── project info ──────────────────────────────────────────
        self.info_view = QTextEdit()
        self.info_view.setReadOnly(True)
        self.info_view.setPlaceholderText("单击项目查看详情")  # 单击项目查看详情
        self.info_view.setFrameShape(QFrame.NoFrame)
        self.info_view.setStyleSheet(
            f"QTextEdit{{background:{t.surface};border:none;color:{t.text};padding:8px;}}"
        )

        info_header = QWidget()
        info_header_layout = QHBoxLayout(info_header)
        info_header_layout.setContentsMargins(8, 4, 8, 4)
        info_label = QLabel("项目信息")  # 项目信息
        info_label.setStyleSheet(f'font-size:11pt;font-weight:600;color:{t.muted};')
        info_header_layout.addWidget(info_label)

        # ── splitter ──────────────────────────────────────────────
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)
        list_layout.addWidget(list_header)
        list_layout.addWidget(self.project_list)

        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(0)
        info_layout.addWidget(info_header)
        info_layout.addWidget(self.info_view)

        splitter.addWidget(list_container)
        splitter.addWidget(info_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(splitter)

    # ── public API ───────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload history from the JSON file (stale entries auto-removed)."""
        self.project_list.clear()

        for entry in load_history():
            name = entry.get("name") or "unknown"
            path_str = entry.get("path") or ""
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, path_str)
            self.project_list.addItem(item)

    # ── slots ────────────────────────────────────────────────────────

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        path_str = item.data(Qt.UserRole)
        if not path_str:
            return
        path = Path(path_str)
        self._show_info(path)
        if self._on_project_selected:
            self._on_project_selected(path)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        path_str = item.data(Qt.UserRole)
        if not path_str:
            return
        path = Path(path_str)
        if self._on_project_opened:
            self._on_project_opened(path)

    def _show_info(self, json_path: Path) -> None:
        try:
            data = json.loads(json_path.read_text(encoding="utf-8-sig"))
        except Exception:
            self.info_view.setPlainText("无法读取项目文件。")  # 无法读取项目文件。
            return

        lines = [
            f'路径：{json_path.parent}',               # 路径：
            f'候选方案数：{data.get("candidate_count", "—")}',  # 候选方案数：
            f'最大迭代：{data.get("max_iterations", "—")}',        # 最大迭代：
            f'任务类型：{data.get("task_type") or "—"}',            # 任务类型：
        ]
        if isinstance(data.get("objective"), str) and data["objective"].strip():
            lines.append(f'目标：{data["objective"].strip()}')  # 目标：
        if isinstance(data.get("design_profile"), dict):
            profile_name = data["design_profile"].get("name", "")
            if profile_name:
                lines.append(f'设计方案：{profile_name}')  # 设计方案：

        self.info_view.setPlainText("\n".join(lines))
