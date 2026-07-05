from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def _resolve_config_path(config_dir: Path, raw_path: str) -> Path:
    path = Path(str(raw_path)).expanduser()
    if not path.is_absolute():
        path = config_dir / path
    return path.resolve()


def _load_scope_map(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    data = _load_json(path)
    scope_map: dict[str, list[str]] = {}
    for key, value in data.items():
        if isinstance(value, list):
            scope_map[str(key)] = [str(item) for item in value]
        else:
            scope_map[str(key)] = []
    return scope_map


def _post_json(url: str, payload: dict[str, Any], timeout_sec: int) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            response_body = response.read().decode("utf-8-sig")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8-sig", errors="replace")
        raise RuntimeError(f"worker HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"failed to reach worker: {exc}") from exc

    data = json.loads(response_body)
    if not isinstance(data, dict):
        raise ValueError("worker response JSON root must be an object")
    return data


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def _build_payload(
    *,
    agent_project: dict[str, Any],
    agent_project_path: Path,
    backend: dict[str, Any],
    scope_map: dict[str, list[str]],
) -> dict[str, Any]:
    automation = agent_project.get("automation")
    if not isinstance(automation, dict):
        automation = {}

    project_name = str(agent_project.get("project_name") or "candidate")
    candidate_id = str(backend.get("candidate_id") or project_name.replace("_optimize", ""))
    job_id = str(backend.get("job_id") or f"{candidate_id}_{int(time.time() * 1000)}")

    remote_model_path = (
        backend.get("remote_model_path")
        or backend.get("model_path")
        or automation.get("sim_model_path")
    )
    if not isinstance(remote_model_path, str) or not remote_model_path.strip():
        raise ValueError(
            "remote simulation backend requires remote_model_path "
            "(or model_path / automation.sim_model_path fallback)"
        )

    payload: dict[str, Any] = {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "remote_model_path": remote_model_path,
        "scope_map": scope_map,
        "timeout_sec": int(backend.get("timeout_sec") or automation.get("sim_timeout_sec") or 1800),
        "no_open_ui": bool(backend.get("no_open_ui", False)),
        "agent_project": str(agent_project_path),
    }

    network_keys = (
        "target_address",
        "receive_port",
        "transmit_port",
        "command_recv_port",
        "command_trans_port",
    )
    network_config = {key: backend[key] for key in network_keys if key in backend}
    if network_config:
        payload["network_config"] = network_config

    for key in (
        "session_name",
        "scope_vars",
        "controller_host",
        "port_base",
    ):
        if key in backend:
            payload[key] = backend[key]

    return payload


def run_remote_simulation(agent_project_path: Path) -> dict[str, Any]:
    agent_project_path = agent_project_path.expanduser().resolve()
    agent_project = _load_json(agent_project_path)
    config_dir = agent_project_path.parent
    automation = agent_project.get("automation")
    if not isinstance(automation, dict):
        raise ValueError("agent_project.json missing automation object")

    backend = automation.get("simulation_backend")
    if not isinstance(backend, dict):
        raise ValueError("automation.simulation_backend must be an object for remote simulation")
    mode = str(backend.get("mode") or "local").strip().lower()
    if mode != "remote":
        raise ValueError(f"remote_sil_client only supports mode=remote, got: {mode}")

    worker_url = str(backend.get("worker_url") or "").strip().rstrip("/")
    if not worker_url:
        raise ValueError("automation.simulation_backend.worker_url is required")

    scope_map_path = _resolve_config_path(
        config_dir,
        str(automation.get("scope_map") or "simulation/scope_channel_map.json"),
    )
    processed_path = _resolve_config_path(
        config_dir,
        str(automation.get("simulation_result") or "simulation/processed.json"),
    )
    try:
        processed_path.unlink()
    except FileNotFoundError:
        pass

    scope_map = _load_scope_map(scope_map_path)
    payload = _build_payload(
        agent_project=agent_project,
        agent_project_path=agent_project_path,
        backend=backend,
        scope_map=scope_map,
    )

    request_timeout = int(payload["timeout_sec"]) + int(backend.get("response_timeout_slack_sec") or 60)
    response = _post_json(
        f"{worker_url}/run_simulation",
        payload,
        timeout_sec=request_timeout,
    )

    if not bool(response.get("ok")):
        raise RuntimeError(f"worker returned failure: {json.dumps(response, ensure_ascii=False)}")

    processed_json = response.get("processed_json")
    if not isinstance(processed_json, dict):
        raise ValueError("worker response missing object field: processed_json")

    _atomic_write_json(processed_path, processed_json)
    return {
        "ok": True,
        "worker_url": worker_url,
        "job_id": response.get("job_id") or payload.get("job_id"),
        "candidate_id": response.get("candidate_id") or payload.get("candidate_id"),
        "processed_json_path": str(processed_path),
        "worker_elapsed_sec": response.get("elapsed_sec"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run remote Simulink through a MotorAI SIL worker")
    parser.add_argument("--agent-project", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run_remote_simulation(args.agent_project)
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
