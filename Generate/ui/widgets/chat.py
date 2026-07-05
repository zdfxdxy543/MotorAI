from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QWidget,
    QVBoxLayout,
)
from PyQt5.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QMovie
import json
import os
import urllib.error
import urllib.request

import core.paths  # ensures repository roots are on sys.path
from core.paths import GENERATE_ROOT
from motorai_config import get_llm_settings, load_settings
from styles.theme import (
    COLOR_MUTED,
    COLOR_PANEL,
    COLOR_PRIMARY,
    COLOR_PRIMARY_SOFT,
    COLOR_SURFACE,
    COLOR_TEXT,
    RADIUS_BUBBLE,
    RADIUS_CARD,
    transparent_qss,
)


CHAT_LINE_CHARS = 30


def _font_text_width(metrics, text: str) -> int:
    if hasattr(metrics, 'horizontalAdvance'):
        return metrics.horizontalAdvance(text)
    return metrics.width(text)


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
        self.role = self._normalize_role(role)
        self.raw_text = text or ''
        self.setFrameShape(QFrame.NoFrame)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.setMinimumWidth(0)
        self.setObjectName(f'chatBubble_{self.role}')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        
        self.avatar = QLabel()
        self.avatar.setFixedSize(44, 44)
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setStyleSheet(transparent_qss())

        self.title = QLabel('')
        self.title.setObjectName('chatBubbleTitle')
        
        self.header_widget = QWidget()
        self.header_widget.setStyleSheet(transparent_qss())
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        header_layout.addWidget(self.avatar)
        header_layout.addWidget(self.title)
        header_layout.addStretch()

        self.body = QLabel(self.raw_text)
        self.body.setObjectName('chatBubbleBody')
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.body.setStyleSheet('background: transparent;')
        self.body.setMinimumWidth(0)

        layout.addWidget(self.header_widget)
        layout.addWidget(self.body)

        if self.role == 'user':
            self.header_widget.hide()
            layout.setContentsMargins(16, 12, 16, 12)
            self.setStyleSheet(
                f'QFrame#chatBubble_user{{background:{COLOR_PRIMARY};border:none;border-radius:{RADIUS_BUBBLE}px;}}'
                'QFrame#chatBubble_user * { border: none; }'
            )
            self.body.setStyleSheet(f'color:{COLOR_SURFACE};background:transparent;border:none;')
        elif self.role == 'assistant':
            self.title.setText('MotorAI')
            self.avatar.hide()
            layout.setContentsMargins(16, 12, 16, 12)
            self.setStyleSheet(
                f'QFrame#chatBubble_assistant{{background:{COLOR_SURFACE};border:1px solid #e5edf6;'
                f'border-radius:{RADIUS_BUBBLE}px;}}'
                'QFrame#chatBubble_assistant * { outline: none; }'
            )
            self.title.setStyleSheet(f'color:{COLOR_MUTED};font-size:10pt;font-weight:600;border:none;background:transparent;')
            self.body.setStyleSheet(f'color:{COLOR_TEXT};background:transparent;border:none;')
        elif self.role == 'debug':
            self._apply_debug_style(layout)
        else:
            self.role = 'assistant'

    @staticmethod
    def _normalize_role(role: str) -> str:
        role = (role or 'assistant').strip().lower()
        if role in {'model', 'system', 'notice', 'success', 'error'}:
            return 'assistant'
        if role in {'progress', 'debug'}:
            return 'debug'
        if role in {'user', 'assistant'}:
            return role
        return 'assistant'

    def _apply_debug_style(self, layout: QVBoxLayout):
        self.header_widget.hide()
        layout.setContentsMargins(12, 8, 12, 8)
        self.setStyleSheet(
            f'QFrame#chatBubble_debug{{background:{COLOR_PANEL};border:none;border-radius:{RADIUS_CARD}px;}}'
            'QFrame#chatBubble_debug * { border: none; }'
        )
        self.body.setStyleSheet(f'color:{COLOR_MUTED};background:transparent;border:none;font-family:Consolas, Microsoft YaHei, monospace;')
        self.body.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.body.hide()

        self.debug_toggle = QPushButton('调试详情')
        self.debug_toggle.setCursor(Qt.PointingHandCursor)
        self.debug_toggle.setStyleSheet(
            f'QPushButton{{background:transparent;color:{COLOR_MUTED};font-weight:600;padding:0;text-align:left;}}'
            f'QPushButton:hover{{color:{COLOR_PRIMARY};}}'
        )
        self.debug_toggle.clicked.connect(self._toggle_debug_body)
        layout.insertWidget(0, self.debug_toggle)

    def _toggle_debug_body(self):
        visible = not self.body.isVisible()
        self.body.setVisible(visible)
        self.debug_toggle.setText('收起调试详情' if visible else '调试详情')
        stream = self.parent()
        while stream is not None and not hasattr(stream, '_scroll_to_bottom'):
            stream = stream.parent()
        if stream is not None:
            stream._scroll_to_bottom()

    def append_text(self, text: str):
        next_text = text or ''
        if not next_text:
            return
        self.raw_text = f'{self.raw_text}\n{next_text}' if self.raw_text else next_text
        self.body.setText(self.raw_text)

    def preferred_width(self, content_width: int) -> int:
        margins = self.layout().contentsMargins()
        horizontal_padding = margins.left() + margins.right()
        available = max(1, content_width - 36)

        if self.role in {'user', 'assistant'}:
            max_body_width = self._line_width(CHAT_LINE_CHARS)
            body_width = min(max_body_width, self._raw_text_width())
            body_width = max(self._min_body_width(), body_width)
            if self.role == 'assistant' and self.title.isVisible():
                body_width = max(body_width, _font_text_width(self.title.fontMetrics(), 'MotorAI'))
            target = body_width + horizontal_padding
            body_available = max(1, min(available, target) - horizontal_padding)
            self.body.setFixedWidth(body_available)
            return max(1, min(available, target))

        max_status_width = min(available, self._line_width(28) + horizontal_padding)
        target = min(max_status_width, max(160, self._raw_text_width() + horizontal_padding))
        self.body.setMaximumWidth(max(1, target - horizontal_padding))
        return max(1, target)

    def _line_width(self, char_count: int) -> int:
        return _font_text_width(self.body.fontMetrics(), '测' * char_count)

    def _min_body_width(self) -> int:
        return _font_text_width(self.body.fontMetrics(), '收到')

    def _raw_text_width(self) -> int:
        metrics = self.body.fontMetrics()
        lines = (self.raw_text or '').splitlines() or ['']
        widths = [_font_text_width(metrics, line) for line in lines]
        return max(widths) if widths else self._min_body_width()


