"""Stage replacement vectors, then apply during an API/worker maintenance window.

The JSON backup contains original vectors and revision fingerprints. Keep it private.
Run using the project's configured container environment and a persistent backup path.
"""

import argparse
import hashlib
import json
from pathlib import Path

from notes_graphrag.api.dependencies import build_gate, build_providers, build_storage
from notes_graphrag.core.config import Settings
from notes_graphrag.ingestion.service import pipeline_fingerprint
from notes_graphrag.providers.gate import GatedEmbeddings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "apply"))
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--previous-fingerprint", required=True)
    args = parser.parse_args()
    settings = Settings()
    store, _, driver = build_storage(settings, "neo4j")
    assert driver is not None

    def query(cypher, **params):
        with driver.session(database=settings.neo4j_database) as session:
            return session.run(cypher, **params).data()

    def chunks():
        return query(
            "MATCH (c:Chunk) RETURN c.workspace_id AS ws, c.chunk_id AS id, "
            "c.text AS text, c.embedding AS embedding ORDER BY ws, id"
        )

    def signature(rows):
        return hashlib.sha256(json.dumps(
            [(r["ws"], r["id"], r["text"], r["embedding"]) for r in rows],
            ensure_ascii=False, sort_keys=True,
        ).encode()).hexdigest()

    try:
        if args.action == "prepare":
            if args.backup.exists():
                raise RuntimeError("Backup already exists; choose a fresh path")
            rows = chunks()
            revisions = query(
                "MATCH (r:NoteRevision) RETURN r.workspace_id AS ws, "
                "r.revision_id AS id, r.fingerprint AS fingerprint"
            )
            data = dict(original=rows, revisions=revisions, signature=signature(rows),
                        replacement=[], profile=settings.embedding_profile,
                        dimensions=settings.embedding_dimensions,
                        fingerprint=pipeline_fingerprint(settings))
            args.backup.parent.mkdir(parents=True, exist_ok=True)
            args.backup.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            providers = build_providers(settings, demo=False)
            try:
                gate = build_gate(settings, store, providers)
                embeddings = GatedEmbeddings(providers.emb, gate, "embedding-migration")
                for offset in range(0, len(rows), 8):
                    batch = rows[offset:offset + 8]
                    vectors = embeddings.embed([
                        settings.embedding_document_prefix + row["text"] for row in batch
                    ])
                    for row, vector in zip(batch, vectors, strict=True):
                        assert len(vector) == settings.embedding_dimensions
                        data["replacement"].append(dict(ws=row["ws"], id=row["id"], vector=vector))
                    if offset % 80 == 0 or offset + 8 >= len(rows):
                        print(f"Embedded {len(data['replacement'])}/{len(rows)}", flush=True)
            finally:
                providers.close()
            args.backup.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            print("Prepared; database unchanged", flush=True)
        else:
            data = json.loads(args.backup.read_text(encoding="utf-8"))
            assert data["profile"] == settings.embedding_profile
            assert data["dimensions"] == settings.embedding_dimensions
            assert len(data["replacement"]) == len(data["original"])
            assert data["signature"] == signature(chunks()), "Database changed; prepare again"
            active = query("MATCH (j:IngestionJob) WHERE j.status IN ['QUEUED','RUNNING'] "
                           "RETURN count(j) AS count")[0]["count"]
            assert active == 0, "Drain jobs and stop API/worker before applying"
            query("DROP INDEX chunk_embedding_v1 IF EXISTS")
            # One transaction keeps all vectors and profile metadata consistent.
            with driver.session(database=settings.neo4j_database) as session:
                with session.begin_transaction() as tx:
                    tx.run("UNWIND $rows AS row MATCH (c:Chunk "
                           "{workspace_id:row.ws, chunk_id:row.id}) "
                           "SET c.embedding=row.vector", rows=data["replacement"]).consume()
                    tx.run("MATCH (r:NoteRevision) WHERE r.fingerprint=$old "
                           "SET r.fingerprint=$new", old=args.previous_fingerprint,
                           new=data["fingerprint"]).consume()
                    tx.run("MATCH (w:Workspace) SET w.graph_version="
                           "coalesce(w.graph_version,0)+1").consume()
                    tx.commit()
            query("CREATE VECTOR INDEX chunk_embedding_v1 FOR (c:Chunk) ON (c.embedding) "
                  "OPTIONS {indexConfig: {`vector.dimensions`: $dims, "
                  "`vector.similarity_function`: 'cosine'}}", dims=settings.embedding_dimensions)
            query("CALL db.awaitIndexes(300)")
            print(f"Applied {len(data['replacement'])} replacement vectors", flush=True)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
