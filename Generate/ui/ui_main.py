from PyQt5.QtWidgets import (
    QAction,
    QFileDialog,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
import json
import os
import subprocess
import sys
from pathlib import Path

from core.paths import MOTORAI_ROOT
from motorai_config import get_output_root, load_settings
from dialogs.project import NewProjectDialog, SettingsDialog
from panels.controller_structure import ControllerStructurePanel
from panels.cosim_config import CandidateNetworkPanel
from panels.tuning_result import TuningResultPanel
from panels.workspace import Design3RightPanel
from styles.theme import (
    app_qss,
    current_theme,
    dark_qss,
    primary_button_qss,
)


class NetworkConfigDialog(QDialog):
    def __init__(self, project_json_getter=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('网络配置')
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        self.panel = CandidateNetworkPanel(project_json_getter=project_json_getter)
        layout.addWidget(self.panel)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.panel.reload_for_project()


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_project_json_path = None

        # ── load theme BEFORE creating any widgets ──
        self._apply_visual_theme()

        self.setWindowTitle('GMP Generator Engine - UI')
        self.resize(1000, 600)
        
        icon_path = os.path.join(os.path.dirname(__file__), '..', 'icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Top toolbar (horizontal)
        toolbar = QWidget()
        toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(4, 4, 4, 4)
        toolbar_layout.setSpacing(6)

        file_menu = QMenu('文件', self)
        self.action_new = QAction('新建', self)
        self.action_save = QAction('保存', self)
        self.action_load = QAction('读取', self)
        self.action_settings = QAction('设置', self)
        self.action_network_config = QAction('网络配置', self)
        self.action_network_config.setEnabled(False)
        file_menu.addAction(self.action_new)
        file_menu.addAction(self.action_save)
        file_menu.addAction(self.action_load)
        file_menu.addAction(self.action_settings)
        file_menu.addAction(self.action_network_config)
        self.action_new.triggered.connect(self.open_new_project_dialog)
        self.action_load.triggered.connect(self.open_project_json)
        self.action_save.triggered.connect(self.save_project_json)
        self.action_settings.triggered.connect(self.open_settings_dialog)
        self.action_network_config.triggered.connect(self.open_network_config_dialog)

        file_button = QPushButton('文件')
        file_button.setMenu(file_menu)
        file_button.setStyleSheet(
            f'QPushButton {{ border: none; background: transparent; padding: 4px 8px; font-size: 24px; color: {current_theme().text}; }}'
            'QPushButton::menu-indicator { image: none; width: 0px; }'
            f'QPushButton:hover {{ background: {current_theme().panel_hover}; }}'
        )
        toolbar_layout.addWidget(file_button)

        self.run_agent_button = QPushButton('运行调优')
        self.run_agent_button.setObjectName('primaryButton')
        self.run_agent_button.setStyleSheet(primary_button_qss(padding='6px 16px'))
        self.run_agent_button.clicked.connect(self.run_agent_optimization)
        toolbar_layout.addWidget(self.run_agent_button)

        toolbar_layout.addStretch()
        toolbar.setFixedHeight(48)

        # Central area: left (1/3) and right (2/3)
        central = QWidget()
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(6)

        self.left_controller_panel = ControllerStructurePanel(project_json_getter=self.get_current_project_json_path)
        self.left_controller_panel.setStyleSheet(f'background:{COLOR_SURFACE};border:none;')
        self.tuning_result_panel = TuningResultPanel(project_json_getter=self.get_current_project_json_path)
        self.tuning_result_panel.setStyleSheet(f'background:{COLOR_SURFACE};border:none;')

        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.setChildrenCollapsible(False)
        left_splitter.addWidget(self.left_controller_panel)
        left_splitter.addWidget(self.tuning_result_panel)
        left_splitter.setStretchFactor(0, 3)
        left_splitter.setStretchFactor(1, 2)
        left_splitter.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        left_splitter.setMinimumWidth(0)

        self.right_panel_widget = Design3RightPanel(
            project_json_getter=self.get_current_project_json_path,
            run_tuning_callback=self.run_agent_optimization,
        )
        self.right_panel_widget.setStyleSheet(f'background:{COLOR_SURFACE};border:none;')
        self.right_panel_widget.set_controller_panel(self.left_controller_panel)
        self.right_panel_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.right_panel_widget.setMinimumWidth(0)

        central_layout.addWidget(left_splitter, 1)
        central_layout.addWidget(self.right_panel_widget, 2)

        # Bottom information bar (horizontal)
        self.info_widget = QWidget()
        self.info_widget.setObjectName('panelCard')
        info_layout = QHBoxLayout(self.info_widget)
        info_layout.setContentsMargins(6, 6, 6, 6)
        info_layout.setSpacing(6)
        info_label = QLabel('Status: Ready')
        info_label.setStyleSheet(f'color:{COLOR_MUTED};font-weight:600;')
        info_layout.addWidget(info_label)
        info_layout.addStretch()
        user_label = QLabel('User: Guest')
        user_label.setStyleSheet(f'color:{current_theme().muted};')
        info_layout.addWidget(user_label)
        self.info_widget.setMinimumHeight(46)
        self.info_widget.setStyleSheet(f'background:{current_theme().panel};border:none;')

        # Assemble main layout
        main_layout.addWidget(toolbar)
        main_layout.addWidget(central)
        main_layout.addWidget(self.info_widget)

        self.setCentralWidget(container)
        self._install_surface_effects()

    def _apply_visual_theme(self):
        theme = 'light'
        try:
            settings = load_settings()
            ui_cfg = settings.get('ui') if isinstance(settings.get('ui'), dict) else {}
            theme = str(ui_cfg.get('theme', 'light')).lower()
        except Exception:
            pass

        if theme == 'dark':
            self.setStyleSheet(dark_qss())
        else:
            self.setStyleSheet(app_qss())

    def _install_surface_effects(self):
        for widget in [self.left_controller_panel, self.right_panel(), self.info_bar()]:
            if widget is not None:
                widget.setGraphicsEffect(None)

    def right_panel(self):
        return getattr(self, 'right_panel_widget', None)

    def info_bar(self):
        return getattr(self, 'info_widget', None)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec_() == SettingsDialog.Accepted:
            self._apply_visual_theme()

    def open_network_config_dialog(self):
        if not self.current_project_json_path:
            QMessageBox.warning(self, '提示', '请先新建或读取项目 JSON。')
            return
        dialog = NetworkConfigDialog(project_json_getter=self.get_current_project_json_path, parent=self)
        dialog.exec_()

    def open_new_project_dialog(self):
        dialog = NewProjectDialog(self)
        if dialog.exec_() == QDialog.Accepted and dialog.project_json_path:
            self.current_project_json_path = Path(dialog.project_json_path)
            self.action_network_config.setEnabled(True)
            QMessageBox.information(self, '已加载项目', f'当前项目：{self.current_project_json_path}')
            self._refresh_project_panels()
            self._load_panel_data()

    def get_current_project_json_path(self):
        return self.current_project_json_path

    def _launch_background_script(self, command, *, cwd: Path | None, log_name: str):
        project_json_path = self.get_current_project_json_path()
        project_dir = Path(project_json_path).parent if project_json_path else MOTORAI_ROOT
        log_dir = project_dir / 'log' / 'ui'
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = log_dir / f'{log_name}_stdout.txt'
        stderr_path = log_dir / f'{log_name}_stderr.txt'
        stdout_file = open(stdout_path, 'w', encoding='utf-8')
        stderr_file = open(stderr_path, 'w', encoding='utf-8')
        try:
            kwargs = {
                'cwd': str(cwd) if cwd else None,
                'stdout': stdout_file,
                'stderr': stderr_file,
            }
            if os.name == 'nt':
                kwargs['creationflags'] = subprocess.CREATE_NEW_CONSOLE
            process = subprocess.Popen(command, **kwargs)
            stdout_file.close()
            stderr_file.close()
        except Exception:
            stdout_file.close()
            stderr_file.close()
            raise
        return process, stdout_path, stderr_path

    def run_agent_optimization(self):
        project_json_path = self.get_current_project_json_path()
        if not project_json_path:
            QMessageBox.warning(self, '提示', '请先打开或创建一个项目文件')
            return
        
        try:
            with open(project_json_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
        except Exception as exc:
            QMessageBox.warning(self, '提示', f'读取项目文件失败：{exc}')
            return

        try:
            if isinstance(project_data, dict) and project_data.get('workspace_mode') == 'competition':
                runner_script = MOTORAI_ROOT / 'Competition' / 'competition_runner.py'
                if not runner_script.exists():
                    QMessageBox.warning(self, '提示', f'未找到脚本文件：{runner_script}')
                    return
                candidate_count = int(project_data.get('candidate_count') or 4)
                _process, stdout_path, stderr_path = self._launch_background_script([
                    sys.executable,
                    str(runner_script),
                    str(project_json_path),
                    '--candidates',
                    str(candidate_count),
                    '--parallel',
                    '2',
                    '--optimize-parallel',
                    '1',
                    '--skip-generate',
                ], cwd=MOTORAI_ROOT, log_name='competition_runner')
                QMessageBox.information(
                    self,
                    '已启动',
                    '多 candidate 调优任务已启动，将按 candidate_01、candidate_02... 串行迭代。\n'
                    f'标准输出：{stdout_path}\n错误输出：{stderr_path}'
                )
                return

            run_agent_script = Path(__file__).parent / 'run_agent.py'
            if not run_agent_script.exists():
                QMessageBox.warning(self, '提示', f'未找到脚本文件：{run_agent_script}')
                return

            _process, stdout_path, stderr_path = self._launch_background_script(
                [sys.executable, str(run_agent_script), str(project_json_path)],
                cwd=run_agent_script.parent,
                log_name='run_agent',
            )
            QMessageBox.information(
                self,
                '已启动',
                f'调优任务已启动。\n标准输出：{stdout_path}\n错误输出：{stderr_path}'
            )
        except Exception as exc:
            QMessageBox.critical(self, '错误', f'启动失败：{type(exc).__name__}: {exc}')

    def _read_project_open_root(self):
        return str(get_output_root(load_settings()))

    def open_project_json(self):
        default_dir = self._read_project_open_root()
        file_path, _ = QFileDialog.getOpenFileName(self, '选择项目 JSON 文件', default_dir, 'JSON Files (*.json)')
        if not file_path:
            return
        selected = Path(file_path)
        try:
            with open(selected, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError('JSON 顶层必须是对象')
            self.current_project_json_path = selected
            self.action_network_config.setEnabled(True)
            QMessageBox.information(self, '已加载项目', f'当前项目：{self.current_project_json_path}')
            self._refresh_project_panels()
            
            self._load_panel_data()
        except Exception as exc:
            QMessageBox.critical(self, '错误', f'加载项目 JSON 失败：{exc}')

    def _refresh_project_panels(self):
        if hasattr(self, 'left_controller_panel') and self.left_controller_panel is not None:
            self.left_controller_panel.refresh_from_project()
        if hasattr(self, 'tuning_result_panel') and self.tuning_result_panel is not None:
            self.tuning_result_panel.refresh_from_project()

    def _load_panel_data(self):
        right_panel = self.right_panel()
        if not right_panel:
            return

        widgets = right_panel.project_widgets() if hasattr(right_panel, 'project_widgets') else []
        for widget in widgets:
            if hasattr(widget, 'reload_for_project'):
                widget.reload_for_project()
            elif hasattr(widget, '_load_chat_record'):
                widget._load_chat_record()
            if hasattr(widget, 'load_from_csv'):
                widget.load_from_csv()
            if hasattr(widget, 'load_from_project_json'):
                try:
                    widget.load_from_project_json()
                except Exception:
                    pass

    def save_project_json(self):
        if not self.current_project_json_path:
            QMessageBox.warning(self, '提示', '请先新建或读取项目 JSON。')
            return
        try:
            with open(self.current_project_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            with open(self.current_project_json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, '完成', f'已保存：{self.current_project_json_path}')
        except Exception as exc:
            QMessageBox.critical(self, '错误', f'保存项目 JSON 失败：{exc}')
