import type { Core, EdgeSingular, StylesheetJson } from "cytoscape";

export const graphPalette = {
  background: "#1E2126",
  hub: "#E5EA86",
  note: "#59C8D6",
  entity: "#9B91CF",
};
const topicTints: Record<string, string> = {
  "#A683C9": "#8C9BD1",
  "#529BD3": "#65BCD7",
  "#46AAA3": "#57C7C6",
  "#D78C4B": "#6AABD0",
  "#C86694": "#C18CB6",
  "#5B9F77": "#64BCA8",
  "#C5AC39": "#C6D583",
  "#9A9A98": "#9CA6C0",
};
export function pointColor(
  kind: string,
  degree: number,
  topicColor?: string,
): string {
  if (kind === "topic" || kind === "collection" || degree >= 9)
    return graphPalette.hub;
  if (kind === "note") return topicTints[topicColor || ""] || graphPalette.note;
  return graphPalette.entity;
}

export const graphStyle: StylesheetJson = [
  {
    selector: "node",
    style: {
      label: "",
      "background-color": "data(color)",
      width: "data(size)",
      height: "data(size)",
      "border-width": 0,
      color: "#E0E5EB",
      "font-family": "Segoe UI, sans-serif",
      "font-size": 9,
      "text-valign": "bottom",
      "text-halign": "center",
      "text-margin-y": 5,
      "text-wrap": "wrap",
      "text-max-width": "145px",
      "text-background-color": graphPalette.background,
      "text-background-opacity": 0.92,
      "text-background-padding": "3px",
      "z-index": 2,
    },
  },
  {
    selector: "edge",
    style: {
      label: "",
      width: 0.45,
      "line-color": "#528C9A",
      opacity: (edge: EdgeSingular) => Number(edge.data("alpha") ?? 0.24),
      "curve-style": "haystack",
      "haystack-radius": 0,
      "target-arrow-shape": "none",
      "target-arrow-color": "#7DBFCB",
      "arrow-scale": 0.45,
      color: "#C6D4DD",
      "font-size": 8,
      "text-rotation": "autorotate",
      "text-background-color": graphPalette.background,
      "text-background-opacity": 0.95,
      "text-background-padding": "3px",
    },
  },
  {
    selector: 'edge[kind = "membership"], edge[kind = "collection_link"]',
    style: { "line-color": "#6B9AA2" },
  },
  {
    selector: 'edge[kind = "claim"]',
    style: { "line-color": "#489CAC", width: 0.6 },
  },
  {
    selector: 'edge[polarity = "NEGATED"]',
    style: { "line-style": "dashed", "line-color": "#C796B8" },
  },
  {
    selector:
      "node.labels-visible, node.hovered, node.selected, node.focused, node.answer-related",
    style: { label: "data(caption)" },
  },
  {
    selector: "edge.labels-visible, edge.hovered, edge.selected",
    style: { label: "data(label)", "curve-style": "bezier" },
  },
  {
    selector: "edge.show-arrows",
    style: { "target-arrow-shape": "triangle", "curve-style": "bezier" },
  },
  {
    selector: "node.hovered, node.selected",
    style: { "border-width": 1.5, "border-color": "#F0F4BB", "z-index": 12 },
  },
  { selector: ".dimmed", style: { opacity: 0.14, "text-opacity": 0.2 } },
  {
    selector: "edge.selected, edge.hovered",
    style: {
      opacity: 0.9,
      width: 1,
      "line-color": "#9AD9DE",
      "target-arrow-color": "#9AD9DE",
    },
  },
  {
    selector: "node.answer-related",
    style: { "border-width": 1.4, "border-color": "#F2F5BD", "z-index": 12 },
  },
  {
    selector: "edge.answer-related",
    style: {
      opacity: 0.85,
      width: 1,
      "line-color": "#8DCFD8",
      "target-arrow-color": "#8DCFD8",
    },
  },
  {
    selector: "node.answer-muted",
    style: {
      "background-color": "#62717C",
      opacity: 0.15,
      "text-opacity": 0.15,
    },
  },
  {
    selector: "edge.answer-muted",
    style: { opacity: 0.035, "text-opacity": 0.1 },
  },
  { selector: ".hidden", style: { display: "none" } },
];

export function fitOverview(cy: Core) {
  cy.fit(undefined, 75);
  if (cy.zoom() > 1.25)
    cy.zoom({
      level: 1.25,
      renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
    });
}

// Cytoscape scales canvas text with the camera. Keep labels readable in screen
// pixels instead of letting an 8× zoom turn them into oversized headings.
export function scaleLabels(cy: Core) {
  const zoom = cy.zoom();
  cy.batch(() => {
    cy.nodes().style({
      "font-size": Math.min(9, 11 / zoom),
      "text-max-width": 145 / zoom,
      "text-margin-y": 4 / zoom,
      "text-background-padding": 2 / zoom,
    });
    cy.edges().style({
      "font-size": Math.min(8, 9 / zoom),
      "text-background-padding": 2 / zoom,
    });
  });
}

// Pack genuine disconnected components into a cloud, without inventing connecting edges.
export function packComponents(cy: Core) {
  const groups = cy
    .elements()
    .components()
    .sort((a, b) => b.nodes().length - a.nodes().length);
  const placed: { x: number; y: number; r: number }[] = [];
  groups.forEach((group) => {
    const nodes = group.nodes();
    const center = nodes.reduce(
      (sum, n) => ({
        x: sum.x + n.position().x / nodes.length,
        y: sum.y + n.position().y / nodes.length,
      }),
      { x: 0, y: 0 },
    );
    nodes.positions((n) => ({
      x: center.x + (n.position().x - center.x) * 0.72,
      y: center.y + (n.position().y - center.y) * 0.72,
    }));
    const box = group
      .nodes()
      .boundingBox({ includeLabels: false, includeOverlays: false });
    const r = Math.max(7, Math.hypot(box.w, box.h) / 2 + 4);
    let destination = { x: 0, y: 0 };
    if (placed.length)
      for (let i = 1; i < 6000; i++) {
        const angle = i * 2.399963,
          radius = Math.sqrt(i) * 10;
        destination = {
          x: Math.cos(angle) * radius,
          y: Math.sin(angle) * radius,
        };
        if (
          placed.every(
            (p) =>
              Math.hypot(p.x - destination.x, p.y - destination.y) >= p.r + r,
          )
        )
          break;
      }
    const dx = destination.x - (box.x1 + box.x2) / 2,
      dy = destination.y - (box.y1 + box.y2) / 2;
    group
      .nodes()
      .positions((n) => ({ x: n.position().x + dx, y: n.position().y + dy }));
    placed.push({ ...destination, r });
  });
}
