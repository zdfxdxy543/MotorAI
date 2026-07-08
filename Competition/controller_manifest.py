from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


KNOWN_CONTROL_METHODS = {
    "pid",
    "pi",
    "pd",
    "p",
    "mit",
    "smc",
    "ladrc",
    "adrc",
    "feedforward",
    "gain_scheduling",
    "disturbance_observer",
    "filtering",
    "ramp_limit",
}


DEFINE_RE = re.compile(
    r"^\s*#define\s+([A-Za-z_][A-Za-z0-9_]*)\s+(.+?)(?:\s*/[/*].*)?$"
)


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, dict) else {}


def _candidate_relative(candidate_dir: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(candidate_dir.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _loop_hierarchy(selected_loops: list[Any]) -> list[str]:
    names: list[str] = []
    for loop in selected_loops:
        if not isinstance(loop, dict):
            continue
        name = str(loop.get("name", "") or "").strip()
        if name:
            names.append(name)
    return names


def _control_methods(selected_loops: list[Any]) -> list[str]:
    methods: list[str] = []
    seen: set[str] = set()
    for loop in selected_loops:
        if not isinstance(loop, dict):
            continue
        properties = loop.get("properties") or []
        if not isinstance(properties, list):
            continue
        for value in properties:
            method = str(value or "").strip().lower()
            if method in KNOWN_CONTROL_METHODS and method not in seen:
                seen.add(method)
                methods.append(method)
    return methods


def _structure_signature(loop_hierarchy: list[str], control_methods: list[str]) -> str:
    loops = "+".join(loop_hierarchy) if loop_hierarchy else "no_loop"
    methods = "+".join(control_methods) if control_methods else "no_method"
    return f"{loops}:{methods}"


def _guess_parameter_loop(name: str) -> str | None:
    upper = name.upper()
    if upper.startswith(("CUR_", "CURRENT_", "ID_", "IQ_")):
        return "current_loop"
    if upper.startswith(("VEL_", "SPEED_", "SPD_")):
        return "mech_loop"
    if upper.startswith(("POS_", "POSITION_")):
        return "position_loop"
    if "CUR" in upper or "CURRENT" in upper:
        return "current_loop"
    if "VEL" in upper or "SPEED" in upper or "SPD" in upper:
        return "mech_loop"
    if "POS" in upper or "POSITION" in upper:
        return "position_loop"
    return None


def _guess_parameter_role(name: str) -> str | None:
    upper = name.upper()
    for role in ("KP", "KI", "KD", "KFF"):
        if upper == role or upper.endswith(f"_{role}") or f"_{role}_" in upper:
            return role.lower()
    if "LIMIT" in upper:
        return "limit"
    if "SLOPE" in upper or "RAMP" in upper:
        return "ramp"
    return None


def parse_tunable_parameters(paras_header: Path) -> list[dict[str, Any]]:
    if not paras_header.exists() or not paras_header.is_file():
        return []

    parameters: list[dict[str, Any]] = []
    for line_number, line in enumerate(paras_header.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        match = DEFINE_RE.match(line)
        if not match:
            continue
        name = match.group(1)
        value = match.group(2).strip()
        if name.startswith("_"):
            continue
        parameters.append(
            {
                "name": name,
                "raw_value": value,
                "loop": _guess_parameter_loop(name),
                "role": _guess_parameter_role(name),
                "source_line": line_number,
            }
        )
    return parameters


def build_controller_manifest(candidate_dir: Path) -> dict[str, Any]:
    candidate_dir = candidate_dir.expanduser().resolve()
    generate_dir = candidate_dir / "log" / "generate"
    src_dir = candidate_dir / "src"

    design_strategy_path = generate_dir / "design_strategy.json"
    loop_ids_path = generate_dir / "controller_loop_ids_generated.json"
    paras_header_path = src_dir / "paras.generated.h"
    ctl_main_c_path = src_dir / "ctl_main.c"
    ctl_main_h_path = src_dir / "ctl_main.h"

    design_strategy = _load_json_if_exists(design_strategy_path)
    loop_ids = _load_json_if_exists(loop_ids_path)
    selected_loops = loop_ids.get("selected_loops")
    if not isinstance(selected_loops, list):
        selected_loops = []

    loop_hierarchy = _loop_hierarchy(selected_loops)
    control_methods = _control_methods(selected_loops)

    generated_files = {
        "design_strategy": _candidate_relative(candidate_dir, design_strategy_path),
        "loop_ids": _candidate_relative(candidate_dir, loop_ids_path),
        "ctl_main_c": _candidate_relative(candidate_dir, ctl_main_c_path),
        "ctl_main_h": _candidate_relative(candidate_dir, ctl_main_h_path),
        "paras_header": _candidate_relative(candidate_dir, paras_header_path),
    }

    return {
        "schema_version": 1,
        "candidate_id": candidate_dir.name,
        "structure_signature": _structure_signature(loop_hierarchy, control_methods),
        "loop_hierarchy": loop_hierarchy,
        "control_methods": control_methods,
        "selected_loops": selected_loops,
        "tunable_parameters": parse_tunable_parameters(paras_header_path),
        "generation_intent": {
            "base_requirement": design_strategy.get("base_requirement"),
            "generation_requirement": design_strategy.get("generation_requirement"),
            "design_profile": design_strategy.get("design_profile") or {},
        },
        "generated_files": generated_files,
        "source_files_exist": {
            key: (candidate_dir / value).exists()
            for key, value in generated_files.items()
            if not Path(value).is_absolute()
        },
    }


def write_controller_manifest(candidate_dir: Path) -> Path:
    candidate_dir = candidate_dir.expanduser().resolve()
    manifest_path = candidate_dir / "log" / "generate" / "controller_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_controller_manifest(candidate_dir)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path
