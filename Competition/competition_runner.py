from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable


sys.dont_write_bytecode = True

MOTORAI_ROOT = Path(__file__).resolve().parents[1]
OPTIMIZE_AGENT_SCRIPT = MOTORAI_ROOT / "Optimize" / "agent_optimize" / "agent_modified.py"
OPTIMIZE_AGENT_CWD = MOTORAI_ROOT / "Optimize" / "agent_optimize"

if str(MOTORAI_ROOT) not in sys.path:
    sys.path.insert(0, str(MOTORAI_ROOT))

from Competition.candidate_evidence import write_candidate_evidence  # noqa: E402
from Competition.competition_workspace import (  # noqa: E402
    candidate_id,
    candidate_optimize_paths,
    configure_candidate_optimize,
    discover_candidate_dirs,
    generate_candidates,
    init_candidates,
    load_json_object,
    write_common_requirement_snapshot,
    write_json,
)


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def selected_candidate_names(count: int) -> list[str]:
    if count < 1:
        raise ValueError("--candidates must be >= 1")
    return [candidate_id(index) for index in range(1, count + 1)]


def ensure_candidates(project_json: Path, count: int, *, force_init: bool) -> list[Path]:
    project_json = project_json.expanduser().resolve()
    project_root = project_json.parent
    candidates_root = project_root / "candidates"
    names = selected_candidate_names(count)
    missing = [name for name in names if not (candidates_root / name / "candidate.json").exists()]

    if force_init:
        init_candidates(project_json, count, force=True)
    elif missing:
        if candidates_root.exists() and any(candidates_root.iterdir()):
            raise FileNotFoundError(
                "candidate workspace is incomplete. Missing: "
                + ", ".join(missing)
                + ". Re-run with --force-init to recreate candidates."
            )
        init_candidates(project_json, count, force=False)

    return [candidates_root / name for name in names]


def configure_optimize(candidate_dirs: Iterable[Path]) -> list[dict[str, Any]]:
    return [
        configure_candidate_optimize(candidate_dir / "candidate.json")
        for candidate_dir in candidate_dirs
    ]


def build_optimize_command(candidate_dir: Path) -> tuple[list[str], dict[str, str], dict[str, str]]:
    candidate_json = (candidate_dir / "candidate.json").resolve()
    optimize_paths = candidate_optimize_paths(candidate_dir)
    agent_project = optimize_paths["agent_project"].resolve()
    command = [
        sys.executable,
        str(OPTIMIZE_AGENT_SCRIPT),
        "--job-file",
        str(candidate_json),
    ]
    env_overlay = {
        "AGENT_PROJECT_CONFIG": str(agent_project),
        "PYTHONUTF8": "1",
    }
    outputs = {
        "agent_project": str(agent_project),
        "tuning_result": str((candidate_dir / "log" / "optimize" / "tuning_result.json").resolve()),
        "evaluation_result": str((candidate_dir / "log" / "optimize" / "evaluation_result.json").resolve()),
        "simulation_result": str((candidate_dir / "log" / "optimize" / "simulation" / "processed.json").resolve()),
        "optimization_history": str((candidate_dir / "log" / "optimize" / "optimization_history.jsonl").resolve()),
    }
    return command, env_overlay, outputs


