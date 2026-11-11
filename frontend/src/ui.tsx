import type { ReactNode } from "react";
import type { Evidence, Note } from "./types";
import { evidenceParts } from "./text";

export function Icon({ name, size = 16 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    sun: (
      <>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" />
      </>
    ),
    moon: <path d="M20.5 13A8.5 8.5 0 0 1 11 3.5 8.5 8.5 0 1 0 20.5 13Z" />,
    layers: (
      <>
        <path d="m3 8 9-5 9 5-9 5-9-5Zm0 5 9 5 9-5M3 18l9 5 9-5" />
      </>
    ),
    search: (
      <>
        <circle cx="10" cy="10" r="6" />
        <path d="m15 15 5 5" />
      </>
    ),
    graph: (
      <>
        <circle cx="12" cy="5" r="2" />
        <circle cx="5" cy="18" r="2" />
        <circle cx="19" cy="18" r="2" />
        <path d="m11 7-5 9m7-9 5 9M7 18h10" />
      </>
    ),
    list: (
      <>
        <path d="M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1" />
      </>
    ),
    folder: <path d="M3 6h6l2 2h10v12H3V6Z" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    plus: <path d="M12 5v14M5 12h14" />,
    minus: <path d="M5 12h14" />,
    fit: (
      <>
        <path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5" />
        <circle cx="12" cy="12" r="3" />
      </>
    ),
    note: (
      <>
        <path d="M5 3h10l4 4v14H5V3Zm10 0v5h4M8 12h8M8 16h6" />
      </>
    ),
    chevron: <path d="m9 5 7 7-7 7" />,
    arrow: <path d="M19 12H5m7-7-7 7 7 7" />,
    edit: (
      <>
        <path d="m4 16 12-12 4 4L8 20H4v-4Zm10-10 4 4" />
      </>
    ),
    ask: (
      <>
        <path d="M21 11a8 8 0 0 1-8 8H7l-4 3V11a9 9 0 0 1 18 0Z" />
        <path d="M8 10h9M8 14h5" />
      </>
    ),
    upload: (
      <>
        <path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6" />
      </>
    ),
    more: (
      <>
        <circle cx="5" cy="12" r="1" />
        <circle cx="12" cy="12" r="1" />
        <circle cx="19" cy="12" r="1" />
      </>
    ),
    refresh: (
      <>
        <path d="M20 8a8 8 0 1 0 1 6M20 3v6h-6" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.note}
    </svg>
  );
}
export function IconButton({
  icon,
  label,
  onClick,
  disabled = false,
}: {
  icon: string;
  label: string;
  onClick(): void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className="icon-button"
      title={label}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
    >
      <Icon name={icon} />
    </button>
  );
}
export function ErrorMessage({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="inline-error" role="alert">
      <span>{message}</span>
      {retry && <button onClick={retry}>Yeniden dene</button>}
    </div>
  );
}
export function StateLabel({ note }: { note: Note }) {
  const labels = {
    ready: "İşlendi",
    processing: "İşleniyor",
    failed: "İşlenemedi",
    failed_update: "Güncellenemedi",
  };
  return (
    <span className={"note-state state-" + note.state}>
      <span className="state-dot" aria-hidden="true" />
      {labels[note.state]}
    </span>
  );
}
export function dateLabel(value: string | null | undefined) {
  return value
    ? new Intl.DateTimeFormat("tr-TR", {
        day: "numeric",
        month: "short",
        year: "numeric",
      }).format(new Date(value))
    : "Bilinmiyor";
}
export function Highlight({
  text,
  evidence,
}: {
  text: string;
  evidence: Evidence | null;
}) {
  if (!evidence) return <div className="note-prose">{text}</div>;
  const result = evidenceParts(text, evidence);
  if (!result)
    return (
      <>
        <ErrorMessage message="Kaynak aralığı bu metinle eşleşmiyor. Kaynağı yeniden aç." />
        <div className="note-prose">{text}</div>
      </>
    );
  return (
    <div className="note-prose">
      {result.before}
      <mark
        tabIndex={-1}
        ref={(el) => {
          if (el) el.scrollIntoView({ block: "center" });
        }}
      >
        {result.quote}
      </mark>
      {result.after}
    </div>
  );
}
