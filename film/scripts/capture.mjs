// Screens for the landing film, captured from the demo company at 2x (2880 x 1800).
//
//   BASE=http://localhost:8000 \
//   FILM_DB_URL=postgresql://postgres@localhost:5432/access_dashboard \
//   node film/scripts/capture.mjs
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
const OUT = path.join(__dirname, "..", "assets", "shots");
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
await page.evaluate(() => localStorage.setItem("tenant-access.lang", "en"));
await page.reload({ waitUntil: "networkidle" });
await page.getByRole("button", { name: "Explore the live demo" }).first().click();
await page.getByText("read-only demo").waitFor();

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

await open("overview");
await shot("overview");
await open("apps");
await shot("apps");

const disabledAt = sql(`select disabled_at from users where email = '${JONAS}'`);
sql(`update users set disabled_at = null where email = '${JONAS}'`);
try {
  await open("people");
  const row = page.locator("tbody tr", { hasText: "Jonas Lie" });
  await shot("people-active");
  await row.locator("button").last().click();
  await page.getByRole("menuitem", { name: "Disable" }).waitFor();
  await shot("people-menu");
} finally {
  const restore = disabledAt ? `'${disabledAt}'` : "null";
  sql(`update users set disabled_at = ${restore} where email = '${JONAS}'`);
}
await open("people");
await shot("people-disabled");

await open("audit");
await shot("audit");
await shot("audit-full", { fullPage: true });

await browser.close();
console.log(`wrote 7 screens to ${OUT}`);
// Positions in compositions/demo.html (camera regions, cursor points, the audit scroll and its
// veils) are CSS pixels measured on these screens. Check them after a layout change.
