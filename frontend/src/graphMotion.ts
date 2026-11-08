import type { Core, NodeSingular } from "cytoscape";

type Body = {
  node: NodeSingular;
  x: number;
  y: number;
  dx: number;
  dy: number;
  vx: number;
  vy: number;
  influence: number;
  degree: number;
};
type Options = {
  enabled(): boolean;
  reducedMotion(): boolean;
  onSettle(): void;
  requestFrame?: typeof requestAnimationFrame;
  cancelFrame?: typeof cancelAnimationFrame;
};

// A transient displacement spring: every component responds to a drag, while
// actual neighbours follow more strongly. No synthetic edges or API writes.
export function createGraphMotion(cy: Core, options: Options) {
  const request = options.requestFrame || requestAnimationFrame;
  const cancel = options.cancelFrame || cancelAnimationFrame;
  let bodies: Body[] = [],
    springs: [Body, Body][] = [],
    held: Body | null = null,
    dragging = false,
    frame = 0,
    previousTime = 0,
    releasedAt = 0;

  function stop() {
    if (frame) cancel(frame);
    frame = 0;
    bodies = [];
    springs = [];
    held = null;
    dragging = false;
  }
  function begin(event: { target: NodeSingular }) {
    stop();
    const node = event.target;
    const origin = node.position();
    const neighbours = new Set(
      node
        .neighborhood()
        .nodes()
        .map((n) => n.id()),
    );
    bodies = cy.nodes().map((n) => {
      const p = n.position();
      const distance = Math.hypot(p.x - origin.x, p.y - origin.y);
      return {
        node: n,
        x: p.x,
        y: p.y,
        dx: 0,
        dy: 0,
        vx: 0,
        vy: 0,
        degree: Math.max(1, n.degree()),
        influence: neighbours.has(n.id())
          ? 0.85
          : 0.16 + 0.52 * Math.exp(-distance / 130),
      };
    });
    const byId = new Map(bodies.map((body) => [body.node.id(), body]));
    held = byId.get(node.id()) || null;
    springs = cy
      .edges()
      .map((edge) => [
        byId.get(edge.source().id())!,
        byId.get(edge.target().id())!,
      ]);
    dragging = true;
    previousTime = 0;
    releasedAt = 0;
  }
  function finish() {
    frame = 0;
    options.onSettle();
    bodies = [];
    springs = [];
    held = null;
  }
  function tick(now: number) {
    frame = 0;
    if (!held || cy.destroyed()) return;
    if (!options.enabled()) {
      finish();
      return;
    }
    const delta = {
      x: held.node.position().x - held.x,
      y: held.node.position().y - held.y,
    };
    const reduced = options.reducedMotion();
    const dt = previousTime
      ? Math.min(2, Math.max(0.3, (now - previousTime) / 16.67))
      : 1;
    previousTime = now;
    if (!dragging && !releasedAt) releasedAt = now;
    for (const body of bodies) {
      if (body === held) {
        body.dx = delta.x;
        body.dy = delta.y;
      } else {
        body.vx += (delta.x * body.influence - body.dx) * 0.09 * dt;
        body.vy += (delta.y * body.influence - body.dy) * 0.09 * dt;
      }
    }
    // Transmit a soft impulse along existing links; divide by degree so dense
    // hubs remain stable rather than accumulating unbounded spring forces.
    for (const [a, b] of springs) {
      const fx = (b.dx - a.dx) * 0.035 * dt;
      const fy = (b.dy - a.dy) * 0.035 * dt;
      if (a !== held) {
        a.vx += fx / a.degree;
        a.vy += fy / a.degree;
      }
      if (b !== held) {
        b.vx -= fx / b.degree;
        b.vy -= fy / b.degree;
      }
    }
    let speed = 0;
    cy.batch(() => {
      for (const body of bodies) {
        if (body === held || body.node.removed()) continue;
        if (reduced) {
          body.dx = delta.x * body.influence;
          body.dy = delta.y * body.influence;
          body.vx = body.vy = 0;
        } else {
          const damping = Math.pow(0.72, dt);
          body.vx *= damping;
          body.vy *= damping;
          body.dx += body.vx * dt;
          body.dy += body.vy * dt;
          speed = Math.max(speed, Math.hypot(body.vx, body.vy));
        }
        body.node.position({ x: body.x + body.dx, y: body.y + body.dy });
      }
    });
    if (!dragging && (reduced || speed < 0.025 || now - releasedAt > 1800)) {
      finish();
    } else if (!reduced || !dragging) frame = request(tick);
  }
  function move() {
    if (!held || !options.enabled()) return;
    if (options.reducedMotion()) {
      if (frame) cancel(frame);
      tick(performance.now());
    } else if (!frame) frame = request(tick);
  }
  function release() {
    dragging = false;
    if (held && options.enabled()) move();
    else {
      options.onSettle();
      stop();
    }
  }
  cy.on("grab", "node", begin);
  cy.on("drag", "node", move);
  cy.on("free", "node", release);
  return {
    stop,
    dispose() {
      stop();
      cy.off("grab", "node", begin);
      cy.off("drag", "node", move);
      cy.off("free", "node", release);
    },
  };
}
