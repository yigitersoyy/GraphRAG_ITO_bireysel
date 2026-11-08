import { useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { api, errorText } from "./api";
import Graph, { colors } from "./graph";
import type { GraphHandle } from "./graph";
import type {
  Answer,
  ClaimGraph,
  Evidence,
  MapData,
  Note,
  NotePage,
  Revision,
  SearchResult,
  SharedEdge,
  SystemStatus,
  Topic,
} from "./types";
import {
  AskPanel,
  ClaimsList,
  Editor,
  NotePanel,
  SystemPanel,
  TopicPanel,
} from "./Panels";
import { Search } from "./Search";
import { dateLabel, ErrorMessage, Icon, IconButton, StateLabel } from "./ui";

type View = "graph" | "list" | "topics";
type Panel =
  "note" | "edit" | "create" | "ask" | "system" | "topics" | "link" | null;
const emptyPage: NotePage = { items: [], total: 0, next_cursor: null };

export default function App() {
  const [view, setView] = useState<View>(() => {
    const v = localStorage.getItem("workspace-view");
    return v === "list" || v === "topics" || v === "graph"
      ? v
      : matchMedia("(max-width: 760px)").matches
        ? "list"
        : "graph";
  });
  const [panel, setPanel] = useState<Panel>(null),
    [width, setWidth] = useState(380),
    [search, setSearch] = useState(false);
  const [map, setMap] = useState<MapData | null>(null),
    [page, setPage] = useState<NotePage>(emptyPage),
    [topics, setTopics] = useState<Topic[]>([]);
  const [topicId, setTopicId] = useState(""),
    [q, setQ] = useState(""),
    [cursors, setCursors] = useState<(string | undefined)[]>([undefined]),
    [pageIndex, setPageIndex] = useState(0);
  const [draggedId, setDraggedId] = useState<string | null>(null),
    [dropTopic, setDropTopic] = useState<string | null>(null),
    [movingId, setMovingId] = useState<string | null>(null);
  const draggedNote = useRef<Note | null>(null),
    moving = useRef(false);
  const [mapCursors, setMapCursors] = useState<(string | undefined)[]>([
      undefined,
    ]),
    [mapIndex, setMapIndex] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null),
    [note, setNote] = useState<Note | null>(null),
    [revision, setRevision] = useState<Revision | null>(null),
    [source, setSource] = useState<Evidence | null>(null);
  const [claims, setClaims] = useState<ClaimGraph | null>(null),
    [answer, setAnswer] = useState<Answer | null>(null),
    [answerFocus, setAnswerFocus] = useState<Answer | null>(null),
    [link, setLink] = useState<SharedEdge | null>(null);
  const [showTopics, setShowTopics] = useState(true),
    [showLinks, setShowLinks] = useState(true),
    [expanded, setExpanded] = useState(new Set<string>());
  const [status, setStatus] = useState<SystemStatus | null>(null),
    [ready, setReady] = useState<{ ok: boolean; body: unknown } | null>(null),
    [error, setError] = useState(""),
    [noteError, setNoteError] = useState(""),
    [notice, setNotice] = useState(""),
    [loading, setLoading] = useState(true);
  const graph = useRef<GraphHandle>(null),
    sequence = useRef(0),
    dirty = useRef(false),
    panelTrigger = useRef<HTMLElement | null>(null),
    refreshNote = useRef<() => void>(() => {});
  const onDirty = useCallback((value: boolean) => {
    dirty.current = value;
  }, []);
  const leave = () => {
    if (
      dirty.current &&
      !confirm("Kaydedilmeyen değişiklikler var. Değişiklikler bırakılsın mı?")
    )
      return false;
    dirty.current = false;
    return true;
  };

  const refresh = useCallback(async () => {
    const seq = ++sequence.current;
    const results = await Promise.allSettled([
      api.map(topicId, q, mapCursors[mapIndex]),
      api.notes(topicId, q, cursors[pageIndex]),
      api.topics(),
      api.status(),
      api.ready(),
    ]);
    if (seq !== sequence.current) return;
    const [m, n, t, s, r] = results;
    if (m.status === "fulfilled") setMap(m.value);
    if (n.status === "fulfilled") setPage(n.value);
    if (t.status === "fulfilled") setTopics(t.value.items);
    if (s.status === "fulfilled") setStatus(s.value);
    else setStatus(null);
    if (r.status === "fulfilled") setReady(r.value);
    else setReady(null);
    const failed = results.find((x) => x.status === "rejected");
    setError(failed?.status === "rejected" ? errorText(failed.reason) : "");
    setLoading(false);
    if (n.status === "fulfilled" && !n.value.items.length && pageIndex > 0)
      setPageIndex((i) => i - 1);
    refreshNote.current();
  }, [topicId, q, cursors, pageIndex, mapCursors, mapIndex]);
  useEffect(() => {
    void refresh();
    const interval = setInterval(() => {
      if (!document.hidden) void refresh();
    }, 5000);
    return () => {
      sequence.current++;
      clearInterval(interval);
    };
  }, [refresh]);
  useEffect(() => {
    localStorage.setItem("workspace-view", view);
  }, [view]);
  useEffect(() => {
    requestAnimationFrame(() => {
      if (!panel) {
        if (panelTrigger.current?.isConnected) panelTrigger.current.focus();
      } else if (panel !== "create" && panel !== "edit" && panel !== "ask") {
        document
          .querySelector<HTMLButtonElement>(".panel-heading button")
          ?.focus();
      }
    });
  }, [panel]);
  useEffect(() => {
    const fn = (event: BeforeUnloadEvent) => {
      if (dirty.current) event.preventDefault();
    };
    window.addEventListener("beforeunload", fn);
    return () => window.removeEventListener("beforeunload", fn);
  }, []);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearch((v) => !v);
      } else if (e.key === "Escape" && !search && panel && leave())
        setPanel(null);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [search, panel]);

  useEffect(() => {
    if (!selectedId || (panel !== "note" && panel !== "edit")) {
      refreshNote.current = () => {};
      return;
    }
    let active = true,
      inFlight = false;
    const update = async () => {
      if (inFlight || panel === "edit") return;
      inFlight = true;
      try {
        const n = await api.note(selectedId);
        if (!active) return;
        setNote(n);
        setNoteError("");
        const rid = source?.revision_id || n.desired_revision_id;
        const rev = await api.revision(n.note_id, rid);
        if (active) setRevision(rev);
      } catch (e) {
        if (active) setNoteError(errorText(e));
      } finally {
        inFlight = false;
      }
    };
    refreshNote.current = () => {
      void update();
    };
    void update();
    return () => {
      active = false;
      refreshNote.current = () => {};
    };
  }, [selectedId, panel, source]);

  const filter = (topic: string, query = q) => {
    setTopicId(topic);
    setQ(query);
    setCursors([undefined]);
    setPageIndex(0);
    setMapCursors([undefined]);
    setMapIndex(0);
  };
  const openNote = (id: string, evidence: Evidence | null = null) => {
    if (!leave()) return;
    if (!panel) panelTrigger.current = document.activeElement as HTMLElement;
    setSelectedId(id);
    setSource(evidence);
    setRevision(null);
    setNote(null);
    setNoteError("");
    setPanel("note");
    if (!evidence) graph.current?.focus(id);
  };
  const openPanel = (value: Panel) => {
    if (leave()) {
      if (!panel) panelTrigger.current = document.activeElement as HTMLElement;
      setPanel(value);
      if (value === "ask") setWidth(420);
    }
  };
  const showGraph = async (scope: { note_id?: string; entity_id?: string }) => {
    try {
      const result = await api.graph(scope);
      setClaims(result);
      setView("graph");
      if (!result.edges.length)
        setNotice("Bu kapsamda yayımlanmış bir ilişki bulunamadı.");
    } catch (e) {
      setNotice(errorText(e));
    }
  };
  const selectSearch = (result: SearchResult) => {
    if (!leave()) return;
    setSearch(false);
    if (result.kind === "note") openNote(result.id);
    else if (result.kind === "topic") {
      filter(result.id, "");
      setClaims(null);
      setView("graph");
    } else {
      setPanel(null);
      void showGraph({ entity_id: result.id });
    }
  };
  const changeView = (next: View) => {
    if (leave()) {
      if (panel === "edit" || panel === "create") setPanel(null);
      setView(next);
    }
  };
  const beginEdit = async () => {
    if (!note) return;
    try {
      const current = await api.revision(
        note.note_id,
        note.desired_revision_id,
      );
      setRevision(current);
      setSource(null);
      setPanel("edit");
    } catch (e) {
      setNoteError(errorText(e));
    }
  };
  const labels: Record<Exclude<Panel, null>, string> = {
    note: source ? "Kaynak" : "Not",
    edit: "Notu düzenle",
    create: "Yeni not",
    ask: "Notlarına sor",
    system: "Sistem",
    topics: "Konuları düzenle",
    link: "Bağlantı",
  };
  const modeLabel = status
    ? `${status.mode.startsWith("neo4j") ? "Kalıcı" : "Geçici"} / ${status.mode.endsWith("demo") ? "Demo" : "Yerel model"}`
    : "Bağlantı kontrol ediliyor";
  const currentTopic = topics.find((t) => t.topic_id === topicId);
  const chooseTopic = (id: string) => {
    graph.current?.focusTopic(id);
    filter(id);
    setClaims(null);
  };

  const moveNote = async (n: Note, destination: string) => {
    const target = destination === "unsorted" ? null : destination;
    if (moving.current || (n.topic_id || null) === target || !leave()) return;
    if (panel === "edit" || panel === "create") setPanel(null);
    moving.current = true;
    setMovingId(n.note_id);
    try {
      // Use the displayed version: a conflicting move must never silently overwrite it.
      await api.assignTopic(n, target);
      setNotice(
        `“${n.title}” ${topics.find((t) => t.topic_id === target)?.name || "Düzenlenmemiş"} konusuna taşındı.`,
      );
    } catch (e) {
      setNotice(errorText(e));
    } finally {
      await refresh();
      moving.current = false;
      setMovingId(null);
    }
  };
  const noteRows = (notes: Note[]) =>
    notes.map((n) => (
      <div
        className={
          "note-table-row" +
          (selectedId === n.note_id ? " selected-row" : "") +
          (draggedId === n.note_id ? " dragging" : "")
        }
        key={n.note_id}
        data-note-id={n.note_id}
        aria-busy={movingId === n.note_id}
        draggable={!movingId}
        onDragStart={(e) => {
          if ((e.target as HTMLElement).closest("select")) {
            e.preventDefault();
            return;
          }
          draggedNote.current = { ...n };
          setDraggedId(n.note_id);
          e.dataTransfer.setData("application/x-graphrag-note", n.note_id);
          e.dataTransfer.effectAllowed = "move";
        }}
        onDragEnd={() => {
          draggedNote.current = null;
          setDraggedId(null);
          setDropTopic(null);
        }}
        onClick={() => openNote(n.note_id)}
      >
        <button
          className="note-name note-open"
          onClick={(e) => {
            e.stopPropagation();
            openNote(n.note_id);
          }}
        >
          <span className="drag-grip" aria-hidden="true">
            ⠿
          </span>
          <Icon name="note" size={15} />
          <span>{n.title || "Başlıksız not"}</span>
        </button>
        <span
          className="note-topic note-move-control"
          onClick={(e) => e.stopPropagation()}
        >
          <span
            className="color-dot"
            style={{
              background:
                colors[
                  topics.find((t) => t.topic_id === n.topic_id)?.color_key ||
                    "gray"
                ],
            }}
          />
          <select
            aria-label={`${n.title} için konu`}
            value={n.topic_id || "unsorted"}
            disabled={!!movingId}
            onChange={(e) => void moveNote(n, e.target.value)}
          >
            <option value="unsorted">Düzenlenmemiş</option>
            {topics.map((t) => (
              <option value={t.topic_id} key={t.topic_id}>
                {t.name}
              </option>
            ))}
          </select>
        </span>
        <StateLabel note={n} />
        <span className="note-date">{dateLabel(n.created_at)}</span>
      </div>
    ));
  const groups = [
    ...topics,
    {
      topic_id: "unsorted",
      name: "Düzenlenmemiş",
      color_key: "gray",
      note_count: map?.nodes.filter((n) => !n.topic_id).length || 0,
      version: 0,
    },
  ];

  return (
    <div
      className={"workspace" + (panel ? " with-panel" : "")}
      style={{ "--panel-width": width + "px" } as CSSProperties}
    >
      <header className="topbar">
        <div className="breadcrumb">
          <span>Bilgi alanı</span>
          <span className="slash">/</span>
          <strong>Notlar</strong>
        </div>
        <div className="top-actions">
          <button className="mode-button" onClick={() => openPanel("system")}>
            <span
              className={
                "status-dot " +
                (status?.worker.fresh &&
                ready?.ok &&
                status?.lm_studio.endpoint_reachable !== false
                  ? "online"
                  : "offline")
              }
            />
            <span>{modeLabel}</span>
          </button>
          <button onClick={() => openPanel("ask")}>
            <Icon name="ask" />
            Soru sor
          </button>
          <button
            className="primary"
            onClick={() => {
              openPanel("create");
              setSource(null);
            }}
          >
            <Icon name="plus" />
            Yeni not
          </button>
        </div>
      </header>
      <main className="workspace-body">
        <section className="main-pane" aria-label="Not çalışma alanı">
          <div className="toolbar">
            <nav className="view-tabs" aria-label="Not görünümü">
              {(["graph", "list", "topics"] as View[]).map((value, i) => (
                <button
                  key={value}
                  className={view === value ? "active" : ""}
                  aria-current={view === value ? "page" : undefined}
                  onClick={() => changeView(value)}
                >
                  <Icon name={["graph", "list", "folder"][i]} />
                  <span>{["Graf", "Liste", "Konular"][i]}</span>
                </button>
              ))}
            </nav>
            <button className="search-trigger" onClick={() => setSearch(true)}>
              <Icon name="search" />
              <span>Not veya varlık ara…</span>
              <kbd>Ctrl K</kbd>
            </button>
            {view === "graph" && !claims ? (
              <div className="layer-controls">
                <label>
                  <input
                    type="checkbox"
                    checked={showTopics}
                    onChange={(e) => setShowTopics(e.target.checked)}
                  />
                  <span className="toggle-track" />
                  <span>Konular</span>
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={showLinks}
                    onChange={(e) => setShowLinks(e.target.checked)}
                  />
                  <span className="toggle-track" />
                  <span>Bağlantılar</span>
                </label>
                <label
                  className="unavailable"
                  title="Notlar arası anlamsal benzerlik bu sürümde hesaplanmıyor."
                >
                  <input type="checkbox" disabled />
                  <span className="toggle-track" />
                  <span>Benzerlik</span>
                </label>
              </div>
            ) : (
              <span className="toolbar-spacer" />
            )}
            {view === "graph" && !claims && (
              <details className="layers-menu">
                <summary aria-label="Graf katmanları">
                  <Icon name="layers" />
                </summary>
                <div>
                  <label>
                    <input
                      type="checkbox"
                      checked={showTopics}
                      onChange={(e) => setShowTopics(e.target.checked)}
                    />
                    Konular
                  </label>
                  <label>
                    <input
                      type="checkbox"
                      checked={showLinks}
                      onChange={(e) => setShowLinks(e.target.checked)}
                    />
                    Bağlantılar
                  </label>
                  <label className="muted">
                    <input type="checkbox" disabled />
                    Benzerlik (henüz yok)
                  </label>
                </div>
              </details>
            )}
            {view === "graph" ? (
              <IconButton
                icon="fit"
                label="Haritayı ekrana sığdır"
                onClick={() => graph.current?.fit()}
              />
            ) : (
              <button
                className="text-button topics-manage"
                onClick={() => openPanel("topics")}
              >
                Konuları düzenle
              </button>
            )}
          </div>
          {(topicId || q || claims) && (
            <div className="scope-bar">
              {claims ? (
                <button className="text-button" onClick={() => setClaims(null)}>
                  <Icon name="arrow" />
                  Not haritasına dön
                </button>
              ) : (
                <>
                  <span>
                    {q ? `“${q}”` : currentTopic?.name || "Düzenlenmemiş"}
                  </span>
                  <button
                    className="text-button"
                    onClick={() => filter("", "")}
                  >
                    Filtreleri temizle
                  </button>
                </>
              )}
            </div>
          )}
          {error && (
            <div className="connection-banner">
              <ErrorMessage
                message={
                  error + (map ? " Son görünüm güncel olmayabilir." : "")
                }
                retry={() => void refresh()}
              />
            </div>
          )}
          {notice && (
            <div className="notice" role="status">
              <span>{notice}</span>
              <IconButton
                icon="close"
                label="Bildirimi kapat"
                onClick={() => setNotice("")}
              />
            </div>
          )}
          <div
            className={"graph-view" + (view === "graph" ? "" : " is-hidden")}
          >
            <Graph
              ref={graph}
              map={map}
              claims={claims}
              selected={selectedId}
              answerFocus={answerFocus}
              onClearFocus={() => setAnswerFocus(null)}
              showTopics={showTopics}
              showLinks={showLinks}
              visible={view === "graph"}
              onNote={(id) => openNote(id)}
              onTopic={chooseTopic}
              onLink={(edge) => {
                if (leave()) {
                  setLink(edge);
                  setPanel("link");
                }
              }}
              onEvidence={(ev) => openNote(ev.note_id, ev)}
            />
            {map && !map.nodes.length && !claims && !loading && (
              <div className="empty-state">
                <Icon name="graph" size={34} />
                <h1>
                  {q || topicId ? "Bu görünümde not yok" : "İlk notunu ekle"}
                </h1>
                <p>
                  {q || topicId
                    ? "Filtreleri temizle veya bu konuya bir not ekle."
                    : "Notların arasında bağlantılar kurmaya başla."}
                </p>
                <button className="primary" onClick={() => openPanel("create")}>
                  <Icon name="plus" />
                  Yeni not
                </button>
                {(q || topicId) && (
                  <button
                    className="text-button"
                    onClick={() => filter("", "")}
                  >
                    Filtreleri temizle
                  </button>
                )}
              </div>
            )}
            {loading && (
              <div className="map-loading" role="status">
                Notlar yükleniyor…
              </div>
            )}
            {!claims && !!map?.nodes.length && (
              <div className="graph-legend" aria-label="Konu renkleri">
                {groups
                  .filter(
                    (t) =>
                      t.note_count > 0 ||
                      map.nodes.some(
                        (n) => (n.topic_id || "unsorted") === t.topic_id,
                      ),
                  )
                  .map((t) => (
                    <button
                      key={t.topic_id}
                      className={topicId === t.topic_id ? "active" : ""}
                      onClick={() => chooseTopic(t.topic_id)}
                    >
                      <span
                        className="color-dot"
                        style={{ background: "#EF7077" }}
                      />
                      {t.name}
                    </button>
                  ))}
                <span className="legend-line">Ortak varlık</span>
              </div>
            )}
            <div className="graph-help">
              <div className="zoom-controls">
                <IconButton
                  icon="minus"
                  label="Uzaklaştır"
                  onClick={() => graph.current?.zoom(-0.2)}
                />
                <IconButton
                  icon="plus"
                  label="Yakınlaştır"
                  onClick={() => graph.current?.zoom(0.2)}
                />
              </div>
              <span>Sürükle: taşı · Tekerlek: yakınlaştır</span>
              <small>Bir not seçerek ayrıntıları aç</small>
            </div>
            {map?.limited && !claims && (
              <div className="map-limit">
                <span>
                  {map.nodes.length} / {map.total} not gösteriliyor
                  {map.edges_limited ? "; bağlantılar sınırlandı" : ""}.
                  {map.relations_limited
                    ? " Kaynak ilişkilerinin bir bölümü gösteriliyor; ayrıntı için not seç."
                    : ""}
                </span>
                {mapIndex > 0 && (
                  <button onClick={() => setMapIndex((i) => i - 1)}>
                    Önceki bölüm
                  </button>
                )}
                {map.next_cursor && (
                  <button
                    onClick={() => {
                      setMapCursors((c) => [
                        ...c.slice(0, mapIndex + 1),
                        map.next_cursor!,
                      ]);
                      setMapIndex((i) => i + 1);
                    }}
                  >
                    Sonraki bölüm
                  </button>
                )}
                <span>Bir konu seçerek daralt.</span>
              </div>
            )}
          </div>
          {view === "list" && (
            <div className="list-view">
              <div className="list-filter">
                <label className="sr-only" htmlFor="topic-filter">
                  Konu filtresi
                </label>
                <select
                  id="topic-filter"
                  value={topicId}
                  onChange={(e) => filter(e.target.value)}
                >
                  <option value="">Tüm konular</option>
                  <option value="unsorted">Düzenlenmemiş</option>
                  {topics.map((t) => (
                    <option key={t.topic_id} value={t.topic_id}>
                      {t.name}
                    </option>
                  ))}
                </select>
                <span>{page.total} not</span>
              </div>
              <div
                className="topic-transfer"
                aria-label="Konu taşıma hedefleri"
              >
                <p>
                  Notu bir konuya sürükle veya satırdaki konu seçimini kullan.
                </p>
                <div className="topic-drop-targets">
                  {groups.map((t) => (
                    <button
                      key={t.topic_id}
                      data-topic-drop={t.topic_id}
                      className={
                        "topic-drop" +
                        (dropTopic === t.topic_id ? " drop-active" : "") +
                        (topicId === t.topic_id ? " active" : "")
                      }
                      aria-label={`Konu: ${t.name}`}
                      title="Notu buraya bırak; filtrelemek için tıkla"
                      onClick={() => filter(t.topic_id)}
                      onDragOver={(e) => {
                        if (draggedNote.current && !moving.current) {
                          e.preventDefault();
                          e.dataTransfer.dropEffect = "move";
                          setDropTopic(t.topic_id);
                        }
                      }}
                      onDragLeave={(e) => {
                        if (!e.currentTarget.contains(e.relatedTarget as Node))
                          setDropTopic(null);
                      }}
                      onDrop={(e) => {
                        e.preventDefault();
                        const n = draggedNote.current;
                        const id = e.dataTransfer.getData(
                          "application/x-graphrag-note",
                        );
                        draggedNote.current = null;
                        setDraggedId(null);
                        setDropTopic(null);
                        if (n && id === n.note_id) void moveNote(n, t.topic_id);
                      }}
                    >
                      <span
                        className="color-dot"
                        style={{
                          background: colors[t.color_key] || colors.gray,
                        }}
                      />
                      {t.name}
                      <small>{t.note_count}</small>
                    </button>
                  ))}
                </div>
              </div>
              <div
                className="note-table"
                role="region"
                aria-label="Not listesi"
              >
                <div className="note-table-head">
                  <span>Ad</span>
                  <span>Konu</span>
                  <span>Durum</span>
                  <span>Eklenme</span>
                </div>
                {noteRows(page.items)}
                {!page.items.length && !loading && (
                  <div className="list-empty">
                    Not bulunamadı.
                    <button onClick={() => openPanel("create")}>
                      Yeni not
                    </button>
                  </div>
                )}
              </div>
              <div className="pagination">
                <span>
                  {page.total
                    ? `${pageIndex * 50 + 1}–${pageIndex * 50 + page.items.length} / ${page.total} not`
                    : "0 not"}
                </span>
                <div>
                  <button
                    disabled={pageIndex === 0}
                    onClick={() => setPageIndex((i) => i - 1)}
                  >
                    Önceki
                  </button>
                  <button
                    disabled={!page.next_cursor}
                    onClick={() => {
                      setCursors((c) => [
                        ...c.slice(0, pageIndex + 1),
                        page.next_cursor!,
                      ]);
                      setPageIndex((i) => i + 1);
                    }}
                  >
                    Sonraki
                  </button>
                </div>
              </div>
            </div>
          )}
          {view === "topics" && (
            <div className="topics-view">
              <div className="topics-heading">
                <p>Konulara göre notlar</p>
                <button onClick={() => openPanel("topics")}>
                  <Icon name="plus" />
                  Konu oluştur
                </button>
              </div>
              {groups.map((t) => (
                <TopicGroup
                  key={t.topic_id}
                  topic={t}
                  expanded={expanded.has(t.topic_id)}
                  onToggle={() =>
                    setExpanded((current) => {
                      const next = new Set(current);
                      if (next.has(t.topic_id)) next.delete(t.topic_id);
                      else next.add(t.topic_id);
                      return next;
                    })
                  }
                  onNote={(id) => openNote(id)}
                  refreshKey={map?.metadata_version + ":" + map?.graph_version}
                />
              ))}
              {!topics.length && (
                <p className="form-hint">
                  Bir konu oluşturup not panelinden atayabilirsin.
                </p>
              )}
            </div>
          )}
          {view !== "graph" && claims && (
            <ClaimsList
              graph={claims}
              onEvidence={(ev) => openNote(ev.note_id, ev)}
            />
          )}
        </section>
        {panel && (
          <aside className="detail-panel" aria-label={labels[panel]}>
            <div
              className="panel-resizer"
              role="separator"
              aria-label="Detay panelinin genişliği"
              aria-orientation="vertical"
              aria-valuenow={width}
              aria-valuemin={340}
              aria-valuemax={520}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "ArrowLeft") {
                  e.preventDefault();
                  setWidth((w) => Math.min(520, w + 20));
                }
                if (e.key === "ArrowRight") {
                  e.preventDefault();
                  setWidth((w) => Math.max(340, w - 20));
                }
              }}
              onPointerDown={(e) => {
                e.currentTarget.setPointerCapture(e.pointerId);
              }}
              onPointerMove={(e) => {
                if (e.currentTarget.hasPointerCapture(e.pointerId))
                  setWidth(
                    Math.max(340, Math.min(520, window.innerWidth - e.clientX)),
                  );
              }}
            />
            <div className="panel-heading">
              <span>{labels[panel]}</span>
              <IconButton
                icon="close"
                label="Paneli kapat"
                onClick={() => {
                  if (leave()) setPanel(null);
                }}
              />
            </div>
            {noteError && (panel === "note" || panel === "edit") && (
              <ErrorMessage
                message={noteError}
                retry={() => refreshNote.current()}
              />
            )}
            {panel === "note" &&
              (note ? (
                <NotePanel
                  note={note}
                  revision={revision}
                  evidence={source}
                  topics={topics}
                  onEdit={() => void beginEdit()}
                  onRefresh={() => void refresh()}
                  onDeleted={() => {
                    setPanel(null);
                    setSelectedId(null);
                    void refresh();
                  }}
                  onGraph={() => void showGraph({ note_id: note.note_id })}
                />
              ) : (
                !noteError && (
                  <div className="panel-scroll muted" role="status">
                    Not yükleniyor…
                  </div>
                )
              ))}
            {(panel === "edit" || panel === "create") && (
              <Editor
                key={panel + (panel === "edit" ? selectedId : "")}
                note={panel === "edit" ? note : null}
                revision={panel === "edit" ? revision : null}
                topics={topics}
                onDirty={onDirty}
                onSaved={(id, warning) => {
                  setNotice(warning || "Not kaydedildi; işleme alındı.");
                  setPanel(null);
                  openNote(id);
                  void refresh();
                }}
                onCancel={() => {
                  if (leave())
                    setPanel(note && panel === "edit" ? "note" : null);
                }}
              />
            )}
            {panel === "topics" && (
              <TopicPanel topics={topics} onRefresh={() => void refresh()} />
            )}
            {panel === "ask" && (
              <AskPanel
                answer={answer}
                onAnswer={(result) => {
                  setAnswer(result);
                  setAnswerFocus(result);
                  setClaims(null);
                  setSelectedId(null);
                  filter("", "");
                  setView("graph");
                }}
                onStart={() => setAnswerFocus(null)}
                onGraph={(g) => {
                  setClaims(g);
                  setView("graph");
                }}
                onBack={() => {
                  setClaims(null);
                  setAnswerFocus(null);
                }}
              />
            )}
            {panel === "system" && (
              <SystemPanel
                status={status}
                ready={ready}
                onRefresh={() => void refresh()}
              />
            )}
            {panel === "link" && link && (
              <div className="panel-scroll">
                <h1 className="panel-title">Ortak varlıklar</h1>
                <p className="muted">
                  Bu notlar aynı varlıklardan söz ediyor. Bu bağlantı, aynı
                  iddiayı doğruladıkları anlamına gelmez.
                </p>
                <div className="shared-entities">
                  {link.entities.map((e) => (
                    <button
                      key={e.entity_id}
                      onClick={() => void showGraph({ entity_id: e.entity_id })}
                    >
                      <Icon name="graph" />
                      {e.name}
                    </button>
                  ))}
                </div>
                <h2 className="section-title">Bağlı notlar</h2>
                {[link.source, link.target].map((id) => (
                  <button
                    key={id}
                    className="linked-note"
                    onClick={() => openNote(id)}
                  >
                    <Icon name="note" />
                    {map?.nodes.find((n) => n.note_id === id)?.title ||
                      "Notu aç"}
                  </button>
                ))}
              </div>
            )}
          </aside>
        )}
      </main>
      {search && (
        <Search
          onClose={() => setSearch(false)}
          onSelect={selectSearch}
          onCreate={() => {
            setSearch(false);
            openPanel("create");
          }}
          onList={(query) => {
            if (leave()) {
              setSearch(false);
              setPanel(null);
              filter("", query);
              setView("list");
            }
          }}
        />
      )}
    </div>
  );
}