class ThinkingIndicatorWidget(QFrame):
    def __init__(self, text: str = '正在思考中', parent=None):
        super().__init__(parent)
        self.setObjectName('thinkingIndicator')
        self.setFrameShape(QFrame.NoFrame)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.setStyleSheet(
            'QFrame#thinkingIndicator{background:transparent;border:none;}'
            'QFrame#thinkingIndicator QLabel{background:transparent;border:none;}'
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        self.gif_label = QLabel()
        self.gif_label.setFixedSize(28, 28)
        self.gif_label.setAlignment(Qt.AlignCenter)
        self.gif_label.setStyleSheet(transparent_qss())
        self.movie = None

        gif_path = GENERATE_ROOT / '旋转.gif'
        if gif_path.exists():
            self.movie = QMovie(str(gif_path))
            self.movie.setScaledSize(QSize(28, 28))
            self.gif_label.setMovie(self.movie)
            self.movie.start()
        else:
            self.gif_label.setText('M')
            self.gif_label.setStyleSheet(
                f'background:{COLOR_PRIMARY_SOFT};color:{COLOR_PRIMARY};border:none;'
                'border-radius:14px;font-weight:700;'
            )

        self.text_label = QLabel(text)
        self.text_label.setStyleSheet(f'color:{COLOR_MUTED};font-weight:600;')

        layout.addWidget(self.gif_label)
        layout.addWidget(self.text_label)

    def stop(self):
        if self.movie is not None:
            self.movie.stop()

    def preferred_width(self, content_width: int) -> int:
        width = 28 + 8 + _font_text_width(self.text_label.fontMetrics(), self.text_label.text()) + 8
        return max(1, min(max(1, content_width - 36), width))


class ChatStreamWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.messages = []
        self.message_rows = []
        self._thinking_row = None
        self._thinking_widget = None
        self.setObjectName('chatStreamWidget')
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet('QWidget#chatStreamWidget{background:transparent;border:none;}')

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
        self.container.setObjectName('chatStreamContainer')
        self.container.setAttribute(Qt.WA_StyledBackground, True)
        self.container.setStyleSheet('QWidget#chatStreamContainer{background:transparent;border:none;}')
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(12, 12, 12, 12)
        self.container_layout.setSpacing(14)
        self.container_layout.addStretch(1)

        self.scroll.setWidget(self.container)
        outer_layout.addWidget(self.scroll)

    def clear_messages(self):
        for role, _row, content in self.message_rows:
            if role == '__thinking__' and hasattr(content, 'stop'):
                content.stop()
            if role == '__widget__' and content is not None:
                content.hide()
                content.setParent(None)
        self._thinking_row = None
        self._thinking_widget = None
        self.messages.clear()
        self.message_rows.clear()
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.container_layout.addStretch(1)

    def append_message(self, role: str, text: str):
        role = ChatBubbleWidget._normalize_role(role)
        if role == 'debug' and self._append_to_last_debug(text):
            self.messages.append((role, text))
            self._update_bubble_widths()
            self._scroll_to_bottom()
            return

        self.messages.append((role, text))

        self._remove_trailing_stretch()

        row = QWidget()
        row.setAttribute(Qt.WA_StyledBackground, True)
        row.setStyleSheet('background:transparent;border:none;')
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)

        bubble = ChatBubbleWidget(role, text)
        bubble.adjustSize()

        if role == 'user':
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0, Qt.AlignRight)
            row_layout.addSpacing(18)
        elif role in {'assistant', 'debug'}:
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
        self._scroll_to_bottom()

    def _append_to_last_debug(self, text: str) -> bool:
        if not self.message_rows:
            return False
        role, _row, bubble = self.message_rows[-1]
        if role != 'debug' or not hasattr(bubble, 'append_text'):
            return False
        bubble.append_text(text)
        return True

    def append_widget(self, widget: QWidget, width_ratio: float = 0.92):
        self._remove_trailing_stretch()

        row = QWidget()
        row.setAttribute(Qt.WA_StyledBackground, True)
        row.setStyleSheet('background:transparent;border:none;')
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
        self._scroll_to_bottom()

    def show_thinking(self, text: str = '正在思考中'):
        if self._thinking_row is not None:
            return

        self._remove_trailing_stretch()

        row = QWidget()
        row.setAttribute(Qt.WA_StyledBackground, True)
        row.setStyleSheet('background:transparent;border:none;')
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        row_layout.addSpacing(18)

        indicator = ThinkingIndicatorWidget(text)
        row_layout.addWidget(indicator, 0, Qt.AlignLeft)
        row_layout.addStretch(1)

        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.container_layout.addWidget(row)
        self.container_layout.addStretch(1)
        self.message_rows.append(('__thinking__', row, indicator))
        self._thinking_row = row
        self._thinking_widget = indicator
        self._update_bubble_widths()
        self._scroll_to_bottom()

    def hide_thinking(self):
        if self._thinking_row is None:
            return
        if self._thinking_widget is not None and hasattr(self._thinking_widget, 'stop'):
            self._thinking_widget.stop()
        for index in range(self.container_layout.count()):
            item = self.container_layout.itemAt(index)
            if item and item.widget() is self._thinking_row:
                self.container_layout.takeAt(index)
                break
        self.message_rows = [
            item for item in self.message_rows
            if item[0] != '__thinking__' or item[1] is not self._thinking_row
        ]
        self._thinking_row.hide()
        self._thinking_row.setParent(None)
        self._thinking_row.deleteLater()
        self._thinking_row = None
        self._thinking_widget = None
        self._ensure_trailing_stretch()
        self._scroll_to_bottom()

    def _remove_trailing_stretch(self):
        last_item = self.container_layout.itemAt(self.container_layout.count() - 1)
        if last_item and last_item.spacerItem():
            self.container_layout.takeAt(self.container_layout.count() - 1)

    def _ensure_trailing_stretch(self):
        last_item = self.container_layout.itemAt(self.container_layout.count() - 1)
        if not (last_item and last_item.spacerItem()):
            self.container_layout.addStretch(1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_bubble_widths()
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(0, self._scroll_to_bottom_now)
        QTimer.singleShot(50, self._scroll_to_bottom_now)

    def _scroll_to_bottom_now(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _update_bubble_widths(self):
        viewport_width = max(0, self.scroll.viewport().width())
        content_width = max(0, viewport_width - 24)
        system_width = int(content_width * 0.66)

        for role, _row, bubble in self.message_rows:
            if role in {'user', 'assistant'}:
                bubble.setFixedWidth(bubble.preferred_width(content_width))
            elif role == '__widget__':
                ratio = bubble.property('chatWidthRatio')
                try:
                    ratio = float(ratio)
                except (TypeError, ValueError):
                    ratio = 0.92
                target_width = max(240, int(content_width * ratio))
                bubble.setFixedWidth(max(1, min(content_width, target_width)))
            elif role == '__thinking__':
                bubble.setFixedWidth(bubble.preferred_width(content_width))
            else:
                if hasattr(bubble, 'preferred_width'):
                    bubble.setFixedWidth(min(system_width, bubble.preferred_width(content_width)))
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
