# Site Studio — Subscription, Billing, Entitlement & Profitability Architecture

## 1. System Overview

This document specifies the authoritative subscription, billing, and entitlement architecture of AI Site Studio.
The system decouples **user-level primary plan subscriptions** (`UserSubscription`) from **per-deployment edge hosting subscriptions** (`HostingSubscription`).

All limits, quotas, and prices originate from a single backend configuration file: [`backend/app/core/plans.py`](file:///d:/Projects/Official/AI-Site-Studio-main/AI-Site-Studio-main/backend/app/core/plans.py), mirrored on the client via [`frontend/src/lib/plans.js`](file:///d:/Projects/Official/AI-Site-Studio-main/AI-Site-Studio-main/frontend/src/lib/plans.js).

---

## 2. Plan Specifications

### 2.1 Free Tier — \$0 / ₹0
- **AI Website Generation**: 1 free trial generation per account (tracked permanently via `TrialHistory`). Subsequent AI generations require purchased token packs or an upgrade to Pro/Extreme.
- **Trial Deployment**: 1 concurrent deployment slot for a 7-day trial period on `*.site-studio.live` subdomains.
- **Custom Domains**: Disabled. No custom domain mapping on the Free tier.
- **Production Hosting**: After the 7-day trial expires, live traffic requires a standard hosting add-on (\$12.00/month).
- **Auto-Heal (AI Site Doctor)**: Disabled.
- **Template Trial History**: One free trial per template per account, permanently. Users may trial different eligible templates, but cannot re-trial previously deployed templates.

### 2.2 Pro Plan — \$19.00 / month (or \$190.00 / year — 2 Months Free)
- **Monthly AI Credits**: 150 Gemini AI credits per billing month.
- **Deployment Project Slots**: Up to 3 active deployments.
- **Included Hosting**: 1 active production hosted website included in the base subscription (\$0 hosting charge). Additional hosted websites are \$12.00/month add-ons.
- **Custom Domains**: Supported for the 1 included hosted website.
- **Auto-Heal (AI Site Doctor)**: Enabled for 1 persistently registered website, up to 10 automated repairs per billing month.
- **Deployment Rollbacks**: 10 version snapshots retained with 1-click rollback.
- **Backup Retention**: 7 days of automated daily snapshots.
- **Credit Top-Up Discount**: 40% discount on credit packs (\$6 / 50 credits).

### 2.3 Extreme Plan — \$50.00 / month (or \$500.00 / year — 2 Months Free)
- **Monthly AI Credits**: 1,000 Gemini AI credits per billing month (deducted predictably per operation).
- **Deployment Project Slots**: Fair-use project capacity (50 active project slots). Rate-limited to 15 builds/hour to prevent build farm abuse.
- **Included Hosting**: 3 active production hosted websites included in the base subscription (\$0 hosting charge). Additional hosted websites are \$12.00/month add-ons.
- **Custom Domains**: Supported for all 3 included hosted websites.
- **Promotional Domain Credit**: Annual Extreme subscribers receive a capped promotional domain subsidy up to \$15.00 for their first year (single redemption via `PromotionalDomainCredit`).
- **Auto-Heal (AI Site Doctor)**: Enabled for up to 3 persistently registered websites, up to 30 automated repairs per billing month.
- **Deployment Rollbacks**: 30 version snapshots retained.
- **Backup Retention**: 30 days of automated daily snapshots.
- **Credit Top-Up Discount**: 60% discount on credit packs (\$4 / 50 credits).

---

## 3. Database Schema & Models

The system introduces 6 new database tables managed via Alembic:

1. **`user_subscriptions`**: Tracks primary plan, status (`active`, `past_due`, `canceled`), current period start/end, grace period end, provider subscription IDs, and cancellation scheduling (`cancel_at_period_end`).
2. **`subscription_events`**: Immutable audit log of all incoming Stripe and Razorpay webhook events. Provides idempotent event deduplication via `provider_event_id`.
3. **`usage_ledger`**: Granular usage ledger logging every credit-consuming operation, provider used (Gemini/OpenAI), model name, tokens, quantity, and estimated variable infrastructure costs.
4. **`trial_history`**: Permanent audit record of trial website generations and 7-day deployment trials, enforcing the 1-trial-per-template restriction.
5. **`auto_heal_registrations`**: Tracks designated Auto-Heal deployment slots (1 for Pro, 3 for Extreme) and repair counts per billing period.
6. **`promotional_domain_credits`**: Tracks redemption of domain subsidy credits up to the \$15.00 hard cap.

---

## 4. API Endpoints

### 4.1 Subscription Routes (`/api/v1/subscriptions`)
- `GET /api/v1/subscriptions/plans`: Returns public plan specs and operation costs.
- `GET /api/v1/subscriptions/my-subscription`: Returns authenticated user plan, quotas, available credits, and renewal dates.
- `POST /api/v1/subscriptions/checkout`: Initiates Stripe Checkout Session (`mode='subscription'`) or Razorpay Subscription mandate.
- `POST /api/v1/subscriptions/cancel`: Schedules cancellation at period end (graceful access retention).
- `POST /api/v1/subscriptions/reactivate`: Restores renewal for a subscription scheduled to cancel.
- `GET /api/v1/subscriptions/usage`: Returns historical usage records from `UsageLedger`.

### 4.2 Admin Profitability Route (`/api/v1/admin/profitability`)
- `GET /api/v1/admin/profitability`: Computes 30-day gross and net revenue against variable costs:
  - Gemini AI inference costs
  - Edge hosting infrastructure
  - Build/worker compute
  - Autonomous Auto-Heal LLM repairs
  - Domain subsidies
- Flags loss-making subscribers and benchmarks blended gross margins against the 70.0% target.

---

## 5. Webhook Idempotency & Failure Handling

- Webhooks delivered by Stripe or Razorpay check `SubscriptionEvent` by `provider_event_id` prior to executing state updates. Duplicate deliveries are immediately acknowledged without double-crediting tokens.
- On payment failure, accounts are marked `past_due` with a 3-day grace period. User websites remain online during the grace period to avoid instant disruption.

