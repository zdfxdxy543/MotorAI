"""
Right panel: motor parameter editor.

Displays parameters grouped in collapsible section cards.
Each param row: [label] [symbol] [spinbox] [unit]  (or placeholder if empty).

FLUX has a lock/unlock toggle for auto-calculation from KV.
"""

from typing import Optional

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QDoubleSpinBox,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
)

from core.model import (
    MotorParamDef,
    ParamCategory,
    PARAM_DEFS,
    PARAMS_BY_CATEGORY,
    CATEGORY_ORDER,
    PARAM_BY_MACRO,
    calc_flux_by_kv,
)

LOCKED_ICON = "\U0001f512"    # 🔒
UNLOCKED_ICON = "\U0001f513"  # 🔓


class ParamRow(QWidget):
    """Single parameter row: label + symbol + spinbox + unit."""

    value_changed = pyqtSignal(str, object)  # macro, float or None

    def __init__(self, param_def: MotorParamDef, parent=None):
        super().__init__(parent)
        self._def = param_def
        self._has_value = False
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        # --- Label side ---
        label_col = QVBoxLayout()
        label_col.setSpacing(0)

        label = QLabel(self._def.label)
        label.setObjectName("paramLabel")
        label_col.addWidget(label)

        symbol = QLabel(self._def.symbol)
        symbol.setObjectName("paramSymbol")
        label_col.addWidget(symbol)

        layout.addLayout(label_col)
        layout.addStretch()

        # --- Spinbox ---
        self._spin = QDoubleSpinBox()
        self._spin.setObjectName("paramSpin")
        self._spin.setDecimals(self._def.decimals)
        self._spin.setRange(self._def.min_val, self._def.max_val)
        self._spin.setMinimumWidth(130)
        self._spin.setMaximumWidth(200)
        self._spin.setSpecialValueText("—")
        self._spin.setValue(self._def.min_val)  # default at min = shows "—"
        self._spin.setEnabled(False)  # starts empty
        self._spin.valueChanged.connect(self._on_spin_changed)
        layout.addWidget(self._spin)

        # --- Unit ---
        if self._def.unit:
            unit_label = QLabel(self._def.unit)
            unit_label.setObjectName("paramUnit")
            unit_label.setMinimumWidth(60)
            layout.addWidget(unit_label)
        else:
            spacer = QWidget()
            spacer.setMinimumWidth(60)
            layout.addWidget(spacer)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def set_value(self, value: Optional[float]):
        """Set the parameter value. None means empty."""
        self._spin.blockSignals(True)
        if value is None:
            self._has_value = False
            self._spin.setEnabled(False)
            self._spin.setSpecialValueText("—")
            self._spin.setValue(self._def.min_val)
        else:
            self._has_value = True
            self._spin.setEnabled(True)
            self._spin.setSpecialValueText("")
            clamped = max(self._def.min_val, min(self._def.max_val, value))
            self._spin.setValue(clamped)
        self._spin.blockSignals(False)

    def set_enabled(self, enabled: bool):
        """Enable/disable editing (e.g. for FLUX when locked)."""
        if self._has_value or not enabled:
            self._spin.setEnabled(enabled)

    def value(self) -> Optional[float]:
        """Return current value, or None if empty."""
        if not self._has_value:
            return None
        return self._spin.value()

    def param_def(self) -> MotorParamDef:
        return self._def

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_spin_changed(self, val: float):
        self._has_value = True
        self._spin.setSpecialValueText("")
        self.value_changed.emit(self._def.macro, val)


class SectionCard(QFrame):
    """A card grouping parameters of one category."""

    def __init__(self, category: ParamCategory, parent=None):
        super().__init__(parent)
        self.setObjectName("sectionCard")
        self._category = category
        self._rows: dict[str, ParamRow] = {}
        self._build()

    def _build(self):
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(16, 12, 16, 14)
        self._outer.setSpacing(6)

        # Header
        header = QLabel(self._category.label)
        header.setObjectName("sectionHeader")
        self._outer.addWidget(header)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("border: none; border-top: 1px solid #e2e4e9;")
        self._outer.addWidget(sep)

        # Param rows container
        self._rows_layout = QVBoxLayout()
        self._rows_layout.setSpacing(2)
        self._outer.addLayout(self._rows_layout)

    def add_param_row(self, param_def: MotorParamDef) -> ParamRow:
        row = ParamRow(param_def)
        self._rows[param_def.macro] = row
        self._rows_layout.addWidget(row)
        return row

    def row(self, macro: str) -> Optional[ParamRow]:
        return self._rows.get(macro)


