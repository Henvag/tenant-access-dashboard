# Screenshots

Referenced from the root `README.md`.

| File | What |
| --- | --- |
| `landing.png` | Signed-out landing, **EN**, Sign in tab |
| `norwegian.png` | Same landing with language set to **NO** |
| `grafana-login.png` | Grafana demo → **Sign in with Tenant Access** |
| `overview.png` | *(optional)* Admin Overview — needs a signed-in session |
| `people.png` | *(optional)* People with invite controls — needs a signed-in session |

Refresh the public ones:

```bash
npm install --no-save playwright@1.49.1
npx playwright install chromium
node scripts/capture-screenshots.mjs
```

Viewport: 1440×900. Blur emails before committing if you add authenticated shots.
