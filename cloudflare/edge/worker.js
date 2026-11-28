// Tenant Access edge copy: serves the public pages from Cloudflare so they open at once,
// even while the free Render server is asleep.
//
// Only the paths listed in wrangler.toml reach this Worker. Every other request (sign-in,
// /oauth, /.well-known, the API) goes straight to Render without passing through here.
//
// How it works:
//  - The public pages (/, /no, /privacy, /personvern, /dpa, /databehandleravtale) are kept
//    in Workers KV. A visit gets
//    the stored copy straight away, and in the background the Worker asks Render for a
//    fresh one (which also wakes Render up) and stores it if it changed.
//  - The scripts, styles, fonts and images those pages load (/assets/...) are kept too.
//  - Anything that can't be answered from KV is passed to Render unchanged.
//
// Turning it off: remove the routes (or delete the Worker). Render serves the same pages
// itself, so nothing else needs to change.

const PAGES = new Set(["/", "/no", "/privacy", "/personvern", "/dpa", "/databehandleravtale"]);
// Files search engines fetch. A 503 from a sleeping Render here makes Google treat the
// whole site as blocked (robots.txt) or the sitemap as unreadable.
const CRAWLER_FILES = new Set(["/robots.txt", "/sitemap.xml"]);
// Public JSON the front page reads, the same for every visitor.
const PUBLIC_JSON = new Set(["/billing/plans"]);
// Videos are fetched in byte ranges, which KV copies don't answer. They go to Render.
const PASS_THROUGH_ASSET = /\.(mp4|webm)$/;
// How often one Cloudflare location asks Render for a fresh copy of a page.
const REFRESH_SECONDS = 60;
// KV holds values up to 25 MiB.
const MAX_BYTES = 20 * 1024 * 1024;
// Headers from Render worth keeping on the stored copy.
const KEEP_HEADERS = [
  "content-type",
  "x-content-type-options",
  "x-frame-options",
  "referrer-policy",
  "permissions-policy",
];

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    // Routes match exact paths, so a request with a query string, or any method other
    // than GET, only gets here for /assets/*. Pass those through as they are.
    if (request.method !== "GET" || url.search) return fetch(request);
    try {
      if (url.pathname.startsWith("/assets/")) return await asset(request, url, env, ctx);
      if (PAGES.has(url.pathname) || PUBLIC_JSON.has(url.pathname) || CRAWLER_FILES.has(url.pathname)) {
        return await page(url, env, ctx);
      }
    } catch (error) {
      console.error("edge copy failed, passing to Render", error);
    }
    return fetch(request);
  },
};

async function page(url, env, ctx) {
  const key = `page:${url.pathname}`;
  const stored = await env.PAGES.getWithMetadata(key, "arrayBuffer");
  ctx.waitUntil(refreshIfDue(url, env));
  if (stored.value) return respond(stored.value, stored.metadata, "hit");

  // Nothing stored yet: wait for Render this once, then keep the copy.
  const fresh = await fetchClean(url);
  if (!storable(fresh)) return fresh;
  const body = await fresh.arrayBuffer();
  const metadata = metadataFor(fresh, await digest(body));
  ctx.waitUntil(storePage(key, body, metadata, url, env));
  return respond(body, metadata, "miss");
}

async function asset(request, url, env, ctx) {
  if (PASS_THROUGH_ASSET.test(url.pathname)) return fetch(request);
  const key = `asset:${url.pathname}`;
  const stored = await env.PAGES.getWithMetadata(key, "arrayBuffer");
  if (stored.value) return respond(stored.value, stored.metadata, "hit");
  const fresh = await fetch(request);
  if (!storable(fresh)) return fresh;
  const body = await fresh.arrayBuffer();
  const metadata = metadataFor(fresh, null);
  if (body.byteLength <= MAX_BYTES) ctx.waitUntil(env.PAGES.put(key, body, { metadata }));
  return respond(body, metadata, "miss");
}

/** Ask Render for fresh copies of all the public pages, at most once a minute per
 * location, so a visit to one page also keeps the others current. */
