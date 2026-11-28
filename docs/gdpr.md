# Personal data: roles, routines and open gaps

Internal notes for running Tenant Access under GDPR (personopplysningsloven in Norway). This is a working document, not legal advice. Check it against Datatilsynet's guidance, or with a lawyer, before relying on it with customers.

The public version of what is stored and who handles it is the privacy page (`frontend/src/PrivacyPage.tsx`, served at `/privacy` and `/personvern`). Keep the two in step.

## Roles

| Data | Controller | Tenant Access is |
| --- | --- | --- |
| People, apps, audit log, webhooks, AI keys of a customer company | The customer company | Processor (databehandler) |
| Visits to tenantaccess.me (Cloudflare Web Analytics) | Teknologihjelpen | Controller |
| Billing contact and Stripe IDs | Teknologihjelpen | Controller |

Operator: Teknologihjelpen (ENK, Norway, org. no. 829 416 042). Contact for privacy questions: post@teknologihjelpen.no.

## Subprocessors

Listed on the privacy page. Today: Render (service), Neon (database), both AWS us-west-2 in Oregon, USA; Cloudflare (DNS, proxy, analytics); Google and Microsoft (sign-in); Stripe (payments); OpenAI, Anthropic or Google only when a company adds its own AI key.

Before adding a new one: update the privacy page in both languages in the same pull request, and tell paying customers ahead of the change, as the data processing agreement requires.

Check once a year that the data processing agreement with Render, Neon, Cloudflare and Stripe is accepted on each account and still includes the EU standard contractual clauses.

## Retention

| Data | Kept |
| --- | --- |
| People, apps, grants | Until the owner deletes them, or deletes the company |
| Audit events | Until the owner deletes the company. The plan only limits how far back the log shows (14/90/365 days). Deleting a person blanks their name, email and IP in their events. |
| Webhook deliveries | 30 days |
| Auth codes | Purged 10 minutes after expiry |
| Partner invites | 7 days valid; expired rows are replaced on the next invite |
| Session cookie | 12 hours |
| Ask and agent conversations | Not stored |
| Render logs | Render's own retention. Request logs hold method, path, status and timing, no IP or email. |

## Requests from people

A person who asks to see, correct, export or delete their data is normally the customer company's employee, so the company is the one to answer.

1. If the request comes to us, tell the person it has been passed on and forward it to the company's owner within a few days.
2. Help the owner if the dashboard can't do it: People (change role, switch off, delete), Audit (CSV export), Organization (delete company).
3. Requests about website visits or billing are ours. Answer within one month.

## Breach routine

A breach is any event where personal data is lost, changed, exposed or made unavailable without permission: a leaked database URL or secret, a cross-tenant bug, a stolen laptop with access, a compromised GitHub, Render, Neon or Cloudflare account.

1. **Stop it.** Rotate the exposed secret, revoke sessions (change `SESSION_SECRET`), roll back the deploy, or take the service down.
2. **Write it down** as you go, in a private note: what happened, when it was found, which companies and how many people, what data, what was done. Keep this log even for small incidents; GDPR art. 33(5) requires it.
3. **Tell the affected customer companies without undue delay**, ideally within 24 hours, with what is known so far. They are the controllers and have 72 hours from when they learn of it to report to Datatilsynet.
4. **For our own data** (website visits, billing): if there is any risk to people, report to Datatilsynet within 72 hours at datatilsynet.no (Melde avvik). If the risk is high, also tell the people affected.
5. **Afterwards**, fix the cause and add a line to `docs/ops.md` if the lesson is operational.

## Open gaps

See the gap list shared on 27 November 2026 in the project. Short version: no published data processing agreement yet, audit events are never deleted automatically, no one-click export of a company's data, data is hosted in the USA.
