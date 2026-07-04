from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
    QVBoxLayout,
)
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF
import csv
import shutil
from pathlib import Path

import core.paths  # ensures repository roots are on sys.path
from Competition.competition_workspace import discover_candidate_dirs


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



class LoadCurvePanel(QWidget):
    def __init__(self, project_json_getter=None, parent=None):
        super().__init__(parent)
        self.project_json_getter = project_json_getter
        self.save_callback = None
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

    def set_save_callback(self, callback):
        self.save_callback = callback

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
            if callable(self.save_callback):
                self.save_callback()
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
