"""
iteration_summary.py  —  跨轮次迭代结果聚合，为 UI 可视化提供预计算数据源。

设计原则：
    1. 纯程序化聚合，不依赖 LLM。
    2. 读取所有已完成轮次的 round_feedback.json 和 candidate_profiles.json。
    3. 预计算排序、配色、趋势判断，输出 chart-ready 的数据结构。
    4. 防御式读取：任何文件缺失/损坏不抛异常，产出部分数据 + errors[]。
    5. 独立于 generate/optimize 流程，可在竞赛结束后随时调用。

用法：
    python Competition/iteration_summary.py <project_json>

输出位置：project/rounds/iteration_summary.json
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MOTORAI_ROOT = Path(__file__).resolve().parents[1]
if str(MOTORAI_ROOT) not in sys.path:
    sys.path.insert(0, str(MOTORAI_ROOT))

from Competition.competition_workspace import load_json_object, write_json  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════════════════

COLOR_PALETTE: dict[str, str] = {
    "candidate_01": "#5470c6",
    "candidate_02": "#91cc75",
    "candidate_03": "#fac858",
    "candidate_04": "#ee6666",
    "candidate_05": "#73c0de",
    "candidate_06": "#3ba272",
    "candidate_07": "#fc8452",
    "candidate_08": "#9a60b4",
}

METRIC_COLORS: list[str] = [
    "#ee6666",  # red    — critical / overshoot
    "#fac858",  # yellow — settling_time
    "#91cc75",  # green  — ripple / steady_state
    "#73c0de",  # blue   — other
    "#fc8452",  # orange
    "#9a60b4",  # purple
    "#ea7ccc",  # pink
    "#5470c6",  # steel blue
]


# ═══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════════

def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _ensure_list(value: Any, default: list[Any] | None = None) -> list[Any]:
    if default is None:
        default = []
    if isinstance(value, list):
        return value
    return default


def _get_candidate_color(candidate_id: str) -> str:
    """确定性候选方案配色。已知 ID 直接用调色板，未知 ID 按序号取模。"""
    if candidate_id in COLOR_PALETTE:
        return COLOR_PALETTE[candidate_id]
    # 尝试提取序号
    import re
    m = re.search(r"(\d+)", candidate_id)
    if m:
        idx = int(m.group(1)) - 1
    else:
        idx = hash(candidate_id) % len(COLOR_PALETTE)
    keys = list(COLOR_PALETTE.keys())
    return COLOR_PALETTE[keys[idx % len(keys)]]


def _get_metric_color(metric_name: str, index: int) -> str:
    """确定性指标配色，按字母序排列后分配。"""
    return METRIC_COLORS[index % len(METRIC_COLORS)]


def _param_short_name(full_name: str) -> str:
    """去掉 MOTORAI_ 前缀，保留可读短名。"""
    upper = full_name.strip()
    for prefix in ("MOTORAI_", "MOTOR_"):
        if upper.startswith(prefix):
            return upper[len(prefix):]
    return upper


def _compute_trend(values: list[int | None], metric_name: str = "") -> str:
    """根据失败次数序列判断趋势。

    Returns:
        "clean" — 从未失败
        "resolved" — 单调递减且最后为 0
        "improving" — 单调递减但未归零
        "worsening" — 单调递增
        "persistent" — 每轮值相同且 > 0
        "intermittent" — 存在振荡
        "unknown" — 数据不足
    """
    clean = [v for v in values if v is not None]
    if not clean:
        return "clean"
    if all(v == 0 for v in clean):
        return "clean"
    if len(clean) < 2:
        return "unknown"

    # 检查单调递减
    decreasing = all(clean[i] >= clean[i + 1] for i in range(len(clean) - 1))
    increasing = all(clean[i] <= clean[i + 1] for i in range(len(clean) - 1))
    constant = all(v == clean[0] for v in clean)

    if decreasing and clean[-1] == 0:
        return "resolved"
    if decreasing:
        return "improving"
    if increasing:
        return "worsening"
    if constant and clean[0] > 0:
        return "persistent"
    return "intermittent"


def _compact_label(candidate_id: str, methods: list[str]) -> str:
    """生成紧凑图表标签，如 "PID (c02)"。"""
    short_id = candidate_id.replace("candidate_", "c")
    method_str = "+".join(m.upper()[:4] for m in methods[:2]) if methods else "?"
    return f"{method_str} ({short_id})"


# ═══════════════════════════════════════════════════════════════════════════════
# 数据发现与加载
# ═══════════════════════════════════════════════════════════════════════════════

def _discover_rounds(project_root: Path) -> list[int]:
    """发现所有已完成的轮次目录，返回排序后的轮次编号列表。"""
    rounds_dir = project_root / "rounds"
    if not rounds_dir.is_dir():
        return []
    result: list[int] = []
    for d in sorted(rounds_dir.glob("round_*")):
        if d.is_dir():
            try:
                num = int(d.name.replace("round_", ""))
                result.append(num)
            except ValueError:
                pass
    return sorted(result)


def _load_round_feedback(project_root: Path, round_number: int) -> dict[str, Any] | None:
    """安全加载 round_feedback.json，缺失或损坏返回 None。"""
    path = project_root / "rounds" / f"round_{round_number:02d}" / "round_feedback.json"
    try:
        data = load_json_object(path)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def _load_candidate_profiles(project_root: Path, round_number: int) -> dict[str, Any] | None:
    """安全加载 candidate_profiles.json（用于 winner_lineage），缺失或损坏返回 None。"""
    path = project_root / "rounds" / f"round_{round_number:02d}" / "candidate_profiles.json"
    try:
        data = load_json_object(path)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Section Builders
# ═══════════════════════════════════════════════════════════════════════════════

def _build_overview(
    rounds_data: list[dict[str, Any]],
    round_numbers: list[int],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    """构建 overview 概览卡片数据。"""
    if not rounds_data:
        return {
            "total_candidates_per_round": 0,
            "stop_conditions": {},
            "best_score_overall": None,
            "best_score_round": None,
            "best_score_candidate": None,
            "score_improvement": None,
            "rounds_completed": [],
            "requirement_met_in_round": None,
        }

    # 候选数：取第一轮的 candidate 数量
    total_candidates = len(rounds_data[0].get("candidates", [])) if rounds_data else 0

    # 停止条件：取最后一轮
    stop_conditions = rounds_data[-1].get("stop_conditions") or {}

    # 全局最高分
    best_score: float | None = None
    best_round: int | None = None
    best_candidate: str | None = None
    for i, fb in enumerate(rounds_data):
        winner = fb.get("winner") if isinstance(fb.get("winner"), dict) else None
        if winner:
            s = _safe_float(winner.get("overall_score"))
            if s is not None and (best_score is None or s > best_score):
                best_score = s
                best_round = round_numbers[i]
                best_candidate = str(winner.get("candidate_id", ""))

    # 得分改善
    first_best: float | None = None
    last_best: float | None = None
    if rounds_data:
        fw = rounds_data[0].get("winner") if isinstance(rounds_data[0].get("winner"), dict) else None
        lw = rounds_data[-1].get("winner") if isinstance(rounds_data[-1].get("winner"), dict) else None
        first_best = _safe_float(fw.get("overall_score")) if fw else None
        last_best = _safe_float(lw.get("overall_score")) if lw else None

    improvement: float | None = None
    if first_best is not None and last_best is not None and len(rounds_data) >= 2:
        improvement = round(last_best - first_best, 6)

    # 需求满足于第几轮
    met_round: int | None = None
    for i, fb in enumerate(rounds_data):
        if fb.get("requirement_satisfied"):
            met_round = round_numbers[i]
            break

    return {
        "total_candidates_per_round": total_candidates,
        "stop_conditions": stop_conditions,
        "best_score_overall": best_score,
        "best_score_round": best_round,
        "best_score_candidate": best_candidate,
        "score_improvement": improvement,
        "rounds_completed": round_numbers,
        "requirement_met_in_round": met_round,
    }


def _build_score_progression(
    rounds_data: list[dict[str, Any]],
    round_numbers: list[int],
) -> dict[str, Any]:
    """构建 score_progression 折线图数据。"""
    best_scores: list[float | None] = []
    avg_scores: list[float | None] = []
    worst_scores: list[float | None] = []
    best_candidates: list[str | None] = []

    for fb in rounds_data:
        scoreboard = _ensure_list(fb.get("scoreboard"))
        scored = [
            s for s in scoreboard
            if isinstance(s, dict) and _safe_float(s.get("overall_score")) is not None
        ]
        if scored:
            vals = [_safe_float(s["overall_score"]) for s in scored]  # type: ignore[arg-type]
            vals_clean = [v for v in vals if v is not None]
            best_scores.append(vals_clean[0] if vals_clean else None)
            worst_scores.append(vals_clean[-1] if vals_clean else None)
            avg_scores.append(round(sum(vals_clean) / len(vals_clean), 6) if vals_clean else None)
            best_candidates.append(str(scored[0].get("candidate_id", "")))
        else:
            best_scores.append(None)
            avg_scores.append(None)
            worst_scores.append(None)
            best_candidates.append(None)

    return {
        "rounds": round_numbers,
        "colors": {"best": "#5470c6", "average": "#91cc75", "worst": "#ee6666"},
        "best_scores": best_scores,
        "average_scores": avg_scores,
        "worst_scores": worst_scores,
        "best_candidates": best_candidates,
    }


def _build_rounds_section(
    rounds_data: list[dict[str, Any]],
    round_numbers: list[int],
) -> list[dict[str, Any]]:
    """构建 rounds 数组：每轮 scoreboard + candidate 详情。"""
    result: list[dict[str, Any]] = []
    for fb in rounds_data:
        scoreboard = _ensure_list(fb.get("scoreboard"))
        enriched_sb: list[dict[str, Any]] = []
        for item in scoreboard:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("candidate_id", ""))
            enriched_sb.append({
                "candidate_id": cid,
                "overall_score": item.get("overall_score"),
                "color": _get_candidate_color(cid),
            })

        candidates_raw = _ensure_list(fb.get("candidates"))
        winner_id = ""
        winner_data = fb.get("winner")
        if isinstance(winner_data, dict):
            winner_id = str(winner_data.get("candidate_id", ""))

        candidates: list[dict[str, Any]] = []
        failed_metric_names: set[str] = set()
        structure_labels: list[str] = []

        for c in candidates_raw:
            if not isinstance(c, dict):
                continue
            cid = str(c.get("candidate_id", ""))
            sm = c.get("structure_manifest") if isinstance(c.get("structure_manifest"), dict) else {}
            methods = _ensure_list(sm.get("control_methods"))
            fm = _ensure_list(c.get("failed_metrics"))
            fm_names = [str(m.get("name", "")) for m in fm if isinstance(m, dict) and m.get("name")]
            failed_metric_names.update(fm_names)
            ph = c.get("parameter_history_summary") if isinstance(c.get("parameter_history_summary"), dict) else {}

            candidates.append({
                "candidate_id": cid,
                "overall_score": c.get("overall_score"),
                "color": _get_candidate_color(cid),
                "structure_signature": sm.get("structure_signature", ""),
                "control_methods": methods,
                "failed_metric_count": len(fm_names),
                "parameter_convergence": ph.get("convergence", "unknown"),
                "is_winner": cid == winner_id,
            })
            structure_labels.append(_compact_label(cid, methods))

        result.append({
            "round": fb.get("round"),
            "requirement_satisfied": fb.get("requirement_satisfied", False),
            "winner": fb.get("winner"),
            "scoreboard": enriched_sb,
            "candidates": candidates,
            "failed_metrics": sorted(failed_metric_names),
            "structure_labels": structure_labels,
        })

    return result


def _build_metric_tracking(
    rounds_data: list[dict[str, Any]],
    round_numbers: list[int],
) -> dict[str, Any]:
    """构建 metric_tracking 热力图数据。"""
    # 收集所有出现过的指标名（按首现轮次排序以保持稳定）
    all_metrics: list[str] = []
    seen: set[str] = set()
    for fb in rounds_data:
        fms = _ensure_list(fb.get("failed_metrics_summary"))
        for item in fms:
            if isinstance(item, dict):
                name = str(item.get("metric", ""))
                if name and name not in seen:
                    seen.add(name)
                    all_metrics.append(name)

    if not all_metrics:
        return {
            "metrics": [],
            "rounds": round_numbers,
            "colors": {},
            "failure_counts": {},
            "trends": {},
        }

    # 构建失败计数矩阵
    failure_counts: dict[str, list[int | None]] = {m: [] for m in all_metrics}
    for fb in rounds_data:
        fms = _ensure_list(fb.get("failed_metrics_summary"))
        fm_map: dict[str, int] = {}
        for item in fms:
            if isinstance(item, dict):
                name = str(item.get("metric", ""))
                cnt = _safe_int(item.get("failed_count"))
                if name and cnt is not None:
                    fm_map[name] = cnt
        for m in all_metrics:
            failure_counts[m].append(fm_map.get(m, 0))

    # 计算趋势
    trends: dict[str, str] = {}
    for m in all_metrics:
        trends[m] = _compute_trend(failure_counts[m], m)

    # 配色
    sorted_metrics = sorted(all_metrics)
    colors: dict[str, str] = {}
    for i, m in enumerate(sorted_metrics):
        colors[m] = _get_metric_color(m, i)

    return {
        "metrics": all_metrics,
        "rounds": round_numbers,
        "colors": colors,
        "failure_counts": failure_counts,
        "trends": trends,
    }


def _build_structure_evolution(
    rounds_data: list[dict[str, Any]],
    round_numbers: list[int],
) -> list[dict[str, Any]]:
    """构建 structure_evolution 时间线数据。"""
    result: list[dict[str, Any]] = []
    for fb in rounds_data:
        candidates = _ensure_list(fb.get("candidates"))
        winner_id = ""
        w = fb.get("winner")
        if isinstance(w, dict):
            winner_id = str(w.get("candidate_id", ""))

        # 按 structure_signature 分组
        groups: dict[str, dict[str, Any]] = {}
        for c in candidates:
            if not isinstance(c, dict):
                continue
            cid = str(c.get("candidate_id", ""))
            sm = c.get("structure_manifest") if isinstance(c.get("structure_manifest"), dict) else {}
            sig = str(sm.get("structure_signature", "") or "unknown")
            score = _safe_float(c.get("overall_score"))

            if sig not in groups:
                groups[sig] = {
                    "signature": sig,
                    "candidate_ids": [],
                    "best_score": None,
                    "best_candidate": None,
                }
            groups[sig]["candidate_ids"].append(cid)
            if score is not None:
                if groups[sig]["best_score"] is None or score > groups[sig]["best_score"]:
                    groups[sig]["best_score"] = score
                    groups[sig]["best_candidate"] = cid

        structures: list[dict[str, Any]] = []
        for sig, g in groups.items():
            best_c = g["best_candidate"] or g["candidate_ids"][0] if g["candidate_ids"] else ""
            structures.append({
                "signature": sig,
                "candidate_ids": g["candidate_ids"],
                "best_score": g["best_score"],
                "color": _get_candidate_color(best_c),
                "is_winner_structure": winner_id in g["candidate_ids"],
            })

        result.append({
            "round": fb.get("round"),
            "structures": structures,
        })

    return result


def _build_parameter_trends(
    rounds_data: list[dict[str, Any]],
    round_numbers: list[int],
) -> dict[str, Any]:
    """构建 parameter_trends 多线图数据。

    只追踪在 >=2 轮 winner 的 final_parameters 中出现的参数，
    按累积变化量绝对值之和降序排列。
    """
    if len(rounds_data) < 2:
        return {
            "parameters": [],
            "rounds": round_numbers,
            "candidates_tracked": [],
            "colors": {},
            "values": {},
            "delta_pcts": {},
        }

    # 收集每轮 winner 的参数
    winner_params: dict[int, dict[str, Any]] = {}  # round_number -> {param_name: {value, delta_pct}}
    candidates_tracked: list[str | None] = []

    for fb in rounds_data:
        rn = fb.get("round", 0)
        w = fb.get("winner")
        winner_id = str(w.get("candidate_id", "")) if isinstance(w, dict) else ""
        candidates_tracked.append(winner_id if winner_id else None)

        # 从 candidates 中找到 winner
        cands = _ensure_list(fb.get("candidates"))
        wparams: dict[str, Any] = {}
        for c in cands:
            if isinstance(c, dict) and str(c.get("candidate_id", "")) == winner_id:
                fps = _ensure_list(c.get("final_parameters"))
                for fp in fps:
                    if isinstance(fp, dict):
                        name = str(fp.get("name", ""))
                        if name:
                            wparams[name] = {
                                "final_value": fp.get("final_value"),
                                "delta_pct": fp.get("delta_pct"),
                            }
                break
        winner_params[rn] = wparams

    # 找出在 >=2 轮中都出现的参数
    param_rounds: dict[str, int] = {}
    for rn, wp in winner_params.items():
        for pname in wp:
            param_rounds[pname] = param_rounds.get(pname, 0) + 1

    common_params = [p for p, cnt in param_rounds.items() if cnt >= 2]
    if not common_params:
        return {
            "parameters": [],
            "rounds": round_numbers,
            "candidates_tracked": candidates_tracked,
            "colors": {},
            "values": {},
            "delta_pcts": {},
        }

    # 按累积变化量排序（用 delta_pct 的绝对值之和）
    def _total_variation(pname: str) -> float:
        total = 0.0
        for wp in winner_params.values():
            pd = wp.get(pname, {})
            dp = pd.get("delta_pct")
            if dp is not None and isinstance(dp, (int, float)):
                total += abs(float(dp))
        return total

    common_params.sort(key=_total_variation, reverse=True)

    # 构建值序列
    values: dict[str, list[float | None]] = {p: [] for p in common_params}
    delta_pcts: dict[str, list[float | None]] = {p: [] for p in common_params}

    for fb in rounds_data:
        rn = fb.get("round", 0)
        wp = winner_params.get(rn, {})
        for p in common_params:
            pd = wp.get(p, {})
            values[p].append(pd.get("final_value"))
            delta_pcts[p].append(pd.get("delta_pct"))

    # 配色
    colors: dict[str, str] = {}
    for i, p in enumerate(common_params):
        colors[p] = METRIC_COLORS[i % len(METRIC_COLORS)]

    # 短名映射
    short_names = {p: _param_short_name(p) for p in common_params}

    return {
        "parameters": common_params,
        "parameter_labels": [short_names[p] for p in common_params],
        "rounds": round_numbers,
        "candidates_tracked": candidates_tracked,
        "colors": colors,
        "values": values,
        "delta_pcts": delta_pcts,
    }


def _build_winner_lineage(
    rounds_data: list[dict[str, Any]],
    round_numbers: list[int],
    all_profiles: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """构建 winner_lineage 继承链数据。"""
    result: list[dict[str, Any]] = []

    for i, fb in enumerate(rounds_data):
        rn = round_numbers[i]
        w = fb.get("winner")
        if not isinstance(w, dict):
            continue
        winner_id = str(w.get("candidate_id", ""))
        if not winner_id:
            continue

        # 找 winner 的结构信息
        winner_sig = ""
        winner_methods: list[str] = []
        for c in _ensure_list(fb.get("candidates")):
            if isinstance(c, dict) and str(c.get("candidate_id", "")) == winner_id:
                sm = c.get("structure_manifest") if isinstance(c.get("structure_manifest"), dict) else {}
                winner_sig = str(sm.get("structure_signature", ""))
                winner_methods = _ensure_list(sm.get("control_methods"))
                break

        # 找下一轮谁继承了这个 winner
        inherited_by: list[dict[str, Any]] = []
        if i + 1 < len(round_numbers):
            next_round = round_numbers[i + 1]
            next_profiles_data = all_profiles.get(next_round)
            if next_profiles_data:
                next_profiles = _ensure_list(next_profiles_data.get("profiles"))
                for np_ in next_profiles:
                    if not isinstance(np_, dict):
                        continue
                    np_cid = str(np_.get("candidate_id", ""))
                    seed = np_.get("parameter_seed_policy")
                    if not isinstance(seed, dict):
                        seed = {}
                    source = str(seed.get("source_candidate", "") or "")
                    refs = _ensure_list(np_.get("reference_candidates"))
                    # 检查是否引用了本轮的 winner
                    if source == winner_id or winner_id in refs:
                        inherited_by.append({
                            "round": next_round,
                            "candidate_id": np_cid,
                            "name": str(np_.get("name", "")),
                            "policy_mode": str(seed.get("mode", "")),
                            "perturbation": str(seed.get("perturbation_direction", "") or ""),
                        })

        result.append({
            "round": rn,
            "winner_id": winner_id,
            "winner_score": w.get("overall_score"),
            "structure_signature": winner_sig,
            "control_methods": winner_methods,
            "color": _get_candidate_color(winner_id),
            "inherited_by": inherited_by,
        })

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════════════════════

def generate_iteration_summary(
    project_json: str | Path,
    *,
    output_dir: str | Path | None = None,
) -> Path:
    """聚合所有轮次数据，生成 iteration_summary.json。

    Args:
        project_json: 项目 JSON 文件路径。
        output_dir: 输出目录，默认 project_root/rounds/。

    Returns:
        写入的 iteration_summary.json 路径。
    """
    project_json = Path(project_json).expanduser().resolve()
    project_root = project_json.parent
    project_data: dict[str, Any] = {}
    try:
        project_data = load_json_object(project_json)
        if not isinstance(project_data, dict):
            project_data = {}
    except Exception:
        pass

    errors: list[dict[str, Any]] = []

    # 发现轮次
    round_numbers = _discover_rounds(project_root)
    if not round_numbers:
        # 没有 rounds 目录，输出骨架
        errors.append({
            "severity": "warning",
            "message": "未找到 rounds/ 目录，请先完成至少一轮优化。",
        })

    # 加载所有 round_feedback
    rounds_data: list[dict[str, Any]] = []
    valid_rounds: list[int] = []
    for rn in round_numbers:
        fb = _load_round_feedback(project_root, rn)
        if fb is None:
            errors.append({
                "severity": "warning",
                "round": rn,
                "message": f"round_{rn:02d}/round_feedback.json 缺失或损坏，已跳过。",
            })
            continue
        candidates = _ensure_list(fb.get("candidates"))
        if not candidates:
            errors.append({
                "severity": "warning",
                "round": rn,
                "message": f"round_{rn:02d} 没有有效的 candidate 数据。",
            })
        rounds_data.append(fb)
        valid_rounds.append(rn)

    # 加载所有 candidate_profiles（用于 winner_lineage）
    all_profiles: dict[int, dict[str, Any]] = {}
    for rn in round_numbers:
        cp = _load_candidate_profiles(project_root, rn)
        if cp is not None:
            all_profiles[rn] = cp
    # 也加载 common/ 下的第一轮 profiles（用于跨轮继承查找）
    common_profiles_path = project_root / "common" / "candidate_profiles.json"
    try:
        common_profiles = load_json_object(common_profiles_path)
        if isinstance(common_profiles, dict) and 1 not in all_profiles:
            all_profiles[1] = common_profiles
    except Exception:
        pass

    # 构建各 section
    overview = _build_overview(rounds_data, valid_rounds, errors)
    score_progression = _build_score_progression(rounds_data, valid_rounds)
    rounds_section = _build_rounds_section(rounds_data, valid_rounds)
    metric_tracking = _build_metric_tracking(rounds_data, valid_rounds)
    structure_evolution = _build_structure_evolution(rounds_data, valid_rounds)
    parameter_trends = _build_parameter_trends(rounds_data, valid_rounds)
    winner_lineage = _build_winner_lineage(rounds_data, valid_rounds, all_profiles)

    # 确定最终需求满足状态
    requirement_satisfied = False
    final_winner: str | None = None
    if rounds_data:
        requirement_satisfied = bool(rounds_data[-1].get("requirement_satisfied", False))
        w = rounds_data[-1].get("winner")
        if isinstance(w, dict):
            final_winner = str(w.get("candidate_id", "")) or None

    # 项目名
    project_name = project_json.stem

    # 源文件索引
    source_files: dict[str, Any] = {
        "project_json": str(project_json),
        "rounds_dir": str((project_root / "rounds").resolve()),
        "round_feedbacks": {
            str(rn): str((project_root / "rounds" / f"round_{rn:02d}" / "round_feedback.json").resolve())
            for rn in valid_rounds
        },
    }

    output: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_name": project_name,
        "total_rounds": len(valid_rounds),
        "requirement_satisfied": requirement_satisfied,
        "final_winner": final_winner,
        "has_errors": len(errors) > 0,
        "errors": errors,
        "overview": overview,
        "score_progression": score_progression,
        "rounds": rounds_section,
        "metric_tracking": metric_tracking,
        "structure_evolution": structure_evolution,
        "parameter_trends": parameter_trends,
        "winner_lineage": winner_lineage,
        "color_palette": COLOR_PALETTE,
        "source_files": source_files,
    }

    # 写入
    out_dir = Path(output_dir).resolve() if output_dir else (project_root / "rounds")
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "iteration_summary.json"
    write_json(output_path, output)
    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="生成跨轮次迭代摘要，为 UI 可视化提供预计算数据源。"
    )
    parser.add_argument("project_json", type=Path, help="项目 JSON 文件路径")
    parser.add_argument("--output-dir", type=Path, default=None, help="输出目录，默认 project/rounds/")
    args = parser.parse_args(argv)

    try:
        output_path = generate_iteration_summary(
            args.project_json,
            output_dir=args.output_dir,
        )
        print(f"iteration_summary written: {output_path}")
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
