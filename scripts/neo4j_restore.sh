#!/usr/bin/env bash
# Compatibility wrapper: the shared Python implementation refuses destructive restores.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON:-python3}" "$SCRIPT_DIR/neo4j_archive.py" restore \
  --container "${1:?container name}" --directory "${2:?directory}" \
  --database "${NEO4J_DATABASE:-neo4j}"
