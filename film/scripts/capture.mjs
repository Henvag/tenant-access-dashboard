// Screens for the landing film, captured from the demo company at 2x (2880 x 1800).
//
//   BASE=http://localhost:8000 \
//   FILM_DB_URL=postgresql://postgres@localhost:5432/access_dashboard \
//   FILM_LANG=en node film/scripts/capture.mjs      # then FILM_LANG=no
//
// Screens go to assets/shots/<lang>/, with geo.json: the boxes (CSS pixels) that the camera
// regions and cursor points in compositions/demo.html are taken from.
//
// BASE serves the built frontend from a local backend whose database role enforces RLS (the demo
// refuses to start otherwise). FILM_DB_URL is the same local database as its owner: the seeded
// Jonas Lie is disabled, so the script briefly clears disabled_at to film him as an active member
// and opening his menu, then restores the original value. Both must point at localhost.
import { chromium } from "playwright";
import { execFileSync } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const LANG = process.env.FILM_LANG === "no" ? "no" : "en";
const OUT = path.join(__dirname, "..", "assets", "shots", LANG);
const T = {
  en: { demo: "Explore the live demo", banner: "read-only demo", disable: "Disable" },
  no: { demo: "Utforsk live-demoen", banner: "skrivebeskyttet demo", disable: "Deaktiver" },
}[LANG];
const BASE = (process.env.BASE || "http://localhost:8000").replace(/\/$/, "");
const DB = process.env.FILM_DB_URL || "";
const JONAS = "jonas.lie@nordlys.example";

const isLocal = (u) => ["localhost", "127.0.0.1"].includes(new URL(u).hostname);
if (!isLocal(BASE) || !DB || !isLocal(DB.replace(/^postgres(ql)?:/, "http:"))) {
  console.error("BASE and FILM_DB_URL must both point at localhost. This script edits the database.");
  process.exit(1);
}
const sql = (q) => execFileSync("psql", [DB, "-tAc", q]).toString().trim();

fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
page.setDefaultTimeout(30000);

await page.goto(BASE, { waitUntil: "networkidle" });
await page.evaluate((lang) => localStorage.setItem("tenant-access.lang", lang), LANG);
await page.reload({ waitUntil: "networkidle" });
await page.getByRole("button", { name: T.demo }).first().click();
await page.getByText(T.banner).waitFor();

async function open(view) {
  await page.goto(`${BASE}/?view=${view}`, { waitUntil: "networkidle" });
  await page.addStyleTag({
    content: ".demo-banner { display: none !important; } * { transition: none !important; animation: none !important; }",
  });
  // Show the public issuer instead of the local one.
  await page.evaluate((base) => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.nodeValue.includes(base)) node.nodeValue = node.nodeValue.replaceAll(base, "https://tenantaccess.me");
    }
  }, BASE);
  await page.mouse.move(5, 895);
  await page.waitForTimeout(400);
}
const shot = (name, opts = {}) => page.screenshot({ path: path.join(OUT, `${name}.png`), ...opts });
const geo = {};
// Boxes in page coordinates (scroll included), rounded to whole CSS pixels.
const measure = (selector, text) =>
  page.evaluate(
    ([sel, txt]) =>
      [...document.querySelectorAll(sel)]
        .filter((e) => e.getBoundingClientRect().width > 0 && (!txt || e.textContent.includes(txt)))
        .map((e) => {
          const r = e.getBoundingClientRect();
          return { text: e.textContent.trim().slice(0, 40), x: Math.round(r.x), y: Math.round(r.y + scrollY), w: Math.round(r.width), h: Math.round(r.height) };
        }),
    [selector, text],
  );

await open("overview");
geo.nav = await measure(".nav-item");
geo.mark = await measure(".sidebar .brand-mark");
geo.tiles = await measure(".tile");
await shot("overview");
await open("apps");
geo.pills = await measure(".app-list .pill");
await shot("apps");

const disabledAt = sql(`select disabled_at from users where email = '${JONAS}'`);
sql(`update users set disabled_at = null where email = '${JONAS}'`);
try {
  await open("people");
  const row = page.locator("tbody tr", { hasText: "Jonas Lie" });
  geo.jonasRow = await measure("tbody tr", "Jonas Lie");
  await shot("people-active");
  await row.locator("button").last().click();
  await page.getByRole("menuitem", { name: T.disable }).waitFor();
  geo.menuItems = await measure("[role=menuitem]");
  await shot("people-menu");
} finally {
  const restore = disabledAt ? `'${disabledAt}'` : "null";
  sql(`update users set disabled_at = ${restore} where email = '${JONAS}'`);
}
await open("people");
await shot("people-disabled");

await open("audit");
geo.auditJonas = await measure("tbody tr", "Jonas Lie");
geo.auditJonasCells = await page.evaluate(() =>
  [...document.querySelectorAll("tbody tr")]
    .filter((row) => row.textContent.includes("Jonas Lie"))
    .flatMap((row) => [...row.querySelectorAll(".pill, .reason-text")])
    .map((e) => {
      const r = e.getBoundingClientRect();
      return { text: e.textContent.trim(), x: Math.round(r.x), y: Math.round(r.y + scrollY), w: Math.round(r.width), h: Math.round(r.height) };
    }),
);
await shot("audit");
await shot("audit-full", { fullPage: true });

await browser.close();
fs.writeFileSync(path.join(OUT, "geo.json"), JSON.stringify(geo, null, 1));
console.log(`wrote 7 screens and geo.json to ${OUT}`);
// Positions in compositions/demo.html (camera regions, cursor points, the audit scroll and its
// veils) are CSS pixels measured on these screens. Check them after a layout change.
