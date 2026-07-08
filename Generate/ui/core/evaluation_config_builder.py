import json
import re
from typing import Any, Callable


SUPPORTED_SIGNALS = {
    "speed": "rotor_speed_rad_s",
    "rotor_speed": "rotor_speed_rad_s",
    "rotor_speed_rad_s": "rotor_speed_rad_s",
    "torque": "electromagnetic_torque_nm",
    "electromagnetic_torque": "electromagnetic_torque_nm",
    "electromagnetic_torque_nm": "electromagnetic_torque_nm",
    "iq": "stator_iq_a",
    "stator_iq": "stator_iq_a",
    "stator_iq_a": "stator_iq_a",
    "id": "stator_id_a",
    "stator_id": "stator_id_a",
    "stator_id_a": "stator_id_a",
}

TARGET_REQUIRED_METRICS = {
    "mean_absolute_error",
    "rms_error",
    "steady_state_error",
    "overshoot",
    "rise_time",
    "settling_time",
    "response_delay",
}

METRIC_ALIASES = {
    "steady_error": "steady_state_error",
    "steady_state": "steady_state_error",
    "settle_time": "settling_time",
    "adjustment_time": "settling_time",
    "overshoot_ratio": "overshoot",
    "peak": "peak_value",
    "max_value": "peak_value",
    "p2p": "ripple",
}


def _json_from_text(text: str) -> dict[str, Any]:
    content = (text or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content)
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end >= start:
        content = content[start : end + 1]
    data = json.loads(content)
    return data if isinstance(data, dict) else {}


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _signal_name(value: Any) -> str | None:
    key = str(value or "").strip().lower()
    key = key.replace(" ", "_").replace("-", "_")
    return SUPPORTED_SIGNALS.get(key)


def _metric_name(value: Any) -> str | None:
    key = str(value or "").strip().lower()
    key = key.replace(" ", "_").replace("-", "_")
    key = METRIC_ALIASES.get(key, key)
    supported = {
        "final_value",
        "peak_value",
        "min_value",
        "peak_to_peak",
        "mean_absolute_error",
        "rms_error",
        "steady_state_error",
        "overshoot",
        "rise_time",
        "settling_time",
        "ripple",
        "response_delay",
        "stability",
    }
    return key if key in supported else None


