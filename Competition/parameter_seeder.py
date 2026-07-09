"""
parameter_seeder.py  —  Step 0: 为每个 candidate 自动生成差异化的 paras.generated.h 初始值。

设计原则：
    1. 根据候选方案的 design_profile，对不同语义类别的参数施加不同方向的扰动。
    2. 使用 candidate_index 作为随机种子，保证每次初始化可复现。
    3. 只修改可调参数块内的数值字面量，不改变参数名、不增删定义行。
    4. 零值参数跳过扰动（零通常意味着"该功能未启用"，乘性扰动无意义）。
    5. 输出 parameter_seed_report.json 记录每次扰动的详情。

扰动策略速览（以模板值为基准的乘数范围）：

    参数语义    稳健低超调    快速响应     抗扰恢复     平滑低纹波
    ─────────  ──────────  ──────────  ──────────  ──────────
    _KP        0.6 – 0.9   1.5 – 2.5   1.0 – 1.8   0.5 – 0.8
    _KI        1.0 – 1.5   0.8 – 1.2   1.2 – 2.0   0.5 – 1.0
    _KD        0.5 – 0.8   1.2 – 2.0   1.0 – 1.5   0.4 – 0.7
    _LIMIT     0.7 – 0.9   1.1 – 1.5   1.0 – 1.3   0.6 – 0.9
    _SLOPE     0.5 – 0.8   1.2 – 2.0   1.0 – 1.5   0.4 – 0.7
    _BW/WC/WO  0.6 – 0.9   1.5 – 2.5   1.0 – 1.8   0.5 – 0.8
    未识别      0.8 – 1.0   1.0 – 1.3   1.0 – 1.2   0.7 – 1.0
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from Optimize.agent_optimize.agent_core.parameters.parameter_header_editor import (
    read_tunable_parameters_detailed,
    patch_tunable_parameters,
)


# ── 语义分类 ────────────────────────────────────────────────────────────────

def classify_parameter(name: str) -> str:
    """根据参数名后缀/前缀识别参数语义类别。

    识别顺序由具体到泛化，避免 'SPEED_LIMIT' 被误判为 generic LIMIT
    而丢失 SPEED 语义。
    """
    upper = name.upper().strip()

    # 精确匹配：纯后缀 / 纯前缀 / 完全相等
    for suffix in ("KP", "KI", "KD", "SLOPE"):
        if upper.endswith("_" + suffix) or upper.startswith(suffix + "_") or upper == suffix:
            return suffix

    # LADRC 特征参数
    for ladrc_tag in ("WC", "WO", "BW"):
        if upper.endswith("_" + ladrc_tag) or upper.startswith(ladrc_tag + "_") or upper == ladrc_tag:
            return ladrc_tag

    # CUR + LIMIT 组合（如 CUR_LIMIT, CUR_MAX）
    if "CUR" in upper and ("LIMIT" in upper or "MAX" in upper):
        return "CUR_LIMIT"

    # SPEED + SLOPE 组合 ─ 必须在 SPEED + LIMIT 之前，否则 SPEED_SLOPE_LIMIT 会被误判
    if "SPEED" in upper and "SLOPE" in upper:
        return "SLOPE"

    # SPEED + LIMIT/MAX 组合
    if "SPEED" in upper and ("LIMIT" in upper or "MAX" in upper):
        return "SPEED_LIMIT"

    # 泛化 LIMIT / MAX
    if "LIMIT" in upper or "MAX" in upper:
        return "LIMIT"

    # 泛化 SLOPE
    if "SLOPE" in upper:
        return "SLOPE"

    # 电流相关
    if "CUR" in upper:
        return "CUR"

    # 速度相关
    if "SPEED" in upper or "VEL" in upper:
        return "SPEED"

    return "DEFAULT"


# ── 方案 → 参数类别 → 乘数范围 ─────────────────────────────────────────────

# profile_index 为 1-based，与 candidate_design_profile(index) 对齐。
# 每个条目为 (min_multiplier, max_multiplier)，乘数在区间内均匀随机。

PROFILE_MULTIPLIERS: dict[int, dict[str, tuple[float, float]]] = {
    1: {  # 稳健低超调：压低增益、收紧限幅 → 降低超调和振荡风险
        "KP":         (0.60, 0.90),
        "KI":         (1.00, 1.50),
        "KD":         (0.50, 0.80),
        "LIMIT":      (0.70, 0.90),
        "CUR_LIMIT":  (0.70, 0.90),
        "SPEED_LIMIT":(0.70, 0.90),
        "SLOPE":      (0.50, 0.80),
        "WC":         (0.60, 0.90),
        "WO":         (0.70, 1.00),
        "BW":         (0.60, 0.90),
        "CUR":        (0.70, 0.90),
        "SPEED":      (0.70, 0.90),
        "DEFAULT":    (0.80, 1.00),
    },
    2: {  # 快速响应：拉高增益、放宽限幅 → 追求上升时间和调节时间
        "KP":         (1.50, 2.50),
        "KI":         (0.80, 1.20),
        "KD":         (1.20, 2.00),
        "LIMIT":      (1.10, 1.50),
        "CUR_LIMIT":  (1.10, 1.50),
        "SPEED_LIMIT":(1.10, 1.50),
        "SLOPE":      (1.20, 2.00),
        "WC":         (1.50, 2.50),
        "WO":         (1.20, 2.00),
        "BW":         (1.50, 2.50),
        "CUR":        (1.10, 1.50),
        "SPEED":      (1.10, 1.50),
        "DEFAULT":    (1.00, 1.30),
    },
    3: {  # 抗扰恢复：适度提高增益、保持限幅适中 → 增强外环抗扰和恢复能力
        "KP":         (1.00, 1.80),
        "KI":         (1.20, 2.00),
        "KD":         (1.00, 1.50),
        "LIMIT":      (1.00, 1.30),
        "CUR_LIMIT":  (1.00, 1.30),
        "SPEED_LIMIT":(1.00, 1.30),
        "SLOPE":      (1.00, 1.50),
        "WC":         (1.00, 1.80),
        "WO":         (1.00, 1.50),
        "BW":         (1.00, 1.80),
        "CUR":        (1.00, 1.30),
        "SPEED":      (1.00, 1.30),
        "DEFAULT":    (1.00, 1.20),
    },
    4: {  # 平滑低纹波：压低增益、收紧限幅和斜坡 → 降低电流/速度波动
        "KP":         (0.50, 0.80),
        "KI":         (0.50, 1.00),
        "KD":         (0.40, 0.70),
        "LIMIT":      (0.60, 0.90),
        "CUR_LIMIT":  (0.60, 0.90),
        "SPEED_LIMIT":(0.60, 0.90),
        "SLOPE":      (0.40, 0.70),
        "WC":         (0.50, 0.80),
        "WO":         (0.50, 0.80),
        "BW":         (0.50, 0.80),
        "CUR":        (0.60, 0.90),
        "SPEED":      (0.60, 0.90),
        "DEFAULT":    (0.70, 1.00),
    },
}


# ── 方案名称 → profile_index 的模糊匹配 ───────────────────────────────────

def _resolve_profile_index(candidate_index: int, profile: dict[str, Any] | None) -> int:
    """从 design_profile 的 name 字段推断方案编号，失败时回退到 candidate_index。"""
    if not isinstance(profile, dict):
        return ((candidate_index - 1) % 4) + 1

    name = str(profile.get("name", "")).lower()
    if not name:
        return ((candidate_index - 1) % 4) + 1

    if "快速" in name or "fast" in name or "响应" in name:
        return 2
    if "抗扰" in name or "扰动" in name or "disturbance" in name or "恢复" in name:
        return 3
    if "平滑" in name or "纹波" in name or "ripple" in name or "smooth" in name:
        return 4
    if "稳健" in name or "低超调" in name or "保守" in name or "conservative" in name:
        return 1

    return ((candidate_index - 1) % 4) + 1


# ── 主函数 ─────────────────────────────────────────────────────────────────

def seed_parameters(
    header_path: str | Path,
    candidate_index: int,
    profile: dict[str, Any] | None = None,
    *,
    seed_report_dir: str | Path | None = None,
    label: str = "",
) -> dict[str, Any]:
    """为单个 candidate 的 paras.generated.h 生成差异化初始参数值。

    Args:
        header_path: paras.generated.h 的路径。
        candidate_index: 1-based candidate 序号，用作随机种子以保证可复现。
        profile: design_profile 字典，用于推断方案倾向。
        seed_report_dir: 如果非空，将在此目录写入 parameter_seed_report.json。
        label: 可选的 human-readable 标签，写入 report.meta.label。

    Returns:
        {
          "schema_version": 1,
          "candidate_index": ...,
          "profile_index": ...,
          "header_path": "...",
          "parameters": [{name, category, old_value, new_value, multiplier, skipped}, ...],
          "updated_count": N,
          "skipped_count": N,
          "patch": {...},
          "report_path": "..."  (如果 seed_report_dir 非空)
        }
    """
    header_path = Path(header_path).expanduser().resolve()

    # 1. 读取当前可调参数
    params = read_tunable_parameters_detailed(header_path)

    # 2. 确定方案编号 & 对应乘数表
    profile_index = _resolve_profile_index(candidate_index, profile)
    multipliers = PROFILE_MULTIPLIERS.get(profile_index, PROFILE_MULTIPLIERS[1])

    # 3. 用 candidate_index 作为随机种子，按参数名排序保证确定性
    rng = random.Random(candidate_index)
    param_names = sorted(params.keys())

    updates: dict[str, Any] = {}
    report_params: list[dict[str, Any]] = []
    skipped_count = 0

    for name in param_names:
        param = params[name]
        cls = classify_parameter(name)
        min_m, max_m = multipliers.get(cls, multipliers["DEFAULT"])

        # 零值参数跳过：乘性扰动对 0 无意义
        if param.value == 0:
            skipped_count += 1
            report_params.append({
                "name": name,
                "category": cls,
                "old_value": param.value,
                "new_value": param.value,
                "multiplier": None,
                "skipped": True,
                "reason": "零值参数，乘性扰动无意义",
                "raw_old": param.raw_value,
            })
            continue

        # 生成确定性乘数
        mult = rng.uniform(min_m, max_m)
        new_value_raw = float(param.value) * mult

        # 保持类型：原值是 int 且新值刚好为整数 → 保留 int
        if isinstance(param.value, int) and new_value_raw == int(new_value_raw):
            new_value: Any = int(new_value_raw)
        else:
            # 合理舍入
            new_value = round(new_value_raw, 6)
            # 避免舍入到 0
            if new_value == 0.0:
                new_value = round(float(param.value) * 0.5, 6)

        updates[name] = new_value
        report_params.append({
            "name": name,
            "category": cls,
            "old_value": param.value,
            "new_value": new_value,
            "multiplier": round(mult, 4),
            "skipped": False,
            "raw_old": param.raw_value,
        })

    # 4. 应用修改（patch_tunable_parameters 自动创建备份）
    patch_result: dict[str, Any]
    if updates:
        patch_result = patch_tunable_parameters(header_path, updates, backup=True)
    else:
        patch_result = {"status": "skipped", "changed": False,
                        "header_path": str(header_path),
                        "updated_parameters": {}}

    # 5. 组装报告
    report: dict[str, Any] = {
        "schema_version": 1,
        "meta": {
            "label": str(label or "").strip() or None,
            "candidate_index": candidate_index,
            "profile_index": profile_index,
        },
        "header_path": str(header_path),
        "parameters": report_params,
        "updated_count": len(updates),
        "skipped_count": skipped_count,
        "patch": {
            "status": patch_result.get("status"),
            "changed": patch_result.get("changed"),
            "detail": {name: record
                       for name, record in patch_result.get("updated_parameters", {}).items()},
        },
    }

    # 6. 可选：写出报告文件
    if seed_report_dir:
        report_dir = Path(seed_report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "parameter_seed_report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report["report_path"] = str(report_path.resolve())

    return report


# ── 便捷函数：为多个 candidate 批量种子 ─────────────────────────────────────

def seed_all_candidates(
    project_root: str | Path,
    candidate_count: int,
    profiles: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """对 project_root/candidates/ 下所有 candidate 的 paras.generated.h 执行种子初始化。

    这是一个批量便捷包装，供外部脚本或测试使用。
    """
    project_root = Path(project_root).expanduser().resolve()
    results: list[dict[str, Any]] = []

    for index in range(1, candidate_count + 1):
        header = project_root / "candidates" / f"candidate_{index:02d}" / "src" / "paras.generated.h"
        if not header.exists():
            results.append({
                "candidate_index": index,
                "status": "header_not_found",
                "header_path": str(header),
            })
            continue

        profile = None
        if profiles and index <= len(profiles):
            profile = profiles[index - 1]

        report = seed_parameters(
            header,
            candidate_index=index,
            profile=profile,
            seed_report_dir=project_root / "candidates" / f"candidate_{index:02d}" / "log" / "generate",
            label=f"candidate_{index:02d}",
        )
        results.append(report)

    return results
