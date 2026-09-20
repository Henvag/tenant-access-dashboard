# Screenshots

Referenced from the root `README.md`.

| File | What |
| --- | --- |
| `landing.png` | Signed-out landing, Sign in tab |
| `overview.png` | Admin Overview — stats, Your apps, recent activity |
| `people.png` | People directory + **Copy invite link** |
| `apps.png` | Registered apps + OIDC issuer endpoints |
| `audit.png` | Audit log (sign-ins and app sign-ins) |
| `norwegian.png` | Landing with language set to **NO** (Playwright) |
| `grafana-login.png` | Grafana → **Sign in with Tenant Access** (Playwright) |

Public landing / Grafana / NO can be refreshed with:

```bash
npm install --no-save playwright@1.49.1
npx playwright install chromium
node scripts/capture-screenshots.mjs
```

Admin shots are captured manually while signed in. Prefer blurring emails before a public push if you do not want addresses in the repo.
