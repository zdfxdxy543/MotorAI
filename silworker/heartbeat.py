"""
UDP heartbeat broadcaster for silworker auto-discovery.

Sends periodic HELLO broadcasts so a Scheduler can discover this worker.
Runs as a daemon thread — zero impact on the main HTTP server.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
import traceback


def list_interfaces() -> list[str]:
    """Return unique local IPv4 addresses on all non-loopback interfaces."""
    ips: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    if not ips:
        ips = ["127.0.0.1"]
    return ips


def pick_interface() -> str:
    """Print local IPs and ask the user to pick one.  Return the chosen IP."""
    ips = list_interfaces()
    if len(ips) == 1:
        print(f"[silworker] 检测到唯一局域网 IP: {ips[0]}")
        return ips[0]

    print("\n检测到以下局域网 IP 地址:")
    for i, ip in enumerate(ips, 1):
        print(f"  [{i}] {ip}")
    while True:
        try:
            raw = input("请选择要使用的网段编号: ").strip()
            idx = int(raw) - 1
            if 0 <= idx < len(ips):
                return ips[idx]
            print(f"无效编号，请输入 1 ~ {len(ips)}")
        except (ValueError, EOFError, KeyboardInterrupt):
            raise SystemExit(0)


def start_heartbeat(
    worker_id: str,
    worker_url: str,
    *,
    scheduler_port: int = 8785,
    interval_sec: int = 30,
) -> threading.Thread:
    """Launch a daemon thread that broadcasts HELLO every *interval_sec* seconds."""

    def _loop() -> None:
        print("[heartbeat] thread started", flush=True)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except OSError:
            pass

        message = f"HELLO {worker_id} {worker_url}".encode("utf-8")
        print(f"[heartbeat] message = {message.decode()}", flush=True)
        first = True

        while True:
            try:
                bytes_sent = sock.sendto(message, ("255.255.255.255", scheduler_port))
                tag = "HELLO (first)" if first else "HELLO"
                first = False
                print(
                    f"[heartbeat] {tag} {worker_id} → 255.255.255.255:{scheduler_port}"
                    f"  ({bytes_sent} bytes)  from {worker_url}",
                    flush=True,
                )
            except OSError as exc:
                print(f"[heartbeat] send error: {exc}", flush=True)
            except Exception as exc:
                traceback.print_exc(file=sys.stderr)
                print(f"[heartbeat] unexpected error: {exc}", flush=True)

            time.sleep(interval_sec)

    t = threading.Thread(target=_loop, daemon=True, name="heartbeat")
    t.start()
    return t
