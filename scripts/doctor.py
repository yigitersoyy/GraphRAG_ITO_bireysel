"""Read-only diagnostics. No migrations, model inference, process stops or data deletion."""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import httpx

from notes_graphrag.core.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("demo", "persistent-demo", "live"), default="demo")
    ap.add_argument("--api-base", default="http://127.0.0.1:8000")
    ap.add_argument("--ui-port", type=int, default=8501)
    ap.add_argument("--no-ui", action="store_true")
    ap.add_argument("--neo4j-uri", help="Override the host Neo4j address for custom Compose ports")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    results = []

    def add(name: str, ok: bool, detail: str) -> None:
        results.append({"name": name, "ok": ok, "detail": detail})

    add("python", sys.version_info >= (3, 12), sys.version.split()[0])
    add(
        "env_file",
        args.mode == "demo" or (ROOT / ".env").exists(),
        ".env present" if (ROOT / ".env").exists() else ".env absent (optional for memory demo)",
    )
    try:
        s = Settings(_env_file=ROOT / ".env")
        if args.neo4j_uri:
            s = s.model_copy(update={"neo4j_uri": args.neo4j_uri})
        add("configuration", True, "Settings valid; secret values omitted")
        if args.mode == "live":
            s.require_live_models()
            add("model_ids", True, "Extraction, answer and embedding IDs configured")
        if args.mode != "demo":
            docker = shutil.which("docker")
            run = (
                subprocess.run(
                    [docker, "info", "--format", "{{.ServerVersion}}"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if docker
                else None
            )
            add(
                "docker",
                run is not None and run.returncode == 0,
                "Engine reachable" if run and run.returncode == 0 else "Docker engine unavailable",
            )
            from neo4j import GraphDatabase

            with GraphDatabase.driver(
                s.neo4j_uri,
                auth=(s.neo4j_username, s.neo4j_password.get_secret_value()),
                connection_timeout=5,
            ) as driver:
                driver.verify_connectivity()
                add("neo4j", True, "Database reachable (no writes performed)")
        if args.mode == "live":
            endpoints = [
                ("chat", s.llm_base_url, s.lm_studio_api_key),
                ("embedding", s.embedding_base_url, s.embedding_api_key or s.lm_studio_api_key),
            ]
            for role, url, key in endpoints:
                headers = {"Authorization": f"Bearer {key.get_secret_value()}"} if key else {}
                r = httpx.get(url.rstrip("/") + "/models", headers=headers, timeout=5)
                expected = (
                    [s.embedding_model]
                    if role == "embedding"
                    else [s.extraction_model, s.answer_model]
                )
                ids = {m["id"] for m in r.json().get("data", [])} if r.status_code == 200 else set()
                add(
                    f"{role}_discovery",
                    r.status_code == 200 and all(m in ids for m in expected),
                    "Configured models served"
                    if all(m in ids for m in expected)
                    else "Model missing or endpoint unavailable",
                )
    except Exception as exc:
        # Exception strings may include configuration values or credential-bearing URLs.
        add("dependencies", False, f"{type(exc).__name__}; check .env, Docker and model server")
    for name, path in (
        ("api_live", "/health/live"),
        ("api_ready", "/health/ready"),
        ("worker", "/api/v1/system/status"),
    ):
        try:
            r = httpx.get(args.api_base.rstrip("/") + path, timeout=5)
            ok = r.status_code == 200 and (name != "worker" or r.json()["worker"]["fresh"])
            add(
                name,
                ok,
                f"HTTP {r.status_code}" + ("; heartbeat checked" if name == "worker" else ""),
            )
        except (httpx.HTTPError, ValueError, KeyError):
            add(name, False, "API unavailable or unexpected response")
    with socket.socket() as sock:
        occupied = sock.connect_ex(("127.0.0.1", args.ui_port)) == 0
    try:
        if not args.no_ui:
            r = httpx.get(f"http://127.0.0.1:{args.ui_port}/health/ui", timeout=3)
            add("ui", r.status_code == 200 and r.text.strip() == "ok", "UI health checked")
    except httpx.HTTPError:
        add(
            "ui", False, "Port occupied by another service" if occupied else "Port free; UI stopped"
        )
    print(
        json.dumps(results, indent=2)
        if args.json
        else "\n".join(
            f"[{'ok' if r['ok'] else 'FAIL'}] {r['name']}: {r['detail']}" for r in results
        )
    )
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
