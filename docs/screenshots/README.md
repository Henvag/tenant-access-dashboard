# Screenshots

Referenced from the root `README.md`.

| File | What |
| --- | --- |
| `landing.png` | Signed-out landing |
| `overview.png` | Admin Overview |
| `people.png` | People + invite link |
| `apps.png` | Apps + OIDC issuer |
| `audit.png` | Audit log |
| `grafana.png` | Grafana home after SSO |
| `outline.png` | Outline workspace after SSO |
| `norwegian.png` | Landing in Norwegian |
| `billing.png` | Billing on the Team plan |
| `grafana-login.png` | Grafana login button (optional) |

Dashboard shots (landing, overview, people, apps, audit, billing) come from the read-only demo company: run the app locally against a role that enforces RLS, then `BASE=http://localhost:8000 node scripts/capture-demo.mjs` (needs Playwright). Grafana and Norwegian shots: `node scripts/capture-screenshots.mjs`.
