"""Windows one-click launcher using installed Docker, LM Studio and project images."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from dotenv import dotenv_values

from notes_graphrag.core.config import Settings
from notes_graphrag.core.process_lock import process_lock

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "reports" / "runtime"
WINDOWS = sys.platform == "win32"
DEFAULT_MODELS = {
    "qwen/qwen3.5-9b": "qwen/qwen3.5-9b",
    "graphrag-embed": "nomic-ai/nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.Q4_K_M.gguf",
}


def progress(message: str) -> None:
    print(message, flush=True)


def command(args: list[str], timeout: float = 120, *, required: bool = True) -> str:
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        result = subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=flags,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        if not required:
            return ""
        raise RuntimeError("İşlem zamanında tamamlanamadı. Başlatıcıyı yeniden deneyin.") from exc
    with (STATE / "launcher.log").open("a", encoding="utf-8") as log:
        # No environment, credentials, note contents or HTTP request bodies are logged.
        log.write(result.stdout + result.stderr)
    if required and result.returncode:
        raise RuntimeError(
            "Gerekli servis başlatılamadı; reports/runtime/launcher.log dosyasına bakın."
        )
    return result.stdout if not result.returncode else ""


def executable(name: str, fallback: Path) -> str:
    found = shutil.which(name)
    if found:
        return found
    if fallback.is_file():
        return str(fallback)
    raise RuntimeError(f"{name} bulunamadı. Bu bilgisayarda ilk kurulum tamamlanmalı.")


def start_hidden(path: Path) -> None:
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    subprocess.Popen(
        [str(path)],
        cwd=path.parent,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=startup,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def ensure_docker(docker: str, values: dict[str, str]) -> None:
    if command([docker, "info", "--format", "{{.OSType}}"], 10, required=False).strip() == "linux":
        return
    candidates = [
        Path(values.get("LAUNCH_DOCKER_DESKTOP", "__not_configured__")),
        Path(docker).parents[2] / "Docker Desktop.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Docker/Docker/Docker Desktop.exe",
    ]
    desktop = next((p for p in candidates if p.is_file()), None)
    if desktop is None:
        raise RuntimeError(
            "Docker Desktop bulunamadı. Kurulumu ve Linux container modunu kontrol edin."
        )
    start_hidden(desktop)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if (
            command([docker, "info", "--format", "{{.OSType}}"], 10, required=False).strip()
            == "linux"
        ):
            return
        time.sleep(2)
    raise RuntimeError("Docker Linux motoru açılamadı. Docker Desktop hata ekranını kontrol edin.")


def model_for(catalog: list[dict[str, Any]], selector: str, kind: str) -> dict[str, Any]:
    found = [
        m
        for m in catalog
        if selector in (m.get("path"), m.get("indexedModelIdentifier"), m.get("modelKey"))
        and m.get("type") == kind
    ]
    if len(found) != 1:
        raise RuntimeError(
            "Yapılandırılan yerel model bulunamadı veya belirsiz. "
            "LAUNCH_CHAT_MODEL / LAUNCH_EMBED_MODEL ayarlarını kontrol edin. Model indirilmedi."
        )
    # This installed CLI loads by modelKey, not by the catalog's file path.
    # Reject non-unique keys instead of allowing -y to choose another quantization.
    key = found[0].get("modelKey")
    if not key or sum(m.get("modelKey") == key for m in catalog) != 1:
        raise RuntimeError("Yerel model anahtarı belirsiz. LM Studio model listesini kontrol edin.")
    return found[0]


def ensure_models(lms: str, settings: Settings, values: dict[str, str]) -> None:
    settings.require_live_models()
    bases = [urlsplit(settings.llm_base_url), urlsplit(settings.embedding_base_url)]
    if any(u.hostname not in ("127.0.0.1", "localhost") or u.scheme != "http" for u in bases):
        raise RuntimeError("Tek tık başlatıcı bu bilgisayardaki HTTP LM Studio sunucusu içindir.")
    ports = {u.port or 80 for u in bases}
    if len(ports) != 1:
        raise RuntimeError("Tek tık başlatmada sohbet ve embedding aynı LM Studio portunda olmalı.")
    command([lms, "daemon", "up", "--json"], 90)
    catalog = json.loads(command([lms, "ls", "--json"]))
    loaded = json.loads(command([lms, "ps", "--json"]))
    specs = [
        (alias, "llm", "LAUNCH_CHAT_MODEL")
        for alias in dict.fromkeys([settings.extraction_model, settings.answer_model])
    ] + [(settings.embedding_model, "embedding", "LAUNCH_EMBED_MODEL")]
    # Resolve every model before loading anything: no fuzzy match or implicit download.
    resolved = [
        (
            alias,
            kind,
            model_for(catalog, values.get(option) or DEFAULT_MODELS.get(alias, alias), kind),
        )
        for alias, kind, option in specs
    ]
    for alias, kind, model in resolved:
        existing = next((m for m in loaded if m.get("identifier") == alias), None)
        if existing is not None:
            if existing.get("path") != model.get("path") or existing.get("type") != kind:
                raise RuntimeError(
                    "Proje model kimliği başka bir modele bağlı. LM Studio ayarını kontrol edin."
                )
            if kind == "llm" and existing.get("contextLength") != settings.lm_studio_context_tokens:
                raise RuntimeError(
                    "Yüklü sohbet modelinin bağlam uzunluğu proje ayarıyla uyuşmuyor."
                )
            continue
        progress("  Model belleğe yükleniyor: " + alias)
        args = [
            lms,
            "load",
            model["modelKey"],
            "--identifier",
            alias,
            "--gpu",
            values.get("LAUNCH_CHAT_GPU", "0.8") if kind == "llm" else "off",
            "-y",
        ]
        if kind == "llm":
            args += ["--context-length", str(settings.lm_studio_context_tokens), "--parallel", "1"]
        command(args, 240)
    status = json.loads(command([lms, "server", "status", "--json"]))
    port = ports.pop()
    if status.get("running") and status.get("port") != port:
        raise RuntimeError("LM Studio başka portta açık. Projedeki sunucu portuyla eşleştirin.")
    if not status.get("running"):
        command([lms, "server", "start", "--port", str(port), "--bind", "127.0.0.1"])


def launch(*, open_browser: bool = True) -> str:
    if not WINDOWS:
        raise RuntimeError(
            "Bu başlatıcı Windows içindir; diğer sistemlerde scripts/runtime.py kullanın."
        )
    STATE.mkdir(parents=True, exist_ok=True)
    with process_lock(
        STATE / "launcher.lock", "Başlatma zaten devam ediyor; mevcut pencereyi bekleyin."
    ):
        if not (ROOT / ".env").is_file():
            raise RuntimeError("Proje kurulumu bulunamadı. Önce scripts/setup.ps1 çalıştırın.")
        values = {
            **{k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None},
            **os.environ,
        }
        settings = Settings(_env_file=ROOT / ".env")
        docker = executable(
            "docker",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Docker/Docker/resources/bin/docker.exe",
        )
        lms = executable("lms", Path.home() / ".lmstudio/bin/lms.exe")
        os.environ["PATH"] = str(Path(docker).parent) + os.pathsep + os.environ.get("PATH", "")
        progress("[1/3] Docker hazırlanıyor…")
        ensure_docker(docker, values)
        progress("[2/3] Yerel modeller ve LM Studio sunucusu hazırlanıyor…")
        ensure_models(lms, settings, values)
        progress("[3/3] Notlar, belge işleme ve arayüz servisleri hazırlanıyor…")
        command(
            [
                sys.executable,
                str(ROOT / "scripts/runtime.py"),
                "start",
                "--mode",
                "live",
                "--api-port",
                "28000",
                "--ui-port",
                "28501",
                "--bolt-port",
                "37687",
                "--neo4j-http-port",
                "37474",
            ],
            600,
        )
        saved = json.loads((STATE / "live.json").read_text(encoding="utf-8"))
        url = f"http://127.0.0.1:{int(saved['ui_port'])}"
        if open_browser:
            webbrowser.open(url, new=2)
        progress("Hazır: " + url)
        return url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-browser", action="store_true", help="Başlatmayı tarayıcı açmadan doğrula"
    )
    args = parser.parse_args()
    try:
        launch(open_browser=not args.no_browser)
        return 0
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        progress("Başlatılamadı: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
