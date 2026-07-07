from PyQt5.QtWidgets import QLabel, QPushButton, QTextEdit, QWidget, QHBoxLayout, QVBoxLayout
from PyQt5.QtCore import QFileSystemWatcher
import json
from pathlib import Path

from widgets.chat import TranslationWorker
from styles.theme import current_theme


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
