"""
Parse motor preset .h files to extract MOTOR_PARAM_* macro values.

Handles:
  - Simple float values:   ((0.165f))
  - Scientific notation:   ((0.45e-3f))
  - Arithmetic expressions: ((0.4 / 2.0))
  - Auto-calc macros:      ((MOTOR_PARAM_CALCULATE_FLUX_BY_KV(...)))
"""

import re
import os
from typing import Optional

# Matches: #define MACRO_NAME ((...content...))
_RE_DEFINE = re.compile(
    r'^\s*#define\s+(MOTOR_PARAM_\w+)\s+\(\(\s*(.+?)\s*\)\)',
    re.MULTILINE,
)

# Matches auto-calc macro invocations
_RE_AUTO_CALC = re.compile(r'MOTOR_PARAM_CALCULATE_\w+\(.*\)')

# For stripping 'f' suffix from float literals
_RE_FLOAT_SUFFIX = re.compile(r'(\d+\.?\d*(?:[eE][+-]?\d+)?)f')


def _strip_f_suffix(expr: str) -> str:
    """Remove 'f' suffix from float literals in an expression."""
    return _RE_FLOAT_SUFFIX.sub(r'\1', expr)


def _try_eval(expr: str) -> Optional[float]:
    """Try to safely evaluate a simple arithmetic expression."""
    try:
        cleaned = _strip_f_suffix(expr)
        # Only allow safe characters
        if not re.match(r'^[\d\s\+\-\*\/\.\(\)eE]+$', cleaned):
            return None
        result = eval(cleaned, {"__builtins__": {}}, {})
        return float(result)
    except Exception:
        return None


def _join_continuations(content: str) -> str:
    """Join lines that end with a backslash continuation marker."""
    return re.sub(r'\\\s*\n\s*', '', content)


def parse_motor_header(filepath: str) -> dict[str, Optional[float]]:
    """
    Parse a motor preset .h file.

    Returns
    -------
    dict
        macro_name → float value, or None if auto-calc / unparseable.
        Only MOTOR_PARAM_* macros are included.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Motor preset not found: {filepath}")

    with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()

    # Join multi-line defines (lines ending with backslash)
    content = _join_continuations(content)

    params: dict[str, Optional[float]] = {}

    for match in _RE_DEFINE.finditer(content):
        macro = match.group(1)
        raw_value = match.group(2).strip()

        # Check for auto-calc macro
        if _RE_AUTO_CALC.match(raw_value):
            params[macro] = None  # mark as auto-calc
            continue

        # Try to evaluate the expression
        val = _try_eval(raw_value)
        params[macro] = val  # may be None if unparseable

    return params


def extract_preset_name(filepath: str) -> str:
    """Derive the preset display name from the filename (without .h)."""
    return os.path.splitext(os.path.basename(filepath))[0]


def extract_brief_info(params: dict[str, Optional[float]]) -> str:
    """Build a one-line summary string for the preset list."""
    parts = []
    kv = params.get("MOTOR_PARAM_KV")
    pp = params.get("MOTOR_PARAM_POLE_PAIRS")
    v_rated = params.get("MOTOR_PARAM_RATED_VOLTAGE")

    if kv is not None:
        parts.append(f"KV {kv:.0f}")
    if pp is not None:
        parts.append(f"{int(pp)}对极")
    if v_rated is not None:
        parts.append(f"{v_rated:.0f}V")

    return " | ".join(parts) if parts else ""
