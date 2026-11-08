import type { Core } from "cytoscape";
import type { Answer } from "./types";

export function nodeSize(kind: string, degree: number): number {
  if (kind === "topic") return Math.min(140, 108 + Math.sqrt(degree) * 6);
  if (kind === "collection") return Math.min(124, 94 + Math.sqrt(degree) * 5);
  if (kind === "entity") return Math.min(108, 58 + Math.sqrt(degree) * 8);
  return 52;
}

// Keep source documents and their own hubs visible, without lighting up siblings.
export function applyAnswerFocus(cy: Core, answer: Answer) {
  const noteIds = new Set([
    ...answer.citations.map((c) => c.note_id),
    ...answer.graph.edges.map((e) => e.evidence.note_id),
  ]);
  const entityIds = new Set(answer.graph.nodes.map((n) => n.id));
  const claimIds = new Set(answer.graph.edges.map((e) => e.id));
  let relevant = cy
    .nodes()
    .filter((n) =>
      n.data("kind") === "note"
        ? noteIds.has(n.data("noteId"))
        : n.data("kind") === "entity" &&
          (entityIds.has(n.id()) ||
            entityIds.has(n.id().replace(/^entity:/, ""))),
    );
  const documents = relevant.filter('[kind = "note"]');
  const hubEdges = documents
    .connectedEdges()
    .filter((e) => ["membership", "collection_link"].includes(e.data("kind")));
  relevant = relevant.union(hubEdges.connectedNodes());
  const links = cy.edges().filter((e) => {
    if (!relevant.contains(e.source()) || !relevant.contains(e.target()))
      return false;
    if (e.data("kind") === "claim")
      return (
        claimIds.has(e.id()) || claimIds.has(e.id().replace(/^relation:/, ""))
      );
    return ["membership", "collection_link", "evidence"].includes(
      e.data("kind"),
    );
  });
  if (!relevant.length) return { highlighted: 0, dimmed: 0 };
  cy.elements().not(relevant.union(links)).addClass("answer-muted");
  relevant.addClass("answer-related");
  links.addClass("answer-related");
  return {
    highlighted: relevant.length,
    dimmed: cy.nodes().not(relevant).length,
  };
}
