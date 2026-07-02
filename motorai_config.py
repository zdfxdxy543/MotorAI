from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any


MOTORAI_ROOT = Path(__file__).resolve().parent
SETTINGS_FILENAME = "motorai_settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "llm": {
        "api_key": "",
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
        "temperature": 0.2,
        "timeout": 180,
    },
    "paths": {
        "gmp_root": "",
        "generate_root": "Generate",
        "optimize_root": "Optimize",
        "output_root": "Output",
    },
    "generate": {
        "max_kb_items": 120,
        "max_control_structure_attempts": 5,
        "max_project4_file_attempts": 5,
        "max_pipeline_attempts": 5,
    },
    "optimize": {
        "config_project": "Optimize/config_project.py",
        "agent_project": "Optimize/agent_optimize/agent_project.json",
        "run_tuning_agent": "Optimize/agent_optimize/run_tuning_agent.bat",
    },
}


def default_settings_path() -> Path:
    override = os.getenv("MOTORAI_SETTINGS_PATH", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return MOTORAI_ROOT / SETTINGS_FILENAME


def _deep_merge(default: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(default)
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings(path: str | Path | None = None) -> dict[str, Any]:
    settings_path = Path(path).expanduser().resolve() if path else default_settings_path()
    if not settings_path.exists():
        return copy.deepcopy(DEFAULT_SETTINGS)

    with open(settings_path, "r", encoding="utf-8-sig") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"MotorAI settings root must be an object: {settings_path}")
    return _deep_merge(DEFAULT_SETTINGS, loaded)


def save_settings(settings: dict[str, Any], path: str | Path | None = None) -> Path:
    settings_path = Path(path).expanduser().resolve() if path else default_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, ensure_ascii=False, indent=2)
    return settings_path


def get_llm_settings(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = settings if isinstance(settings, dict) else load_settings()
    llm = settings.get("llm") if isinstance(settings.get("llm"), dict) else {}
    defaults = DEFAULT_SETTINGS["llm"]
    return {
        "api_key": str(llm.get("api_key", defaults["api_key"]) or "").strip(),
        "model": str(llm.get("model", defaults["model"]) or defaults["model"]).strip(),
        "base_url": str(llm.get("base_url", defaults["base_url"]) or defaults["base_url"]).strip(),
        "temperature": llm.get("temperature", defaults["temperature"]),
        "timeout": llm.get("timeout", defaults["timeout"]),
    }


def resolve_motorai_path(raw_path: str | Path | None, fallback: str | Path) -> Path:
    path = Path(str(raw_path or fallback)).expanduser()
    if not path.is_absolute():
        path = MOTORAI_ROOT / path
    return path.resolve()


def get_gmp_root(settings: dict[str, Any] | None = None) -> str:
    settings = settings if isinstance(settings, dict) else load_settings()
    paths = settings.get("paths") if isinstance(settings.get("paths"), dict) else {}
    return str(paths.get("gmp_root", "") or "").strip()


def get_optimize_root(settings: dict[str, Any] | None = None) -> Path:
    settings = settings if isinstance(settings, dict) else load_settings()
    paths = settings.get("paths") if isinstance(settings.get("paths"), dict) else {}
    return resolve_motorai_path(paths.get("optimize_root"), DEFAULT_SETTINGS["paths"]["optimize_root"])


def get_output_root(settings: dict[str, Any] | None = None) -> Path:
    settings = settings if isinstance(settings, dict) else load_settings()
    paths = settings.get("paths") if isinstance(settings.get("paths"), dict) else {}
    return resolve_motorai_path(paths.get("output_root"), DEFAULT_SETTINGS["paths"]["output_root"])


def normalize_optimize_config(settings: dict[str, Any] | None = None) -> dict[str, str]:
    settings = settings if isinstance(settings, dict) else load_settings()
    optimize = settings.get("optimize") if isinstance(settings.get("optimize"), dict) else {}
    optimize_root = get_optimize_root(settings)
    defaults = DEFAULT_SETTINGS["optimize"]

    return {
        "root": str(optimize_root),
        "config_project": str(resolve_motorai_path(optimize.get("config_project"), defaults["config_project"])),
        "agent_project": str(resolve_motorai_path(optimize.get("agent_project"), defaults["agent_project"])),
        "run_tuning_agent": str(resolve_motorai_path(optimize.get("run_tuning_agent"), defaults["run_tuning_agent"])),
    }
