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
const roleColors = { topic: "#EF7077", note: "#65B9EE", entity: "#526779" };
const caption = (text: string) => {
  const value = text.replace(/_/g, " ");
  return value.length > 42 ? value.slice(0, 39) + "…" : value;
};
const Graph = forwardRef<GraphHandle, Props>(function Graph(props, ref) {
  const host = useRef<HTMLDivElement>(null),
    canvas = useRef<HTMLCanvasElement>(null),
    cyRef = useRef<Core | null>(null);
  const latest = useRef(props);
  latest.current = props;
  const positions = useRef(new Map<string, Point>()),
    frame = useRef(0),
    firstFit = useRef(false);
  const structure = useRef("");
  const [seriesCount, setSeriesCount] = useState(0);
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
      zoom = Math.max(cy.zoom(), 1);
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
  const draw = () => {
    if (frame.current) return;
    frame.current = requestAnimationFrame(() => {
      frame.current = 0;
      const cy = cyRef.current,
        el = canvas.current,
        holder = host.current;
      if (!cy || !el || !holder) return;
      const box = holder.getBoundingClientRect(),
        dpr = Math.min(devicePixelRatio || 1, 2);
      if (
        el.width !== Math.round(box.width * dpr) ||
        el.height !== Math.round(box.height * dpr)
      ) {
        el.width = Math.round(box.width * dpr);
        el.height = Math.round(box.height * dpr);
      }
      const ctx = el.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, box.width, box.height);
    });
  };
  useImperativeHandle(ref, () => ({
    fit: () => {
      cyRef.current?.fit(undefined, 90);
      draw();
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
          level: Math.max(0.2, Math.min(3, cy.zoom() + delta)),
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
      maxZoom: 3.5,
      wheelSensitivity: 0.22,
      boxSelectionEnabled: false,
      style: [
        {
          selector: "node",
          style: {
            label: "data(caption)",
            color: "#18364C",
            "font-family": "Segoe UI, sans-serif",
            "font-size": 8.5,
            "text-valign": "center",
            "text-halign": "center",
            "text-margin-y": 0,
            "background-color": "data(color)",
            width: "data(size)",
            height: "data(size)",
            "text-wrap": "wrap",
            "text-max-width": "45px",
            "border-width": 1,
            "border-color": "#FFFFFF",
          },
        },
        {
          selector: 'node[kind = "topic"]',
          style: {
            "font-size": 13,
            color: "#421E25",
            "font-weight": 500,
            "z-index": 3,
            "text-wrap": "wrap",
            "text-max-width": "92px",
          },
        },
        {
          selector: "edge",
          style: {
            width: 0.8,
            "line-color": "#ADB8C6",
            opacity: 0.8,
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 8,
            color: "#BCC7D4",
            "text-rotation": "autorotate",
            "text-background-color": "#000000",
            "text-background-opacity": 0.9,
            "text-background-padding": "2px",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#ADB8C6",
            "arrow-scale": 0.55,
          },
        },
        {
          selector: 'edge[kind = "membership"]',
          style: { "line-color": "#B9C2CE", opacity: 0.75, width: 0.8 },
        },
        {
          selector: 'node[kind = "note"]',
          style: {
            "border-width": 1,
            "border-color": "data(color)",
            label: "data(caption)",
          },
        },
        {
          selector: "node.selected",
          style: {
            "border-color": "#163E61",
            "border-width": 2.5,
            "border-opacity": 1,
            label: "data(caption)",
            "z-index": 10,
          },
        },
        { selector: "node.focused", style: { label: "data(caption)" } },
        { selector: ".dimmed", style: { opacity: 0.26, "text-opacity": 0.35 } },
        {
          selector: "edge.selected",
          style: { opacity: 0.95, width: 1.5, "line-color": "#C6CAD2" },
        },
        {
          selector: 'edge[kind = "claim"]',
          style: {
            label: "data(label)",
            "font-size": 12,
            color: "#BCC7D4",
            "text-background-color": "#000000",
            "text-background-opacity": 1,
            "text-background-padding": "5px",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#AAAAAA",
            "curve-style": "bezier",
            opacity: 0.75,
            width: 1.3,
          },
        },
        {
          selector: 'edge[polarity = "NEGATED"]',
          style: {
            "line-style": "dashed",
            "line-color": "#D7AC7B",
            "target-arrow-color": "#D7AC7B",
          },
        },
        {
          selector: 'node[kind = "entity"], node[kind = "collection"]',
          style: {
            "font-size": 10,
            color: "#FFFFFF",
            "text-max-width": "76px",
            "text-margin-y": 0,
          },
        },
        {
          selector: "node.answer-related",
          style: {
            "border-width": 2.5,
            "border-color": "#B5DEFF",
            "z-index": 12,
          },
        },
        {
          selector: "edge.answer-related",
          style: {
            opacity: 1,
            width: 2,
            "line-color": "#8ACAFF",
            "target-arrow-color": "#8ACAFF",
          },
        },
        {
          selector: "node.answer-muted",
          style: {
            "background-color": "#B7BABF",
            "border-color": "#B7BABF",
            opacity: 0.3,
            "text-opacity": 0.25,
          },
        },
        {
          selector: "edge.answer-muted",
          style: { opacity: 0.12, "text-opacity": 0.1 },
        },
        { selector: ".hidden", style: { display: "none" } },
      ],
      layout: { name: "preset" },
    });
    cyRef.current = cy;
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
    cy.on("mouseover", 'node, edge[kind = "shared_entity"]', (e) => {
      const el = e.target;
      const p = e.renderedPosition || el.renderedPosition();
      const label = el.isNode()
        ? el.data("label")
        : "Ortak varlık: " +
          (latest.current.map?.edges
            .find((v) => v.id === el.id())
            ?.entities.map((v) => v.name)
            .join(", ") || "");
      setTooltip({ text: label, x: p.x, y: p.y });
      if (host.current) host.current.style.cursor = "pointer";
    });
    cy.on("mouseout", "node, edge", () => {
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
    cy.on("pan zoom render position", draw);
    const observer = new ResizeObserver(() => {
      cy.resize();
      draw();
    });
    observer.observe(host.current);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame.current);
      cy.destroy();
      cyRef.current = null;
    };
    // The instance persists across panel changes, polling and list/graph switches.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
        e.data.size = nodeSize(
          String(e.data.kind),
          degrees.get(e.data.id!) || 0,
        );
        e.data.caption = caption(String(e.data.label || ""));
        e.data.color =
          roleColors[e.data.kind as keyof typeof roleColors] ||
          roleColors.entity;
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
        nodeRepulsion: () => 9000,
        idealEdgeLength: () => 130,
        nodeOverlap: 20,
        numIter: 450,
        gravity: 0.12,
        componentSpacing: 100,
      }).run();
      cy.nodes().forEach((n) => {
        positions.current.set(n.id(), { ...n.position() });
      });
    }
    if (cy.nodes().length && !firstFit.current && props.visible) {
      firstFit.current = true;
      const saved = cameras.current.get(layer.current);
      requestAnimationFrame(() => {
        cy.resize();
        if (saved) cy.viewport(saved);
        else cy.fit(undefined, 85);
        draw();
      });
    }
    draw();
  }, [
    props.map,
    props.claims,
    props.selected,
    props.answerFocus,
    props.showTopics,
    props.showLinks,
    props.visible,
  ]);
  useEffect(() => {
    if (props.visible) {
      requestAnimationFrame(() => {
        cyRef.current?.resize();
        applyFocus();
        draw();
      });
    }
  }, [props.visible]);

  return (
    <div
      className="graph-stage reference-graph"
      role="region"
      aria-label={props.claims ? "Kaynak ilişkileri grafı" : "Not haritası"}
      data-series-count={seriesCount}
      data-answer-focus={!!props.answerFocus}
      data-highlighted-nodes={props.answerFocus ? focusCounts.highlighted : 0}
      data-dimmed-nodes={props.answerFocus ? focusCounts.dimmed : 0}
    >
      <canvas ref={canvas} className="cluster-canvas" aria-hidden="true" />
      <div ref={host} className="graph-canvas" aria-hidden="true" />
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
