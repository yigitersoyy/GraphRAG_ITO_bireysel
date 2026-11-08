import { expect, test } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";
import type { APIRequestContext } from "@playwright/test";

const created: string[] = [],
  topics: { topic_id: string; version: number }[] = [];
const screenshotDir = "../reports/frontend-e2e";

test("open search removes deleted documents and entities without changing query", async ({
  page,
  request,
}) => {
  const note = await json(request, "/api/v1/notes", {
    title: "SearchGone deletion check",
    text: "SearchGone works on Project SearchGone. Project SearchGone uses Neo4j.",
  });
  created.push(note.note_id);
  await expect
    .poll(
      async () => (await json(request, "/api/v1/notes/" + note.note_id)).state,
    )
    .toBe("ready");
  await page.goto("/");
  await page.locator(".search-trigger").click();
  const query = page.getByRole("combobox", { name: "Arama" });
  await query.fill("SearchGone");
  await expect(
    page.getByRole("option").filter({ hasText: "SearchGone deletion check" }),
  ).toBeVisible();
  await expect(
    page.getByRole("option").filter({ hasText: "Varlık" }),
  ).not.toHaveCount(0);
  await request.delete("/api/v1/notes/" + note.note_id);
  expect((await json(request, "/api/v1/search?q=SearchGone")).items).toEqual(
    [],
  );
  await expect(page.getByRole("option")).toHaveCount(0, { timeout: 8000 });
  await expect(query).toHaveValue("SearchGone");
  await expect(
    page.getByText("Sonuç bulunamadı.", { exact: false }),
  ).toBeVisible();
});

