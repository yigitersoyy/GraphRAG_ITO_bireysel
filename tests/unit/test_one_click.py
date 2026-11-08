import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from scripts import one_click, runtime

from notes_graphrag.core.config import Settings
from notes_graphrag.core.process_lock import process_lock


def settings(**kwargs):
    return Settings(
        _env_file=None,
        extraction_model="qwen/qwen3.5-9b",
        answer_model="qwen/qwen3.5-9b",
        embedding_model="graphrag-embed",
        **kwargs,
    )


def models():
    return [
        {
            "path": path,
            "modelKey": alias
            if alias != "graphrag-embed"
            else "text-embedding-nomic-embed-text-v1.5",
            "type": "embedding" if alias == "graphrag-embed" else "llm",
            "identifier": alias,
            "contextLength": 8192,
        }
        for alias, path in one_click.DEFAULT_MODELS.items()
    ]


@pytest.mark.parametrize("warm", [True, False])
def test_model_startup_reuses_aliases_or_loads_exact_local_files(monkeypatch, warm):
    calls = []

    def command(args, *a, **kw):
        calls.append(args)
        if "ls" in args:
            return json.dumps(models())
        if "ps" in args:
            return json.dumps(models() if warm else [])
        if "status" in args:
            return json.dumps({"running": warm, "port": 1234})
        return "{}"

    monkeypatch.setattr(one_click, "command", command)
    one_click.ensure_models("lms", settings(), {})
    loads = [a for a in calls if "load" in a]
    assert len(loads) == (0 if warm else 2)
    assert not any("unload" in a or "get" in a for a in calls)
    if not warm:
        assert loads[0][2] == "qwen/qwen3.5-9b"
        assert "8192" in loads[0] and "--parallel" in loads[0]
        assert "off" in loads[1]
        assert ["lms", "server", "start", "--port", "1234", "--bind", "127.0.0.1"] in calls


@pytest.mark.parametrize("case", ["missing", "ambiguous", "wrong_alias", "wrong_context"])
def test_wrong_models_fail_without_unloading_or_downloading(monkeypatch, case):
    catalog = models()
    loaded = models()
    calls = []
    if case == "missing":
        catalog = []
    if case == "ambiguous":
        catalog += catalog
    if case == "wrong_alias":
        loaded[0]["path"] = "another-model"
    if case == "wrong_context":
        loaded[0]["contextLength"] = 1024

    def command(args, *a, **kw):
        calls.append(args)
        return json.dumps(catalog if "ls" in args else loaded if "ps" in args else {})

    monkeypatch.setattr(one_click, "command", command)
    with pytest.raises(RuntimeError):
        one_click.ensure_models("lms", settings(), {})
    assert not any("unload" in a or "get" in a or "load" in a for a in calls)


def test_remote_models_do_not_start_local_services(monkeypatch):
    def unexpected(*a, **kw):
        pytest.fail("Must validate local endpoint before commands")

    monkeypatch.setattr(one_click, "command", unexpected)
    with pytest.raises(RuntimeError, match="bilgisayardaki"):
        one_click.ensure_models("lms", settings(llm_base_url="http://remote.example/v1"), {})


def test_docker_ready_is_reused(monkeypatch):
    monkeypatch.setattr(one_click, "command", lambda *a, **kw: "linux\n")
    monkeypatch.setattr(one_click, "start_hidden", lambda *a: pytest.fail("Already running"))
    one_click.ensure_docker("docker", {})


