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

    # ── Step 1: 结构清单 ────────────────────────────────────────────────
    # 从 generate 产物中提取结构化摘要，供后续轮次的 agent 决策使用。
    _write_candidate_manifest(paras_output)

    generated_files = f"{loop_ids_output}, {c_output}, {h_output}, {paras_output}"
    print(f"Pipeline completed: {generated_files}")
    return 0


def _resolve_source_header(candidate_dir: Path, source_id: str) -> Path:
    """解析参数继承的源文件路径，优先使用 rounds 备份中的优化后值。

    generate 阶段 LLM 会先用模板默认值覆写 paras.generated.h，
    如果 source 是同一轮的其他 candidate，此时读到的是模板默认值而非优化值。
    因此优先从 rounds/ 备份中读取上一轮的优化后参数。
    """
    # 直接在 candidates/ 下找（可能已被覆写）
    direct = candidate_dir.parent / source_id / "src" / "paras.generated.h"

    # 查找 rounds/ 备份中的最新版本
    project_root = candidate_dir.parent.parent
    rounds_dir = project_root / "rounds"
    if rounds_dir.is_dir():
        # 按轮次降序排列，找最新备份
        round_dirs = sorted(rounds_dir.glob("round_*"), reverse=True)
        for rd in round_dirs:
            backup = rd / "candidates" / source_id / "src" / "paras.generated.h"
            if backup.exists():
                return backup

    return direct