test("failed-job retry control preserves API error handling", async ({
  page,
  request,
}) => {
  const note = await json(request, "/api/v1/notes", {
    title: "Retry control",
    text: "Ada works on Project Atlas.",
  });
  created.push(note.note_id);
  await page.route(`**/api/v1/notes/${note.note_id}`, async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.state = "failed";
    body.job = {
      ...body.job,
      status: "FAILED",
      error_code: "EXTRACTION_INVALID",
    };
    await route.fulfill({ response, json: body });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Liste", exact: true }).click();
  await page.getByRole("button", { name: "Sonraki", exact: true }).click();
  await page
    .getByRole("button", { name: "Retry control", exact: false })
    .click();
  await expect(
    page.getByRole("button", { name: "Yeniden dene", exact: true }),
  ).toBeVisible();
  await page.route("**/api/v1/jobs/*/retry", (route) =>
    route.fulfill({
      status: 503,
      json: { error: { code: "API_UNREACHABLE", message: "Unavailable" } },
    }),
  );
  const sent = page.waitForRequest(
    (r) => r.url().includes("/retry") && r.method() === "POST",
  );
  await page.getByRole("button", { name: "Yeniden dene", exact: true }).click();
  await sent;
  await expect(page.getByRole("alert")).toContainText("API");
  await request.delete(`/api/v1/notes/${note.note_id}`);
});

test("safe hostile title, corrected form and insufficient answer retain legacy coverage", async ({
  page,
  request,
}) => {
  const title = "😀 <img src=x onerror=alert(1)> [click](javascript:alert(1))";
  const dialogs: string[] = [];
  page.on("dialog", async (dialog) => {
    dialogs.push(dialog.message());
    await dialog.dismiss();
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Yeni not", exact: true }).click();
  await page.getByLabel("Başlık", { exact: true }).fill(title);
  await page.getByLabel("Metin", { exact: true }).fill("   ");
  await page.getByRole("button", { name: "Kaydet", exact: true }).click();
  await expect(
    page.getByText("Not için bir başlık ve metin yaz.", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Metin", { exact: true })
    .fill("Ada works on Project Atlas. Project Atlas uses Neo4j.");
  await page.getByRole("button", { name: "Kaydet", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  await expect(page.locator(".detail-panel img")).toHaveCount(0);
  const notes = (
    await json(
      request,
      "/api/v1/workspace/notes?q=" + encodeURIComponent(title),
    )
  ).items;
  expect(notes).toHaveLength(1);
  created.push(notes[0].note_id);
  await page.getByRole("button", { name: "Soru sor", exact: true }).click();
  await page
    .getByLabel("Sorun", { exact: true })
    .fill("What is the capital of France?");
  await page.getByRole("button", { name: "Sor", exact: true }).click();
  await expect(page.locator(".answer-result .field-label")).toHaveText(
    "Yeterli kaynak yok",
  );
  await expect(page.locator(".source-button")).toHaveCount(0);
  expect(dialogs).toEqual([]);
  await request.delete(`/api/v1/notes/${notes[0].note_id}`);
});

test("multiple successful files finish with a note view and clean close", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Yeni not", exact: true }).click();
  await page.getByLabel("Not dosyası yükle").setInputFiles([
    {
      name: "Batch success a.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Ada works on Project Atlas."),
    },
    {
      name: "Batch success b.md",
      mimeType: "text/markdown",
      buffer: Buffer.from("Project Atlas uses Neo4j."),
    },
  ]);
  await page
    .getByRole("button", { name: "Batch success a.txt", exact: true })
    .click();
  await expect(page.getByLabel("Dosya önizlemesi")).toHaveValue(
    "Ada works on Project Atlas.",
  );
  await page.getByRole("button", { name: "Önizlemeyi kapat" }).click();
  await page
    .getByRole("button", { name: "Dosyaları yükle", exact: true })
    .click();
  await expect(page.locator(".bulk-progress")).toHaveText(
    "2 / 2 dosya işleme alındı",
  );
  const imported = (
    await json(request, "/api/v1/workspace/notes?q=Batch%20success")
  ).items;
  for (const n of imported) created.push(n.note_id);
  expect(imported.length).toBe(2);
  await page.screenshot({ path: screenshotDir + "/bulk-complete.png" });
  await page.getByRole("button", { name: "Tamam", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Batch success a", exact: true }),
  ).toBeVisible();
  for (const n of imported) await request.delete("/api/v1/notes/" + n.note_id);
});

test("multiple files queue isolates failures and retries without duplicates", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Yeni not", exact: true }).click();
  await expect(page.getByLabel("Not dosyası yükle")).toHaveAttribute(
    "multiple",
    "",
  );
  const files = [
    {
      name: "Toplu bir.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Ada works on Project Atlas."),
    },
    {
      name: "Bozuk toplu.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("broken"),
    },
    {
      name: "Toplu iki.md",
      mimeType: "text/markdown",
      buffer: Buffer.from("Project Atlas uses Neo4j."),
    },
  ];
  await page.getByLabel("Not dosyası yükle").setInputFiles(files);
  await expect(
    page.getByRole("heading", { name: "Toplu dosya yükleme" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Dosyaları yükle", exact: true })
    .click();
  await expect(page.locator(".bulk-progress")).toHaveText(
    "2 / 3 dosya işleme alındı",
  );
  await expect(
    page.locator('[data-file-name="Bozuk toplu.pdf"]'),
  ).toContainText("Yüklenemedi");
  const imported = (await json(request, "/api/v1/workspace/notes?q=Toplu"))
    .items;
  for (const n of imported) created.push(n.note_id);
  expect(imported.length).toBe(2);
  await page
    .getByRole("button", { name: "Kalanları yeniden dene", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Kalanları yeniden dene", exact: true }),
  ).toBeEnabled();
  expect((await json(request, "/api/v1/workspace/notes?q=Toplu")).total).toBe(
    2,
  );
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Kapat", exact: true }).click();
  for (const n of imported) await request.delete("/api/v1/notes/" + n.note_id);
});

test("automatic file families and drag between topics persist, with mobile selection", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Yeni not", exact: true }).click();
  await expect(page.locator("#editor-topic")).toHaveValue("__auto__");
  const title = "01_kvkk_6698_kanun_bolum_01";
  await page.getByLabel("Başlık", { exact: true }).fill(title);
  await page
    .getByLabel("Metin", { exact: true })
    .fill("Ada works on Project Atlas. Project Atlas uses Neo4j.");
  const accepted = page.waitForResponse(
    (r) => r.url().endsWith("/api/v1/notes") && r.status() === 202,
  );
  await page.getByRole("button", { name: "Kaydet", exact: true }).click();
  const first = await (await accepted).json();
  created.push(first.note_id);
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  const second = await json(request, "/api/v1/notes", {
    title: "03_bddk_5411_kanun_bolum_01",
    text: "Test note.",
  });
  created.push(second.note_id);
  const section = await json(request, "/api/v1/notes", {
    title: "01_kvkk_6698_kanun_bolum_02",
    text: "Additional section.",
  });
  created.push(section.note_id);
  await expect(page.locator(".reference-graph")).toHaveAttribute(
    "data-series-count",
    "1",
  );
  const all = (await json(request, "/api/v1/topics")).items;
  const kvkk = all.find((t: { name: string }) => t.name === "KVKK"),
    bddk = all.find((t: { name: string }) => t.name === "BDDK");
  topics.push(kvkk, bddk);
  const original = await json(request, `/api/v1/notes/${first.note_id}`);
  expect(original.topic_id).toBe(kvkk.topic_id);
  await page.getByRole("button", { name: "Paneli kapat" }).click();
  await page.getByRole("button", { name: "Liste", exact: true }).click();
  await page.locator("#topic-filter").selectOption(kvkk.topic_id);
  const row = page.locator(`[data-note-id="${first.note_id}"]`);
  await expect(row).toBeVisible();
  await row.dragTo(page.locator(`[data-topic-drop="${bddk.topic_id}"]`));
  await expect
    .poll(
      async () =>
        (await json(request, `/api/v1/notes/${first.note_id}`)).topic_id,
    )
    .toBe(bddk.topic_id);
  await expect(row).toHaveCount(0);
  await page.reload();
  await page.locator("#topic-filter").selectOption(bddk.topic_id);
  await expect(row).toBeVisible();
  const current = await json(request, `/api/v1/notes/${first.note_id}`);
  expect(current.desired_revision_id).toBe(original.desired_revision_id);
  await page.setViewportSize({ width: 360, height: 800 });
  await expect(row.locator("select")).toBeVisible();
  await row.locator("select").selectOption(kvkk.topic_id);
  await expect
    .poll(
      async () =>
        (await json(request, `/api/v1/notes/${first.note_id}`)).topic_id,
    )
    .toBe(kvkk.topic_id);
  await page.locator("#topic-filter").selectOption(kvkk.topic_id);
  await expect(row).toBeVisible();
  await expect(row.locator("select")).toHaveValue(kvkk.topic_id);
  await expect(row.locator("select")).toBeEnabled();
  await page.route("**/api/v1/notes/*/metadata", (route) =>
    route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "METADATA_CHANGED", message: "changed" },
      }),
    }),
  );
  await row.locator("select").selectOption(bddk.topic_id);
  await expect(
    page.getByRole("status").filter({ hasText: "başka bir işlemde" }),
  ).toBeVisible();
  expect((await json(request, `/api/v1/notes/${first.note_id}`)).topic_id).toBe(
    kvkk.topic_id,
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({ path: screenshotDir + "/topic-move-mobile.png" });
  await page.unroute("**/api/v1/notes/*/metadata");
  await request.delete(`/api/v1/notes/${first.note_id}`);
  await request.delete(`/api/v1/notes/${second.note_id}`);
  await request.delete(`/api/v1/notes/${section.note_id}`);
});
async function json(request: APIRequestContext, path: string, data?: unknown) {
  const r = data
    ? await request.post(path, {
        data,
        headers: { "Idempotency-Key": crypto.randomUUID() },
      })
    : await request.get(path);
  expect(r.ok(), await r.text()).toBeTruthy();
  return r.json();
}

test.beforeAll(async ({ request }) => {
  const status = await json(request, "/api/v1/system/status");
  // Never seed or mutate a live/user workspace, even when a URL is accidentally overridden.
  expect(status.mode).toBe("memory-demo");
  expect((await json(request, "/api/v1/workspace/notes")).total).toBe(0);
  const groups = [
    ["Projeler", "purple", "Atlas", "Neo4j"],
    ["Toplantılar", "blue", "Borealis", "PostgreSQL"],
    ["Araştırma", "orange", "Vega", "Redis"],
    ["Öğrenme", "teal", "Deniz", "Python"],
    ["Kişisel", "green", "Orion", "SQLite"],
    ["Tasarım", "pink", "Lyra", "Kuzu"],
    ["Düzen", "yellow", "Nova", "MongoDB"],
  ];
  const names = [
    "Atlas mimari notları",
    "Haftalık ekip toplantısı",
    "Neo4j okuma notları",
    "Python çalışma günlüğü",
    "Hafta sonu planı",
    "Graf yerleşimi fikirleri",
    "İş planı",
  ];
  for (const [name, color] of groups)
    topics.push(
      await json(request, "/api/v1/topics", { name, color_key: color }),
    );
  for (let i = 0; i < 51; i++) {
    const group = i % 7,
      [, , project, db] = groups[group];
    const title =
      i < 7 ? names[group] : `${names[group]} / ${Math.floor(i / 7) + 1}`;
    const text =
      group === 0
        ? "Ada works on Project Atlas. Project Atlas uses Neo4j."
        : `Person${group} works on Project ${project}. Project ${project} uses ${db}.`;
    const n = await json(request, "/api/v1/notes", { title, text });
    created.push(n.note_id);
    expect(
      (
        await request.patch(`/api/v1/notes/${n.note_id}/metadata`, {
          data: { topic_id: topics[group].topic_id, expected_version: 0 },
        })
      ).ok(),
    ).toBeTruthy();
  }
  await expect
    .poll(
      async () =>
        (await json(request, "/api/v1/workspace/map")).nodes.filter(
          (n: { state: string }) => n.state === "ready",
        ).length,
      { timeout: 30000 },
    )
    .toBe(51);
});
test.afterAll(async ({ request }) => {
  for (const id of created) await request.delete("/api/v1/notes/" + id);
  for (const t of topics)
    await request.delete(
      `/api/v1/topics/${t.topic_id}?expected_version=${t.version}`,
    );
});

test("PDF, Word and Excel previews, uploads, edited preview and malformed file", async ({
  page,
  request,
}) => {
  const fixtures = JSON.parse(readFileSync("e2e/documents.json", "utf8"));
  for (const extension of ["pdf", "docx", "xlsx", "xls"]) {
    await page.goto("/");
    await page.getByRole("button", { name: "Yeni not", exact: true }).click();
    const total = (await json(request, "/api/v1/workspace/notes")).total;
    await page.getByLabel("Not dosyası yükle").setInputFiles({
      name: `Dosya denemesi.${extension}`,
      mimeType: "application/octet-stream",
      buffer: Buffer.from(fixtures[extension], "base64"),
    });
    await expect(page.getByLabel("Metin", { exact: true })).toHaveValue(
      /Project Atlas uses Neo4j/,
    );
    expect((await json(request, "/api/v1/workspace/notes")).total).toBe(total);
    const response = page.waitForResponse(
      (r) => r.url().endsWith("/api/v1/notes/upload") && r.status() === 202,
    );
    await page.getByRole("button", { name: "Kaydet", exact: true }).click();
    const note = await (await response).json();
    created.push(note.note_id);
    await expect(page.locator(".note-prose")).toContainText(
      "Project Atlas uses Neo4j",
    );
    await page.screenshot({
      path: `${screenshotDir}/document-${extension}.png`,
    });
    await request.delete(`/api/v1/notes/${note.note_id}`);
  }
  await page.goto("/");
  await page.getByRole("button", { name: "Yeni not", exact: true }).click();
  await page.getByLabel("Not dosyası yükle").setInputFiles({
    name: "Bozuk.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("broken"),
  });
  await expect(page.getByRole("alert")).toContainText("PDF değil");
  await page.getByLabel("Not dosyası yükle").setInputFiles({
    name: "Düzenle.docx",
    mimeType: "application/octet-stream",
    buffer: Buffer.from(fixtures.docx, "base64"),
  });
  await expect(page.getByLabel("Metin", { exact: true })).toHaveValue(/Neo4j/);
  await page
    .getByLabel("Metin", { exact: true })
    .fill("Ada works on Project Atlas. Project Atlas uses Redis.");
  const response = page.waitForResponse(
    (r) => r.url().endsWith("/api/v1/notes") && r.status() === 202,
  );
  await page.getByRole("button", { name: "Kaydet", exact: true }).click();
  const note = await (await response).json();
  created.push(note.note_id);
  await expect(page.locator(".note-prose")).toContainText("Redis");
  await request.delete(`/api/v1/notes/${note.note_id}`);
});

test("graph, pagination, keyboard search, source and camera", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("region", { name: "Not haritası" }),
  ).toBeVisible();
  await expect(page.locator(".graph-legend button")).toHaveCount(7);
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve)),
    );
  });
  await page.screenshot({ path: screenshotDir + "/01-map.png" });
  await page.getByRole("button", { name: "Liste", exact: true }).click();
  await expect(page.locator(".note-table-row")).toHaveCount(50);
  await page.getByRole("button", { name: "Sonraki", exact: true }).click();
  await expect(page.locator(".note-table-row")).toHaveCount(1);
  await page.getByRole("button", { name: "Önceki", exact: true }).click();
  await expect(page.locator(".note-table-row")).toHaveCount(50);
  await page.screenshot({ path: screenshotDir + "/02-list.png" });
  await page.keyboard.press("Control+k");
  await page.getByRole("combobox", { name: "Arama" }).fill("Atlas mimari");
  await expect(
    page.locator("#search-results").getByRole("option").first(),
  ).toContainText("Atlas mimari");
  await page.screenshot({ path: screenshotDir + "/03-search.png" });
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Atlas mimari notları", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".note-prose")).toContainText("Neo4j");
  await page.getByRole("button", { name: "Graf", exact: true }).click();
  await page.screenshot({ path: screenshotDir + "/04-note.png" });
  await page.getByRole("button", { name: "Soru sor", exact: true }).click();
  // Keep the real API answer and add only the advisory flag to exercise its UI treatment.
  await page.route("**/api/v1/questions", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.diagnostics.semantic_review_uncertain = true;
    await route.fulfill({ response, json: body });
  });
  await page
    .getByLabel("Sorun", { exact: true })
    .fill("What database does Project Atlas use?");
  await page.getByRole("button", { name: "Sor", exact: true }).click();
  await expect(page.locator(".answer-text")).toContainText("Neo4j");
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Bu yanıtın yorumunu kaynaklardan kontrol edin." }),
  ).toBeVisible();
  await expect(page.locator(".source-button")).not.toHaveCount(0);
  const graph = page.getByRole("region", { name: "Not haritası", exact: true });
  await expect(graph).toHaveCSS("background-color", "rgb(0, 0, 0)");
  await expect(graph).toHaveAttribute("data-answer-focus", "true");
  await expect
    .poll(async () =>
      Number(await graph.getAttribute("data-highlighted-nodes")),
    )
    .toBeGreaterThan(0);
  await expect
    .poll(async () => Number(await graph.getAttribute("data-dimmed-nodes")))
    .toBeGreaterThan(0);
  await page.screenshot({ path: screenshotDir + "/05-answer.png" });
  await page
    .getByRole("button", { name: "Vurguyu temizle", exact: true })
    .click();
  await expect(graph).toHaveAttribute("data-answer-focus", "false");
  await expect(graph).toHaveAttribute("data-dimmed-nodes", "0");
  await page.locator(".source-button").first().click();
  await expect(page.locator("mark")).toContainText("Atlas");
  await page.getByRole("button", { name: "Cevaba dön" }).click();
  await expect(page.locator(".answer-text")).toBeVisible();
  await page
    .getByRole("button", { name: "Destekleyici ilişkileri göster" })
    .click();
  await page.getByRole("button", { name: "Liste", exact: true }).click();
  await page.locator(".claim-row").first().click();
  await expect(page.locator(".source-label")).toContainText("Kaynak revizyonu");
  await expect(page.locator("mark")).toContainText("Atlas");
  expect(errors).toEqual([]);
});