async function refreshIfDue(url, env) {
  const cache = caches.default;
  const marker = new Request("https://edge-refresh.invalid/");
  if (await cache.match(marker)) return;
  await cache.put(
    marker,
    new Response("", { headers: { "Cache-Control": `max-age=${REFRESH_SECONDS}` } }),
  );

  // Wake the server (and its database) now, so a sign-in a few seconds later is quick.
  const wake = fetch(new URL("/health", url.origin), { headers: { "User-Agent": "tenant-access-edge" } })
    .then((response) => response.body?.cancel())
    .catch(() => undefined);

  // The page being visited first.
  for (const path of new Set([url.pathname, ...PAGES, ...PUBLIC_JSON, ...CRAWLER_FILES])) {
    await refreshOne(new URL(path, url.origin), env).catch((error) =>
      console.error(`refresh of ${path} failed`, error),
    );
  }
  await wake;
}

async function refreshOne(url, env) {
  const fresh = await fetchClean(url);
  if (!storable(fresh)) return fresh.body?.cancel();
  const body = await fresh.arrayBuffer();
  const hash = await digest(body);
  const key = `page:${url.pathname}`;
  const current = await env.PAGES.getWithMetadata(key, "stream");
  current.value?.cancel();
  // KV allows 1,000 writes a day on the free plan, so only write what changed.
  if (current.metadata?.hash !== hash) {
    await storePage(key, body, metadataFor(fresh, hash), url, env);
  }
}

/** Keep a page, and every /assets file it needs, so the stored page never points at a
 * file Render has since replaced. */
async function storePage(key, body, metadata, url, env) {
  if (metadata.type.startsWith("text/html")) {
    await storeAssets(new TextDecoder().decode(body), url, env, new Set());
  }
  await env.PAGES.put(key, body, { metadata });
}

async function storeAssets(text, url, env, seen) {
  const paths = new Set(text.match(/\/assets\/[A-Za-z0-9._-]+/g) ?? []);
  // Scripts load their other chunks by a path relative to /assets/, such as "./index-abc.js".
  for (const [, name] of text.matchAll(/"\.\/([A-Za-z0-9._-]+\.js)"/g)) paths.add(`/assets/${name}`);
  for (const path of paths) {
    if (seen.has(path) || PASS_THROUGH_ASSET.test(path)) continue;
    seen.add(path);
    const key = `asset:${path}`;
    const existing = await env.PAGES.getWithMetadata(key, "stream");
    if (existing.value) {
      existing.value.cancel();
      continue; // asset names carry a content hash, so a stored one never changes
    }
    const response = await fetchClean(new URL(path, url.origin)).catch(() => null);
    if (!response || !storable(response)) continue;
    const body = await response.arrayBuffer();
    if (body.byteLength > MAX_BYTES) continue;
    const metadata = metadataFor(response, null);
    await env.PAGES.put(key, body, { metadata });
    // Scripts and styles point at further files (chunks, fonts, images).
    if (/\.(js|css)$/.test(path)) await storeAssets(new TextDecoder().decode(body), url, env, seen);
  }
}

/** A request to Render with no cookies or other visitor headers, so the copy is the
 * same page any visitor gets. */
function fetchClean(url) {
  return fetch(url.toString(), {
    headers: { Accept: "*/*", "User-Agent": "tenant-access-edge" },
    redirect: "manual",
  });
}

function storable(response) {
  const length = Number(response.headers.get("content-length") || 0);
  return response.status === 200 && !response.headers.has("set-cookie") && length <= MAX_BYTES;
}

function metadataFor(response, hash) {
  const headers = {};
  for (const name of KEEP_HEADERS) {
    const value = response.headers.get(name);
    if (value) headers[name] = value;
  }
  return { type: headers["content-type"] || "application/octet-stream", headers, hash };
}

function respond(body, metadata, state) {
  const headers = new Headers(metadata?.headers ?? {});
  const type = metadata?.type ?? "";
  if (type.startsWith("text/html")) {
    // Same as Render: the browser always checks for a newer page.
    headers.set("Cache-Control", "no-cache, must-revalidate");
  } else if (type.includes("json")) {
    headers.set("Cache-Control", "no-store");
  } else if (type.startsWith("text/plain") || type.includes("xml")) {
    // robots.txt and sitemap.xml keep their names when they change.
    headers.set("Cache-Control", "public, max-age=3600");
  } else {
    headers.set("Cache-Control", "public, max-age=31536000, immutable");
  }
  headers.set("X-Edge-Copy", state);
  return new Response(body, { status: 200, headers });
}

async function digest(body) {
  const hash = await crypto.subtle.digest("SHA-256", body);
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
