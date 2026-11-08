// Workspace metadata is independent of immutable text revisions and ingestion jobs.
CREATE CONSTRAINT topic_id_unique IF NOT EXISTS FOR (t:Topic) REQUIRE (t.workspace_id, t.topic_id) IS UNIQUE;
CREATE CONSTRAINT topic_name_unique IF NOT EXISTS FOR (t:Topic) REQUIRE (t.workspace_id, t.normalized_name) IS UNIQUE;
CREATE INDEX note_topic_lookup IF NOT EXISTS FOR (n:Note) ON (n.workspace_id, n.topic_id);
MATCH (w:Workspace) SET w.metadata_version = coalesce(w.metadata_version, 0);
