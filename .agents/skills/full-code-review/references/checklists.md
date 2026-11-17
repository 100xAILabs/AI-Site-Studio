# Lens checklists

Each item is a question to answer from the source. Confirm it by following the code, not by grepping alone. Adapt the framework names to the stack in front of you: the examples are FastAPI/Python and React/JS, and the questions carry over to other stacks.

## 1. Security: auth, authorization, payments

**Authentication**
- OAuth:
  - Is the `state` parameter checked in every environment, or only skipped in "development"?
  - Is the redirect URI or frontend URL taken from an allowlist?
  - Is the provider's email used only when `verified`?
  - Is there an `emails[0]`, placeholder-email or "any email" fallback?
  - Are existing accounts auto-linked by email? That leads to account takeover.
- Account linking: is a "connect provider" flow started by a GET with `?token=`? That is link-CSRF, and it puts the token in URLs.
- Login CSRF: does the frontend accept any `?token=` in the URL and log in with it?
- JWT:
  - Is there a default or weak secret, and is it accepted when `ENVIRONMENT` is unset?
  - What are the algorithm and expiry?
  - Is there revocation (token version)?
  - Does a password reset invalidate sessions?
  - Is the token type checked (access vs refresh)?
  - Are tokens accepted from the query string?
  - Where does the frontend store them (localStorage vs httpOnly cookie)?
- OTP:
  - Is the code printed or logged?
  - Is the attempt counter atomic (`INCR` first, then compare)?
  - Is the comparison constant-time?
  - Is there a per-address daily send cap and expiry?
- Is the email lookup case-sensitive, allowing duplicate accounts?

**Authorization (do this for every route file)**
- List each route's auth dependency: none / optional user / required user / admin.
- For every route that takes an ID: does the query filter by owner (`user_id == current_user.id`) or check admin? Optional-user routes that mutate data are red flags.
- Admin: is the role read from the database or trusted from the token or client? Can a user set their own role (`PUT /me {role}`)?
- Ownership claims by weak signals: matching display name, substring match on file IDs, "any row exists" checks (`select(...).where(user_id==me).limit(1)` without the resource filter).
- Fields users can edit that they should not: status, featured flags, price on others' items, `seller_id`, file references.

**Payments and money**
- Is the price, amount or plan taken from the client?
- Signature verification:
  - Is the HMAC computed over values the client sent, or over the gateway order stored on the server for *this* order?
  - Can one valid signature complete a different order (replay)?
  - Is there a unique constraint on the gateway payment ID?
- Any endpoint that marks an order paid or completed without a gateway proof ("activate", "confirm", "mock", "manual")?
- Webhooks:
  - Does verification fail open when the secret is empty?
  - Is the event deduplicated *after* verification and inside the fulfilment transaction?
  - Is there a row lock (`SELECT ... FOR UPDATE`)?
  - Is the amount and currency checked?
  - Does it return 5xx on failure so the provider retries?
  - Are "mock" signatures accepted in default environments?
- Checkout sessions: is the redeemed session bound to the current user and to the right product type?
- Recurring charges and renewals: does a failed charge ever fall through to "paid"? Can any user trigger a batch for all users?
- Payouts:
  - Are earnings computed from captured payments, net of refunds, after a hold period?
  - Do self-purchases count?
  - Is there admin approval and an idempotency key?
  - Is currency conversion handled?

## 2. Security: code execution, AI, deploy, infra

- **File paths:**
  - Is `os.path.join`, `Path /` or `send_file` used with user input?
  - An absolute path discards the base directory. Check `..`, `%2f`, and IDs taken from `Referer`.
  - Does each read or write `resolve()` and check `is_relative_to(root)`?
  - Do fallback loops scan other users' directories?
