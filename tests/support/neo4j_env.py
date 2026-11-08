"""Neo4j test environment helpers.

Tests that touch a real database need NEO4J_TEST_URI, NEO4J_TEST_PASSWORD and NEO4J_TEST_WIPE=1.
The wipe clears the target database, so it is never implied: the caller must opt in explicitly.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]


def refuse_live_target(uri: str) -> None:
    """A stopped live worker is not permission to wipe its database."""

    def address(value: str) -> tuple[str | None, int | None]:
        parsed = urlsplit(value)
        host = parsed.hostname
        if host in {"localhost", "127.0.0.1", "::1"}:
            host = "loopback"
        return host, parsed.port or 7687

    protected = []
    env_path = ROOT / ".env"
    if env_path.is_file():
        configured = dotenv_values(env_path).get("NEO4J_URI")
        if configured:
            protected.append(configured)
    state = ROOT / "reports/runtime/live.json"
    if state.is_file():
        saved = json.loads(state.read_text(encoding="utf-8"))
        port = saved.get("ports", {}).get("NEO4J_BOLT_PORT")
        if port:
            protected.append(f"bolt://127.0.0.1:{port}")
    if address(uri) in {address(value) for value in protected}:
        raise RuntimeError(
            "Refusing to wipe a configured live database; use a separate test target"
        )


@dataclass(frozen=True)
class Neo4jTarget:
    uri: str
    user: str
    password: str


def target_or_skip() -> Neo4jTarget:
    uri = os.environ.get("NEO4J_TEST_URI")
    if not uri:
        pytest.skip("NEO4J_TEST_URI not set; Neo4j tests not run")
    if os.environ.get("NEO4J_TEST_WIPE") != "1":
        pytest.skip("set NEO4J_TEST_WIPE=1 to allow clearing the test database")
    refuse_live_target(uri)
    return Neo4jTarget(
        uri=uri,
        user=os.environ.get("NEO4J_TEST_USER", "neo4j"),
        password=os.environ["NEO4J_TEST_PASSWORD"],
    )


def _active_worker_heartbeat(session: Any) -> bool:
    row = session.run(
        "MATCH (w:Workspace) WHERE w.worker_heartbeat IS NOT NULL "
        "RETURN max(w.worker_heartbeat) AS hb"
    ).single()
    if row is None or row["hb"] is None:
        return False
    from datetime import UTC, datetime

    hb = datetime.fromisoformat(row["hb"])
    return (datetime.now(UTC) - hb).total_seconds() < 120


def wipe_and_migrate(driver: Any, database: str, dims: int, directory: Any = None) -> list[int]:
    """Clear the database and apply migrations. Refuses if a worker is actively using it."""
    from notes_graphrag.persistence.migrations import migrate

    with driver.session(database=database) as s:
        if _active_worker_heartbeat(s):
            raise RuntimeError(
                "a worker heartbeat is fresh on this database; stop the running services "
                "before running tests that clear it"
            )
        for row in s.run("SHOW CONSTRAINTS YIELD name RETURN name").data():
            s.run(f"DROP CONSTRAINT `{row['name']}` IF EXISTS").consume()
        for row in s.run("SHOW INDEXES YIELD name, type WHERE type <> 'LOOKUP' RETURN name").data():
            s.run(f"DROP INDEX `{row['name']}` IF EXISTS").consume()
        s.run("MATCH (n) DETACH DELETE n").consume()
    return migrate(driver, database, dims, directory)
