"""Best-effort host RAM and NVIDIA VRAM sampling, not a model-process memory profiler."""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
import threading
from typing import Any


def host_memory() -> dict[str, int] | None:
    if os.name == "nt":

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong)
                for name in (
                    "total",
                    "available",
                    "page_total",
                    "page_available",
                    "virtual_total",
                    "virtual_available",
                    "extended",
                )
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return {"total_bytes": status.total, "used_bytes": status.total - status.available}
    elif os.path.exists("/proc/meminfo"):
        with open("/proc/meminfo") as source:
            values = {line.split(":")[0]: int(line.split()[1]) * 1024 for line in source}
        return {
            "total_bytes": values["MemTotal"],
            "used_bytes": values["MemTotal"] - values["MemAvailable"],
        }
    return None


class ResourceMonitor:
    def __init__(self, interval: float = 2.0) -> None:
        self.interval = interval
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.peak_ram: int | None = None
        self.peak_vram: float | None = None
        self.gpus: list[str] = []
        self.samples = 0

    def sample(self) -> None:
        memory = host_memory()
        if memory:
            self.peak_ram = max(self.peak_ram or 0, memory["used_bytes"])
        if shutil.which("nvidia-smi"):
            try:
                r = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=name,memory.total,memory.used",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if r.returncode == 0:
                    self.gpus = [line.strip() for line in r.stdout.splitlines() if line.strip()]
                    usage = sum(float(line.rsplit(",", 1)[1]) for line in self.gpus)
                    self.peak_vram = max(self.peak_vram or 0, usage)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass
        self.samples += 1

    def _run(self) -> None:
        while not self.stop.wait(self.interval):
            self.sample()

    def start(self) -> None:
        self.sample()
        self.thread.start()

    def finish(self) -> dict[str, Any]:
        self.stop.set()
        self.thread.join(timeout=5)
        self.sample()
        return {
            "platform": platform.platform(),
            "host_ram": host_memory(),
            "peak_host_ram_used_bytes": self.peak_ram,
            "peak_gpu_memory_used_mib": self.peak_vram,
            "gpu_last_samples": self.gpus,
            "samples": self.samples,
            "sample_interval_seconds": self.interval,
            "scope": "Whole host/GPU usage, includes other applications; sampled peak only",
            "unavailable": [
                name
                for name, value in (("ram", self.peak_ram), ("nvidia_vram", self.peak_vram))
                if value is None
            ],
        }
