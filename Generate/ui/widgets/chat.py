from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QWidget,
    QVBoxLayout,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import json
import os
import urllib.error
import urllib.request

import core.paths  # ensures repository roots are on sys.path
from motorai_config import get_llm_settings, load_settings


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
        for role, _row, content in self.message_rows:
            if role == '__widget__' and content is not None:
                content.hide()
                content.setParent(None)
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

    def append_widget(self, widget: QWidget, width_ratio: float = 0.92):
        last_item = self.container_layout.itemAt(self.container_layout.count() - 1)
        if last_item and last_item.spacerItem():
            self.container_layout.takeAt(self.container_layout.count() - 1)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        row_layout.addStretch(1)
        row_layout.addWidget(widget)
        row_layout.addStretch(1)

        widget.show()
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.container_layout.addWidget(row)
        self.container_layout.addStretch(1)
        self.message_rows.append(('__widget__', row, widget))
        widget.setProperty('chatWidthRatio', width_ratio)
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
            elif role == '__widget__':
                ratio = bubble.property('chatWidthRatio')
                try:
                    ratio = float(ratio)
                except (TypeError, ValueError):
                    ratio = 0.92
                target_width = max(240, int(content_width * ratio))
                bubble.setFixedWidth(max(1, min(content_width, target_width)))
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
