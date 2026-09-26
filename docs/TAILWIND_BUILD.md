# Tailwind CSS build (2026-09-26)

The site used to load `https://cdn.tailwindcss.com?plugins=typography` (the Tailwind "Play CDN")
at runtime on every public/admin/account page. That CDN is explicitly documented by Tailwind as
**not for production use** — it JIT-compiles utility classes in the visitor's own browser, is
render-blocking, and makes the site's appearance depend on a third-party CDN's uptime on every
request. It is now replaced with a normal compiled, purged CSS file checked into the repo:
`app/static/css/tailwind.css`.

## Why the standalone CLI, not npm

This project has no Node/npm tooling anywhere (dev machine or the staging VPS), and deliberately
doesn't want one just for this. Tailwind publishes a **standalone CLI** — a single self-contained
executable with no Node dependency — that bundles the first-party plugins (including
`@tailwindcss/typography`, which the old CDN used via `?plugins=typography`) directly into the
binary. That's what this build uses. It is **not** committed to the repo (it's a 40MB+ binary per
platform) — download it fresh when you need to rebuild.

## Files

- `tailwind.config.js` (repo root) — the design tokens (colors, radii, shadows, font), copied
  verbatim from the old Play-CDN inline config. **This is the one place to change a token.**
  Also holds the `content` scan paths and an explicit `safelist` (see below).
- `app/static/css/tailwind_input.css` — the 3-line Tailwind source (`@tailwind base/components/
  utilities`). You will not normally need to touch this.
- `app/static/css/tailwind.css` — the **compiled, minified output**. This is what
  `app/templates/partials/tailwind_head.html` and `app/templates/admin/forms/builder.html` link
  to. Committed to git like any other static asset; rebuild and re-commit it whenever a template
  uses a Tailwind class that isn't already covered.

## Rebuilding

1. Download the standalone CLI for your platform from the
   [Tailwind CSS releases page](https://github.com/tailwindlabs/tailwindcss/releases) — this repo
   was built against **v3.4.17** (pin the same version to avoid an unreviewed Tailwind upgrade):
   - Windows: `tailwindcss-windows-x64.exe`
   - Linux (the staging/production VPS): `tailwindcss-linux-x64`
   - macOS: `tailwindcss-macos-x64` or `-arm64`

   Make it executable if needed (`chmod +x tailwindcss-linux-x64`).

2. From the repo root, run:

   ```bash
   ./tailwindcss-linux-x64 -i ./app/static/css/tailwind_input.css -o ./app/static/css/tailwind.css --config ./tailwind.config.js --minify
   ```

   (swap the binary name for your platform). This is a one-shot build — there is no watch/dev
   server step in this project's deploy process; run it, review the diff, commit the result.

3. Commit the updated `app/static/css/tailwind.css` alongside whatever template change prompted
   the rebuild, in the same commit.

## The safelist — read this before adding a new admin "chip" color

Three admin templates (`app/templates/admin/ds260_prep.html`, `itin_case.html`, `w7_prep.html`)
build a Tailwind class name at **render time** from a Jinja variable:
`bg-{{ tone }}-100 text-{{ tone }}-700`. Tailwind's content scanner only ever sees the raw
template *text* — it cannot see `tone`'s actual runtime value, so it can never discover
`bg-emerald-100` etc. as a real class unless that exact string appears literally somewhere in a
scanned file. `tailwind.config.js`'s `safelist` array hardcodes the compound classes for every
`tone` value these three files are actually called with (`slate`, `red`, `amber`, `emerald` —
verified by grepping every call site). **If you ever add a new tone color at a call site, add its
two classes to the safelist and rebuild** — otherwise that chip will silently render unstyled
(no background, no colored text) with no error anywhere.

Every other place in the codebase that looks similar (`id="req-{{ r.id }}"`,
`id="q-{{ q.key }}"`, `class="og-ratio-{{ ratio }}"`, etc.) is either a plain HTML `id`/`data-*`
attribute (not a Tailwind class at all) or a hand-written class from `app/static/css/custom.css`
(a separate, already-static stylesheet Tailwind never touches) — audited during this migration,
nothing else needed a safelist entry.

## What was NOT changed

- `app/static/css/custom.css` (hand-written component CSS, safe-area, image-slot crops) — loaded
  separately, untouched.
- The Sortable.js CDN script in `builder.html` — an unrelated drag-and-drop library, not Tailwind.
- Google Fonts (`fonts.googleapis.com`) — unrelated to this change.
