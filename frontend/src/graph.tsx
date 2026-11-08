import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import cytoscape from "cytoscape";
import type { Core, ElementDefinition, NodeSingular } from "cytoscape";
import type {
  Answer,
  ClaimGraph,
  Evidence,
  MapData,
  SharedEdge,
} from "./types";
import { applyAnswerFocus, nodeSize } from "./graphFocus";
import {
  graphPalette,
  graphStyle,
  pointColor,
  fitOverview,
  packComponents,
} from "./graphTheme";

export const colors: Record<string, string> = {
  purple: "#A683C9",
  blue: "#529BD3",
  teal: "#46AAA3",
  orange: "#D78C4B",
  pink: "#C86694",
  green: "#5B9F77",
  yellow: "#C5AC39",
  gray: "#9A9A98",
};
export interface GraphHandle {
  fit(): void;
  focus(id: string): void;
  zoom(delta: number): void;
  focusTopic(id: string): void;
}
type Point = { x: number; y: number };
type Props = {
  map: MapData | null;
  claims: ClaimGraph | null;
  selected: string | null;
  answerFocus: Answer | null;
  onClearFocus(): void;
  onShowTopics(value: boolean): void;
  onShowLinks(value: boolean): void;
  showTopics: boolean;
  showLinks: boolean;
  visible: boolean;
  onNote(id: string): void;
  onTopic(id: string): void;
  onLink(edge: SharedEdge): void;
  onEvidence(evidence: Evidence): void;
};
const anchors = [
  [440, 260],
  [840, 610],
  [990, 355],
  [280, 550],
  [500, 750],
  [125, 365],
  [1060, 150],
  [1100, 700],
];
const hash = (s: string) =>
  [...s].reduce((n, c) => (n * 31 + c.charCodeAt(0)) >>> 0, 0);
