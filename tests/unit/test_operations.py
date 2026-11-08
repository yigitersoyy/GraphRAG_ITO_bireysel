"""Lifecycle ownership and non-destructive archive safeguards."""

import argparse
import json
import sys
import uuid

import pytest
from scripts import neo4j_archive, runtime


def test_stop_without_ownership_never_calls_docker_or_signals_processes(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "STATE", tmp_path)

    def unexpected(*args, **kwargs):
        pytest.fail("An unowned service must be left alone")

    monkeypatch.setattr(runtime, "compose", unexpected)
    monkeypatch.setattr(runtime, "stop_owned", unexpected)
    assert runtime.manage(argparse.Namespace(action="stop", mode="demo")) == 0


def test_lifecycle_lock_rejects_overlapping_commands(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "STATE", tmp_path)
    with runtime.process_lock(tmp_path / "manager.lock", "active"):
        with pytest.raises(RuntimeError, match="active"):
            runtime.manage(argparse.Namespace(action="stop", mode="demo"))
    assert (tmp_path / "manager.lock").exists()


def test_service_token_cannot_escape_runtime_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "STATE", tmp_path)
    with pytest.raises(ValueError):
        runtime.fresh("../../outside")
    with pytest.raises(ValueError):
        runtime.child(argparse.Namespace(token="../../outside", role="api"))
    token = str(uuid.uuid4())
    (tmp_path / token).mkdir()
    (tmp_path / token / "heartbeat").touch()
    assert runtime.fresh(token)


def test_explicit_environment_wins_over_dotenv(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("NEO4J_PASSWORD=file-value\n")
    monkeypatch.setenv("NEO4J_PASSWORD", "environment-value")
    args = argparse.Namespace(api_port=8001, ui_port=8502, bolt_port=7688, neo4j_http_port=7475)
    assert runtime.environment("live", args)["NEO4J_PASSWORD"] == "environment-value"


def test_restore_refuses_nonempty_target_before_loading(tmp_path, monkeypatch):
    (tmp_path / "neo4j.dump").write_bytes(b"dump")
    calls = []

    def docker(*args, **kwargs):
        calls.append(args)
        if args[0] == "inspect":
            return json.dumps(
                [{"Config": {"Image": "neo4j:5.26-community"}, "State": {"Running": False}}]
            )
        return "/data/databases/neo4j/neostore"

    monkeypatch.setattr(neo4j_archive, "docker", docker)
    monkeypatch.setattr(
        sys, "argv", ["archive", "restore", "--container", "target", "--directory", str(tmp_path)]
    )
    with pytest.raises(SystemExit):
        neo4j_archive.main()
    assert not any("load" in call or "stop" in call for call in calls)
