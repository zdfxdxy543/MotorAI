"""
MotorAI Simulation Scheduler.

Receives UDP heartbeats from silworkers, maintains an available worker pool,
and distributes incoming simulation requests to idle workers via a FIFO queue.

Two listeners:
  - UDP  :8785   heartbeat receiver (WORKER_HELLO broadcasts)
  - HTTP :8786   agent-facing API   (GET /health, POST /submit)
"""

from __future__ import annotations

import json
import queue
import signal
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# ── constants ────────────────────────────────────────────────────────

SCHEDULER_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG: dict[str, Any] = {
    "http_host": "0.0.0.0",
    "http_port": 8786,
    "udp_port": 8785,
    "heartbeat_timeout_sec": 90,     # worker considered dead after this
    "simulation_timeout_sec": 3600,  # max wait for a simulation result
    "max_request_bytes": 5 * 1024 * 1024,
}

# ── config ────────────────────────────────────────────────────────────


def _merge_config(config_path: Path | None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if config_path is None:
        return cfg
    config_path = config_path.expanduser()
    if not config_path.is_absolute():
        config_path = SCHEDULER_DIR / config_path
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            cfg.update(data)
    return cfg


# ── worker pool ───────────────────────────────────────────────────────

class WorkerPool:
    """Thread-safe registry of available workers (discovered via UDP heartbeat)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._workers: dict[str, dict[str, Any]] = {}  # worker_id → {url, last_seen, ...}

    def heartbeat(self, worker_id: str, worker_url: str) -> None:
        with self._lock:
            self._workers[worker_id] = {
                "worker_id": worker_id,
                "url": worker_url.rstrip("/"),
                "last_seen": time.time(),
            }

    def prune(self, timeout_sec: float) -> list[str]:
        """Remove workers that haven't sent a heartbeat within *timeout_sec*."""
        now = time.time()
        stale: list[str] = []
        with self._lock:
            for wid, info in list(self._workers.items()):
                if now - info["last_seen"] > timeout_sec:
                    stale.append(wid)
                    del self._workers[wid]
        return stale

    def idle_workers(self) -> list[dict[str, Any]]:
        """Return all currently-known workers (for health reporting)."""
        with self._lock:
            return list(self._workers.values())

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return dict(self._workers)


# ── task queue ────────────────────────────────────────────────────────

class SimulationTaskQueue:
    """FIFO queue of pending simulation requests.  Each request is a dict
    with keys: job_id, payload (the forwarded simulation body), event (threading.Event),
    and result (filled by the dispatcher)."""

    def __init__(self) -> None:
        self._q: queue.Queue[dict[str, Any]] = queue.Queue()

    def enqueue(self, task: dict[str, Any]) -> None:
        self._q.put(task)

    def dequeue(self, timeout: float | None = None) -> dict[str, Any] | None:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def qsize(self) -> int:
        return self._q.qsize()


# ── dispatcher thread ─────────────────────────────────────────────────

def _dispatcher_loop(
    pool: WorkerPool,
    task_queue: SimulationTaskQueue,
    simulation_timeout_sec: int,
) -> None:
    """Continuously dequeue tasks and forward them to idle workers."""
    QUEUE_WAIT_TIMEOUT = 300  # max seconds to wait for a worker before giving up

    while True:
        task = task_queue.dequeue(timeout=1.0)
        if task is None:
            continue

        dispatched = False
        wait_start = time.time()
        while not dispatched:
            if time.time() - wait_start > QUEUE_WAIT_TIMEOUT:
                task["result"] = {
                    "ok": False,
                    "error": f"No workers available after {QUEUE_WAIT_TIMEOUT}s. "
                             f"Check that at least one worker is running and broadcasting heartbeats.",
                }
                dispatched = True
                break

            workers = pool.idle_workers()
            if not workers:
                time.sleep(2)
                continue

            for worker in workers:
                worker_url = worker["url"]
                try:
                    _http_get(f"{worker_url}/health", timeout=3)
                except Exception:
                    continue

                try:
                    result = _http_post(
                        f"{worker_url}/run_simulation",
                        task["payload"],
                        timeout=simulation_timeout_sec,
                    )
                    task["result"] = result
                    dispatched = True
                    break
                except Exception as exc:
                    print(
                        f"[scheduler] worker {worker_url} failed: {exc}. "
                        f"Retrying with next worker for job {task['job_id']}."
                    )
                    continue

            if not dispatched:
                time.sleep(2)

        task["event"].set()


# ── UDP heartbeat listener ────────────────────────────────────────────

def _udp_listener(pool: WorkerPool, udp_port: int) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", udp_port))
    sock.settimeout(2.0)
    print(f"[scheduler] UDP heartbeat listener on port {udp_port}")

    # Also allow broadcast reception on Windows
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except OSError:
        pass

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            text = data.decode("utf-8", errors="replace").strip()
            # Expected format:  HELLO <worker_id> <worker_url>
            parts = text.split()
            if len(parts) >= 3 and parts[0].upper() == "HELLO":
                worker_id = parts[1]
                worker_url = parts[2]
                known = worker_id in pool.snapshot()
                pool.heartbeat(worker_id, worker_url)
                tag = "refresh" if known else "DISCOVERED"
                print(f"[scheduler] {tag} worker {worker_id} @ {worker_url}")
        except socket.timeout:
            pass
        except OSError:
            continue


def _prune_loop(pool: WorkerPool, timeout_sec: int) -> None:
    while True:
        time.sleep(15)
        stale = pool.prune(timeout_sec)
        for wid in stale:
            print(f"[scheduler] worker timed out: {wid}")


# ── HTTP helpers ──────────────────────────────────────────────────────

def _http_get(url: str, timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8-sig"))


def _http_post(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8-sig"))


# ── HTTP handler ──────────────────────────────────────────────────────

def _make_handler(
    pool: WorkerPool,
    task_queue: SimulationTaskQueue,
    simulation_timeout_sec: int,
    max_request_bytes: int,
) -> type[BaseHTTPRequestHandler]:
    class SchedulerHandler(BaseHTTPRequestHandler):
        server_version = "MotorAI-Scheduler/1.0"

        def log_message(self, fmt: str, *args: Any) -> None:
            sys.stderr.write(
                "%s - - [%s] %s\n"
                % (self.client_address[0], self.log_date_time_string(), fmt % args)
            )

        # -- GET /health -------------------------------------------------
        def do_GET(self) -> None:
            if self.path.rstrip("/") != "/health":
                self._json(404, {"ok": False, "error": "not found"})
                return
            workers = pool.idle_workers()
            self._json(
                200,
                {
                    "ok": True,
                    "scheduler": "MotorAI-Scheduler/1.0",
                    "workers": len(workers),
                    "worker_list": [
                        {"worker_id": w["worker_id"], "url": w["url"], "age_sec": round(time.time() - w["last_seen"], 1)}
                        for w in workers
                    ],
                    "queue_depth": task_queue.qsize(),
                },
            )

        # -- POST /submit ------------------------------------------------
        def do_POST(self) -> None:
            if self.path.rstrip("/") != "/submit":
                self._json(404, {"ok": False, "error": "not found"})
                return

            try:
                body = self._read_body()
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(400, {"ok": False, "error": str(exc)})
                return

            job_id = body.get("job_id") or f"job_{uuid.uuid4().hex[:12]}"
            candidate_id = body.get("candidate_id") or ""

            event = threading.Event()
            task: dict[str, Any] = {
                "job_id": job_id,
                "candidate_id": candidate_id,
                "payload": body,
                "event": event,
                "result": None,
            }
            task_queue.enqueue(task)

            print(
                f"[scheduler] queued {job_id} ({candidate_id}), "
                f"queue_depth={task_queue.qsize()}"
            )

            # Block until dispatched or timeout
            if not event.wait(timeout=simulation_timeout_sec):
                self._json(
                    504,
                    {
                        "ok": False,
                        "job_id": job_id,
                        "error": "simulation timed out in scheduler queue",
                    },
                )
                return

            result = task.get("result")
            if result is None:
                self._json(
                    500,
                    {
                        "ok": False,
                        "job_id": job_id,
                        "error": "simulation completed but no result returned",
                    },
                )
                return

            self._json(200, result)

        # -- helpers -----------------------------------------------------
        def _read_body(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            if content_length <= 0:
                raise ValueError("empty request body")
            if content_length > max_request_bytes:
                raise ValueError(f"request body too large: {content_length}")
            raw = self.rfile.read(content_length)
            data = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(data, dict):
                raise ValueError("JSON root must be an object")
            return data

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return SchedulerHandler


# ── main ──────────────────────────────────────────────────────────────

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="MotorAI Simulation Scheduler")
    parser.add_argument("--config", type=Path, default=SCHEDULER_DIR / "scheduler_config.json")
    args = parser.parse_args()

    cfg = _merge_config(args.config)
    http_host = str(cfg["http_host"])
    http_port = int(cfg["http_port"])
    udp_port = int(cfg["udp_port"])
    heartbeat_timeout = int(cfg["heartbeat_timeout_sec"])
    sim_timeout = int(cfg["simulation_timeout_sec"])
    max_body = int(cfg["max_request_bytes"])

    pool = WorkerPool()
    task_queue = SimulationTaskQueue()

    # -- background threads --
    threading.Thread(target=_udp_listener, args=(pool, udp_port), daemon=True).start()
    threading.Thread(target=_prune_loop, args=(pool, heartbeat_timeout), daemon=True).start()
    threading.Thread(
        target=_dispatcher_loop, args=(pool, task_queue, sim_timeout), daemon=True
    ).start()

    # -- HTTP server --
    handler_cls = _make_handler(pool, task_queue, sim_timeout, max_body)
    server = ThreadingHTTPServer((http_host, http_port), handler_cls)

    print(f"[scheduler] worker pool heartbeat timeout = {heartbeat_timeout}s")
    print(f"[scheduler] UDP heartbeat listener on :{udp_port}")
    print(f"[scheduler] HTTP API on http://{http_host}:{http_port}")
    print("[scheduler] endpoints: GET /health   POST /submit")

    def _shutdown(signum, frame):
        print("\n[scheduler] shutting down")
        server.shutdown()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