const roleColors = {
  topic: graphPalette.hub,
  note: graphPalette.note,
  entity: graphPalette.entity,
};
const caption = (text: string) => {
  const value = text.replace(/_/g, " ");
  return value.length > 42 ? value.slice(0, 39) + "…" : value;
};
const Graph = forwardRef<GraphHandle, Props>(function Graph(props, ref) {
  const host = useRef<HTMLDivElement>(null),
    cyRef = useRef<Core | null>(null);
  const latest = useRef(props);
  latest.current = props;
  const positions = useRef(new Map<string, Point>()),
    firstFit = useRef(false);
  const structure = useRef("");
  const [seriesCount, setSeriesCount] = useState(0);
  const [showLabels, setShowLabels] = useState(false);
  const [showArrows, setShowArrows] = useState(false);
  const [nodeScale, setNodeScale] = useState(1);
  const [lineOpacity, setLineOpacity] = useState(0.24);
  const display = useRef({ labels: false, arrows: false });
  display.current = { labels: showLabels, arrows: showArrows };
  const syncDisplay = () => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.elements().toggleClass(
        "labels-visible",
        display.current.labels || cy.zoom() >= 1.65,
      );
      cy.edges().toggleClass("show-arrows", display.current.arrows);
    });
  };
  const [focusCounts, setFocusCounts] = useState({ highlighted: 0, dimmed: 0 });
  const cameras = useRef(new Map<string, { pan: Point; zoom: number }>()),
    layer = useRef("notes");
  const pendingFocus = useRef<string | null>(null);
  const applyFocus = () => {
    const cy = cyRef.current,
      id = pendingFocus.current;
    if (!cy || !id || !latest.current.visible || !host.current?.clientWidth)
      return;
    const node = cy.getElementById("note:" + id);
    if (!node.length) return;
    cy.resize();
    const p = node.position(),
      zoom = Math.max(cy.zoom(), 2.2);
    cy.viewport({
      zoom,
      pan: { x: cy.width() / 2 - p.x * zoom, y: cy.height() / 2 - p.y * zoom },
    });
    pendingFocus.current = null;
  };
  const [tooltip, setTooltip] = useState<{
    text: string;
    x: number;
    y: number;
  } | null>(null);
  useImperativeHandle(ref, () => ({
    fit: () => {
      if (cyRef.current) fitOverview(cyRef.current);
    },
    focus: (id) => {
      pendingFocus.current = id;
      requestAnimationFrame(() => requestAnimationFrame(applyFocus));
    },
    focusTopic: (id) => {
      const cy = cyRef.current,
        node = cy?.getElementById("topic:" + id);
      if (cy && node?.length) cy.fit(node.closedNeighborhood(), 90);
    },
    zoom: (delta) => {
      const cy = cyRef.current;
      if (cy)
        cy.zoom({
          level: Math.max(0.2, Math.min(8, cy.zoom() + delta)),
          renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
        });
    },
  }));
  useEffect(() => {
    if (!host.current) return;
    const cy = cytoscape({
      container: host.current,
      elements: [],
      minZoom: 0.15,
      maxZoom: 8,
      wheelSensitivity: 0.22,
      boxSelectionEnabled: false,
      style: graphStyle,
      layout: { name: "preset" },
    });
    cyRef.current = cy;
    cy.on("zoom", syncDisplay);
    cy.on("tap", "node", (e) => {
      const n = e.target as NodeSingular;
      if (n.data("kind") === "note") latest.current.onNote(n.data("noteId"));
      if (n.data("kind") === "topic") latest.current.onTopic(n.data("rawId"));
      if (n.data("kind") === "collection")
        latest.current.onNote(n.data("noteId"));
      if (n.data("kind") === "entity") {
        const evidence = n
          .connectedEdges()
          .filter((e) => !!e.data("evidence"))
          .first()
          .data("evidence");
        if (evidence) latest.current.onEvidence(evidence);
      }
    });
    cy.on("tap", "edge", (e) => {
      if (e.target.data("evidence")) {
        latest.current.onEvidence(e.target.data("evidence"));
        return;
      }
      const id = e.target.id();
      if (latest.current.claims) {
        const c = latest.current.claims.edges.find((edge) => edge.id === id);
        if (c) latest.current.onEvidence(c.evidence);
      } else {
        const edge = latest.current.map?.edges.find((edge) => edge.id === id);
        if (edge) latest.current.onLink(edge);
      }
    });
    cy.on("mouseover", "node, edge", (e) => {
      const el = e.target;
      el.addClass("hovered");
      const p = e.renderedPosition || el.renderedPosition();
      const label = el.isNode()
        ? el.data("label")
        : el.data("kind") === "shared_entity"
          ? "Ortak varlık: " +
            (latest.current.map?.edges
              .find((v) => v.id === el.id())
              ?.entities.map((v) => v.name)
              .join(", ") || "")
          : String(el.data("label") || "Kaynak bağlantısı");
      setTooltip({ text: label, x: p.x, y: p.y });
      if (host.current) host.current.style.cursor = "pointer";
    });
    cy.on("mouseout", "node, edge", (e) => {
      e.target.removeClass("hovered");
      setTooltip(null);
      if (host.current) host.current.style.cursor = "grab";
    });
    let previous: Point | null = null;
    cy.on("grab", 'node[kind = "topic"]', (e) => {
      previous = { ...e.target.position() };
    });
    cy.on("drag", 'node[kind = "topic"]', (e) => {
      const n = e.target;
      const p = n.position();
      if (previous) {
        const dx = p.x - previous.x,
          dy = p.y - previous.y;
        cy.nodes('[kind = "note"]')
          .filter((v) => v.data("topicId") === n.id())
          .forEach((v) => {
            const old = v.position();
            v.position({ x: old.x + dx, y: old.y + dy });
          });
      }
      previous = { ...p };
    });
    cy.on("dragfree", "node", () => {
      cy.nodes().forEach((n) => {
        positions.current.set(n.id(), { ...n.position() });
      });
    });
    const observer = new ResizeObserver(() => {
      cy.resize();
    });
    observer.observe(host.current);
    return () => {
      observer.disconnect();
      cy.destroy();
      cyRef.current = null;
    };
    // The instance persists across panel changes, polling and list/graph switches.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(syncDisplay, [showLabels, showArrows]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const nextLayer = props.claims ? "claims" : "notes";
    if (nextLayer !== layer.current) {
      cameras.current.set(layer.current, {
        pan: { ...cy.pan() },
        zoom: cy.zoom(),
      });
      layer.current = nextLayer;
      firstFit.current = false;
    }
    const elements: ElementDefinition[] = [];
    if (props.claims) {
      const nodes = props.claims.nodes;
      nodes.forEach((n, i) => {
        const a = (i / Math.max(nodes.length, 1)) * Math.PI * 2;
        elements.push({
          data: {
            id: n.id,
            label: n.label,
            kind: "entity",
            color: Object.values(colors)[i % 7],
          },
          position: positions.current.get("claim:" + n.id) || {
            x: 600 + Math.cos(a) * Math.min(300, nodes.length * 45),
            y: 380 + Math.sin(a) * 200,
          },
        });
      });
      props.claims.edges.forEach((e) =>
        elements.push({
          data: {
            ...e,
            kind: "claim",
            label: `${predicate(e.predicate)}${e.polarity === "NEGATED" ? " (değil)" : ""}${e.modality !== "ASSERTED" ? ` · ${modality(e.modality)}` : ""}`,
          },
        }),
      );
    } else if (props.map) {
      const groups = new Map<string, typeof props.map.nodes>();
      for (const n of props.map.nodes) {
        const key = n.topic_id || "unsorted";
        groups.set(key, [...(groups.get(key) || []), n]);
      }
      const topics = [
        ...props.map.topics,
        {
          topic_id: "unsorted",
          name: "Düzenlenmemiş",
          color_key: "gray",
          note_count: groups.get("unsorted")?.length || 0,
          version: 0,
        },
      ];
      topics.forEach((topic) => {
        const notes = groups.get(topic.topic_id);
        if (!notes?.length) return;
        const color = colors[topic.color_key] || colors.gray,
          id = "topic:" + topic.topic_id;
        const existing = cy.getElementById(id);
        let center =
          positions.current.get(id) ||
          (existing.length ? existing.position() : null);
        if (!center) {
          const occupied = [...positions.current.entries()]
            .filter(([key]) => key.startsWith("topic:"))
            .map(([, value]) => value);
          const preferred =
            (
              {
                purple: 0,
                blue: 1,
                orange: 2,
                teal: 3,
                pink: 4,
                green: 5,
                gray: 6,
                yellow: 7,
              } as Record<string, number>
            )[topic.color_key] ?? 0;
          const candidates =
            topic.topic_id === "unsorted"
              ? [anchors[6]]
              : [
                  anchors[preferred],
                  ...anchors.filter(
                    (_, index) => index !== 6 && index !== preferred,
                  ),
                ];
          const anchor = candidates.find(
            (a) =>
              !occupied.some((p) => Math.hypot(p.x - a[0], p.y - a[1]) < 150),
          );
          const fallback = (hash(id) / 4294967296) * Math.PI * 2;
          center = anchor
            ? { x: anchor[0], y: anchor[1] }
            : {
                x: 600 + Math.cos(fallback) * 700,
                y: 420 + Math.sin(fallback) * 500,
              };
          positions.current.set(id, center);
        }
        elements.push({
          data: {
            id,
            topicId: id,
            rawId: topic.topic_id,
            label: topic.name + "\n" + notes.length + " not",
            kind: "topic",
            color,
            size: Math.min(76, 30 + Math.sqrt(notes.length) * 8),
          },
          position: center,
        });
        notes.forEach((n, i) => {
          const angle = i * 2.399963 + (hash(n.note_id) % 10) / 10;
          const radius = 52 + Math.sqrt(i) * 18;
          const oldNode = cy.getElementById("note:" + n.note_id);
          if (oldNode.length && oldNode.data("topicId") !== id)
            positions.current.delete("note:" + n.note_id);
          elements.push({
            data: {
              id: "note:" + n.note_id,
              noteId: n.note_id,
              topicId: id,
              kind: "note",
              label: n.title || "Başlıksız not",
              color,
              state: n.state,
            },
            position: positions.current.get("note:" + n.note_id) || {
              x: center.x + Math.cos(angle) * radius,
              y: center.y + Math.sin(angle) * radius,
            },
          });
          elements.push({
            data: {
              id: "member:" + n.note_id,
              source: id,
              target: "note:" + n.note_id,
              kind: "membership",
              label: "KONU",
              color,
            },
          });
        });
      });
      const collections = new Map<string, typeof props.map.nodes>();
      props.map.nodes.forEach((n) => {
        const match = n.title.match(
          /^(.+?)[_\-](?:bolum|bölüm|part|chapter|section)[_\-]\d+$/iu,
        );
        if (!match) return;
        const key =
          (n.topic_id || "unsorted") +
          ":" +
          match[1].toLocaleLowerCase("tr-TR");
        collections.set(key, [...(collections.get(key) || []), n]);
      });
      collections.forEach((notes, key) => {
        if (notes.length < 2) return;
        const id = "collection:" + key;
        const name = notes[0].title
          .replace(/[_\-](?:bolum|bölüm|part|chapter|section)[_\-]\d+$/iu, "")
          .replace(/^\d+[_\-]/, "")
          .replace(/_/g, " ");
        elements.push({
          data: {
            id,
            label: `${name}\n${notes.length} bölüm`,
            kind: "collection",
            noteId: notes[0].note_id,
          },
          position: positions.current.get(id) || { x: 650, y: 450 },
        });
        notes.forEach((n) =>
          elements.push({
            data: {
              id: "section:" + n.note_id,
              source: "note:" + n.note_id,
              target: id,
              kind: "collection_link",
              label: "BÖLÜMÜ",
            },
          }),
        );
      });
      (props.map.relations?.length ? [] : props.map.edges).forEach((e) =>
        elements.push({
          data: {
            ...e,
            source: "note:" + e.source,
            target: "note:" + e.target,
            label: "ORTAK VARLIK",
          },
        }),
      );
      const entities = props.map.entities || [];
      entities.forEach((e, i) => {
        const a = i * 2.399963;
        elements.push({
          data: { id: "entity:" + e.id, label: e.label, kind: "entity" },
          position: positions.current.get("entity:" + e.id) || {
            x: 650 + Math.cos(a) * (210 + Math.sqrt(i) * 25),
            y: 420 + Math.sin(a) * (160 + Math.sqrt(i) * 20),
          },
        });
      });
      const evidenceKeys = new Set<string>();
      (props.map.relations || []).forEach((e) => {
        elements.push({
          data: {
            ...e,
            id: "relation:" + e.id,
            source: "entity:" + e.source,
            target: "entity:" + e.target,
            kind: "claim",
            label:
              e.predicate +
              (e.polarity === "NEGATED" ? " (DEĞİL)" : "") +
              (e.modality !== "ASSERTED" ? ` · ${modality(e.modality)}` : ""),
          },
        });
        const key = e.evidence.note_id + ":" + e.source;
        if (!evidenceKeys.has(key)) {
          evidenceKeys.add(key);
          elements.push({
            data: {
              id: "source:" + key,
              source: "note:" + e.evidence.note_id,
              target: "entity:" + e.source,
              kind: "evidence",
              label: "KAYNAK",
              evidence: e.evidence,
            },
          });
        }
      });
    }
    const degrees = new Map<string, number>();
    elements.forEach((e) => {
      for (const id of [e.data.source, e.data.target]) {
        if (id) degrees.set(id, (degrees.get(id) || 0) + 1);
      }
    });
    elements.forEach((e) => {
      if (!e.data.source) {
        const degree = degrees.get(e.data.id!) || 0;
        e.data.baseSize = nodeSize(String(e.data.kind), degree);
        e.data.size = e.data.baseSize * nodeScale;
        e.data.caption = caption(String(e.data.label || ""));
        e.data.color = pointColor(String(e.data.kind), degree, e.data.color);
      } else {
        e.data.alpha = lineOpacity;
      }
    });
    const count = elements.filter((e) => e.data.kind === "collection").length;
    setSeriesCount((previous) => (previous === count ? previous : count));
    const ids = new Set(elements.map((e) => e.data.id));
    cy.batch(() => {
      cy.elements()
        .filter((e) => !ids.has(e.id()))
        .remove();
      for (const element of elements) {
        const old = cy.getElementById(element.data.id!);
        if (old.length) {
          const changedTopic =
            old.isNode() && old.data("topicId") !== element.data.topicId;
          old.data(element.data);
          if (changedTopic && element.position) old.position(element.position);
        } else cy.add(element);
      }
      cy.nodes('[kind = "topic"]').toggleClass("hidden", !props.showTopics);
      cy.edges('[kind = "membership"]').toggleClass(
        "hidden",
        !props.showTopics,
      );
      cy.edges('[kind = "shared_entity"]').toggleClass(
        "hidden",
        !props.showLinks,
      );
      cy.edges(
        '[kind = "claim"], [kind = "evidence"], [kind = "collection_link"]',
      ).toggleClass("hidden", !props.showLinks);
      cy.elements().removeClass(
        "selected dimmed focused answer-muted answer-related",
      );
      const selected = props.selected
        ? cy.getElementById("note:" + props.selected)
        : null;
      if (props.answerFocus) {
        const counts = applyAnswerFocus(cy, props.answerFocus);
        setFocusCounts((previous) =>
          previous.highlighted === counts.highlighted &&
          previous.dimmed === counts.dimmed
            ? previous
            : counts,
        );
      } else if (selected?.length && !props.claims) {
        const neighborhood = selected.closedNeighborhood();
        cy.elements().not(neighborhood).addClass("dimmed");
        selected.addClass("selected");
        neighborhood.nodes('[kind = "note"]').addClass("focused");
        neighborhood.edges().addClass("selected");
      }
    });
    const signature = elements
      .map((e) => `${e.data.id}:${e.data.source || ""}:${e.data.target || ""}`)
      .join("|");
    if (
      signature !== structure.current &&
      !cy.nodes().some((n) => (n as NodeSingular).grabbed())
    ) {
      structure.current = signature;
      cy.layout({
        name: "cose",
        animate: false,
        fit: false,
        randomize: false,
        nodeRepulsion: () => 1600,
        idealEdgeLength: () => 34,
        nodeOverlap: 5,
        numIter: 450,
        gravity: 0.65,
        componentSpacing: 36,
      }).run();
      packComponents(cy);
      cy.nodes().forEach((n) => {
        positions.current.set(n.id(), { ...n.position() });
      });
    }
    syncDisplay();
    if (cy.nodes().length && !firstFit.current && props.visible) {
      firstFit.current = true;
      const saved = cameras.current.get(layer.current);
      requestAnimationFrame(() => {
        cy.resize();
        if (saved) cy.viewport(saved);
        else fitOverview(cy);
      });
    }
  }, [
    props.map,
    props.claims,
    props.selected,
    props.answerFocus,
    props.showTopics,
    props.showLinks,
    props.visible,
    nodeScale,
    lineOpacity,
  ]);
  useEffect(() => {
    if (props.visible) {
      requestAnimationFrame(() => {
        cyRef.current?.resize();
        applyFocus();
      });
    }
  }, [props.visible]);

  return (
    <div
      className="graph-stage reference-graph"
      role="region"
      aria-label={props.claims ? "Kaynak ilişkileri grafı" : "Not haritası"}
      data-series-count={seriesCount}
      data-appearance="constellation"
      data-labels-enabled={showLabels}
      data-answer-focus={!!props.answerFocus}
      data-highlighted-nodes={props.answerFocus ? focusCounts.highlighted : 0}
      data-dimmed-nodes={props.answerFocus ? focusCounts.dimmed : 0}
    >
      <div ref={host} className="graph-canvas" aria-hidden="true" />
      <div className="graph-settings" aria-label="Graf görünüm ayarları">
        <details>
          <summary>Filtreler</summary>
          <label>
            <input
              type="checkbox"
              checked={props.showTopics}
              onChange={(e) => props.onShowTopics(e.target.checked)}
            />
            Konu merkezleri
          </label>
          <label>
            <input
              type="checkbox"
              checked={props.showLinks}
              onChange={(e) => props.onShowLinks(e.target.checked)}
            />
            Belge bağlantıları
          </label>
        </details>
        <details>
          <summary>Görünüm</summary>
          <label>
            <input
              type="checkbox"
              checked={showLabels}
              onChange={(e) => setShowLabels(e.target.checked)}
            />
            Düğüm adları
          </label>
          <label>
            <input
              type="checkbox"
              checked={showArrows}
              onChange={(e) => setShowArrows(e.target.checked)}
            />
            İlişki yönleri
          </label>
          <label className="graph-range">
            Düğüm boyutu
            <input
              aria-label="Düğüm boyutu"
              type="range"
              min="0.6"
              max="2.4"
              step="0.1"
              value={nodeScale}
              onChange={(e) => setNodeScale(Number(e.target.value))}
            />
          </label>
          <label className="graph-range">
            Bağlantı görünürlüğü
            <input
              aria-label="Bağlantı görünürlüğü"
              type="range"
              min="0.06"
              max="0.65"
              step="0.01"
              value={lineOpacity}
              onChange={(e) => setLineOpacity(Number(e.target.value))}
            />
          </label>
        </details>
      </div>
      <div className="graph-types" aria-label="Düğüm türleri">
        <span className="sr-only" aria-label="Graf özeti">
          {seriesCount} belge serisi
        </span>
        <span>
          <i style={{ background: roleColors.topic }} />
          Konu
        </span>
        <span>
          <i style={{ background: roleColors.note }} />
          Belge
        </span>
        <span>
          <i style={{ background: roleColors.entity }} />
          Varlık / seri
        </span>
      </div>
      {props.answerFocus && (
        <div className="answer-graph-focus" role="status">
          <span>
            {focusCounts.highlighted
              ? "Yanıtın kaynakları renkli; diğer düğümler sönük."
              : "Bu yanıtta haritada vurgulanacak kaynak bulunamadı."}
          </span>
          <button className="text-button" onClick={props.onClearFocus}>
            Vurguyu temizle
          </button>
        </div>
      )}
      {tooltip && (
        <div
          className="graph-tooltip"
          style={{
            left: Math.max(
              8,
              Math.min(tooltip.x, (host.current?.clientWidth || 1000) - 190),
            ),
            top: Math.max(8, tooltip.y - 40),
          }}
        >
          {tooltip.text}
        </div>
      )}
    </div>
  );
});
export default Graph;
export function predicate(value: string): string {
  return (
    (
      {
        WORKS_ON: "üzerinde çalışıyor",
        USES: "kullanıyor",
        PART_OF: "parçası",
        LOCATED_IN: "konumu",
        RELATED_TO: "ilişkili",
        KNOWS: "tanıyor",
        HAS_ROLE: "rolü",
      } as Record<string, string>
    )[value] || value
  );
}
export function modality(value: string): string {
  return (
    (
      {
        POSSIBLE: "olası",
        PLANNED: "planlanan",
        REPORTED: "aktarılan",
        ASSERTED: "belirtilen",
      } as Record<string, string>
    )[value] || value.toLowerCase()
  );
}
