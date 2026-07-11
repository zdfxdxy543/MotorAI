"""
Motor parameter data model.

Defines the complete parameter set based on SM060R20B30MNAD
and the runtime state of the motor configuration being edited.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ParamCategory(Enum):
    ELECTRICAL = "electrical"
    MECHANICAL = "mechanical"
    CHARACTERISTIC = "characteristic"
    RATED = "rated"
    LIMIT = "limit"

    @property
    def label(self) -> str:
        _labels = {
            "electrical": "电气参数",
            "mechanical": "机械参数",
            "characteristic": "特性常数",
            "rated": "额定参数",
            "limit": "极限参数",
        }
        return _labels[self.value]


@dataclass
class MotorParamDef:
    """Metadata definition for one motor parameter."""

    macro: str          # e.g. "MOTOR_PARAM_RS"
    label: str          # e.g. "定子电阻"
    symbol: str         # e.g. "Rs"
    unit: str           # e.g. "Ω"
    category: ParamCategory
    decimals: int = 3
    min_val: float = 0.0
    max_val: float = 1e6
    auto_calc: bool = False  # can be auto-calculated (e.g. FLUX from KV)


# ---------------------------------------------------------------------------
# Complete parameter set – the union of all SM060R20B30MNAD parameters.
# ---------------------------------------------------------------------------

PARAM_DEFS: list[MotorParamDef] = [
    # -- Electrical --
    MotorParamDef("MOTOR_PARAM_RS",  "定子电阻",   "Rs",    "Ω",
                  ParamCategory.ELECTRICAL, decimals=4, min_val=0.0001, max_val=1000.0),
    MotorParamDef("MOTOR_PARAM_LS",  "定子电感",   "Ls",    "H",
                  ParamCategory.ELECTRICAL, decimals=6, min_val=1e-6, max_val=1.0),
    MotorParamDef("MOTOR_PARAM_FLUX","永磁磁链",   "Flux",  "Wb",
                  ParamCategory.ELECTRICAL, decimals=6, min_val=0.0001, max_val=10.0,
                  auto_calc=True),

    # -- Mechanical --
    MotorParamDef("MOTOR_PARAM_POLE_PAIRS", "极对数",     "Pole Pairs", "",
                  ParamCategory.MECHANICAL, decimals=0, min_val=1, max_val=100),
    MotorParamDef("MOTOR_PARAM_INERTIA",    "转动惯量",   "Inertia",    "g·cm²",
                  ParamCategory.MECHANICAL, decimals=1, min_val=0.0, max_val=1e6),
    MotorParamDef("MOTOR_PARAM_FRICTION",   "摩擦系数",   "Friction",   "μN·m·s/rad",
                  ParamCategory.MECHANICAL, decimals=1, min_val=0.0, max_val=1e6),

    # -- Characteristic --
    MotorParamDef("MOTOR_PARAM_KV",  "速度常数",     "Kv",  "RPM/V",
                  ParamCategory.CHARACTERISTIC, decimals=1, min_val=1.0, max_val=10000.0),
    MotorParamDef("MOTOR_PARAM_EMF", "反电动势常数", "EMF", "V/kRPM",
                  ParamCategory.CHARACTERISTIC, decimals=2, min_val=0.01, max_val=1000.0),

    # -- Rated --
    MotorParamDef("MOTOR_PARAM_RATED_VOLTAGE",   "额定电压", "V_rated",  "V",
                  ParamCategory.RATED, decimals=1, min_val=0.1, max_val=10000.0),
    MotorParamDef("MOTOR_PARAM_RATED_CURRENT",   "额定电流", "I_rated",  "A (峰值)",
                  ParamCategory.RATED, decimals=2, min_val=0.01, max_val=1000.0),
    MotorParamDef("MOTOR_PARAM_NO_LOAD_CURRENT", "空载电流", "I_noload", "A (峰值)",
                  ParamCategory.RATED, decimals=3, min_val=0.0, max_val=100.0),
    MotorParamDef("MOTOR_PARAM_RATED_FREQUENCY", "额定频率", "f_rated",  "Hz",
                  ParamCategory.RATED, decimals=1, min_val=0.1, max_val=10000.0),

    # -- Limits --
    MotorParamDef("MOTOR_PARAM_MAX_SPEED",       "最大转速",     "N_max",    "RPM",
                  ParamCategory.LIMIT, decimals=0, min_val=0, max_val=100000),
    MotorParamDef("MOTOR_PARAM_MAX_TORQUE",      "最大转矩",     "T_max",    "N·m",
                  ParamCategory.LIMIT, decimals=3, min_val=0.0, max_val=10000.0),
    MotorParamDef("MOTOR_PARAM_MAX_DC_VOLTAGE",  "最大母线电压", "Vdc_max",  "V",
                  ParamCategory.LIMIT, decimals=1, min_val=0.1, max_val=10000.0),
    MotorParamDef("MOTOR_PARAM_MAX_PH_CURRENT",  "最大相电流",   "Iph_max",  "A (峰值)",
                  ParamCategory.LIMIT, decimals=2, min_val=0.01, max_val=1000.0),
]

# Lookup helpers
PARAM_BY_MACRO: dict[str, MotorParamDef] = {p.macro: p for p in PARAM_DEFS}
PARAMS_BY_CATEGORY: dict[ParamCategory, list[MotorParamDef]] = {}
for p in PARAM_DEFS:
    PARAMS_BY_CATEGORY.setdefault(p.category, []).append(p)

# Ordered categories for display
CATEGORY_ORDER = [
    ParamCategory.ELECTRICAL,
    ParamCategory.MECHANICAL,
    ParamCategory.CHARACTERISTIC,
    ParamCategory.RATED,
    ParamCategory.LIMIT,
]


# ---------------------------------------------------------------------------
# Formula helpers
# ---------------------------------------------------------------------------

def calc_flux_by_kv(kv: float, pole_pairs: int) -> float:
    """Flux = 60 / (2 * pi * sqrt(3) * Kv * PolePairs)."""
    if kv <= 0 or pole_pairs <= 0:
        return 0.0
    return 60.0 / (10.882796185405308 * kv * pole_pairs)
