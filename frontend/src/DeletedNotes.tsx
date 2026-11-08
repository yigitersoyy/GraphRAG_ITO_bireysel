import { useEffect, useState } from "react";
import { api, errorText } from "./api";
import type { DeletedNotePage } from "./types";
import { ErrorMessage } from "./ui";

const empty: DeletedNotePage = { items: [], total: 0, next_cursor: null };
const dates = new Intl.DateTimeFormat("tr-TR", {
  dateStyle: "short",
  timeStyle: "short",
});

export function DeletedNotes({ revision }: { revision: string }) {
  const [page, setPage] = useState(empty);
  const [cursors, setCursors] = useState<(string | undefined)[]>([undefined]);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    setCursors([undefined]);
    setIndex(0);
  }, [revision]);
  useEffect(() => {
    const abort = new AbortController();
    setLoading(true);
    setError("");
    api
      .deletedNotes(cursors[index], abort.signal)
      .then((result) => {
        if (!abort.signal.aborted) setPage(result);
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(errorText(e));
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => abort.abort();
  }, [cursors, index, revision, retry]);
  return (
    <section className="deleted-notes" aria-label="Silinen notlar">
      <h1 className="section-title">Silinenler</h1>
      <p className="form-hint">
        Bu kayıtlar normal not listesinde, graf ve arama sonuçlarında
        gösterilmez. İçeriği saklama süresi sonunda temizlenmiş kayıtlarda belge
        adı da kaldırılır.
      </p>
      {error && (
        <ErrorMessage message={error} retry={() => setRetry((n) => n + 1)} />
      )}
      {loading ? (
        <p role="status">Silinen notlar yükleniyor…</p>
      ) : (
        <>
          <div className="deleted-table">
            <div className="deleted-row deleted-head" aria-hidden="true">
              <span>Ad</span>
              <span>Silinme</span>
              <span>Durum</span>
            </div>
            {page.items.map((note) => (
              <div
                className="deleted-row"
                key={note.note_id}
                data-deleted-note={note.note_id}
              >
                <span className="deleted-title">
                  {note.title || "İçeriği temizlenmiş not"}
                </span>
                <time dateTime={note.deleted_at}>
                  {dates.format(new Date(note.deleted_at))}
                </time>
                <span>
                  {note.content_purged ? "İçeriği temizlendi" : "Silindi"}
                </span>
              </div>
            ))}
            {!page.items.length && (
              <p className="list-empty">Silinen not yok.</p>
            )}
          </div>
          <div className="pagination">
            <span>{page.total} silinen not</span>
            <div>
              <button
                disabled={index === 0}
                onClick={() => setIndex((n) => n - 1)}
              >
                Önceki
              </button>
              <button
                disabled={!page.next_cursor}
                onClick={() => {
                  setCursors((current) => [
                    ...current.slice(0, index + 1),
                    page.next_cursor!,
                  ]);
                  setIndex((n) => n + 1);
                }}
              >
                Sonraki
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
