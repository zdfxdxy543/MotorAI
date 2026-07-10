"""
candidate_evidence.py  —  Step 2: 为每个 candidate 生成优化证据摘要。

设计原则：
    1. 纯程序化提取，不依赖 LLM。
    2. 只包含需要计算加工的内容，不重复 source_files 里已有的数据。
    3. 任一文件缺失或解析失败不影响主流程——对应字段留空。
    4. failed_metrics 从 evaluation_result.json 程序化提取，不编造。

输出位置：candidate/log/optimize/candidate_evidence.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from Optimize.agent_optimize.agent_core.parameters.parameter_header_editor import (
    read_tunable_parameters,
)
from Optimize.agent_optimize.agent_core.parameters.parameter_history import (
    read_optimization_history,
    extract_overall_score,
)

# 匹配 C 宏风格的参数名：大写字母 + 下划线 + 数字
_PARAM_NAME_RE = re.compile(r"\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b")


# ── 辅助：加载 JSON 文件 ──────────────────────────────────────────────────

def _load_json(path: Path) -> dict[str, Any]:
    """安全加载 JSON 文件，失败返回空 dict。"""
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    """安全加载 JSONL 文件，失败返回空 list。"""
    try:
        if path.exists():
            return read_optimization_history(path, limit=500)
    except Exception:
        pass
    return []


# ── 失败指标提取 ──────────────────────────────────────────────────────────

def _extract_failed_metrics(evaluation: dict[str, Any]) -> list[dict[str, Any]]:
    """从 evaluation_result 中提取未达标的指标列表。"""
    if not evaluation:
        return []

    metrics = evaluation.get("metrics")
    if not isinstance(metrics, dict):
        error_count = evaluation.get("metric_error_count")
        if isinstance(error_count, (int, float)) and int(error_count) > 0:
            return [{"note": f"{int(error_count)} metrics reported as error, no detail available"}]
        return []

    failed: list[dict[str, Any]] = []
    for name, m in metrics.items():
        if not isinstance(m, dict):
            continue
        status = str(m.get("status", "")).lower()
        if status != "ok":
            entry: dict[str, Any] = {"name": name, "status": status}
            for field in ("value", "score", "weight", "optimization_direction"):
                if field in m:
                    entry[field] = m[field]
            extra = m.get("extra")
            if isinstance(extra, dict):
                for thresh in ("good_threshold", "bad_threshold", "target_value"):
                    if thresh in extra:
                        entry[thresh] = extra[thresh]
            for thresh in ("good_threshold", "bad_threshold"):
                if thresh in m and thresh not in entry:
                    entry[thresh] = m[thresh]
            target = entry.get("target_value") or entry.get("good_threshold")
            value = entry.get("value")
            if target is not None and value is not None:
                try:
                    entry["gap"] = round(float(value) - float(target), 6)
                except (TypeError, ValueError):
                    pass
            failed.append(entry)

    return failed


# ── 参数变化分析 ──────────────────────────────────────────────────────────

def _analyze_parameter_changes(
    initial_params: dict[str, Any],
    final_params: dict[str, Any],
    history_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """分析参数在优化过程中的变化情况。"""
    param_details: list[dict[str, Any]] = []
    deltas: list[tuple[str, float]] = []

    for name in sorted(final_params.keys()):
        final_val = final_params.get(name)
        init_val = initial_params.get(name)
        detail: dict[str, Any] = {"name": name, "final_value": final_val}
        if init_val is not None:
            detail["initial_value"] = init_val
            try:
                fi = float(init_val)
                ff = float(final_val)
                if abs(fi) > 1e-12:
                    delta_pct = round((ff - fi) / abs(fi) * 100, 2)
                else:
                    delta_pct = round(ff - fi, 6)
                detail["delta_abs"] = round(ff - fi, 6)
                detail["delta_pct"] = delta_pct
                deltas.append((name, abs(delta_pct) if abs(fi) > 1e-12 else abs(ff - fi)))
            except (TypeError, ValueError):
                detail["delta_pct"] = None
        param_details.append(detail)

    if deltas:
        deltas.sort(key=lambda x: x[1], reverse=True)
        total = len(deltas)
        most_adjusted = [name for name, _ in deltas[:max(1, total // 3)] if deltas[0][1] > 1.0]
        barely_moved = [name for name, d in deltas[-max(1, total // 3):] if d < 0.5]
        if not most_adjusted:
            most_adjusted = [deltas[0][0]]
        if not barely_moved:
            barely_moved = [deltas[-1][0]]
    else:
        most_adjusted = []
        barely_moved = []

    return {
        "most_adjusted": most_adjusted,
        "barely_moved": barely_moved,
        "parameters": param_details,
        "convergence": _judge_convergence(history_records),
    }


def _judge_convergence(history_records: list[dict[str, Any]]) -> str:
    """基于 history 中的 overall_score 序列判断收敛趋势。"""
    if not history_records:
        return "unknown"

    scores: list[float] = []
    for rec in history_records:
        score = None
        try:
            score = float(rec.get("overall_score", None))
        except (TypeError, ValueError):
            pass
        if score is None:
            score = extract_overall_score(rec.get("evaluation_result"))
        if score is not None:
            scores.append(score)

    if len(scores) < 3:
        return "unknown"

    recent = scores[-4:] if len(scores) >= 4 else scores
    diffs = [recent[i] - recent[i - 1] for i in range(1, len(recent))]

    if all(d > 0 for d in diffs):
        return "improving"
    if all(d < 0 for d in diffs):
        return "diverging"
    signs = [1 if d > 0 else -1 if d < 0 else 0 for d in diffs]
    if len(signs) >= 3 and signs.count(1) > 0 and signs.count(-1) > 0:
        return "oscillating"
    max_change = max(abs(d) for d in diffs)
    if max_change < (recent[0] * 0.01 if recent[0] > 0 else 0.1):
        return "stable"

    return "unknown"


# ── 诊断提取 ────────────────────────────────────────────────────────────────

def _extract_diagnosed_but_unchanged(
    history_records: list[dict[str, Any]],
) -> list[str]:
    """Find parameter names the agent discussed but never changed.

    Scans agent_reason text for UPPER_CASE parameter name patterns and
    subtracts the set of names that appear in any iteration's parameter_updates.
    """
    mentioned: set[str] = set()
    changed: set[str] = set()

    for rec in history_records:
        reason = str(rec.get("agent_reason", "") or "")
        mentioned.update(_PARAM_NAME_RE.findall(reason))

        updates = rec.get("parameter_updates")
        if isinstance(updates, dict):
            changed.update(str(k).upper() for k in updates)

    return sorted(mentioned - changed)


def _build_tuning_diagnostics(
    history_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a structured tuning_diagnostics block from optimisation history."""
    iterations_log: list[dict[str, Any]] = []
    for i, rec in enumerate(history_records, start=1):
        reason = rec.get("agent_reason", "")
        updates = rec.get("parameter_updates", {})
        iterations_log.append({
            "iteration": i,
            "agent_reason": reason,
            "parameters_changed": (
                sorted(updates.keys()) if isinstance(updates, dict) else []
            ),
        })

    final_assessment = iterations_log[-1]["agent_reason"] if iterations_log else ""
    diagnosed_but_unchanged = _extract_diagnosed_but_unchanged(history_records)

    return {
        "final_agent_assessment": final_assessment,
        "parameters_diagnosed_but_unchanged": diagnosed_but_unchanged,
        "iterations_log": iterations_log,
    }