- **Archives:** zip-slip on extract; symlinks followed on `zip.write`, `shutil.copytree` and `git clone` (`core.symlinks=false`).
- **Subprocess and builds:**
  - Do `npm install`, `pip install`, `make` or user `build_command` run on the API host?
  - Do lifecycle scripts run (`--ignore-scripts`)? `npm run build` runs the attacker's script anyway, so a sandbox (container, no network, no mounts, non-root, CPU/memory/time limits) is the real fix.
  - Is the environment passed to the child scrubbed?
  - Can user env vars override `NODE_OPTIONS` or `npm_config_*`?
  - Is there a timeout?
- **AI/LLM:**
  - Can prompts make the model write code that is then executed?
  - Does a "debug/auto-fix" loop rerun builds with the full environment?
  - Are AI endpoints callable anonymously, without rate limits or credit checks?
  - Are request sizes capped?
  - Are AI-written file paths contained?
- **SSRF:** server-side fetch of user URLs (webhooks, imports, previews, image fetch) without an allowlist or private-IP block.
- **User-generated HTML:**
  - Served from the app or API origin?
  - Sandbox CSP with `allow-same-origin`?
  - `Access-Control-Allow-Origin: *`?
  - Unescaped interpolation into HTML (`f"<h1>{name}</h1>"`)?
- **Paywall and content:**
  - Are clean or watermarked editions chosen by a query parameter?
  - Do signed URLs leave parameters out of the HMAC, or last for years?
  - Does preview serve raw source files?
  - Do forks or clones inherit download rights?
  - Can drafts be fetched with guessable IDs?
  - Do flags like `?clean=1` remove watermarks?
- **Multi-tenant hosting:**
  - Is a custom domain routed before verification?
  - Does verification accept an A record pointing at the platform IP, or use a substring CNAME match?
  - Does the on-demand TLS "ask" endpoint approve any subdomain (certificate exhaustion)?
  - Is `/internal/*` reachable through the proxy?
  - Does an unknown host fall back to some tenant's site?
  - Is the entitlement or expiry check skipped on a fast path?
- **Unauthenticated actions on others' resources:** "report", "auto-fix", "revoke" or "restore" endpoints that accept an ID and act as the owner.
- **Infrastructure:**
  - Containers running as root.
  - Source bind-mounted with `--reload` in the production compose.
  - No `.dockerignore`, so `.env` is baked into the image.
  - Default `ENVIRONMENT=development` enables mocks or debug.
  - `DEBUG=true` in `.env.example`.
  - Checks written as `== "production"` fail open for "prod" or "staging".
  - Redis/Celery TLS set to `CERT_NONE`.
  - Docs endpoints exposed.
- **Secrets:** hardcoded keys, committed `.env`, secrets in git history, secrets logged or printed.

## 3. Privacy

- **Inventory the PII in the models:**
  - email, phone, name, address, IP, user agent;
  - bank, UPI, PAN, card data;
  - OAuth tokens;
  - business contact data;
  - end-customer data (the platform acting as processor).
- **At rest:** is sensitive data plaintext that should be encrypted (bank details, OAuth tokens) or not stored at all (OTP, full gateway payloads with phone/UPI/card)?
- **In APIs:**
  - Do response schemas return full bank numbers, IPs, other users' emails?
  - Do public endpoints (incidents, previews, creator profiles) leak PII?
  - Can preview sessions be read without auth, and do they expire?
- **In logs:** grep `print(`, `logger.*(` and `console.log` for email, OTP, token, license key, provider response bodies, full request bodies and IPs.
- **To third parties:**
  - What goes into AI prompts?
  - Geo-IP lookups, especially over plain HTTP or on non-commercial tiers.
  - Analytics scripts.
  - Email and SMS providers.
  - Registrars.

  Compare that list with the privacy policy.
- **Covert collection:** code shipped to customers' sites that beacons back, or embeds buyer email or license keys in delivered code.
- **Frontend:**
  - Is the whole `user` object persisted to localStorage?
  - Is PII in URLs or query strings?
  - Are tokens in URLs?