def _extract_speed_target(text: str) -> float | None:
    patterns = [
        r"(?:目标|恒定|稳态|稳定)?(?:速度|转速)[^\d\-+]{0,12}([+-]?\d+(?:\.\d+)?)\s*(rad/s|rpm|r/min|转/分)?",
        r"([+-]?\d+(?:\.\d+)?)\s*(rad/s|rpm|r/min|转/分)[^\n，,。；;]{0,12}(?:速度|转速)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = _as_float(match.group(1))
        if value is None:
            continue
        unit = (match.group(2) or "rad/s").lower()
        if unit in {"rpm", "r/min", "转/分"}:
            return value * 6.283185307179586 / 60.0
        return value
    return None


def _extract_percent_after_terms(text: str, terms: tuple[str, ...]) -> float | None:
    term_pattern = "|".join(re.escape(term) for term in terms)
    patterns = [
        rf"(?:{term_pattern})[^\d%％]{{0,12}}([+-]?\d+(?:\.\d+)?)\s*[%％]",
        rf"([+-]?\d+(?:\.\d+)?)\s*[%％][^\n，,。；;]{{0,12}}(?:{term_pattern})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _as_float(match.group(1))
    return None


def _extract_seconds_after_terms(text: str, terms: tuple[str, ...]) -> float | None:
    term_pattern = "|".join(re.escape(term) for term in terms)
    patterns = [
        rf"(?:{term_pattern})[^\d]{{0,16}}([+-]?\d+(?:\.\d+)?)\s*(ms|毫秒|s|秒)",
        rf"([+-]?\d+(?:\.\d+)?)\s*(ms|毫秒|s|秒)[^\n，,。；;]{{0,16}}(?:{term_pattern})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = _as_float(match.group(1))
        if value is None:
            continue
        unit = match.group(2).lower()
        return value / 1000.0 if unit in {"ms", "毫秒"} else value
    return None


def _local_spec(text: str) -> dict[str, Any]:
    target_speed = _extract_speed_target(text)
    targets = []
    if target_speed is not None:
        targets.append(
            {
                "signal": "rotor_speed_rad_s",
                "target_value": target_speed,
                "unit": "rad/s",
            }
        )

    metric_requests: list[dict[str, Any]] = []
    steady_percent = _extract_percent_after_terms(text, ("稳态误差", "速度误差", "误差"))
    if steady_percent is not None:
        metric_requests.append(
            {
                "metric_name": "steady_state_error",
                "signal": "rotor_speed_rad_s",
                "limit_value": steady_percent,
                "limit_unit": "percent",
                "window_ratio": 0.1,
            }
        )

    overshoot_percent = _extract_percent_after_terms(text, ("超调量", "超调"))
    if overshoot_percent is not None:
        metric_requests.append(
            {
                "metric_name": "overshoot",
                "signal": "rotor_speed_rad_s",
                "limit_value": overshoot_percent,
                "limit_unit": "percent",
            }
        )

    settling_seconds = _extract_seconds_after_terms(text, ("调整时间", "调节时间", "恢复时间", "响应时间"))
    if settling_seconds is not None:
        metric_requests.append(
            {
                "metric_name": "settling_time",
                "signal": "rotor_speed_rad_s",
                "limit_value": settling_seconds,
                "limit_unit": "s",
                "tolerance_percent": steady_percent if steady_percent is not None else 2.0,
            }
        )

    rise_seconds = _extract_seconds_after_terms(text, ("上升时间",))
    if rise_seconds is not None:
        metric_requests.append(
            {
                "metric_name": "rise_time",
                "signal": "rotor_speed_rad_s",
                "limit_value": rise_seconds,
                "limit_unit": "s",
            }
        )

    return {
        "targets": targets,
        "metric_requests": metric_requests,
    }


def _extract_spec_with_llm(
    requirement_text: str,
    llm_caller: Callable[..., str] | None,
) -> dict[str, Any]:
    if llm_caller is None:
        return {}
    prompt = (
        "请把用户需求解析为严格 JSON。不要输出 Markdown。\n"
        "字段：targets 和 metric_requests。\n"
        "targets 数组元素：signal, target_value, unit。signal 只能是 "
        "rotor_speed_rad_s, electromagnetic_torque_nm, stator_iq_a, stator_id_a。\n"
        "metric_requests 数组元素：metric_name, signal, limit_value, limit_unit, "
        "可选 tolerance_percent/window_ratio/weight。metric_name 只能是 "
        "steady_state_error, overshoot, settling_time, rise_time, ripple, "
        "mean_absolute_error, rms_error, peak_value, final_value, stability。\n"
        "百分比 limit_unit 写 percent，时间写 s，物理量绝对值写原单位。"
        "不要把 rad/s 换算成别的默认速度；用户写 31.416 rad/s 就保持 31.416。\n"
        f"用户需求：\n{requirement_text}"
    )
    try:
        raw = llm_caller(prompt, "你是性能指标结构化解析器，只输出 JSON。", temperature=0.0)
        return _json_from_text(raw)
    except Exception:
        return {}


def _merge_specs(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = dict(primary or {})
    if not merged.get("targets") and fallback.get("targets"):
        merged["targets"] = fallback["targets"]
    if not merged.get("metric_requests") and fallback.get("metric_requests"):
        merged["metric_requests"] = fallback["metric_requests"]
    return merged


def _target_map(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for item in spec.get("targets") or []:
        if not isinstance(item, dict):
            continue
        signal = _signal_name(item.get("signal"))
        value = _as_float(item.get("target_value"))
        if signal is None or value is None:
            continue
        targets[signal] = {
            "target_value": value,
            "unit": str(item.get("unit") or ""),
            "description": str(item.get("description") or "目标值"),
        }
    return targets


def _thresholds(
    metric_name: str,
    limit_value: float | None,
    limit_unit: str,
    target_value: float | None,
) -> tuple[float | None, float | None]:
    if limit_value is None:
        return None, None
    unit = (limit_unit or "").lower()
    if metric_name in {"steady_state_error", "mean_absolute_error", "rms_error", "ripple"}:
        if unit in {"percent", "%", "％"} and target_value is not None:
            good = abs(target_value) * limit_value / 100.0
        else:
            good = limit_value
        return good, good * 5.0 if good >= 0 else None
    if metric_name == "overshoot":
        good = limit_value / 100.0 if unit in {"percent", "%", "％"} else limit_value
        return good, max(good * 5.0, good + 0.02)
    if metric_name in {"settling_time", "rise_time", "response_delay"}:
        good = limit_value
        return good, good * 3.0
    if metric_name in {"peak_value", "final_value", "stability"}:
        good = limit_value
        return good, good * 1.5 if good >= 0 else None
    return None, None


def _build_metrics(spec: dict[str, Any], targets: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    requests = spec.get("metric_requests") or []
    for item in requests:
        if not isinstance(item, dict):
            continue
        metric_name = _metric_name(item.get("metric_name"))
        signal = _signal_name(item.get("signal"))
        if metric_name is None or signal is None:
            continue
        target_value = targets.get(signal, {}).get("target_value")
        if metric_name in TARGET_REQUIRED_METRICS and target_value is None:
            continue

        metric: dict[str, Any] = {
            "metric_name": metric_name,
            "signal": signal,
            "weight": _as_float(item.get("weight")) or 1.0,
            "optimization_direction": "minimize",
            "result_name": f"{signal}_{metric_name}",
        }
        if target_value is not None and metric_name in TARGET_REQUIRED_METRICS:
            metric["target_value"] = target_value
        if metric_name == "overshoot":
            metric["normalize"] = True
        if metric_name in {"steady_state_error", "ripple", "stability"}:
            metric["window"] = _as_float(item.get("window_ratio")) or 0.1
        if metric_name == "settling_time":
            tolerance_percent = _as_float(item.get("tolerance_percent"))
            if tolerance_percent is not None:
                metric["tolerance_ratio"] = tolerance_percent / 100.0

        limit_value = _as_float(item.get("limit_value"))
        good, bad = _thresholds(
            metric_name,
            limit_value,
            str(item.get("limit_unit") or ""),
            target_value,
        )
        if good is not None:
            metric["good_threshold"] = good
        if bad is not None:
            metric["bad_threshold"] = bad
        metrics.append(metric)

    if not metrics and "rotor_speed_rad_s" in targets:
        target_value = targets["rotor_speed_rad_s"]["target_value"]
        metrics.extend(
            [
                {
                    "metric_name": "steady_state_error",
                    "signal": "rotor_speed_rad_s",
                    "target_value": target_value,
                    "weight": 0.5,
                    "optimization_direction": "minimize",
                    "window": 0.1,
                    "good_threshold": abs(target_value) * 0.01,
                    "bad_threshold": abs(target_value) * 0.05,
                    "result_name": "rotor_speed_rad_s_steady_state_error",
                },
                {
                    "metric_name": "overshoot",
                    "signal": "rotor_speed_rad_s",
                    "target_value": target_value,
                    "weight": 0.5,
                    "optimization_direction": "minimize",
                    "normalize": True,
                    "good_threshold": 0.05,
                    "bad_threshold": 0.25,
                    "result_name": "rotor_speed_rad_s_overshoot",
                },
            ]
        )

    if metrics:
        weight = 1.0 / len(metrics)
        for metric in metrics:
            metric["weight"] = weight
    return metrics


def build_evaluation_payload(
    requirement_text: str,
    *,
    task_type: str = "",
    llm_caller: Callable[..., str] | None = None,
) -> dict[str, Any]:
    local = _local_spec(requirement_text)
    llm_spec = _extract_spec_with_llm(requirement_text, llm_caller)
    spec = _merge_specs(llm_spec, local)
    targets = _target_map(spec)
    metrics = _build_metrics(spec, targets)
    signals = {metric["signal"]: metric["signal"] for metric in metrics}
    for signal in targets:
        signals.setdefault(signal, signal)

    resolved_task_type = task_type or ("constant_speed_control" if "rotor_speed_rad_s" in signals else "custom_control")
    objective = str(spec.get("objective") or requirement_text or "").strip()
    evaluation_config = {
        "task_type": resolved_task_type,
        "objective": objective,
        "signals": signals,
        "metrics": metrics,
    }
    return {
        "objective": objective,
        "signals": signals,
        "targets": targets,
        "metrics": metrics,
        "evaluation_config": evaluation_config,
    }