test("edit guards, topic assignment, topic tree and delete", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Yeni not", exact: true }).click();
  await page.getByLabel("Başlık", { exact: true }).fill("UI acceptance note");
  await page
    .getByLabel("Metin", { exact: true })
    .fill("Ada works on Project Atlas.");
  const dismissal = page.waitForEvent("dialog").then((d) => d.dismiss());
  await page.getByRole("button", { name: "Paneli kapat", exact: true }).click();
  await dismissal;
  await expect(page.getByLabel("Başlık", { exact: true })).toHaveValue(
    "UI acceptance note",
  );
  await page
    .getByLabel("Konu", { exact: true })
    .selectOption(topics[0].topic_id);
  await page.getByRole("button", { name: "Kaydet", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "UI acceptance note", exact: true }),
  ).toBeVisible();
  const found = (
    await json(request, "/api/v1/workspace/notes?q=UI%20acceptance")
  ).items[0];
  created.push(found.note_id);
  await expect(page.getByLabel("Notun konusu")).toHaveValue(topics[0].topic_id);
  await page.getByRole("button", { name: "Düzenle", exact: true }).click();
  await page
    .getByLabel("Metin", { exact: true })
    .fill("Ada works on Project Atlas. Project Atlas uses Redis.");
  await page.getByRole("button", { name: "Kaydet", exact: true }).click();
  await expect(page.locator(".note-prose")).toContainText("Redis");
  await page.getByRole("button", { name: "Paneli kapat" }).click();
  await page
    .getByRole("button", { name: "Konular", exact: true })
    .first()
    .click();
  await page
    .locator(".topic-group-heading")
    .filter({ hasText: "Projeler" })
    .click();
  await expect(page.locator(".topic-group-notes")).toContainText(
    "UI acceptance note",
  );
  await page
    .getByRole("button", { name: "UI acceptance note", exact: false })
    .click();
  await page.getByRole("button", { name: "Not işlemleri" }).click();
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Notu sil", exact: true }).click();
  await expect(page.locator(".detail-panel")).toHaveCount(0);
  await expect
    .poll(
      async () =>
        (await json(request, "/api/v1/workspace/notes?q=UI%20acceptance"))
          .total,
    )
    .toBe(0);
});

