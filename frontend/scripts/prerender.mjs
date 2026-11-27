// Turns the built SPA into static HTML for the public pages, so search engines and
// visitors get the full page at once, before any script runs or the server answers.
// Runs after `vite build` and `vite build --ssr src/prerender.tsx --outDir dist-ssr`.
//
// Writes, next to dist/index.html (which it replaces with the English front page):
//   dist/no/index.html          Norwegian front page        /no
//   dist/privacy/index.html     privacy, English            /privacy
//   dist/personvern/index.html  privacy, Norwegian          /personvern
//   dist/404.html               what the backend sends with a 404
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ORIGIN = "https://tenantaccess.me";
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");

const { renderPage, pageTitle, pageDescription, previewDescription, PAGE_PATHS: PATHS } = await import(
  join(root, "dist-ssr", "prerender.js")
);

const HTML_LANG = { en: "en", no: "nb" };
const OG_LOCALE = { en: "en_US", no: "nb_NO" };

const template = readFileSync(join(dist, "index.html"), "utf8");

const escape = (text) =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function setMeta(html, attr, name, content) {
  const pattern = new RegExp(`<meta ${attr}="${name}" content="[^"]*"\\s*/?>`);
  const tag = `<meta ${attr}="${name}" content="${escape(content)}" />`;
  if (!pattern.test(html)) throw new Error(`index.html has no <meta ${attr}="${name}">`);
  return html.replace(pattern, tag);
}

function build(page, lang) {
  let html = template;
  html = html.replace(/<html lang="[^"]*">/, `<html lang="${HTML_LANG[lang]}">`);
  html = html.replace(/<title>[^<]*<\/title>/, `<title>${escape(pageTitle(page, lang))}</title>`);
  html = setMeta(html, "name", "description", pageDescription(page, lang));

  const extra = [];
  if (page === "notFound") {
    extra.push('<meta name="robots" content="noindex" />');
  } else {
    const url = `${ORIGIN}${PATHS[page][lang]}`;
    html = setMeta(html, "property", "og:url", url);
    html = setMeta(html, "property", "og:description", previewDescription(lang));
    extra.push(`<link rel="canonical" href="${url}" />`);
    extra.push(`<link rel="alternate" hreflang="en" href="${ORIGIN}${PATHS[page].en}" />`);
    extra.push(`<link rel="alternate" hreflang="nb" href="${ORIGIN}${PATHS[page].no}" />`);
    extra.push(`<link rel="alternate" hreflang="x-default" href="${ORIGIN}${PATHS[page].en}" />`);
    extra.push(`<meta property="og:locale" content="${OG_LOCALE[lang]}" />`);
    extra.push(
      `<meta property="og:locale:alternate" content="${OG_LOCALE[lang === "en" ? "no" : "en"]}" />`,
    );
  }
  html = html.replace("  </head>", `    ${extra.join("\n    ")}\n  </head>`);

  const body = renderPage(page, lang);
  if (!html.includes('<div id="root"></div>')) throw new Error('index.html has no empty <div id="root">');
  html = html.replace('<div id="root"></div>', `<div id="root">${body}</div>`);
  return html;
}

function write(relative, html) {
  const file = join(dist, relative);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, html);
  console.log(`prerendered ${relative} (${Math.round(html.length / 1024)} KB)`);
}

write("index.html", build("home", "en"));
write("no/index.html", build("home", "no"));
write("privacy/index.html", build("privacy", "en"));
write("personvern/index.html", build("privacy", "no"));
write("404.html", build("notFound", "en"));
