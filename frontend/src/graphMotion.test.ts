import { describe, expect, it } from "vitest";
import cytoscape from "cytoscape";
import { createGraphMotion } from "./graphMotion";
import { packComponents, scaleLabels } from "./graphTheme";

function graph() {
  return cytoscape({
    headless: true,
    styleEnabled: true,
    layout: { name: "preset" },
    elements: [
      { data: { id: "hub" }, position: { x: 0, y: 0 } },
      { data: { id: "near" }, position: { x: 40, y: 0 } },
      { data: { id: "disconnected" }, position: { x: 350, y: 50 } },
      { data: { id: "link", source: "hub", target: "near" } },
    ],
  });
}

describe("graph drag response", () => {
  it("moves even disconnected nodes, settles, and leaves topology and camera intact", () => {
    const cy = graph();
    const frames = new Map<number, FrameRequestCallback>();
    let id = 0,
      settled = 0;
    const motion = createGraphMotion(cy, {
      enabled: () => true,
      reducedMotion: () => false,
      onSettle: () => settled++,
      requestFrame: (cb) => {
        frames.set(++id, cb);
        return id;
      },
      cancelFrame: (key) => {
        frames.delete(key);
      },
    });
    const camera = { zoom: cy.zoom(), pan: { ...cy.pan() } };
    const held = cy.$id("hub");
    held.emit("grab");
    held.position({ x: 100, y: 30 });
    held.emit("drag");
    function advance(now: number) {
      const callbacks = [...frames.values()];
      frames.clear();
      callbacks.forEach((cb) => cb(now));
    }
    for (let frame = 1; frame <= 12; frame++) advance(frame * 16.67);
    expect(cy.$id("near").position().x).toBeGreaterThan(50);
    expect(cy.$id("disconnected").position().x).toBeGreaterThan(350);
    expect(cy.$id("disconnected").position().x - 350).toBeLessThan(
      cy.$id("near").position().x - 40,
    );
    held.emit("free");
    for (let frame = 13; frame < 160; frame++) advance(frame * 16.67);
    expect(settled).toBe(1);
    expect(frames.size).toBe(0);
    expect(held.position()).toEqual({ x: 100, y: 30 });
    expect(cy.nodes()).toHaveLength(3);
    expect(cy.edges()).toHaveLength(1);
    expect({ zoom: cy.zoom(), pan: cy.pan() }).toEqual(camera);
    held.emit("grab");
    held.position({ x: 120, y: 40 });
    held.emit("drag");
    expect(frames.size).toBe(1);
    motion.dispose();
    expect(frames.size).toBe(0);
    cy.destroy();
  });

  it("respects reduced motion and removes drag handlers on disposal", () => {
    const cy = graph();
    let queued = 0;
    const frames = new Map<number, FrameRequestCallback>();
    const motion = createGraphMotion(cy, {
      enabled: () => true,
      reducedMotion: () => true,
      onSettle: () => {},
      requestFrame: (cb) => {
        frames.set(++queued, cb);
        return queued;
      },
      cancelFrame: (key) => {
        frames.delete(key);
      },
    });
    const held = cy.$id("hub");
    held.emit("grab");
    held.position({ x: 80, y: 0 });
    held.emit("drag");
    held.emit("free");
    expect(cy.$id("disconnected").position().x).toBeGreaterThan(350);
    expect(queued).toBe(0);
    motion.dispose();
    const previous = { ...cy.$id("near").position() };
    held.emit("grab");
    held.position({ x: 150, y: 0 });
    held.emit("drag");
    expect(cy.$id("near").position()).toEqual(previous);
    cy.destroy();
  });

  it("keeps zoomed labels at most 11 screen pixels and compacts disconnected groups without creating links", () => {
    const cy = graph();
    cy.zoom(8);
    scaleLabels(cy);
    expect(
      parseFloat(cy.$id("hub").style("font-size")) * cy.zoom(),
    ).toBeLessThanOrEqual(11);
    expect(
      parseFloat(cy.$id("link").style("font-size")) * cy.zoom(),
    ).toBeLessThanOrEqual(9);
    const before = cy.nodes().boundingBox({ includeLabels: false });
    packComponents(cy);
    const after = cy.nodes().boundingBox({ includeLabels: false });
    expect(after.w * after.h).toBeLessThan(before.w * before.h);
    expect(cy.edges()).toHaveLength(1);
    cy.destroy();
  });
});
