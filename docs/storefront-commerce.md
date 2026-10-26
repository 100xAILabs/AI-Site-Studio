# Generated store data and customer accounts

Store customer accounts, sessions, products, and orders use the separate
`COMMERCE_DATABASE_URL` connection and the `store_*` tables. They are not part
of the AI Site Studio `DATABASE_URL` or its platform user/order tables. The API
fails closed with HTTP 503 when the commerce database is not configured; it
never falls back to the Studio database.

## Configuration

Provision a separate PostgreSQL database and a database role limited to that
database. Set `COMMERCE_DATABASE_URL` in the backend's secret environment. On
startup the API creates the commerce tables if they do not exist. It does not
create a PostgreSQL database or grant itself database-administrator rights.

## API routes

The server owns password hashing, session creation and validation, product
price/inventory checks, and order persistence. Browser code can call these
routes, but must never connect to the database or decide authentication:

- `POST /api/v1/storefront/{site}/auth/register`
- `POST /api/v1/storefront/{site}/auth/login`
- `GET /api/v1/storefront/{site}/products`
- `POST /api/v1/storefront/{site}/products` (authenticated Studio site owner)
- `POST /api/v1/storefront/{site}/orders` (authenticated store customer)
- `GET /api/v1/storefront/{site}/orders/mine` (authenticated store customer)
- `GET /api/v1/storefront/{site}/orders` (authenticated Studio site owner)
- `GET /api/v1/storefront/{site}/notification-settings` (authenticated site owner)
- `PUT /api/v1/storefront/{site}/notification-settings` (authenticated site owner)

Customer accounts are scoped to a site, use scrypt password hashes, and receive
random server-validated sessions that expire after seven days. Orders snapshot
the server-side product names and prices and reduce inventory transactionally.
The order endpoint records an order with `awaiting_payment`; it does not charge
a card. When provider credentials and owner destinations are configured, the
server sends a new-order email and/or SMS containing customer name, customer
phone, purchased items, order total, and payment status. The customer email is
not included in these alerts. Email uses Resend if `RESEND_API_KEY` is set,
otherwise SMTP (`SMTP_USER`, `SMTP_PASSWORD`, and related settings). SMS uses
Twilio (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`).
Store owners configure their alert email and E.164 phone in the Deployments
dashboard. Provider credentials are never stored per store or exposed to the
browser. The order remains recorded if an alert cannot be delivered; API
response reports each channel as `sent` or `not_sent`.

Configure the separate commerce database and provider credentials in backend
secret environment variables. Store owners must configure an alert destination
in the dashboard. Twilio account approval, a permitted sender number, and
destination-country messaging rules may apply. Email/SMS provider delivery
acceptance does not guarantee inbox placement or handset delivery.
