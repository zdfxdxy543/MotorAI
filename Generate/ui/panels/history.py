"""History panel — recent projects list + selected project info."""

from __future__ import annotations

import json
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
from motorai_config import get_output_root, load_settings
from styles.theme import current_theme


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
        self._projects: dict[str, Path] = {}  # display_name → json_path

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
        title_label = QLabel('历史工程')
        title_label.setStyleSheet(f'font-size:12pt;font-weight:700;color:{t.text_strong};')
        list_header_layout.addWidget(title_label)

        # ── project info ──────────────────────────────────────────
        self.info_view = QTextEdit()
        self.info_view.setReadOnly(True)
        self.info_view.setPlaceholderText('单击项目查看详情')
        self.info_view.setFrameShape(QFrame.NoFrame)
        self.info_view.setStyleSheet(
            f"QTextEdit{{background:{t.surface};border:none;color:{t.text};padding:8px;}}"
        )

        info_header = QWidget()
        info_header_layout = QHBoxLayout(info_header)
        info_header_layout.setContentsMargins(8, 4, 8, 4)
        info_label = QLabel('项目信息')
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
        """Re-scan the output directory for project JSON files."""
        self.project_list.clear()
        self._projects.clear()

        try:
            output_root = get_output_root(load_settings())
        except Exception:
            return

        if not output_root.exists():
            return

        items: list[tuple[str, Path]] = []
        for json_file in sorted(output_root.rglob("*.json")):
            if json_file.name.startswith("."):
                continue
            try:
                data = json.loads(json_file.read_text(encoding="utf-8-sig"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, dict):
                continue
            # Only list project JSONs (have candidate_count or workspace_mode)
            if "candidate_count" not in data and "workspace_mode" not in data:
                continue

            name = data.get("project_name") or json_file.parent.name
            items.append((name, json_file))

        for display_name, json_path in items:
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, str(json_path))
            self.project_list.addItem(item)
            self._projects[display_name] = json_path

    # ── slots ────────────────────────────────────────────────────────

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        json_path_str = item.data(Qt.UserRole)
        if not json_path_str:
            return
        path = Path(json_path_str)
        self._show_info(path)
        if self._on_project_selected:
            self._on_project_selected(path)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        json_path_str = item.data(Qt.UserRole)
        if not json_path_str:
            return
        path = Path(json_path_str)
        if self._on_project_opened:
            self._on_project_opened(path)

    def _show_info(self, json_path: Path) -> None:
        t = current_theme()
        try:
            data = json.loads(json_path.read_text(encoding="utf-8-sig"))
        except Exception:
            self.info_view.setPlainText("无法读取项目文件。")
            return

        lines = [
            f'路径：{json_path.parent}',
            f'候选方案数：{data.get("candidate_count", "—")}',
            f'最大迭代：{data.get("max_iterations", "—")}',
            f'任务类型：{data.get("task_type") or "—"}',
        ]
        if isinstance(data.get("objective"), str) and data["objective"].strip():
            lines.append(f'目标：{data["objective"].strip()}')
        if isinstance(data.get("design_profile"), dict):
            profile_name = data["design_profile"].get("name", "")
            if profile_name:
                lines.append(f'设计方案：{profile_name}')

        self.info_view.setPlainText("\n".join(lines))