test("360px viewport, keyboard focus, reduced motion and offline assets", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const external: string[] = [];
  page.on("request", (r) => {
    if (
      !r.url().startsWith("http://127.0.0.1:18502") &&
      !r.url().startsWith("data:")
    )
      external.push(r.url());
  });
  await page.goto("/");
  await expect(page.locator(".note-table-row")).toHaveCount(50);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.locator(".note-table-row").first().click();
  await expect(page.locator(".detail-panel")).toBeVisible();
  expect(
    await page
      .locator(".detail-panel")
      .evaluate((el) => el.getBoundingClientRect().width),
  ).toBe(360);
  await page.screenshot({ path: screenshotDir + "/06-mobile.png" });
  await page.getByRole("button", { name: "Paneli kapat" }).click();
  await page.getByRole("button", { name: "Graf", exact: true }).click();
  await expect(page.locator(".graph-canvas canvas").first()).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByLabel("Graf katmanları", { exact: true }).click();
  await expect(
    page.locator(".layers-menu label").filter({ hasText: "Bağlantılar" }),
  ).toBeVisible();
  await page.getByLabel("Graf katmanları", { exact: true }).click();
  await page.context().setOffline(true);
  await page.getByRole("button", { name: "Haritayı ekrana sığdır" }).click();
  await page.screenshot({ path: screenshotDir + "/07-offline-graph.png" });
  await page.context().setOffline(false);
  expect(external).toEqual([]);
});

