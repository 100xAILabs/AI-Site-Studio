# Domain purchase and managed hosting

## Customer flow

1. The customer selects a deployed Studio-hosted website and enters the domain registrant's legal contact details.
2. Studio asks GoDaddy for availability, the registration price, renewal price, fees, and required registry agreements. The customer accepts the displayed total and agreements.
3. Studio creates a one-time Stripe Checkout Session. If the quote changes before payment, Checkout is rejected and the customer must review the new quote.
4. A signed Stripe webhook confirms payment. Studio refreshes the GoDaddy quote, registers with a stable idempotency key, and polls the asynchronous registration operation.
5. Studio applies the submitted registrant contact, disables GoDaddy's default auto-renew, creates apex and `www` DNS records, and marks DNS setup complete only after those steps succeed. When `CUSTOM_DOMAIN_TLS_ENABLED=true`, Caddy provisions HTTPS certificates on first secure visit for platform domains and verified customer domains.
6. The successful-registration response shows the expiry date. The domain is a fixed-term registration and renews separately; the current flow does not auto-charge a renewal.

GoDaddy charges the payment method on the Studio GoDaddy account. Stripe separately charges the customer for the quoted registration total. If the provider confirms registration failed, Studio attempts a Stripe refund. A completed domain registration is not refunded merely because the customer later cancels hosting, subject to applicable law.

**Account ownership limitation:** domains are registered inside the Studio GoDaddy account. The registrant contact identifies the customer but does not give them the Studio account login or direct registrar controls. A production product that promises customers independent domain ownership needs a domain push/transfer or a customer-owned GoDaddy account flow before launch. A registered domain prevents deleting its attached deployment until Studio support confirms a transfer or release; expiry alone is not proof the registrar has released it.

## Monthly hosting and non-payment

- Hosting is a separate monthly Stripe subscription.
- If a renewal payment fails, the site remains available for `HOSTING_GRACE_PERIOD_DAYS` (default: 3) while Stripe can retry.
- If payment is still overdue at the deadline, the Celery worker cancels the Stripe subscription and suspends the deployment. A public-site request also fails closed after the grace deadline.
- If Stripe confirms payment before the deadline, the subscription returns to active and the site stays available.
- A customer-requested cancellation is scheduled for the end of the paid billing period. The site remains available until that period ends. There is no prorated refund for unused time, subject to applicable law.

The `celery_worker` service in `docker-compose.yml` must be running with a reachable Redis broker for timed cancellation and registrar polling jobs. Without it, a past-due site still fails closed after its grace period, but Stripe cancellation and background domain polling will not run automatically.

## Production configuration

Set these values in the backend environment; keep credentials out of the frontend:

- `GODADDY_PAT`: GoDaddy PAT with `domains.domain:read`, `domains.domain:create`, `domains.domain:update`, `domains.contact:update`, and `domains.dns:update` scopes, plus the required billing method on the GoDaddy account.
- `DEPLOYMENT_HOST_IP`: the server's publicly reachable static IPv4 address for GoDaddy apex DNS records.
- `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, and `STRIPE_WEBHOOK_SECRET`.
- `STRIPE_HOSTING_PRICE_ID`: an active Stripe Price with a monthly recurring interval.
- `HOSTING_GRACE_PERIOD_DAYS`: optional; defaults to 3.
- `FRONTEND_URL`: the public Studio frontend origin used for Checkout return links.

Configure the Stripe webhook endpoint at `/api/v1/payment/webhook/stripe` for `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `checkout.session.expired`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`, and `invoice.payment_succeeded`.

The purchased domain's DNS points at the configured server IP. The app does not issue TLS certificates itself; production HTTPS requires a TLS reverse proxy/certificate service on the server.

## Self-hosted HTTPS with Docker Compose

The included `Caddyfile` enables on-demand TLS for `aisitestudio.com` subdomains and verified tenant domains. Caddy checks `/internal/tls-authorize` before issuing each certificate. It redirects HTTP to HTTPS and proxies traffic to the API, which serves tenant static files.

Before using this setup publicly, point the Studio host and purchased tenant domains at the server, allow inbound TCP ports 80 and 443 (and UDP 443 for HTTP/3), persist the Caddy data volume, and run `docker compose up -d`. Keep `CUSTOM_DOMAIN_TLS_ENABLED=true` only when this or an equivalent TLS reverse proxy is active. For a deployment outside Docker Compose, configure its TLS proxy and certificate-authorization route before enabling that setting. Caddy provisions tenant certificates when the first HTTPS request arrives, so DNS propagation and initial certificate issuance take time.