- **Rights:**
  - Self-service deletion: anonymise and keep financial records, rather than a cascade hard-delete.
  - Data export.
  - Consent record and version.
  - Grievance officer contact (DPDP).
  - Children's age threshold (DPDP: under 18).
- **Retention:** is there a scheduled purge for previews, analytics, logs, tamper or incident records, orphaned files and build logs? Is a scheduler (cron, Celery beat) even present?
- **Policy versus code:** list every statement in the privacy policy that the code makes false.

## 4. Architecture and system design

- Five-line "as built" description: process model, where heavy work runs, where state lives, how the schema is managed, how it is deployed. Note drift between docs and code (README hosting story vs config, ADRs vs implementation).
- **Layering:** business logic in route handlers (count `db.execute` in routes vs repositories/services); god files and god functions (give line ranges).
- **Async correctness:**
  - Sync SDK calls (Stripe, Razorpay, boto3, requests) inside `async def`.
  - `time.sleep` and sync file I/O in handlers.
  - DB sessions held across slow external calls.
- **Long work in requests:**
  - Builds, deploys or AI generation inline in HTTP/SSE handlers.
  - `BackgroundTasks` or threads used for durable work, which is lost on restart.
  - Client disconnect cancelling paid work.
- **Schema:**
  - Is Alembic/migrations the only path, or is there `create_all` plus startup `ALTER ... except: pass`?
  - Do models match the migrations?
  - Is there a baseline?
- **State and scaling:**
  - Per-process caches, locks and dicts with more than one worker.
  - Local disk for artifacts with no volume.
  - Startup or shutdown hooks that wipe shared state.
- **Data:**
  - Blobs in the database by default.
  - Silent fallbacks from object storage to the database.
  - Missing indexes on hot lookups (host resolution, webhook keys).
  - N+1 admin queries.
  - Unpaginated lists.
- **Reliability:** timeouts and retries on external calls; idempotency keys; transactions around money; a scheduler for periodic jobs.
- **Config:** dev defaults leaking to prod; one compose file used for both; environment checks scattered as string compares.
- **Testing and CI:**
  - Is there CI?
  - Does the test DB match production (SQLite vs Postgres)?
  - Are the critical paths covered (payments, auth, entitlements)?
  - Are tests mock-heavy?
  - Are there frontend tests?
- **Observability:** count of `print` vs logger; `except: pass` count; health check covering the DB; request IDs; error tracking.
- **Done well:** list the patterns worth copying (idempotent payouts, retries with timeouts, fail-closed config).

## 5. Code quality

- **Bugs:**
  - Imports missing from requirements.
  - Names used without import (`timedelta`, `func`).
  - Unawaited coroutines.
  - Mutable defaults.
  - Swallowed exceptions reporting success.
  - Over-broad deletes (`"draft" in name`).
  - Race conditions.
  - Naive vs aware datetimes.
  - Float money.
  - Route shadowing by catch-all routes registered first.
- **Frontend:**
  - Library API misuse after major upgrades (e.g. React Query v5 `invalidateQueries({ queryKey })`).
  - Effects without bounds (endless polling).
  - Blocking `alert()`.
  - Components with hundreds of `useState` calls.
  - No `React.lazy` for routes.
- **Duplication:**
  - Multiple API clients or base URLs.
  - Business rules copied between frontend and backend (prices, tax).
  - Duplicate routes, classes and helpers.
  - Several email senders.
- **Size:** files over ~1,500 lines and functions over ~200 lines. Name the seams by line range and target file, not "split it".
- **Dependencies:** unused packages (zero imports), duplicates, dev tools in production requirements, unpinned versions, broken lint config.
- **Dead code and junk:** never-imported files, leftover framework code, one-off scripts, committed binaries, AI output dumps, local DB folders, root package files nothing uses.
- **API consistency:**
  - 200 with `{"success": false}`.
  - Untyped `dict` payloads with hand validation.
  - Owner lookup copy-pasted many times (make it a dependency).
- **Tests:** do they import current code? Do they test behaviour or mocks? Do they use deprecated fixtures?
