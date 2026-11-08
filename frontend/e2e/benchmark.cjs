/* Read/write ONLY an empty memory-demo API; three isolated cold browser contexts. */
const { chromium, request } = require("@playwright/test");
const fs = require("node:fs");
const path = require("node:path");
const apiURL = process.env.BENCHMARK_API_URL || "http://127.0.0.1:18501";
const targets = process.argv.slice(2);
if (!targets.length) targets.push("react=http://127.0.0.1:18502");
const out = path.resolve(__dirname, "../../reports/ui-benchmark");
fs.mkdirSync(out, { recursive: true });
const median = (values) =>
  [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];

(async () => {
  const api = await request.newContext({ baseURL: apiURL });
  const status = await (await api.get("/api/v1/system/status")).json();
  if (status.mode !== "memory-demo")
    throw Error("Benchmark refuses non-memory-demo API");
  if ((await (await api.get("/api/v1/workspace/notes")).json()).total !== 0)
    throw Error("Benchmark requires empty API");
  const notes = [],
    topics = [];
  let browser;
  const json = async (url, data) => {
    const response = await api.post(url, {
      data,
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
    if (!response.ok()) throw Error(await response.text());
    return response.json();
  };
  try {
    for (const [name, color] of [
      ["Projeler", "purple"],
      ["Toplantılar", "blue"],
      ["Araştırma", "orange"],
      ["Öğrenme", "teal"],
      ["Kişisel", "green"],
      ["Tasarım", "pink"],
      ["Düzen", "yellow"],
    ])
      topics.push(await json("/api/v1/topics", { name, color_key: color }));
    for (let i = 0; i < 300; i++) {
      const n = await json("/api/v1/notes", {
        title: "Benchmark note " + i,
        text: "Ada works on Project Atlas. Project Atlas uses Neo4j.",
      });
      notes.push(n.note_id);
      await api.patch(`/api/v1/notes/${n.note_id}/metadata`, {
        data: { topic_id: topics[i % 7].topic_id, expected_version: 0 },
      });
    }
    for (let attempt = 0; attempt < 100; attempt++) {
      const map = await (await api.get("/api/v1/workspace/map")).json();
      if (
        map.nodes.length === 300 &&
        map.nodes.every((n) => n.state === "ready")
      )
        break;
      if (attempt === 99) throw Error("Synthetic documents not ready");
      await new Promise((r) => setTimeout(r, 100));
    }
    browser = await chromium.launch({
      channel: process.platform === "win32" ? "msedge" : undefined,
      headless: true,
    });
    const results = {};
    for (const target of targets) {
      const split = target.indexOf("=");
      const name = target.slice(0, split),
        url = target.slice(split + 1);
      const runs = [];
      for (let i = 0; i < 3; i++) {
        const context = await browser.newContext({
          viewport: { width: 1440, height: 960 },
        });
        const page = await context.newPage();
        const errors = [];
        page.on("pageerror", (e) => errors.push(e.message));
        await page.goto(url);
        await page.waitForFunction(
          () =>
            document.querySelector(".graph-canvas")?._cyreg?.cy?.nodes()
              .length >= 300,
        );
        const firstUsable = await page.evaluate(async () => {
          await document.fonts.ready;
          await new Promise((r) =>
            requestAnimationFrame(() => requestAnimationFrame(r)),
          );
          return performance.now();
        });
        const frames = page.evaluate(
          () =>
            new Promise((resolve) => {
              const times = [];
              const start = performance.now();
              let previous = start;
              function frame(now) {
                times.push(now - previous);
                previous = now;
                if (now - start < 1500) requestAnimationFrame(frame);
                else {
                  times.sort((a, b) => a - b);
                  resolve({
                    samples: times.length,
                    p95_frame_ms: times[Math.floor((times.length - 1) * 0.95)],
                    max_frame_ms: times.at(-1),
                  });
                }
              }
              requestAnimationFrame(frame);
            }),
        );
        await page.mouse.move(550, 400);
        await page.mouse.down();
        await page.mouse.move(750, 450, { steps: 40 });
        await page.mouse.up();
        runs.push({ first_usable_ms: firstUsable, ...(await frames), errors });
        await page.screenshot({ path: path.join(out, `${name}-${i + 1}.png`) });
        await context.close();
      }
      results[name] = {
        runs,
        median_first_usable_ms: median(runs.map((r) => r.first_usable_ms)),
        median_p95_frame_ms: median(runs.map((r) => r.p95_frame_ms)),
      };
    }
    if (results.react && results.nicegui) {
      results.acceptance = {
        first_usable_limit_ms:
          results.react.median_first_usable_ms * 1.25 + 250,
        frame_limit_ms: Math.max(
          16.7,
          results.react.median_p95_frame_ms * 1.25,
        ),
      };
      results.acceptance.passed =
        results.nicegui.median_first_usable_ms <=
          results.acceptance.first_usable_limit_ms &&
        results.nicegui.median_p95_frame_ms <=
          results.acceptance.frame_limit_ms;
    }
    fs.writeFileSync(
      path.join(out, "results.json"),
      JSON.stringify(
        {
          api_mode: status.mode,
          notes: 300,
          viewport: "1440x960",
          contexts:
            "3 cold contexts per UI; same Edge process; local synthetic demo",
          ...results,
        },
        null,
        2,
      ),
    );
    console.log(JSON.stringify(results));
  } finally {
    if (browser) await browser.close();
    for (const id of notes) await api.delete("/api/v1/notes/" + id);
    for (const topic of topics)
      await api.delete(
        `/api/v1/topics/${topic.topic_id}?expected_version=${topic.version}`,
      );
    await api.dispose();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
