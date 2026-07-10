"""Quick validation script for iteration_summary module."""
import json
import sys
import tempfile
from pathlib import Path

MOTORAI_ROOT = Path(__file__).resolve().parents[1]
if str(MOTORAI_ROOT) not in sys.path:
    sys.path.insert(0, str(MOTORAI_ROOT))


def main() -> int:
    # 创建临时项目结构
    tmp = Path(tempfile.mkdtemp())
    project_json = tmp / "test_project.json"
    project_json.write_text(
        json.dumps(
            {
                "objective_text": "test",
                "stop_conditions": {"overall_score_min": 0.85},
                "max_rounds": 3,
                "candidate_count": 4,
            }
        ),
        encoding="utf-8",
    )

    # round_01
    r1 = tmp / "rounds" / "round_01"
    r1.mkdir(parents=True)
    r1_fb = {
        "schema_version": 1,
        "round": 1,
        "requirement_satisfied": False,
        "stop_conditions": {"overall_score_min": 0.85},
        "winner": {"candidate_id": "candidate_02", "overall_score": 0.72},
        "scoreboard": [
            {"candidate_id": "candidate_02", "overall_score": 0.72},
            {"candidate_id": "candidate_01", "overall_score": 0.65},
            {"candidate_id": "candidate_03", "overall_score": 0.61},
            {"candidate_id": "candidate_04", "overall_score": 0.58},
        ],
        "candidates": [
            {
                "candidate_id": "candidate_01",
                "overall_score": 0.65,
                "structure_manifest": {
                    "structure_signature": "current_loop+mech_loop:pid",
                    "loop_hierarchy": ["current_loop", "mech_loop"],
                    "control_methods": ["pid"],
                },
                "failed_metrics": [
                    {"name": "overshoot", "status": "error", "value": 0.15},
                    {"name": "settling_time", "status": "error", "value": 0.5},
                ],
                "final_parameters": [
                    {"name": "SPEED_KP", "final_value": 0.5, "initial_value": 0.4, "delta_pct": 25.0},
                ],
                "parameter_history_summary": {
                    "convergence": "improving",
                    "most_adjusted": ["SPEED_KP"],
                    "barely_moved": ["SPEED_KI"],
                },
            },
            {
                "candidate_id": "candidate_02",
                "overall_score": 0.72,
                "structure_manifest": {
                    "structure_signature": "current_loop+mech_loop:pid",
                    "loop_hierarchy": ["current_loop", "mech_loop"],
                    "control_methods": ["pid"],
                },
                "failed_metrics": [
                    {"name": "overshoot", "status": "error", "value": 0.08},
                ],
                "final_parameters": [
                    {"name": "SPEED_KP", "final_value": 0.6, "initial_value": 0.5, "delta_pct": 20.0},
                    {"name": "CUR_LIMIT", "final_value": 10.0, "initial_value": 10.0, "delta_pct": 0.0},
                ],
                "parameter_history_summary": {
                    "convergence": "stable",
                    "most_adjusted": ["SPEED_KP"],
                    "barely_moved": ["CUR_LIMIT"],
                },
            },
        ],
        "failed_metrics_summary": [
            {"metric": "overshoot", "failed_in": ["candidate_01", "candidate_02"], "failed_count": 2},
            {"metric": "settling_time", "failed_in": ["candidate_01"], "failed_count": 1},
        ],
    }
    (r1 / "round_feedback.json").write_text(
        json.dumps(r1_fb, ensure_ascii=False), encoding="utf-8"
    )

    # round_02
    r2 = tmp / "rounds" / "round_02"
    r2.mkdir(parents=True)
    r2_fb = {
        "schema_version": 1,
        "round": 2,
        "requirement_satisfied": False,
        "winner": {"candidate_id": "candidate_01", "overall_score": 0.78},
        "scoreboard": [
            {"candidate_id": "candidate_01", "overall_score": 0.78},
            {"candidate_id": "candidate_02", "overall_score": 0.74},
            {"candidate_id": "candidate_04", "overall_score": 0.68},
            {"candidate_id": "candidate_03", "overall_score": 0.64},
        ],
        "candidates": [
            {
                "candidate_id": "candidate_01",
                "overall_score": 0.78,
                "structure_manifest": {
                    "structure_signature": "current_loop+mech_loop:pid",
                    "loop_hierarchy": ["current_loop", "mech_loop"],
                    "control_methods": ["pid"],
                },
                "failed_metrics": [
                    {"name": "overshoot", "status": "error", "value": 0.05},
                ],
                "final_parameters": [
                    {"name": "SPEED_KP", "final_value": 0.62, "initial_value": 0.5, "delta_pct": 24.0},
                    {"name": "CUR_LIMIT", "final_value": 12.0, "initial_value": 10.0, "delta_pct": 20.0},
                ],
                "parameter_history_summary": {
                    "convergence": "improving",
                    "most_adjusted": ["SPEED_KP"],
                    "barely_moved": ["SPEED_KI"],
                },
            }
        ],
        "failed_metrics_summary": [
            {"metric": "overshoot", "failed_in": ["candidate_01"], "failed_count": 1},
        ],
    }
    (r2 / "round_feedback.json").write_text(
        json.dumps(r2_fb, ensure_ascii=False), encoding="utf-8"
    )

    # candidate_profiles for round 2
    r2_cp = {
        "round": 2,
        "from_round": 1,
        "profiles": [
            {
                "candidate_id": "candidate_01",
                "name": "继承优化方案",
                "structure_bias": "基于 winner 微调",
                "preferred_control_methods": ["pid"],
                "reference_candidates": ["candidate_02"],
                "parameter_seed_policy": {
                    "mode": "inherit_then_perturb",
                    "source_candidate": "candidate_02",
                    "perturbation_direction": "提高 SPEED_KP 约 20%",
                },
                "expected_improvement": {"target_failed_metrics": ["overshoot"]},
            },
            {
                "candidate_id": "candidate_02",
                "name": "精英保留",
                "structure_bias": "与 winner 一致",
                "preferred_control_methods": ["pid"],
                "reference_candidates": ["candidate_02"],
                "parameter_seed_policy": {
                    "mode": "inherit",
                    "source_candidate": "candidate_02",
                    "perturbation_direction": "",
                },
                "expected_improvement": {"target_failed_metrics": []},
            },
        ],
    }
    (r2 / "candidate_profiles.json").write_text(
        json.dumps(r2_cp, ensure_ascii=False), encoding="utf-8"
    )

    # ── 运行 ──────────────────────────────────────────────────────
    from Competition.iteration_summary import generate_iteration_summary

    output = generate_iteration_summary(project_json)
    data = json.loads(output.read_text(encoding="utf-8"))

    errors: list[str] = []

    def check(desc: str, condition: bool, detail: str = "") -> None:
        if not condition:
            errors.append(f"FAIL: {desc} {detail}")
        else:
            print(f"  [OK] {desc}")

    print("=== 基本结构 ===")
    check("schema_version == 1", data["schema_version"] == 1)
    check("total_rounds == 2", data["total_rounds"] == 2)
    check("requirement_satisfied is False", data["requirement_satisfied"] is False)
    check("has_errors is False", data["has_errors"] is False)
    check("errors is empty", len(data["errors"]) == 0)
    check("final_winner is not None", data["final_winner"] == "candidate_01")

    print("\n=== overview ===")
    ov = data["overview"]
    check("best_score_overall == 0.78", ov["best_score_overall"] == 0.78)
    check("score_improvement == 0.06", ov["score_improvement"] == 0.06)
    check("rounds_completed == [1, 2]", ov["rounds_completed"] == [1, 2])
    check("requirement_met_in_round is None", ov["requirement_met_in_round"] is None)
    check("total_candidates_per_round == 2", ov["total_candidates_per_round"] == 2)

    print("\n=== score_progression ===")
    sp = data["score_progression"]
    check("rounds == [1, 2]", sp["rounds"] == [1, 2])
    check("best_scores[0] == 0.72", sp["best_scores"][0] == 0.72)
    check("best_scores[1] == 0.78", sp["best_scores"][1] == 0.78)
    check(
        "arrays length match",
        len(sp["rounds"])
        == len(sp["best_scores"])
        == len(sp["average_scores"])
        == len(sp["worst_scores"])
        == len(sp["best_candidates"]),
        f"got rounds={len(sp['rounds'])} best={len(sp['best_scores'])} avg={len(sp['average_scores'])} worst={len(sp['worst_scores'])} cands={len(sp['best_candidates'])}",
    )

    print("\n=== rounds ===")
    for r in data["rounds"]:
        check(f"round {r['round']} has scoreboard", len(r["scoreboard"]) > 0)
        check(f"round {r['round']} has candidates", len(r["candidates"]) > 0)
        winner_found = any(c["is_winner"] for c in r["candidates"])
        check(f"round {r['round']} has a winner", winner_found)
        for c in r["candidates"]:
            check(
                f"round {r['round']} {c['candidate_id']} has color",
                "color" in c and c["color"].startswith("#"),
            )

    print("\n=== metric_tracking ===")
    mt = data["metric_tracking"]
    check("metrics list has overshoot", "overshoot" in mt["metrics"])
    check("metrics list has settling_time", "settling_time" in mt["metrics"])
    check(
        "failure_counts[overshoot] length matches rounds",
        len(mt["failure_counts"]["overshoot"]) == len(mt["rounds"]),
    )
    check("overshoot trend is improving", mt["trends"]["overshoot"] == "improving")
    check(
        "settling_time trend is resolved",
        mt["trends"]["settling_time"] == "resolved",
    )

    print("\n=== structure_evolution ===")
    for se in data["structure_evolution"]:
        check(
            f"round {se['round']} has structures",
            len(se["structures"]) > 0,
        )

    print("\n=== parameter_trends ===")
    pt = data["parameter_trends"]
    check("SPEED_KP is tracked", "SPEED_KP" in pt["parameters"])
    check("CUR_LIMIT is tracked", "CUR_LIMIT" in pt["parameters"])
    check(
        "values[SPEED_KP] length matches rounds",
        len(pt["values"]["SPEED_KP"]) == len(pt["rounds"]),
    )
    check(
        "parameter_labels map exists",
        "parameter_labels" in pt and len(pt["parameter_labels"]) == len(pt["parameters"]),
    )

    print("\n=== winner_lineage ===")
    wl = data["winner_lineage"]
    check("round 1 has winner", wl[0]["winner_id"] == "candidate_02")
    check(
        "round 1 winner inherited in round 2",
        len(wl[0]["inherited_by"]) == 2,
        f"got {len(wl[0]['inherited_by'])}",
    )
    check(
        "round 2 winner inherited_by is empty",
        len(wl[1]["inherited_by"]) == 0,
    )
    check(
        "inherit_then_perturb has perturbation",
        wl[0]["inherited_by"][0]["perturbation"] != "",
    )

    print("\n=== 边界条件测试 ===")

    # 测试 1：空 rounds 目录
    tmp2 = Path(tempfile.mkdtemp())
    pj2 = tmp2 / "empty.json"
    pj2.write_text("{}", encoding="utf-8")
    (tmp2 / "rounds").mkdir()
    from Competition.iteration_summary import generate_iteration_summary

    out2 = generate_iteration_summary(pj2)
    d2 = json.loads(out2.read_text(encoding="utf-8"))
    check("empty rounds: total_rounds == 0", d2["total_rounds"] == 0)
    check("empty rounds: has_errors is True", d2["has_errors"] is True)
    check("empty rounds: overview rounds_completed is empty", d2["overview"]["rounds_completed"] == [])
    check("empty rounds: score_progression rounds is empty", d2["score_progression"]["rounds"] == [])
    check("empty rounds: rounds section is empty", len(d2["rounds"]) == 0)

    # 测试 2：单轮数据
    tmp3 = Path(tempfile.mkdtemp())
    pj3 = tmp3 / "single.json"
    pj3.write_text("{}", encoding="utf-8")
    r1d = tmp3 / "rounds" / "round_01"
    r1d.mkdir(parents=True)
    single_fb = {
        "schema_version": 1,
        "round": 1,
        "requirement_satisfied": False,
        "winner": {"candidate_id": "candidate_01", "overall_score": 0.70},
        "scoreboard": [{"candidate_id": "candidate_01", "overall_score": 0.70}],
        "candidates": [
            {
                "candidate_id": "candidate_01",
                "overall_score": 0.70,
                "structure_manifest": {"structure_signature": "test", "control_methods": ["pid"]},
                "failed_metrics": [],
                "final_parameters": [{"name": "SPEED_KP", "final_value": 0.5, "delta_pct": None}],
                "parameter_history_summary": {"convergence": "unknown"},
            }
        ],
        "failed_metrics_summary": [],
    }
    (r1d / "round_feedback.json").write_text(
        json.dumps(single_fb, ensure_ascii=False), encoding="utf-8"
    )
    out3 = generate_iteration_summary(pj3)
    d3 = json.loads(out3.read_text(encoding="utf-8"))
    check("single round: total_rounds == 1", d3["total_rounds"] == 1)
    check("single round: score_improvement is None", d3["overview"]["score_improvement"] is None,
           f"got {d3['overview']['score_improvement']}")
    check("single round: parameter_trends empty", len(d3["parameter_trends"]["parameters"]) == 0)
    check("single round: winner_lineage empty inherited_by", len(d3["winner_lineage"][0]["inherited_by"]) == 0)

    # ── 结果汇总 ──────────────────────────────────────────────────
    print()
    if errors:
        print(f"FAIL: {len(errors)} checks failed:")
        for e in errors:
            print(f"  {e}")
        return 1
    else:
        print("ALL OK: all checks passed!")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
