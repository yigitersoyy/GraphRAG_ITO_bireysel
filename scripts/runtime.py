"""Project-owned service lifecycle. Never kills processes by name or deletes volumes."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from dotenv import dotenv_values

from notes_graphrag.core.process_lock import process_lock

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "reports" / "runtime"
MODES = ("demo", "persistent-demo", "live")


def environment(mode: str, args: argparse.Namespace) -> dict[str, str]:
    env = {**{k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}, **os.environ}
    env.update(
        GRAPHRAG_DEMO="0" if mode == "live" else "1",
        API_PORT=str(args.api_port),
        UI_PORT=str(args.ui_port),
        NEO4J_BOLT_PORT=str(args.bolt_port),
        NEO4J_HTTP_PORT=str(args.neo4j_http_port),
        API_BASE_URL=f"http://127.0.0.1:{args.api_port}",
        PYTHONUTF8="1",
    )
    return env


def compose(mode: str, *args: str, env: dict[str, str]) -> None:
    subprocess.run(
        ["docker", "compose", "-p", f"notes-graphrag-{mode}", *args], cwd=ROOT, env=env, check=True
    )


def available(port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def wait_http(url: str, timeout: float = 60, *, worker: bool = False) -> None:
    deadline = time.monotonic() + timeout
    with httpx.Client(timeout=3) as client:
        while time.monotonic() < deadline:
            try:
                r = client.get(url)
                if r.status_code == 200 and (not worker or r.json()["worker"]["fresh"]):
                    return
            except (httpx.HTTPError, KeyError, ValueError):
                pass
            time.sleep(0.25)
    raise RuntimeError(f"Service did not become ready: {url}; see reports/runtime logs")


def child(args: argparse.Namespace) -> int:
    """A private stop-file controls this supervisor, never an arbitrary PID."""
    if str(uuid.UUID(args.token)) != args.token or args.role not in ("api", "ui"):
        raise ValueError("A child needs a valid ownership token and service role")
    token_dir = STATE / args.token
    heartbeat = token_dir / "heartbeat"
    stop_file = token_dir / "stop"
    env = environment(args.mode, args)
    if args.role == "api":
        command = [
            sys.executable,
            "-m",
            "notes_graphrag.cli",
            "serve",
            "--demo",
            "--store",
            "memory",
            "--embedded-worker",
            "--port",
            str(args.api_port),
        ]
    else:
        command = [
            sys.executable,
            str(ROOT / "scripts/frontend_server.py"),
            "--port",
            str(args.ui_port),
            "--upstream",
            f"http://127.0.0.1:{args.api_port}",
        ]
    process = subprocess.Popen(command, cwd=ROOT, env=env)
    try:
        while process.poll() is None:
            heartbeat.touch()
            if stop_file.exists():
                break
            time.sleep(0.25)
    finally:
        if process.poll() is None:
            if os.name == "nt":
                # Popen still owns this live child's handle. Include its venv launcher children.
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        heartbeat.unlink(missing_ok=True)
    return process.returncode or 0


def fresh(token: str) -> bool:
    # UUID-only paths: metadata cannot request writes outside the runtime directory.
    if str(uuid.UUID(token)) != token:
        raise ValueError("Invalid service ownership token")
    heartbeat = STATE / token / "heartbeat"
    return heartbeat.exists() and time.time() - heartbeat.stat().st_mtime < 5


def stop_owned(tokens: list[str]) -> None:
    for token in tokens:
        if fresh(token):
            (STATE / token / "stop").touch()
    deadline = time.monotonic() + 25
    while any(fresh(t) for t in tokens) and time.monotonic() < deadline:
        time.sleep(0.25)
    if any(fresh(t) for t in tokens):
        raise RuntimeError("An owned service did not stop; inspect its logs")


def launch(role: str, args: argparse.Namespace) -> str:
    token = str(uuid.uuid4())
    (STATE / token).mkdir()
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_child",
        "--role",
        role,
        "--token",
        token,
        "--mode",
        args.mode,
        "--api-port",
        str(args.api_port),
        "--ui-port",
        str(args.ui_port),
    ]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (STATE / f"{args.mode}-{role}.log").open("ab") as output:
        subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=output,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
            start_new_session=os.name != "nt",
        )
    return token


def manage(args: argparse.Namespace) -> int:
    STATE.mkdir(parents=True, exist_ok=True)
    metadata = STATE / f"{args.mode}.json"
    lock_path = STATE / "manager.lock"
    # OS releases the lock after crashes/reboots; a leftover file cannot block startup.
    with process_lock(
        lock_path, "Another lifecycle command is active (reports/runtime/manager.lock)"
    ):
        return _manage_locked(args, metadata)


def _manage_locked(args: argparse.Namespace, metadata: Path) -> int:
    saved = json.loads(metadata.read_text("utf-8")) if metadata.exists() else None
    if args.action == "stop":
        if not saved:
            print("No services managed for this mode; existing processes were left alone.")
            return 0
        stop_owned(saved.get("tokens", []))
        if args.mode != "demo":
            compose(args.mode, "stop", env={**os.environ, **saved["ports"]})
        metadata.unlink(missing_ok=True)
        print("Stopped project services. Data volumes preserved.")
        return 0
    if saved:
        if args.build:
            raise RuntimeError("Stop this mode before rebuilding; existing services preserved")
        if args.mode != "demo":
            try:
                wait_http(f"http://127.0.0.1:{saved['api_port']}/health/ready", 8)
                wait_http(
                    f"http://127.0.0.1:{saved['api_port']}/api/v1/system/status", 8, worker=True
                )
                if saved.get("ui_port"):
                    wait_http(f"http://127.0.0.1:{saved['ui_port']}/_stcore/health", 8)
            except RuntimeError:
                # Saved ownership survives a machine shutdown. Resume this project only.
                env = environment(args.mode, args)
                for key in ("API_PORT", "UI_PORT", "NEO4J_BOLT_PORT", "NEO4J_HTTP_PORT"):
                    env[key] = str(int(saved["ports"][key]))
                start_persistent(args.mode, env, saved["api_port"], saved.get("ui_port"))
            print(f"Ready: http://localhost:{saved.get('ui_port') or saved['api_port']}")
            return 0
        if args.mode != "demo" or all(fresh(t) for t in saved.get("tokens", [])):
            wait_http(f"http://127.0.0.1:{saved['api_port']}/health/ready", 8)
            wait_http(f"http://127.0.0.1:{saved['api_port']}/api/v1/system/status", 8, worker=True)
            if saved.get("ui_port"):
                wait_http(f"http://127.0.0.1:{saved['ui_port']}/_stcore/health", 8)
            print(f"Already running: http://localhost:{saved.get('ui_port') or saved['api_port']}")
            return 0
        stop_owned(saved.get("tokens", []))
        metadata.unlink()
    ports = [args.api_port] + ([] if args.no_ui else [args.ui_port])
    if args.mode != "demo":
        ports += [args.bolt_port, args.neo4j_http_port]
    if len(set(ports)) != len(ports) or any(not 1 <= p <= 65535 for p in ports):
        raise RuntimeError("Service ports must be distinct numbers between 1 and 65535")
    for port in ports:
        if not available(port):
            raise RuntimeError(
                f"Port {port} is occupied. Choose another port; no process was stopped."
            )
    env = environment(args.mode, args)
    tokens: list[str] = []
    # Persist only ports; never persist the environment with its passwords.
    port_env = {k: env[k] for k in ("API_PORT", "UI_PORT", "NEO4J_BOLT_PORT", "NEO4J_HTTP_PORT")}
    record = {
        "api_port": args.api_port,
        "ui_port": None if args.no_ui else args.ui_port,
        "ports": port_env,
        "tokens": tokens,
    }
    if args.mode == "demo":
        if not args.no_ui:
            build_frontend()
        tokens.append(launch("api", args))
        metadata.write_text(json.dumps(record), encoding="utf-8")
        wait_http(f"http://127.0.0.1:{args.api_port}/health/ready")
        if not args.no_ui:
            tokens.append(launch("ui", args))
            metadata.write_text(json.dumps(record), encoding="utf-8")
    else:
        if args.build:
            subprocess.run(
                [sys.executable, str(ROOT / "scripts/build_wheelhouse.py")],
                cwd=ROOT,
                env=env,
                check=True,
            )
            targets = ["api", "worker", "migrate"] + ([] if args.no_ui else ["ui"])
            compose(args.mode, "build", *targets, env=env)
        metadata.write_text(json.dumps(record), encoding="utf-8")
        start_persistent(args.mode, env, args.api_port, record["ui_port"])
    wait_http(f"http://127.0.0.1:{args.api_port}/api/v1/system/status", worker=True)
    if not args.no_ui:
        wait_http(f"http://127.0.0.1:{args.ui_port}/_stcore/health")
    shown_port = args.api_port if args.no_ui else args.ui_port
    print(f"Started {args.mode}: http://localhost:{shown_port}")
    return 0


def start_persistent(mode: str, env: dict[str, str], api_port: int, ui_port: int | None) -> None:
    compose(mode, "up", "-d", "--wait", "neo4j", env=env)
    compose(mode, "run", "--rm", "migrate", env=env)
    if mode == "live":
        compose(mode, "run", "--rm", "api", "probe", "--record", env=env)
    compose(mode, "up", "-d", "api", "worker", *(["ui"] if ui_port else []), env=env)
    wait_http(f"http://127.0.0.1:{api_port}/health/ready", 120)
    wait_http(f"http://127.0.0.1:{api_port}/api/v1/system/status", worker=True)
    if ui_port:
        wait_http(f"http://127.0.0.1:{ui_port}/_stcore/health")


def build_frontend() -> None:
    directory = ROOT / "frontend"
    npm = "npm.cmd" if os.name == "nt" else "npm"
    subprocess.run([npm, "ci", "--no-fund", "--no-audit"], cwd=directory, check=True)
    subprocess.run([npm, "run", "build"], cwd=directory, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "stop", "_child"))
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--ui-port", type=int, default=8501)
    parser.add_argument("--bolt-port", type=int, default=7687)
    parser.add_argument("--neo4j-http-port", type=int, default=7474)
    parser.add_argument("--no-ui", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--role", choices=("api", "ui"))
    parser.add_argument("--token")
    args = parser.parse_args()
    try:
        return child(args) if args.action == "_child" else manage(args)
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
