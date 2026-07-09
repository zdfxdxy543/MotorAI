"""
controller_manifest.py  —  Step 1: 为每个 candidate 生成结构化控制方案摘要。

设计原则：
    1. 纯程序化提取，不依赖 LLM。
    2. 所有数据从 generate 阶段的已有产物中读取。
    3. 任一文件缺失或解析失败不影响主流程——对应字段留空。
    4. 参数归属（loop / role）基于命名规则推断，不保证 100% 准确，
       标注 "unknown" 而非强行归类。

输出位置：candidate/log/generate/controller_manifest.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from Optimize.agent_optimize.agent_core.parameters.parameter_header_editor import (
    read_tunable_parameters_detailed,
)


# ── 已知控制方法标识 ───────────────────────────────────────────────────────
# 从 loop properties 中筛出属于控制方法的 token

KNOWN_CONTROL_METHODS: set[str] = {
    "pid",
    "mit",
    "smc",
    "feedforward",
    "disturbance_observer",
    "gain_scheduling",
    "filtering",
    "ramp_limit",
    "ladrc",
    "adrc",
    "pi",
    "pd",
}


# ── 参数 → loop 归属 ──────────────────────────────────────────────────────

def _infer_parameter_loop(name: str, loop_names: list[str]) -> str:
    """根据参数名前缀推断该参数属于哪个控制环路。

    规则（按优先级）：
        POS_*         → position_loop（若存在）否则 mech_loop
        VEL_* / SPEED_* → mech_loop
        CUR_* / IQ_* / ID_* → current_loop
        TARGET_* / INERTIA / TORQUE_* → mech_loop（机械层参数）
        其他          → "unknown"
    """
    upper = name.upper().strip()

    # 位置环参数
    if upper.startswith("POS_"):
        return "position_loop" if "position_loop" in loop_names else "mech_loop"

    # 速度环参数
    if upper.startswith("VEL_") or upper.startswith("SPEED_"):
        return "mech_loop"

    # 电流环参数
    if upper.startswith("CUR_") or upper.startswith("IQ_") or upper.startswith("ID_"):
        return "current_loop"

    # 机械层通用参数（惯量、转矩常数、带宽等）
    if upper.startswith("TARGET_") or upper in {"INERTIA", "TORQUE_CONST", "OMEGA_BASE", "I_BASE"}:
        return "mech_loop"

    # LADRC 带宽参数
    if any(upper.endswith("_" + tag) or upper == tag for tag in ("WC", "WO", "BW")):
        return "mech_loop"

    return "unknown"


# ── 参数 → role 角色 ──────────────────────────────────────────────────────

def _infer_parameter_role(name: str) -> str:
    """根据参数名后缀推断该参数在控制环路中的角色。"""
    upper = name.upper().strip()

    if upper.endswith("_KP") or upper == "KP":
        return "kp"
    if upper.endswith("_KI") or upper == "KI":
        return "ki"
    if upper.endswith("_KD") or upper == "KD":
        return "kd"
    if upper.endswith("_BW") or upper in {"TARGET_WC", "TARGET_WO", "TARGET_BW"}:
        return "bandwidth"
    # SLOPE 必须在 LIMIT 之前检查，否则 SPEED_SLOPE_LIMIT 会被误判为 limit
    if "SLOPE" in upper:
        return "slope_limit"
    if "_LIMIT" in upper or upper.endswith("_MAX"):
        return "limit"
    if upper in {"INERTIA", "TORQUE_CONST", "OMEGA_BASE", "I_BASE"}:
        return "physical_constant"
    if upper.startswith("DIST_REJECT"):
        return "disturbance_rejection"

    return "unknown"


# ── 结构签名 ──────────────────────────────────────────────────────────────

def _build_structure_signature(
    loop_hierarchy: list[str],
    control_methods: list[str],
) -> str:
    """构建人类可读的结构签名。

    格式："环路1+环路2:方法1,方法2"
    示例："current_loop+mech_loop:pid"
    """
    loops_part = "+".join(loop_hierarchy) if loop_hierarchy else "unknown"
    methods_part = ",".join(sorted(control_methods)) if control_methods else "unknown"
    return f"{loops_part}:{methods_part}"


# ── 主函数 ────────────────────────────────────────────────────────────────

def write_controller_manifest(candidate_dir: str | Path) -> Path:
    """为单个 candidate 生成 controller_manifest.json。

    读取 generate 阶段的产物，提取结构摘要，写入
    <candidate_dir>/log/generate/controller_manifest.json。

    Args:
        candidate_dir: candidate 根目录路径。

    Returns:
        写入的 manifest 文件的 Path。
    """
    candidate_dir = Path(candidate_dir).expanduser().resolve()
    candidate_id = candidate_dir.name
    log_generate = candidate_dir / "log" / "generate"
    src_dir = candidate_dir / "src"

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "candidate_id": candidate_id,
    }

    # ── 1. 读取 controller_loop_ids_generated.json ─────────────────
    loop_ids_path = log_generate / "controller_loop_ids_generated.json"
    selected_loops: list[dict[str, Any]] = []
    loop_hierarchy: list[str] = []
    control_methods: list[str] = []

    if loop_ids_path.exists():
        try:
            data = json.loads(loop_ids_path.read_text(encoding="utf-8-sig"))
            raw_loops = data.get("selected_loops")
            if isinstance(raw_loops, list):
                selected_loops = raw_loops
                for loop in raw_loops:
                    if isinstance(loop, dict):
                        name = str(loop.get("name", "")).strip()
                        if name:
                            loop_hierarchy.append(name)
                        props = loop.get("properties")
                        if isinstance(props, list):
                            for prop in props:
                                prop_lower = str(prop).strip().lower()
                                if prop_lower in KNOWN_CONTROL_METHODS and prop_lower not in control_methods:
                                    control_methods.append(prop_lower)
        except Exception:
            pass  # 文件损坏 → 留空

    manifest["structure_signature"] = _build_structure_signature(loop_hierarchy, control_methods)
    manifest["loop_hierarchy"] = loop_hierarchy
    manifest["control_methods"] = control_methods
    manifest["selected_loops"] = selected_loops

    # ── 2. 读取 design_strategy.json ──────────────────────────────
    strategy_path = log_generate / "design_strategy.json"
    generation_intent: dict[str, Any] = {}

    if strategy_path.exists():
        try:
            strategy = json.loads(strategy_path.read_text(encoding="utf-8-sig"))
            profile = strategy.get("design_profile")
            if isinstance(profile, dict):
                generation_intent["profile_name"] = profile.get("name", "")
                methods = profile.get("preferred_control_methods")
                if isinstance(methods, list):
                    generation_intent["preferred_control_methods"] = [
                        str(m).strip() for m in methods if str(m).strip()
                    ]
                generation_intent["structure_bias"] = profile.get("structure_bias", "")
        except Exception:
            pass

    manifest["generation_intent"] = generation_intent

    # ── 3. 记录生成文件路径 ─────────────────────────────────────
    manifest["generated_files"] = {
        "ctl_main_c": str((src_dir / "ctl_main.c").resolve()),
        "ctl_main_h": str((src_dir / "ctl_main.h").resolve()),
        "paras_header": str((src_dir / "paras.generated.h").resolve()),
        "loop_ids": str(loop_ids_path.resolve()),
        "design_strategy": str(strategy_path.resolve()),
    }

    # ── 4. 读取可调参数并推断归属 ────────────────────────────────
    paras_header = src_dir / "paras.generated.h"
    tunable_parameters: list[dict[str, Any]] = []

    if paras_header.exists():
        try:
            params = read_tunable_parameters_detailed(paras_header)
            for pname in sorted(params.keys()):
                param = params[pname]
                loop = _infer_parameter_loop(pname, loop_hierarchy)
                role = _infer_parameter_role(pname)
                tunable_parameters.append({
                    "name": pname,
                    "loop": loop,
                    "role": role,
                    "initial_value": param.value,
                    "declaration_kind": param.declaration_kind,
                })
        except Exception:
            pass

    manifest["tunable_parameters"] = tunable_parameters

    # ── 5. 写入文件 ─────────────────────────────────────────────
    log_generate.mkdir(parents=True, exist_ok=True)
    output_path = log_generate / "controller_manifest.json"
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return output_path
