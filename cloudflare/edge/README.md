# Edge copy of the public pages (Cloudflare Worker)

The free Render server sleeps after 15 minutes without traffic and takes 30 to 60 seconds
to wake. This Worker keeps a copy of the public pages in Cloudflare so they open at once
while Render wakes up in the background.

## What goes through it

Only these exact addresses (see `wrangler.toml`):

| Address | What |
| --- | --- |
| `/`, `/no` | Front page in English and Norwegian |
| `/privacy`, `/personvern` | Privacy page in English and Norwegian |
| `/dpa`, `/databehandleravtale` | Data processing agreement in English and Norwegian |
| `/billing/plans` | The public price list the front page shows |
| `/robots.txt`, `/sitemap.xml` | For search engines, so Google never gets a 503 from a sleeping Render |
| `/assets/*` | Scripts, styles, fonts and images (videos are passed to Render) |

Everything else, including sign-in (`/auth/*`), the OIDC provider (`/oauth/*`,
`/.well-known/*`), the API and any address with a query string such as
`/?continue=grafana`, never reaches the Worker and goes to Render as before.

On each visit it answers from its stored copy, and at most once a minute it asks Render
for fresh copies (that request is also what wakes Render). After a deploy, the first
visit can still get the previous version; the one after that gets the new one. The
response header `X-Edge-Copy: hit` shows a page came from the stored copy.

Storage is the Workers KV namespace `tenant-access-edge-pages`. It only writes when a
page changed, so it stays far inside the free plan (1,000 writes and 100,000 reads a day,
100,000 Worker requests a day).

## Turning it on (once)

1. Cloudflare dashboard, **Workers & Pages**, **Create**, **Import a repository**.
2. Pick `Henvag/tenant-access-dashboard` (connect GitHub if it asks).
3. Project name `tenant-access-edge`. Under **Advanced settings**, set **Root directory**
   (or path) to `cloudflare/edge`. Leave the build command empty and the deploy command
   as `npx wrangler deploy`.
4. **Create and deploy**. Wrangler adds the routes and the KV binding from
   `wrangler.toml`. Later changes to this folder deploy by themselves when merged.
5. Check: `curl -sI https://tenantaccess.me/no | grep -i x-edge-copy` shows `miss` the
   first time and `hit` after that.

## Turning it off

Workers & Pages, `tenant-access-edge`, **Settings**, **Domains & Routes**: remove the
routes, or delete the Worker. Render serves the very same pages itself, so nothing else
needs to change. Do this if you move Render to a paid plan that doesn't sleep, or
whenever you want to rule the Worker out while debugging.
