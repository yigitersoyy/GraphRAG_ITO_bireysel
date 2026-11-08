"""Prepare locked Linux/Python 3.12 backend wheels from Windows or Linux."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def uv_command() -> str:
    for candidate in (
        os.environ.get("UV_EXE"),
        shutil.which("uv"),
        str(ROOT / ".tools" / ("Scripts/uv.exe" if os.name == "nt" else "bin/uv")),
    ):
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("uv not found; run scripts/setup.ps1 or install uv")


def main() -> int:
    uv = uv_command()
    # A dedicated runtime directory prevents old Streamlit/dev wheels entering Docker layers.
    wheels = ROOT / "wheelhouse" / "backend"
    wheels.mkdir(parents=True, exist_ok=True)
    for app_wheel in wheels.glob("notes_graphrag-*.whl"):
        app_wheel.unlink()
    filename = "requirements.lock.txt"
    subprocess.run(
        [uv, "export", "--frozen", "--no-hashes", "--no-emit-project", "--no-dev", "-o", filename],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            uv,
            "tool",
            "run",
            "--python",
            "3.12",
            "--from",
            "pip==25.0.1",
            "pip",
            "download",
            "--quiet",
            "-r",
            filename,
            "-d",
            str(wheels),
            "--only-binary=:all:",
            "--python-version",
            "3.12",
            "--implementation",
            "cp",
            "--abi",
            "cp312",
            "--platform",
            "manylinux_2_28_x86_64",
            "--platform",
            "manylinux_2_17_x86_64",
            "--platform",
            "manylinux2014_x86_64",
            "--platform",
            "any",
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([uv, "build", "--wheel", "-o", str(wheels)], cwd=ROOT, check=True)
    print(f"wheelhouse ready: {len(list(wheels.glob('*.whl')))} wheels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
