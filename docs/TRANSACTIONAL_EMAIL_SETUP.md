# Transactional Email Setup — steps Marcos must perform

**Status: NOT activated.** `MAIL_ENABLED` is unset (off) everywhere today, so no real email has ever been
sent by this app. This document is the checklist for turning on real Titan SMTP delivery, plus a reference
for how the system works and how to extend it.

No secret values are written anywhere in this document, in `CLAUDE.md`, or in git history — every
credential lives only in environment variables (`.env` locally, your host's secret manager in production),
already excluded from source control (`.gitignore`).

---

## 1. What you need from Titan / Bluehost

You already have the mailbox `info@ogmultiservicesllc.com` on Titan (Bluehost Professional Email Plus),
with SPF/DKIM/DMARC configured and third-party access enabled. You need:

1. The mailbox password for `info@ogmultiservicesllc.com` (or an app-specific password if Titan offers
   one — prefer that if available, so the main mailbox password stays out of server config).
2. Confirmation that SMTP access is enabled for this mailbox (you already confirmed this).

Titan's standard SMTP settings (already the defaults in `config.py`):

| Setting | Value |
|---|---|
| Host | `smtp.titan.email` |
| Port | `465` |
| Encryption | Implicit TLS (SSL) |
| Username | `info@ogmultiservicesllc.com` |

## 2. Environment variables

Set these in `.env` locally (or your host's environment in production — never commit real values):

```
MAIL_ENABLED=1
SMTP_HOST=smtp.titan.email
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_USERNAME=info@ogmultiservicesllc.com
SMTP_PASSWORD=<the real mailbox password — never commit this>
MAIL_FROM_EMAIL=info@ogmultiservicesllc.com
MAIL_FROM_NAME=OG Multiservices LLC
MAIL_REPLY_TO=info@ogmultiservicesllc.com
APP_PUBLIC_URL=https://ogmultiservicesllc.com
```

- **`MAIL_ENABLED`** is the master switch (item 15). It defaults to off. Nothing is ever sent — not a
  verification code, not a receipt — unless this is explicitly `1`. This is deliberate, belt-and-suspenders
  dev safety, the same pattern as `SQUARE_ALLOW_PRODUCTION` for payments.
- **`SMTP_PASSWORD`** is a secret. Never log it, never put it in a URL, never return it to the browser, never
  store it in the database. `config.py` reads it from the environment only.
- **`APP_PUBLIC_URL`** is the origin used to build every link inside an email (verification, password
  reset, "View Receipt", etc.) — see `app/email_render.py:abs_url`. In production this MUST be your real
  HTTPS domain (`https://ogmultiservicesllc.com`, no trailing slash) — never `localhost`.
- **`MAIL_DEV_REDIRECT_TO`** (optional): outside production, if set, every outgoing email's actual delivery
  address is redirected here instead of the real customer, while the admin-visible `EmailLog` still shows
  the real intended recipient. Use this if you want to test with `MAIL_ENABLED=1` locally without any risk
  of a real customer receiving a test message.

`config.py`'s `validate_for_production()` refuses to start the app if `APP_ENV=production` and
`MAIL_ENABLED=1` but `SMTP_USERNAME`/`SMTP_PASSWORD` are missing, or `APP_PUBLIC_URL` still looks like
localhost — production fails safely rather than silently sending nothing or sending through the wrong
place.

## 3. Development safety (already active, nothing to do)

- `MAIL_ENABLED` defaults off. Every code path that would send an email still runs (an `EmailLog` row is
  still created, so you can see what *would* have gone out), but the actual SMTP call is skipped and the
  row is recorded as `failed` with a clear reason ("Email delivery is disabled in this environment").
- Automated tests never set `MAIL_ENABLED`, so they never risk a real send.
- If you ever want to test real delivery locally without risking a real customer email, set
  `MAIL_DEV_REDIRECT_TO=your-own-email@example.com` alongside `MAIL_ENABLED=1` — every email will actually
  arrive in YOUR inbox regardless of who it was "sent to."

## 4. First Titan SMTP test — exact steps

1. Set the four required variables above in `.env` (`MAIL_ENABLED=1`, `SMTP_USERNAME`, `SMTP_PASSWORD`,
   and leave `APP_PUBLIC_URL` as `http://localhost:5001` for a local test — it only affects link URLs, not
   whether the send itself works).
2. Restart the app so the new `.env` values load.
3. Sign in to Admin → System → **Test Email**.
4. Enter your own email address and click **Send Test Email**.
5. You should receive an email titled **"OG TEST EMAIL"** within a few seconds, and the page should show
   **Status: Sent**.
6. If it fails, the page shows the exact SMTP error (e.g. authentication failure, connection timeout) —
   this is the same failure text stored on the `EmailLog` row, and the same mechanism every other
   transactional email uses, so a successful test here means the whole system is wired correctly.
7. Turn `MAIL_ENABLED` back to `0` (or remove it) if you're not ready for real customer emails yet — the
   rest of the site works identically either way; only actual delivery is gated.

## 5. Production activation

When ready to go live:

1. Set the same variables in your production host's environment (never a committed file).
2. `APP_PUBLIC_URL` must be the real `https://` domain.
3. Restart the app.
4. Repeat the Admin Test Email step against your production instance before relying on it for real
   customers.
5. Register a real customer account and confirm the verification-code email actually arrives, the code
   works, and the account activates — the single most important end-to-end check.

## 6. How templates are organized (for adding a NEW transactional email later)

- `app/email_render.py` — the shared `EmailContent` dataclass and `render_email()` (renders the ONE shared
  layout, `app/templates/emails/base.html`, to both HTML and a plain-text fallback). `mask_email()` and
  `abs_url()` (production-origin-aware link builder) live here too.
- `app/email_templates.py` — the catalog. Two shapes:
  - **DIRECT templates** (`email_verification`, `password_reset`, `email_changed`) carry a secret or a
    moment-in-time value that must never be persisted — their `EmailContent` is built once by the caller
    and passed straight to `send_transactional_email(..., content=...)`. Not retryable by design.
  - **REGISTRY templates** (everything else — `TEMPLATES` dict) are looked up by `template_key` and
    rebuilt from a small `ref` dict of safe reference ids (e.g. `{"payment_id": 5}`) — never rendered
    content, never extra PII. This is what makes Admin's Retry button safe and generic: it just re-calls
    the same builder with the same `ref` against CURRENT data.
- `app/email_service.py` — `send_transactional_email(...)` is the one function every business event calls.
  It never raises (a failed email can never break the customer transaction that triggered it), it dedupes
  via an optional `dedupe_key` (prevents two code paths — e.g. a webhook and a synchronous confirm — from
  sending the same email twice), and it persists an `EmailLog` row for every attempt.
- `app/mailer.py` — the actual SMTP transport (stdlib `smtplib`, no new dependency). Knows nothing about
  templates or logging.

**To add a new transactional email:**

1. Add EN/ES copy + a `build_xxx(lang, ref)` function to `app/email_templates.py`, returning an
   `EmailContent`. Register it in the `TEMPLATES` dict under a new `template_key`.
2. Call `send_transactional_email(student, "your_new_key", lang, ref={...}, related_type=..., related_id=...,
   dedupe_key=...)` from the business-logic call site (wrapped in try/except, matching every existing call
   site — see `app/payments.py:_notify` for the pattern). Never call SMTP directly from a route.
3. That's it — Admin visibility (list, per-customer tab, retry) and the dev-safety gate all work
   automatically because they operate on `EmailLog`/`TEMPLATES` generically.

## 7. How to disable sending safely

Set `MAIL_ENABLED=0` (or remove the variable) and restart. Every code path keeps running exactly as
before — `EmailLog` rows are still created for audit, just recorded as `failed` with a clear reason instead
of attempting SMTP. Nothing else in the site depends on mail actually being delivered (no code path blocks
on send success).

## 8. Verification security (documented limits — item 5)

- 6-digit numeric code, generated via `secrets.randbelow` (cryptographically secure), hashed with the same
  slow hash used for passwords (`werkzeug.security.generate_password_hash`) — never stored in plaintext.
- Expires after **10 minutes**.
- Maximum **5 attempts** per code; a 6th wrong guess invalidates the code (must request a new one).
- Resend cooldown: **60 seconds** between resends.
- Resend cap: **5 per hour** per account.
- Verify-attempt rate limit: **10 attempts per 15 minutes** per account (defense in depth beyond the
  per-code attempt counter).
- Issuing a new code always invalidates the previous one.
- Password reset tokens: `secrets.token_urlsafe(32)` (256 bits of entropy), SHA-256 hashed for lookup,
  expire after **30 minutes**, single-use, and requesting a new one invalidates any outstanding token.
- The forgot-password flow never reveals whether an email belongs to an account (identical response either
  way) and only ever sends to an account whose email is already verified.

## 9. Troubleshooting

- **"MAIL_ENABLED is not set to 1"** on every `EmailLog` row — this is expected in development; it means
  the safety switch is correctly off, not a bug.
- **Authentication failed** — double-check `SMTP_USERNAME`/`SMTP_PASSWORD`; Titan mailbox passwords are
  case-sensitive and may need to be regenerated in the Titan/Bluehost control panel if unsure.
- **Connection timeout** — check port 465 isn't blocked by your host's outbound firewall (common on some
  shared hosts — confirm with Bluehost/your VPS provider that outbound SMTP on 465 is allowed).
- **A customer says they never got a code** — check Admin → System → Emails (or the customer's own profile
  → Emails tab) for the `email_verification` row; the failure reason (if any) is shown there, and you can
  Retry a failed one directly (except verification codes/reset links — those must be freshly requested by
  the customer, since a stale code/link is never safely resendable).
- **Emails go to spam** — SPF/DKIM/DMARC are already configured per your confirmation; if delivery
  issues arise later, check Titan's own sending reputation dashboard, not this app (nothing here affects
  domain reputation).
