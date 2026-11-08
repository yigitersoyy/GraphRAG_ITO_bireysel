import { useEffect, useRef, useState } from "react";
import { api, errorText } from "./api";
import type { Topic } from "./types";
import { ErrorMessage } from "./ui";

type Row = {
  file: File;
  key: string;
  status: "pending" | "uploading" | "accepted" | "error";
  message: string;
  noteId?: string;
};
export default function BulkUpload({
  files,
  topics,
  initialTopic,
  onDirty,
  onSaved,
  onCancel,
}: {
  files: File[];
  topics: Topic[];
  initialTopic: string;
  onDirty(value: boolean): void;
  onSaved(id: string, warning?: string): void;
  onCancel(): void;
}) {
  const [rows, setRows] = useState<Row[]>(() =>
    files.map((file) => ({
      file,
      key: crypto.randomUUID(),
      status: "pending",
      message: "Hazır",
    })),
  );
  const current = useRef(rows),
    busyRef = useRef(false),
    stop = useRef(false);
  const [busy, setBusy] = useState(false),
    [topic, setTopic] = useState(initialTopic),
    [preview, setPreview] = useState<{ name: string; text: string } | null>(
      null,
    ),
    [previewing, setPreviewing] = useState(false),
    [error, setError] = useState("");
  const update = (index: number, patch: Partial<Row>) => {
    current.current = current.current.map((r, i) =>
      i === index ? { ...r, ...patch } : r,
    );
    setRows(current.current);
  };
  const accepted = rows.filter((r) => r.status === "accepted").length;
  const remaining = rows.some((r) => r.status !== "accepted");
  useEffect(() => {
    onDirty(remaining);
  }, [remaining, onDirty]);
  const run = async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    stop.current = false;
    setBusy(true);
    setError("");
    try {
      for (let i = 0; i < current.current.length; i++) {
        if (stop.current) break;
        const row = current.current[i];
        if (row.status === "accepted") continue;
        const file = row.file;
        update(i, { status: "uploading", message: "Yükleniyor…" });
        try {
          if (!/\.(txt|md|pdf|docx|xlsx|xls)$/i.test(file.name))
            throw new Error("Desteklenmeyen dosya türü.");
          if (file.size > (/\.(txt|md)$/i.test(file.name) ? 1048576 : 10485760))
            throw new Error("Dosya boyut sınırını aşıyor.");
          const title = file.name.replace(/\.[^.]+$/, "").slice(0, 200);
          const result = await api.upload(
            title,
            file,
            row.key,
            topic === "__auto__",
          );
          let warning = result.topic_warning || "";
          if (topic !== "__auto__") {
            try {
              await api.assignTopic(
                await api.note(result.note_id),
                topic || null,
              );
            } catch (e) {
              warning = "Not eklendi; konu atanamadı. " + errorText(e);
            }
          }
          update(i, {
            status: "accepted",
            noteId: result.note_id,
            message: warning || "İşlemeye alındı",
          });
        } catch (e) {
          update(i, { status: "error", message: errorText(e) });
        }
      }
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };
  const showPreview = async (row: Row) => {
    setPreviewing(true);
    setError("");
    try {
      setPreview({
        name: row.file.name,
        text: (await api.previewUpload(row.file)).text,
      });
    } catch (e) {
      setError(errorText(e));
    } finally {
      setPreviewing(false);
    }
  };
  const labels = {
    pending: "Hazır",
    uploading: "Yükleniyor",
    accepted: "İşlemeye alındı",
    error: "Yüklenemedi",
  };
  return (
    <form
      className="editor-form bulk-upload"
      onSubmit={(e) => {
        e.preventDefault();
        void run();
      }}
    >
      <div className="panel-scroll">
        <h2>Toplu dosya yükleme</h2>
        <p className="form-hint">
          Her dosya ayrı not olur. Dosyalar sırayla yüklenir; biri hata verse de
          diğerleri devam eder.
        </p>
        <label className="field-label" htmlFor="bulk-topic">
          Dosyaların konusu
        </label>
        <select
          id="bulk-topic"
          value={topic}
          disabled={busy || accepted > 0}
          onChange={(e) => setTopic(e.target.value)}
        >
          <option value="__auto__">Dosya adına göre otomatik</option>
          <option value="">Düzenlenmemiş</option>
          {topics.map((t) => (
            <option key={t.topic_id} value={t.topic_id}>
              {t.name}
            </option>
          ))}
        </select>
        <p role="status" className="bulk-progress">
          {accepted} / {rows.length} dosya işleme alındı
        </p>
        <ul className="bulk-file-list">
          {rows.map((row) => (
            <li
              key={row.key}
              data-file-name={row.file.name}
              className={"bulk-file " + row.status}
            >
              <button
                type="button"
                className="bulk-file-name"
                disabled={busy || previewing}
                title="Metin önizlemesini aç"
                onClick={() => void showPreview(row)}
              >
                {row.file.name}
              </button>
              <span
                className="bulk-file-status"
                aria-label={`${row.file.name}: ${labels[row.status]}`}
              >
                {labels[row.status]}
              </span>
              <small>{row.message}</small>
            </li>
          ))}
        </ul>
        {previewing && <p role="status">Önizleme hazırlanıyor…</p>}
        {preview && (
          <div className="bulk-preview">
            <h3>{preview.name}</h3>
            <textarea
              aria-label="Dosya önizlemesi"
              readOnly
              value={preview.text}
            />
            <button type="button" onClick={() => setPreview(null)}>
              Önizlemeyi kapat
            </button>
          </div>
        )}
        {error && <ErrorMessage message={error} />}
        <p className="form-hint">
          İşlemeye alınan dosyaların model işleme durumunu listeden takip
          edebilirsin. Yeniden deneme başarılı dosyaları çoğaltmaz.
        </p>
      </div>
      <div className="panel-actions">
        {busy ? (
          <button
            type="button"
            onClick={() => {
              stop.current = true;
            }}
          >
            Bu dosyadan sonra durdur
          </button>
        ) : (
          <button type="button" onClick={onCancel}>
            {accepted ? "Kapat" : "Vazgeç"}
          </button>
        )}
        {remaining ? (
          <button
            className="primary"
            type="submit"
            disabled={busy || previewing}
          >
            {busy
              ? "Yükleniyor…"
              : rows.some((r) => r.status === "error")
                ? "Kalanları yeniden dene"
                : "Dosyaları yükle"}
          </button>
        ) : (
          <button
            className="primary"
            type="button"
            onClick={() => {
              onDirty(false);
              onSaved(
                rows.find((r) => r.noteId)!.noteId!,
                `${accepted} dosya işleme alındı.`,
              );
            }}
          >
            Tamam
          </button>
        )}
      </div>
    </form>
  );
}
