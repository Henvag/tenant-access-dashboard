import { chromium } from "playwright";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(__dirname, "..", "docs", "screenshots");
const BASE = "https://tenant-access-dashboard.onrender.com/";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(60000);

await page.goto(BASE, { waitUntil: "networkidle" });
await page.getByRole("button", { name: "EN" }).click();
await page.getByRole("heading", { name: /One sign-in/i }).waitFor();
await page.screenshot({ path: path.join(OUT, "landing.png") });

await page.getByRole("button", { name: "NO" }).click();
await page.getByRole("heading", { name: /Én innlogging/i }).waitFor();
await page.screenshot({ path: path.join(OUT, "norwegian.png") });

await page.goto("https://tenant-access-grafana.onrender.com/login", {
  waitUntil: "domcontentloaded",
});
await page.waitForTimeout(5000);
await page.screenshot({ path: path.join(OUT, "grafana-login.png") });

await browser.close();
console.log("wrote landing.png, norwegian.png, grafana-login.png");
