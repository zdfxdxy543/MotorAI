from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QMenu,
    QAction,
    QDialog,
    QLineEdit,
    QFormLayout,
    QDialogButtonBox,
    QFileDialog,
    QPushButton,
    QMessageBox,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QFrame,
    QGraphicsDropShadowEffect,
    QScrollArea,
)
from PyQt5.QtCore import Qt, QThread, QFileSystemWatcher, pyqtSignal, QPointF, QRectF, QDateTime
from PyQt5.QtGui import QLinearGradient, QMovie
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF, QFont, QFontMetrics, QIcon
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
import csv

MOTORAI_ROOT = Path(__file__).resolve().parents[2]
GENERATE_ROOT = Path(__file__).resolve().parents[1]
V2_ROOT = GENERATE_ROOT
for import_root in (MOTORAI_ROOT, V2_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from motorai_config import (
    get_gmp_root,
    get_llm_settings,
    get_output_root,
    load_settings,
    normalize_optimize_config,
    resolve_motorai_path,
    save_settings,
)

import controller_loop_id_exporter as loop_exporter
import merge_loop_ids_into_ctl_main as merger
from Competition.competition_workspace import (
    apply_candidate_profile_overrides,
    build_candidate_generation_requirement,
    candidate_design_profile,
    candidate_llm_temperature,
    configure_candidate_optimize,
    discover_candidate_dirs,
    init_candidates,
    sync_candidate_profiles_from_common,
    write_candidate_generation_context,
    write_common_requirement_snapshot,
)


def sync_optimize_project_from_settings(project_json_path: Path) -> tuple[bool, str]:
    optimize_config = normalize_optimize_config(load_settings())
    config_project = Path(optimize_config['config_project'])
    if not config_project.exists():
        return False, f'未找到 Optimize 配置脚本：{config_project}'

    result = subprocess.run(
        [sys.executable, str(config_project), str(project_json_path)],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or '').strip()
        return False, detail or f'Optimize 配置脚本退出码：{result.returncode}'
    return True, (result.stdout or '').strip()


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('设置')
        self.resize(560, 220)
        self.setObjectName('SettingsDialog')

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        gmp_root_row = QWidget()
        gmp_root_layout = QHBoxLayout(gmp_root_row)
        gmp_root_layout.setContentsMargins(0, 0, 0, 0)
        gmp_root_layout.setSpacing(6)
        self.gmp_root_edit = QLineEdit()
        self.gmp_root_edit.setPlaceholderText('请选择或输入 GMP 根目录')
        self.browse_btn = QPushButton('浏览...')
        self.browse_btn.clicked.connect(self.choose_gmp_root)
        gmp_root_layout.addWidget(self.gmp_root_edit)
        gmp_root_layout.addWidget(self.browse_btn)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText('请输入 API Key')
        self.api_key_edit.setEchoMode(QLineEdit.Password)

        self.model_name_edit = QLineEdit()
        self.model_name_edit.setPlaceholderText('请输入大模型名称')

        self.model_url_edit = QLineEdit()
        self.model_url_edit.setPlaceholderText('请输入大模型网址')

        form_layout.addRow('GMP根目录', gmp_root_row)
        form_layout.addRow('api-key', self.api_key_edit)
        form_layout.addRow('大模型名称', self.model_name_edit)
        form_layout.addRow('大模型网址', self.model_url_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.on_accept)
        buttons.rejected.connect(self.reject)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(buttons)

        self._settings_path = MOTORAI_ROOT / 'motorai_settings.json'
        self.load_settings()

    def choose_gmp_root(self):
        folder = QFileDialog.getExistingDirectory(self, '选择 GMP 根目录')
        if folder:
            self.gmp_root_edit.setText(folder)

    def on_accept(self):
        if self.save_settings():
            self.accept()

    def load_settings(self):
        try:
            settings = load_settings(self._settings_path)
            llm_data = get_llm_settings(settings)

            self.gmp_root_edit.setText(get_gmp_root(settings))
            self.api_key_edit.setText(llm_data.get('api_key', ''))
            self.model_name_edit.setText(llm_data.get('model', ''))
            self.model_url_edit.setText(llm_data.get('base_url', ''))
        except Exception:
            pass

    def save_settings(self):
        api_key = self.api_key_edit.text().strip()
        model_name = self.model_name_edit.text().strip()
        model_url = self.model_url_edit.text().strip()

        try:
            settings = load_settings(self._settings_path)
            paths = settings.setdefault('paths', {})
            paths['gmp_root'] = self.gmp_root_edit.text().strip()

            llm_data = settings.setdefault('llm', {})
            llm_data['api_key'] = api_key
            llm_data['model'] = model_name
            llm_data['base_url'] = model_url
            save_settings(settings, self._settings_path)
            return True
        except Exception as exc:
            QMessageBox.warning(self, '设置保存失败', f'保存配置失败：{exc}')
            return False


class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('新建项目')
        self.resize(640, 240)
        self.setObjectName('NewProjectDialog')

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        project_parent_row = QWidget()
        project_parent_layout = QHBoxLayout(project_parent_row)
        project_parent_layout.setContentsMargins(0, 0, 0, 0)
        project_parent_layout.setSpacing(6)
        self.project_parent_edit = QLineEdit()
        self.project_parent_edit.setPlaceholderText('请选择或输入项目保存路径')
        self.project_parent_edit.setText(str(self._get_project_parent_path()))
        self.project_parent_btn = QPushButton('浏览...')
        self.project_parent_btn.clicked.connect(self.choose_project_parent)
        project_parent_layout.addWidget(self.project_parent_edit)
        project_parent_layout.addWidget(self.project_parent_btn)

        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText('请输入项目名')

        self.max_iter_spin = QSpinBox()
        self.max_iter_spin.setRange(1, 9999)
        self.max_iter_spin.setValue(5)

        self.candidate_count_spin = QSpinBox()
        self.candidate_count_spin.setRange(1, 16)
        self.candidate_count_spin.setValue(4)

        form_layout.addRow('项目保存路径', project_parent_row)
        form_layout.addRow('项目名', self.project_name_edit)
        form_layout.addRow('最大迭代次数', self.max_iter_spin)
        form_layout.addRow('候选工作区数量', self.candidate_count_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.on_accept)
        buttons.rejected.connect(self.reject)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(buttons)

        self.project_root = None
        self.project_json_path = None

    def _read_gmp_root(self):
        return get_gmp_root(load_settings())

    def _get_project_parent_path(self):
        if hasattr(self, 'project_parent_edit'):
            raw_path = self.project_parent_edit.text().strip()
            if raw_path:
                return resolve_motorai_path(raw_path, raw_path)
        return get_output_root(load_settings())

    def choose_project_parent(self):
        current_path = str(self._get_project_parent_path())
        folder = QFileDialog.getExistingDirectory(self, '选择项目保存路径', current_path)
        if folder:
            self.project_parent_edit.setText(folder)

    def _get_template_project_path(self):
        gmp_root = self._read_gmp_root()
        if not gmp_root:
            return None
        return Path(gmp_root) / 'ctl' / 'suite' / 'mcs_pmsm_nt'

    def _save_output_root(self, project_parent: Path):
        settings = load_settings()
        paths = settings.setdefault('paths', {})
        paths['output_root'] = str(project_parent.resolve())
        save_settings(settings)

    def _build_project_data(self, project_root, template_root: Path, candidate_count: int):
        return {
            'schema_version': 1,
            'workspace_mode': 'competition',
            'candidate_count': int(candidate_count),
            'template_project_path': str(template_root),
            'gmp_path': self._read_gmp_root(),
            'paths': {
                'candidates_dir': 'candidates',
                'common_dir': 'common',
                'record_file': 'record.json',
                'competition_file': 'competition.json',
            },
            'objective_text': '',
            'task_type': '',
            'max_iterations': int(self.max_iter_spin.value()),
            'objective': '',
            'available_signals': [],
            'signals': {},
            'targets': {},
            'events': {},
            'metrics': [],
            'tuning_policy': {},
            'stop_conditions': {},
            'selected_loops': [],
        }

    def on_accept(self):
        project_name = self.project_name_edit.text().strip()

        if not project_name:
            QMessageBox.warning(self, '提示', '请先填写项目名。')
            return

        gmp_root = self._read_gmp_root()
        if not gmp_root:
            QMessageBox.warning(self, '提示', '请先在“设置”中配置 GMP 根目录。')
            return

        project_parent = self._get_project_parent_path()
        if project_parent is None:
            QMessageBox.warning(self, '提示', '无法确定项目保存路径。')
            return
        project_parent = project_parent.expanduser()

        project_root = project_parent / project_name
        if project_root.exists():
            QMessageBox.warning(self, '提示', f'项目目录已存在：{project_root}')
            return

        template_root = self._get_template_project_path()
        if template_root is None or not template_root.exists():
            QMessageBox.warning(
                self,
                '提示',
                f'模板文件夹不存在：{template_root}',
            )
            return

        try:
            project_parent.mkdir(parents=True, exist_ok=True)
            project_root.mkdir(parents=True, exist_ok=False)
            self._save_output_root(project_parent)

            candidate_count = int(self.candidate_count_spin.value())
            project_data = self._build_project_data(project_root, template_root, candidate_count)
            self.project_json_path = project_root / f'{project_name}.json'
            with open(self.project_json_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, ensure_ascii=False, indent=2)

            self.project_root = project_root
            competition_manifest = init_candidates(
                self.project_json_path,
                candidate_count,
                force=False,
                template_root=template_root,
            )
            QMessageBox.information(
                self,
                '完成',
                (
                    f'项目已创建：{self.project_json_path}\n'
                    f'候选工作区：{competition_manifest.get("candidate_count", candidate_count)} 个\n'
                    f'候选策略文件：{project_root / "common" / "candidate_profiles.json"}'
                ),
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, '错误', f'创建项目失败：{exc}')


def read_ui_settings() -> dict:
    settings = load_settings()
    llm_data = get_llm_settings(settings)
    return {
        'api_key': llm_data.get('api_key', ''),
        'model_name': llm_data.get('model', ''),
        'model_url': llm_data.get('base_url', ''),
        'temperature': llm_data.get('temperature', 0.2),
        'timeout': llm_data.get('timeout', 180),
    }


def resolve_ui_api_key(settings: dict) -> str:
    return (
        str(settings.get('api_key', '')).strip()
        or os.getenv('SILICONFLOW_API_KEY', '').strip()
        or os.getenv('OPENAI_API_KEY', '').strip()
    )


class ChatInputEdit(QTextEdit):
    enterPressed = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            event.accept()
            self.enterPressed.emit()
            return
        super().keyPressEvent(event)


class ChatBubbleWidget(QFrame):
    def __init__(self, role: str, text: str, parent=None):
        super().__init__(parent)
        self.role = role
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.setMinimumWidth(0)
        self.setObjectName(f'chatBubble_{role}')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        
        self.avatar = QLabel()
        self.avatar.setFixedSize(44, 44)
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setStyleSheet('background-color: #d1d5db; color: #374151; font-weight: bold; font-size: 16px; border-radius: 22px;')

        self.title = QLabel('')
        self.title.setObjectName('chatBubbleTitle')
        
        self.header_widget = QWidget()
        self.header_widget.setStyleSheet('border: none; background: transparent; margin: 0; padding: 0;')
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        header_layout.addWidget(self.avatar)
        header_layout.addWidget(self.title)
        header_layout.addStretch()

        self.body = QLabel(text or '')
        self.body.setObjectName('chatBubbleBody')
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.body.setStyleSheet('background: transparent;')
        self.body.setMinimumWidth(0)

        layout.addWidget(self.header_widget)
        layout.addWidget(self.body)

        if role == 'user':
            self.title.setText('用户')
            self.avatar.setText('U')
            self.avatar.setStyleSheet('background-color: #93c5fd; color: #1e3a8a; font-weight: bold; font-size: 18px; border-radius: 22px; border: none; margin: 0; padding: 0;')
            self.setStyleSheet(
                'QFrame#chatBubble_user{background:#0f62fe;border:none;border-top-left-radius:18px;border-top-right-radius:18px;'
                'border-bottom-left-radius:18px;border-bottom-right-radius:4px;}'
                'QFrame#chatBubble_user * { border: none; }'
            )
            self.title.setStyleSheet('color:#ffffff;font-size:14pt;font-weight:700; border: none; background: transparent;')
            self.body.setStyleSheet('color:#ffffff;background:transparent; border: none;')
        elif role == 'model':
            self.title.setText('大模型')
            self.avatar.setText('AI')
            self.avatar.setStyleSheet('background-color: #bfdbfe; color: #1e40af; font-weight: bold; font-size: 18px; border-radius: 22px; border: none; margin: 0; padding: 0;')
            self.setStyleSheet(
                'QFrame#chatBubble_model{background:#ffffff;border:1px solid #d9e2ec;'
                'border-top-left-radius:18px;border-top-right-radius:18px;'
                'border-bottom-left-radius:4px;border-bottom-right-radius:18px;}'
                'QFrame#chatBubble_model * { outline: none; }'
            )
            self.title.setStyleSheet('color:#0f62fe;font-size:14pt;font-weight:700; border: none; background: transparent;')
            self.body.setStyleSheet('color:#1f2937;background:transparent; border: none;')
        else:
            self.header_widget.hide()
            self.setStyleSheet(
                'QFrame#chatBubble_system{background:#eef2f7;border:1px solid #d9e2ec;border-radius:14px;}'
                'QFrame#chatBubble_system * { border: none; }'
            )
            self.body.setStyleSheet('color:#64748b;background:transparent; border: none;')
            self.body.setAlignment(Qt.AlignCenter)


class ChatStreamWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.messages = []
        self.message_rows = []
        self.setObjectName('chatStreamWidget')

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setStyleSheet('QScrollArea{background:transparent;border:none;}')

        self.container = QWidget()
        self.container.setAttribute(Qt.WA_StyledBackground, True)
        self.container.setStyleSheet('background: transparent;')
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(12, 12, 12, 12)
        self.container_layout.setSpacing(14)
        self.container_layout.addStretch(1)

        self.scroll.setWidget(self.container)
        outer_layout.addWidget(self.scroll)

    def clear_messages(self):
        self.messages.clear()
        self.message_rows.clear()
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.container_layout.addStretch(1)

    def append_message(self, role: str, text: str):
        self.messages.append((role, text))

        last_item = self.container_layout.itemAt(self.container_layout.count() - 1)
        if last_item and last_item.spacerItem():
            self.container_layout.takeAt(self.container_layout.count() - 1)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)

        bubble = ChatBubbleWidget(role, text)
        bubble.adjustSize()

        if role == 'user':
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0, Qt.AlignRight)
            row_layout.addSpacing(18)
        elif role == 'model':
            row_layout.addSpacing(18)
            row_layout.addWidget(bubble, 0, Qt.AlignLeft)
            row_layout.addStretch(1)
        else:
            bubble.title.hide()
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0, Qt.AlignCenter)
            row_layout.addStretch(1)

        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.container_layout.addWidget(row)
        self.container_layout.addStretch(1)
        self.message_rows.append((role, row, bubble))
        self._update_bubble_widths()
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_bubble_widths()

    def _update_bubble_widths(self):
        viewport_width = max(0, self.scroll.viewport().width())
        content_width = max(0, viewport_width - 24)
        user_model_width = int(content_width * 0.66)
        system_width = int(content_width * 0.66)

        for role, _row, bubble in self.message_rows:
            if role in {'user', 'model'}:
                bubble.setFixedWidth(user_model_width)
            else:
                bubble.setFixedWidth(system_width)