def test_docker_readiness_timeout_is_retried_but_required_command_fails(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("docker", 10)

    monkeypatch.setattr(one_click.subprocess, "run", timeout)
    assert one_click.command(["docker", "info"], required=False) == ""
    with pytest.raises(RuntimeError, match="zamanında"):
        one_click.command(["docker", "info"])


def test_stopped_docker_starts_installed_desktop_and_waits(tmp_path, monkeypatch):
    desktop = tmp_path / "Docker Desktop.exe"
    desktop.touch()
    replies = iter(["", "", "linux"])
    started = []
    monkeypatch.setattr(one_click, "command", lambda *a, **kw: next(replies))
    monkeypatch.setattr(one_click, "start_hidden", lambda path: started.append(path))
    monkeypatch.setattr(one_click.time, "sleep", lambda _: None)
    one_click.ensure_docker(str(tmp_path / "resources/bin/docker.exe"), {})
    assert started == [desktop]


def test_leftover_lock_and_crash_recovery(tmp_path):
    path = tmp_path / "manager.lock"
    path.write_text("old process id")
    with process_lock(path, "busy"):
        with pytest.raises(RuntimeError, match="busy"):
            with process_lock(path, "busy"):
                pass
    code = (
        "import sys; from pathlib import Path; "
        "from notes_graphrag.core.process_lock import process_lock; "
        "lock=process_lock(Path(sys.argv[1]),'busy'); lock.__enter__(); "
        "print('ready',flush=True); sys.stdin.read()"
    )
    child = subprocess.Popen(
        # A Windows venv executable is a launcher: terminating it need not kill its
        # Python child, which owns this lock. Crash the actual interpreter instead.
        [getattr(sys, "_base_executable", sys.executable), "-c", code, str(path)],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src")},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout.readline().strip() == "ready"
        with pytest.raises(RuntimeError):
            with process_lock(path, "busy"):
                pass
    finally:
        child.terminate()
        child.wait(timeout=10)
    with process_lock(path, "busy"):
        pass


def test_saved_stopped_project_resumes_original_ports(tmp_path, monkeypatch):
    saved = {
        "api_port": 28000,
        "ui_port": 28501,
        "tokens": [],
        "ports": {
            "API_PORT": "28000",
            "UI_PORT": "28501",
            "NEO4J_BOLT_PORT": "37687",
            "NEO4J_HTTP_PORT": "37474",
        },
    }
    (tmp_path / "live.json").write_text(json.dumps(saved))
    monkeypatch.setattr(runtime, "STATE", tmp_path)
    calls = []
    monkeypatch.setattr(
        runtime, "wait_http", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("down"))
    )
    monkeypatch.setattr(runtime, "start_persistent", lambda *args: calls.append(args))
    args = argparse.Namespace(
        action="start",
        mode="live",
        build=False,
        api_port=8000,
        ui_port=8501,
        bolt_port=7687,
        neo4j_http_port=7474,
    )
    assert runtime.manage(args) == 0
    assert calls[0][0] == "live" and calls[0][2:] == (28000, 28501)
    assert calls[0][1]["NEO4J_BOLT_PORT"] == "37687"
    assert json.loads((tmp_path / "live.json").read_text()) == saved


@pytest.mark.parametrize("fail", [False, True])
def test_browser_opens_only_after_runtime_ready(tmp_path, monkeypatch, fail):
    (tmp_path / ".env").write_text("")
    state = tmp_path / "state"
    state.mkdir()
    (state / "live.json").write_text(json.dumps({"ui_port": 28501}))
    monkeypatch.setattr(one_click, "ROOT", tmp_path)
    monkeypatch.setattr(one_click, "STATE", state)
    monkeypatch.setattr(one_click, "WINDOWS", True)
    monkeypatch.setattr(one_click, "executable", lambda name, *a: name)
    calls = []
    monkeypatch.setattr(one_click, "ensure_docker", lambda *a: calls.append("docker"))
    monkeypatch.setattr(one_click, "ensure_models", lambda *a: calls.append("models"))

    def command(*a, **kw):
        calls.append("runtime")
        if fail:
            raise RuntimeError("not ready")
        return ""

    monkeypatch.setattr(one_click, "command", command)
    monkeypatch.setattr(one_click.webbrowser, "open", lambda *a, **kw: calls.append("browser"))
    if fail:
        with pytest.raises(RuntimeError):
            one_click.launch()
        assert calls == ["docker", "models", "runtime"]
    else:
        assert one_click.launch() == "http://127.0.0.1:28501"
        assert calls == ["docker", "models", "runtime", "browser"]