# ── 主函数 ────────────────────────────────────────────────────────────────

def write_candidate_evidence(candidate_dir: str | Path) -> Path:
    """为单个 candidate 生成 candidate_evidence.json。"""
    candidate_dir = Path(candidate_dir).expanduser().resolve()
    candidate_id = candidate_dir.name
    log_optimize = candidate_dir / "log" / "optimize"
    log_generate = candidate_dir / "log" / "generate"
    src_dir = candidate_dir / "src"

    evidence: dict[str, Any] = {
        "schema_version": 1,
        "candidate_id": candidate_id,
    }

    # ── 1. final_evaluation：从 tuning_result.json 透传 ────────────
    tuning_path = log_optimize / "tuning_result.json"
    tuning = _load_json(tuning_path)
    final_evaluation = tuning.get("final_evaluation")
    evidence["final_evaluation"] = final_evaluation if isinstance(final_evaluation, dict) else {}

    # ── 2. failed_metrics：从 evaluation_result.json 提取 ──────────
    eval_path = log_optimize / "evaluation_result.json"
    evidence["failed_metrics"] = _extract_failed_metrics(_load_json(eval_path))

    # ── 3. structure：从 controller_manifest.json 透传 ─────────────
    manifest_path = log_generate / "controller_manifest.json"
    initial_params: dict[str, Any] = {}
    structure: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = _load_json(manifest_path)
        structure = {
            "structure_signature": manifest.get("structure_signature"),
            "loop_hierarchy": manifest.get("loop_hierarchy"),
            "control_methods": manifest.get("control_methods"),
        }
        for p in manifest.get("tunable_parameters") or []:
            if isinstance(p, dict) and "name" in p:
                initial_params[p["name"]] = p.get("initial_value")
    evidence["structure"] = structure

    # ── 4. final_parameters：从 paras.generated.h + manifest 计算 ──
    paras_header = src_dir / "paras.generated.h"
    final_params: dict[str, Any] = {}
    try:
        if paras_header.exists():
            final_params = read_tunable_parameters(paras_header)
    except Exception:
        pass

    final_param_details: list[dict[str, Any]] = []
    for name in sorted(final_params.keys()):
        entry: dict[str, Any] = {"name": name, "final_value": final_params[name]}
        if name in initial_params:
            entry["initial_value"] = initial_params[name]
            try:
                fi = float(initial_params[name])
                ff = float(final_params[name])
                if abs(fi) > 1e-12:
                    entry["delta_pct"] = round((ff - fi) / abs(fi) * 100, 2)
                else:
                    entry["delta_abs"] = round(ff - fi, 6)
            except (TypeError, ValueError):
                pass
        final_param_details.append(entry)
    evidence["final_parameters"] = final_param_details

    # ── 5. parameter_history_summary：从 history JSONL 计算 ────────
    history_path = log_optimize / "optimization_history.jsonl"
    evidence["parameter_history_summary"] = _analyze_parameter_changes(
        initial_params, final_params, _load_jsonl(history_path),
    )

    # ── 6. source_files：各产物路径 ────────────────────────────────
    sim_path = log_optimize / "simulation" / "processed.json"
    evidence["source_files"] = {
        "tuning_result": str(tuning_path.resolve()),
        "evaluation_result": str(eval_path.resolve()),
        "optimization_history": str(history_path.resolve()),
        "simulation_result": str(sim_path.resolve()),
        "controller_manifest": str(manifest_path.resolve()),
        "paras_header": str(paras_header.resolve()),
    }

    # ── 7. tuning_diagnostics：agent 诊断的结构化提取 ───────────────
    # agent 在 agent_reason 中的根因诊断原本是自由文本，在后续
    # round_feedback → next_round_strategy 链路中被丢弃。
    # 这里把它结构化：迭代日志 + 最终评估 + "提到但没改"的参数。
    history_records = _load_jsonl(history_path)
    evidence["tuning_diagnostics"] = _build_tuning_diagnostics(history_records)

    # ── 写入 ──────────────────────────────────────────────────────
    log_optimize.mkdir(parents=True, exist_ok=True)
    output_path = log_optimize / "candidate_evidence.json"
    output_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
