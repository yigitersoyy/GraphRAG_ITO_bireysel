import type {
  Answer,
  ClaimGraph,
  DeletedNotePage,
  MapData,
  Note,
  NotePage,
  Revision,
  SearchResult,
  SystemStatus,
  Topic,
} from "./types";

export class ApiError extends Error {
  code: string;
  status: number;
  requestId: string;
  constructor(message: string, code: string, status: number, requestId = "") {
    super(message);
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, options);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ApiError(
      "API’ye ulaşılamıyor. Bağlantıyı kontrol edip yeniden dene.",
      "API_UNREACHABLE",
      0,
    );
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (!response.ok)
    throw new ApiError(
      body?.error?.message || "İstek tamamlanamadı.",
      body?.error?.code ||
        (response.status >= 502 ? "API_UNREACHABLE" : "ERROR"),
      response.status,
      body?.request_id || "",
    );
  return body as T;
}
const json = (body: unknown, method = "POST", key?: string): RequestInit => ({
  method,
  headers: {
    "Content-Type": "application/json",
    ...(key ? { "Idempotency-Key": key } : {}),
  },
  body: JSON.stringify(body),
});
export function params(
  values: Record<string, string | number | null | undefined>,
): string {
  return new URLSearchParams(
    Object.entries(values)
      .filter(([, v]) => v != null && v !== "")
      .map(([k, v]) => [k, String(v)]),
  ).toString();
}
export const api = {
  deletedNotes: (cursor?: string, signal?: AbortSignal) =>
    request<DeletedNotePage>(
      "/api/v1/workspace/deleted-notes?" + params({ cursor }),
      { signal },
    ),
  map: (topic?: string, q?: string, cursor?: string) =>
    request<MapData>(
      "/api/v1/workspace/map?" + params({ topic_id: topic, q, cursor }),
    ),
  notes: (topic?: string, q?: string, cursor?: string) =>
    request<NotePage>(
      "/api/v1/workspace/notes?" +
        params({ topic_id: topic, q, cursor, limit: 50 }),
    ),
  note: (id: string) =>
    request<Note>("/api/v1/notes/" + encodeURIComponent(id)),
  revision: (id: string, rid: string) =>
    request<Revision>(
      `/api/v1/notes/${encodeURIComponent(id)}/revisions/${encodeURIComponent(rid)}`,
    ),
  topics: () => request<{ items: Topic[] }>("/api/v1/topics"),
  createTopic: (name: string, color_key: string) =>
    request<Topic>("/api/v1/topics", json({ name, color_key })),
  editTopic: (topic: Topic, name: string, color_key: string) =>
    request<Topic>(
      "/api/v1/topics/" + topic.topic_id,
      json({ name, color_key, expected_version: topic.version }, "PATCH"),
    ),
  deleteTopic: (topic: Topic) =>
    request(
      "/api/v1/topics/" + topic.topic_id + "?expected_version=" + topic.version,
      { method: "DELETE" },
    ),
  assignTopic: (note: Note, topic_id: string | null) =>
    request(
      `/api/v1/notes/${note.note_id}/metadata`,
      json({ topic_id, expected_version: note.metadata_version }, "PATCH"),
    ),
  createNote: (title: string, text: string, key: string, auto_topic = true) =>
    request<{ note_id: string; job_id: string; topic_warning?: string }>(
      "/api/v1/notes",
      json({ title, text, auto_topic }, "POST", key),
    ),
  replaceNote: (id: string, title: string, text: string, key: string) =>
    request(`/api/v1/notes/${id}`, json({ title, text }, "PUT", key)),
  previewUpload: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<{ text: string }>("/api/v1/notes/upload/preview", {
      method: "POST",
      body,
    });
  },
  upload: (title: string, file: File, key: string, auto_topic = true) => {
    const body = new FormData();
    body.append("title", title);
    body.append("file", file);
    body.append("auto_topic", String(auto_topic));
    return request<{ note_id: string; topic_warning?: string }>(
      "/api/v1/notes/upload",
      {
        method: "POST",
        headers: { "Idempotency-Key": key },
        body,
      },
    );
  },
  deleteNote: (id: string) =>
    request(`/api/v1/notes/${id}`, { method: "DELETE" }),
  retry: (id: string) =>
    request(`/api/v1/jobs/${id}/retry`, { method: "POST" }),
  ask: (question: string) =>
    request<Answer>(
      "/api/v1/questions",
      json({ question, include_graph: true }),
    ),
  graph: (scope: { note_id?: string; entity_id?: string }) =>
    request<ClaimGraph>("/api/v1/graph?" + params({ ...scope, hops: 2 })),
  search: (q: string, kind: string, signal: AbortSignal) =>
    request<{ items: SearchResult[]; limited: boolean }>(
      "/api/v1/search?" + params({ q, kind }),
      { signal },
    ),
  status: () => request<SystemStatus>("/api/v1/system/status"),
  ready: async () => {
    const r = await fetch("/health/ready");
    const body = await r.json();
    return { ok: r.ok, body };
  },
};
export function errorText(error: unknown): string {
  const messages: Record<string, string> = {
    API_UNREACHABLE:
      "API’ye ulaşılamıyor. API servisini ve bağlantıyı kontrol et.",
    METADATA_CHANGED:
      "Bu kayıt başka bir işlemde değişti. Yenileyip tekrar dene.",
    TOPIC_EXISTS: "Bu isimde bir konu zaten var.",
    INFERENCE_BUSY:
      "Model şu anda başka bir işlemle meşgul. Biraz sonra yeniden dene.",
    LM_STUDIO_UNAVAILABLE:
      "Yerel modele ulaşılamıyor. LM Studio’yu ve model sunucusunu kontrol et.",
    GENERATION_INVALID:
      "Model geçerli, kaynaklı bir cevap üretemedi. Soruyu daraltarak yeniden dene.",
    NOT_FOUND:
      "Kayıt bulunamadı. Silinmiş veya yeni bir sürümle değişmiş olabilir.",
    PROVIDER_TIMEOUT: "Model zamanında yanıt vermedi. Yeniden deneyebilirsin.",
  };
  return error instanceof ApiError
    ? messages[error.code] || error.message
    : error instanceof Error
      ? error.message
      : "İşlem tamamlanamadı.";
}
