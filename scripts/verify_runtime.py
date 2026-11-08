"""Exercise start/idempotence/HTTP flow/stop on unused demo ports, including Windows."""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--api-port", type=int, default=18001)
    ap.add_argument("--ui-port", type=int, default=18502)
    args = ap.parse_args()
    command = [sys.executable, "scripts/runtime.py"]
    start = [
        *command,
        "start",
        "--mode",
        "demo",
        "--api-port",
        str(args.api_port),
        "--ui-port",
        str(args.ui_port),
    ]
    # Preflight before taking ownership: never stop a pre-existing managed demo.
    if (ROOT / "reports/runtime/demo.json").exists():
        raise RuntimeError("Stop your managed demo first, or test in an isolated checkout")
    try:
        subprocess.run(start, cwd=ROOT, check=True)
        subprocess.run(start, cwd=ROOT, check=True)
        subprocess.run(
            [
                sys.executable,
                "scripts/smoke.py",
                "--api-base",
                f"http://127.0.0.1:{args.api_port}",
                "--timeout",
                "20",
            ],
            cwd=ROOT,
            check=True,
        )
    finally:
        subprocess.run([*command, "stop", "--mode", "demo"], cwd=ROOT, check=True)
    for port in (args.api_port, args.ui_port):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"Project process still listening on {port}")
    print("Lifecycle verified; test ports released.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