def _seed_candidate_parameters(paras_output: Path) -> None:
    """Post-generate step: 根据 parameter_seed_policy 初始化参数。

    支持三种模式：
    - inherit：从 source_candidate 的最终参数值原样复制同名参数
    - inherit_then_perturb：先继承，再按 perturbation_direction 描述微调
    - fresh（或无 policy）：走原有的差异化乘性扰动逻辑
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

    if candidate_index <= 1 and not profile:
        import re
        match = re.search(r"candidate[_\s]*(\d+)", candidate_dir.name, re.IGNORECASE)
        if match:
            candidate_index = int(match.group(1))

    seed_report_dir = candidate_dir / "log" / "generate"

    # ── 检查 parameter_seed_policy ──────────────────────────────────────
    seed_policy = None
    if isinstance(profile, dict):
        seed_policy = profile.get("parameter_seed_policy")
    if not isinstance(seed_policy, dict):
        seed_policy = None

    mode = str(seed_policy.get("mode", "") or "").strip() if seed_policy else ""
    source_id = str(seed_policy.get("source_candidate", "") or "").strip() if seed_policy else ""

    if mode in ("inherit", "inherit_then_perturb") and source_id:
        # ── 从 source candidate 继承参数 ──────────────────────────────
        # 优先读备份（rounds/ 下的优化后值），避免读到 LLM 刚生成的模板默认值
        source_header = _resolve_source_header(candidate_dir, source_id)
        try:
            report = _inherit_parameters(
                target_header=paras_output,
                source_header=source_header,
                candidate_index=candidate_index,
                mode=mode,
                perturbation_text=str(seed_policy.get("perturbation_direction", "") or "").strip() if mode == "inherit_then_perturb" else "",
                seed_report_dir=seed_report_dir,
                label=candidate_dir.name,
                source_label=source_id,
            )
            updated = report.get("updated_count", 0)
            inherited = report.get("inherited_count", 0)
            print(f"  [seed] parameter inherit complete: {inherited} inherited, {updated} perturbed (mode={mode}, source={source_id})")
            for p in report.get("parameters", []):
                if p.get("skipped"):
                    continue
                print(f"    {p['name']}: {p.get('old_value')} -> {p.get('new_value')}")
        except Exception as exc:
            print(f"  [seed] warning: parameter inherit failed ({exc}), falling back to fresh")
            _run_default_seeding(paras_output, candidate_index, profile, seed_report_dir, candidate_dir.name)
    else:
        # ── fresh 模式或无 policy：走原有逻辑 ─────────────────────────
        _run_default_seeding(paras_output, candidate_index, profile, seed_report_dir, candidate_dir.name)


def _run_default_seeding(paras_output, candidate_index, profile, seed_report_dir, label):
    """原有的乘性扰动逻辑，用于 fresh 模式或回退。"""
    try:
        report = seed_parameters(
            paras_output,
            candidate_index=candidate_index,
            profile=profile,
            seed_report_dir=seed_report_dir,
            label=label,
        )
        updated = report.get("updated_count", 0)
        skipped = report.get("skipped_count", 0)
        print(f"  [seed] parameter seeding complete: {updated} updated, {skipped} skipped")
        for p in report.get("parameters", []):
            if p.get("skipped"):
                continue
            print(f"    {p['name']}: {p.get('old_value')} -> {p.get('new_value')}  (x{p.get('multiplier', 0):.3f}, {p['category']})")
    except Exception as exc:
        print(f"  [seed] warning: parameter seeding failed ({exc}), keeping defaults")


def _inherit_parameters(
    target_header, source_header, candidate_index, mode,
    perturbation_text, seed_report_dir, label, source_label,
):
    """从 source_header 继承同名参数到 target_header。

    使用 Optimize 的 parameter_header_editor 读写 paras.generated.h。
    perturbation_text 为 LLM 自由文本，用正则提取参数名和百分比。
    """
    from Optimize.agent_optimize.agent_core.parameters.parameter_header_editor import (
        read_tunable_parameters_detailed,
        patch_tunable_parameters,
    )
    import re

    target_params = read_tunable_parameters_detailed(target_header)
    source_params = read_tunable_parameters_detailed(source_header)

    # ── Step 1: 继承同名参数 ──────────────────────────────────────────
    inherited: dict[str, Any] = {}
    for name in target_params:
        if name in source_params:
            inherited[name] = source_params[name].value

    # ── Step 2: inherit_then_perturb 模式，解析扰动方向 ───────────────
    perturbed: dict[str, Any] = {}
    if mode == "inherit_then_perturb" and perturbation_text:
        # 匹配两种语序的扰动描述：
        #   A) "提高 VEL_KP 和 POS_KP 约 20%"（方向词在前）
        #   B) "VEL_KP 提高 10%，SPEED_SLOPE_LIMIT 降低 5%"（参数名在前）
        # 方向词和参数名之间允许出现 "再"、"进一步" 等修饰词。
        _PT_DIR = r'(提高|增加|加大|升高|上调|降低|减少|减小|下调)'
        _PT_NAME_LIST = r'([A-Za-z_][A-Za-z0-9_]*(?:\s*(?:和|、|,)\s*[A-Za-z_][A-Za-z0-9_]*)*)'
        _PT_PCT = r'(?:约|約|大约|大概)?\s*(\d+(?:\.\d+)?)\s*%'
        _PT_FILLER = r'(?:再|进一步|适当|略微|小幅|大幅)?\s*'

        def _apply_perturbation(dir_word, names_text, pct_val):
            """将单条扰动应用到 inherited dict。"""
            for raw_name in re.split(r'\s*(?:和|、|,)\s*', names_text):
                pn = raw_name.strip().upper()
                if not pn or pn not in inherited:
                    continue
                if dir_word in ("提高", "增加", "加大", "升高", "上调"):
                    inherited[pn] = round(inherited[pn] * (1.0 + pct_val), 6)
                else:
                    inherited[pn] = round(inherited[pn] * (1.0 - pct_val), 6)
                perturbed[pn] = inherited[pn]

        # 语序 A：方向词在前 → groups: (direction, names, pct)
        for match in re.finditer(
            rf'{_PT_DIR}\s*{_PT_FILLER}?{_PT_NAME_LIST}\s*{_PT_PCT}',
            perturbation_text,
        ):
            _apply_perturbation(match.group(1), match.group(2), float(match.group(3)) / 100.0)

        # 语序 B：参数名在前 → groups: (names, direction, pct)
        for match in re.finditer(
            rf'{_PT_NAME_LIST}\s*{_PT_FILLER}{_PT_DIR}\s*{_PT_PCT}',
            perturbation_text,
        ):
            _apply_perturbation(match.group(2), match.group(1), float(match.group(3)) / 100.0)

    # ── Step 3: 合并并写入 ────────────────────────────────────────────
    updates = dict(inherited)
    patch_result = patch_tunable_parameters(target_header, updates, backup=True) if updates else {"status": "skipped", "changed": False, "header_path": str(target_header), "updated_parameters": {}}

    # ── Step 4: 报告 ──────────────────────────────────────────────────
    report_params: list[dict[str, Any]] = []
    for name in sorted(target_params.keys()):
        old_v = target_params[name].value
        new_v = updates.get(name, old_v)
        report_params.append({
            "name": name,
            "old_value": old_v,
            "new_value": new_v,
            "inherited": name in inherited,
            "perturbed": name in perturbed,
            "skipped": name not in inherited,
        })

    report = {
        "schema_version": 1,
        "meta": {"label": label, "candidate_index": candidate_index, "mode": mode, "source": source_label},
        "header_path": str(target_header),
        "parameters": report_params,
        "inherited_count": len(inherited),
        "updated_count": len(perturbed),
        "skipped_count": len(target_params) - len(inherited),
        "patch": {"status": patch_result.get("status"), "changed": patch_result.get("changed")},
    }
    if seed_report_dir:
        report_dir = Path(seed_report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "parameter_seed_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["report_path"] = str((report_dir / "parameter_seed_report.json").resolve())
    return report


def _write_candidate_manifest(paras_output: Path) -> None:
    """Post-generate step: write controller_manifest.json from generate artifacts.

    Derives the candidate directory from the paras output path, same as
    _seed_candidate_parameters().
    """
    candidate_dir = paras_output.expanduser().resolve().parent.parent
    try:
        from Competition.controller_manifest import write_controller_manifest  # noqa: E402
        manifest_path = write_controller_manifest(candidate_dir)
        print(f"  [manifest] wrote {manifest_path}")
    except Exception as exc:
        print(f"  [manifest] warning: controller manifest failed ({exc})")


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
