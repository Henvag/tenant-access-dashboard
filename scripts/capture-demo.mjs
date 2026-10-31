// Screenshots of the read-only demo company for the README and the landing-page tour.
//
//   BASE=http://localhost:8000 node scripts/capture-demo.mjs
//
// BASE must serve the built frontend with a database role that enforces RLS,
// otherwise the demo refuses to start.
import { chromium } from "playwright";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, "..");
const DOCS = path.join(ROOT, "docs", "screenshots");
const BASE = (process.env.BASE || "http://localhost:8000").replace(/\/$/, "");

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(30000);

await page.goto(BASE, { waitUntil: "networkidle" });
await page.evaluate(() => localStorage.setItem("tenant-access.lang", "en"));
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(1000); // let the fade-in finish
await page.screenshot({ path: path.join(DOCS, "landing.png") });

await page.getByRole("button", { name: "Explore the live demo" }).first().click();
await page.getByText("read-only demo").waitFor();

// The tour and README show the product itself, so hide the demo notice.
async function shot(view, name) {
  await page.goto(`${BASE}/?view=${view}`, { waitUntil: "networkidle" });
  await page.addStyleTag({ content: ".demo-banner { display: none !important; }" });
  // Show the public issuer instead of the local one on the Apps page.
  await page.evaluate((base) => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.nodeValue.includes(base)) {
        node.nodeValue = node.nodeValue.replaceAll(base, "https://tenantaccess.me");
      }
    }
  }, BASE);
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(DOCS, `${name}.png`) });
}

for (const view of ["overview", "people", "apps", "audit", "billing"]) {
  await shot(view, view);
}

await browser.close();
console.log(`wrote landing, overview, people, apps, audit and billing to ${DOCS}`);

// The tour uses WebP copies (quality 80) of overview, people, apps and audit, plus
// grafana-login.png saved as grafana.webp, in frontend/src/assets/tour/.
