"""Cross-platform offline backup/restore. Restore requires an empty, stopped target."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def docker(*args: str, capture: bool = False) -> str:
    r = subprocess.run(
        ["docker", *args], check=True, text=True, stdout=subprocess.PIPE if capture else None
    )
    return r.stdout if capture else ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("backup", "restore"))
    ap.add_argument("--container", required=True)
    ap.add_argument("--directory", type=Path, required=True)
    ap.add_argument("--database", default="neo4j")
    args = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.database):
        ap.error("Invalid database name")
    meta = json.loads(docker("inspect", args.container, capture=True))[0]
    image = meta["Config"]["Image"]
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    dump = directory / f"{args.database}.dump"
    running = meta["State"]["Running"]
    if args.action == "backup" and dump.exists():
        ap.error("Dump already exists; use a new backup directory")
    if args.action == "restore":
        if not dump.is_file():
            ap.error("Dump not found")
        if running:
            ap.error(
                "Restore target must be stopped; the source database is never stopped implicitly"
            )
        # No overwrite switch: refuse initialized targets, including another project's data.
        found = docker(
            "run",
            "--rm",
            "--volumes-from",
            args.container + ":ro",
            "--entrypoint",
            "sh",
            image,
            "-c",
            "find /data/databases /data/transactions -mindepth 1 "
            "-type f -print -quit 2>/dev/null || true",
            capture=True,
        )
        if found.strip():
            ap.error("Restore target contains data; create a fresh container/volume")
    if running:
        docker("stop", args.container)
    try:
        operation = "dump" if args.action == "backup" else "load"
        path_arg = "--to-path=/backups" if args.action == "backup" else "--from-path=/backups"
        docker(
            "run",
            "--rm",
            "--volumes-from",
            args.container,
            "--mount",
            f"type=bind,source={directory},target=/backups",
            image,
            "neo4j-admin",
            "database",
            operation,
            args.database,
            path_arg,
        )
    finally:
        if running:
            docker("start", args.container)
    print(f"{args.action} completed: {dump.name}; target={args.container}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