test("topic management and readiness failure preserve access to notes", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Konular", exact: true })
    .first()
    .click();
  await page.getByRole("button", { name: "Konu oluştur", exact: true }).click();
  const panel = page.locator(".detail-panel");
  await panel.getByLabel("Yeni konu", { exact: true }).fill("UI konusu");
  await panel
    .getByRole("button", { name: "Renk: Turkuaz", exact: true })
    .click();
  await panel
    .getByRole("button", { name: "Konu oluştur", exact: true })
    .click();
  await expect(
    panel.locator(".topic-edit").filter({ hasText: "UI konusu" }),
  ).toBeVisible();
  const t = (await json(request, "/api/v1/topics")).items.find(
    (t: { name: string }) => t.name === "UI konusu",
  );
  topics.push(t);
  await panel.locator(".topic-edit").filter({ hasText: "UI konusu" }).click();
  await panel
    .getByLabel("Konuyu düzenle", { exact: true })
    .fill("UI yeni konu");
  await panel.getByRole("button", { name: "Değişiklikleri kaydet" }).click();
  await expect(
    panel.locator(".topic-edit").filter({ hasText: "UI yeni konu" }),
  ).toBeVisible();
  const row = panel
    .locator(".topic-management-row")
    .filter({ hasText: "UI yeni konu" });
  page.once("dialog", (d) => d.accept());
  await row.getByRole("button", { name: "Sil", exact: true }).click();
  await expect(row).toHaveCount(0);
  await panel.getByRole("button", { name: "Paneli kapat" }).click();
  await page.route("**/health/ready", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        status: "not_ready",
        checks: { reachable: true, schema_ok: true },
      }),
    }),
  );
  await page
    .getByRole("button", { name: "Geçici / Demo", exact: false })
    .click();
  await page.getByRole("button", { name: "Durumu yenile" }).click();
  await expect(page.locator(".system-details")).toContainText("Hazır değil");
  await expect(page.locator(".system-details")).toContainText("Erişilebilir");
  await page.getByRole("button", { name: "Paneli kapat" }).click();
  await page.getByRole("button", { name: "Liste", exact: true }).click();
  await expect(page.locator(".note-table-row")).toHaveCount(50);
});

