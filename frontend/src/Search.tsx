import { useEffect, useRef, useState } from "react";
import { api, errorText } from "./api";
import type { SearchResult } from "./types";
import { ErrorMessage, Icon, IconButton } from "./ui";

export function Search({
  onClose,
  onSelect,
  onList,
  onCreate,
}: {
  onClose(): void;
  onSelect(result: SearchResult): void;
  onList(q: string): void;
  onCreate(): void;
}) {
  const [q, setQ] = useState(""),
    [kind, setKind] = useState("all");
  const [items, setItems] = useState<SearchResult[]>([]),
    [index, setIndex] = useState(0),
    [limited, setLimited] = useState(false),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false);
  const dialog = useRef<HTMLDivElement>(null),
    input = useRef<HTMLInputElement>(null),
    options = useRef<(HTMLButtonElement | null)[]>([]);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    input.current?.focus();
    return () => previous?.focus();
  }, []);
  useEffect(() => {
    const abort = new AbortController();
    setIndex(0);
    setError("");
    if (!q.trim()) {
      setItems([]);
      setLoading(false);
      return () => abort.abort();
    }
    setLoading(true);
    const timer = setTimeout(() => {
      api
        .search(q, kind, abort.signal)
        .then((r) => {
          if (!abort.signal.aborted) {
            setItems(r.items);
            setLimited(r.limited);
          }
        })
        .catch((e) => {
          if (!abort.signal.aborted) {
            setError(errorText(e));
            setItems([]);
          }
        })
        .finally(() => {
          if (!abort.signal.aborted) setLoading(false);
        });
    }, 200);
    return () => {
      clearTimeout(timer);
      abort.abort();
    };
  }, [q, kind]);
  useEffect(() => {
    options.current[index]?.scrollIntoView({ block: "nearest" });
  }, [index]);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="search-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Not, varlık veya konu ara"
        ref={dialog}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.stopPropagation();
            onClose();
          }
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setIndex((i) => Math.max(0, Math.min(items.length - 1, i + 1)));
          }
          if (e.key === "ArrowUp") {
            e.preventDefault();
            setIndex((i) => Math.max(0, i - 1));
          }
          if (e.key === "Enter" && items[index] && e.target === input.current) {
            e.preventDefault();
            onSelect(items[index]);
          }
          if (e.key === "Tab") {
            const focusable = [
              ...(dialog.current?.querySelectorAll<HTMLElement>(
                "button:not([disabled]),input",
              ) || []),
            ];
            const first = focusable[0],
              last = focusable.at(-1);
            if (e.shiftKey && document.activeElement === first) {
              e.preventDefault();
              last?.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
              e.preventDefault();
              first?.focus();
            }
          }
        }}
      >
        <div className="search-input-row">
          <Icon name="search" size={19} />
          <input
            ref={input}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Not, varlık veya konu ara…"
            aria-label="Arama"
            role="combobox"
            aria-expanded={items.length > 0}
            aria-controls="search-results"
            aria-autocomplete="list"
            aria-activedescendant={items[index] ? "result-" + index : undefined}
            maxLength={200}
          />
          <IconButton icon="close" label="Aramayı kapat" onClick={onClose} />
        </div>
        <div className="search-kinds">
          {[
            ["all", "Tümü"],
            ["note", "Notlar"],
            ["entity", "Varlıklar"],
            ["topic", "Konular"],
          ].map(([key, label]) => (
            <button
              key={key}
              aria-pressed={kind === key}
              onClick={() => setKind(key)}
            >
              {label}
            </button>
          ))}
        </div>
        {error && <ErrorMessage message={error} />}
        <div
          className="search-results"
          id="search-results"
          role="listbox"
          aria-label="Arama sonuçları"
          aria-busy={loading}
        >
          {loading && (
            <div className="search-hint" role="status">
              Aranıyor…
            </div>
          )}
          {!loading && !q && (
            <div className="search-hint">
              Not başlığı, metin, varlık veya konu adını yaz.
            </div>
          )}
          {!loading && q && !items.length && !error && (
            <div className="search-hint">
              Sonuç bulunamadı.
              <button className="text-button" onClick={onCreate}>
                Yeni not oluştur
              </button>
            </div>
          )}
          {items.map((item, i) => (
            <button
              type="button"
              key={item.kind + item.id}
              id={"result-" + i}
              ref={(el) => {
                options.current[i] = el;
              }}
              className={"search-result" + (index === i ? " active" : "")}
              role="option"
              aria-selected={index === i}
              onMouseEnter={() => setIndex(i)}
              onClick={() => onSelect(item)}
            >
              <span>
                <strong>{item.label || "Başlıksız not"}</strong>
                <small>{item.snippet || "Notu aç"}</small>
              </span>
              <span className="result-kind">
                {{ note: "Not", entity: "Varlık", topic: "Konu" }[item.kind]}
              </span>
            </button>
          ))}
        </div>
        <div className="search-footer">
          <span>
            ↑ ↓ Seç <span className="key-space">Enter Aç</span>
          </span>
          <button className="text-button" onClick={() => onList(q)}>
            {limited ? "Daha fazla notu listede ara" : "Not listesini aç"}
          </button>
        </div>
      </div>
    </div>
  );
}
