# Branding assets (2026-09-26)

## The audit

`SiteSettings.logo_filename` (Admin → Settings → Branding → "Primary Website Logo") only ever
controlled things that called the `logo_url()` Jinja global: the public header/footer/mobile nav,
the customer My Account header, the Smart Intake header, the Open Graph image, and the
Organization/BlogPosting JSON-LD `image`/`logo` fields. Everything else was either hardcoded to
the same static file (`app/static/img/logo.png`) or didn't exist at all:

| Asset | Before | Controlled by `logo_filename`? |
|---|---|---|
| Admin dashboard sidebar/header | Hardcoded (`admin/base_admin.html`, 2 places) | No |
| Admin login page | Hardcoded (`admin/login.html`) | No |
| Favicon — every page type (public/admin/intake, via `partials/tailwind_head.html`) | Hardcoded, full-size PNG | No |
| Forms Builder page's own favicon (separate `<head>`) | Hardcoded | No |
| Transactional email header | No image at all — plain text | N/A |
| PWA manifest / apple-touch-icon | Does not exist anywhere in this app | N/A |

## What changed

`app/models/settings.py` gained 4 nullable `MediaAsset` references, purely additive (migration
`561354a2ee0c`), `logo_filename` untouched:

- `admin_logo_media_id` — Admin dashboard + Admin login.
- `favicon_media_id` — the browser-tab icon, everywhere.
- `email_logo_media_id` — transactional email header (new capability; emails had no image before).
- `social_logo_media_id` — Open Graph image + Organization/BlogPosting JSON-LD.

`app/branding.py` is the one place each resolves, every one falling back to the **primary logo**
(admin/email/social) or the **static default** (favicon) when unset — so leaving a field blank is
visually identical to before this change. Exposed as Jinja globals (`admin_logo_url()`,
`favicon_url()`, `social_logo_url()`) the same way `logo_url()` already was; `email_logo_abs_url()`
is called from Python (`app/email_render.py`) since it needs the caller's already-resolved
`APP_PUBLIC_URL`, never a request-relative URL — an email is read outside any request.

## Admin UI

Settings → Branding now has 5 labeled slots: the existing Primary Website Logo upload (unchanged),
plus 4 new ones using the same reusable Media Library picker already built for Home/Services hero
images (`admin/_media_slot.html` + `admin/_media_modal.html`, included once in `base_admin.html`) —
search the existing library, upload a new file inline, or remove, with no separate upload
mechanism to maintain. Each slot's caption says exactly what it controls and what it falls back to.

## Not changed / out of scope

- Favicon upload stays PNG (matches what the Media Library already validates via Pillow). ICO/SVG
  would require extending that upload-validation pipeline — separate task if ever needed.
- No PWA manifest/apple-touch-icons were added — none existed before, and none were requested
  beyond auditing whether they exist (they don't).
- Nothing about DNS, Nginx, SSL, `robots.txt`, sitemap, indexing (`SiteSettings.
  block_search_indexing` / `should_block_search_indexing()`), `APP_PUBLIC_URL`, Square, or SMTP
  configuration was touched.