def run_optimize_for_candidate(candidate_dir: Path, *, dry_run: bool) -> dict[str, Any]:
    command, env_overlay, outputs = build_optimize_command(candidate_dir)
    candidate_id_value = candidate_dir.name

    if dry_run:
        return {
            "candidate_id": candidate_id_value,
            "status": "dry_run",
            "command": command,
            "cwd": str(OPTIMIZE_AGENT_CWD),
            "env": env_overlay,
            "outputs": outputs,
        }

    log_dir = candidate_dir / "log" / "optimize"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "run_optimize_stdout.txt"
    stderr_path = log_dir / "run_optimize_stderr.txt"

    env = os.environ.copy()
    env.update(env_overlay)
    result = subprocess.run(
        command,
        cwd=str(OPTIMIZE_AGENT_CWD),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stdout_path.write_text(result.stdout or "", encoding="utf-8")
    stderr_path.write_text(result.stderr or "", encoding="utf-8")

    # ── Step 2: 优化证据 ───────────────────────────────────────────────
    # optimize 子进程结束后，从产物中提取指标、参数变化、收敛情况。
    if result.returncode == 0 and not dry_run:
        try:
            evidence_path = write_candidate_evidence(candidate_dir)
            outputs["candidate_evidence"] = str(evidence_path.resolve())
        except Exception:
            pass  # 证据生成失败不阻塞 optimize 流程

    return {
        "candidate_id": candidate_id_value,
        "status": "completed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stdout": str(stdout_path.resolve()),
        "stderr": str(stderr_path.resolve()),
        "outputs": outputs,
    }


def run_optimize(candidate_dirs: Iterable[Path], *, parallel: int, dry_run: bool) -> list[dict[str, Any]]:
    candidate_dir_list = list(candidate_dirs)
    if parallel < 1:
        raise ValueError("--optimize-parallel must be >= 1")

    if parallel == 1:
        return [
            run_optimize_for_candidate(candidate_dir, dry_run=dry_run)
            for candidate_dir in candidate_dir_list
        ]

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {
            executor.submit(run_optimize_for_candidate, candidate_dir, dry_run=dry_run): candidate_dir
            for candidate_dir in candidate_dir_list
        }
        for future in as_completed(futures):
            results.append(future.result())

    return sorted(results, key=lambda item: item.get("candidate_id", ""))


def read_score(candidate_dir: Path) -> dict[str, Any]:
    result_path = candidate_dir / "log" / "optimize" / "tuning_result.json"
    if not result_path.exists():
        return {
            "candidate_id": candidate_dir.name,
            "status": "missing_result",
            "overall_score": None,
            "tuning_result": str(result_path.resolve()),
        }

    try:
        data = load_json_object(result_path)
    except Exception as exc:
        return {
            "candidate_id": candidate_dir.name,
            "status": "invalid_result",
            "overall_score": None,
            "error": f"{type(exc).__name__}: {exc}",
            "tuning_result": str(result_path.resolve()),
        }

    final_evaluation = data.get("final_evaluation") if isinstance(data.get("final_evaluation"), dict) else {}
    score = final_evaluation.get("overall_score")
    try:
        score = None if score is None else float(score)
    except (TypeError, ValueError):
        score = None

    return {
        "candidate_id": candidate_dir.name,
        "status": data.get("status"),
        "stop_reason": data.get("stop_reason"),
        "overall_score": score,
        "metric_error_count": final_evaluation.get("metric_error_count"),
        "metric_ok_count": final_evaluation.get("metric_ok_count"),
        "tuning_result": str(result_path.resolve()),
    }


def choose_winner(scoreboard: list[dict[str, Any]]) -> dict[str, Any] | None:
    scoreable = [
        item
        for item in scoreboard
        if isinstance(item.get("overall_score"), (int, float))
    ]
    if not scoreable:
        return None
    return max(scoreable, key=lambda item: float(item["overall_score"]))


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


def stop_conditions_met(score_item: dict[str, Any], stop_conditions: dict[str, Any]) -> bool:
    if not stop_conditions:
        return False

    checked_any = False

    if "overall_score_min" in stop_conditions:
        checked_any = True
        actual = _safe_float(score_item.get("overall_score"))
        required = _safe_float(stop_conditions.get("overall_score_min"))
        if actual is None or required is None or actual < required:
            return False

    error_key = None
    if "metric_error_count_max" in stop_conditions:
        error_key = "metric_error_count_max"
    elif "max_metric_error_count" in stop_conditions:
        error_key = "max_metric_error_count"
    if error_key:
        checked_any = True
        actual = _safe_int(score_item.get("metric_error_count"))
        allowed = _safe_int(stop_conditions.get(error_key))
        if actual is None or allowed is None or actual > allowed:
            return False

    if "metric_ok_count_min" in stop_conditions:
        checked_any = True
        actual = _safe_int(score_item.get("metric_ok_count"))
        required = _safe_int(stop_conditions.get("metric_ok_count_min"))
        if actual is None or required is None or actual < required:
            return False

    if "status_equals" in stop_conditions:
        checked_any = True
        if str(score_item.get("status")) != str(stop_conditions.get("status_equals")):
            return False

    return checked_any


def build_winner_summary(
    winner: dict[str, Any] | None,
    stop_conditions: dict[str, Any],
) -> dict[str, Any]:
    if winner is None:
        return {
            "winner": None,
            "requirement_satisfied": False,
            "winner_reason": "没有 candidate 产生可评分的 overall_score。",
        }

    satisfied = stop_conditions_met(winner, stop_conditions)
    candidate = winner.get("candidate_id")
    score = winner.get("overall_score")
    if satisfied:
        reason = f"{candidate} 达到停止条件，并且 overall_score={score} 为最高。"
    else:
        reason = f"未达到停止条件，但 {candidate} overall_score={score} 最高。"

    return {
        "winner": winner,
        "requirement_satisfied": satisfied,
        "winner_reason": reason,
    }


def run_competition(
    project_json: Path,
    *,
    candidates: int,
    parallel: int,
    optimize_parallel: int = 1,
    dry_run: bool,
    skip_generate: bool,
    skip_optimize: bool,
    force_init: bool,
    force_next_round: bool = False,
    round_number: int = 1,
) -> dict[str, Any]:
    project_json = project_json.expanduser().resolve()
    project_data = load_json_object(project_json)
    write_common_requirement_snapshot(project_json, project_data)
    stop_conditions = project_data.get("stop_conditions")
    if not isinstance(stop_conditions, dict):
        stop_conditions = {}

    # ── 多轮支持：round > 1 时备份上一轮源码 + 加载本轮 profiles ──
    if round_number > 1:
        import shutil
        project_root = project_json.parent
        prev_round = round_number - 1

        # 备份上一轮源码：candidates/candidate_XX/src → rounds/round_NN/candidates/
        for cdir in sorted((project_root / "candidates").glob("candidate_*")):
            if cdir.is_dir():
                src_dir = cdir / "src"
                if src_dir.is_dir():
                    backup_dir = project_root / "rounds" / f"round_{prev_round:02d}" / "candidates" / cdir.name / "src"
                    backup_dir.parent.mkdir(parents=True, exist_ok=True)
                    if backup_dir.exists():
                        shutil.rmtree(backup_dir)
                    shutil.copytree(src_dir, backup_dir)

        # 用本轮 profiles 覆盖 common，generate 阶段会读取它
        round_profiles = project_root / "rounds" / f"round_{round_number:02d}" / "candidate_profiles.json"
        if round_profiles.exists():
            common_profiles = project_root / "common" / "candidate_profiles.json"
            common_profiles.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(round_profiles, common_profiles)

        skip_generate = False   # 可能换了控制结构，必须重新生成
        force_init = False      # 不重建 candidate 目录

    candidate_dirs = ensure_candidates(project_json, candidates, force_init=force_init)
    optimize_config_results = configure_optimize(candidate_dirs)

    selectors = selected_candidate_names(candidates)
    generate_result: dict[str, Any] | None = None
    if not skip_generate:
        generate_result = generate_candidates(
            project_json,
            selectors,
            parallel=parallel,
            dry_run=dry_run,
        )

    # 检查 generate 是否全部成功；如果有失败，跳过 optimize 并报错
    generate_all_ok = True
    if generate_result and not dry_run:
        gen_results = generate_result.get("results") or []
        for r in gen_results:
            if r.get("status") != "completed":
                generate_all_ok = False
                print(f"[ERROR] {r.get('candidate_id')} generate 失败 (status={r.get('status')})，"
                      f"跳过 optimize。详见 stderr: {r.get('stderr')}", file=sys.stderr)

    optimize_results: list[dict[str, Any]] = []
    if not skip_optimize and generate_all_ok:
        optimize_results = run_optimize(candidate_dirs, parallel=optimize_parallel, dry_run=dry_run)

    # ── Step 3: 轮次反馈 ───────────────────────────────────────────────
    round_feedback_path: str | None = None
    next_round_profiles_path: str | None = None
    if not skip_optimize and not dry_run:
        try:
            from Competition.round_feedback import generate_round_feedback  # noqa: E402
            fb_path = generate_round_feedback(project_json, round_number=round_number)
            round_feedback_path = str(fb_path.resolve())

            # ── Step 4: 下一轮策略生成 ─────────────────────────────
            fb_data = load_json_object(fb_path)
            max_rounds = int(project_data.get("max_rounds") or 0)
            at_limit = max_rounds > 0 and round_number >= max_rounds
            if not at_limit and (force_next_round or not fb_data.get("requirement_satisfied", True)):
                from Competition.next_round_strategy import generate_next_round_strategy  # noqa: E402
                next_count = int(project_data.get("candidate_count", candidates))
                next_result = generate_next_round_strategy(
                    project_json,
                    from_round=round_number,
                    to_round=round_number + 1,
                    candidate_count=next_count,
                )
                next_round_profiles_path = next_result.get("candidate_profiles")
        except Exception:
            pass

    scoreboard = [read_score(candidate_dir) for candidate_dir in candidate_dirs]
    winner = None if dry_run else choose_winner(scoreboard)
    winner_summary = (
        {
            "winner": None,
            "requirement_satisfied": False,
            "winner_reason": "dry-run 不读取真实评分，不选择最终方案。",
        }
        if dry_run
        else build_winner_summary(winner, stop_conditions)
    )

    result = {
        "schema_version": 1,
        "project_json": str(project_json),
        "candidate_count": candidates,
        "parallel": parallel,
        "generate_parallel": parallel,
        "optimize_parallel": optimize_parallel,
        "optimize_execution_mode": "sequential" if optimize_parallel == 1 else "parallel",
        "dry_run": dry_run,
        "skip_generate": skip_generate,
        "skip_optimize": skip_optimize,
        "candidates": [str(path.resolve()) for path in candidate_dirs],
        "optimize_config": optimize_config_results,
        "generate": generate_result,
        "optimize": optimize_results,
        "round_feedback": round_feedback_path,
        "next_round_profiles": next_round_profiles_path,
        "scoreboard": scoreboard,
        "stop_conditions": stop_conditions,
        **winner_summary,
    }

    output_name = "competition_dry_run_result.json" if dry_run else "competition_run_result.json"
    write_json(project_json.parent / output_name, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MotorAI candidate competition from the command line.")
    parser.add_argument("project_json", type=Path)
    parser.add_argument("--candidates", type=int, default=4)
    parser.add_argument(
        "--parallel",
        "---parallel",
        type=int,
        default=2,
        help="Generate-stage parallelism. Kept for backward compatibility with the original command.",
    )
    parser.add_argument(
        "--optimize-parallel",
        type=int,
        default=1,
        help="Optimize/simulation parallelism. Default is 1 so candidates are tuned sequentially.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-generate", action="store_true")
    parser.add_argument("--skip-optimize", action="store_true")
    parser.add_argument("--force-init", action="store_true")
    parser.add_argument("--round", type=int, default=1, help="轮次编号，默认 1")
    parser.add_argument("--force-next-round", action="store_true", help="即使停止条件已满足，也强制生成下一轮策略")
    args = parser.parse_args(argv)

    try:
        result = run_competition(
            args.project_json,
            candidates=args.candidates,
            parallel=args.parallel,
            optimize_parallel=args.optimize_parallel,
            dry_run=args.dry_run,
            skip_generate=args.skip_generate,
            skip_optimize=args.skip_optimize,
            force_init=args.force_init,
            force_next_round=args.force_next_round,
            round_number=args.round,
        )
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
