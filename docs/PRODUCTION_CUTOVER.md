# Production cutover — audit findings and launch-day runbook (2026-09-26)

Read-only audit performed against the live VPS (`og-staging`, IP `2.25.242.113`). No DNS, Nginx,
database, or `.env` changes were made while writing this document — see `deploy/
nginx_production.conf.example` for the one inert, unactivated file this task added.

## 0. The most important thing to understand first

**"Staging" and the eventual production site are already the same running application and the
same database.** `APP_ENV=production` is already set on this host, the database is already named
`ogwebsite_prod`, and `deploy/README.md` (written earlier in this project) already describes this
as a "promote in place" plan, not a separate environment to be built from scratch. Confirmed live:
the 250 `Student` rows here are real (imported Wix customers + real signups) — a spot check found
**zero** rows with the `@example.invalid` pattern this session's own automated test suites always
use, and only one `AdminUser` (`info@ogmultiservicesllc.com`, the real admin). None of this
session's testing touched this database — every suite ran against a throwaway local SQLite copy.

This changes the shape of "cutover" from "stand up a new environment" to "point the real domain at
the environment that already exists, and make sure the one thing that's still shared (the
search-indexing setting) gets separated first."

## 1. Current Nginx / domain state

- One Nginx site, `/etc/nginx/sites-available/ogwebsite` (symlinked into `sites-enabled/`):
  `server_name staging.ogmultiservicesllc.com;` only. **No production-domain config exists yet.**
- Proxies to `http://127.0.0.1:8000` (Gunicorn), `client_max_body_size 50M`, standard
  `X-Real-IP`/`X-Forwarded-For`/`X-Forwarded-Proto` headers, 60s connect/send/read timeouts.