def call_ui_chat_model(user_prompt: str, system_prompt: str, temperature: float | None = None) -> str:
    settings = read_ui_settings()
    api_key = resolve_ui_api_key(settings)
    if not api_key:
        raise RuntimeError('未配置 API Key，请先在设置中填写，或配置环境变量。')

    base_url = str(settings.get('model_url', '')).strip() or 'https://api.siliconflow.cn/v1'
    model = str(settings.get('model_name', '')).strip() or 'deepseek-ai/DeepSeek-V3.2'
    timeout = int(settings.get('timeout') or 180)
    url = base_url.rstrip('/') + '/chat/completions'
    payload = {
        'model': model,
        'temperature': float(temperature if temperature is not None else 0.2),
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
    }
    body = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode('utf-8')
            data = json.loads(response_body)
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f'HTTPError {error.code}: {detail}') from error
    except urllib.error.URLError as error:
        raise RuntimeError(f'网络错误: {error}') from error

    choices = data.get('choices') or []
    if not choices:
        raise RuntimeError('模型返回为空。')
    message = choices[0].get('message') or {}
    content = str(message.get('content') or '').strip()
    if not content:
        raise RuntimeError('模型未返回有效文本。')
    return content


class ChatWorker(QThread):
    success = pyqtSignal(str)
    failure = pyqtSignal(str)

    def __init__(self, user_prompt: str, system_prompt: str, parent=None):
        super().__init__(parent)
        self.user_prompt = user_prompt
        self.system_prompt = system_prompt

    def run(self):
        try:
            result = call_ui_chat_model(self.user_prompt, self.system_prompt)
            self.success.emit(result)
        except Exception as exc:
            self.failure.emit(str(exc))


class TranslationWorker(QThread):
    success = pyqtSignal(str, str)
    failure = pyqtSignal(str, str)

    def __init__(self, summary_key: str, summary_text: str, parent=None):
        super().__init__(parent)
        self.summary_key = summary_key
        self.summary_text = summary_text

    def run(self):
        try:
            system_prompt = (
                '你是中文翻译助手。请将用户提供的调优总结翻译成准确、自然的中文。'
                '要求：保留原有层级、编号、项目符号、数值、符号和专业术语；不要增加解释、评论或总结。'
                '只输出中文译文。'
            )
            translated = call_ui_chat_model(self.summary_text, system_prompt, temperature=0.2)
            self.success.emit(self.summary_key, translated)
        except Exception as exc:
            self.failure.emit(self.summary_key, str(exc))


