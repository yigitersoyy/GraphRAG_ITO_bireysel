import { useEffect, useRef, useState } from "react";
import { api, errorText } from "./api";
import BulkUpload from "./BulkUpload";
import type {
  Answer,
  ClaimGraph,
  Evidence,
  Note,
  Revision,
  SystemStatus,
  Topic,
} from "./types";
import { colors, modality, predicate } from "./graph";
import {
  dateLabel,
  ErrorMessage,
  Highlight,
  Icon,
  IconButton,
  StateLabel,
} from "./ui";

export function NotePanel({
  note,
  revision,
  evidence,
  topics,
  onEdit,
  onRefresh,
  onDeleted,
  onGraph,
}: {
  note: Note;
  revision: Revision | null;
  evidence: Evidence | null;
  topics: Topic[];
  onEdit(): void;
  onRefresh(): void;
  onDeleted(): void;
  onGraph(): void;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [menu, setMenu] = useState(false);
  const act = async (fn: () => Promise<unknown>) => {
    setError("");
    setBusy(true);
    try {
      await fn();
      onRefresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="panel-scroll">
        <h1 className="note-title">
          {evidence
            ? revision?.title || evidence.title
            : note.title || "Başlıksız not"}
        </h1>
        {evidence && (
          <p className="source-label">
            Kaynak revizyonu <span>{evidence.revision_id.slice(0, 8)}</span>
          </p>
        )}
        <dl className="note-metadata">
          <dt>Konu</dt>
          <dd>
            <select
              aria-label="Notun konusu"
              value={note.topic_id || ""}
              disabled={busy || !!evidence}
              onChange={(e) =>
                void act(() => api.assignTopic(note, e.target.value || null))
              }
            >
              <option value="">Düzenlenmemiş</option>
              {topics.map((t) => (
                <option key={t.topic_id} value={t.topic_id}>
                  {t.name}
                </option>
              ))}
            </select>
          </dd>
          <dt>Durum</dt>
          <dd>
            <StateLabel note={note} />
          </dd>
          <dt>{note.updated_at ? "Güncellendi" : "Eklenme"}</dt>
          <dd>{dateLabel(note.updated_at || note.created_at)}</dd>
        </dl>
        {note.state === "processing" && (
          <div className="processing-info" role="status">
            <span>
              Yeni sürüm işleniyor
              {note.job?.stage ? `: ${note.job.stage.toLowerCase()}` : "…"}
            </span>
            {note.active_revision_id && (
              <small>Arama önceki sürümü kullanıyor.</small>
            )}
            {!!note.job?.chunks_total && (
              <progress
                value={note.job.chunks_done}
                max={note.job.chunks_total}
                aria-label="İşleme ilerlemesi"
              />
            )}
          </div>
        )}
        {(note.state === "failed" || note.state === "failed_update") && (
          <div className="processing-info failed">
            <span>
              {note.state === "failed_update"
                ? "Yeni sürüm işlenemedi; önceki sürüm aranabilir."
                : "Bu not işlenemedi."}
            </span>
            <small>{note.job?.error_code}</small>
            {note.job && (
              <button
                onClick={() => void act(() => api.retry(note.job!.job_id))}
                disabled={busy}
              >
                Yeniden dene
              </button>
            )}
          </div>
        )}
        {error && <ErrorMessage message={error} />}
        <div className="note-content">
          {revision ? (
            <Highlight text={revision.text} evidence={evidence} />
          ) : (
            <p className="muted" role="status">
              Not yükleniyor…
            </p>
          )}
        </div>
        {note.active_revision_id && (
          <section className="note-relations">
            <h2>Kaynak ilişkileri</h2>
            <p>
              Bu nottan çıkarılan varlıkları ve ilişkilerin kaynaklarını incele.
            </p>
            <button onClick={onGraph}>
              <Icon name="graph" />
              İlişkileri göster
            </button>
          </section>
        )}
      </div>
      <div className="panel-actions">
        <button onClick={onEdit} disabled={busy}>
          <Icon name="edit" />
          Düzenle
        </button>
        <div className="actions-menu">
          <IconButton
            icon="more"
            label="Not işlemleri"
            onClick={() => setMenu(!menu)}
          />
          {menu && (
            <div className="popover-menu">
              <button
                className="danger-text"
                disabled={busy}
                onClick={() => {
                  if (confirm(`“${note.title}” notu silinsin mi?`))
                    void act(async () => {
                      await api.deleteNote(note.note_id);
                      onDeleted();
                    });
                }}
              >
                Notu sil
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

export function Editor({
  note,
  revision,
  topics,
  onDirty,
  onSaved,
  onCancel,
}: {
  note: Note | null;
  revision: Revision | null;
  topics: Topic[];
  onDirty(value: boolean): void;
  onSaved(id: string, warning?: string): void;
  onCancel(): void;
}) {
  const [title, setTitle] = useState(revision?.title || note?.title || ""),
    [text, setText] = useState(revision?.text || ""),
    [topic, setTopic] = useState(note ? note.topic_id || "" : "__auto__");
  const [file, setFile] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [reading, setReading] = useState(false),
    [error, setError] = useState("");
  const [batch, setBatch] = useState<File[]>([]);
  const submission = useRef({ signature: "", key: crypto.randomUUID() });
  useEffect(() => {
    onDirty(
      title !== (revision?.title || note?.title || "") ||
        text !== (revision?.text || "") ||
        topic !== (note ? note.topic_id || "" : "__auto__") ||
        file !== null,
    );
  }, [title, text, topic, file, note, revision, onDirty]);
  const save = async () => {
    if (!title.trim() || !text.trim()) {
      setError("Not için bir başlık ve metin yaz.");
      return;
    }
    setError("");
    setBusy(true);
    const signature = JSON.stringify([
      note?.note_id,
      title,
      text,
      topic,
      file?.name,
      file?.lastModified,
    ]);
    if (signature !== submission.current.signature)
      submission.current = { signature, key: crypto.randomUUID() };
    try {
      let id = note?.note_id;
      let warning: string | undefined;
      if (note)
        await api.replaceNote(
          note.note_id,
          title,
          text,
          submission.current.key,
        );
      else {
        const result = file
          ? await api.upload(
              title,
              file,
              submission.current.key,
              topic === "__auto__",
            )
          : await api.createNote(
              title,
              text,
              submission.current.key,
              topic === "__auto__",
            );
        id = result.note_id;
        warning = result.topic_warning || undefined;
      }
      if (topic !== "__auto__" && (!note || (note.topic_id || "") !== topic)) {
        try {
          const latest = await api.note(id!);
          await api.assignTopic(latest, topic || null);
        } catch (e) {
          warning = "Not kaydedildi; konu atanamadı. " + errorText(e);
        }
      }
      onDirty(false);
      onSaved(id!, warning);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  if (batch.length)
    return (
      <BulkUpload
        files={batch}
        topics={topics}
        initialTopic={topic}
        onDirty={onDirty}
        onSaved={onSaved}
        onCancel={onCancel}
      />
    );
  return (
    <form
      className="editor-form"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <div className="panel-scroll">
        <label className="field-label" htmlFor="note-title">
          Başlık
        </label>
        <input
          id="note-title"
          autoFocus
          className="title-input"
          value={title}
          maxLength={200}
          onChange={(e) => setTitle(e.target.value)}
          disabled={busy}
          placeholder="Notuna bir ad ver"
        />
        <label className="field-label" htmlFor="editor-topic">
          Konu
        </label>
        <select
          id="editor-topic"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          disabled={busy}
        >
          {!note && (
            <option value="__auto__">Başlığa göre otomatik konu</option>
          )}
          <option value="">Düzenlenmemiş</option>
          {topics.map((t) => (
            <option key={t.topic_id} value={t.topic_id}>
              {t.name}
            </option>
          ))}
        </select>
        {!note && topic === "__auto__" && (
          <p className="form-hint">
            Dosya adının ortak ön eki konu olur: 01_kvkk_… → KVKK. Konuyu
            listeden sürükleyerek değiştirebilirsin.
          </p>
        )}
        <label className="field-label" htmlFor="note-text">
          Metin
        </label>
        <textarea
          id="note-text"
          className="note-editor"
          value={text}
          onChange={(e) => {
            setFile(null);
            setText(e.target.value);
          }}
          disabled={busy}
          placeholder="Türkçe veya İngilizce notlarını buraya yaz…"
        />
        {!note && (
          <>
            <label className="upload-control">
              <Icon name="upload" />
              <span>
                {file ? file.name : "PDF, Word, Excel veya metin dosyası yükle"}
              </span>
              <input
                aria-label="Not dosyası yükle"
                type="file"
                multiple
                accept=".txt,.md,.pdf,.docx,.xlsx,.xls"
                disabled={busy}
                onChange={async (e) => {
                  const selectedFiles = Array.from(e.target.files || []);
                  const selected = selectedFiles[0];
                  e.target.value = "";
                  if (!selected) return;
                  if (selectedFiles.length > 50) {
                    setError("Bir seçimde en fazla 50 dosya yükleyebilirsin.");
                    return;
                  }
                  if (selectedFiles.length > 1) {
                    setBatch(selectedFiles);
                    setError("");
                    return;
                  }
                  if (
                    !/\.(txt|md|pdf|docx|xlsx|xls)$/i.test(selected.name) ||
                    selected.size >
                      (/\.(pdf|docx|xlsx|xls)$/i.test(selected.name)
                        ? 10485760
                        : 1048576)
                  ) {
                    setError(
                      "PDF/Word/Excel en fazla 10 MiB; UTF-8 TXT/Markdown en fazla 1 MiB olabilir.",
                    );
                    return;
                  }
                  setBusy(true);
                  setReading(true);
                  setError("");
                  try {
                    const preview = await api.previewUpload(selected);
                    setText(preview.text);
                    setFile(selected);
                    if (!title) setTitle(selected.name.replace(/\.[^.]+$/, ""));
                    setError("");
                  } catch (e) {
                    setError(errorText(e));
                  } finally {
                    setReading(false);
                    setBusy(false);
                  }
                }}
              />
            </label>
            <p className="form-hint">
              PDF/Word/Excel: en fazla 10 MiB; çıkarılan metin en fazla 100.000
              karakter. PDF en fazla 200 sayfa olabilir. Taranmış sayfalar için
              OCR gerekir. Kaynaklar yukarıdaki metni gösterir; kontrol edip
              kaydet. Excel'de sayfa ve hücre adresleri korunur; formüller
              yeniden hesaplanmaz.
            </p>
          </>
        )}
        {error && <ErrorMessage message={error} />}
        <p className="form-hint">
          Kaydettikten sonra notun işleme alınır. Konu ataması metni
          değiştirmez.
        </p>
      </div>
      <div className="panel-actions">
        <button type="button" onClick={onCancel} disabled={busy}>
          Vazgeç
        </button>
        <button type="submit" className="primary" disabled={busy}>
          {busy ? (reading ? "Belge okunuyor…" : "Kaydediliyor…") : "Kaydet"}
        </button>
      </div>
    </form>
  );
}

export function TopicPanel({
  topics,
  onRefresh,
}: {
  topics: Topic[];
  onRefresh(): void;
}) {
  const [editing, setEditing] = useState<Topic | null>(null),
    [name, setName] = useState(""),
    [color, setColor] = useState("purple"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const reset = () => {
    setEditing(null);
    setName("");
    setColor("purple");
  };
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      reset();
      onRefresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="panel-scroll">
      <h1 className="panel-title">Konular</h1>
      <p className="muted">
        Notlarını kendine uygun gruplara ayır. Her konunun haritada kendi rengi
        olur.
      </p>
      <form
        className="topic-form"
        onSubmit={(e) => {
          e.preventDefault();
          void act(() =>
            editing
              ? api.editTopic(editing, name, color)
              : api.createTopic(name, color),
          );
        }}
      >
        <label htmlFor="topic-name">
          {editing ? "Konuyu düzenle" : "Yeni konu"}
        </label>
        <input
          id="topic-name"
          value={name}
          maxLength={80}
          required
          onChange={(e) => setName(e.target.value)}
          placeholder="Örneğin Projeler"
          disabled={busy}
        />
        <div className="swatches" role="group" aria-label="Konu rengi">
          {Object.entries(colors).map(([key, hex]) => (
            <button
              key={key}
              type="button"
              className={color === key ? "chosen" : ""}
              style={{ "--swatch": hex } as React.CSSProperties}
              aria-label={
                "Renk: " +
                (
                  {
                    purple: "Mor",
                    blue: "Mavi",
                    teal: "Turkuaz",
                    orange: "Turuncu",
                    pink: "Pembe",
                    green: "Yeşil",
                    yellow: "Sarı",
                    gray: "Gri",
                  } as Record<string, string>
                )[key]
              }
              aria-pressed={color === key}
              onClick={() => setColor(key)}
            />
          ))}
        </div>
        <div className="form-buttons">
          {editing && (
            <button type="button" onClick={reset}>
              Vazgeç
            </button>
          )}
          <button className="primary" disabled={busy || !name.trim()}>
            {editing ? "Değişiklikleri kaydet" : "Konu oluştur"}
          </button>
        </div>
      </form>
      {error && <ErrorMessage message={error} />}
      <div className="topic-management-list">
        {topics.map((t) => (
          <div className="topic-management-row" key={t.topic_id}>
            <button
              className="topic-edit"
              onClick={() => {
                setEditing(t);
                setName(t.name);
                setColor(t.color_key);
              }}
            >
              <span
                className="color-dot"
                style={{ background: colors[t.color_key] }}
              />
              <span>
                {t.name}
                <small>{t.note_count} not</small>
              </span>
              <Icon name="edit" size={14} />
            </button>
            <button
              className="text-button danger-text"
              disabled={busy}
              onClick={() => {
                if (
                  confirm(
                    `“${t.name}” konusu silinsin mi? Notların silinmez; Düzenlenmemiş grubuna taşınır.`,
                  )
                )
                  void act(() => api.deleteTopic(t));
              }}
            >
              Sil
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export function AskPanel({
  answer,
  onAnswer,
  onStart,
  onGraph,
  onBack,
}: {
  answer: Answer | null;
  onAnswer(answer: Answer): void;
  onStart(): void;
  onGraph(graph: ClaimGraph): void;
  onBack(): void;
}) {
  const [question, setQuestion] = useState(""),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  const [source, setSource] = useState<Evidence | null>(null),
    [revision, setRevision] = useState<Revision | null>(null),
    [sourceError, setSourceError] = useState("");
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const ask = async () => {
    if (!question.trim()) return;
    onStart();
    setLoading(true);
    setError("");
    try {
      const r = await api.ask(question);
      if (mounted.current) {
        onAnswer(r);
      }
    } catch (e) {
      if (mounted.current) setError(errorText(e));
    } finally {
      if (mounted.current) setLoading(false);
    }
  };
  const open = async (ev: Evidence) => {
    setSource(ev);
    setRevision(null);
    setSourceError("");
    try {
      const rev = await api.revision(ev.note_id, ev.revision_id);
      setRevision(rev);
    } catch (e) {
      setSourceError(errorText(e));
    }
  };
  if (source)
    return (
      <div className="panel-scroll">
        <button
          className="text-button back-link"
          onClick={() => setSource(null)}
        >
          <Icon name="arrow" />
          Cevaba dön
        </button>
        <h1 className="note-title">{source.title}</h1>
        <p className="source-label">
          Kaynak revizyonu {source.revision_id.slice(0, 8)}
        </p>
        {sourceError && <ErrorMessage message={sourceError} />}
        {revision ? (
          <Highlight text={revision.text} evidence={source} />
        ) : (
          !sourceError && <p role="status">Kaynak yükleniyor…</p>
        )}
      </div>
    );
  return (
    <div className="panel-scroll ask-panel">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask();
        }}
      >
        <label className="sr-only" htmlFor="question">
          Sorun
        </label>
        <textarea
          id="question"
          autoFocus
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={2000}
          placeholder="Notlarına bir soru sor…"
          disabled={loading}
        />
        <button className="primary" disabled={loading || !question.trim()}>
          {loading ? "Yanıt bekleniyor…" : "Sor"}
        </button>
      </form>
      {loading && (
        <p className="pending-answer" role="status">
          Notlar taranıyor ve yerel modelden yanıt bekleniyor.
        </p>
      )}
      {error && <ErrorMessage message={error} />}
      {!answer && !loading && (
        <p className="ask-empty">
          Bir kişi, proje veya karar hakkında sor. Cevabın dayandığı notları
          birlikte görebilirsin.
        </p>
      )}
      {answer && (
        <div className="answer-result">
          <p className="field-label">
            {answer.diagnostics.semantic_review_uncertain
              ? "Kaynak kontrolü gerekiyor"
              : answer.status === "partial"
                ? "Notlarda bulabildiklerim"
                : answer.status === "insufficient_evidence"
                  ? "Yeterli kaynak yok"
                  : "Yanıt"}
          </p>
          <div className="answer-text">{answer.answer}</div>
          {!!answer.diagnostics.semantic_review_uncertain && (
            <p className="form-hint" role="status">
              Bu yanıtın yorumunu kaynaklardan kontrol edin.
            </p>
          )}
          {answer.missing_information.length > 0 && (
            <div className="missing-info">
              <strong>Eksik kalan bilgi</strong>
              <ul>
                {answer.missing_information.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
          {answer.citations.length > 0 && (
            <section className="answer-sources">
              <h2>Kaynaklar</h2>
              {answer.citations.map((c, i) => (
                <button
                  className="source-button"
                  key={c.evidence_id || i}
                  onClick={() => void open(c)}
                >
                  <span className="source-number">
                    {c.evidence_id || i + 1}
                  </span>
                  <span>
                    <strong>{c.title}</strong>
                    <q>{c.quote}</q>
                    <span className="source-open">Kaynağı aç</span>
                  </span>
                </button>
              ))}
            </section>
          )}
          {!!answer.diagnostics.limited_by_budget && (
            <p className="form-hint">Sonuçlar kaynak bütçesiyle sınırlandı.</p>
          )}
          {answer.graph.edges.length > 0 && (
            <button onClick={() => onGraph(answer.graph)}>
              <Icon name="graph" />
              Destekleyici ilişkileri göster
            </button>
          )}
          <button className="text-button back-link" onClick={onBack}>
            Not haritasına dön
          </button>
        </div>
      )}
    </div>
  );
}

export function SystemPanel({
  status,
  ready,
  onRefresh,
}: {
  status: SystemStatus | null;
  ready: { ok: boolean; body: unknown } | null;
  onRefresh(): void;
}) {
  const checks = (
    ready?.body as { checks?: { reachable?: boolean } } | undefined
  )?.checks;
  return (
    <div className="panel-scroll">
      <h1 className="panel-title">Sistem durumu</h1>
      <dl className="system-details">
        <dt>API</dt>
        <dd>{status ? "Erişilebilir" : "Erişilemiyor"}</dd>
        <dt>Hazır olma</dt>
        <dd>
          {ready ? (ready.ok ? "Hazır" : "Hazır değil") : "Kontrol edilemiyor"}
        </dd>
        <dt>Depolama</dt>
        <dd>
          {status?.mode.startsWith("neo4j")
            ? "Neo4j / kalıcı"
            : status
              ? "Bellek / geçici"
              : "Bilinmiyor"}
        </dd>
        <dt>Model</dt>
        <dd>
          {status?.mode.endsWith("demo")
            ? "Demo"
            : status
              ? "Yerel model"
              : "Bilinmiyor"}
        </dd>
        <dt>Worker</dt>
        <dd>
          {status
            ? status.worker.fresh
              ? "Çalışıyor"
              : "Güncel sinyal yok"
            : "Bilinmiyor"}
        </dd>
        <dt>Neo4j</dt>
        <dd>
          {status?.mode.startsWith("memory")
            ? "Bu modda kullanılmıyor"
            : checks?.reachable === true
              ? "Erişilebilir"
              : checks?.reachable === false
                ? "Erişilemiyor"
                : "Bilinmiyor"}
        </dd>
        <dt>LM Studio</dt>
        <dd>
          {status?.mode.endsWith("demo")
            ? "Demo sağlayıcı kullanılıyor"
            : status?.lm_studio.endpoint_reachable === true
              ? "Erişilebilir"
              : status?.lm_studio.endpoint_reachable === false
                ? "Erişilemiyor"
                : "Bilinmiyor"}
        </dd>
        <dt>Model işlemi</dt>
        <dd>{status?.inference_slot.state || "Bilinmiyor"}</dd>
      </dl>
      {status && (
        <>
          <h2 className="section-title">Modeller</h2>
          <dl className="model-details">
            {Object.entries(status.models).map(([k, v]) => (
              <div key={k}>
                <dt>
                  {(
                    {
                      extraction: "Çıkarım",
                      answer: "Cevap",
                      embedding: "Embedding",
                      embedding_profile: "Profil",
                      embedding_dimensions: "Boyut",
                    } as Record<string, string>
                  )[k] || k}
                </dt>
                <dd>{String(v || "Ayarlanmamış")}</dd>
              </div>
            ))}
          </dl>
        </>
      )}
      <button onClick={onRefresh}>
        <Icon name="refresh" />
        Durumu yenile
      </button>
      {ready && !ready.ok && (
        <details className="technical-detail">
          <summary>Hazır olmama ayrıntısı</summary>
          <pre>{JSON.stringify(ready.body, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}

export function ClaimsList({
  graph,
  onEvidence,
}: {
  graph: ClaimGraph;
  onEvidence(e: Evidence): void;
}) {
  const names = new Map(graph.nodes.map((n) => [n.id, n.label]));
  return (
    <div className="claims-list">
      <h2>Kaynak ilişkileri</h2>
      {graph.limited && (
        <p className="form-hint">
          İlişkiler sınırlandı. Bir varlık seçerek daralt.
        </p>
      )}
      {graph.edges.map((e) => (
        <button
          className="claim-row"
          key={e.id}
          onClick={() => onEvidence(e.evidence)}
        >
          <span>
            {names.get(e.source)}{" "}
            <span className="muted">
              {predicate(e.predicate)}
              {e.polarity === "NEGATED" ? " (değil)" : ""}
            </span>{" "}
            {names.get(e.target)}
          </span>
          <small>
            {e.modality !== "ASSERTED" && modality(e.modality) + " / "}
            {e.evidence.title}
          </small>
        </button>
      ))}
    </div>
  );
}
