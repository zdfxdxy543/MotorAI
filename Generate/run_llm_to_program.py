"""End-to-end controller generation pipeline.

1) Call the LLM-backed loop-id exporter.
2) Feed the generated loop-ids JSON into the Example-based merge step.
3) Generate `ctl_main.c`, `ctl_main.h`, `paras.generated.h` from the Example templates.
4) Copy `user_main.c` and `user_main.h` from Example/ to the output (static copy, not generated).
5) Seed differentiated initial parameter values based on the candidate design profile (Step 0).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

MOTORAI_ROOT = Path(__file__).resolve().parents[1]
if str(MOTORAI_ROOT) not in sys.path:
    sys.path.insert(0, str(MOTORAI_ROOT))

import controller_loop_id_exporter as loop_exporter
import merge_loop_ids_into_ctl_main as merger
from Competition.parameter_seeder import seed_parameters  # noqa: E402

EXAMPLE_DIR = Path(__file__).with_name("Example")


def candidate_output_paths(candidate_dir: Path) -> tuple[Path, Path, Path, Path]:
    candidate_dir = candidate_dir.expanduser().resolve()
    return (
        candidate_dir / "log" / "generate" / "controller_loop_ids_generated.json",
        candidate_dir / "src" / "ctl_main.c",
        candidate_dir / "src" / "ctl_main.h",
        candidate_dir / "src" / "paras.generated.h",
    )


def main(
    requirement: str,
    loop_ids_output: Path,
    c_output: Path,
    h_output: Path,
    paras_output: Path,
    llm_config: Path,
    temperature: float | None = None,
) -> int:
    for output_path in (loop_ids_output, c_output, h_output, paras_output):
        output_path.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

    print("[1/2] Generating loop-ids via LLM...")
    loop_exporter.export_json(
        loop_ids_output,
        requirement,
        settings_path=llm_config,
        temperature_override=temperature,
    )

    print("[2/2] Generating ctl_main.c, ctl_main.h, paras.generated.h from Example templates...")
    merger.main(
        loop_ids_path=loop_ids_output,
        template_path=EXAMPLE_DIR / "ctl_main.c",
        output_path=c_output,
        header_template_path=EXAMPLE_DIR / "ctl_main.h",
        header_output_path=h_output,
        paras_template_path=EXAMPLE_DIR / "paras.h",
        paras_output_path=paras_output,
    )

    # Copy user_main.c and user_main.h as-is (they are static, not generated).
    # The template versions have mech_ctrl references commented out so they
    # compile correctly regardless of controller mode (PID/LADRC/SMC).
    c_output_dir = c_output.expanduser().resolve().parent
    for name in ("user_main.c", "user_main.h"):
        src = EXAMPLE_DIR / name
        dst = c_output_dir / name
        if src.exists():
            shutil.copy2(src, dst)
            print(f"Copied {dst}")

    # ── Step 0: 差异化参数种子 ──────────────────────────────────────────
    # paras.generated.h 刚由 merger 生成，所有 candidate 此时参数相同。
    # 根据 candidate 的设计方案倾向对初始值做差异化扰动，增强优化多样性。
    _seed_candidate_parameters(paras_output)

    generated_files = f"{loop_ids_output}, {c_output}, {h_output}, {paras_output}"
    print(f"Pipeline completed: {generated_files}")
    return 0


def _seed_candidate_parameters(paras_output: Path) -> None:
    """Post-generate step: perturbs paras.generated.h based on design profile.

    The candidate directory is derived from the paras output path:
        <candidate_dir>/src/paras.generated.h  →  <candidate_dir>
    Design profile and candidate index are read from candidate.json.
    """
    candidate_dir = paras_output.expanduser().resolve().parent.parent
    candidate_json = candidate_dir / "candidate.json"

    profile = None
    candidate_index = 1
    if candidate_json.exists():
        try:
            data = json.loads(candidate_json.read_text(encoding="utf-8-sig"))
            profile = data.get("design_profile")
            candidate_index = int(data.get("candidate_index", 1))
        except Exception:
            pass

    # Fallback: parse index from directory name "candidate_03"
    if candidate_index <= 1 and not profile:
        import re
        match = re.search(r"candidate[_\s]*(\d+)", candidate_dir.name, re.IGNORECASE)
        if match:
            candidate_index = int(match.group(1))

    seed_report_dir = candidate_dir / "log" / "generate"

    try:
        report = seed_parameters(
            paras_output,
            candidate_index=candidate_index,
            profile=profile,
            seed_report_dir=seed_report_dir,
            label=candidate_dir.name,
        )
        updated = report.get("updated_count", 0)
        skipped = report.get("skipped_count", 0)
        print(f"  [seed] parameter seeding complete: {updated} updated, {skipped} skipped")
        for p in report.get("parameters", []):
            if p.get("skipped"):
                continue
            old_v = p.get("old_value")
            new_v = p.get("new_value")
            mult = p.get("multiplier", 0)
            if isinstance(old_v, float):
                old_v = round(old_v, 4)
            if isinstance(new_v, float):
                new_v = round(new_v, 4)
            print(f"    {p['name']}: {old_v} -> {new_v}  (x{mult:.3f}, {p['category']})")
    except Exception as exc:
        print(f"  [seed] warning: parameter seeding failed ({exc}), keeping defaults")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LLM loop-id generation and then program generation.")
    parser.add_argument("requirement", nargs="?", default="需要设计高性能位置控制器")
    parser.add_argument(
        "--candidate-dir",
        type=Path,
        help=(
            "Candidate workspace root. When provided, default outputs are "
            "candidate/log/generate/controller_loop_ids_generated.json and "
            "candidate/src/ctl_main.c|ctl_main.h|paras.generated.h."
        ),
    )
    parser.add_argument("--loop-ids-output", type=Path)
    parser.add_argument("--c-output", type=Path)
    parser.add_argument("--h-output", type=Path)
    parser.add_argument("--paras-output", type=Path)
    parser.add_argument("--llm-config", type=Path, default=MOTORAI_ROOT / "motorai_settings.json")
    parser.add_argument("--temperature", type=float, help="Override loop-selection LLM temperature for this run.")
    args = parser.parse_args()

    if args.candidate_dir:
        default_loop_ids, default_c, default_h, default_paras = candidate_output_paths(args.candidate_dir)
    else:
        default_loop_ids = Path(__file__).with_name("controller_loop_ids_generated.json")
        default_c = Path(__file__).with_name("ctl_main.generated.c")
        default_h = Path(__file__).with_name("ctl_main.generated.h")
        default_paras = Path(__file__).with_name("paras.generated.h")

    raise SystemExit(
        main(
            args.requirement,
            args.loop_ids_output or default_loop_ids,
            args.c_output or default_c,
            args.h_output or default_h,
            args.paras_output or default_paras,
            args.llm_config,
            args.temperature,
        )
    )
