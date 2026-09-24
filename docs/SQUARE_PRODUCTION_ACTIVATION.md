# Square Production Activation — steps Marcos must perform

**Status: NOT activated.** This app currently runs against **Square Sandbox only**. Nothing here has been
done yet — this document is the checklist for switching from Sandbox to a real, live Square account when
OG is ready to accept real payments. Do not skip steps or reorder the "test before you trust it" ones.

No secret values are written anywhere in this document, in `CLAUDE.md`, or in git history. Every credential
below lives only in the server's own environment variables (`.env` locally, or your host's secret manager
in production), which is already excluded from source control (`.gitignore`).

---

## 1. Square Developer Dashboard — production application

1. Sign in at [developer.squareup.com](https://developer.squareup.com) with OG's real Square business account
   (not a personal/sandbox-only account).
2. Open the application already used for Sandbox (or create a new one) and switch to its **Production**
   tab — Square gives every application both a Sandbox and a Production credential set under the same app.
3. Note the **Production Application ID** (starts `sq0idp-...`). This is safe to expose to the browser (it
   identifies the app to Square's Web Payments SDK) but should still only be set via environment variables,
   not hard-coded.
4. Generate/copy the **Production Access Token**. This is a secret — treat it exactly like a password. Never
   commit it, never paste it into chat/Slack/email, never put it in a screenshot.

## 2. Production Location

1. In the Square Dashboard (not the Developer Dashboard), confirm OG's business **Location** is fully set up
   (business name, address, bank account for payouts) under Account & Settings.
2. In the Developer Dashboard's Production tab, note the **Location ID** for that location.

## 3. Webhook endpoint (production)

1. This app's webhook endpoint is `POST https://<your-production-domain>/webhooks/square` — it does **not**
   take a language prefix and does **not** require a customer session, because Square calls it
   server-to-server.
2. In the Developer Dashboard -> your application -> **Webhooks**, add a new **Production** subscription
   pointing at that exact URL.
3. Subscribe to at minimum: `payment.created`, `payment.updated`, `refund.created`, `refund.updated`.
   (Adding more event types is harmless — `app.payments.handle_square_webhook_event` ignores anything it
   doesn't recognize.)
4. Square will show a **Signature Key** for this webhook subscription — copy it. This is a secret.

## 4. HTTPS requirement

Square **requires HTTPS** for both the webhook endpoint and the page that loads the Web Payments SDK in
production (Sandbox is more lenient about this in local development). Confirm the production domain has a
valid TLS certificate before proceeding — an HTTP-only deployment cannot go live with Square.

## 5. Environment variables (production server)

Set these on the production server's environment (never in a committed file):

| Variable | Value |
|---|---|
| `SQUARE_ENVIRONMENT` | `production` |
| `SQUARE_APPLICATION_ID` | the Production Application ID from step 1 |
| `SQUARE_ACCESS_TOKEN` | the Production Access Token from step 1 |
| `SQUARE_LOCATION_ID` | the Location ID from step 2 |
| `SQUARE_WEBHOOK_URL` | the exact webhook URL you registered in step 3 (must match character-for-character, including `https://` and no trailing slash) |
| `SQUARE_WEBHOOK_SIGNATURE_KEY` | the Signature Key from step 3 |
| `SQUARE_ALLOW_PRODUCTION` | `1` |

**`SQUARE_ALLOW_PRODUCTION=1` is a deliberate second switch.** Even with `SQUARE_ENVIRONMENT=production` set,
`app/square_client.py` refuses to build a live Square client unless this is *also* set — a safeguard against
a single mistyped/misapplied environment variable accidentally moving real money. Only set it once you have
completed every step below and are genuinely ready to accept live charges.

Restart the application after setting these so the new configuration takes effect.

## 6. Production test transaction (small, real money)

Before telling any real customer to pay:

1. With `SQUARE_ALLOW_PRODUCTION=1` set, open the site as a real signed-in customer account (a test account
   is fine) and go through one real payment flow end to end — e.g., grant yourself a $1–$5 test charge via
   Admin ("New Charge" -> a small amount -> "Request Payment") and pay it with your OWN real card.
2. Confirm in **My Account > Payments** that the payment shows as **Paid**, with the correct amount and a
   receipt.
3. Confirm in the **Square Dashboard** (Transactions) that the same payment appears there with a matching
   amount.
4. Confirm in **Admin > [that customer] > Payments** that the same payment appears with the correct method,
   amount, and status.

## 7. Production refund test

1. From Admin, refund the small test payment from step 6 (full refund).
2. Confirm the refund appears in the Square Dashboard.
3. Confirm **My Account > Payments** now shows the payment as refunded and the balance is correct again.
4. If you tested a partial refund, confirm the remaining balance/paid amount is arithmetically correct.

## 8. Webhook delivery verification

1. In the Square Developer Dashboard -> Webhooks, use Square's own "Send Test Notification" (if available
   for your webhook type) or trigger a real event (the test payment above) and check the **Webhook event
   log** in the Dashboard — it should show a `200` response from this app.
2. If Square shows a signature-verification failure or a non-200 response, double check `SQUARE_WEBHOOK_URL`
   matches EXACTLY what's registered (protocol, host, path, no trailing slash) — the signature check depends
   on this string matching precisely.

## 9. Logging verification

1. Check the production application logs after the test transaction above. You should see log lines from
   the `og_payments` logger (payment created/completed) with **no card numbers, no CVV, and no full Square
   access token** ever appearing in them — only amounts, statuses, and Square's own payment/refund IDs.
2. If anything sensitive appears in logs, stop and fix the logging call before continuing — this should not
   happen given how the code is written, but is worth confirming once against a real transaction.

## 10. Academy course pricing

Before advertising a course as purchasable for real money:

1. In Admin -> Courses -> [course] -> Price, double-check the price is correct (it's stored once, in USD, as
   whole dollars/cents — verify the exact number before publishing).
2. Do one real, small-dollar end-to-end purchase test per priced course (or at least one representative
   course) following steps 6 above, confirming the course actually unlocks in My Courses afterward.

## 11. Go live

Once every step above has been verified:

1. Make sure `SQUARE_ENVIRONMENT=production`, `SQUARE_ALLOW_PRODUCTION=1`, and all four other `SQUARE_*`
   production values are set on the real production server (not just a staging box).
2. Restart the application one final time.
3. The Sandbox banner ("Sandbox / Test Mode — no real charge will occur") on the customer pay page will stop
   appearing automatically once `SQUARE_ENVIRONMENT` is `production` — if you still see it, the environment
   variable did not take effect; do not tell customers to pay until it's gone.

## If something goes wrong after going live

- **A payment succeeded in Square but doesn't show as paid in OG:** use the "Check Square" button on that
  pending payment in Admin (Customer -> Payments) — this asks Square directly and reconciles safely, without
  ever guessing.
- **You need to roll back to Sandbox temporarily:** set `SQUARE_ENVIRONMENT=sandbox` (and you can leave
  `SQUARE_ALLOW_PRODUCTION` set, it's a no-op outside production mode) and restart. No customer payment data
  is lost — it's a routing switch, not a data migration.