- SSL via Certbot (Let's Encrypt), auto-renewal already running as a system timer — the same
  mechanism will cover the new certificate once issued.
- `/etc/nginx/sites-available/default` exists but is **not enabled** — Debian's stock placeholder,
  harmless, not part of this app's routing.
- DNS today (confirmed live): `staging.ogmultiservicesllc.com` → `2.25.242.113` (this VPS).
  `ogmultiservicesllc.com` / `www.ogmultiservicesllc.com` → `185.230.63.186/.107/.171` — **Wix's
  IPs, unchanged.** Nameservers are `ns1/ns2.bluehost.com`. DNS has not been touched.
- One systemd service, `ogwebsite.service` — `EnvironmentFile=/var/www/ogmultiservices/.env`,
  Gunicorn (3 workers, 2 threads, gthread) bound to `127.0.0.1:8000`, `Requires=postgresql.service`
  (local Postgres on the same VPS). One process serves whatever hostname reaches it today.

## 2. Proposed production Nginx configuration

Prepared, **not installed**: [`deploy/nginx_production.conf.example`](../deploy/nginx_production.conf.example).
Two plain HTTP server blocks (canonical `www.ogmultiservicesllc.com` proxying to the same
`127.0.0.1:8000`, `ogmultiservicesllc.com` apex 301-redirecting to it) — identical body-size/
proxy/timeout settings to the existing staging block, on purpose, since it's the same backend. No
`ssl_certificate` lines yet (see §3 — those don't exist and Certbot writes them in, the same way it
did for staging's block).

## 3. SSL strategy

**HTTP-01 cannot complete yet** — Let's Encrypt would connect to whatever IP the domain currently
resolves to (Wix's), not this VPS, so a certificate request today would simply fail. This is not a
risk to run blind; it just won't work until DNS points here.

**DNS-01 pre-provisioning is technically possible** (works over `certbot certonly --manual
--preferred-challenges dns` regardless of what the A record currently points to — it only checks a
`_acme-challenge` TXT record) but Bluehost has no first-party Certbot DNS plugin, so it would mean
manually adding a TXT record in the Bluehost panel, waiting for propagation, then continuing —
usable, but a manual step that would need repeating (or a cPanel API check, if this Bluehost plan
exposes one — not confirmed) for renewal automation later.

**Recommended: HTTP-01, right after DNS cutover.** Cheapest, matches exactly how the existing
staging cert was obtained (fully automated `certbot --nginx`, auto-renews forever afterward), and
completes in well under a minute once DNS has propagated — there's no meaningful reason to take on
DNS-01's manual TXT-record step for a small-business launch. The launch-day runbook (§9) sequences
this so the HTTP-only gap is minutes, not hours.

## 4. `APP_PUBLIC_URL` / domain-dependent settings audit

- **Canonical tags, hreflang, sitemap URLs, JSON-LD `url` fields**: all built from
  `request.url_root` / `url_for(..., _external=True)` at request time — i.e. from the actual
  `Host` header Nginx forwards. **Nothing to change here**; these become correct for
  `www.ogmultiservicesllc.com` automatically the moment traffic actually arrives on that hostname.
  Confirmed no hardcoded `staging.ogmultiservicesllc.com` string exists anywhere in the codebase.
- **Transactional email links** (`app/email_render.py`, `app/email_service.py`) and the **Square
  webhook URL** deliberately do NOT use the request's host — they use the explicit
  `APP_PUBLIC_URL` / `SQUARE_WEBHOOK_URL` config values, by design (an email must link to the real
  site regardless of which internal process rendered it). **These two `.env` values must change**
  at cutover: `APP_PUBLIC_URL` from the staging URL to `https://www.ogmultiservicesllc.com`, and
  (only when Square production is separately activated per `docs/SQUARE_PRODUCTION_ACTIVATION.md`
  — not part of this task) `SQUARE_WEBHOOK_URL` to the production equivalent.
  Low current risk either way: `MAIL_ENABLED` and `SQUARE_ALLOW_PRODUCTION` are both off today, so
  neither is actually sending/charging anything yet regardless of the URL value.
- **Account activation/reset links** go through the same `APP_PUBLIC_URL`-based builder as
  transactional email — covered by the same fix.

## 5. Environment strategy

One `.env`, read by systemd's `EnvironmentFile=`. Given §0 (this is a promote-in-place, not a
parallel build), the pragmatic, lowest-risk approach is to **keep one `.env`** and change exactly
the handful of domain-dependent values at cutover (`APP_PUBLIC_URL`; `SQUARE_WEBHOOK_URL` only if/
when Square production is activated) rather than introducing a second parallel `.env`/systemd
service/Postgres database — that would be a materially bigger change than this task's scope, and
would face the real question of which database is authoritative going forward (this one already
has 250 real customers). No secret values are changed by anything in this document.

## 6. Database / media strategy

**Reuse the current PostgreSQL database (`ogwebsite_prod`) and the current media directory
(`/var/lib/ogmultiservices/media`, already outside the code checkout per `docs/
PRODUCTION_MEDIA_STORAGE.md`).** This is not a fallback choice — it's the only choice that doesn't
throw away 250 real customer records and their real uploaded documents. No clone/drop/migrate was
performed or is recommended; nothing changes here at cutover except which hostname reaches the
same data. As noted in §0, no cleanup pass is needed first — the spot check found no test-data
contamination.

## 7. Search indexing separation — CUTOVER BLOCKER

**Confirmed blocker, exactly as suspected.** `SiteSettings` is an explicit singleton table (`"""
Singleton row (id=1) holding sitewide settings."""`, `app/models/settings.py`) — one
`block_search_indexing` boolean for the entire application. Since staging and the future
production domain are the same process and the same database (§0), simply adding the production
Nginx block today would make both hostnames share that one flag: turning it off to let production
be indexed would also unblock staging (and vice versa), and staging currently *is* production's
data, so "staging" would just become a duplicate-content mirror of the live site.

**Proposed fix (design only — not implemented in this task, since it's a code change, not a config
file, and this step was scoped to audit/prep):** make the noindex decision host-aware, reusing the
`app/seo.py` mechanism already built for the SEO hygiene pass. A small, explicit
`ALWAYS_NOINDEX_HOSTS` list (or a `STAGING_HOSTNAME` env var compared against `request.host`)
forces `noindex, nofollow` for `staging.ogmultiservicesllc.com` unconditionally, independent of
`SiteSettings.block_search_indexing` — so that flag can then be turned off for real production
indexing while staging stays permanently blocked no matter what the shared setting says. This is a
small, low-risk, well-contained change (one new check alongside the existing `site_settings.
block_search_indexing or request.blueprint == 'account'` condition in `base.html` / `robots_txt()`)
— proposing it here for a future authorized implementation step, not doing it now.

## 8. Cutover blockers — summary

1. **Search-indexing separation (§7)** — must be implemented (small code change, proposed above)
   before both hostnames can safely be live simultaneously with different indexing states.
2. **`APP_PUBLIC_URL`** must be updated in `.env` at cutover (§4) — low risk today since
   `MAIL_ENABLED=0`, but must happen before mail is ever turned on pointing at the new domain.
3. **No SSL certificate exists yet for the production hostnames** — expected; not a blocker, just
   a launch-day step (§3, §9), since HTTP-01 cannot run before DNS points here.
4. **Nothing else found.** No hardcoded staging hostnames, no destructive DB/media decision
   needed, no test-data cleanup needed.

## 9. Exact steps for launch day (in order)

1. Implement and deploy the host-aware indexing fix (§7) to staging first, confirm
   `staging.ogmultiservicesllc.com` still shows `noindex`/`Disallow: /` regardless of the
   `SiteSettings` toggle.
2. Copy `deploy/nginx_production.conf.example` to `/etc/nginx/sites-available/ogmultiservices-prod`,
   symlink into `sites-enabled/`, `sudo nginx -t`, `sudo systemctl reload nginx`. (Harmless before
   DNS changes — these hostnames don't route here yet.)
3. Change DNS at Bluehost: `ogmultiservicesllc.com` and `www.ogmultiservicesllc.com` A/CNAME
   records → `2.25.242.113`. Wait for propagation (check with `nslookup`).
4. Once DNS resolves to this VPS: `sudo certbot --nginx -d ogmultiservicesllc.com -d
   www.ogmultiservicesllc.com` (HTTP-01; completes in under a minute; auto-renewal is automatic,
   same mechanism already running for staging).
5. Update `.env`: `APP_PUBLIC_URL=https://www.ogmultiservicesllc.com`. Restart
   `ogwebsite.service`.
6. In Admin → Settings, turn `block_search_indexing` **off** (this now only affects production,
   per step 1). Confirm live: `curl -I https://www.ogmultiservicesllc.com/robots.txt` shows
   `Allow: /`, and `curl -I https://staging.ogmultiservicesllc.com/robots.txt` still shows
   `Disallow: /`.
7. Smoke test the real domain end to end (home, a service page, login, a blog post) exactly like
   every staging deploy already does.
8. Submit the new sitemap (`https://www.ogmultiservicesllc.com/sitemap.xml`) in Google Search
   Console; leave the legacy Wix property/verification alone until Wix is actually decommissioned.
9. Only after all the above is confirmed working: proceed with any separate, explicitly-authorized
   Wix decommission / Square production activation / mail activation steps — each is its own gated
   task per the existing docs, not part of this cutover.
