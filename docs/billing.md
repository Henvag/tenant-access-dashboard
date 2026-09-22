# Billing (Stripe + Vipps)

Portfolio monetization for Tenant Access: Free / Team / Business plans with seat and
app limits. Card subscriptions go through Stripe Checkout; Vipps annual is a one-shot
payment (Stripe does not support Vipps in subscription mode).

## Plans (display prices in NOK)

| Plan     | Monthly | Annual (Vipps) | Seats | Apps | Audit retention |
|----------|---------|----------------|-------|------|-----------------|
| Free     | —       | —              | 10    | 3    | 14 days         |
| Team     | 99      | 990            | 50    | 15   | 90 days         |
| Business | 249     | 2490           | 250   | 25   | 365 days        |

Owners open **Billing** in the dashboard. Without Stripe keys the UI still shows
usage and plan cards (demo mode).

## Env vars

Set on the dashboard web service (Render dashboard or `render.yaml` sync:false):

```
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_TEAM_MONTHLY=price_...
STRIPE_PRICE_BUSINESS_MONTHLY=price_...
STRIPE_PRICE_TEAM_ANNUAL=price_...
STRIPE_PRICE_BUSINESS_ANNUAL=price_...
STRIPE_VIPPS_ENABLED=true
```

Leave secrets empty locally to exercise the Billing screen without charging.

## Stripe Dashboard setup

1. Create Products + Prices (NOK) matching Team/Business monthly and annual.
2. Enable **Vipps** as a payment method (may require Stripe Vipps preview access in your country).
3. Add a webhook endpoint: `https://<your-host>/billing/webhook`
   - Events: `checkout.session.completed`, `customer.subscription.updated`,
     `customer.subscription.deleted`
4. Enable Customer Portal for cancel / payment method updates.

## How checkout works

- **Card monthly** → Checkout `mode=subscription`; webhook stores `stripe_subscription_id`
  and sets `tenant.plan`.
- **Vipps annual** → Checkout `mode=payment` with `payment_method_types` including `vipps`;
  webhook sets `plan_expires_at` to now + 365 days (no recurring Vipps charge).
- Expired prepaid plans fall back to Free until renewed.
- The audit log only returns events inside the plan's retention window. Older rows stay in the database and reappear after an upgrade.

## Local webhook testing

```
stripe listen --forward-to localhost:8000/billing/webhook
```

Use the printed `whsec_…` as `STRIPE_WEBHOOK_SECRET`.

## API

- `GET /billing/plans` — public catalog
- `GET /billing/status` — current plan + usage (auth)
- `POST /billing/checkout` — owner only; body `{ plan, method }`
- `POST /billing/portal` — Stripe Customer Portal (owner)
- `POST /billing/webhook` — Stripe signed events