class FluxRow(QWidget):
    """Special row for FLUX with lock/unlock toggle and auto-calc hint."""

    flux_locked_changed = pyqtSignal(bool)
    value_changed = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._locked = True
        self._param_def = PARAM_BY_MACRO["MOTOR_PARAM_FLUX"]
        self._has_value = False
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        # Label
        label_col = QVBoxLayout()
        label_col.setSpacing(0)

        label = QLabel(self._param_def.label)
        label.setObjectName("paramLabel")
        label_col.addWidget(label)

        symbol = QLabel(self._param_def.symbol)
        symbol.setObjectName("paramSymbol")
        label_col.addWidget(symbol)

        layout.addLayout(label_col)

        # Hint between label and spinbox
        self._hint = QLabel("")
        self._hint.setObjectName("fluxHint")
        layout.addWidget(self._hint)
        layout.addStretch()

        # Spinbox
        self._spin = QDoubleSpinBox()
        self._spin.setObjectName("paramSpin")
        self._spin.setDecimals(self._param_def.decimals)
        self._spin.setRange(self._param_def.min_val, self._param_def.max_val)
        self._spin.setMinimumWidth(130)
        self._spin.setMaximumWidth(200)
        self._spin.setSpecialValueText("—")
        self._spin.setValue(self._param_def.min_val)
        self._spin.setEnabled(False)
        self._spin.valueChanged.connect(self._on_spin_changed)
        layout.addWidget(self._spin)

        # Unit
        unit_label = QLabel(self._param_def.unit)
        unit_label.setObjectName("paramUnit")
        unit_label.setMinimumWidth(60)
        layout.addWidget(unit_label)

        # Lock button
        self._lock_btn = QPushButton(LOCKED_ICON)
        self._lock_btn.setObjectName("lockButton")
        self._lock_btn.setToolTip("点击解锁以手动输入磁链值")
        self._lock_btn.clicked.connect(self._toggle_lock)
        layout.addWidget(self._lock_btn)

    def _toggle_lock(self):
        self._locked = not self._locked
        if self._locked:
            self._lock_btn.setText(LOCKED_ICON)
            self._lock_btn.setToolTip("点击解锁以手动输入磁链值")
            self._spin.setEnabled(False)
            self._hint.setText("由 KV 和极对数自动计算")
        else:
            self._lock_btn.setText(UNLOCKED_ICON)
            self._lock_btn.setToolTip("点击锁定以恢复自动计算")
            self._spin.setEnabled(True)
            self._hint.setText("手动输入")
            self._has_value = True
            self._spin.setSpecialValueText("")
        self._spin.blockSignals(True)
        self._spin.setStyleSheet(
            "QDoubleSpinBox { background: #f9fafb; }"
            if self._locked
            else ""
        )
        self._spin.blockSignals(False)
        self.flux_locked_changed.emit(self._locked)
        # Re-emit current value
        self.value_changed.emit(
            "MOTOR_PARAM_FLUX",
            self._spin.value() if self._has_value else None,
        )

    def set_value(self, value: Optional[float], locked: bool = True):
        self._locked = locked
        self._spin.blockSignals(True)
        if value is None:
            self._has_value = False
            self._spin.setValue(self._param_def.min_val)
            self._spin.setSpecialValueText("—")
        else:
            self._has_value = True
            self._spin.setSpecialValueText("")
            self._spin.setValue(max(self._param_def.min_val,
                                min(self._param_def.max_val, value)))
        self._spin.setEnabled(not locked)
        self._lock_btn.setText(LOCKED_ICON if locked else UNLOCKED_ICON)
        self._hint.setText("由 KV 和极对数自动计算" if locked else "手动输入")
        self._spin.blockSignals(False)

    def recalc(self, kv: Optional[float], pole_pairs: Optional[float]):
        """Auto-calculate FLUX from KV and pole pairs."""
        if not self._locked:
            return
        if kv is not None and pole_pairs is not None and kv > 0 and pole_pairs > 0:
            flux = calc_flux_by_kv(kv, int(pole_pairs))
            self._spin.blockSignals(True)
            self._spin.setValue(flux)
            self._has_value = True
            self._spin.setSpecialValueText("")
            self._spin.blockSignals(False)
            self.value_changed.emit("MOTOR_PARAM_FLUX", flux)
        else:
            self._spin.blockSignals(True)
            self._has_value = False
            self._spin.setValue(self._param_def.min_val)
            self._spin.setSpecialValueText("—")
            self._spin.blockSignals(False)
            self.value_changed.emit("MOTOR_PARAM_FLUX", None)

    def value(self) -> Optional[float]:
        if not self._has_value:
            return None
        return self._spin.value()

    def is_locked(self) -> bool:
        return self._locked

    def _on_spin_changed(self, val: float):
        self._has_value = True
        self._spin.setSpecialValueText("")
        self.value_changed.emit("MOTOR_PARAM_FLUX", val)


