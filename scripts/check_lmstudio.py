"""Recorded probes share the application's configuration and inference slot."""

from notes_graphrag.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["probe", "--record", "--report", "reports/probe.json"]))