test("300 note and 600 edge map budget remains interactive", async ({
  page,
  request,
}) => {
  test.setTimeout(90000);
  for (let i = 0; i < 249; i++) {
    const n = await json(request, "/api/v1/notes", {
      title: `UI performance ${i}`,
      text: "Ada works on Project Atlas. Project Atlas uses Neo4j.",
    });
    created.push(n.note_id);
  }
  await expect
    .poll(
      async () =>
        (await json(request, "/api/v1/workspace/map")).nodes.filter(
          (n: { state: string }) => n.state === "ready",
        ).length,
      { timeout: 40000 },
    )
    .toBe(300);
  const map = await json(request, "/api/v1/workspace/map");
  expect(map.nodes).toHaveLength(300);
  expect(map.edges).toHaveLength(600);
  expect(map.edges_limited).toBe(true);
  await page.goto("/");
  await expect(page.locator(".map-limit")).toContainText("300 / 300");
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve)),
    );
  });
  const measurement = page.evaluate(
    () =>
      new Promise<{
        samples: number;
        p95_frame_ms: number;
        max_frame_ms: number;
      }>((resolve) => {
        const times: number[] = [];
        const started = performance.now();
        let previous = started;
        function frame(now: number) {
          times.push(now - previous);
          previous = now;
          if (now - started < 900) requestAnimationFrame(frame);
          else {
            times.sort((a, b) => a - b);
            resolve({
              samples: times.length,
              p95_frame_ms: times[Math.floor((times.length - 1) * 0.95)],
              max_frame_ms: times.at(-1)!,
            });
          }
        }
        requestAnimationFrame(frame);
      }),
  );
  await page.mouse.move(550, 400);
  await page.mouse.down();
  await page.mouse.move(750, 450, { steps: 30 });
  await page.mouse.up();
  const frames = await measurement;
  writeFileSync(
    screenshotDir + "/performance.json",
    JSON.stringify(
      {
        nodes: 300,
        edges: 600,
        renderer: "Cytoscape Canvas: labeled note/topic/entity graph",
        viewport: "1440x960",
        measurement:
          "900 ms rAF sampling during mouse pan; local headless Edge, not independent benchmark",
        ...frames,
      },
      null,
      2,
    ),
  );
  expect(frames.samples).toBeGreaterThan(1);
  expect(frames.p95_frame_ms).toBeLessThanOrEqual(50);
  await page.getByRole("button", { name: "Haritayı ekrana sığdır" }).click();
  await page.screenshot({ path: screenshotDir + "/08-budget-map.png" });
});
