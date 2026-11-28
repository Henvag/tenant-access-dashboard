// Screens for the Ask clip, captured from the public read-only demo at 2x (2880 x 1800).
//
//   FILM_LANG=en node film/scripts/capture-ask.mjs      # then FILM_LANG=no
//   ASK_DRY=1 ...                                        # only the empty screen, no question sent
//
// Unlike capture.mjs this needs no local database: the demo lets visitors try Ask, so the
// answer on screen is the real built-in model's answer. Each run uses one of the demo's 30
// questions a day. Screens go to assets/ask/<lang>/ with geo.json (CSS pixels).
import { chromium } from "playwright";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const LANG = process.env.FILM_LANG === "no" ? "no" : "en";
const OUT = path.join(__dirname, "..", "assets", "ask", LANG);
const BASE = (process.env.BASE || "https://tenantaccess.me").replace(/\/$/, "");
const T = {
  en: { demo: "Explore the live demo", banner: "read-only demo", q: "Who hasn't signed in this week?" },
  no: { demo: "Utforsk live-demoen", banner: "skrivebeskyttet demo", q: "Hvem har ikke logget inn denne uken?" },
}[LANG];

fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
page.setDefaultTimeout(60000);

await page.goto(BASE, { waitUntil: "networkidle" });
await page.evaluate((lang) => localStorage.setItem("tenant-access.lang", lang), LANG);
await page.reload({ waitUntil: "networkidle" });
await page.getByRole("button", { name: T.demo }).first().click();
await page.getByText(T.banner).waitFor();
await page.goto(`${BASE}/?view=ask`, { waitUntil: "networkidle" });
await page.addStyleTag({
  content: ".demo-banner, .ask-admin-bar .btn { display: none !important; } * { transition: none !important; animation: none !important; caret-color: transparent !important; }",
});
// The usage line counts the whole demo's questions; it would differ between takes.
await page.evaluate(() => {
  for (const el of document.querySelectorAll(".ask-admin-bar .hint")) el.textContent = el.textContent.split(" · ")[0];
});
const input = page.locator(".agent-compose input");
await input.waitFor();

const box = async (sel) => {
  const b = await page.locator(sel).first().boundingBox();
  return b && { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) };
};
const geo = { input: await box(".agent-compose input"), send: await box(".agent-compose button"), card: await box("section.card") };
await page.screenshot({ path: path.join(OUT, "empty.png") });

if (!process.env.ASK_DRY) {
  // One screen per typed character, so the typing in the clip is the real input.
  await input.click();
  for (let i = 1; i <= T.q.length; i += 1) {
    await input.fill(T.q.slice(0, i));
    await page.screenshot({ path: path.join(OUT, `type-${String(i).padStart(2, "0")}.png`) });
  }
  geo.typed = T.q.length;
  const answered = page.waitForResponse((r) => r.url().endsWith("/ask/chat"));
  await page.locator(".agent-compose button").click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(OUT, "thinking.png") });
  const res = await answered;
  if (!res.ok()) throw new Error(`ask failed: ${res.status()} ${await res.text()}`);
  geo.answer = (await res.json()).content;
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, "answer.png") });
  geo.bubble = await box(".agent-thread > :last-child");
  geo.thread = await box(".agent-thread");
}
fs.writeFileSync(path.join(OUT, "geo.json"), JSON.stringify(geo, null, 2));
await browser.close();
console.log(OUT, geo);
