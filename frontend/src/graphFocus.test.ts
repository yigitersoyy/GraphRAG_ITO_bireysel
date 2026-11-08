import { describe, expect, it } from "vitest";
import cytoscape from "cytoscape";
import { applyAnswerFocus, nodeSize } from "./graphFocus";
import type { Answer } from "./types";

const answer: Answer = {
  status: "answered",
  answer: "A",
  missing_information: [],
  diagnostics: {},
  citations: [
    {
      note_id: "a",
      revision_id: "r",
      title: "A",
      quote: "A",
      start_char: 0,
      end_char: 1,
    },
  ],
  graph: { nodes: [], edges: [] },
};

describe("question source focus", () => {
  it("keeps source hubs colored without highlighting unrelated documents in the same topic", () => {
    const cy = cytoscape({
      headless: true,
      elements: [
        { data: { id: "topic", kind: "topic" } },
        { data: { id: "series", kind: "collection" } },
        { data: { id: "note:a", kind: "note", noteId: "a" } },
        { data: { id: "note:b", kind: "note", noteId: "b" } },
        {
          data: {
            id: "ma",
            source: "topic",
            target: "note:a",
            kind: "membership",
          },
        },
        {
          data: {
            id: "mb",
            source: "topic",
            target: "note:b",
            kind: "membership",
          },
        },
        {
          data: {
            id: "sa",
            source: "note:a",
            target: "series",
            kind: "collection_link",
          },
        },
        {
          data: {
            id: "sb",
            source: "note:b",
            target: "series",
            kind: "collection_link",
          },
        },
      ],
    });
    expect(applyAnswerFocus(cy, answer)).toEqual({ highlighted: 3, dimmed: 1 });
    expect(cy.$id("note:a").hasClass("answer-related")).toBe(true);
    expect(cy.$id("series").hasClass("answer-related")).toBe(true);
    expect(cy.$id("note:b").hasClass("answer-muted")).toBe(true);
    expect(cy.$id("mb").hasClass("answer-muted")).toBe(true);
    expect(cy.$id("ma").hasClass("answer-related")).toBe(true);
    cy.destroy();
  });

  it("does not dim everything for an answer with no matching sources", () => {
    const cy = cytoscape({
      headless: true,
      elements: [{ data: { id: "other", kind: "note", noteId: "other" } }],
    });
    expect(applyAnswerFocus(cy, answer)).toEqual({ highlighted: 0, dimmed: 0 });
    expect(cy.$(".answer-muted").length).toBe(0);
    cy.destroy();
  });

  it("makes topic and series hubs substantially larger than their documents", () => {
    expect(nodeSize("topic", 10)).toBeGreaterThan(nodeSize("note", 10) * 2);
    expect(nodeSize("collection", 3)).toBeGreaterThan(
      nodeSize("note", 1) * 1.8,
    );
    expect(nodeSize("entity", 9)).toBeGreaterThan(nodeSize("entity", 1));
  });
});
