export type Job = {
  job_id: string;
  status: string;
  stage: string | null;
  chunks_done: number;
  chunks_total: number;
  error_code: string | null;
};
export type Note = {
  note_id: string;
  title: string;
  created_at: string;
  updated_at: string | null;
  topic_id: string | null;
  metadata_version: number;
  state: "ready" | "processing" | "failed" | "failed_update";
  active_revision_id: string | null;
  desired_revision_id: string;
  pending_revision_id: string | null;
  job: Job | null;
};
export type Topic = {
  topic_id: string;
  name: string;
  color_key: string;
  version: number;
  note_count: number;
};
export type SharedEdge = {
  id: string;
  source: string;
  target: string;
  kind: "shared_entity";
  entities: { entity_id: string; name: string }[];
};
export type MapData = {
  nodes: Note[];
  topics: Topic[];
  edges: SharedEdge[];
  entities?: { id: string; label: string }[];
  relations?: ClaimEdge[];
  relations_limited?: boolean;
  total: number;
  limited: boolean;
  edges_limited: boolean;
  next_cursor: string | null;
  graph_version: number;
  metadata_version: number;
  similarity_available: boolean;
};
export type NotePage = {
  items: Note[];
  next_cursor: string | null;
  total: number;
};
export type Revision = {
  note_id: string;
  revision_id: string;
  title: string;
  text: string;
  offset_unit: string;
  status: string;
};
export type Evidence = {
  note_id: string;
  revision_id: string;
  title: string;
  quote: string;
  start_char: number;
  end_char: number;
  evidence_id?: string;
};
export type ClaimEdge = {
  id: string;
  source: string;
  target: string;
  predicate: string;
  polarity: string;
  modality: string;
  evidence: Evidence;
};
export type ClaimGraph = {
  nodes: { id: string; label: string }[];
  edges: ClaimEdge[];
  limited?: boolean;
};
export type Answer = {
  status: string;
  answer: string;
  citations: Evidence[];
  missing_information: string[];
  graph: ClaimGraph;
  diagnostics: Record<string, unknown>;
};
export type SearchResult = {
  kind: "note" | "entity" | "topic";
  id: string;
  label: string;
  snippet: string;
  topic_id?: string | null;
};
export type SystemStatus = {
  mode: string;
  graph_version: number;
  worker: { fresh: boolean };
  inference_slot: { state: string };
  lm_studio: Record<string, unknown>;
  models: Record<string, string>;
};