class ControllerStructureCanvas(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(640)
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName('CurveCanvas')
        self.setObjectName('ControllerStructureCanvas')
        self._model = {
            'items': [],
            'mech_props': [],
            'source': '',
        }

    def set_model(self, model: dict):
        self._model = model or {'items': [], 'mech_props': [], 'source': ''}
        self.update()

    @staticmethod
    def _arrow_head(end_x, end_y, direction='down'):
        size = 16
        if direction == 'down':
            return [QPointF(end_x, end_y), QPointF(end_x - size, end_y - size * 1.4), QPointF(end_x + size, end_y - size * 1.4)]
        return [QPointF(end_x, end_y), QPointF(end_x - size * 1.4, end_y - size), QPointF(end_x - size * 1.4, end_y + size)]

    def _draw_arrow(self, painter: QPainter, start: QPointF, end: QPointF):
        painter.setPen(QPen(QColor('#4d4d4d'), 3.2))
        painter.drawLine(start, end)
        if end.y() >= start.y():
            head = self._arrow_head(end.x(), end.y(), 'down')
        else:
            head = self._arrow_head(end.x(), end.y(), 'right')
        painter.setBrush(QColor('#4d4d4d'))
        painter.drawPolygon(QPolygonF(head))

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(20, 20, -20, -20)
        painter.fillRect(rect, QColor('#fcfcfd'))

        painter.setPen(QColor('#303030'))
        painter.drawText(QRectF(rect.left(), rect.top(), rect.width(), 36), Qt.AlignCenter, '控制器结构框图')

        items = self._model.get('items') or []
        if not items:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0, QColor(220, 220, 220, 60))
            gradient.setColorAt(1, QColor(180, 180, 180, 90))
            painter.fillRect(rect, gradient)
            
            painter.setPen(QPen(QColor(150, 150, 150, 100), 1))
            painter.drawRect(rect)
            
            painter.setPen(QPen(QColor(180, 180, 180, 50), 2, Qt.DashLine))
            painter.drawLine(rect.topLeft(), rect.bottomRight())
            painter.drawLine(rect.topRight(), rect.bottomLeft())
            
            painter.setPen(QColor('#7a7a7a'))
            painter.drawText(rect, Qt.AlignCenter, '暂无控制器结构\n请先在“主程序生成”中生成并保存 loop-ids 结果')
            return

        box_w = 352
        box_h = 104
        gap = 52
        
        label_font_size = int(painter.font().pointSize() * 1.5)
        prop_font_size = int(painter.font().pointSize() * 0.8)
        
        max_prop_width = 0
        for item in items:
            props = item.get('properties') or []
            display_props = '，'.join(props) if props else '-'
            prop_text = f'属性参数：{display_props}'
            prop_font = QFont(painter.font().family(), prop_font_size)
            fm = QFontMetrics(prop_font)
            max_prop_width = max(max_prop_width, fm.width(prop_text))
        
        text_padding = 28
        total_width = box_w + text_padding + max_prop_width + 40
        total_height = 84 + box_h + (gap + 8 if next((item for item in items if item['kind'] == 'current_loop'), None) else 0) + len([item for item in items if item['kind'] in {'speed_loop', 'position_loop'}]) * (box_h + gap)
        
        start_x = rect.left() + (rect.width() - total_width) / 2
        start_y = rect.top() + (rect.height() - total_height) / 2
        
        if start_x < rect.left():
            start_x = rect.left()
        if start_y < rect.top():
            start_y = rect.top()

        x = start_x + 20
        y = start_y + 42

        # Build layout positions.
        positions = []
        current_item = next((item for item in items if item['kind'] == 'current_loop'), None)
        inner_items = [item for item in items if item['kind'] in {'speed_loop', 'position_loop'}]

        box_pen_colors = {
            'current_loop': QColor('#0f62fe'),
            'speed_loop': QColor('#0f7b3a'),
            'position_loop': QColor('#a05a00'),
        }
        fill_colors = {
            'current_loop': QColor('#eef4ff'),
            'speed_loop': QColor('#effaf3'),
            'position_loop': QColor('#fff4e6'),
        }

        if current_item:
            positions.append((current_item, QRectF(x, y, box_w, box_h)))
            y += box_h + gap + 16

        for inner in inner_items:
            positions.append((inner, QRectF(x, y, box_w, box_h)))
            y += box_h + gap

        # draw arrows between consecutive visible nodes
        for idx in range(len(positions) - 1):
            _, prev_rect = positions[idx]
            _, next_rect = positions[idx + 1]
            start = QPointF(prev_rect.center().x(), prev_rect.bottom())
            end = QPointF(next_rect.center().x(), next_rect.top())
            self._draw_arrow(painter, start, end)

        # mechanical wrapper around speed/position nodes
        if inner_items:
            first_rect = positions[1 if current_item else 0][1]
            last_rect = positions[-1][1]
            wrapper = QRectF(
                first_rect.left() - 20,
                first_rect.top() - 28,
                first_rect.width() + 40,
                (last_rect.bottom() - first_rect.top()) + 56,
            )
            painter.setPen(QPen(QColor('#8c8c8c'), 3.2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(wrapper, 20, 20)
            painter.setPen(QColor('#666666'))
            mech_props = self._model.get('mech_props') or []
            mech_text = '机械环'
            if mech_props:
                mech_text += f"  ({', '.join(mech_props)})"
            painter.drawText(QRectF(wrapper.left() + 16, wrapper.top() - 24, wrapper.width() - 32, 32), Qt.AlignLeft | Qt.AlignVCenter, mech_text)

        # draw node boxes and property labels
        for item, box in positions:
            kind = item['kind']
            label = item['label']
            props = item.get('properties') or []
            display_props = '，'.join(props) if props else '-'

            painter.setPen(QPen(box_pen_colors.get(kind, QColor('#4d4d4d')), 3.6))
            painter.setBrush(fill_colors.get(kind, QColor('#f2f2f2')))
            painter.drawRoundedRect(box, 16, 16)
            
            label_font = QFont(painter.font().family(), int(painter.font().pointSize() * 1.5))
            painter.setFont(label_font)
            painter.setPen(QColor('#222222'))
            painter.drawText(box.adjusted(20, 0, -20, 0), Qt.AlignCenter, label)

            prop_font = QFont(painter.font().family(), int(painter.font().pointSize() * 0.8))
            painter.setFont(prop_font)
            painter.setPen(QColor('#4d4d4d'))
            text_x = box.right() + 28
            prop_rect = QRectF(text_x, box.top() + 20, rect.right() - text_x, box.height() - 40)
            painter.drawText(prop_rect, Qt.AlignLeft | Qt.AlignVCenter, f'属性参数：{display_props}')


class ControllerStructurePanel(QWidget):
    def __init__(self, project_json_getter=None, parent=None):
        super().__init__(parent)
        self.project_json_getter = project_json_getter
        self.canvas = ControllerStructureCanvas()
        self.source_label = QLabel('来源：未加载项目')
        self.source_label.setStyleSheet('color: #666666;')
        self.source_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(QLabel('控制器结构'))
        title_layout.addStretch()
        refresh_btn = QPushButton('刷新框图')
        refresh_btn.clicked.connect(self.refresh_from_project)
        title_layout.addWidget(refresh_btn)

        layout.addWidget(title_row)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(self.source_label)
        self.refresh_from_project()

    def _project_json_path(self):
        if callable(self.project_json_getter):
            return self.project_json_getter()
        return None

    def _load_payload(self):
        project_json = self._project_json_path()
        if not project_json:
            return None, None

        candidates = [project_json]
        candidates.append(project_json.parent / 'candidates' / 'candidate_01' / 'log' / 'generate' / 'controller_loop_ids_generated.json')
        candidates.append(project_json.parent / 'controller_loop_ids_generated.json')

        for path in candidates:
            try:
                if not path.exists():
                    continue
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    selected = data.get('selected_loops') or data.get('structured_requirement', {}).get('selected_loops')
                    if isinstance(selected, list) and selected:
                        return data, path
            except Exception:
                continue
        return None, None

    @staticmethod
    def _loop_label(kind: str) -> str:
        return {
            'current_loop': '电流环',
            'speed_loop': '速度环',
            'position_loop': '位置环',
        }.get(kind, kind)

    def _build_model(self, payload: dict | None):
        if not payload:
            return {'items': [], 'mech_props': [], 'source': ''}

        loops = payload.get('selected_loops') or payload.get('structured_requirement', {}).get('selected_loops') or []
        by_name = {str(loop.get('name') or '').strip().lower(): loop for loop in loops if isinstance(loop, dict)}

        mech_loop = by_name.get('mech_loop')
        mech_props = list(mech_loop.get('properties') or []) if mech_loop else []
        mech_target = mech_props[0] if mech_props else ''

        items = []
        current = by_name.get('current_loop')
        if current:
            items.append({
                'kind': 'current_loop',
                'label': self._loop_label('current_loop'),
                'properties': current.get('properties') or [],
            })

        speed = by_name.get('speed_loop')
        position = by_name.get('position_loop')

        if not speed and mech_target == 'speed':
            speed = {'properties': mech_props}
        if not position and mech_target == 'position':
            position = {'properties': mech_props}

        if speed:
            items.append({
                'kind': 'speed_loop',
                'label': self._loop_label('speed_loop'),
                'properties': speed.get('properties') or [],
            })
        if position:
            items.append({
                'kind': 'position_loop',
                'label': self._loop_label('position_loop'),
                'properties': position.get('properties') or [],
            })

        return {
            'items': items,
            'mech_props': mech_props,
            'source': payload.get('_source_path', ''),
        }

    def refresh_from_project(self):
        payload, source_path = self._load_payload()
        if payload and source_path:
            payload = dict(payload)
            payload['_source_path'] = str(source_path)
        model = self._build_model(payload)
        self.canvas.set_model(model)
        if source_path:
            self.source_label.setText(f'来源：{source_path}')
        else:
            self.source_label.setText('来源：未找到 controller_loop_ids_generated.json 或当前项目 JSON 中的 selected_loops')


class TuningResultPanel(QWidget):
    def __init__(self, project_json_getter=None, parent=None):
        super().__init__(parent)
        self.project_json_getter = project_json_getter
        self._current_result_key = ''
        self._current_summary_key = ''
        self._translated_summary = ''
        self._current_score = None
        self._current_summary_text = ''
        self._competition_note_text = ''
        self._translation_worker = None
        self._pending_refresh = False
        self._last_source_path = ''
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_watch_triggered)
        self._watcher.directoryChanged.connect(self._on_watch_triggered)
        self._watched_paths = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(QLabel('调优结果'))
        title_layout.addStretch()
        refresh_btn = QPushButton('刷新结果')
        refresh_btn.clicked.connect(self.refresh_from_project)
        title_layout.addWidget(refresh_btn)

        self.result_view = QTextEdit()
        self.result_view.setReadOnly(True)
        self.result_view.setPlaceholderText('等待生成 tuning_result.json ...')
        self.result_view.setMinimumHeight(180)
        self.result_view.setStyleSheet('QTextEdit{background:#ffffff;border:1px solid #d9e2ec;border-radius:0;padding:8px;border-top:none;}')

        self.source_label = QLabel('来源：未加载项目')
        self.source_label.setStyleSheet('color: #666666;')
        self.source_label.setWordWrap(True)

        layout.addWidget(title_row)
        layout.addWidget(self.result_view, 1)
        layout.addWidget(self.source_label)

        self.refresh_from_project()

    def _project_json_path(self):
        if callable(self.project_json_getter):
            return self.project_json_getter()
        return None

    @staticmethod
    def _normalize_summary(summary):
        if summary is None:
            return ''
        if isinstance(summary, str):
            return summary.strip()
        if isinstance(summary, (list, tuple)):
            parts = []
            for item in summary:
                if isinstance(item, str):
                    text = item.strip()
                else:
                    text = json.dumps(item, ensure_ascii=False, indent=2)
                if text:
                    parts.append(text)
            return '\n'.join(parts).strip()
        if isinstance(summary, dict):
            return json.dumps(summary, ensure_ascii=False, indent=2).strip()
        return str(summary).strip()

    def _result_summary_text(self, payload):
        if not isinstance(payload, dict):
            return ''
        rounds = payload.get('rounds')
        if isinstance(rounds, list):
            for item in reversed(rounds):
                if not isinstance(item, dict):
                    continue
                text = self._normalize_summary(item.get('assistant_summary'))
                if text:
                    return text
        return self._normalize_summary(payload.get('setup_summary'))

    @staticmethod
    def _format_score(value):
        if value is None:
            return 'N/A'
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def _tuning_result_path(self):
        project_json = self._project_json_path()
        if not project_json:
            return None
        try:
            return Path(project_json).parent / 'tuning_result.json'
        except Exception:
            return None

    def _project_dir(self):
        project_json = self._project_json_path()
        if not project_json:
            return None
        try:
            return Path(project_json).parent
        except Exception:
            return None

    @staticmethod
    def _read_json(path: Path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _competition_result_path(self):
        project_dir = self._project_dir()
        if project_dir is None:
            return None
        for name in ('competition_run_result.json', 'competition_dry_run_result.json'):
            path = project_dir / name
            if path.exists():
                return path
        return None

    @staticmethod
    def _score_text(value):
        return 'N/A' if value is None else str(value)

    def _competition_note(self, competition_payload, selected_result_path: Path | None):
        if not isinstance(competition_payload, dict):
            return ''

        lines = ['competition summary']
        winner_reason = str(competition_payload.get('winner_reason') or '').strip()
        if winner_reason:
            lines.append(f'winner_reason: {winner_reason}')
        if 'requirement_satisfied' in competition_payload:
            lines.append(f'requirement_satisfied: {competition_payload.get("requirement_satisfied")}')
        mode = competition_payload.get('optimize_execution_mode')
        if mode:
            lines.append(f'optimize_execution_mode: {mode}')

        scoreboard = competition_payload.get('scoreboard')
        if isinstance(scoreboard, list) and scoreboard:
            lines.append('')
            lines.append('scoreboard:')
            for item in scoreboard:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    '- {candidate}: score={score}, status={status}, stop={stop}'.format(
                        candidate=item.get('candidate_id', ''),
                        score=self._score_text(item.get('overall_score')),
                        status=item.get('status', ''),
                        stop=item.get('stop_reason', ''),
                    )
                )

        if selected_result_path is not None:
            lines.append('')
            lines.append(f'showing_detail: {selected_result_path}')
        return '\n'.join(lines).strip()

    def _candidate_result_from_competition(self, competition_payload):
        if not isinstance(competition_payload, dict):
            return None

        winner = competition_payload.get('winner')
        if isinstance(winner, dict):
            winner_path = winner.get('tuning_result')
            if winner_path:
                path = Path(str(winner_path))
                if path.exists():
                    return path

        scoreboard = competition_payload.get('scoreboard')
        if isinstance(scoreboard, list):
            scored_items = []
            fallback_items = []
            for item in scoreboard:
                if not isinstance(item, dict):
                    continue
                path_text = item.get('tuning_result')
                if not path_text:
                    continue
                path = Path(str(path_text))
                if not path.exists():
                    continue
                score = item.get('overall_score')
                if isinstance(score, (int, float)):
                    scored_items.append((float(score), path))
                else:
                    fallback_items.append(path)
            if scored_items:
                scored_items.sort(key=lambda pair: pair[0], reverse=True)
                return scored_items[0][1]
            if fallback_items:
                return fallback_items[0]

        optimize_items = competition_payload.get('optimize')
        if isinstance(optimize_items, list):
            for item in optimize_items:
                if not isinstance(item, dict):
                    continue
                outputs = item.get('outputs')
                if not isinstance(outputs, dict):
                    continue
                path_text = outputs.get('tuning_result')
                if path_text:
                    path = Path(str(path_text))
                    if path.exists():
                        return path
        return None

    def _resolve_result_source(self):
        root_result = self._tuning_result_path()
        if root_result is not None and root_result.exists():
            return root_result, None

        competition_path = self._competition_result_path()
        if competition_path is None:
            return None, None

        try:
            competition_payload = self._read_json(competition_path)
        except Exception:
            return None, None

        candidate_result = self._candidate_result_from_competition(competition_payload)
        return candidate_result, competition_payload

    def _clear_watch_paths(self):
        paths = list(self._watched_paths)
        if paths:
            try:
                self._watcher.removePaths(paths)
            except Exception:
                pass
        self._watched_paths.clear()

    def _set_watch_path(self, path: Path | None):
        if path is None:
            return
        path_text = str(path)
        if path_text not in self._watched_paths and path.exists():
            try:
                if self._watcher.addPath(path_text):
                    self._watched_paths.add(path_text)
            except Exception:
                pass

    def _sync_watch_paths(self):
        tuning_result_path = self._tuning_result_path()
        competition_result_path = self._competition_result_path()
        competition_candidate_result_path = None
        project_json = self._project_json_path()
        project_dir = None
        if project_json:
            try:
                project_dir = Path(project_json).parent
            except Exception:
                project_dir = None

        desired_paths = set()
        if project_dir is not None:
            desired_paths.add(str(project_dir))
        if tuning_result_path is not None and tuning_result_path.exists():
            desired_paths.add(str(tuning_result_path))
        if competition_result_path is not None and competition_result_path.exists():
            desired_paths.add(str(competition_result_path))
            try:
                competition_payload = self._read_json(competition_result_path)
                candidate_result = self._candidate_result_from_competition(competition_payload)
                if candidate_result is not None and candidate_result.exists():
                    competition_candidate_result_path = candidate_result
                    desired_paths.add(str(candidate_result))
            except Exception:
                pass

        current_paths = set(self._watched_paths)
        to_remove = list(current_paths - desired_paths)
        if to_remove:
            try:
                self._watcher.removePaths(to_remove)
            except Exception:
                pass
            for path_text in to_remove:
                self._watched_paths.discard(path_text)

        if project_dir is not None:
            self._set_watch_path(project_dir)
        if tuning_result_path is not None and tuning_result_path.exists():
            self._set_watch_path(tuning_result_path)
        if competition_result_path is not None and competition_result_path.exists():
            self._set_watch_path(competition_result_path)
        if competition_candidate_result_path is not None and competition_candidate_result_path.exists():
            self._set_watch_path(competition_candidate_result_path)

    def _on_watch_triggered(self, _path: str):
        self.refresh_from_project()

    def _render(self, score_value, translated_summary, source_path_text, status_text=None, competition_note=''):
        lines = [f'overall_score: {self._format_score(score_value)}']
        note = (competition_note or '').strip()
        if note:
            lines.append('')
            lines.append(note)
        body = (translated_summary or '').strip()
        if body:
            lines.append('')
            lines.append(body)
        else:
            lines.append('')
            lines.append('等待 setup_summary 翻译结果...')
        self.result_view.setPlainText('\n'.join(lines))
        if source_path_text:
            self.source_label.setText(f'来源：{source_path_text}')
        else:
            self.source_label.setText('来源：未找到 tuning_result.json')
        if status_text:
            self.result_view.setToolTip(status_text)

    def _start_translation(self, summary_key: str, summary_text: str):
        if self._translation_worker is not None and self._translation_worker.isRunning():
            self._pending_refresh = True
            return

        self._translation_worker = TranslationWorker(summary_key, summary_text, self)
        self._translation_worker.success.connect(self._on_translation_success)
        self._translation_worker.failure.connect(self._on_translation_failure)
        self._translation_worker.finished.connect(self._on_translation_finished)
        self._translation_worker.start()

    def _on_translation_success(self, summary_key: str, translated_text: str):
        if summary_key != self._current_summary_key:
            return
        self._translated_summary = translated_text.strip()
        self._render(self._current_score, self._translated_summary, self._last_source_path, '翻译完成', getattr(self, '_competition_note_text', ''))

    def _on_translation_failure(self, summary_key: str, error_text: str):
        if summary_key != self._current_summary_key:
            return
        fallback = self._current_summary_text or '翻译失败：' + error_text
        self._translated_summary = fallback
        self._render(self._current_score, self._translated_summary, self._last_source_path, f'翻译失败：{error_text}', getattr(self, '_competition_note_text', ''))

    def _on_translation_finished(self):
        self._translation_worker = None
        if self._pending_refresh:
            self._pending_refresh = False
            self.refresh_from_project()

    def refresh_from_project(self):
        self._sync_watch_paths()
        tuning_result_path, competition_payload = self._resolve_result_source()
        competition_note = self._competition_note(competition_payload, tuning_result_path)
        self._competition_note_text = competition_note
        if not tuning_result_path or not tuning_result_path.exists():
            self._current_result_key = ''
            self._current_summary_key = ''
            self._translated_summary = ''
            self._current_score = None
            self._current_summary_text = ''
            self._last_source_path = ''
            self._render(None, '', '', '未找到 tuning_result.json', competition_note)
            return

        try:
            with open(tuning_result_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
        except Exception as exc:
            self._render(None, f'读取失败：{exc}', str(tuning_result_path), f'读取 tuning_result.json 失败：{exc}', competition_note)
            return

        final_evaluation = payload.get('final_evaluation') or {}
        score_value = final_evaluation.get('overall_score')
        summary_text = self._result_summary_text(payload)
        summary_key = f'{tuning_result_path}:{competition_note}:{summary_text}'
        result_key = f'{tuning_result_path}:{score_value!r}:{summary_key}'

        self._last_source_path = str(tuning_result_path)
        score_changed = score_value != self._current_score
        summary_changed = summary_key != self._current_summary_key
        if result_key == self._current_result_key:
            return

        self._current_result_key = result_key
        self._current_score = score_value
        self._current_summary_text = summary_text

        if not summary_text:
            self._current_summary_key = ''
            self._translated_summary = ''
            self._render(score_value, '', str(tuning_result_path), 'setup_summary 为空', competition_note)
            return

        if summary_changed:
            self._current_summary_key = summary_key
            self._translated_summary = ''
            self._render(score_value, '正在翻译 setup_summary...', str(tuning_result_path), '正在翻译 setup_summary', competition_note)
            self._start_translation(summary_key, summary_text)
        else:
            self._render(score_value, self._translated_summary, str(tuning_result_path), 'overall_score 已刷新' if score_changed else None, competition_note)


class CurveCanvas(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(260)
        self.setFrameShape(QFrame.StyledPanel)
        self._points: list[tuple[float, float]] = []
        self._title = '负载曲线'
        self._x_label = '时间'
        self._y_label = '负载值'

    def set_curve(self, points: list[tuple[float, float]], title='负载曲线', x_label='时间', y_label='负载值'):
        self._points = list(points)
        self._title = title
        self._x_label = x_label
        self._y_label = y_label
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(12, 12, -12, -12)
        painter.fillRect(rect, QColor('#fbfbfb'))

        title_rect = QRectF(rect.left(), rect.top(), rect.width(), 24)
        painter.setPen(QColor('#333333'))
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, self._title)

        plot_rect = QRectF(rect.left() + 44, rect.top() + 32, rect.width() - 58, rect.height() - 64)
        if plot_rect.width() <= 0 or plot_rect.height() <= 0:
            return

        # grid and axes
        painter.setPen(QPen(QColor('#d8d8d8'), 1))
        for i in range(6):
            y = plot_rect.top() + i * plot_rect.height() / 5.0
            painter.drawLine(int(plot_rect.left()), int(y), int(plot_rect.right()), int(y))
        for i in range(6):
            x = plot_rect.left() + i * plot_rect.width() / 5.0
            painter.drawLine(int(x), int(plot_rect.top()), int(x), int(plot_rect.bottom()))

        painter.setPen(QPen(QColor('#666666'), 1.5))
        painter.drawLine(int(plot_rect.left()), int(plot_rect.bottom()), int(plot_rect.right()), int(plot_rect.bottom()))
        painter.drawLine(int(plot_rect.left()), int(plot_rect.top()), int(plot_rect.left()), int(plot_rect.bottom()))

        painter.setPen(QColor('#666666'))
        painter.drawText(QRectF(rect.left(), plot_rect.top() - 18, 38, 18), Qt.AlignRight | Qt.AlignVCenter, self._y_label)
        painter.drawText(QRectF(plot_rect.left(), rect.bottom() - 18, plot_rect.width(), 18), Qt.AlignCenter, self._x_label)

        if len(self._points) < 2:
            painter.setPen(QColor('#888888'))
            painter.drawText(plot_rect, Qt.AlignCenter, '暂无可绘制数据\n请在下方列表输入两列数值')
            return

        xs = [p[0] for p in self._points]
        ys = [p[1] for p in self._points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        if abs(max_x - min_x) < 1e-9:
            max_x = min_x + 1.0
        if abs(max_y - min_y) < 1e-9:
            max_y = min_y + 1.0

        num_ticks = 6
        painter.setPen(QColor('#666666'))
        f = painter.font()
        f.setPointSize(8)
        painter.setFont(f)

        for i in range(num_ticks):
            tval = min_x + i * (max_x - min_x) / (num_ticks - 1)
            tx = plot_rect.left() + (tval - min_x) / (max_x - min_x) * plot_rect.width()
            painter.drawLine(int(tx), int(plot_rect.bottom()), int(tx), int(plot_rect.bottom() + 6))
            txt = ('%g' % (round(tval, 6)))
            painter.drawText(QRectF(tx - 36, plot_rect.bottom() + 6, 72, 16), Qt.AlignCenter, txt)

        for i in range(num_ticks):
            yval = min_y + i * (max_y - min_y) / (num_ticks - 1)
            y_ratio = (yval - min_y) / (max_y - min_y)
            py = plot_rect.bottom() - y_ratio * plot_rect.height()
            painter.drawLine(int(plot_rect.left() - 6), int(py), int(plot_rect.left()), int(py))
            ytxt = ('%g' % (round(yval, 6)))
            painter.drawText(QRectF(rect.left(), py - 8, 40, 16), Qt.AlignRight | Qt.AlignVCenter, ytxt)

        def map_point(x_val, y_val):
            x_ratio = (x_val - min_x) / (max_x - min_x)
            y_ratio = (y_val - min_y) / (max_y - min_y)
            px = plot_rect.left() + x_ratio * plot_rect.width()
            py = plot_rect.bottom() - y_ratio * plot_rect.height()
            return QPointF(px, py)

        poly = QPolygonF([map_point(x, y) for x, y in self._points])
        painter.setPen(QPen(QColor('#0f62fe'), 2.2))
        painter.drawPolyline(poly)

        painter.setPen(QPen(QColor('#0f62fe'), 1.2))
        painter.setBrush(QColor('#ffffff'))
        for point in poly:
            painter.drawEllipse(point, 3.8, 3.8)

        painter.setPen(QColor('#444444'))
        painter.drawText(QRectF(plot_rect.right() - 140, plot_rect.top() + 6, 140, 18), Qt.AlignRight, f'点数: {len(self._points)}')


class MainProgramPanel(QWidget):
    def __init__(self, project_json_getter=None, structure_refresh_callback=None, parent=None):
        super().__init__(parent)
        self.current_requirement = ''
        self.chat_worker = None
        self.project_json_getter = project_json_getter
        self.structure_refresh_callback = structure_refresh_callback
        self.chat_history = []
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        self.chat_view = ChatStreamWidget()
        
        self.input_row = QWidget()
        input_layout = QHBoxLayout(self.input_row)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(10)

        self.input_edit = ChatInputEdit()
        self.input_edit.setPlaceholderText('请输入需求描述...')
        self.input_edit.setFixedHeight(96)
        self.input_edit.enterPressed.connect(self.send_requirement)

        input_actions = QWidget()
        input_actions_layout = QVBoxLayout(input_actions)
        input_actions_layout.setContentsMargins(0, 0, 0, 0)
        input_actions_layout.setSpacing(8)
        self.send_btn = QPushButton('发送需求')
        self.send_btn.setObjectName('primaryButton')
        self.send_btn.setStyleSheet(
            'QPushButton{background:#0f62fe;color:#ffffff;border:none;font-weight:600;}'
            'QPushButton:hover{background:#0a55df;}'
            'QPushButton:pressed{background:#0848c7;}'
            'QPushButton:disabled{background:#9abafc;color:#f8fbff;}'
        )
        self.send_btn.clicked.connect(self.send_requirement)
        self.clear_btn = QPushButton('清空')
        self.clear_btn.setObjectName('ghostButton')
        self.clear_btn.clicked.connect(self.clear_input)
        input_actions_layout.addWidget(self.send_btn)
        input_actions_layout.addWidget(self.clear_btn)
        input_actions_layout.addStretch()

        input_layout.addWidget(self.input_edit, 1)
        input_layout.addWidget(input_actions)

        self.action_row = QWidget()
        action_layout = QHBoxLayout(self.action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)
        action_layout.addStretch()
        self.run_btn = QPushButton('生成程序')
        self.run_btn.setObjectName('secondaryActionButton')
        self.run_btn.clicked.connect(self.generate_program)
        action_layout.addWidget(self.run_btn)

        self.status_label = QLabel('状态：等待输入需求')

        self.welcome_overlay = QWidget()
        self.welcome_layout = QVBoxLayout(self.welcome_overlay)
        self.welcome_layout.setContentsMargins(0, 0, 0, 0)
        self.welcome_layout.setSpacing(0)
        
        self.welcome_title = QLabel('通用电机驱动器智能开发平台')
        self.welcome_title.setStyleSheet('''
            QLabel {
                font-size: 32pt;
                font-weight: 700;
                color: #374151;
                padding-bottom: 40px;
                border: none;
                background: transparent;
            }
        ''')
        self.welcome_title.setAlignment(Qt.AlignCenter)
        
        self.welcome_input = QLineEdit()
        self.welcome_input.setPlaceholderText('请输入需求描述...')
        self.welcome_input.setStyleSheet('''
            QLineEdit {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 40px;
                padding: 16px 24px;
                font-size: 14pt;
                color: #374151;
                min-height: 56px;
                min-width: 1200px;
                max-width: 1400px;
            }
            QLineEdit::placeholder {
                color: #9ca3af;
            }
        ''')
        self.welcome_input.returnPressed.connect(self._on_welcome_input)
        
        self.quick_action_buttons = QWidget()
        self.quick_action_buttons.setStyleSheet('border: none; background: transparent;')
        quick_action_layout = QHBoxLayout(self.quick_action_buttons)
        quick_action_layout.setContentsMargins(0, 20, 0, 0)
        quick_action_layout.setSpacing(16)
        
        self.btn_vacuum = QPushButton('设计吸尘器驱动器')
        self.btn_vacuum.setStyleSheet('''
            QPushButton {
                background: #f3f4f6;
                border: none;
                border-width: 0;
                border-style: none;
                outline: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 12pt;
                color: #374151;
                min-width: 160px;
            }
            QPushButton:hover {
                background: #e5e7eb;
            }
            QPushButton:pressed {
                background: #d1d5db;
            }
            QPushButton:focus {
                outline: none;
            }
        ''')
        self.btn_vacuum.setFlat(True)
        self.btn_vacuum.clicked.connect(lambda: self._apply_quick_template('吸尘器驱动器'))
        
        self.btn_servo = QPushButton('设计伺服电机驱动器')
        self.btn_servo.setStyleSheet('''
            QPushButton {
                background: #f3f4f6;
                border: none;
                border-width: 0;
                border-style: none;
                outline: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 12pt;
                color: #374151;
                min-width: 180px;
            }
            QPushButton:hover {
                background: #e5e7eb;
            }
            QPushButton:pressed {
                background: #d1d5db;
            }
            QPushButton:focus {
                outline: none;
            }
        ''')
        self.btn_servo.setFlat(True)
        self.btn_servo.clicked.connect(lambda: self._apply_quick_template('伺服电机驱动器'))
        
        self.btn_current = QPushButton('设计电流环驱动器')
        self.btn_current.setStyleSheet('''
            QPushButton {
                background: #f3f4f6;
                border: none;
                border-width: 0;
                border-style: none;
                outline: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 12pt;
                color: #374151;
                min-width: 160px;
            }
            QPushButton:hover {
                background: #e5e7eb;
            }
            QPushButton:pressed {
                background: #d1d5db;
            }
            QPushButton:focus {
                outline: none;
            }
        ''')
        self.btn_current.setFlat(True)
        self.btn_current.clicked.connect(lambda: self._apply_quick_template('电流环驱动器'))
        
        quick_action_layout.addWidget(self.btn_vacuum)
        quick_action_layout.addWidget(self.btn_servo)
        quick_action_layout.addWidget(self.btn_current)
        
        self.welcome_gif_label = QLabel()
        self.welcome_gif_label.setAlignment(Qt.AlignCenter)
        self.welcome_gif_label.setFrameShape(QFrame.NoFrame)
        self.welcome_gif_label.setStyleSheet('border: none; outline: none; margin: 0; padding: 0;')
        self.welcome_movie = None
        welcome_gif_path = GENERATE_ROOT / '旋转.gif'
        if welcome_gif_path.exists():
            self.welcome_movie = QMovie(str(welcome_gif_path))
            self.welcome_gif_label.setMovie(self.welcome_movie)
            self.welcome_movie.start()
        
        self.welcome_layout.addStretch(2)
        self.welcome_layout.addWidget(self.welcome_gif_label, 0, Qt.AlignCenter)
        self.welcome_layout.addWidget(self.welcome_title, 0, Qt.AlignCenter)
        self.welcome_layout.addWidget(self.welcome_input, 0, Qt.AlignCenter)
        self.welcome_layout.addWidget(self.quick_action_buttons, 0, Qt.AlignCenter)
        self.welcome_layout.addStretch(3)
        self.welcome_overlay.setStyleSheet('background: #ffffff;')
        
        self._load_chat_record()
        
        if not self.chat_history:
            self.show_welcome_overlay()
        else:
            self.show_main_content()

    def show_welcome_overlay(self):
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
        
        self.welcome_overlay.show()
        self.main_layout.addWidget(self.welcome_overlay)
    
    def show_main_content(self):
        if self.welcome_overlay in [self.main_layout.itemAt(i).widget() for i in range(self.main_layout.count())]:
            self.welcome_overlay.hide()
            self.main_layout.removeWidget(self.welcome_overlay)
        
        self.main_layout.addWidget(QLabel('主程序生成'))
        self.main_layout.addWidget(self.chat_view, 1)
        self.main_layout.addWidget(self.input_row)
        self.main_layout.addWidget(self.action_row)
        self.main_layout.addWidget(self.status_label)
        
        self.chat_view.show()
        self.input_row.show()
        self.action_row.show()
        self.status_label.show()

    def _on_welcome_input(self):
        text = self.welcome_input.text().strip()
        if not text:
            return
        
        self.current_requirement = text
        self._append_chat('user', text)
        self._apply_candidate_profile_overrides(text)
        self._append_chat('system', '正在调用大模型完善需求...')
        
        self.show_main_content()
        self.status_label.setText('状态：对话处理中...')
        self.send_btn.setEnabled(False)

        self.chat_worker = ChatWorker(
            text,
            (
                '你是面向 loop-ids 生成系统的控制器需求完善助手。'
                '你的任务是把用户原始需求改写为可直接用于控制环路选择与程序生成的中文需求。'
                '重点聚焦以下内容：'
                '1) 明确电流环（current_loop）目标、约束、动态响应与可测量量；'
                '2) 明确机械环（mech_loop）控制目标与结构层级（速度或位置）；'
                '3) 明确机械环控制方法（pid/mit/smc）及其选择依据；'
                '4) 明确内外环关系、必要信号链路与关键性能指标。'
                '如果用户提到 candidate_01/candidate_02/候选1/候选2 等候选方案设置，例如高生成温度、低生成温度、偏滑模、偏前馈、偏抗扰，请保留为“候选方案设置：...”文本；'
                '如果用户没有指定候选方案设置，则说明沿用默认四策略：稳健低超调、快速响应、抗扰恢复、平滑低纹波。'
                '输出要求：仅输出“完善后的需求文本”，不输出代码块、不输出额外解释。'
            ),
            self,
        )
        self.chat_worker.success.connect(self.on_chat_success)
        self.chat_worker.failure.connect(self.on_chat_failure)
        self.chat_worker.finished.connect(self.on_chat_finished)
        self.chat_worker.start()
        self.welcome_input.clear()

    def _apply_quick_template(self, template_type):
        templates = {
            '吸尘器驱动器': '设计一个高性能吸尘器电机驱动器，要求：支持宽电压输入范围，具备过流保护功能，响应速度快，噪音低。',
            '伺服电机驱动器': '设计一个高精度伺服电机驱动器，要求：支持位置环和速度环控制，具备良好的动态响应特性，支持编码器反馈。',
            '电流环驱动器': '设计一个电流环驱动器，要求：具备高精度电流控制能力，支持快速电流响应，具有限流保护功能。'
        }
        
        template_text = templates.get(template_type, '')
        if template_text:
            self.welcome_input.setText(template_text)
            self._on_welcome_input()

    def clear_input(self):
        self.input_edit.clear()

    def _append_chat(self, role: str, text: str):
        self.chat_view.append_message(role, text)
        self.chat_history.append({
            'role': role,
            'text': text,
            'timestamp': QDateTime.currentDateTime().toString(Qt.ISODate)
        })
        self._save_chat_record()

    def send_requirement(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        if self.chat_worker is not None and self.chat_worker.isRunning():
            self._append_chat('system', '正在等待上一条对话返回，请稍后。')
            return

        self.current_requirement = text
        self._append_chat('user', text)
        self._apply_candidate_profile_overrides(text)
        self._append_chat('system', '正在调用大模型完善需求...')
        self.status_label.setText('状态：对话处理中...')
        self.send_btn.setEnabled(False)

        self.chat_worker = ChatWorker(
            text,
            (
                '你是面向 loop-ids 生成系统的控制器需求完善助手。'
                '你的任务是把用户原始需求改写为可直接用于控制环路选择与程序生成的中文需求。'
                '重点聚焦以下内容：'
                '1) 明确电流环（current_loop）目标、约束、动态响应与可测量量；'
                '2) 明确机械环（mech_loop）控制目标与结构层级（速度或位置）；'
                '3) 明确机械环控制方法（pid/mit/smc）及其选择依据；'
                '4) 明确内外环关系、必要信号链路与关键性能指标。'
                '如果用户提到 candidate_01/candidate_02/候选1/候选2 等候选方案设置，例如高生成温度、低生成温度、偏滑模、偏前馈、偏抗扰，请保留为“候选方案设置：...”文本；'
                '如果用户没有指定候选方案设置，则说明沿用默认四策略：稳健低超调、快速响应、抗扰恢复、平滑低纹波。'
                '输出要求：仅输出“完善后的需求文本”，不输出代码块、不输出额外解释。'
            ),
            self,
        )
        self.chat_worker.success.connect(self.on_chat_success)
        self.chat_worker.failure.connect(self.on_chat_failure)
        self.chat_worker.finished.connect(self.on_chat_finished)
        self.chat_worker.start()
        self.input_edit.clear()

    def _project_json_path(self):
        if callable(self.project_json_getter):
            return self.project_json_getter()
        return None

    def _update_project_json_requirement(self, requirement_text: str):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            data['objective_text'] = requirement_text
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            write_common_requirement_snapshot(Path(project_json), data)
            for candidate_dir in self._candidate_dirs():
                candidate_json = candidate_dir / 'candidate.json'
                if not candidate_json.exists():
                    continue
                with open(candidate_json, 'r', encoding='utf-8') as f:
                    candidate_data = json.load(f)
                if isinstance(candidate_data, dict):
                    candidate_data['objective_text'] = requirement_text
                    with open(candidate_json, 'w', encoding='utf-8') as f:
                        json.dump(candidate_data, f, ensure_ascii=False, indent=2)
            self._append_chat('system', f'已写入需求到项目文件 {project_json.name}')
        except Exception as exc:
            self._append_chat('system', f'写入项目 JSON 失败：{exc}')

    def _apply_candidate_profile_overrides(self, text: str):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            result = apply_candidate_profile_overrides(Path(project_json), text)
            updated = result.get('updated') if isinstance(result, dict) else None
            if updated:
                profiles_path = result.get('profiles_path', '')
                self._append_chat(
                    'system',
                    f'已更新候选生成策略：{", ".join(updated)}。策略文件：{profiles_path}'
                )
        except Exception as exc:
            self._append_chat('system', f'更新 candidate 策略失败：{exc}')

    def _candidate_dirs(self):
        project_json = self._project_json_path()
        if not project_json:
            return []
        try:
            return discover_candidate_dirs(Path(project_json), ['all'])
        except Exception:
            return []

    @staticmethod
    def _candidate_profile(index: int) -> dict:
        return candidate_design_profile(index)

    def _load_candidate_profile(self, candidate_dir: Path, index: int) -> dict:
        profile = self._candidate_profile(index)
        candidate_json = candidate_dir / 'candidate.json'
        if not candidate_json.exists():
            return profile
        try:
            with open(candidate_json, 'r', encoding='utf-8') as f:
                candidate_data = json.load(f)
            candidate_profile = candidate_data.get('design_profile') if isinstance(candidate_data, dict) else None
            if isinstance(candidate_profile, dict):
                merged = dict(profile)
                merged.update(candidate_profile)
                return merged
        except Exception:
            pass
        return profile

    @staticmethod
    def _build_tuning_policy_from_loops(selected_loops):
        loop_names = {loop.get('name', '').lower() for loop in selected_loops if isinstance(loop, dict)}

        allowed_parameters = {}
        if 'current_loop' in loop_names or 'current_error_loop' in loop_names:
            allowed_parameters['CUR_KP'] = {'min': 1.0, 'max': 500.0, 'description': '电流环比例增益'}
            allowed_parameters['CUR_KI'] = {'min': 0.0, 'max': 100.0, 'description': '电流环积分增益'}
            allowed_parameters['CUR_LIMIT'] = {'min': 0.05, 'max': 10.0, 'description': '电流限幅'}
        if 'speed_loop' in loop_names or 'speed_error_loop' in loop_names or 'mech_loop' in loop_names:
            allowed_parameters['VEL_KP'] = {'min': 0.1, 'max': 20.0, 'description': '速度环比例增益'}
            allowed_parameters['VEL_KI'] = {'min': 0.0, 'max': 5.0, 'description': '速度环积分增益'}
            allowed_parameters['CUR_LIMIT'] = {'min': 0.05, 'max': 10.0, 'description': '电流限幅'}
        if 'position_loop' in loop_names or 'position_error_loop' in loop_names:
            allowed_parameters['POS_KP'] = {'min': 0.1, 'max': 50.0, 'description': '位置环比例增益'}
            allowed_parameters['POS_KI'] = {'min': 0.0, 'max': 10.0, 'description': '位置环积分增益'}
            allowed_parameters['VEL_LIMIT'] = {'min': 0.1, 'max': 100.0, 'description': '速度限幅'}
        if 'torque_loop' in loop_names or 'torque_reference_loop' in loop_names:
            allowed_parameters['TRQ_KP'] = {'min': 1.0, 'max': 500.0, 'description': '转矩环比例增益'}
            allowed_parameters['TRQ_KI'] = {'min': 0.0, 'max': 100.0, 'description': '转矩环积分增益'}

        return {
            'allowed_parameters': allowed_parameters,
            'update_rule': '每轮只允许小幅修改 1 到 2 个参数；如果编译、仿真或评价失败，不修改参数。'
        }

    def _write_candidate_generated_result(self, candidate_dir: Path, loop_ids_path: Path, profile: dict):
        with open(loop_ids_path, 'r', encoding='utf-8') as f:
            loops_payload = json.load(f)
        if not isinstance(loops_payload, dict):
            return {}

        candidate_json = candidate_dir / 'candidate.json'
        with open(candidate_json, 'r', encoding='utf-8') as f:
            candidate_data = json.load(f)
        if not isinstance(candidate_data, dict):
            candidate_data = {}

        selected_loops = loops_payload.get('selected_loops') or []
        candidate_data['selected_loops'] = selected_loops
        candidate_data['generated_loop_ids_path'] = str(loop_ids_path)
        candidate_data['design_profile'] = profile
        candidate_data['tuning_policy'] = self._build_tuning_policy_from_loops(selected_loops)
        candidate_data.setdefault('paths', {})
        candidate_data['paths']['header_path'] = 'src/paras.generated.h'
        candidate_data['paths']['result_file'] = 'log/optimize/tuning_result.json'
        with open(candidate_json, 'w', encoding='utf-8') as f:
            json.dump(candidate_data, f, ensure_ascii=False, indent=2)

        configure_candidate_optimize(candidate_json)
        return candidate_data

    def _update_project_json_selected_loops(self, loop_ids_path: Path):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(loop_ids_path, 'r', encoding='utf-8') as f:
                loops_payload = json.load(f)
            if not isinstance(loops_payload, dict):
                return

            with open(project_json, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            if not isinstance(project_data, dict):
                project_data = {}

            project_data['selected_loops'] = loops_payload.get('selected_loops') or []
            project_data['generated_loop_ids_path'] = str(loop_ids_path)
            paths = project_data.get('paths')
            if not isinstance(paths, dict):
                paths = {}
                project_data['paths'] = paths
            paths['generated_loop_ids_path'] = str(loop_ids_path)

            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, ensure_ascii=False, indent=2)
            self._append_chat('system', f'已写入主程序结构到项目文件 {project_json.name}')
            self._generate_tuning_policy()
        except Exception as exc:
            self._append_chat('system', f'写入主程序结构失败：{exc}')

    def _generate_tuning_policy(self):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            selected_loops = data.get('selected_loops', [])
            data['tuning_policy'] = self._build_tuning_policy_from_loops(selected_loops)
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._append_chat('system', f'已生成调参策略到项目文件')
        except Exception as exc:
            self._append_chat('system', f'生成调参策略失败：{exc}')

    def on_chat_success(self, reply: str):
        self._append_chat('model', reply)
        self._apply_candidate_profile_overrides(reply)
        self.current_requirement = reply
        self._update_project_json_requirement(reply)
        self.status_label.setText('状态：需求已完善，可点击“生成程序”')

    def on_chat_failure(self, error_text: str):
        self._append_chat('system', f'对话失败：{error_text}')
        self.status_label.setText('状态：对话失败，请检查设置与网络')

    def on_chat_finished(self):
        self.send_btn.setEnabled(True)

    def generate_program(self):
        if not self.current_requirement:
            self._append_chat('system', '请先输入并发送需求，再执行生成。')
            self.status_label.setText('状态：缺少需求')
            return

        script_path = Path(__file__).resolve().parent.parent / 'run_llm_to_program.py'
        project_json = self._project_json_path()
        llm_config = MOTORAI_ROOT / 'motorai_settings.json'
        candidate_dirs = self._candidate_dirs()

        if not project_json or not candidate_dirs:
            self._append_chat('system', '未找到 candidate 工作区。请重新新建竞争模式工程。')
            self.status_label.setText('状态：缺少 candidate')
            return

        self.status_label.setText('状态：正在生成程序...')
        self._append_chat('system', f'开始为 {len(candidate_dirs)} 个 candidate 生成控制器程序。')

        try:
            sync_candidate_profiles_from_common(Path(project_json), candidate_dirs)
            candidate_summaries = []
            first_loop_ids_path = None
            first_candidate_data = None

            for index, candidate_dir in enumerate(candidate_dirs, start=1):
                profile = self._load_candidate_profile(candidate_dir, index)
                loop_ids_output = candidate_dir / 'log' / 'generate' / 'controller_loop_ids_generated.json'
                c_output = candidate_dir / 'src' / 'ctl_main.c'
                h_output = candidate_dir / 'src' / 'ctl_main.h'
                paras_output = candidate_dir / 'src' / 'paras.generated.h'
                loop_ids_output.parent.mkdir(parents=True, exist_ok=True)
                c_output.parent.mkdir(parents=True, exist_ok=True)

                candidate_requirement = build_candidate_generation_requirement(self.current_requirement, profile)
                write_candidate_generation_context(
                    candidate_dir / 'candidate.json',
                    self.current_requirement,
                    candidate_requirement,
                    profile,
                )
                profile_temperature = candidate_llm_temperature(profile)

                profile_name = profile.get("name", candidate_dir.name)
                self._append_chat('system', f'[{index}/{len(candidate_dirs)}] {candidate_dir.name} 生成 loop-ids：{profile_name}')
                loop_exporter.export_json(
                    output_path=loop_ids_output,
                    requirement=candidate_requirement,
                    settings_path=llm_config,
                    chat_text_caller=lambda system_prompt, user_prompt, temp: call_ui_chat_model(
                        user_prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=profile_temperature if profile_temperature is not None else temp,
                    ),
                    temperature_override=profile_temperature,
                )

                self._append_chat('system', f'[{index}/{len(candidate_dirs)}] {candidate_dir.name} 生成 ctl_main 与 paras')
                merger.main(
                    loop_ids_path=loop_ids_output,
                    template_path=script_path.parent.joinpath('Example', 'ctl_main.c'),
                    output_path=c_output,
                    header_template_path=script_path.parent.joinpath('Example', 'ctl_main.h'),
                    header_output_path=h_output,
                    paras_template_path=script_path.parent.joinpath('Example', 'paras.h'),
                    paras_output_path=paras_output,
                )

                candidate_data = self._write_candidate_generated_result(candidate_dir, loop_ids_output, profile)
                if first_loop_ids_path is None:
                    first_loop_ids_path = loop_ids_output
                    first_candidate_data = candidate_data

                candidate_summaries.append({
                    'candidate_id': candidate_dir.name,
                    'design_profile': profile,
                    'loop_ids': str(loop_ids_output),
                    'ctl_main_c': str(c_output),
                    'ctl_main_h': str(h_output),
                    'paras_header': str(paras_output),
                })

            if first_loop_ids_path is not None:
                self._update_project_json_selected_loops(first_loop_ids_path)

            with open(project_json, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            if not isinstance(project_data, dict):
                project_data = {}
            project_data['candidate_generation'] = candidate_summaries
            if isinstance(first_candidate_data, dict):
                project_data['selected_loops'] = first_candidate_data.get('selected_loops') or []
                project_data['tuning_policy'] = first_candidate_data.get('tuning_policy') or {}
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, ensure_ascii=False, indent=2)

            self.status_label.setText('状态：生成完成')
            self._append_chat('system', '所有 candidate 控制器程序生成完成。根目录 src 未被修改。')
            if callable(self.structure_refresh_callback):
                self.structure_refresh_callback()
        except Exception as exc:
            self.status_label.setText('状态：调用失败')
            self._append_chat('system', f'生成过程中发生异常：{exc}')

    def _project_folder(self):
        if callable(self.project_json_getter):
            pj = self.project_json_getter()
            if pj:
                try:
                    return Path(pj).parent
                except Exception:
                    pass
        return Path(__file__).resolve().parent.parent

    def _save_chat_record(self):
        record_path = self._project_folder() / 'record.json'
        try:
            data = {}
            if record_path.exists():
                with open(record_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data['main_program'] = self.chat_history
            with open(record_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_chat_record(self):
        record_path = self._project_folder() / 'record.json'
        if not record_path.exists():
            return
        try:
            with open(record_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.chat_history = data.get('main_program', [])
            for msg in self.chat_history:
                self.chat_view.append_message(msg.get('role', 'system'), msg.get('text', ''))
        except Exception:
            pass


class LoadCurvePanel(QWidget):
    def __init__(self, project_json_getter=None, parent=None):
        super().__init__(parent)
        self.project_json_getter = project_json_getter
        self._updating_table = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.chart_canvas = CurveCanvas()
        self.chart_hint = QLabel('说明：在下方输入两列数值后，曲线会自动更新。')
        self.chart_hint.setStyleSheet('color: #666;')

        self.table = QTableWidget(1, 2)
        self.table.setHorizontalHeaderLabels(['转速', '转矩'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.itemChanged.connect(self.ensure_trailing_row)

        layout.addWidget(QLabel('负载曲线设置'))
        layout.addWidget(self.chart_canvas, 2)
        layout.addWidget(self.chart_hint)
        layout.addWidget(self.table, 1)

        # bottom row with save button aligned to bottom-right of the table
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addStretch()
        self.save_btn = QPushButton('保存')
        self.save_btn.setObjectName('secondaryActionButton')
        self.save_btn.clicked.connect(self.save_to_csv)
        btn_layout.addWidget(self.save_btn)
        layout.addWidget(btn_row)

    def ensure_trailing_row(self, item):
        if self._updating_table:
            return
        if self.table.rowCount() == 0:
            self.table.insertRow(0)
        last_row = self.table.rowCount() - 1
        points = self.collect_points()
        self.chart_canvas.set_curve(points, title='负载曲线', x_label='转速', y_label='转矩')

        if item.row() != last_row:
            return

        row_has_data = False
        for col in range(self.table.columnCount()):
            cell = self.table.item(last_row, col)
            if cell and cell.text().strip():
                row_has_data = True
                break

        if row_has_data:
            self._updating_table = True
            try:
                self.table.blockSignals(True)
                self.table.insertRow(self.table.rowCount())
            finally:
                self.table.blockSignals(False)
                self._updating_table = False

    def collect_points(self):
        points = []
        for row in range(self.table.rowCount()):
            x_item = self.table.item(row, 0)
            y_item = self.table.item(row, 1)
            if not x_item or not y_item:
                continue
            x_text = x_item.text().strip()
            y_text = y_item.text().strip()
            if not x_text or not y_text:
                continue
            try:
                x_val = float(x_text)
                y_val = float(y_text)
            except ValueError:
                continue
            points.append((x_val, y_val))
        return points

    def _project_folder(self):
        if callable(self.project_json_getter):
            pj = self.project_json_getter()
            if pj:
                try:
                    return Path(pj).parent
                except Exception:
                    pass
        return Path(__file__).resolve().parent.parent

    def _simulate_folder(self):
        return self._project_folder() / 'common'

    def _candidate_simulate_folders(self):
        if not callable(self.project_json_getter):
            return []
        project_json = self.project_json_getter()
        if not project_json:
            return []
        try:
            return [candidate / 'project' / 'simulate' for candidate in discover_candidate_dirs(Path(project_json), ['all'])]
        except Exception:
            return []

    def save_to_csv(self):
        points = self.collect_points()
        if not points:
            QMessageBox.warning(self, '提示', '没有可保存的数据。')
            return
        out_dir = self._simulate_folder()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / 'load.csv'
        try:
            with open(out_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                for x, y in points:
                    writer.writerow([x, y])
            for candidate_sim_dir in self._candidate_simulate_folders():
                candidate_sim_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(out_path, candidate_sim_dir / 'load.csv')
            QMessageBox.information(self, '完成', f'已保存：{out_path}')
        except Exception as exc:
            QMessageBox.critical(self, '错误', f'保存失败：{exc}')

    def clear_points(self):
        self._updating_table = True
        try:
            self.table.blockSignals(True)
            while self.table.rowCount() > 0:
                self.table.removeRow(0)
            self.table.insertRow(0)
        finally:
            self.table.blockSignals(False)
            self._updating_table = False

    def add_point(self, x, y):
        self._updating_table = True
        try:
            self.table.blockSignals(True)
            row = self.table.rowCount()
            self.table.insertRow(row)
            x_item = QTableWidgetItem(str(x))
            y_item = QTableWidgetItem(str(y))
            self.table.setItem(row, 0, x_item)
            self.table.setItem(row, 1, y_item)
        finally:
            self.table.blockSignals(False)
            self._updating_table = False
            self.chart_canvas.set_curve(self.collect_points(), title='负载曲线', x_label='转速', y_label='转矩')

    def load_from_csv(self):
        csv_path = self._simulate_folder() / 'load.csv'
        if not csv_path.exists():
            return
        try:
            points = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(',')
                    if len(parts) >= 2:
                        try:
                            x_val = float(parts[0].strip())
                            y_val = float(parts[1].strip())
                            points.append((x_val, y_val))
                        except ValueError:
                            continue
            
            if points:
                self._updating_table = True
                self.table.blockSignals(True)
                try:
                    while self.table.rowCount() > 0:
                        self.table.removeRow(0)
                    
                    for idx, (x, y) in enumerate(points):
                        self.table.insertRow(idx)
                        x_item = QTableWidgetItem(str(x))
                        y_item = QTableWidgetItem(str(y))
                        self.table.setItem(idx, 0, x_item)
                        self.table.setItem(idx, 1, y_item)
                    
                    self.table.insertRow(self.table.rowCount())
                finally:
                    self.table.blockSignals(False)
                    self._updating_table = False
                
                self.chart_canvas.set_curve(self.collect_points(), title='负载曲线', x_label='转速', y_label='转矩')
        except Exception as exc:
            QMessageBox.critical(self, '错误', f'加载失败：{exc}')


class RequirementPanel(QWidget):
    def __init__(self, project_json_getter=None, parent=None):
        super().__init__(parent)
        self.chat_worker = None
        self.project_json_getter = project_json_getter
        self.chat_history = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.chat_view = ChatStreamWidget()
        self._append_chat('system', '请输入需求指标。')

        self.input_edit = ChatInputEdit()
        self.input_edit.setPlaceholderText('请输入需求指标描述...')
        self.input_edit.setFixedHeight(110)
        self.input_edit.enterPressed.connect(self.send_requirement)

        self.send_btn = QPushButton('发送需求')
        self.send_btn.setObjectName('primaryButton')
        self.send_btn.setStyleSheet(
            'QPushButton{background:#0f62fe;color:#ffffff;border:none;font-weight:600;}'
            'QPushButton:hover{background:#0a55df;}'
            'QPushButton:pressed{background:#0848c7;}'
            'QPushButton:disabled{background:#9abafc;color:#f8fbff;}'
        )
        self.send_btn.clicked.connect(self.send_requirement)

        self.clear_btn = QPushButton('清空')
        self.clear_btn.setObjectName('ghostButton')
        self.clear_btn.clicked.connect(self.input_edit.clear)

        self.status_label = QLabel('状态：等待输入需求指标')

        self.param_form = QWidget()
        self.param_form.setStyleSheet('background:#f4f4f4;border-radius:4px;')
        param_layout = QVBoxLayout(self.param_form)
        param_layout.setContentsMargins(10, 10, 10, 10)
        param_layout.setSpacing(8)
        param_layout.addWidget(QLabel('目标参数设置'))
        
        self.param_table = QTableWidget()
        self.param_table.setColumnCount(3)
        self.param_table.setHorizontalHeaderLabels(['信号名称', '目标值', '单位'])
        self.param_table.horizontalHeader().setStretchLastSection(True)
        self.param_table.verticalHeader().setVisible(False)
        self.param_table.setStyleSheet('QTableWidget{background:white;border:1px solid #ddd;}QHeaderView::section{background:#e0e0e0;padding:4px;}')
        param_layout.addWidget(self.param_table)

        input_bar = QWidget()
        input_bar_layout = QHBoxLayout(input_bar)
        input_bar_layout.setContentsMargins(0, 0, 0, 0)
        input_bar_layout.setSpacing(10)
        input_bar_layout.addWidget(self.input_edit, 1)

        side_actions = QWidget()
        side_actions_layout = QVBoxLayout(side_actions)
        side_actions_layout.setContentsMargins(0, 0, 0, 0)
        side_actions_layout.setSpacing(8)
        side_actions_layout.addWidget(self.send_btn)
        side_actions_layout.addWidget(self.clear_btn)
        side_actions_layout.addStretch()
        input_bar_layout.addWidget(side_actions)

        layout.addWidget(QLabel('需求指标设置'))
        layout.addWidget(self.chat_view, 1)
        layout.addWidget(self.param_form, 1)
        layout.addWidget(input_bar)
        layout.addWidget(self.status_label)

    def _append_chat(self, role: str, text: str):
        self.chat_view.append_message(role, text)
        self.chat_history.append({
            'role': role,
            'text': text,
            'timestamp': QDateTime.currentDateTime().toString(Qt.ISODate)
        })
        self._save_chat_record()

    def _project_folder(self):
        if callable(self.project_json_getter):
            pj = self.project_json_getter()
            if pj:
                try:
                    return Path(pj).parent
                except Exception:
                    pass
        return Path(__file__).resolve().parent.parent

    def _save_chat_record(self):
        record_path = self._project_folder() / 'record.json'
        try:
            data = {}
            if record_path.exists():
                with open(record_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data['requirement'] = self.chat_history
            with open(record_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_chat_record(self):
        record_path = self._project_folder() / 'record.json'
        if not record_path.exists():
            return
        try:
            with open(record_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.chat_history = data.get('requirement', [])
            for msg in self.chat_history:
                self.chat_view.append_message(msg.get('role', 'system'), msg.get('text', ''))
        except Exception:
            pass

    def load_from_project_json(self):
        """Load targets and other UI state from the current project JSON.
        Called by the main window when a project is opened.
        """
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            targets = data.get('targets', {})
            # ensure format: mapping signal -> {target_value, unit, description}
            if isinstance(targets, dict):
                self._update_param_table(targets)
        except Exception:
            pass

    def send_requirement(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        if self.chat_worker is not None and self.chat_worker.isRunning():
            self._append_chat('system', '正在等待上一条对话返回，请稍后。')
            return

        project_json = self._project_json_path()
        if not project_json:
            QMessageBox.warning(self, '提示', '请先打开项目文件。')
            return

        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            selected_loops = project_data.get('selected_loops', [])
            if not selected_loops:
                QMessageBox.warning(self, '提示', '请先在“主程序生成”中生成并保存 loop-ids 结果。')
                return
        except Exception as exc:
            QMessageBox.warning(self, '提示', f'读取项目文件失败：{exc}')
            return

        self._append_chat('user', text)
        self._append_chat('system', '正在调用大模型完善需求指标...')
        self.status_label.setText('状态：对话处理中...')
        self.send_btn.setEnabled(False)

        loop_info = '\n'.join([f"- {loop.get('name', '')}: {loop.get('description', '')}" for loop in selected_loops])
        existing_objective = project_data.get('objective', '')

        user_input = f"控制器结构：\n{loop_info}\n\n"
        if existing_objective:
            user_input += f"当前已有的需求指标：\n{existing_objective}\n\n"
        user_input += f"用户新增需求：\n{text}\n\n请对已有需求指标和新增需求进行整合，输出一句完整的需求指标描述。"

        self.chat_worker = ChatWorker(
            user_input,
            (
                '你是面向 loop-ids 生成系统的需求指标完善助手。'
                '你的任务是根据给定的控制器结构，把用户输入改写为可执行、可测量、适合控制器设计验证的中文需求指标。'
                '性能指标仅限于：超调量、调整时间、上升时间、稳态误差。'
                '当存在已有需求指标时，需要将其与新增需求进行整合、合并，保留合理的部分，去除冲突的部分。'
                '请在现有控制器结构的基础上设计指标，不要改变控制器结构。'
                '输出要求：用一句话简洁描述整合后的需求指标，不输出其他内容。'
            ),
            self,
        )
        self.chat_worker.success.connect(self.on_chat_success)
        self.chat_worker.failure.connect(self.on_chat_failure)
        self.chat_worker.finished.connect(self.on_chat_finished)
        self.chat_worker.start()
        self.input_edit.clear()

    def _project_json_path(self):
        if callable(self.project_json_getter):
            return self.project_json_getter()
        return None

    def _ctl_main_paths(self):
        project_json = self._project_json_path()
        if not project_json:
            return []

        base_dir = project_json.parent
        candidates = [
            base_dir / 'ctl_main.c',
            base_dir / 'src' / 'ctl_main.c',
        ]

        paths = []
        seen = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate.exists():
                paths.append(candidate)
        return paths

    def _format_float_literal(self, value):
        literal = f'{value:.6f}'.rstrip('0').rstrip('.')
        if not literal:
            literal = '0'
        if '.' not in literal and 'e' not in literal.lower():
            literal = f'{literal}.0'
        return f'{literal}f'

    def _rewrite_target_velocity_literal(self, content, target_speed):
        import re

        velocity_value = target_speed / 3000.0 * 9.55
        velocity_literal = self._format_float_literal(velocity_value)

        pattern = r'(ctl_set_mech_target_velocity\(&mech_ctrl,\s*)([^)]*?)(\)\s*;)'

        def repl(match):
            return f'{match.group(1)}{velocity_literal}{match.group(3)}'

        updated_content, count = re.subn(pattern, repl, content, count=1)
        return updated_content, bool(count)

    def _write_requirement_to_project_json(self, requirement_text: str):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            data['objective'] = requirement_text
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            write_common_requirement_snapshot(Path(project_json), data)
            self._append_chat('system', f'已写入需求指标到项目文件 {project_json.name}')
        except Exception as exc:
            self._append_chat('system', f'写入项目 JSON 失败：{exc}')

    METRICS_PARAM_TEMPLATES = {
        "overshoot": {
            "metric_name": "overshoot",
            "optimization_direction": "minimize",
            "normalize": True,
            "good_threshold": 0.10,
            "bad_threshold": 0.30,
            "description": "超调量，归一化后 0.10 表示 10%"
        },
        "settling_time": {
            "metric_name": "settling_time",
            "optimization_direction": "minimize",
            "tolerance_ratio": 0.05,
            "good_threshold": 0.20,
            "bad_threshold": 1.00,
            "description": "调节时间，进入并保持在目标值 ±5% 范围内所需时间"
        },
        "steady_state_error": {
            "metric_name": "steady_state_error",
            "optimization_direction": "minimize",
            "window": 0.10,
            "good_threshold": 15.708,
            "bad_threshold": 62.832,
            "description": "稳态误差，末尾 10% 数据窗口内的平均绝对误差"
        },
        "ripple": {
            "metric_name": "ripple",
            "optimization_direction": "minimize",
            "window": 0.10,
            "good_threshold": 0.02,
            "bad_threshold": 0.20,
            "description": "稳态纹波，末尾 10% 数据窗口内的峰峰值"
        }
    }

    PHYSICAL_QUANTITIES = {
        "speed": {"signal": "rotor_speed_rad_s", "target_value": 314.16, "weight": 0.25},
        "torque": {"signal": "electromagnetic_torque_nm", "target_value": 0.2, "weight": 0.15},
        "iq": {"signal": "stator_iq_a", "target_value": 3.0, "weight": 0.15},
        "id": {"signal": "stator_id_a", "target_value": 0.0, "weight": 0.15}
    }

    def on_chat_success(self, reply: str):
        self._append_chat('model', reply)
        self._write_requirement_to_project_json(reply)
        self._append_chat('system', '正在生成任务类型...')
        self._generate_task_type()
        self._append_chat('system', '正在生成信号、目标和事件...')
        self._generate_signals_targets_events()
        self._append_chat('system', '正在生成评价指标...')
        self._generate_metrics()
        self._append_chat('system', '正在生成目标参数...')
        self._generate_targets_from_metrics()
        self._append_chat('system', '正在生成停止条件...')
        self._generate_stop_conditions()
        self.status_label.setText('状态：需求指标已完善')

    def _generate_task_type(self):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            objective_text = data.get('objective_text', '')
            system_prompt = (
                '你是需求分析助手。请根据用户需求文本，总结出一句话描述用户设计的是什么控制系统。'
                '输出要求：仅输出任务类型，例如："PMSM速度控制系统"、"PMSM位置控制系统"、"永磁同步电机转矩控制系统"等。'
                '不要输出其他内容。'
            )
            result = call_ui_chat_model(objective_text, system_prompt, temperature=0.2)
            data['task_type'] = result.strip()
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self._append_chat('system', f'生成 task_type 失败：{exc}')

    def _generate_signals_targets_events(self):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            objective_text = data.get('objective_text', '')
            objective = data.get('objective', '')
            
            system_prompt = (
                '你是控制器分析助手。请分析用户需求中是否涉及以下控制环路类型：\n\n'
                '1. 机械环/速度环/位置环：涉及速度、位置、转速等控制要求\n'
                '2. 电流环：涉及电流、iq、id等控制要求\n\n'
                '输出格式要求（严格遵守）：\n'
                '1. 只输出JSON数组格式，不输出任何其他文字、解释或说明\n'
                '2. JSON必须是有效的，可以被标准JSON解析器解析\n'
                '3. 数组元素只能是 "mechanical"（机械环）和/或 "current"（电流环）\n'
                '4. 如果两种环都涉及，输出 ["mechanical", "current"]\n'
                '5. 如果都不涉及，输出空数组 []\n\n'
                '用户需求：' + objective + '\n\n'
                '请输出JSON数组：'
            )
            
            parsed = None
            max_retries = 2
            for attempt in range(max_retries + 1):
                result = call_ui_chat_model(objective, system_prompt, temperature=0.2)
                
                self._append_chat('system', f'大模型返回（环路分析）：{result.strip()}')
                
                if not result or not result.strip():
                    if attempt < max_retries:
                        self._append_chat('system', f'第{attempt+1}次调用返回为空，重新调用...')
                        system_prompt = f'你上次返回了空内容。请重新输出正确的JSON数组格式。\n\n只输出JSON数组，不要其他内容：'
                        continue
                    else:
                        self._append_chat('system', '多次调用返回为空，使用默认值')
                        parsed = []
                        break
                
                try:
                    parsed = json.loads(result.strip())
                    if isinstance(parsed, list):
                        break
                    else:
                        raise ValueError("返回内容不是有效的JSON数组")
                except (json.JSONDecodeError, ValueError) as e:
                    if attempt < max_retries:
                        self._append_chat('system', f'第{attempt+1}次调用解析失败({e})，重新调用...')
                        system_prompt = f'你上次返回的内容不是有效的JSON格式：{result.strip()}\n\n请重新输出正确的JSON数组格式。\n\n只输出JSON数组，不要其他内容：'
                        continue
                    else:
                        self._append_chat('system', f'多次调用解析失败({e})，使用默认值')
                        parsed = []
                        break
            
            speed_signals = [
                "rotor_angle_rad",
                "rotor_speed_rad_s",
                "electromagnetic_torque_nm"
            ]
            current_signals = [
                "stator_iq_a",
                "stator_id_a"
            ]
            
            available_signals = []
            if 'mechanical' in parsed:
                available_signals.extend(speed_signals)
            if 'current' in parsed:
                available_signals.extend(current_signals)
            
            data['available_signals'] = available_signals
            
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self._append_chat('system', f'生成 available_signals 失败：{exc}')

    def _generate_metrics(self):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            objective_text = data.get('objective_text', '')
            objective = data.get('objective', '')
            available_signals = data.get('available_signals', [])
            
            if not objective_text.strip() and not objective.strip():
                data['metrics'] = []
                with open(project_json, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return
            
            system_prompt = (
                '你是性能评价指标分析助手。请根据用户需求，分析需要测量哪些物理量的哪些参数。\n\n'
                '可选物理量：speed(速度), torque(转矩), iq(q轴电流), id(d轴电流)\n'
                '可选测量参数：overshoot(超调量), settling_time(调整时间), steady_state_error(稳态误差), ripple(纹波)\n\n'
                '输出格式要求（严格遵守）：\n'
                '1. 只输出JSON数组格式，不输出任何其他文字、解释或说明\n'
                '2. JSON必须是有效的，可以被标准JSON解析器解析\n'
                '3. 顶层必须是一个数组，数组元素是字符串，表示物理量-测量参数组合\n'
                '4. 每个字符串格式为：物理量_测量参数，如 "speed_overshoot", "torque_ripple"\n\n'
                '用户需求：' + objective + '\n\n'
                '请输出JSON数组：'
            )
            
            parsed = None
            max_retries = 2
            for attempt in range(max_retries + 1):
                result = call_ui_chat_model(objective, system_prompt, temperature=0.2)
                
                self._append_chat('system', f'大模型返回：{result.strip()}')
                
                if not result or not result.strip():
                    if attempt < max_retries:
                        self._append_chat('system', f'第{attempt+1}次调用返回为空，重新调用...')
                        system_prompt = f'你上次返回了空内容。请重新输出正确的JSON数组格式。\n\n只输出JSON数组，不要其他内容：'
                        continue
                    else:
                        self._append_chat('system', '多次调用返回为空，使用默认指标')
                        parsed = ["speed_overshoot", "speed_settling_time", "speed_steady_state_error"]
                        break
                
                try:
                    parsed = json.loads(result.strip())
                    if isinstance(parsed, list) and len(parsed) > 0:
                        break
                    else:
                        raise ValueError("返回内容不是有效的JSON数组或数组为空")
                except (json.JSONDecodeError, ValueError) as e:
                    if attempt < max_retries:
                        self._append_chat('system', f'第{attempt+1}次调用解析失败({e})，重新调用...')
                        system_prompt = f'你上次返回的内容不是有效的JSON格式：{result.strip()}\n\n请重新输出正确的JSON数组格式。\n\n只输出JSON数组，不要其他内容：'
                        continue
                    else:
                        self._append_chat('system', f'多次调用解析失败({e})，使用默认指标')
                        parsed = ["speed_overshoot", "speed_settling_time", "speed_steady_state_error"]
                        break
            
            metrics = []
            for combo in parsed:
                if isinstance(combo, str):
                    parts = combo.split('_', 1)
                    if len(parts) == 2:
                        physical_quantity = parts[0].strip().lower()
                        metric_param = parts[1].strip().lower()
                        
                        if physical_quantity in self.PHYSICAL_QUANTITIES and metric_param in self.METRICS_PARAM_TEMPLATES:
                            phys_info = self.PHYSICAL_QUANTITIES[physical_quantity]
                            param_template = self.METRICS_PARAM_TEMPLATES[metric_param]
                            
                            metric = {
                                "result_name": combo,
                                "signal": phys_info["signal"],
                                "target_value": phys_info["target_value"],
                                "weight": phys_info["weight"],
                            }
                            metric.update(param_template)
                            
                            if phys_info["signal"] in available_signals or not available_signals:
                                metrics.append(metric)
            
            data['metrics'] = metrics
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self._append_chat('system', f'生成 metrics 失败：{exc}')

    def _generate_targets_from_metrics(self):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            metrics = data.get('metrics', [])
            if not metrics:
                return
            
            signals_needed = set()
            for metric in metrics:
                signal = metric.get('signal')
                if signal:
                    signals_needed.add(signal)
            
            signal_info = {
                "rotor_speed_rad_s": {"unit": "rad/s", "description": "期望稳定转速"},
                "electromagnetic_torque_nm": {"unit": "N*m", "description": "期望稳定转矩"},
                "stator_iq_a": {"unit": "A", "description": "期望 q 轴电流"},
                "stator_id_a": {"unit": "A", "description": "期望 d 轴电流"}
            }
            
            targets = {}
            for signal in signals_needed:
                if signal in signal_info:
                    target_value = 0.0
                    for metric in metrics:
                        if metric.get('signal') == signal:
                            target_value = metric.get('target_value', 0.0)
                            break
                    
                    targets[signal] = {
                        "target_value": target_value,
                        "unit": signal_info[signal]["unit"],
                        "description": signal_info[signal]["description"]
                    }
            
            data['targets'] = targets
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self._update_param_table(targets)
        except Exception as exc:
            self._append_chat('system', f'生成 targets 失败：{exc}')

    def _update_param_table(self, targets):
        self.param_table.setRowCount(len(targets))
        row = 0
        for signal, target_info in targets.items():
            signal_item = QTableWidgetItem(signal)
            signal_item.setFlags(signal_item.flags() & ~Qt.ItemIsEditable)
            
            target_value_item = QTableWidgetItem(str(target_info.get('target_value', 0.0)))
            target_value_item.setData(Qt.UserRole, signal)
            
            unit_item = QTableWidgetItem(target_info.get('unit', ''))
            unit_item.setFlags(unit_item.flags() & ~Qt.ItemIsEditable)
            
            self.param_table.setItem(row, 0, signal_item)
            self.param_table.setItem(row, 1, target_value_item)
            self.param_table.setItem(row, 2, unit_item)
            row += 1
        
        self.param_table.itemChanged.connect(self._on_target_value_changed)

    def _on_target_value_changed(self, item):
        if item.column() != 1:
            return
        
        signal = item.data(Qt.UserRole)
        if not signal:
            return
        
        try:
            new_value = float(item.text())
        except ValueError:
            QMessageBox.warning(self, '提示', '请输入有效的数字')
            item.setText(str(self._get_current_target_value(signal)))
            return
        
        self._sync_target_value(signal, new_value)

    def _get_current_target_value(self, signal):
        project_json = self._project_json_path()
        if not project_json:
            return 0.0
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            targets = data.get('targets', {})
            return targets.get(signal, {}).get('target_value', 0.0)
        except Exception:
            return 0.0

    def _sync_target_value(self, signal, new_value):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'targets' in data and signal in data['targets']:
                data['targets'][signal]['target_value'] = new_value
            
            if 'metrics' in data:
                for metric in data['metrics']:
                    if metric.get('signal') == signal:
                        metric['target_value'] = new_value
            
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            if signal == 'rotor_speed_rad_s':
                self._update_ctl_main_target_velocity(new_value)
        except Exception as exc:
            self._append_chat('system', f'同步目标值失败：{exc}')

    def _update_ctl_main_target_velocity(self, target_speed):
        ctl_main_paths = self._ctl_main_paths()
        if not ctl_main_paths:
            return
        try:
            updated_paths = []
            for ctl_main_path in ctl_main_paths:
                with open(ctl_main_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                updated_content, changed = self._rewrite_target_velocity_literal(content, target_speed)
                if not changed:
                    continue

                with open(ctl_main_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
                updated_paths.append(ctl_main_path)

            if updated_paths:
                names = ', '.join(path.name for path in updated_paths)
                self._append_chat('system', f'已同步目标速度到 {names}')
            else:
                self._append_chat('system', '未找到可更新的 ctl_main.c 目标速度行')
        except Exception as exc:
            self._append_chat('system', f'更新 ctl_main.c 目标速度失败：{exc}')

    def _generate_stop_conditions(self):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['stop_conditions'] = {
                'overall_score_min': 85,
                'metric_error_count_max': 0
            }
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self._append_chat('system', f'生成 stop_conditions 失败：{exc}')

    def on_chat_failure(self, error_text: str):
        self._append_chat('system', f'对话失败：{error_text}')
        self.status_label.setText('状态：对话失败，请检查设置与网络')

    def on_chat_finished(self):
        self.send_btn.setEnabled(True)


class Design3RightPanel(QWidget):
    def __init__(self, project_json_getter=None, parent=None):
        super().__init__(parent)
        self.controller_panel = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.tabs = QTabWidget()
        self.main_program_panel = MainProgramPanel(
            project_json_getter=project_json_getter,
            structure_refresh_callback=self.refresh_structure,
        )
        self.tabs.addTab(self.main_program_panel, '主程序生成')
        self.tabs.addTab(LoadCurvePanel(project_json_getter=project_json_getter), '负载曲线设置')
        self.tabs.addTab(RequirementPanel(project_json_getter=project_json_getter), '需求指标设置')

        layout.addWidget(self.tabs)

    def set_controller_panel(self, controller_panel):
        self.controller_panel = controller_panel

    def refresh_structure(self):
        if self.controller_panel is not None:
            self.controller_panel.refresh_from_project()


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_project_json_path = None
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
        file_menu.addAction(self.action_new)
        file_menu.addAction(self.action_save)
        file_menu.addAction(self.action_load)
        file_menu.addAction(self.action_settings)
        self.action_new.triggered.connect(self.open_new_project_dialog)
        self.action_load.triggered.connect(self.open_project_json)
        self.action_save.triggered.connect(self.save_project_json)
        self.action_settings.triggered.connect(self.open_settings_dialog)

        file_button = QPushButton('文件')
        file_button.setMenu(file_menu)
        file_button.setStyleSheet(
            'QPushButton { border: none; background: transparent; padding: 4px 8px; font-size: 24px; color: black; }'
            'QPushButton::menu-indicator { image: none; width: 0px; }'
            'QPushButton:hover { background: #e5e5e5; }'
        )
        toolbar_layout.addWidget(file_button)

        self.run_agent_button = QPushButton('运行调优')
        self.run_agent_button.setObjectName('primaryButton')
        self.run_agent_button.setStyleSheet(
            'QPushButton{background:#0f62fe;color:#ffffff;border:none;font-weight:600;padding:6px 16px;border-radius:4px;}'
            'QPushButton:hover{background:#0a55df;}'
            'QPushButton:pressed{background:#0848c7;}'
            'QPushButton:disabled{background:#9abafc;color:#f8fbff;}'
        )
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
        self.left_controller_panel.setStyleSheet('background: #ffffff; border: 1px solid #ddd;')
        self.tuning_result_panel = TuningResultPanel(project_json_getter=self.get_current_project_json_path)
        self.tuning_result_panel.setStyleSheet('background: #ffffff; border: 1px solid #ddd;')

        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.setChildrenCollapsible(False)
        left_splitter.addWidget(self.left_controller_panel)
        left_splitter.addWidget(self.tuning_result_panel)
        left_splitter.setStretchFactor(0, 3)
        left_splitter.setStretchFactor(1, 2)
        left_splitter.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        left_splitter.setMinimumWidth(0)

        self.right_panel_widget = Design3RightPanel(project_json_getter=self.get_current_project_json_path)
        self.right_panel_widget.setStyleSheet('background: #ffffff; border: 1px solid #ddd;')
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
        info_label.setStyleSheet('color: #475467; font-weight: 600;')
        info_layout.addWidget(info_label)
        info_layout.addStretch()
        user_label = QLabel('User: Guest')
        user_label.setStyleSheet('color: #475467;')
        info_layout.addWidget(user_label)
        self.info_widget.setMinimumHeight(46)
        self.info_widget.setStyleSheet('background: #f7f9fc;')

        # Assemble main layout
        main_layout.addWidget(toolbar)
        main_layout.addWidget(central)
        main_layout.addWidget(self.info_widget)

        self.setCentralWidget(container)
        self._apply_visual_theme()
        self._install_surface_effects()

    def _apply_visual_theme(self):
        self.setStyleSheet(
            """
            QMainWindow {
                background: #eef2f7;
            }
            QWidget {
                color: #1f2937;
                font-family: Segoe UI, Microsoft YaHei, Arial;
                font-size: 10pt;
            }
            QLabel {
                color: #1f2937;
            }
            QFrame#ControllerStructureCanvas,
            QFrame#CurveCanvas,
            QTextEdit,
            QTableWidget,
            QTabWidget::pane,
            QMenu,
            QDialog,
            QWidget#panelCard {
                background: #ffffff;
                border: 1px solid #d9e2ec;
                border-radius: 14px;
            }
            QFrame#chatBubble_user {
                background: #0f62fe;
                color: #ffffff;
                border: none;
                border-top-left-radius: 18px;
                border-top-right-radius: 18px;
                border-bottom-left-radius: 18px;
                border-bottom-right-radius: 4px;
            }
            QFrame#chatBubble_model {
                background: #ffffff;
                color: #1f2937;
                border: 1px solid #d9e2ec;
                border-top-left-radius: 18px;
                border-top-right-radius: 18px;
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 18px;
            }
            QFrame#systemBubble {
                background: #eef2f7;
                color: #64748b;
                border: 1px solid #d9e2ec;
                border-radius: 999px;
            }
            QLabel#chatBubbleTitle {
                font-size: 14pt;
                font-weight: 700;
                color: rgba(255,255,255,0.90);
            }
            QFrame#chatBubble_user QLabel#chatBubbleTitle,
            QFrame#chatBubble_user QLabel#chatBubbleBody {
                color: #ffffff;
            }
            QFrame#chatBubble_model QLabel#chatBubbleTitle {
                color: #0f62fe;
            }
            QFrame#chatBubble_model QLabel#chatBubbleBody {
                color: #1f2937;
            }
            QFrame#systemBubble QLabel#chatBubbleTitle {
                color: #64748b;
            }
            QFrame#systemBubble QLabel#chatBubbleBody {
                color: #64748b;
            }
            QLabel#chatBubbleBody {
                font-size: 11pt;
                line-height: 1.55;
            }
            QTabWidget::pane {
                padding: 6px;
            }
            QTabBar::tab {
                background: #e9eef5;
                color: #344054;
                border: 1px solid #cfd8e3;
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                min-width: 120px;
                padding: 8px 14px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0f62fe;
                font-weight: 600;
            }
            QTabBar::tab:hover {
                background: #f6f8fc;
            }
            QPushButton {
                background: #ffffff;
                color: #0f172a;
                border: 1px solid #cfd8e3;
                border-radius: 10px;
                padding: 7px 14px;
                min-height: 18px;
            }
            QPushButton:hover {
                background: #f3f7ff;
                border-color: #7da7ff;
            }
            QPushButton:pressed {
                background: #dce8ff;
            }
            QPushButton#primaryButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f62fe, stop:1 #1d7bff);
                color: white;
                border: none;
                font-weight: 600;
            }
            QPushButton#primaryButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0a55df, stop:1 #1769dd);
            }
            QPushButton#ghostButton,
            QPushButton#secondaryActionButton {
                background: #f8fafc;
                color: #344054;
                border: 1px solid #d6deea;
                font-weight: 600;
            }
            QPushButton#secondaryActionButton {
                min-width: 112px;
            }
            QPushButton#ghostButton:hover,
            QPushButton#secondaryActionButton:hover {
                background: #eef4ff;
                border-color: #9fb7ff;
            }
            QToolButton {
                background: #ffffff;
                color: #0f172a;
                border: 1px solid #cfd8e3;
                border-radius: 10px;
                padding: 7px 14px;
            }
            QToolButton:hover {
                background: #f3f7ff;
                border-color: #7da7ff;
            }
            QTextEdit {
                padding: 10px;
                selection-background-color: #dbeafe;
                line-height: 1.4;
            }
            QTableWidget {
                gridline-color: #e1e8f0;
                selection-background-color: #dbeafe;
                selection-color: #111827;
            }
            QHeaderView::section {
                background: #f2f6fb;
                color: #344054;
                border: none;
                border-bottom: 1px solid #d9e2ec;
                padding: 8px 10px;
                font-weight: 600;
            }
            QMenu {
                border: 1px solid #d9e2ec;
                padding: 6px;
            }
            QMenu::item {
                padding: 8px 24px 8px 18px;
                border-radius: 8px;
                margin: 2px 0;
            }
            QMenu::item:selected {
                background: #eaf1ff;
                color: #0f62fe;
            }
            QDialog {
                background: #f7f9fc;
            }
            """
        )

    def _install_surface_effects(self):
        for widget in [self.left_controller_panel, self.right_panel(), self.info_bar()]:
            effect = QGraphicsDropShadowEffect(widget)
            effect.setBlurRadius(26)
            effect.setXOffset(0)
            effect.setYOffset(6)
            effect.setColor(QColor(31, 41, 55, 38))
            widget.setGraphicsEffect(effect)

    def right_panel(self):
        return getattr(self, 'right_panel_widget', None)

    def info_bar(self):
        return getattr(self, 'info_widget', None)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec_()

    def open_new_project_dialog(self):
        dialog = NewProjectDialog(self)
        if dialog.exec_() == QDialog.Accepted and dialog.project_json_path:
            self.current_project_json_path = Path(dialog.project_json_path)
            QMessageBox.information(self, '已加载项目', f'当前项目：{self.current_project_json_path}')
            self._refresh_project_panels()
            self._load_panel_data()

    def get_current_project_json_path(self):
        return self.current_project_json_path

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
                candidate_count = int(project_data.get('candidate_count') or 4)
                subprocess.Popen([
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
                ])
                QMessageBox.information(self, '已启动', '多 candidate 调优任务已启动，将按 candidate_01、candidate_02... 串行迭代，请查看终端输出')
                return

            run_agent_script = Path(__file__).parent / 'run_agent.py'
            if not run_agent_script.exists():
                QMessageBox.warning(self, '提示', f'未找到脚本文件：{run_agent_script}')
                return

            subprocess.Popen([sys.executable, str(run_agent_script), str(project_json_path)])
            QMessageBox.information(self, '已启动', '调优任务已启动，请查看终端输出')
        except Exception as exc:
            QMessageBox.error(self, '错误', f'启动失败：{exc}')

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
        if right_panel and hasattr(right_panel, 'tabs'):
            for i in range(right_panel.tabs.count()):
                widget = right_panel.tabs.widget(i)
                if hasattr(widget, '_load_chat_record'):
                    widget._load_chat_record()
                if hasattr(widget, 'load_from_csv'):
                    widget.load_from_csv()
                # call new project load hook if present
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
