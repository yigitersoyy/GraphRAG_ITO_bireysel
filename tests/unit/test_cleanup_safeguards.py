import json
import subprocess
import sys

import pytest
from scripts import neo4j_archive
from tests.support import neo4j_env

from notes_graphrag.retrieval.vector import cosine


def test_live_target_is_protected_even_when_no_worker_is_running(tmp_path, monkeypatch):
    monkeypatch.setattr(neo4j_env, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("NEO4J_URI=bolt://localhost:7687\n")
    state = tmp_path / "reports/runtime"
    state.mkdir(parents=True)
    (state / "live.json").write_text(json.dumps({"ports": {"NEO4J_BOLT_PORT": "37687"}}))
    for uri in ["bolt://127.0.0.1:7687", "bolt://localhost:37687"]:
        with pytest.raises(RuntimeError, match="live database"):
            neo4j_env.refuse_live_target(uri)
    neo4j_env.refuse_live_target("bolt://127.0.0.1:27687")


@pytest.mark.parametrize(
    "a,b,expected",
    [([0, 0], [1, 2], 0), ([1], [1, 2], 0), ([1, 2], [2, 4], 1), ([1, 0], [-1, 0], -1)],
)
def test_shared_cosine_preserves_scoring_boundaries(a, b, expected):
    assert cosine(a, b) == pytest.approx(expected)


def test_backup_refuses_unwritable_directory_before_stopping_source(tmp_path, monkeypatch):
    calls = []

    def docker(*args, **kwargs):
        calls.append(args)
        if args[0] == "inspect":
            return json.dumps(
                [{"Config": {"Image": "neo4j:5.26-community"}, "State": {"Running": True}}]
            )
        raise subprocess.CalledProcessError(1, "docker")

    monkeypatch.setattr(neo4j_archive, "docker", docker)
    monkeypatch.setattr(
        sys, "argv", ["archive", "backup", "--container", "source", "--directory", str(tmp_path)]
    )
    with pytest.raises(RuntimeError, match="writable"):
        neo4j_archive.main()
    assert not any(c[0] == "stop" for c in calls)


def test_dump_failure_restarts_previously_running_source(tmp_path, monkeypatch):
    calls = []

    def docker(*args, **kwargs):
        calls.append(args)
        if args[0] == "inspect":
            return json.dumps(
                [{"Config": {"Image": "neo4j:5.26-community"}, "State": {"Running": True}}]
            )
        if "dump" in args:
            raise subprocess.CalledProcessError(1, "docker")
        return ""

    monkeypatch.setattr(neo4j_archive, "docker", docker)
    monkeypatch.setattr(
        sys, "argv", ["archive", "backup", "--container", "source", "--directory", str(tmp_path)]
    )
    with pytest.raises(subprocess.CalledProcessError):
        neo4j_archive.main()
    assert ("stop", "source") in calls
    assert calls[-1] == ("start", "source")
