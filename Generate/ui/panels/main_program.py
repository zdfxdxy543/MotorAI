from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtGui import QMovie
import json
from pathlib import Path

from core.paths import GENERATE_ROOT, MOTORAI_ROOT
from widgets.chat import ChatInputEdit, ChatStreamWidget, ChatWorker, call_ui_chat_model
from workflow.agent_flow import (
    ACTION_ANSWER_QUESTION,
    ACTION_CLARIFY,
    ACTION_CONFIRM_GENERATE,
    ACTION_REVISE_PROGRAM,
    ACTION_SHOW_LOAD_CURVE,
    ACTION_START_TUNING,
    ACTION_SUBMIT_METRICS,
    FlowRouteWorker,
    heuristic_route,
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
    sync_candidate_profiles_from_common,
    write_candidate_generation_context,
    write_common_requirement_snapshot,
)


class MainProgramPanel(QWidget):
    def __init__(self, project_json_getter=None, structure_refresh_callback=None, parent=None):
        super().__init__(parent)
        self.current_requirement = ''
        self.chat_worker = None
        self.route_worker = None
        self._chat_task = None
        self._pending_route_text = ''
        self.project_json_getter = project_json_getter
        self.structure_refresh_callback = structure_refresh_callback
        self.chat_history = []
        self.load_curve_panel = None
        self.requirement_panel = None
        self.run_tuning_callback = None
        self.input_mode = 'agent'
        self._workflow_steps = set()
        self._main_content_widgets = []
        self._load_curve_card_count = 0
        self._auto_tuning_started = False
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        self.title_label = QLabel('主程序生成')
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
        self._main_content_widgets = []
        self._set_program_input_mode()
        
        self.welcome_overlay.show()
        self.main_layout.addWidget(self.welcome_overlay)
    
    def show_main_content(self):
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()

        self._main_content_widgets = [
            self.title_label,
            self.chat_view,
            self.input_row,
            self.status_label,
        ]
        self.main_layout.addWidget(self.title_label)
        self.main_layout.addWidget(self.chat_view, 1)
        self.main_layout.addWidget(self.input_row)
        self.main_layout.addWidget(self.status_label)
        
        self.chat_view.show()
        self.input_row.show()
        self.action_row.hide()
        self.status_label.show()
        self.title_label.show()

    def _welcome_is_active(self):
        for index in range(self.main_layout.count()):
            item = self.main_layout.itemAt(index)
            if item and item.widget() is self.welcome_overlay:
                return True
        return False

    def set_workflow_widgets(self, load_curve_panel=None, requirement_panel=None, run_tuning_callback=None):
        self.load_curve_panel = load_curve_panel
        self.requirement_panel = requirement_panel
        self.run_tuning_callback = run_tuning_callback

        if self.load_curve_panel is not None:
            self.load_curve_panel.setMinimumHeight(520)
            if hasattr(self.load_curve_panel, 'set_save_callback'):
                self.load_curve_panel.set_save_callback(self._on_load_curve_saved)

        if self.requirement_panel is not None:
            if hasattr(self.requirement_panel, 'set_completion_callback'):
                self.requirement_panel.set_completion_callback(self._on_requirement_ready)
            if hasattr(self.requirement_panel, 'set_external_callbacks'):
                self.requirement_panel.set_external_callbacks(
                    chat_callback=self._append_chat,
                    status_callback=self._set_status_text,
                    finished_callback=self._on_metric_requirement_finished,
                )

        if self.chat_history and not self._welcome_is_active():
            self._restore_workflow_from_project()

    def _make_flow_card(self, title: str, subtitle: str, body_widget: QWidget | None = None) -> QFrame:
        card = QFrame()
        card.setObjectName('workflowCard')
        card.setStyleSheet(
            'QFrame#workflowCard{background:#ffffff;border:1px solid #d9e2ec;border-radius:14px;}'
            'QFrame#workflowCard QLabel{border:none;background:transparent;}'
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setStyleSheet('font-size:13pt;font-weight:700;color:#0f172a;')
        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet('color:#64748b;')
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        if body_widget is not None:
            layout.addWidget(body_widget)
            body_widget.setVisible(True)

        return card

    def _append_workflow_widget(self, key: str, widget: QWidget, width_ratio: float = 0.94):
        if key in self._workflow_steps:
            return
        self._workflow_steps.add(key)
        if self._welcome_is_active():
            self.show_main_content()
        self.chat_view.append_widget(widget, width_ratio=width_ratio)

    def show_load_curve_card(self, announce: bool = True, force: bool = False):
        if self.load_curve_panel is None:
            return
        if 'load_curve' in self._workflow_steps and not force:
            return
        if announce:
            self._append_chat('system', '请在下方设置负载曲线。保存后可以继续输入指标，也可以随时要求重画。')
        card = self._make_flow_card(
            '负载曲线设置',
            '输入转速和转矩点，保存后会同步到 common/load.csv 和各 candidate 仿真目录。',
            self.load_curve_panel,
        )
        if 'load_curve' not in self._workflow_steps:
            key = 'load_curve'
        else:
            self._load_curve_card_count += 1
            key = f'load_curve_{self._load_curve_card_count}'
        self._append_workflow_widget(key, card)

    def show_tuning_entry_card(self, announce: bool = True):
        self._auto_start_tuning_if_ready(force=False, announce=announce)

    def _on_load_curve_saved(self):
        self._append_chat(
            'system',
            '负载曲线已保存。请在下方输入详细的指标需求；如果还想重画负载曲线，也可以直接告诉我。'
        )
        self._set_metric_input_mode()
        if self._has_metrics_ready():
            self._auto_start_tuning_if_ready(force=True)

    def _on_requirement_ready(self):
        self._auto_start_tuning_if_ready(force=False)

    def _set_status_text(self, text: str):
        self.status_label.setText(text)

    def _set_program_input_mode(self):
        self.input_mode = 'agent'
        self.input_edit.setPlaceholderText('可以继续补充需求；确认方案后回复“生成程序”。')
        self.send_btn.setText('发送')
        self.run_btn.setEnabled(False)
        self.status_label.setText('状态：等待输入')

    def _set_metric_input_mode(self):
        self.input_mode = 'agent'
        self.input_edit.setPlaceholderText('请输入指标需求；也可以要求重画负载曲线、补充程序需求或继续提问。')
        self.send_btn.setText('发送')
        self.run_btn.setEnabled(False)
        self.status_label.setText('状态：等待输入需求指标')

    def _on_metric_requirement_finished(self):
        self.send_btn.setEnabled(True)

    def _run_tuning_from_chat(self):
        self._append_chat('system', '正在启动调优任务...')
        if callable(self.run_tuning_callback):
            self.run_tuning_callback()

    def _detach_workflow_panels(self):
        for panel in (self.load_curve_panel, self.requirement_panel):
            if panel is not None:
                panel.hide()
                panel.setParent(None)

    def _program_requirement_prompt(self):
        return (
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
        )

    def _start_program_requirement_refinement(self, text: str, append_user: bool = True):
        self.current_requirement = text
        if append_user:
            self._append_chat('user', text)
        self._apply_candidate_profile_overrides(text)
        self._append_chat('system', '正在调用大模型完善需求...')

        if self._welcome_is_active():
            self.show_main_content()
        self.status_label.setText('状态：对话处理中...')
        self.send_btn.setEnabled(False)
        self._chat_task = 'program_refine'

        self.chat_worker = ChatWorker(text, self._program_requirement_prompt(), self)
        self.chat_worker.success.connect(self.on_chat_success)
        self.chat_worker.failure.connect(self.on_chat_failure)
        self.chat_worker.finished.connect(self.on_chat_finished)
        self.chat_worker.start()

    def _on_welcome_input(self):
        text = self.welcome_input.text().strip()
        if not text:
            return
        self._start_program_requirement_refinement(text, append_user=True)
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

    def _flow_state(self):
        return {
            'program_requirement': self.current_requirement,
            'program_generated': self._has_generated_program(),
            'load_curve_saved': self._has_load_curve_saved(),
            'metrics_ready': self._has_metrics_ready(),
            'tuning_started': self._auto_tuning_started,
        }

    def _route_user_message_with_agent(self, text: str):
        if self.route_worker is not None and self.route_worker.isRunning():
            self._append_chat('system', '正在理解上一条输入，请稍后。')
            return

        self._pending_route_text = text
        self.status_label.setText('状态：正在判断对话意图...')
        self.send_btn.setEnabled(False)
        self.route_worker = FlowRouteWorker(text, self._flow_state(), list(self.chat_history), self)
        self.route_worker.routed.connect(self._on_route_success)
        self.route_worker.failure.connect(self._on_route_failure)
        self.route_worker.finished.connect(self._on_route_finished)
        self.route_worker.start()

    def _on_route_success(self, route: dict):
        text = self._pending_route_text
        self._pending_route_text = ''
        self._handle_user_route(text, route)

    def _on_route_failure(self, error_text: str):
        text = self._pending_route_text
        self._pending_route_text = ''
        fallback = self._fallback_route(text)
        self._append_chat('system', f'意图判断失败，已使用本地规则继续：{error_text}')
        self._handle_user_route(text, fallback)

    def _on_route_finished(self):
        if not self._assistant_busy():
            self.send_btn.setEnabled(True)

    def _fallback_route(self, text: str) -> dict:
        state = self._flow_state()
        route = heuristic_route(text, state)
        if route:
            return route
        if not state.get('program_generated'):
            return {'action': ACTION_REVISE_PROGRAM, 'reason': '默认继续完善程序需求'}
        if state.get('load_curve_saved') and not state.get('metrics_ready'):
            return {'action': ACTION_SUBMIT_METRICS, 'reason': '默认作为指标需求处理'}
        return {'action': ACTION_ANSWER_QUESTION, 'reason': '默认作为普通问题回答'}

    def _handle_user_route(self, text: str, route: dict):
        action = (route or {}).get('action') or ACTION_CLARIFY
        reply = (route or {}).get('reply') or ''

        if action == ACTION_CONFIRM_GENERATE:
            self._append_chat('user', text)
            self.input_edit.clear()
            self.generate_program()
            return

        if action == ACTION_REVISE_PROGRAM:
            self.input_edit.clear()
            self._start_program_requirement_refinement(text, append_user=True)
            return

        if action == ACTION_SHOW_LOAD_CURVE:
            self._append_chat('user', text)
            self.input_edit.clear()
            self.show_load_curve_card(announce=True, force=True)
            self.status_label.setText('状态：等待负载曲线')
            return

        if action == ACTION_SUBMIT_METRICS:
            if not self._has_generated_program():
                self.input_edit.clear()
                self._start_program_requirement_refinement(text, append_user=True)
                return
            self.send_metric_requirement(text)
            return

        if action == ACTION_START_TUNING:
            self._append_chat('user', text)
            self.input_edit.clear()
            normalized = ''.join(text.strip().lower().split())
            explicit_restart = any(term in normalized for term in ('调优', '优化', '迭代参数', '重新', '再跑', '再运行'))
            if self._auto_tuning_started and not explicit_restart:
                self._append_chat('model', 'Optimize Agent 已经启动。你可以继续询问结果、修改负载曲线或补充指标；如果需要重新运行，请明确输入“重新调优”。')
                self.status_label.setText('状态：调优已启动')
                return
            self._auto_start_tuning_if_ready(force=True)
            return

        if action == ACTION_ANSWER_QUESTION:
            self._append_chat('user', text)
            self.input_edit.clear()
            if reply:
                self._append_chat('model', reply)
                self.status_label.setText('状态：已回答')
            else:
                self._start_answer_response(text)
            return

        self._append_chat('user', text)
        self.input_edit.clear()
        self._append_chat('model', reply or '我需要再确认一下你的意图。你是想修改程序需求、重画负载曲线，还是输入指标需求？')
        self.status_label.setText('状态：等待澄清')

    def _answer_prompt(self):
        state = self._flow_state()
        state_text = json.dumps(state, ensure_ascii=False, indent=2)
        return (
            '你是 MotorAI 电机控制程序生成工作台中的对话助手。'
            '请回答用户关于当前项目、程序需求、负载曲线、指标或调优流程的问题。'
            '回答要简洁、具体，不要擅自推进生成程序、负载曲线、指标处理或调优。'
            f'当前工作流状态：\n{state_text}'
        )

    def _start_answer_response(self, text: str):
        self._append_chat('system', '正在回答问题...')
        self.status_label.setText('状态：正在回答...')
        self.send_btn.setEnabled(False)
        self._chat_task = 'answer'
        self.chat_worker = ChatWorker(text, self._answer_prompt(), self)
        self.chat_worker.success.connect(self.on_chat_success)
        self.chat_worker.failure.connect(self.on_chat_failure)
        self.chat_worker.finished.connect(self.on_chat_finished)
        self.chat_worker.start()

    def send_requirement(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        if self.chat_worker is not None and self.chat_worker.isRunning():
            self._append_chat('system', '正在等待上一条对话返回，请稍后。')
            return
        if self.route_worker is not None and self.route_worker.isRunning():
            self._append_chat('system', '正在理解上一条输入，请稍后。')
            return

        route = heuristic_route(text, self._flow_state())
        if route is not None:
            self._handle_user_route(text, route)
            return

        self._route_user_message_with_agent(text)

    def send_metric_requirement(self, text: str):
        if self.requirement_panel is None:
            self._append_chat('system', '需求指标处理器尚未初始化。')
            return
        if getattr(self.requirement_panel, 'chat_worker', None) is not None and self.requirement_panel.chat_worker.isRunning():
            self._append_chat('system', '正在等待上一条指标需求返回，请稍后。')
            return

        submitted = self.requirement_panel.submit_requirement_text(text)
        if submitted:
            self.send_btn.setEnabled(False)
            self.input_edit.clear()

    def _project_json_path(self):
        if callable(self.project_json_getter):
            return self.project_json_getter()
        return None

    def _project_data(self):
        project_json = self._project_json_path()
        if not project_json:
            return {}
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _has_generated_program(self):
        data = self._project_data()
        candidate_dirs = self._candidate_dirs()
        if candidate_dirs:
            required_names = ('ctl_main.c', 'ctl_main.h', 'paras.generated.h')
            for candidate_dir in candidate_dirs:
                src_dir = candidate_dir / 'src'
                if not all((src_dir / name).exists() for name in required_names):
                    return False
            return True

        candidate_generation = data.get('candidate_generation')
        if isinstance(candidate_generation, list) and candidate_generation:
            for item in candidate_generation:
                if not isinstance(item, dict):
                    return False
                paths = [item.get('ctl_main_c'), item.get('ctl_main_h'), item.get('paras_header')]
                if not all(path and Path(str(path)).exists() for path in paths):
                    return False
            return True

        return False

    def _has_load_curve_saved(self):
        if self.load_curve_panel is not None and hasattr(self.load_curve_panel, '_simulate_folder'):
            try:
                return (self.load_curve_panel._simulate_folder() / 'load.csv').exists()
            except Exception:
                return False
        return False

    def _has_metrics_ready(self):
        data = self._project_data()
        return bool(data.get('objective') or data.get('metrics') or data.get('targets'))

    def _assistant_busy(self):
        if self.chat_worker is not None and self.chat_worker.isRunning():
            return True
        if self.route_worker is not None and self.route_worker.isRunning():
            return True
        if self.requirement_panel is not None:
            worker = getattr(self.requirement_panel, 'chat_worker', None)
            if worker is not None and worker.isRunning():
                return True
        return False

    def _auto_start_tuning_if_ready(self, force: bool = False, announce: bool = True):
        missing = []
        if not self._has_generated_program():
            missing.append('控制程序')
        if not self._has_load_curve_saved():
            missing.append('负载曲线')
        if not self._has_metrics_ready():
            missing.append('需求指标')

        if missing:
            if announce:
                self._append_chat('system', f'还缺少{"、".join(missing)}，暂不启动调优。')
            return False

        if self._auto_tuning_started and not force:
            return True

        self._auto_tuning_started = True
        self._workflow_steps.add('tuning_started')
        self._append_chat('system', '控制程序、负载曲线和需求指标已收集完成，正在自动启动 Optimize Agent 迭代调优。')
        self.status_label.setText('状态：正在启动调优...')
        if callable(self.run_tuning_callback):
            self.run_tuning_callback()
        else:
            self._append_chat('system', '调优入口尚未初始化，无法启动 Optimize Agent。')
        return True

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

    def _candidate_plan_text(self):
        candidate_dirs = self._candidate_dirs()
        if candidate_dirs:
            plan_lines = ['目前计划生成的各个 candidate 的负责代码逻辑如下，请确认无误后回复“生成程序”：']
            for index, candidate_dir in enumerate(candidate_dirs, start=1):
                profile = self._load_candidate_profile(candidate_dir, index)
                name = profile.get('name') or candidate_dir.name
                structure_bias = profile.get('structure_bias') or '沿用默认结构生成策略。'
                implementation_bias = profile.get('implementation_bias') or '按当前模板生成 ctl_main.c、ctl_main.h 和 paras.generated.h。'
                methods = profile.get('preferred_control_methods') or []
                method_text = '、'.join(str(item) for item in methods) if methods else '默认方法'
                plan_lines.append(f'{candidate_dir.name}：{name}；结构侧重：{structure_bias}；候选方法：{method_text}；代码侧重：{implementation_bias}')
        else:
            plan_lines = ['目前计划按当前需求生成控制程序。请确认无误后回复“生成程序”；如果还要补充，请直接继续输入。']
        return '\n'.join(plan_lines)

    def on_chat_success(self, reply: str):
        if self._chat_task == 'answer':
            self._append_chat('model', reply)
            self.status_label.setText('状态：已回答')
            return

        self._append_chat('model', reply)
        self._apply_candidate_profile_overrides(reply)
        self.current_requirement = reply
        self._update_project_json_requirement(reply)
        self._append_chat('system', self._candidate_plan_text())
        self._set_program_input_mode()
        self.status_label.setText('状态：等待确认生成程序')

    def on_chat_failure(self, error_text: str):
        self._append_chat('system', f'对话失败：{error_text}')
        self.status_label.setText('状态：对话失败，请检查设置与网络')

    def on_chat_finished(self):
        self._chat_task = None
        self.send_btn.setEnabled(True)

    def generate_program(self):
        if not self.current_requirement:
            self._append_chat('system', '请先输入并发送需求，再执行生成。')
            self.status_label.setText('状态：缺少需求')
            return

        template_dir = GENERATE_ROOT / 'Example'
        project_json = self._project_json_path()
        llm_config = MOTORAI_ROOT / 'motorai_settings.json'
        candidate_dirs = self._candidate_dirs()

        if not project_json or not candidate_dirs:
            self._append_chat('system', '未找到 candidate 工作区。请重新新建竞争模式工程。')
            self.status_label.setText('状态：缺少 candidate')
            return
        for template_name in ('ctl_main.c', 'ctl_main.h', 'paras.h'):
            template_path = template_dir / template_name
            if not template_path.exists():
                self._append_chat('system', f'生成模板不存在：{template_path}')
                self.status_label.setText('状态：生成模板缺失')
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
                merge_code = merger.main(
                    loop_ids_path=loop_ids_output,
                    template_path=template_dir / 'ctl_main.c',
                    output_path=c_output,
                    header_template_path=template_dir / 'ctl_main.h',
                    header_output_path=h_output,
                    paras_template_path=template_dir / 'paras.h',
                    paras_output_path=paras_output,
                )
                if merge_code != 0:
                    raise RuntimeError(f'{candidate_dir.name} 模板合并失败，返回码：{merge_code}')
                for generated_path in (c_output, h_output, paras_output):
                    if not generated_path.exists():
                        raise FileNotFoundError(f'{candidate_dir.name} 未生成文件：{generated_path}')

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
            self.show_load_curve_card()
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
        return None

    def _save_chat_record(self):
        project_folder = self._project_folder()
        if project_folder is None:
            return
        record_path = project_folder / 'record.json'
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
        self._detach_workflow_panels()
        self.chat_view.clear_messages()
        self.chat_history = []
        self._workflow_steps.clear()
        self._load_curve_card_count = 0

        project_folder = self._project_folder()
        if project_folder is None:
            return
        record_path = project_folder / 'record.json'
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

    def reload_for_project(self):
        self.current_requirement = ''
        self._auto_tuning_started = False
        self._load_chat_record()
        self._set_program_input_mode()
        if not self.chat_history and not self._project_has_workflow_state():
            self.show_welcome_overlay()
            return
        self.show_main_content()
        self._restore_workflow_from_project()

    def _project_has_workflow_state(self):
        project_json = self._project_json_path()
        if not project_json:
            return False

        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}

        if isinstance(data, dict):
            for key in ('objective_text', 'objective', 'selected_loops', 'metrics', 'targets'):
                value = data.get(key)
                if value:
                    return True

        if self.load_curve_panel is not None and hasattr(self.load_curve_panel, '_simulate_folder'):
            try:
                return (self.load_curve_panel._simulate_folder() / 'load.csv').exists()
            except Exception:
                return False

        return False

    def _restore_workflow_from_project(self):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}

        if isinstance(data, dict):
            self.current_requirement = str(data.get('objective_text') or self.current_requirement or '').strip()

        selected_loops = data.get('selected_loops') if isinstance(data, dict) else None
        if isinstance(selected_loops, list) and selected_loops:
            self.show_load_curve_card(announce=False)

        has_load_curve = self._has_load_curve_saved()
        if has_load_curve:
            self._set_metric_input_mode()

        if isinstance(data, dict) and (data.get('objective') or data.get('metrics') or data.get('targets')):
            self.status_label.setText('状态：信息已准备，可继续提问或输入“重新调优”启动优化')