function TopicGroup({
  topic,
  expanded,
  onToggle,
  onNote,
  refreshKey,
}: {
  topic: Topic;
  expanded: boolean;
  onToggle(): void;
  onNote(id: string): void;
  refreshKey: string;
}) {
  const [page, setPage] = useState<NotePage | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false);
  const load = useCallback(
    async (cursor?: string) => {
      setLoading(true);
      try {
        const r = await api.notes(topic.topic_id, "", cursor);
        setPage((previous) =>
          cursor && previous
            ? { ...r, items: [...previous.items, ...r.items] }
            : r,
        );
        setError("");
      } catch (e) {
        setError(errorText(e));
      } finally {
        setLoading(false);
      }
    },
    [topic.topic_id],
  );
  useEffect(() => {
    if (expanded) void load();
  }, [expanded, load, refreshKey]);
  return (
    <div className="topic-group">
      <button
        className="topic-group-heading"
        onClick={onToggle}
        aria-expanded={expanded}
      >
        <span className={"topic-chevron" + (expanded ? " expanded" : "")}>
          <Icon name="chevron" size={14} />
        </span>
        <span
          className="color-dot"
          style={{ background: colors[topic.color_key] }}
        />
        <strong>{topic.name}</strong>
        <span>
          {page?.total ??
            (topic.topic_id === "unsorted" ? "" : topic.note_count)}
        </span>
      </button>
      {expanded && (
        <div className="topic-group-notes">
          {error && <ErrorMessage message={error} retry={() => void load()} />}
          {page?.items.map((n) => (
            <button key={n.note_id} onClick={() => onNote(n.note_id)}>
              <Icon name="note" size={14} />
              <span>{n.title || "Başlıksız not"}</span>
              <StateLabel note={n} />
            </button>
          ))}
          {!page?.items.length && !loading && (
            <p className="form-hint">Bu konuda not yok.</p>
          )}
          {loading && (
            <p className="form-hint" role="status">
              Yükleniyor…
            </p>
          )}
          {page?.next_cursor && (
            <button
              onClick={() => void load(page.next_cursor!)}
              disabled={loading}
            >
              Sonraki notları yükle
            </button>
          )}
        </div>
      )}
    </div>
  );
}