class ParamEditorPanel(QWidget):
    """Right panel: scrollable parameter editor with section cards."""

    param_changed = pyqtSignal(str, object)  # macro, float | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: dict[str, ParamRow] = {}
        self._flux_row: Optional[FluxRow] = None
        self._current_params: dict[str, Optional[float]] = {}
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Title
        title = QLabel("电机参数")
        title.setObjectName("sectionHeader")
        outer.addWidget(title)
        outer.addSpacing(4)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(10)

        # Build section cards
        for cat in CATEGORY_ORDER:
            card = SectionCard(cat)
            for pdef in PARAMS_BY_CATEGORY[cat]:
                if pdef.macro == "MOTOR_PARAM_FLUX":
                    # Use special FluxRow
                    flux_row = FluxRow()
                    flux_row.value_changed.connect(self.param_changed.emit)
                    flux_row.flux_locked_changed.connect(
                        self._on_flux_lock_changed
                    )
                    # Insert FluxRow into the card layout manually
                    # (inject before last item if needed)
                    card._rows_layout.addWidget(flux_row)
                    card._rows["MOTOR_PARAM_FLUX"] = flux_row  # type: ignore
                    self._flux_row = flux_row
                else:
                    row = card.add_param_row(pdef)
                    row.value_changed.connect(self.param_changed.emit)
                    self._rows[pdef.macro] = row
            container_layout.addWidget(card)

        container_layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_params(self, params: dict[str, Optional[float]], flux_locked: bool = True):
        """
        Load parameters from a preset.

        Parameters
        ----------
        params : dict
            macro_name → float value or None.
        flux_locked : bool
            Whether FLUX should start in locked (auto-calc) mode.
        """
        self._current_params = dict(params)

        # Block all signals during bulk load
        for macro, row in self._rows.items():
            row.blockSignals(True)

        # Load values into rows
        for macro, row in self._rows.items():
            val = params.get(macro)
            row.set_value(val)

        # Handle FLUX specially
        if self._flux_row:
            flux_val = params.get("MOTOR_PARAM_FLUX")
            # Determine if flux was auto-calc in the preset
            # (None value for FLUX means it was auto-calc)
            self._flux_row.set_value(
                flux_val, locked=flux_locked
            )
            if flux_locked:
                kv = params.get("MOTOR_PARAM_KV")
                pp = params.get("MOTOR_PARAM_POLE_PAIRS")
                self._flux_row.recalc(kv, pp)

        # Unblock
        for macro, row in self._rows.items():
            row.blockSignals(False)

    def get_all_params(self) -> dict[str, Optional[float]]:
        """Collect current values from all rows."""
        result: dict[str, Optional[float]] = {}
        for macro, row in self._rows.items():
            result[macro] = row.value()
        if self._flux_row:
            result["MOTOR_PARAM_FLUX"] = self._flux_row.value()
        return result

    def is_flux_locked(self) -> bool:
        if self._flux_row:
            return self._flux_row.is_locked()
        return True

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_flux_lock_changed(self, locked: bool):
        """When FLUX lock state changes, recalculate if now locked."""
        if locked and self._flux_row:
            kv = self._rows.get("MOTOR_PARAM_KV")
            pp = self._rows.get("MOTOR_PARAM_POLE_PAIRS")
            kv_val = kv.value() if kv else None
            pp_val = pp.value() if pp else None
            self._flux_row.recalc(kv_val, pp_val)

    def on_kv_or_pole_pairs_changed(self):
        """Called when KV or POLE_PAIRS changes, to update FLUX if locked."""
        if self._flux_row and self._flux_row.is_locked():
            kv = self._rows.get("MOTOR_PARAM_KV")
            pp = self._rows.get("MOTOR_PARAM_POLE_PAIRS")
            kv_val = kv.value() if kv else None
            pp_val = pp.value() if pp else None
            self._flux_row.recalc(kv_val, pp_val)
