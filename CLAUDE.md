# OG Multiservices LLC — Website V2

Rebuild of the OG Multiservices website, built step by step alongside the untouched
production site at `../OG Website`. This file is the brand/content/IA reference —
read it before adding or restyling any page.

## The business

OG Multiservices LLC serves primarily the Hispanic community in the U.S. with tax
prep, ITIN/CAA services, certified translations, notary, immigration document
assistance, and professional education (OG Academy). OG is positioning itself as
**professional services + technology under one modern brand** — not a legacy tax-prep
storefront, not a generic immigration site, not a Wix template.

**Important legal-language rule:** OG provides *document preparation / immigration
assistance*, never *legal representation*. Never imply OG is a law firm or that OG
gives legal advice.

## Contact (real — use everywhere, no placeholders)

- **Office:** 145 Presidential Blvd, STE 2, Paterson, NJ 07522, United States
- **Phone:** 201-685-5444
- **WhatsApp:** 862-332-2321 → link as `https://wa.me/18623322321`
- **Email:** info@ogmultiservicesllc.com
- **Hours:** Mon–Fri 9:00 AM – 5:00 PM. Sat/Sun closed.
- Remote clients served nationwide for services that don't require physical presence.

These live as plain constants in `app/business_info.py` (language-neutral — phone/email/
address don't need translation, only their labels do).

## Services taxonomy

**Primary (get top-nav or Services-hub prominence, SEO-first):**
| Service | Nav treatment |
|---|---|
| A. Income Tax Preparation | combined with B under **Taxes & ITIN** top-nav item |
| B. ITIN / Certified Acceptance Agent (CAA) | combined with A under **Taxes & ITIN** |
| C. Certified Translations | own top-nav item, **Translations** — flagship page |
| D. Notary Public (NJ, some TX) | prominent card inside **Services** hub |
| E. Immigration Document Preparation/Assistance | prominent card inside **Services** hub |
| F. OG Academy | own top-nav item, own sub-brand feel |

**Secondary (discoverable via Services hub, don't compete visually with primary):**
Apostille Assistance · NJ Driver License Assistance (6-Points doc checklist,
foreign-license translation) · Wedding Officiant Services · **Document & Office
Services** (groups: Forms & Administrative Assistance [Medicaid/SNAP/Unemployment/NJ
ANCHOR] + copies/fax/scan/email/passport photos/printing).

## Navigation

Top nav (small, per spec — never dump 15 links in the header):
`Services | Translations | Taxes & ITIN | OG Academy | Resources | About` + primary
CTA button **Get Started**. "Services" is a dropdown/hub revealing Notary, Immigration
Assistance, Apostille, Driver License Assistance, Wedding Officiant, Document & Office
Services. Student/client **Log In** stays present but secondary to Get Started.

## Visual identity

**Concept:** Modern Professional Services + fintech/SaaS aesthetic. Explicitly NOT:
a traditional tax office, a flag-heavy immigration site, a government site, a generic
Wix template, stock handshake photos, red/white/blue overload, walls of text.

**Palette** (Tailwind tokens in `tailwind.config` inside `base.html`):
- `brand` (deep navy) — primary institutional color, headlines, dark surfaces.
- `accent` (controlled brighter blue) — primary CTAs, links, interactive states. Used
  moderately, not everywhere.
- `academy` (warm gold/amber) — OG Academy sub-brand only (course cards, progress,
  certificates) so Academy feels related but distinct, per "second ecosystem" below.
- Neutrals: white / off-white / light gray / slate for everything else. Avoid adding
  more hues.

**Typography:** Inter (already wired). Big, strong headlines; light/secondary body
text; large but elegant buttons; generous whitespace.

**Every page must answer in order:** What is this? Can OG help me? What do I do next?
CTAs are always contextual to the page (Translations → "Upload Document", Taxes →
"Start Tax Service", ITIN → "Start ITIN Application", Notary → "Contact / Visit
Office", Academy → "Explore Courses") — never a generic "Contact Us" everywhere.

**Trust signals** (weave in elegantly, never a badge wall): client reviews, years of
experience, bilingual service, secure & confidential, IRS Certified Acceptance Agent,
certified translations, Paterson NJ office.

## Home page shape

Hero (clear headline + one-sentence subheadline covering taxes/ITIN/translations/
notary/immigration/education) → primary CTA "Get Started" + secondary "Explore
Services" → **Service Finder** ("What can we help you with?" — 6 direct-intent
buttons: file taxes / need an ITIN / translate a document / notarize a document /
immigration assistance / take a course, each routing straight into that flow) →
trust section → OG Academy cross-promo.

## Service landing page pattern (Translations is the reference build)

Hero → what we handle → how it works (numbered steps) → common documents/scenarios →
FAQ → contextual CTA. Reuse the *shape*, not an identical layout, for every primary
service page.

## Mobile-first

Many clients arrive by phone/WhatsApp. Thumb-friendly buttons, short forms, WhatsApp
always reachable (floating button), a discreet mobile bottom bar (**Call | WhatsApp |
Start**) on small screens.

## Bilingual

Full EN/ES via `/en/...` / `/es/...` prefixes (not machine-translated at render time —
every string is authored in both languages in `app/i18n.py`). Language switch keeps the
user on the equivalent page, never bounces to Home — implemented via
`url_for(request.endpoint, lang=other, **view_args)`, no hardcoded path-pair tables
(the old site's biggest routing bug — see the audit).

## OG Academy as a second ecosystem

Visually related (same navy base) but distinguishable (gold/amber accent). User should
feel "OG Multiservices → services" vs "OG Academy → education," not "just another
service card." Academy eventually needs: course catalog, student accounts, My Courses,
progress, interactive lessons, assessments, certificates, certificate verification.

## Build for the future

Don't paint the architecture into a corner. Eventually: Client Portal, Document Upload
Center, translation tracking, tax/ITIN intake, appointments, payments, OG Academy (full
LMS), AI assistance, customer accounts, professional dashboards, OG software products.
Keep blueprints/models decoupled enough that these can be added incrementally (this is
exactly what the audit of the old site flagged as missing — see the audit for the
mistakes not to repeat: no shared auth/CSRF module, no migrations, hardcoded bilingual
path tables, positional-only Visual Editor block IDs).

## Build log

1. **Foundation** — scaffold, bilingual routing, base layout, placeholder pages.
2. **Brand rebuild** — real business info, navy/accent/academy palette, restructured
   nav + Services hub, Service Finder, WhatsApp + mobile bottom bar, Translations and
   Taxes & ITIN flagship pages.
3. **Platform redesign (2026-09)** — one design system, structured CMS, media library and
   smart service intake. Details below; this section supersedes the older notes above
   wherever they conflict (e.g. "hand-built flagship pages", the Service Finder shape and
   the Translations-as-reference pattern).
4. **Smart Service Intake, Phase 1 (2026-09-18)** — production I-90 intake (edition 01/20/25),
   generic intake engine, form versioning, My OG Account portal, admin customer profile,
   activity log. N-400 (Phase 2) and I-130 (Phase 3) are now production intakes.
5. **Person identity + I-485 + I-864 + I-765 + I-751 (2026-09-19)** — real-person layer, I-485, I-864 (Affidavit of Support), I-765 (Employment Authorization) and I-751 (Removal of Conditions, its own case type) production intakes;
   see the sections below.
6. **DS-260 Consular Processing (2026-09-19)** — the Department of State's online immigrant-visa application (CEAC) prepared, never submitted, by OG: own case type, one DS-260 per visa
   applicant Person, source snapshots, CEAC-ready English layer and Admin CEAC Preparation View; see "DS-260 (production" below and `docs/DS-260_source_coverage.md`.
7. **ITIN / W-7 Smart Intake — Tax & ITIN Services (2026-09-20)** — new case type `itin_application`, one W-7 per ITIN applicant Person in one case, passport-first (confirmed by the customer, upload-later never blocks),
   source-driven evidence matrix, physical-original / CAA tracking, Admin ITIN Case view + W-7 Preparation View, IRS package tracking without ever implying approval; see the section below and `docs/W-7_source_coverage.md`.
8. **OG Tax Smart Intake v1 — Tax Year 2025 (2026-09-21)** — dedicated `app/tax/` module (not the Form Builder): own case type `tax_return`, plain-language document-first interview,
   dynamic Document Vault requirements, a data-driven Pricing Engine with a returning-client discount, encrypted refund bank details, versioned terms acceptance, Admin Tax Case view +
   Tax Pricing config; see "Tax Return (production)" below.
9. **My Account redesign (2026-09-22)** — customer-friendly status language layer, unified Action Required aggregation, unified Services/Documents/Messages pages, simplified nav,
   profile photo; see `app/customer_status.py` / `app/account_dashboard.py` below.
10. **NJ Driver License Assistance + Knowledge Test Practice (2026-09-22)** — guided, document-first DL intake (own case type, own pricing/rules engines, MVC location config,
    milestone roadmap) plus a free, account-gated Knowledge Test practice simulator (own original question bank, no OCR/AI); see "NJ Driver License Assistance" and "NJ Knowledge Test
    Practice" below.
11. **My Account visual shell + global reopen/self-edit architecture (2026-09-22)** — premium header + sidebar shell replacing the old horizontal tab bar, Action Required as
    verb-driven task rows, a `CaseRevision` change-tracking layer extending Admin Reopen to the Tax and NJ Driver License modules, and NJ Driver License customer self-edit
    ("Edit My Information"); see "My Account visual shell" and "Reopen / change-tracking architecture" below.
12. **Files from OG as a first-class digital file vault + Academy Grant Course Access + public-site return navigation (2026-09-22, same day)** — "Files from OG" split out of My
    Documents into its own sidebar item and page with categories/search/tax-year grouping; `Enrollment` gained a structured access-source model so Admin can grant course access to a
    student migrating from the old Wix site without a fake purchase; the My Account header logo and a sidebar/drawer link now return the customer to the public website without
    ending their session. See "Files from OG (digital file vault)" and "OG Academy — Admin Grant Course Access" below.
13. **OG Payments — Square integration (2026-09-22, SANDBOX ONLY)** — a reusable `Charge`/`PaymentRequest`/`Payment`/`Refund` ledger (integer cents, never a float) that every service/
    course payment flows through regardless of HOW the customer paid (Square online, or Zelle/cash/check/other recorded by Admin); Square is the processor, never the only payment
    record. Covers all four business models (fixed-price Academy courses, OG-confirms-price services, estimate-to-final-price DL/Tax, and balance/partial-payment immigration cases),
    idempotent Square payments, webhook reconciliation, refunds, and a My Account "Payments" page. Live production Square is explicitly NOT activated — see "OG Payments (Square,
    sandbox)" below and `docs/SQUARE_PRODUCTION_ACTIVATION.md` for exactly what Marcos must still do to go live.
14. **Transactional Email + mandatory email verification (2026-09-22, MAIL_ENABLED off / not activated)** — a reusable `send_transactional_email()` seam (`app/email_service.py`) every
    business event calls through, backed by SMTP over Titan/Bluehost (`app/mailer.py`, stdlib only, no new dependency); a 6-digit-code email verification system now REQUIRED for every
    customer account (new registrations only — existing accounts were grandfathered verified at migration time, never fabricated as verified-at-registration); a brand-new password
    reset flow (none existed before); a verified email-change flow reused by both "fix a typo before first verifying" and Profile & Settings; and 11 connected transactional events
    across Payments/Files-from-OG/Academy/Case-documents/Tax/Driver-License/generic-intakes. See "Transactional Email system" below and `docs/TRANSACTIONAL_EMAIL_SETUP.md` for exactly
    what Marcos must still do to turn on real delivery.

## Platform architecture (current)

**Design system.** Tokens live in the Tailwind config (`partials/tailwind_head.html`):
`brand` navy, `accent` OG cyan, `mist` (very light cyan surfaces), `fog` (neutral grey),
`wa` (WhatsApp green — WhatsApp actions only), `academy` (gold — Academy only). Components
are Jinja macros in `templates/partials/ui.html` (`btn`, `pill`, `media`, `section_header`,
`service_card`, `page_hero`, `info_panel`, `cta_block`, `faq_list`, `steps_row`, `chips`,
`progress`, `save_status`, `empty_state`); icons in `partials/icons.html` (one stroke family).
Base CSS (safe-area, image-slot crops, forms) in `static/css/custom.css`. Build public pages
from these — never with page-specific markup. The mobile bottom bar is Call | WhatsApp | Start.

**Content is data, not templates.** Service categories and services are records
(`ServiceCategory`, `Service`, `ServiceContentItem` in `models/site_content.py`), edited in
Admin -> Services. Two shared templates render everything: `public/service_category.html`
and `public/service_detail.html`. URLs are unchanged from the original site (SEO); a
category owns its endpoint. Home and the Services hub are edited in Admin -> Website
(`app/site_content.py` registry over the `PageBlock` key/value table; empty field = built-in
i18n default). `app/service_pages.py`, `app/service_areas.py` and
`app/legacy_block_defaults.py` are now only the SEED SOURCE for the first-run migration in
`app/seed_content.py` (runs once, only when there are no categories) — do not edit content
there. "Flagship Page Text" no longer exists as an admin concept.

**Media Library** (`app/media_library.py`, Admin -> Website -> Media Library). Every public
image is a `MediaAsset`; pages pick from the library through controlled slots (hero, mobile
hero, card, overview, social) with a focal position. Missing images fall back to a polished
placeholder. Public route `/media/<id>/<name>?w=480|960|1600` serves cached WebP downscales.
Uploads are verified with Pillow, not just extension.

**Navigation** (`NavItem`, Admin -> Website -> Navigation): built-in items can be hidden,
renamed, reordered but not deleted; custom items link a Custom Page or a URL. The Services
dropdown is the published categories with "Show in menu".

**Custom Pages** = the old `Page` model (Privacy Policy, Terms, campaigns). Structured
services never go through it.

**Smart intake = the Forms engine.** `Form.form_type` is `inquiry` (public, no account) or
`service_intake` (signed-in customer, autosave, resumable). A `Service` has `requires_intake`,
`form_id`, `requires_account`; "Get Started" resolves in one place (`service_public.service_cta`).
Flow: `/services/<cat>/<svc>/start` -> sign in if needed (returns to the same URL, language
kept) -> `intake.start_or_resume` (one open draft per customer+form+service) -> `/f/<slug>?t=`.
Ownership is always checked against the session student (`intake.owned_submission`); never
trust ids in URLs. Autosave is `POST /f/<slug>/autosave` (lenient, rate-limited); conditional
logic is evaluated server-side (authoritative, same-page rules included) and mirrored live in
the browser. Answers hidden by a rule are purged on save. Customers see drafts under
Account -> My applications.

**Pilot: I-90 (production).** `seed_i90.ensure_i90_intake()` builds "I-90 Client Intake"
(slug `i-90-client-intake`, Form ID 2, v1, published, linked to Green Card Renewal) from the
supplied USCIS Form I-90 **edition 01/20/25**. ~29 micro-step pages, ~21 on a typical path.
Every field carries `source_ref` (Part/Item, admin-only); questions that are OG UX helpers, not
USCIS items, say "OG helper". Signatures and Part 7 (preparer) are NOT collected: OG is the preparer and guides the
signature according to how the case is filed (never state an absolute "sign in ink" rule). Nothing says or implies the form is filed with USCIS ("Submit to OG").
It is rebuilt only if it has no submissions. Services planned but unbuilt get `Service.intake_label`
(`seed_i90.PREPARED_INTAKES`) with no form, so `Service.intake_state` is `not_configured`, admin shows
"NOT YET CONFIGURED", and Get Started never routes to them.

**Intake engine (generic, no per-service code).** `intake_engine.py` derives everything from
answers: `path_pages` (active path), `progress_for` (step/total/percent on that path),
`review_sections`, `validate_value` (email/phone/number/date+`date_rule`/length/`pattern`),
`build_snapshot`/`load_snapshot` (frozen bilingual answers at final submit), `status_key`/
`status_label` (Draft/Submitted/In Review/Waiting for Client/Completed/Archived; Draft = not
`is_complete`, stored status `new` = Submitted). `intake.purge_hidden_values` deletes answers
and files for hidden fields AND for pages off the active path. Steps live in
`public/routes.py` (`og_form_view`/`og_form_submit`/`og_form_autosave`/`service_start`) and
`public/intake_routes.py` (review, finalize, instant upload, file remove). `og_form_view`
redirects off-path pages to the next applicable one. Templates: `intake_base.html` (no site
nav/bottom bar), `public/intake_step|intake_review|intake_done.html`, field macros in
`forms/_field_macros.html`, behaviour in `static/js/og_form.js`.

**Versioning.** `Form.version/source_form_name/source_edition/published_at/previous_version_id`;
submissions store `form_version` + `source_edition_snapshot` + `snapshot_json`. Admin "Create
version N+1" clones the form as a draft; publishing it repoints services that used the previous
version, which stays published so drafts already in progress finish on it (`find_draft` matches
by service across versions). Completed applications keep the snapshot they were completed under.

**Intake UX rules (learned from testing).** Never use `position: fixed/sticky` or a transformed
ancestor for the intake action buttons: an animated `transform` on the card turns it into the
containing block of "fixed" children and the bar collapsed onto the last answers (the mobile
scroll bug). Actions are ordinary in-flow content; the page scrolls naturally. Field defaults:
`FormField.default_value` may be `@biz:NAME`, resolved from `app/business_info.py` (used for
the interpreter/OG office defaults); they are only starting values (a saved answer, even an
emptied one, wins) and are purged with the branch. Paragraph fields render trusted admin HTML.
The one-time UX pass on the I-90 is `seed_i90_refine.py` (in place, bumps `Form.version`).

**Reopen for customer editing (generic).** `app/reopen.py`: Admin -> application -> "Reopen for
Customer Editing" (dialog with optional message; a separate action, never the status dropdown).
The SAME `FormSubmission` goes `Submitted -> Reopened (is_complete False, status "reopened") ->
Submitted`. `submitted_at`, form version/edition, answers, files, notes and activity are untouched;
each cycle is a `SubmissionRevision` (reopened/resubmitted times + a per-field before/after change
log, sensitive values masked). Customers see "Reopened for Editing" + the OG message + "Continue
Editing" (opens the review, where every section has Edit). Ownership rules are unchanged
(`owned_submission`). Works for any service intake (I-90, N-400, ...).

**Master customer directory.** One identity: `Student` (staff logins are `AdminUser`, never listed).
Admin -> Clients -> Customers (`customers_routes.customers_list`: search name/email/phone, filters,
counts) opens the 360 profile `/admin/customers/<id>` (tabs Overview/Applications/Documents/Courses/
Activity/Notes). `/admin/students` is only an Academy-filtered view of the same accounts;
`/admin/students/<id>` redirects. Admin -> Applications lists every Smart Intake across forms.

**Record / timeline components (reusable, `app/intake_records.py` + `static/js/og_records.js`).** A
`record_list` field stores JSON records; `FormField.config_json` picks the record type (`address`,
`activity`, `trip`, `child`, `other_name`, `offense`) and timeline rules (years, gap/overlap
tolerance). ALL date logic (coverage, gaps, overlaps, duplicates, trip durations/totals) lives in
`analyze()` and is served to the browser by `POST /f/<slug>/records/analyze`, so the builder,
review, completeness check and Admin agree. Gaps/overlaps never block Continue; reversed/missing
dates do. Wording is "please review", never eligibility.

**Completeness check + consistency.** `Form.features_json` enables it ({"completeness_check": true,
"consistency": "n400", "sections": [...]}); `FormPage.group_key` assigns pages to sections.
`intake_completeness.completeness_report` (used by `/f/<slug>/check` and Admin) reports missing
answers, format errors and review prompts; cross-answer checks live in `n400_checks.py`.

**N-400 (production).** `seed_n400.py`, form id 3 `n-400-client-intake`, USCIS edition 01/20/25
(14 pages), 50 steps (~40 typical), linked to Naturalization. Signatures, Part 13 (preparer) and
Parts 15-16 are not collected. The PDF does not include the Instructions, so the builders collect the
last 5 years for every filing basis and say OG confirms the exact period. Yes-answers that need
Part 14 explanations open required follow-ups. `app/n400_data.py` = field-office list transcribed from the PDF.

**I-130 (production).** `seed_i130.py`, form `i-130-client-intake`, USCIS edition 04/01/24 (from the supplied
PDF), 51 pages (~41 on a typical path), linked to `i-130-petition`. Petitioner vs Beneficiary is a reusable
**context** feature: `FormPage.context_key` + `Form.features["contexts"/"context_names"]` render a persistent
chip (`ui.context_chip`), a coloured left edge and grouped review/admin headings (`intake_engine.context_map`);
any two-person intake can reuse it. Branching keys off the language-independent `relationship_type`
(spouse/parent/child/sibling) and `relationship_basis`. Reusable record types added: employment, spouse, parent,
relative, prior_petition, other_relative; `default_from` seeds the address history from the mailing address;
`FormField.help_where_en/es` is the "Where can I find this?" hint; `i130_checks.py` = consistency prompts
(registered in `intake_completeness.CONSISTENCY["i130"]`). `app/i130_data.py` = class-of-admission list from the PDF.
Documents are "OG asks for" only: the USCIS Instructions (which list required evidence) are not in the PDF.
Signatures, Part 8 (preparer), G-28 and USCIS-use boxes are not collected; **Form I-130A is NOT built**
(spouse cases only get an "OG will review" note). Processing route (Part 4 items 61-62) is the customer's
statement with a "Not sure? Save this for OG review" option; OG never decides it.

**I-130A (supplement of the SAME I-130 intake, spouse only).** `seed_i130a.ensure_i130a_supplement()` extends
`i-130-client-intake` in place (Form v2, edition 04/01/24 of I-130A from the supplied PDF): 12 spouse-only steps shown
when `relationship_type == spouse`, in ONE application (no second form, service or application id). The customer sees
"Additional spouse information" in the BENEFICIARY context; "Form I-130A" is only a small secondary label. Steps after
the beneficiary section: address history (Part 1 items 4-7), last address outside the U.S. (8-9), parents (10-23,
NOT collected by the I-130), employment history (Part 2), last job outside the U.S. (Part 3). After the petitioner's own
interpreter steps: spouse language / interpreter (Parts 4-5, Part 5 only when the interpreter differs) and a signature
explanation (no signature collected; Part 6 preparer not collected: OG prepares both). Shared answers are asked ONCE
(name, A-Number, USCIS account, phone/mobile/email, "Anything else?"): `FormField.source_form/source_edition/
source_extra_json` (`FormField.sources()`) let one answer list every official form/Part/Item it maps to; the
snapshot stores `sources` + section `group`. `app/intake_shared.py` = reusable multi-form helpers: name tokens
(`{ben}` in step text, via `g.name_tokens`, set by `set_name_tokens`), canonical sync (current address and current job
exist as I-130 answers AND as the `present` entry of the histories: `sync_after_save` keeps them identical, config in
`Form.features["sync"]`), dynamic candidate blocks (the "we found this in Maria's history" confirmation for the last
foreign address/job, `intake_records.CANDIDATES`), and `supplement_status`/`supplement_map`
(`Form.features["supplements"]`: groups, customer title, `required_field`). New record types: `ben_parent`,
`foreign_address`, `foreign_employment`. Existing spouse drafts adopt the steps (saved positions are remapped by page
identity); already-submitted spouse applications are never edited (their snapshot is frozen): Admin sees a banner and
"I-130A info needed" in the applications list, and uses Reopen for Customer Editing. Not built: PDF/official-form export.

**Case architecture (Customer -> Cases -> People / Applications / Shared data / Vault).** `models/cases.py`,
`app/cases.py` (services), `app/case_documents.py` (vault + requirement engine), `app/case_types.py` (registries).
A **Case** (`OGC-000123`, migration `0fb7ac30f97e`) is the customer's overall matter; an **Application** stays the
existing `FormSubmission` (`OGF-...`) and only gains a nullable `case_id`. Every customer application joins the
customer's open case of its type (I-90 = Green Card Renewal, N-400 = Naturalization, I-130 = Family Petition; other
types such as Adjustment of Status are created by Admin and applications can be moved in: only the grouping changes,
`updated_at` is deliberately preserved). `intake.link_to_case`, `sync_people` (each saved step) and `harvest_facts`
(on submit) are wrapped so a case-layer error never breaks an intake. `backfill_cases()` (idempotent, run at startup)
attached all existing applications without touching a row of them. **People**: `CasePerson` (only the customer has a
`student_id`/login; others get no access) + `ApplicationRole` (what a person is in ONE application: the same person
keeps one record and gains roles, e.g. petitioner in I-130 and sponsor later). **Three data levels**: PERSON facts
(`PersonFact`, explicit allow-list in `FORM_CASE_CONFIG`, with provenance: source application/form/field/Part-Item,
`PersonFactUse` = where used, `PersonFactEvent` = recorded/updated/confirmed/differs, `last_confirmed_at`), CASE data
(people, roles, relationship) and APPLICATION data (everything else stays in the application). A different value
from another application is never applied silently: `needs_review` + a `differs` event; `facts_for_review`,
`confirm_facts`, `update_fact` are the service a future "We already have this - please review" screen calls.
**Vault**: `CaseDocument` (file stored once, random server name, superseded not deleted on replacement) is separate
from `DocumentRequirement` (what OG needs; status needed/requested/uploaded/under_review/accepted/needs_replacement;
person; `RequirementApplication` = applications it serves; `DocumentAttachment` = which document fills it, one document
can fill several requirements). `sync_requirements(case, source_key, desired)` / `ensure_requirement` are the API future
intakes call to add/withdraw requirements from answers (each rule owns a `rule_key`; admin-made requirements are never
touched). Admin: `/admin/client-cases` (endpoints `ocase_*`; the Academy owns `/admin/cases`, `case_*`), tabs Overview/
People/Applications/Documents/Activity/Notes, "+ Request Document", accept / needs-replacement (with customer message),
Customer 360 "Cases" tab. Customer: `/account/cases` (upload, reuse an existing document, remove own pre-review upload,
download). Every document/requirement/case lookup goes THROUGH the customer's own case (`owned_case/owned_document/
owned_requirement`). Case timeline = `ActivityEvent.case_id` + the events of the case's applications. Existing
application uploads stay `SubmissionFile` (unchanged secure routes); the vault is for case-level documents.
I-765 is built too (see its section); the I-485 phase added the customer-facing confirmation UI for shared facts, requirement rules and the case-setup step; the I-864 is built too — see its section).

**I-485 (production, natively on the Case architecture).** `seed_i485.py` + `seed_i485_elig.py` (Part 9), form
`i-485-client-intake`, USCIS edition 09/18/26 (supplied PDF, 24 pages), ~103 steps (~71 on a typical path, most are the 84 short
Part 9 yes/no items in themed screens), linked to Adjustment of Status. Item numbers were read from the PDF layout; every one of
the 189 printed Part/Item entries maps to a field (internal audit: `docs/I-485_source_coverage.md`, regenerate from the seeded
form). NOT collected on purpose: every signature/date, Part 12 (OG is the preparer), Part 13, Part 14 (assembled from the
explanation answers, whose `source_ref` is "Part 14 (explanation for Part 9, Item N)"). Forms I-864 and I-765 are built (below).
"Not sure — OG will review" exists only for Parts 2-3 and Part 4 items 1/5/6 (workflow questions); Part 9 keeps exact yes/no
meaning; every Yes opens a required explanation; no wording ever says inadmissible/qualify/waiver ("OG should review this answer").
The Instructions are not in the PDF, so no document request claims USCIS requires it (`DocumentRequirement.doc_basis`:
source = the form itself says to attach it, workflow = OG request, answer = triggered by an answer, admin).

**I-864 (production, its own application on the Case + Person architecture).** `seed_i864.py`, form `i-864-client-intake`, USCIS edition
08/24/26 (supplied PDF, 12 pages, Parts 1-11), ~54 pages (~34-40 on a typical path), linked to the *Affidavit of Support* service that
`ensure_i864_intake()` creates in the Immigration category if missing (additive; the seeder only runs when the form does not exist). Every
printed Part/Item has an honest status in `docs/I-864_source_coverage.md` (COLLECTED / CONDITIONAL / DERIVED / NOT COLLECTED — SIGNATURE EXECUTION / NOT APPLICABLE). NOT collected: every signature and date of
signature (Parts 8, 9, 10), the G-28 box and every "For USCIS Use Only" box. Part 10 Items 1-5 (preparer = OG) ARE collected as information on a
"Who prepares your affidavit" page whose defaults come from `business_info.PREPARER_*` (`@biz:` defaults, like the interpreter's `INTERPRETER_*`); the interpreter
page (Part 9) appears only when the sponsor says an interpreter was used (never assumed). Contract/certification Spanish is OG's courtesy translation
(labelled on the pages and in `source_note`); English is official. It is a separate Application (never inside the I-485) attachable ONLY to a compatible
case (`FORM_CASE_CONFIG["I-864"]["case_types"]` = adjustment_of_status, family_petition); it is NOT auto-attached: `setup: "sponsor_principal"`
-> `/f/<slug>/setup` (`case_setup.options_i864/apply_i864`, template `intake_setup_i864.html`) where the customer picks the SPONSOR and the
PRINCIPAL IMMIGRANT from the customer's existing real People ("Already in this case" / "Add another person") and the case; Person ids are
re-read as the customer's own, sponsor != principal, a duplicate pair is refused. Roles `sponsor`, `principal_immigrant`, plus
`joint_sponsor` / `substitute_sponsor` from Part 1 (`b_basis` 1d/1e/1f) on the SAME sponsor Person, `sponsored_immigrant`.
*Reuse:* stable/situational facts use `shared_blocks` (`sb_s_*` for the sponsor, `sb_p_*` for the principal; `{sp}`/`{pi}` name tokens);
conflicts use the existing `/conflicts` flow. *Application-only data* (household, income, tax, assets, calculated totals) is NEVER a
Person fact. *Records* (`intake_records.py`): `i864_family`, `i864_household`, `i864_income_person` (each can point at an existing
Person via `person_id`, verified server-side; `i864_views.normalize_records`), `i864_income_source`, `i864_tax_year` (no hard-coded years;
amount/"zero"/"N/A"; concept "total income (adjusted gross income on IRS Form 1040EZ)"), `i864_asset`. *Arithmetic* is `i864_calc.py`
(household size with double-count prevention by Person link or normalized name + non-contradicting DOB, income Item 7/12, tax rows,
asset Items 1-10) written back as hidden calculated answers (`c_hh_*`, `c_inc_*`, `c_ast_*`; `keep` + never-true show rule) by the
`i864_calc` sync rule so Review/Admin/snapshot show them; `i864_checks.py` = consistency prompts ("please review", never a
conclusion). NO poverty-guideline values exist anywhere (the I-864P comparison is OG's review); nothing says income/assets are enough
or that a joint sponsor is/isn't needed. *Documents:* `i864_docs.py` -> vault requirements from the answers with `doc_basis` labels; `sync` computes the requirements of EVERY active I-864 of the case together (so a joint sponsor's
affidavit never withdraws another's), requirements are per (rule, Person), person-less ones are scoped to one affidavit, and `case_documents.find_reusable_document` never gives a person's file to a
person-less requirement.
*Admin:* `i864_views.admin_summary` panel on the application (sponsor + basis, principal, other people with links to Person pages,
household with counted/not counted, income, tax, assets, flags). *Contract:* Part 8 text is shown verbatim (EN) with OG's courtesy
Spanish; `c_read` / `c_cert_ack` are acknowledgments only, never signatures. Tests: scratchpad `e2e_i864a-d` on DB copies (harness
`i864data.py` also resets a dev-seeded I-864 form, like the I-485). Note the running dev server seeds new forms into the real DB on
auto-reload (and the customer may already have started a draft), so a deployed form is upgraded IN PLACE by `seed_i864.ensure_i864_refinements()` (adds the Part 10 page,
courtesy labels; bumps `Form.version`; never touches answers) — do not delete a form that has submissions.

**I-765 (production, its own application on the Case + Person architecture).** `seed_i765.py`, form `i-765-client-intake`, USCIS edition 08/21/25
(supplied PDF, 7 pages, Parts 1-6), ~39 pages (~22-28 on a typical path), linked to a new *Employment Authorization (Form I-765) Preparation* service
(created if missing) AND the existing *Work Permit (EAD) Renewal* service. Every printed Part/Item has an honest status in `docs/I-765_source_coverage.md`.
NOT collected: every signature and date of signature (Part 3 Item 7, Part 4 Item 7, Part 5 Item 8), the G-28 box, every USCIS-use box.
It is NOT an AoS-only form: `FORM_CASE_CONFIG["I-765"]["case_types"]` = `employment_authorization` (new case type, default for a standalone I-765) and
`adjustment_of_status` (only by the customer's explicit choice in the setup step); `allow_repeat_in_case` lets an initial and a renewal I-765 share a
case (only an unfinished draft blocks another). Setup = the generic applicant setup (`case_setup.py`, heading specific to the I-765).
*Reuse through the Person layer* (blocks `sb_identity`, `sb_othernames`, `sb_address`, `sb_ids`, `sb_marital`, `sb_arrival`, `sb_docs`, `sb_contact`): after
"correct" only the details the person's data cannot supply are asked (`<block>_missing` computed by `shared_blocks.prime_blocks` from the block's `ask` list;
field rules never depend on the field's own value). New facts: birth_state, marital_status, arrival_place, current_status, sevis_number, passport_number,
travel_document_number, document_country/expiry, arrival_document_* (from the I-485: passport OR travel document at last arrival). `cases.extract_fact` gained
`compose` / `first_of` mappings; `shared_blocks` gained tuple `only` (values the form has no option for are not offered) and a block `prefill`
(the arrival document prefills passport OR travel document only after the applicant says which it is: `d_kind`). Class of admission = status at last arrival.
*Never guessed:* Part 2 Item 12 (previous I-765) is ALWAYS asked (OG's own I-765s are shown as context only); the eligibility category (Item 27) is stored
exactly as typed in the three printed boxes (`e_cat_a/b/c`) or "Not sure — OG will review" — `i765_calc` only normalizes syntax and derives `c_branch`
(which of Items 28-31 apply: exactly `(c)(3)(C)`, `(c)(26)`, `(c)(8)`, `(c)(35)`, `(c)(36)`); `i765_views.CATEGORY_SUGGESTIONS` is an EMPTY configuration hook.
Arrest/conviction Yes = OG-review flag + "court dispositions" request (no eligibility statement). ABC question (Part 3 Item 6) only asked for El Salvador/Guatemala.
Part 5 Item 7 (preparer statement) is DERIVED from `business_info.PREPARER_STATUS` (never defaulted to attorney/accredited). Part 6 entries are generated
(`i765_calc.additional_entries`, hidden `c_addl`); the customer never gives page/part/item numbers. Documents: `i765_docs.py` (union sync across the case's I-765s;
passport/I-94 requests are shared with an existing I-485 request). Admin panel: `i765_views.admin_summary`. Tests: scratchpad `e2e_i765a-c`, `verify_cov765`.

**I-751 (production, its own application AND its own case type on the Case + Person architecture).** `seed_i751.py` (+ `i751_text.py` verbatim texts and OG's courtesy
Spanish, `i751_calc/views/docs/checks.py`), form `i-751-client-intake`, USCIS edition 04/01/24 (supplied PDF, 11 pages, Parts 1-11), 55 pages (~35 on a typical joint
path), linked to a *Removal of Conditions on Residence (Form I-751)* service (slug `removal-of-conditions`, created if missing). Every printed Part/Item has an honest status
in `docs/I-751_source_coverage.md` (automated check: scratchpad `verify_cov751.py`). NOT collected: every signature and date (Part 7 Item 6, Part 8 Item 6, Part 9 Item 6,
Part 10 Item 8), the attorney/G-28 block and every USCIS-use box; the Part 8 spouse's certification is never collected on the spouse's behalf.
*New case, same people:* `FORM_CASE_CONFIG["I-751"]["case_types"]` = `removal_of_conditions` ONLY (never Adjustment of Status / Family Petition / Naturalization / Renewal;
`IncompatibleCase` both ways). Setup is the generic sponsor/principal-style step driven by `setup_pair` (`case_setup.apply_i864`, template `intake_setup_i864.html`): "whose
conditional residence" + "who is the spouse (or parent's spouse)" from the customer's real People; a new CasePerson links to the SAME `Person`, so Marisol's I-130/I-485/I-765
facts and Luis's I-130 facts are reused across cases and older cases are never touched. A finished petition for the same pair does not block a fresh case
(`completed_elsewhere_ok`); an unfinished one or the same pair in the same case does. Roles: `conditional_resident`, `relevant_individual`, time-aware `spouse` /
`former_spouse` / `parent_spouse` (`i751_calc.p4_role`), `joint_petitioner`, `child`.
*Part 3 is asked FIRST* (it drives Part 4, Part 8, Item 21): `b_route` joint | waiver | unsure; joint = ONE box (1.a / 1.b); waiver = a MULTI-select of 1.c-1.g (+ "not sure").
Never decided: no timeliness, good-faith, hardship or eligibility conclusion anywhere. *Privacy:* `FormField.config_json` `private` (filing basis, Part 6 health answers,
explanations for Items 18/20) -> the snapshot carries it and My Applications shows "Private — shared only with OG"; document titles/messages, completeness text, roles and
activity never name a sensitive basis; Admin sees everything with a PRIVATE marker. Part 8 (spouse's statement + contact) only for a joint petition (1.b: OG confirms).
*Residence history (Item 22):* the address builder gained `timeline.since_field` (`intake_records.analyze(..., since=)`, `POST records/analyze` sends `since`, JS reads
`spec.since_input`): the window starts at the date the customer became a resident (`r_resident_since`, an OG helper), NOT a fixed number of years; N-400 keeps its fixed 5 years.
A reused address history is offered as a starting point and the edit step re-opens until `c_hist` says the period is covered (`block_pair(..., extra_edit=)`).
*Children:* repeatable record type `i751_child` (no five-row limit, Children 6+ -> DERIVED Part 11 entries); every child is a real Person (`record_people` flags `dob_match` /
`dob_claim`: a name match is rejected when the known date of birth differs, so two same-named children stay two people; the typed DOB is recorded as a claim). Records
that point at a Person (`person_id`) are filled from that Person BEFORE validation (`fill_from_people` in the save path) and a foreign id is dropped.
Reuse blocks: identity, other names, ids, marital, physical address, residence history, biographic (new facts `ethnicity`, `race`(list), `height_*`, `weight_lbs`, `eye_color`,
`hair_color`, mapped from the I-485 and N-400; never inferred) and, for the spouse, name, DOB, ids, address, contact. Part 11 is generated (`i751_calc.additional_entries`,
hidden `c_addl`); the customer never gives page/part/item numbers. Documents: `i751_docs.py` (workflow / answer basis labels only — the Instructions were not supplied, so no
claim about what USCIS requires; grouped for the customer as Your status / marriage / filing situation / children / other; titles tied to a private basis are neutral).
Part 10 Item 7 is DERIVED from `business_info.PREPARER_STATUS`; `PREPARER_FAX` added. Admin panel: `i751_views.admin_summary`. Tests: scratchpad `e2e_i751a-d`, `verify_cov751`.

*Case setup* (`case_setup.py`, `/f/<slug>/setup`, template `public/intake_setup.html`): forms whose `FORM_CASE_CONFIG` has
`case_setup: True` (only the I-485) are NOT auto-attached to a case; the customer picks the applicant (self / an existing case
person / someone new) and the case (existing or new). Only the customer's own open cases are offered; the petitioner-only person
and a second active I-485 for the same person are refused; every step, autosave, review, finalize and the backfill redirect/skip
a draft that still needs setup. Standalone I-485 (no I-130) creates its own case. One open draft per customer+service remains.

*Shared review blocks* (`shared_blocks.py`, `FORM_CASE_CONFIG["I-485"]["blocks"]`): for each shared fact group (name, birth,
other names, A-Number, USCIS account, SSN, arrival, I-94, address, address history, employment, parents, spouse, contact) the
intake has a review step ("We already have this information for Maria" -> Everything is correct / I need to change something) and
the ordinary edit step. `<block>_avail` (frozen on the never-shown first page) says whether the case knows it; confirm copies the
values into the application's own answers AND records `confirmed`/`updated` on the canonical `PersonFact` (original source kept,
`PersonFactEvent` history). The edit step also appears after a confirmation while a `needed` detail the case cannot supply is empty.
Config flags in `FormField.config_json`: `keep` (never purged although the step is skipped), `system` (hidden from Review/Admin),
`block` (which block a field belongs to; Review "Edit" of a skipped edit step opens the block's review step; `edit_followup`).
The applicant is a Case Person (role `applicant`); the spouse/children/parents in the answers are matched to existing case people
(never duplicated; no logins); `ApplicationLink` links the I-130 the applicant says the I-485 is based on (only if the customer says so).
Admin sees a Case panel on every application (`case_panel.py`: people/roles, related applications, document requirements with
basis, which shared facts were used and whether confirmed).
Tests live in the session scratchpad only (e2e_i485a-f); to rerun the whole regression on a DB copy use a wrapper that sets
`DATABASE_URL` to a copy BEFORE importing `app` and removes a dev-seeded I-485 form first.

**Real-person identity (Customer -> Person -> CasePerson -> ApplicationRole), migration `b4d1e9a2c7f3`.** `Person` (`persons`) is a REAL
human inside ONE customer's data, once (`is_self` = the customer's own, partial-unique per customer); `CasePerson.person_id` links each
participation in a case to it (an `after_insert` listener links every new CasePerson: the customer's own to the single self Person,
anyone else to a NEW Person; two people are NEVER merged by name — only `pers.link_case_person` / `case_person_for` /
`add_person(link_to=)` / Admin "Link as the same person", all same-customer only). Facts belong to the Person
(`PersonFact.real_person_id`; `person_id` is only the CasePerson it was first recorded through) so stable facts follow the human
across cases; the source application does NOT have to share a case with the destination. `app/persons.py` = the whole service:
per-application **claims** (`PersonFactClaim`: value, form/field/Part-Item, state draft|submitted|reopened|manual, resolved),
`record_claim`, `evaluate` (conflict detection), `offer(person, key, submission)` (what could be reused for ONE application, never
its own claims: single | conflict, confirmed?, stale?, draft_only?), `confirm/update/accept_offer/resolve_conflict`, `open_conflicts`.
**Scopes** (`case_types.FACT_SCOPE`): stable (names, DOB, sex, birthplace, nationality, A-Number, USCIS account, SSN, other names, parents;
different values = CONFLICT, never picked silently) vs situational (address, phones, email, employment, I-94, arrival: newest is
offered with its date, "Is this still current?", stale after `STALE_DAYS`); case data and application data are never globalised.
**Conflict flow**: review step of a shared block redirects to `/f/<slug>/conflicts?block=` (nothing pre-selected; options show each
source form/date; "Enter a different value"); `resolve_conflict` confirms the chosen value, keeps every claim as history and
never rewrites any application answer. **Availability**: `<block>_avail` is recomputed on every visit until the customer answers the
block (`answered` = the review choice or the edit step saved); afterwards newer/different data is only flagged
(`shared_blocks.changes_after_confirmation` -> completeness/admin). **Lifecycle** (`cases.sync_claims`): drafts feed claims after every
step/autosave (state draft, never confirmed), submit -> submitted, reopen -> reopened (`reopen.py`), resubmit/lock -> submitted.
**Case compatibility** is data (`FORM_CASE_CONFIG[form]["case_types"]`, `compatible_case_types/is_compatible`): I-90 -> Green Card
Renewal, N-400 -> Naturalization, I-130 -> Family Petition | Adjustment of Status, I-485 -> Adjustment of Status; enforced in
`attach_application` (raises `IncompatibleCase`) and the case-setup page. Moving an application keeps WHO each role belongs to
(roles re-map to the CasePerson of the same Person in the new case). Documents stay case-oriented (no cross-case exposure).
Admin: `/admin/persons` (+ detail: cases, application roles, facts with every source, open/resolved conflicts, masked sensitive values,
match suggestions by A-Number or name+DOB, explicit link). `cases.backfill_persons()` (startup, idempotent) linked existing CasePeople,
merged facts under the Person (differences kept as claims -> conflicts) and `fix_incompatible_placements()` moved the I-485 dev draft
OGF-58D5DC out of the Naturalization case; `seed_i485.ensure_i485_shared_data()` refreshes wording and resets only DEFAULTED block choices.

**DS-260 (production, Consular Processing, 2026-09-19).** The DS-260 is an ONLINE Department of State form (CEAC), NOT a USCIS form: no edition number, and OG never
completes, signs, certifies or submits it. The intake PREPARES answers; staff type them into CEAC. `seed_ds260.py` (form `ds-260-client-intake`, 53 pages, ~345 fields, ~276 CEAC-mapped),
service `immigrant-visa-ds-260`. New case type `consular_processing` (`models/consular.py`: `Ds260Source` snapshot, `ConsularCaseData`, `Ds260Application`, `Ds260CeacOverride`;
migrations `d260c0a51e01/02`). **One DS-260 per visa-applicant Person** (roles `visa_applicant` + `principal_applicant|derivative_applicant`), all in one consular case; the underlying
I-130 stays in its own case and is only LINKED (`ConsularCaseData.underlying_submission_id`). `FORM_CASE_CONFIG["DS-260"]` has `multi_draft` (several open drafts; `service_start?new=1`,
never two for one applicant in a case) and `setup: "visa_applicant"` (`consular.py` options/apply, `public/intake_setup_ds260.html`: applicant, principal/derivative, case, petitioner,
NVC number + invoice ID (masked everywhere, never in a URL/log/activity), linked I-130). Father/mother/spouse/previous spouses/children are person-linked records (`ds260_records.py`,
`person_id` picked from the customer's own People, `fill_extra` copies birth place); typed relatives that look like an existing Person get a "reuse them" prompt (`ds260_checks`).
**Source snapshots** (`ds260_source.py`): agency/system/official name/references/verified date/schema hash + frozen registry; an application keeps its snapshot; `introduce_snapshot`
adds a new one without touching old applications; `diff(a, b)`; admin `/admin/ds260/snapshots`. Sources: the supplied 2019 sample + Federal Register 2025-20231 deltas (travel = fifteen
years, asylum question wording, medical disclosure); the June-2023 sample and live CEAC were NOT reachable, social-media provider list is not in the sample (free text), section
visibility rules (age/sex/nationality/visa class) are recorded as UNVERIFIED hints only (`ds260_calc.hints`), never used to hide a customer question. `docs/DS-260_source_coverage.md`
audits every question. **CEAC-ready layer** (`ds260_ceac.py`): per field `features["ceac"]` (section, question, transform); customer value, canonical value, English CEAC value
(ASCII-folded, names upper-cased, dates DD-MMM-YYYY, free text that looks Spanish flagged "needs English" until staff sets an override), provenance, confirmation, flags. Admin CEAC
Preparation View `/admin/ds260/<id>/ceac`: sections in CEAC order, per-value Copy buttons (no copy-all), Security sections private, "Only in CEAC" list (signature, certification,
NVC number/CAPTCHA, FGM/C, medical consent are never collected). OG status (`ready_for_ceac` = prepared, never submitted) is separate from the CEAC status recorded by staff
(`not_started|incomplete|submitted|reopened`); after CEAC "submitted" every action shows the reopening warning. Ready for CEAC is refused with missing answers, an unsent
application or an open Person conflict. Security & Background: every 2019 question (8 pages, vaccination question inverted), all private/sensitive, Yes = required explanation and
"OG review" count only (never a conclusion); documents (`ds260_docs.py`, bases `dos_nvc|answer|workflow|admin|customer`) are per Person with neutral titles for private ones.
Reuse/conflict/time-sensitivity use the existing Person layer unchanged. Customer Review shows group headings (`features.review_groups`, `review_documents`). Tests: scratchpad
`e2e_ds260a-c` (harness `ds260data.py`); note `cases._sync_record_people` now decides role deletion after all specs (father + mother share role `parent`).

**ITIN / Form W-7 (production, Tax & ITIN Services, 2026-09-20).** OG's ACTUAL online ITIN workflow (not a line-by-line digital W-7): `seed_w7.py`, form `w-7-client-intake`, IRS Form W-7 **Rev. December 2024**
(supplied form + instructions), ~24 pages (~14 on a typical path), linked to the existing *ITIN Application* service (`itin-application`, category `taxes-itin`). New case type
`itin_application` (its own domain "Tax & ITIN Services", `case_types.CASE_DOMAINS` / `domain_of`), **one W-7 application per ITIN applicant Person** (a `FormSubmission` of the W-7 form,
`W7Application` row) **all inside ONE ITIN case** (`ItinCaseData`: tax year at case level, new/renew, taxpayer status, income of the primary taxpayer, package / IRS tracking / response). Models
`models/itin.py` (migration `w7a1c0de5e01`: `itin_case_data`, `w7_applications`, `itin_doc_tracks`, `w7_extractions`), coverage in `docs/W-7_source_coverage.md`.
*Scope (OG's operational rule, never an IRS eligibility decision):* applicant physically in the U.S., valid U.S. mailing address, ITIN tied to a federal return OG prepares
(`itin.parse_setup` / `apply_setup`, `/f/<slug>/setup` kind `itin_case`, template `intake_setup_itin.html`); anything else shows "This type of ITIN request is not currently handled through
OG's online ITIN intake…" and creates nothing. **ITIN Exceptions 1-5, reasons a/f, line 6g, tax-return intake, e-file, payments and IRS submission automation are NOT IMPLEMENTED.**
The customer never sees or chooses a W-7 reason (a-h): `w7_calc.reason_candidate` derives a CANDIDATE (primary b/c; spouse e or b/c/g; dependent d, d/g or review) and staff confirm the final
letter (`itin_admin.confirm_reason`) before Ready for IRS. OG does not approve or deny ITINs; every customer page says the IRS decides and that "Send to OG" is not a W-7 signature/filing.
*Passport-first (`w7_passport.py`, `/f/<slug>/passport`):* `pp_status` have / later / none. There is NO OCR service and no customer document is ever sent to a third party: a photo page is read by the
local pure-Python ICAO 9303 TD3 MRZ parser (`parse_mrz`, check digits), an optional LOCAL tesseract hook (`extract`, absent here), OG staff (Admin pastes the MRZ / types values: source `staff_read`) or the
customer (typed). The CUSTOMER always confirms or corrects ("We found this information on the passport.") before anything becomes a confirmed Person fact; provenance = source document, reading source
(`mrz_ocr|staff_read|customer_typed`), confirmed-by-customer date (`PassportExtraction`, `PersonFact.source_ref`). A confirmed value that differs from a confirmed Person fact becomes a visible claim
(open conflict), never an overwrite; the customer resolves it on the passport page (`w7_views.conflict_rows/resolve_conflicts`). "Later" never blocks: requirement `w7.passport` stays "needed"
(flags PASSPORT — NEEDED / PERSONAL DATA — PENDING PASSPORT VERIFICATION), a later upload from My Account or the passport page creates a pending reading and the same Application updates (no duplicate). Identity
fields (`a_family`… `a_nationality`) are required ONLY when there is no passport (`require_field` rule), otherwise they are kept answers written by the confirmation and never block Review.
*Evidence rules (`w7_rules.py`, Instructions p. 4/6/16):* three separate questions are never mixed: ACCEPTED BY THE IRS (identity/foreign status/photo/residency matrix, passport stands alone, otherwise >= 2
document types), OG (as a CAA) CAN VERIFY (dependents only passports and birth certificates; everyone else all but a foreign military ID) and ORIGINAL MUST BE PROVIDED. Age drives the dependent rules (photo exempt
< 14 / < 18 student, medical record < 6, school record < 24 if a student, residency options by age band, passport without an entry date is not stand-alone for dependents; Canada/Mexico = OG review note).
`w7_docs.py` builds the vault requirements (`doc_basis` `irs_w7|answer|workflow`, one sync over every active W-7 of the case) and `ItinDocTrack` (physical original: required / will mail / will bring / in transit / received /
CAA verified / ready to return / returned; `caa_route` caa | irs_original). A photo upload NEVER moves the original state (only staff, `itin_admin.record_original`); CAA verification is an explicit staff action recording who,
when and which document version (`verify_original`, `caa_review`). Originals go to OG Multiservices LLC, 145 Presidential Blvd, STE 2, Paterson, NJ 07522 or in person (central config, `w7_text.delivery_html`).
*Flags (`w7_calc.flags`, "OG REVIEW — ADDITIONAL W-7 INFORMATION REQUIRED" style, never a conclusion):* passport needed / unconfirmed, w2_identifier ("W-2 / taxpayer identifier requires OG review"), ssn_status, taxpayer_id_missing (d/e),
line3_foreign_address, renew_itin_missing, visa_details, canada_mexico, residency_open. Customer text is neutral; W-2 is collected as issued.
*Admin:* `/admin/itin` (list), `/admin/itin/<case_id>` (`itin_routes.py`, ITIN Case view: readiness blockers, staff status set, tax info, applicants, per-document original tracking and CAA verification, USPS package, IRS response),
`/admin/w7/<submission_id>` (W-7 Preparation View in W-7 order: `w7_map.build`, provenance, candidate vs confirmed reason, staff passport reading, signature status, CAA review) and a panel on the application page. Statuses:
Intake Started, Waiting for Documents, Waiting for Original Documents, Ready for OG Review, OG Reviewing, Tax Preparation, Ready for Signature, Ready for IRS (needs: sent to OG, passport confirmed, reason confirmed, signature recorded,
CAA review, no open documents / originals / conflicts), Sent to IRS, IRS Processing, IRS Response Received, Completed. USPS delivery NEVER implies IRS Processing and the IRS response (ITIN issued / IRS notice / other) is only what staff record.
*Customer:* My Account case page (`account/_itin_dash.html`): domain chip, status, applicants with "Passport Needed [Upload Passport]", originals to give OG + Paterson instructions + mail/in-person choice
(`my_case_original`, intention only), "Package sent to the IRS / Tracking Number / [Track Package]", the IRS processing copy (7 weeks / 9-11 weeks, EN/ES) and the disclaimer. Not built: PDF W-7 export, IRS signature collection.
*Customer UX rules for this intake (cleanup 2026-09-20):* the customer is not a tax professional. Short intro ("Antes de empezar": who, tax year, one lead sentence, passport tip, saved automatically, small IRS note; the long
disclaimer stays on "What happens next" / Review). The passport page is upload -> reading -> "2. Confirma la información" -> Confirm: NO conflict panel is ever rendered for the customer (Person conflicts stay internal:
open `PersonFact` conflict + admin flag `person_conflict`, `w7_checks` no longer mentions them). The customer can Replace / Remove the uploaded passport (`w7_views.remove_passport`, also from My Account): the vault document goes
through `vault.remove_document` (only before OG review, `customer_can_remove`), earlier readings become `superseded` (history kept, never a confirmed passport again), the requirement is open again and completeness is recalculated;
a replacement is a new pending reading that must be confirmed again. Customer-facing document wording is localized in `w7_text.REQ_TEXT / ALT_TEXT / RES_TEXT / BIRTH_CERT_TEXT` and resolved by `w7_docs.req_text(req, lang)` through the generic
hook `case_documents.customer_text` (stored `DocumentRequirement.title / customer_message` remain the English admin record; other case types are unchanged). Any new customer text must be authored EN + ES there or in the form seed.
IRS/source terminology is not shown to the customer. `seed_w7.ensure_w7_refinements()` applies text-only wording changes IN PLACE to an existing form (intro, income note paragraph `self_gross_note`, passport/documents page text) without touching answers or rules.
CAA identifiers (`CAA_EIN`, `CAA_PTIN`, `CAA_OFFICE_CODE`, fax) are empty in `business_info.py`: OG must enter them (never guessed). Tests: scratchpad `e2e_w7a-d` (harness `w7data.py`), `verify_covw7`.

**Tax Return (production, OG Tax Smart Intake v1, Tax Year 2025, 2026-09-21).** A DEDICATED module, `app/tax/` (never the generic Form Builder / `FormSubmission`): own case type `tax_return`
(`case_types.py`), its own `TaxCaseData`/`TaxRecord`/`TaxPriceRule`/`TaxPriceQuote`/`TermsAcceptance`/`TaxBankInfo` tables (migration `tx25a1c0de01`, additive), linked to the *Individual & Family
Tax Preparation* service (`tax-preparation`, `app/tax/registry.py SERVICE_SLUG`) whose "Get Started" resolves in `service_public.service_cta` straight to `public.tax_start` (bypasses the generic
intake `service_cta` path entirely; label becomes "Continue Your 2025 Tax Return" while a draft is open). The customer is NEVER asked about schedules, credits, filing-status law, or IRS line
numbers — every question is a plain fact; "Not sure" is always an option and only creates an OG review flag, never a wrong answer.
*Interview engine* (`app/tax/questions.py`): a declarative `Step`/`Q` framework (kinds text/number/money/date/select/choice/multi/yn3/ssn/phone/email/state/note/docs/records/person_pick/secret),
server-authoritative `show` conditions read through `Ctx.v()` (a hidden answer is kept, never erased, but ignored everywhere until its question is visible again — same rule as every other intake in
this project). `Ctx.deps`/`Ctx.bizs` additionally gate on whether their OWN list step (`works_biz`, `has_deps`) is still on the active path: unchecking self-employment stops the hidden business
record from driving documents/pricing/flags although the row stays in the database (nothing the customer typed is ever silently discarded — `service.remove_record` is the only real delete, driven
by the customer's own "Remove" button). `app/tax/y2025.py` is the whole 2025 interview (26 steps, ~123 questions): About You, prior-year return (new customers only, upload now/later/none, never
blocking), marital status at Dec 31 (a fact, never a HOH/QSS determination), spouse, dependents (`TaxRecord kind="dependent"`, linked to a real Person, facts only — no qualifying-child questions),
one income-routing screen, W-2 (document-first, no manual box typing, no OCR/AI), self-employment (`TaxRecord kind="business"`, repeatable, separates TOTAL RECEIPTS / documents supporting / income
NOT in any document — never summed together), vehicle (mileage always asked; no tax-method question), business expenses (category + amount, "Not sure" → OG review), health insurance, childcare,
education, home/mortgage, charity, estimated payments, one "other situations" routing screen (foreign / complex crypto / complex self-employment route to `flags.PRO_REVIEW`, "OG TAX PROFESSIONAL
REVIEW REQUIRED", never a customer-facing wording problem — see `app/tax/flags.py`), IRS payment preference, refund direct deposit. **Returning-customer detection is from OG's own records**
(`service.returning_status`: an earlier tax case OG completed), never a checkbox; the intro and an annual "what changed" screen adapt, but nothing from a prior year is copied into 2025 without the
customer confirming it that year (dependents are *offered* via "From last year", `service.previous_dependents`/`carry_over`, not auto-added).
*People* (`app/tax/people.py`): every Person-bound question (`Q.bind`, e.g. `given_name`/`ssn`/`address.street`) writes through the SAME real-Person layer as every other intake
(`people.set_fact` → `pers.record_claim`/`confirm`/`update`); SSN is NEVER stored in `TaxCaseData.answers_json`, only as a masked Person fact. A carried-over dependent's name/DOB/SSN come straight
from the Person (pre-filled, editable) but relationship and SSN status are per-record and are asked again every year (`carry_over` routes to the FIRST record step, `dep_who`, not past it — an
earlier version of this route skipped straight to `dep_life` and lost those two answers; fixed before ship).
*Documents* (`app/tax/docs.py`, `SOURCE_KEY="tax"`): every requirement is generated from the answers (W-2 #n by count, 1099 types, dependent birth certificate + a 2025 residency proof, 1095-A #n,
1098-T per student, 1098-E, 1098, business platform/1099/expense records, prior-year return, photo ID) through the SAME Document Vault as every other case type (`case_documents.py`); a *reusable*
category (birth certificate, photo ID) is offered "Already on file" within the case AND across the customer's other cases (`vault.find_reusable_elsewhere`/`reuse_across_cases`, same file, new vault
row, history kept) — an *annual* document (2025 residency proof, this year's W-2s) is NEVER reused across tax years even for a returning customer. Upload Later / Can't Find are stored as
`TaxCaseData.doc_choices` and never block *sending* information to OG (`docs.missing_required` only blocks the *Ready for Preparation* status transition, `service.readiness`).
*Pricing Engine* (`app/tax/pricing.py`, fully data-driven — `TaxPriceRule` rows per tax year, `SEED_2025`, `pricing.ensure_seed(year)` called from `seed_content.ensure_seeded()` at startup, admin-
edited rows are never touched by re-seeding): base fee by pricing CATEGORY (single/mfj/hoh/mfj_family/qss — a pricing bucket, never a filing-status conclusion) + complexity add-ons (extra dependent/
W-2, self-employment simple/moderate/complex, Marketplace, childcare, education, investment sales, rental, itemized complexity, extra state, simple crypto) + the 10% Returning Client Discount
(percentage, active flag, stackable setting, applies to the preparation fee only) − nothing is ever charged per IRS form or schedule. A complex situation (foreign income, complex/unclear crypto,
complex self-employment, moved to another state, an estimate above `max_auto_quote` = $400) becomes `mode="manual"`: the customer sees only "OG will review and confirm the price" (`pricing.
customer_view`), staff still see the full calculated estimate and reasons in Admin. `pricing.snapshot` creates a `TaxPriceQuote` revision; a CONFIRMED price is never silently replaced by a new
estimate — a changed estimate becomes a `revised` quote OG must re-confirm, and `pricing.confirm` requires a written reason whenever the fee differs from the estimate or replaces an earlier
confirmed fee; `needs_ack` makes the customer acknowledge a changed confirmed price in My Account (`public.tax_price_ack`) before the banner clears. No amount is ever hardcoded in a template — every
price shown anywhere comes from this engine.
*Refund bank details* (`app/secure_store.py`, Fernet via the `cryptography` package, key from `DATA_ENCRYPTION_KEY` or `SECRET_KEY` — refuses to store in clear if neither is a real value, i.e. the
dev-only insecure default): `TaxBankInfo.routing_enc/account_enc` are encrypted at rest, only `routing_last4`/`account_last4` are ever displayed to the customer or in Admin; the full numbers are
shown to staff only via an explicit, audited action (`tax_bank_reveal`, logs `tax_bank_viewed`) and never appear in a flash message, log line or URL. A secret field left blank on save KEEPS the
existing saved value; typing a new value always overrides "leave blank to keep it" (fixed a bug where a freshly typed routing/account number was still flagged missing).
*Workflow* (`app/tax/service.py`): Draft → Submitted to OG → OG Review → Waiting for Client → Ready for Preparation → In Preparation → Ready for Client Review/Signature → Ready to File → Filed →
Accepted → Completed, plus Rejected/Amendment Needed/On Hold/Closed/Reopened. "Send my information to OG" (`service.submit`, versioned `TermsAcceptance` recorded with language + hashed IP, never
the raw address) is explicitly NOT filing; Filed ≠ Accepted; Accepted is never described as an IRS approval of any amount. Reopen for Customer Editing reuses the SAME `Case`/`TaxCaseData` row
(status `reopened`, `resubmit_count`), exactly like every other reopen flow in this project. `app/tax/summary.py` builds both the customer's plain-language review cards (SSN/bank masked) and
Admin's structured `admin_summary` (same underlying data, English, unmasked where staff are allowed to see it).
*My Account* (`app/tax/portal.py` + `account/_tax_dash.html`, included from the existing `account/case_detail.html` next to the ITIN dashboard): status in the customer's own words, "What you need
to do" (finish the intake / OG's message / missing documents / acknowledge a new price), the price panel, and a documents link — the case also appears in My Cases with the "Tax & ITIN Services"
domain chip for free, via the same `domain_of`/`type_title` helpers every other case type uses.
*Admin* (`app/blueprints/admin/tax_routes.py`, templates `admin/tax_list.html`/`tax_case.html`/`tax_pricing.html`/`tax_bank.html`): Tax cases list (year/status filters), the Tax Case view
(readiness blockers, status change, request information, reopen, price confirm/override with reason + full revision history, payment placeholder — state and reference only, no gateway, OG review
flags, per-requirement document status, the full interview summary by section, audited bank reveal, internal notes, activity), and Tax Services → Pricing (every base/add-on amount, the discount
percentage and stackable flag, thresholds and manual-review triggers, per tax year, active/inactive).
*Not built:* no tax calculation engine anywhere (no refund/balance is ever computed), no e-file, no PDF/Form 1040 export, no payment gateway (Square/Stripe are placeholders only:
`payment_status`/`payment_reference`), no AI/OCR on any tax document. Tests: scratchpad `tax_suite.py`/`tax_suite2.py` (harness `taxdata.py`) — cases A–J from the spec (pricing by household
category, W-2/self-employment/Marketplace documents, the 10% returning-client discount with cross-case document reuse, manual pricing for a complex/foreign case, Upload Later never blocking Send,
answer changes safely recomputing hidden records, unauthorized cross-customer access denied on every tax route) plus reopen/price-revision/acknowledgment, encrypted bank details, and a full Spanish
walk with no English-string leaks.

**NJ Driver License Assistance (production, its own case type, 2026-09-22).** A SIMPLE, guided, one-question-per-screen intake (`app/driver_license/`, reuses `app.tax.questions`'
`Step`/`Q`/`Opt`/`Ctx` engine unchanged — confirmed to have zero tax-specific coupling) — never a document-points worksheet for the customer. Own case type `nj_driver_license`
(`models/driver_license.py`: `DlCaseData`, `DlPriceRule`/`DlPriceQuote`, `MvcLocation`, migration adds 7 tables), linked to the *NJ Driver License Assistance* service
(`nj-driver-license-assistance`, seeded by `app/driver_license/seed.py`). First question is "Where are you in the process?" (8 options, verbatim per spec); branching from there
decides how many of the ~12 steps a customer sees. **Document discovery** is large multi-select cards (Passport, Driver License from your country, National ID/Cédula/DNI, Birth
Certificate, Permanent Resident Card, EAD, Other, Not sure) — never asks about MVC points. **Rules engine** (`app/driver_license/rules.py`, `RULES_VERSION`/`RULES_SOURCE`
constants): identity/point classification, NJ address evidence, SSN/ITIN path, translation need — stamped onto `DlCaseData.rules_version` per submission so a future MVC rule
change never silently rewrites a past assessment. **SOURCE NOTE (unverified):** no official NJ MVC 6-Point document was supplied this session; point values in `rules.py` are
OG's own understanding and are flagged for OG's manual review before being treated as authoritative — same honesty pattern as the DS-260/W-7 SOURCE NOTEs. SSN/ITIN/Affidavit is
one simple question (SSN / ITIN / Neither / Not sure); "Neither" flags `affidavit_review` for OG internally — customer text never shows the flag string and never auto-declares
affidavit eligibility. A foreign driver license is asked (country/validity/language) but NEVER waives the Road Test: `DlCaseData.road_test_state`
(`ROAD_TEST_STATES` = to_be_determined/required/not_required/appointment_needed/scheduled/passed/failed) starts and stays `to_be_determined` until an Admin explicitly sets it.
NJ address proof offers the full official category list (bank/electric/water/lease/credit card/government mail/insurance/tax document/other/none yet/not sure).
**Translation pricing** (`app/driver_license/pricing.py`, mirrors `app/tax/pricing.py` exactly): `DlPriceRule` rows (Admin-editable, seeded once) for Spanish national ID/foreign
license/birth certificate (~$35 each, a non-standard birth certificate flips to OG Review instead of an auto-price), Portuguese/French id/license (~$45), and Initial Permit
appointment assistance ($10) — every price shown to the customer is labeled an estimate; `DlPriceQuote` revisions mean a confirmed price is never silently replaced (`needs_ack`).
**MVC locations** are an Admin-managed table (`MvcLocation`: name/slug/active/sort_order/appointment_types), never hardcoded in a template; the customer picks 1st/2nd/3rd choice
from it. **Documents** go through the existing Vault (`app/driver_license/docs.py`, `SOURCE_KEY="nj_dl"`, cross-case reuse for passport/birth certificate/PR card/EAD via
`case_svc.ensure_customer_person`); Upload Now / Upload Later / Don't Have It Yet never blocks Send. **Milestones**
(`DL_MILESTONE_ORDER` = documents, initial_permit, knowledge_test, road_test, license_obtained, completed; customer-friendly text in `app/customer_status.py`'s `_DL_MILESTONE`)
drive a simple visual roadmap (done/current/upcoming/not_required/to_be_determined — `app/driver_license/portal.py roadmap()`); Road Test alone can show "To be determined"
before it is reached, every other future step shows "Upcoming". **My Account**: `account/_dl_dash.html` (roadmap + one "What you need to do now" section + the price panel),
included from the existing generic `account/case_detail.html` next to the Tax/ITIN dashboards, wired from `cases_portal_routes.py my_case_detail`; the Home/Services task
aggregation needed zero extra code (`app/account_dashboard.py`'s `_dl_entry`, added the same way `_tax_dash`/`_itin_dash` were). **Admin**: `/admin/driver-license` (list, case
view, pricing, locations, questions) in `app/blueprints/admin/dl_routes.py`; case view covers documents/pricing/SSN-ITIN path/foreign license/appointment locations/milestones in
one screen, with actions to confirm price, set milestone/sub-status (Initial Permit/Knowledge Test/Road Test), and request documents — all through the existing activity/audit
architecture. **Not built:** no MVC appointment-availability scraping or booking, no PDF export, no payment gateway (price fields are placeholders, same as Tax).

**NJ Knowledge Test Practice (production, account required, 2026-09-22).** A free practice simulator (`app/driver_license/quiz.py`, `app/blueprints/public/dl_practice_routes.py`)
that requires an OG Account to start (never anonymous — the explainer page alone stays public); starting or completing practice NEVER creates a Driver License Case on its own
(`DlAttempt.dl_case_id` is set only when the student already has one, purely informational). Modes: Quick (10 questions, immediate per-question feedback), By Topic (10, immediate
feedback), Full Exam Simulation (50 questions, feedback withheld until Results — mirrors the real exam's flow); passing target 80% (`quiz.PASS_PERCENT`). Every practice page states
"This is a practice tool provided by OG Multiservices LLC. It is not the official NJ MVC knowledge test." (EN/ES). **Question bank**: `DlQuestion`/`DlQuestionOption`
(`app/driver_license/seed_questions.py`, ~57 ORIGINAL questions across the 16 topics the spec named — concept_key/topic/difficulty/EN+ES question/EN+ES choices/correct
answer/EN+ES explanation/source_ref/version/active). **SOURCE NOTE (unverified):** written from general knowledge of NJ driving rules, NOT transcribed from the official NJ Driver
Manual or any third-party bank; numeric specifics (exact fines, exact distances) should be verified against the current manual before being treated as authoritative — same honesty
pattern as the rules engine above. `quiz._draw()` randomizes and spreads across topics so a large-enough bank never repeats the same 50; `DlAttempt`/`DlAttemptResponse` are a
DEDICATED small model (not Academy's `QuizQuestion`/`QuizAttempt`, which are one-quiz-per-lesson with no topic/difficulty tagging or cross-bank random draw). Results show
score/percent/pass-fail, a topic performance breakdown, and Review Incorrect Answers; practice history (`quiz.history`/`quiz.best_score`) shows Tests Completed/Best Score/Last
Score in both My Account and the practice-modes page — no excess data stored (no per-second timing, no IP, no device fingerprint). A student with no Driver License Case sees a
single, non-aggressive "Need help starting your NJ Driver License process? [Check What I Need]" card on the practice-modes page (gone once they have one). Auth-gating reuses the
exact `student_required` + `next=` return-URL pattern already proven throughout the app (register/login return to the precise practice URL, language and mode preserved). **Not
built:** no per-question timer, no adaptive difficulty, no more than 16 topics.

**NJ Driver License — correction/refactor pass (2026-09-22, same day).** A manual click-through after the build above found real business-logic and UX gaps; all fixed IN PLACE (never rebuilt).
*Translation priority* (`app/driver_license/rules.py document_plan()`): the pricing engine used to translate EVERY translatable identity document the customer selected. It now walks
`PRIORITY_TRANSLATABLE = (foreign_license, national_id, birth_certificate)` (OG's stated order) plus `PRIMARY_KEYS` (passport/PR card/EAD, non-translatable, any ONE is enough) and marks
each document "needed" only while more points are still needed to reach `MIN_POINTS_REQUIRED`; everything past that is "alternative" — the customer HAS it, OG can still ask for it on
review, but it is never sold a translation or shown as mandatory. `pricing.estimate()` only prices "needed" documents. `docs.is_optional()`/`docs.cards()` read the SAME plan so the
upload screen shows differentiated statuses (Needed vs. the neutral "Alternative — not currently needed", never a blanket "Necesario" on every document) and `docs.counts()` never counts
an alternative document toward "documents still needed". *Affidavit of No SSN/ITIN — $25* (`pricing.py` SEED row `affidavit_no_ssn_itin`, kind `affidavit`, Admin-configurable): added
automatically to the estimate whenever `ssn_itin_path == "neither"`; customer-facing label is "Affidavit of No SSN / ITIN — Preparation Assistance" (never a legal/MVC eligibility
determination — the internal `affidavit_review_required` flag stays admin-only, unchanged). *Other-document translation* (item 4): NJ address proof and ITIN evidence each gained a
language question (`addr_lang`/`itin_lang`) and, for address proof, a length question (`addr_long`); both price through the SAME "configured rule, else OG Review" mechanism as identity
documents — no flat $35 is ever assumed for a bank statement or ITIN letter. *Country of Birth* (`a_birth_country`, `select` kind, `app/driver_license/countries.py` — the existing
`select` field pattern already used for MVC locations/US states, inherently type-to-jump searchable; no new autocomplete widget introduced) is bound to the canonical `birth_country`
Person fact already used by I-485/I-765/I-130/N-400/DS-260, so it prefills/reuses automatically through the same bound-field mechanism every other intake relies on — never asked twice.
*WhatsApp preference* (`a_wa_same` yn3 + conditional `a_wa_number`) is a plain communication preference stored in `DlCaseData.answers`, not a Person fact. *Front/Back + multi-page
documents* (items 9-10): `docs.TWO_SIDED = (foreign_license, national_id)` splits a "needed" two-sided document into two Document Vault requirements (`dl.doc.<key>.front` / `.back`);
`BC_MAX_PAGES = 3` does the same for a "needed" birth certificate (`.p1` mandatory, `.p2`/`.p3` optional extras via `docs.is_optional()`) — no new Vault model, just more `rule_key`
rows under the existing `DocumentRequirement`/`CaseDocument` architecture (`req_text_for()` renders "— Front"/"— Back"/"— Page N"); an "alternative"-role document stays a single plain
requirement, never split. The upload macro gained `capture="environment"` and "Upload / Take Photo" wording for real mobile camera capture. *UX polish*: the customer detail page's
top-level "N document(s) need your attention" banner is suppressed for Driver License (it duplicated the dashboard's own "What you need to do now" — `case_detail.html`
`not tax_dash and not dl_dash`, mirroring the pre-existing Tax suppression); `_dl_dash.html` was restructured so the current step + required action are the strongest thing on the
page and the 6-milestone roadmap collapses into a compact `<details>` list below, not six equal boxes; the shared `case_number` label changed from "Case" to "Reference" (de-emphasized,
applies to every case type). *The public category hub page* (`/services/nj-driver-license`) had a dead "Get the Document Checklist" WhatsApp CTA predating the guided intake, left over
from before this feature existed — `service_public.category_cta()` now special-cases this one category the same way `service_cta()` already special-cases the service page (auth-aware
"Check What I Need" / "Continue My Process" straight into `public.dl_start`), and the "NJ Driver License Assistance" card under "Our services" had been linking back to the category's
own URL (self-link) because `ServiceCategory.subpage_endpoint` was left unset by an earlier partial seeder run — `seed.py` gained `ensure_category_wiring()` (+ `ensure_service_content()`
+ `ensure_faq_translation_fix()`, the last repairing two Spanish FAQ questions that had silently fallen back to English) as permanent, idempotent backfills, the same "repair an
already-deployed row in place" pattern as `seed_w7.ensure_w7_refinements()`. Tests: `dl_suite.py` (148 scenarios, was 112 before this pass).
*Two more real bugs, found only by an actual live-browser walkthrough after the 148/148 automated pass — neither was visible to route-level tests, which post directly to Flask and never
exercise the browser's own JS*: (1) `app/static/js/tax.js` (shared verbatim by the Tax and Driver License intakes) looked up the step form by `document.getElementById('tax-form')` —
the DL step template's form has `id="dl-form"`, so on every DL intake page the script's `form` variable was silently `null` and the WHOLE client-side autosave/conditional-reveal
mechanism never ran (a newly-answered radio never revealed its follow-up question without a full page reload) — this predates this correction pass and affected the ENTIRE DL intake,
not just the new fields; fixed by widening the lookup (`getElementById('tax-form') || getElementById('dl-form')`), a one-line JS fix, no server-side change, reconfirmed against
`dl_suite.py` and `tax_suite.py` afterward. (2) The "Alternative — not currently needed" status only appeared on the intake's own upload step (`docs.cards()`); the SAME requirement
still read as a plain, undifferentiated "Needed"/"Necesario" everywhere else it's shown (the My Account case detail page, the Documents page, Home's document preview) because those
paths call the shared `vault.status_label()`/`customer_status.requirement_status()` directly. Added `case_documents.status_override(req, lang)` — a hook dispatched by `source_key`
the same way `customer_text()` already is — and wired it into both `cases_portal_routes.py`'s case detail and `account_dashboard.all_requirements()`, so the label is now consistent
everywhere the customer can see it.

**My OG Account (redesigned, 2026-09-22).** Customer-friendly status layer (`app/customer_status.py`) + a single presentation/aggregation module (`app/account_dashboard.py`) reused by
every page — NO new backend architecture; Case/Application/Tax/ITIN/DL/Person/Vault are completely unchanged underneath. Home is a summary (avatar, one cross-cutting "Action Required"
list aggregated from every case type, then Immigration/Taxes & ITIN/NJ Driver License family cards, then an "Other Services" section only when populated, then a compact Documents
summary) — never a flat list of every case. Nav stays exactly Home/Services/Documents/Messages/My Courses/Profile (`account/_nav.html`) — Immigration/Taxes/Driver License are never
separate top-level links, only groupings inside Services and cards on Home. **Four CUSTOMER-FACING families** (`account_dashboard.FAMILIES`/`_family_of()`, a presentation layer only):
Immigration, Taxes & ITIN (Tax + ITIN together, backend Case types stay separate), NJ Driver License, Other Services. The Services page (`services.html`) shows a cross-cutting "Needs
Your Attention" list first, then each family as its own labeled section (only shown when the customer has something in it — item 35), each internally split Active/Completed.
**Sorting** (`_sort_entries`/`_sort_priority`, item 36): action-required first, then processing/"OG working", then done/completed, then everything else — by recency within each tier —
applied to both Home and Services, never plain database id order. Every entry a family renders already carries the SAME customer-status tone (action/processing/done/neutral) from
`customer_status.py`, so status language is consistent everywhere ("We need information from you", never "Waiting for Client").
**Files from OG** (`app/models/customer_files.py CustomerFile`, migration `2f79b0180827`, service `app/customer_files.py`) is the INVERSE of the Document Vault: OG delivering a file TO
a customer (a certified translation, an affidavit copy, a receipt) — a deliberately separate small model, not a repurposed `CaseDocument`, because the ownership/visibility direction is
opposite. Same secure-storage convention as everything else (`app.uploads.save_course_media`, random server filename, real content-type sniffing via `_probe_upload`/`_matches_extension`).
A file is a DRAFT (`published_at` null) until an admin explicitly publishes it — never visible or counted for the customer until then. Admin: Customer 360 profile gained a "Files from
OG" tab (`admin/routes.py customer_file_upload/publish/download`, `admin/student_detail.html`) — upload with a display name/description/optional related case, Save as Draft or Upload &
Publish, publish/unpublish toggle, staff download. Customer: `/account/documents` now has two CLEARLY SEPARATE sections — "Documents I Sent" (unchanged: the existing Vault requirements
+ older Forms-engine `SubmissionFile` uploads) and "Files from OG" (`account.og_file_download`, ownership checked through the signed-in customer via `customer_files.owned()`, only ever
returns a PUBLISHED file, never a draft or another customer's) — never mixed in one list. Home shows a compact "Documents you sent: N · Files from OG: N" line. Not built: customer
notifications on a new file (the spec's "if the notification architecture supports it" — it doesn't yet, so this is a known gap, not silently faked).

**My Account visual shell (2026-09-22).** A premium header + sidebar shell replaces the old horizontal tab strip, reusing the SAME `account_dashboard.py`/`customer_status.py` data layer
— no backend change, presentation only. `templates/base.html` renders `account/_account_header.html` (logo, EN/ES, notification bell with count, profile dropdown with Profile & Settings
+ Log Out) instead of the marketing header, and skips the marketing footer/WhatsApp float/chat widget/mobile bottom bar, whenever `_is_acct_shell` (`request.blueprint == 'account' and
student` — deliberately requiring a signed-in student, not just the blueprint, so `/account/login` and `/account/register`, which share the same blueprint but render before sign-in,
keep the ordinary marketing chrome) is true. Every signed-in account page extends `account/base_account.html` (not `base.html` directly) and fills `account_body` (never `content`,
which now belongs to the shell) plus an optional `account_aside` for a right-column widget. The shell provides: a desktop sidebar (`lg:` and up) with Home/Services/Documents/Messages/
OG Academy/Profile & Settings + a small "Need Help?" WhatsApp box pinned near the bottom (never Immigration/Taxes/Driver License as their own sidebar items — those stay inside
Services, matching the four-family model above); a mobile off-canvas drawer (`#acct-drawer`, toggled by the header's hamburger button, same nav items + WhatsApp + Log Out) so mobile
never gets a squeezed desktop sidebar; and the same `_nav_items` list rendered twice (desktop `<aside>`, mobile drawer) rather than shared via one Jinja macro, kept simple on purpose.
Home (`dashboard.html`) additionally fills `account_aside` with a profile card (photo/initials, name, email, phone, language, Edit Profile) shown only at `xl` and up — it collapses away
entirely on narrower desktop widths and mobile rather than fighting the main column for space. Action Required is no longer a bullet list: each item is a full-width task row (icon +
text + a specific verb) that deep-links straight to the task; `account_dashboard._action_verb()` derives Upload / Review / Confirm / Continue from the entry's own state (docs missing,
reopened, a price awaiting acknowledgment, still a draft) so nothing says the generic "View". The four service families keep their own labeled sections on Home exactly as the prior
redesign built them (Immigration, Taxes & ITIN, NJ Driver License, Other Services) — NJ Driver License and the OG Academy course promo were previously sharing one unlabeled row and now
each gets its own small family header, matching Immigration/Taxes & ITIN. Not built this pass: a richer per-state copy pass for every reopened/self-edit family-card variant beyond what
already existed, and a dedicated accessibility audit beyond what the existing markup already carried (semantic landmarks, `aria-current`, alt text and focus states were preserved, not
newly authored).

**Reopen / change-tracking architecture (2026-09-22).** `app/reopen.py` (pre-existing, unchanged) already covers every generic Smart Intake on the `FormSubmission` engine — I-90, N-400,
I-130, I-130A, I-485, I-864, I-765, I-751, DS-260, W-7 — with `SubmissionRevision` before/after diffs and an Admin change summary. Tax and NJ Driver License are dedicated modules (not on
that engine) and previously had reopen/resubmit as a plain status flip with no change history; `models/cases.py CaseRevision` (migration `645dc3b27359`) + `app/case_revisions.py` add
the SAME capability to them: `open_revision`/`close_revision` snapshot answers through each module's own `Ctx.v()` (so a bound Person-fact, not just a plain stored answer, is captured),
`diff_answers` produces `[{key, label, before, after}]` using each module's `Step/Q/Config` field labels for a human-readable Admin change summary (`admin/tax_case.html` /
`admin/dl_case.html` "Revision history" panels), and `revisions_of`/`history` read it back. `Tax.service.reopen/submit` and `DriverLicense.service.reopen/submit` call this at the same
points `FormSubmission` reopen/resubmit already did; `reopen()` also takes `actor`/`actor_id` so a revision is credited to "admin" (staff, from `admin/*_routes.py`) or "customer".
**NJ Driver License self-edit** (`driver_license/service.py`, the one intake where the customer — not just Admin — may reopen their own submitted case): `can_self_edit(dl)` is refused
once `dl.status` is draft/reopened/completed/closed or `dl.milestone` is license_obtained/completed (Part 37's completion lockout); `start_self_edit` is `reopen()` with `actor="customer"`
— same `CaseRevision`, same Case, same everything, by construction no duplicate case is possible. Customer flow: `/nj-driver-license/edit` (confirmation PAGE, not a one-click reopen or a
JS `confirm()`) → POST `/nj-driver-license/edit/start` unlocks the SAME case → the customer edits through the ordinary intake steps → resubmitting locks it again exactly like an
Admin-initiated reopen. `discard_self_edit` restores every answer (including bound Person facts) from the open revision's `before_json` via the same `Ctx`-based snapshot mechanism, then
closes the revision with before == after (an empty diff, not a deleted row — the attempt stays in the audit trail) — its own confirmation page is `/nj-driver-license/edit/discard`.
**Safety** (Part 36): `driver_license/summary.py _flags()` adds an Admin-only, read-only flag when the customer changes their preferred MVC location (`loc1/2/3`) in a revision AFTER
`initial_permit_state` was already `scheduled`/`obtained` — it never rewrites the recorded appointment itself; Admin decides what to do. Account UI: `_dl_dash.html` shows "Discard
Changes" only while a customer-initiated edit is in progress (`dl_dash.self_editing`, derived from the case's own open `CaseRevision.reopened_by`), and a small "Made a mistake? Edit My
Information" link once the case is submitted and eligible. Tests: scratchpad `reopen_suite.py` (41 checks: Admin reopen + change summary, the full self-edit cycle, discard, the
completion lockout, the appointment-conflict safety flag, and IDOR checks that a stranger's session can never reach another customer's case through any of these routes) plus the
pre-existing `dl_suite.py`/`tax_suite.py`/`tax_suite2.py` (148 + 41 + 61 checks) re-run clean with zero regressions. Not built: the same explicit change-tracking UI for the generic
`FormSubmission` intakes' Admin change summary was not re-verified this pass (it already existed from `app/reopen.py` and was not touched); a customer self-edit option for any intake
other than NJ Driver License (out of scope — every other intake keeps the "Admin reopens, customer edits" default per the spec).

**Files from OG (digital file vault, 2026-09-22).** "My Documents" (customer -> OG, unchanged Document Vault) and "Files from OG" (OG -> customer, `CustomerFile`) are two
DELIBERATELY SEPARATE pages — Files from OG used to be a section at the bottom of My Documents; it is now its own sidebar item/page (`account/files_from_og.html`,
`account_dashboard.files_from_og_data`) because it is the customer's permanent record of everything OG has produced for them (tax return copies, certified translations,
immigration document copies, affidavits, DL paperwork), not an afterthought. `CustomerFile` (migration `db4a161092d7`, additive) gained `category` (`taxes`/`immigration`/
`translations`/`nj_driver_license`/`other` — presentation only, `app.models.FILE_CATEGORIES`/`category_label`, never a second storage system), `person_id` (optional, which family
member a file is about), `related_service` (free-text customer-facing label), `tax_year`, and `released_by_admin_id` (who clicked Publish, separate from `uploaded_by_admin_id` — who
uploaded it, since a draft can sit before anyone releases it). `title` doubles as the customer-facing display name (e.g. "2025 Federal Tax Return"); the physical filename never has
to match it and is never the primary thing shown. The page is category tabs (only categories with a published file show, so an empty category is never a dead tab) + free-text search
(`customer_files.search`, matches display name/category/related service/tax year/description/person) + newest-first, with the Taxes category additionally grouped by `tax_year`
(newest year first, undated last) so a returning customer can find a prior year's return without scrolling through everything. `og_file_download` (`account.og_file_download`)
supports `?inline=1` for a PDF/image "View" (matching the Document Vault's own `document_file` inline convention) alongside a plain "Download"; only a PUBLISHED file the signed-in
customer owns is ever returned (`customer_files.owned`, unchanged from before) — a draft 404s even to its own owner. Home shows a compact summary card only
(`account_dashboard.files_from_og_summary`: total count, how many are unseen — reusing the existing `downloaded_at` column as the "new" signal rather than inventing a read-flag —
and the single most recent file), never the full page duplicated. **Admin release** (`admin/student_detail.html` "Files from OG" tab, `admin.customer_file_upload`): Category,
Related case/application, Related service, Person (only shown when the customer has more than one), Tax year, Description, then "Make Available to Customer" or "Save as Draft
(Internal Only)" — a draft is never visible or counted for the customer until explicitly published. **Smart defaults** (item A17): the Tax Case, DL Case and Immigration Case admin
views each have a "Release a file to the customer" link that opens the same upload form with `?prefill_category=&prefill_case_id=&prefill_related_service=&prefill_tax_year=` —
a tiny inline script sets the matching field values on load; Admin can still override anything. Customer-uploaded source documents (W-2, 1099, 1095-A, birth certificate the customer
sent in) live in My Documents/the Vault and are NEVER auto-copied into Files from OG — the two directions never share a record. Tests: scratchpad `files_academy_suite.py` (part of
38 checks shared with the Academy section below) covers multi-category, multi-tax-year, search, draft-never-visible, and cross-customer IDOR on both the page and the direct file URL.
Not built: a service-detail-page "related Files from OG" widget (the spec allowed but didn't require it); per-file Spanish translation of admin-authored `title`/`related_service`
text (matches this project's existing convention — every other admin-authored customer-facing label, e.g. Document Vault requirement titles for non-seeded document types, is English
text passed straight through, not bilingual-authored); and this page's release date now uses the same `%b %d, %Y` (English month abbreviation) format every other page in this project
already uses — that is a pre-existing, project-wide limitation (no page anywhere localizes dates into Spanish month names), not something newly introduced or fixed here.

**OG Academy — Admin Grant Course Access (2026-09-22).** For students migrating from the old Wix site who already paid there: reuses `Enrollment`/`Course`/progress/quiz/certificate
architecture completely unchanged, never a fake $0 purchase or a second enrollment record — the pre-existing unique constraint on `(student_id, course_id)` already guarantees at most
one `Enrollment` row per student+course, so granting access when a row exists always UPDATES that row (see `app/academy_access.py`'s docstring). `Enrollment` gained `access_source`
(`app.models.ACCESS_SOURCES`: paid_new_site / migrated_wix / admin_complimentary / promotion / staff_test / other — a Wix student is always "Migrated from Wix", never "free" or
"complimentary", since they already paid OG), `granted_by_admin_id`/`granted_at`, `migration_reference` (e.g. a Wix order id), `internal_note` (never customer-visible), and
`revoked_at`/`revoked_by_admin_id` (migration `db4a161092d7`, additive) plus `is_revoked`/`is_active` properties. **Revoking never deletes the row** — `revoked_at` is set instead —
so lesson/quiz/certificate progress (all keyed by student_id+course_id, never by enrollment id) is structurally impossible to lose; "Restore Access" simply clears `revoked_at`, and
the SAME access_source/migration_reference/expiration survive the round trip. `app/academy_access.py` (`grant_access`/`extend_access`/`revoke_access`/`restore_access`) is the whole
service, logged through the EXISTING activity log (`app.activity.log_event`, new event types `course_access_granted/extended/revoked/restored`) rather than a new audit table.
**Admin UI** (`admin/student_detail.html` Courses tab, `admin.student_enroll`/`enrollment_extend`/`student_unenroll` [kept at its historical URL, now revokes rather than deletes]/
`enrollment_restore`): "Grant Course Access" (course, access source, Access Start Date/Duration — Course default / 30 / 60 / 90 days / custom expiration date / No expiration, never
defaulted to unlimited, migration reference, internal note); each enrolled-course row shows its access source badge and an "Extend Access / Change Expiration" disclosure with the
same duration choices. Granting access to a course the student is already active on is refused with a clear message ("already has access... until X — use Extend Access instead"),
never a silent no-op and never a duplicate row. **Admin -> Courses -> Students** (`admin.course_students`, new `admin/course_students.html`): every enrolled student for one course,
filterable by status (Active/Expired/Completed/Revoked) and access source. **Customer side**: the course appears in My Courses immediately on grant, with no checkout/payment step
anywhere in the flow (there still is no payment gateway in this project — see Known limits); a revoked enrollment shows "Access revoked" (`acct_course_revoked` i18n key) instead of
Continue, and both the page-view gate (`public.lesson_view`, redirects away with a flash, matching the existing expired-access UX exactly) and the completion POST gate
(`account._require_enrollment`, aborts 403) now check `enrollment.is_active` (expired OR revoked) instead of only `is_expired`. The self-service free-enroll route
(`account.enroll`) was also taught to never silently reinstate a revoked enrollment if the customer clicks "Enroll" again. Certificates never mention access source, "free" or
"migrated" — `app/certificates.py` has no reference to `access_source` at all, so this requires no change. Tests: scratchpad `files_academy_suite.py` (38 checks total: grant with
`migrated_wix` label verified never "free", duplicate-grant refusal, extend, revoke blocking lesson access while preserving the row/history, restore, admin-route IDOR for a
non-admin session). Not built: a Wix API integration or bulk CSV importer (explicitly out of scope — the access-source model is deliberately structured so a future importer can reuse
`academy_access.grant_access` directly with `access_source="migrated_wix"` per row).

**My Account <-> public website navigation (2026-09-22).** Two distinct destinations that must never be confused: the sidebar's "Home" is always the My Account dashboard
(`account.dashboard`); the OG logo/wordmark in `account/_account_header.html` and a secondary "Back to OG Website" link (desktop: bottom of the sidebar, below "Need Help?"; mobile:
bottom of the off-canvas drawer, above Log Out) both go to the PUBLIC site home (`public.home`, language-aware — `/en/`/`/es/` — via the same `url_for(..., lang=lang)` convention
every other link in this project uses; never a hardcoded domain). The logo carries an explicit accessible label ("OG Multiservices — Back to Website" / "— Volver al Sitio Web").
Session preservation needed NO new code: the marketing site and My Account already share one Flask session cookie, so browsing the public site while signed in, then clicking
"My Account" in the marketing header, returns to the dashboard without re-authenticating — verified live rather than assumed. Likewise "Get Started" on an authenticated service page
already resolves through the existing `service_public.service_cta()`, which already reads `current_student()` and swaps its label/target when a case is in progress (e.g. "Continue
Your 2025 Tax Return" straight into `/tax/start`, no login prompt) — this predates this task and needed no change, only verification. Tests: scratchpad `files_academy_suite.py`
covers the header/sidebar link markup and that returning to `/account/dashboard` after a public-site visit renders the dashboard directly; the CTA-while-authenticated behavior and
the visual logo/drawer clicks were verified live in the browser (desktop, mobile, EN, ES) rather than by an automated check, since it is fundamentally a click-through of existing,
unmodified routing.

**OG Payments (Square, sandbox) — 2026-09-22.** OG is not an e-commerce store — payments belong to a Case, an Academy course, or (for a service without its own Smart Intake yet, e.g.
Translations/Notary) a plain Case of the new `general_service` case type Admin creates the ordinary way. Square is the ONLINE PROCESSOR; the OG database (`Charge`/`PaymentRequest`/
`Payment`/`Refund`, `app/models/payments.py`, migration `1486c9978526` + `a5614f0aef99`) is the single source of truth for what a customer owes and has paid, whether that's a Square
card payment or a Zelle/cash/check/other payment Admin records manually — the two coexist on the SAME `Charge`. All money is integer cents end to end, matching this project's existing
`TaxPriceRule.amount_cents`/`DlPriceRule.amount_cents` convention — never a float.
**Three tables, deliberately not double-entry accounting** (`app/payments.py` is the whole service layer): `Charge` = what is owed for one service/course (`case_id` OR `enrollment_id`
OR `course_id` — a course purchase has no `Enrollment` yet at charge-creation time, since access only activates on a CONFIRMED payment; `total_cents` is null until priced —
"No Payment Required" is a real state, never assumed $0; `price_mode` is `none`/`estimate`/`final`, and an estimate is NEVER silently promoted to authoritative — only `set_price(...,
mode="final")`, an explicit Admin action, does that, keeping `previous_total_cents` for audit). `PaymentRequest` = one specific "please pay $X now" ask (Admin's Phase 23 "Request
Payment" — may be less than the full balance for a partial payment; only one OPEN request per charge at a time; a customer can only ever pay the SERVER-FIXED `requested_cents`, never
an amount they supply — Phase 30 amount-tampering protection is structural, not a check). `Payment` = one attempt/record, Square or manual (`method` in zelle/cash/check/
square_offline/other/square), `status` pending/completed/failed/canceled, a `receipt_number` (`OGP-000123`, same convention as `OGC-`/`OGF-`), and for Square only a
`square_payment_id`/`idempotency_key`/`card_brand`/`card_last4` — no card number or CVV is ever stored (Square's own Web Payments SDK tokenizes the card in the browser; the backend
never sees raw card data, only the token). `Refund` is a child of `Payment` — the original `Payment` row is NEVER deleted or mutated to look unpaid; a refund is its own row, so
`Payment.refunded_cents`/`net_cents` and the derived charge balance always reflect the truth.
**Balance/status are pure functions, not stored columns** (`app/payments.py balance_cents`/`paid_cents`/`status_of`): `status_of(charge)` returns one of no_payment_required / estimate
/ payment_pending / partially_paid / paid / refunded / partially_refunded / canceled, derived fresh from the actual `Payment`/`Refund` rows every time — it can never silently drift
from the authoritative records, and the browser is never trusted for it. `app/customer_status.py` gained `payment_status()` (same tone convention as `tax_status`/`dl_status`/etc.) so
wording stays consistent everywhere.
**Model A — fixed price (Academy).** `Course.price_cents` (null/0 = free, unchanged self-service `account.enroll`); a priced, published course shows "Enroll & Pay — $X.XX"
(`public/course_detail.html`) instead of the free-enroll button, going to `account.course_enroll_pay` which creates/reuses a `course_id`-linked Charge + an open PaymentRequest for the
full price, then hands off to the generic pay page. On a CONFIRMED (never pending) Square payment, `app.payments._fulfill_charge_context` calls the EXISTING
`app.academy_access.grant_access(..., access_source="paid_new_site", actor="system")` — the exact same function Admin's "Grant Course Access" uses, just a different actor/source — so
course activation, duration (`Course.access_duration_days`, never hard-coded), and everything else about Academy enrollment is completely unchanged. An already-active student is never
shown the purchase flow again (Phase 15); a revoked/expired enrollment follows the SAME renewal rules as before. Migrated-from-Wix and Admin-Complimentary grants are untouched — no
Charge is ever created for an Admin-only grant, and `grant_access`'s `actor` param (`"admin"` vs `"system"`) keeps the activity log honest about who/what triggered it.
**Model B — OG confirms price (e.g. Translations, Notary, ad-hoc services).** No new Smart Intake was built (translations/notary/apostille/etc. remain a public `Inquiry`, unchanged) —
when OG needs to charge for one of these, Admin creates an ordinary `Case` (`case_type="general_service"`, `app/case_types.py`, the same "+ New Case" action every other case type
already uses) for the customer, then a `Charge` with a plain customer-facing `description` (Admin -> Customer -> Payments tab -> "New Charge"), sets the final price, and "Request
Payment". The customer sees exactly this in My Account > Payments and Home's Action Required.
**Model C — estimate then OG confirms final price (Tax, NJ Driver License).** Reuses the intake modules' OWN pre-existing estimate/confirm architecture unchanged
(`TaxPriceQuote.final_fee_cents`/`DlPriceQuote.final_total_cents`, the SAME "Confirm fee"/"Confirm price" admin actions documented above) — OG Payments adds exactly one new action next
to it: `admin.tax_request_payment` / `admin.dl_request_payment` (`app/blueprints/admin/tax_routes.py` / `dl_routes.py`), a "Request Payment ($X)" button shown only once a price is
CONFIRMED. It finds-or-creates the case's Charge and syncs `Charge.total_cents` to the SAME confirmed fee (never a second, disconnected price) — if the confirmed price changes later,
requesting again resyncs the EXISTING Charge in place (previous amount kept for audit) rather than creating a duplicate — then opens a PaymentRequest for the current balance. An
estimate alone is never requestable (the route refuses with "Confirm the price before requesting payment.").
**Model D — balance / partial payments (immigration).** No new mechanics beyond A-C: Admin creates a Charge with the full service total, then "Request Payment" for whatever amount is
due now (never more than the current balance — Phase 23's overpayment guard). Manual and Square payments accumulate on the SAME Charge in any mix; the balance is always `total_cents -
paid_cents` computed fresh.
**Manual payments (Phase 6, Admin-only — a customer can never create one).** Admin -> Customer -> Payments -> "Record Manual Payment" (amount, method — zelle/cash/check/
square_offline/other — date, optional reference/internal note) calls `app.payments.record_manual_payment`, which marks the payment `completed` immediately (no processor round trip)
and fulfills the open PaymentRequest it's applied to, if any.
**Square integration** (`app/square_client.py`, a thin wrapper around the official `square` Python SDK / PyPI package `squareup`): `SQUARE_ENVIRONMENT`/`SQUARE_APPLICATION_ID`/
`SQUARE_ACCESS_TOKEN`/`SQUARE_LOCATION_ID`/`SQUARE_WEBHOOK_URL`/`SQUARE_WEBHOOK_SIGNATURE_KEY` (`config.py`, `.env.example` — no real values committed). Only `SQUARE_APPLICATION_ID`/
`SQUARE_LOCATION_ID` ever reach the browser (Square's own Web Payments SDK needs them to render the card form — they are not secrets); the access token and webhook key stay
server-side. A SECOND explicit opt-in, `SQUARE_ALLOW_PRODUCTION=1`, is required in addition to `SQUARE_ENVIRONMENT=production` before the client will ever build a live connection
(`square_client.get_client`) — belt-and-suspenders against a mistyped env var moving real money; see `docs/SQUARE_PRODUCTION_ACTIVATION.md`. The customer pay page
(`account/pay.html`) loads Square's Web Payments SDK (`sandbox.web.squarecdn.com` in sandbox) and tokenizes the card entirely in the browser — the token (`source_id`) is the only
card-related data that ever reaches the Flask backend, which calls Square's Payments API with it; OG never sees or stores the card number or CVV. A SANDBOX banner is shown on the pay
page whenever `SQUARE_ENVIRONMENT` isn't `production`, so a test payment can never be mistaken for a real one.
**Idempotency (Phase 8, critical).** `start_square_payment` creates a `pending` `Payment` row with a persisted `idempotency_key` BEFORE ever calling Square; every retry of that SAME
logical attempt (double-click, page refresh, network retry) reuses the identical row/key via `get_or_resume_pending_square_payment` — Square's own API guarantees a repeated
idempotency key never creates a second charge, and `confirm_square_payment` itself is a no-op once `payment.status != "pending"`. Verified live: reloading the pay page twice never
creates a second pending row; posting the charge twice in a row never creates two completed payments or two course enrollments (scratchpad `payments_suite.py`, scenario G).
**Webhooks (Phase 9).** `POST /webhooks/square` (`app/__init__.py`, no `/en//es/` prefix and no student session — Square calls this server-to-server) verifies Square's HMAC-SHA256
signature (`square_client.verify_webhook_signature`, Square's documented `base64(HMAC-SHA256(signature_key, notification_url + raw_body))` scheme — implemented directly against
stdlib `hmac`, since the installed SDK version doesn't expose a signature-verification helper) against `SQUARE_WEBHOOK_URL` before touching any data; an unverifiable request is
rejected with 401 before parsing. `app.payments.handle_square_webhook_event` is a thin dispatcher that finds the matching `Payment`/`Refund` row by `square_payment_id`/
`square_refund_id` and calls the SAME `_apply_square_payment` the synchronous confirm path uses — so a webhook is never the ONLY way a payment resolves (the customer's own request
already does it), only a safety net, and duplicate delivery is a proven no-op (re-applying an already-`completed` payment changes nothing; verified in `payments_suite.py`).
`app.payments.reconcile_payment` (Admin "Check Square" button on a pending Square payment) is the Phase 38 manual reconciliation path — it asks Square directly via `GET
/v2/payments/{id}` and applies the SAME idempotent logic, never marking something paid without asking the processor first.
**Refunds (Phase 13).** Admin -> Payments -> a completed payment -> "Refund" (amount, reason). A Square payment calls Square's Refunds API with a fresh idempotency key and records a
`pending` `Refund` that a later webhook (or "Check Square") settles to `completed`; a manual payment's refund is pure bookkeeping (no processor call) and completes immediately. Either
way the original `Payment` row is untouched — `Payment.refunded_cents`/`net_cents` and the Charge's derived balance recompute correctly for both full and partial refunds (verified:
a $175 refund on a $200+$175 charge correctly drops paid back to $200, not $0; a $30 refund on a $100 payment leaves a $70 net).
**My Account > Payments** (`app/blueprints/account/payments_routes.py`, `app/payments_dashboard.py`, sidebar item between Files from OG and Messages — EN "Payments"/ES "Pagos"):
"Amount Due" summary, "Payments Needed" (Total/Paid/Balance + "Make a Payment" per payable Charge — only charges with an OPEN PaymentRequest ever show a Pay button, matching Phase 17's
own example exactly), and "Payment History" (date/service/amount/status/method, card payments show "Visa •••• 4242"-style safe metadata, never a Square internal ID) with a
receipt page per payment (`account/payment_receipt.html`). `Charge.display_title(lang)` is the one place the customer-facing title is decided: a course purchase shows the REAL
bilingual `Course.title(lang)` (never the English name duplicated next to its own Spanish translation — a real bug caught and fixed during EN/ES verification); every other charge
shows Admin's own `description` (English-only, the same convention as every other admin-authored customer-facing label in this project, e.g. Document Vault requirement titles).
Home's Action Required gets one row per payable charge, deep-linking straight to that exact payment with a "Pay Now"/"Pagar Ahora" verb (`payments_dashboard.action_items`, merged into
`account_dashboard.home_data` ahead of every other action) — never a generic link to Payments when an exact target exists.
**Admin** (`app/blueprints/admin/payments_routes.py` + the customer "Payments" tab in `admin/student_detail.html`, `CUSTOMER_TABS`): New Charge, Set/Confirm Price, Request Payment,
Record Manual Payment, Refund (with a "Check Square" reconciliation action on a still-pending Square payment), Cancel Charge — every action requires `@admin_required` and re-derives
the charge/payment from the DB rather than trusting anything but its own id in the URL. IDOR is enforced identically to every other customer-owned record in this project:
`owned_charge`/`owned_request`/`owned_payment` in `payments_routes.py` check `.customer_id` against the signed-in student before returning anything, and every admin route is
`@admin_required`-gated — verified with a dedicated stranger/non-admin test pass.
**Activity/audit.** Reuses the EXISTING `app.activity.log_event`/`ActivityEvent` mechanism — no new audit table. New event types (`payment_price_confirmed`/`_estimated`/`_changed`,
`payment_requested`, `payment_request_canceled`, `square_payment_initiated`, `payment_completed`, `payment_failed`, `manual_payment_recorded`, `payment_refunded`/
`_partially_refunded`, `refund_failed`, `course_activated_from_payment`) in a new `"payments"` filter group; sensitive card data is never logged, only amount/method/service.
**Notifications.** No new notification system — matches this project's existing "notifications are logged, not sent" state (see Known limits); a real payment-confirmation/failure
email is future work once an email transport exists, same as every other notification in this project today.
**Tests.** Scratchpad `payments_suite.py` (51 checks: fixed-price Academy purchase + real activation + no-card-data-stored, duplicate-purchase prevention, idempotent double-click/
double-POST, balance math across mixed manual+Square payments, amount-tampering rejection, customer/admin IDOR, a declined card leaves the balance untouched, webhook idempotency,
full and partial refunds with correct balance recalculation, Wix-migration/Admin-Complimentary grants unaffected) and `payments_tax_dl_suite.py` (10 checks: a REAL submitted NJ DL
case through Confirm Price -> Request Payment -> the Charge matches the confirmed price exactly -> a later price change resyncs the SAME Charge, never a duplicate -> the customer
sees the updated amount, not the stale one). Square itself is mocked at the `app.square_client` boundary (no real network calls/credentials needed for deterministic testing);
everything above that boundary — idempotency, balance math, status derivation, IDOR, Academy activation, webhook handling — runs for real against the actual routes and database.
Full regression: the complete pre-existing suite (`dl_suite`/`tax_suite`/`tax_suite2`/`reopen_suite`/`acct_suite`/`acct_suite2`/`files_academy_suite`/`e2e_person`/`e2e_i485a`, 507
checks) plus the new payments suites (61 checks) — 568 total, zero regressions.
**Not built (Phase 48, explicitly out of scope):** a Wix payment migration/importer, a stored-card vault (Square tokenizes per-transaction only, nothing is saved for reuse), consumer
financing/installment credit, double-entry accounting, a new notification system, subscriptions. Live production Square was NOT activated during this task — see
`docs/SQUARE_PRODUCTION_ACTIVATION.md` for the exact remaining steps. Real Square Sandbox credentials were not available during this task, so the actual card-tokenization round trip
through Square's hosted card form could not be exercised live in a browser; the page correctly shows "Online payment is not available right now" when Square is unconfigured
(verified live) rather than a broken page, and every business-logic path above that boundary is covered by the automated suites instead.

**Transactional Email system (2026-09-22, MAIL_ENABLED off — real delivery NOT activated).** One reusable seam, `app.email_service.send_transactional_email(...)`, that every business
event across the whole app calls through — never raw SMTP calls scattered through route handlers. Transport is stdlib `smtplib`/`email.mime` (`app/mailer.py`, zero new dependency) over
Titan/Bluehost SMTP (`smtp.titan.email:465`, implicit TLS); synchronous with a bounded 10s socket timeout — the simplest reliable architecture for this project's single-server Flask
deployment, per explicit instruction not to introduce Redis/Celery/etc.; the one seam to swap later if volume ever demands a background worker. **Contract every caller relies on: this
function never raises** — a payment, a document upload, a case status change all succeed or fail on their own merits, email is always a side effect.
**Two governance/config layers, mirroring the Square sandbox/production pattern.** `MAIL_ENABLED` (default off) is the master dev-safety switch: unset, every code path still runs and
still creates an `EmailLog` row (so you can see what *would* have gone out), but the actual SMTP call is skipped and the row is recorded `failed` with a clear, honest reason — never a
silent no-op. `MAIL_DEV_REDIRECT_TO` (optional, non-production only) redirects the real SMTP envelope to a developer's own inbox while `EmailLog` still shows the true intended recipient.
`config.py.validate_for_production()` refuses to start if `APP_ENV=production` and `MAIL_ENABLED=1` but `SMTP_USERNAME`/`SMTP_PASSWORD` are missing or `APP_PUBLIC_URL` still looks like
localhost. See `docs/TRANSACTIONAL_EMAIL_SETUP.md` for the exact `.env` variables and the first-SMTP-test procedure.
**Templates, two shapes** (`app/email_templates.py`, `app/email_render.py` for the shared layout `templates/emails/base.html` + plain-text fallback, one EN/ES-aware `EmailContent`
dataclass, never two separate business objects per language). DIRECT templates (`email_verification`, `password_reset`, `email_changed`) carry a secret or a moment-in-time value that
must never be persisted — built once by the caller and passed via `send_transactional_email(..., content=...)`; not in the `TEMPLATES` registry and not retryable (a stale code/link is
never safely resent — the customer requests a fresh one). REGISTRY templates (`service_submitted`, `info_needed`, `document_needed`, `document_replacement`, `service_completed`,
`file_available`, `payment_requested`, `payment_received`, `refund_processed`, `course_access`, `certificate_available`) are looked up by `template_key` and rebuilt from a small `ref`
dict of safe reference ids (e.g. `{"payment_id": 5}`) — never rendered content, never extra PII — so Admin's Retry button is generic and safe, and a retry always reflects CURRENT data.
`dedupe_key` (optional) prevents two code paths for the SAME logical event (e.g. Square's webhook and the synchronous confirm both completing the same payment) from sending twice.
**Delivery ledger** (`EmailLog`, migration `e7c1a4f902b3`): recipient, template_key, language, subject, `related_type`/`related_id`, `ref_json` (safe ids only — see above), status
(pending/sending/sent/failed), attempt_count, timestamps, failure_reason. Never stores a verification code, a reset token, or the SMTP password. A successful/failed send also logs
through the EXISTING `app.activity.log_event` (`email_sent`/`email_failed`) so it appears in the customer's own Activity tab, same mechanism as every other event in this project.
**Mandatory email verification** (`app/verification.py`, models `EmailVerificationCode`/`Student.email_verified_at`, migration `e7c1a4f902b3`): a cryptographically secure
(`secrets.randbelow`) 6-digit code, hashed with the SAME slow hash used for passwords (`werkzeug.security`, appropriate for a low-entropy secret) — never stored in plaintext. Expires
10 minutes; max 5 attempts per code (a 6th wrong guess invalidates it); issuing a new code always invalidates the previous one; resend cooldown 60s, cap 5/hour; a separate 10-attempts-
per-15-minutes rate limit via the EXISTING `app.ratelimit.allow()` (defense in depth beyond the per-code counter). Enforced at ONE choke point: `app.student_auth.student_required` —
already used by every protected route in the app (My Account, Academy, the NJ Knowledge Test, every service intake) — redirects an unverified student to `/account/verify-email?next=...`,
preserving the original destination via the SAME `next=`/`_safe_next` pattern login already used. The verify-email/forgot-password/reset-password screens render the ORDINARY marketing
header (`base.html`'s `_is_acct_shell` now also requires `student.is_email_verified`), not the full My Account shell — an unverified account never sees an "Action Required" badge or a
profile menu implying it already has access; a verified account's OWN mid-flow pages (e.g. Profile → Change Email) still get the full shell as normal. The masked-email UI ("m•••••@…")
is `app.email_render.mask_email`.
**Existing-user migration strategy (item 20, documented, not fabricated):** the migration backfills `email_verified_at` for every account that existed BEFORE this feature shipped to the
migration's OWN run timestamp — an honest "grandfathered as of this deployment" — never a fabricated claim that they verified at registration (which didn't exist for them). Only
accounts created AFTER the migration go through the real 6-digit flow. `AdminUser` is a completely separate table/login system, structurally unaffected.
**Change email** (`app/blueprints/account/verify_routes.py verify_email_change` / `verify_email_pending_change`) is ONE shared flow reused by two entry points that differ only in where
`next` sends them afterward: item 6 ("Change Email" link on the verify screen itself, fixing a mistyped address before ever verifying) and item 7 (Profile & Settings → Change Email, for
an already-verified customer — `account/profile.html`, `next=url_for('account.profile', lang=lang)` passed explicitly). Either way the OLD email stays the account's verified email until
the NEW one is confirmed by code; on success the account replaces its email and stays verified, and a security-notice email (`email_changed`, template shape DIRECT) goes to the OLD
address, never the new one (the new address already got the code).
**Password reset** (`app/password_reset.py`, `app/blueprints/account/password_routes.py`) — a brand-new flow; none existed in this project before. `secrets.token_urlsafe(32)` (256 bits),
SHA-256-hashed for lookup (appropriate for a high-entropy token, unlike the 6-digit code), 30-minute expiry, single-use, requesting a new one invalidates any outstanding token. Only ever
sent to an account whose email is ALREADY verified. `forgot_password()` always shows the identical "If an account exists…" response regardless of outcome — no code path distinguishes a
real account from a non-existent one (enumeration protection, item 8) — and never reveals or emails the old password.
**Connected events (11 registry templates, all wrapped in try/except at the call site so email can never break the underlying transaction):** `app.forms_engine.queue_form_notifications`
(the pre-existing, self-documenting hook — its docstring literally described this task; now sends `service_submitted` for any signed-in customer's Smart Intake) and the generic
`admin.form_submission_request_info` route (`info_needed`); `app.tax.service.submit/request_info/set_status` and `app.driver_license.service.submit/request_info/set_status` (same
three, Tax/DL are dedicated modules on the SAME Case architecture, not the FormSubmission engine); the generic `admin.ocase_status` route's completed transition (`service_completed`);
`app.case_documents.create_requirement`/`request_replacement` (`document_needed`/`document_replacement`); `app.customer_files.publish`/`create(publish=True)` (`file_available`);
`app.payments.request_payment`/`_apply_square_payment`/`record_manual_payment`/`refund_payment` + the webhook refund-completion branch (`payment_requested`/`payment_received`/
`refund_processed` — the refund hook covers BOTH the synchronous and webhook-driven completion paths, closing a gap the Square phase's own docs had flagged); `app.academy_access.
grant_access` (`course_access`, for created/renewed/restored — never for an already-active no-op); `app.progress.get_or_create_certificate` (`certificate_available`, only on first
creation). Admin-to-staff notification emails (the pre-existing `Form.notify_admin_enabled` toggle) were deliberately left as a log-only stub — not one of the 14 customer-facing emails
in the spec's catalog, and Admin already has first-class visibility via Admin → Applications; wiring it is still just swapping that one branch later.
**Admin** (`app/blueprints/admin/email_routes.py`): a customer's own "Emails" tab (`CUSTOMER_TABS`, `admin/student_detail.html`) shows that customer's send history with a Retry action on
any failed row; Admin → System → **Emails** is a small cross-customer troubleshooting list (status filters, same Retry); Admin → System → **Test Email** is the Admin-only SMTP
connectivity test (item 16) — sends a clearly-labeled "OG TEST EMAIL" to an Admin-chosen recipient, records success/failure the same way as everything else, never exposes SMTP
credentials, not a public endpoint. Nothing in Admin ever displays a verification code, a reset token, or the SMTP password.
**Not built (explicitly out of scope, matching the spec's non-goals):** newsletters, marketing automation, mailing lists, promotional campaigns, SMS/WhatsApp automation, SendGrid/
Mailgun/AWS SES integration, a customer email inbox, open/click tracking, unsubscribe management (these are service/account transactional emails, not marketing). Live SMTP delivery was
NOT activated during this task (`MAIL_ENABLED` unset everywhere) — see `docs/TRANSACTIONAL_EMAIL_SETUP.md` for the exact remaining steps Marcos must take with the real Titan mailbox
password. Tests: scratchpad suite (54 checks: registration → verify → dashboard, wrong/expired/max-attempts/reissued codes, resend cooldown, grandfathered accounts, password reset
including enumeration protection and single-use tokens, dedupe, retry (including the DIRECT-template refusal), masking, EN/ES content divergence, admin IDOR, HTML+text rendering) plus a
second regression pass (8 checks: existing verified customers still reach every My Account page, admin login/routes unaffected, Square webhook signature rejection unchanged) — zero
regressions against the pre-existing app. Every customer-facing screen (register → verify-email, forgot-password, reset-password, change-email) was also walked through live in the
browser in both English and Spanish and at mobile width, including a full change-email round trip that correctly moved the account to the new address and emailed a security notice to
the old one.

**Rule semantics changed:** several `show_field` / `show_page` rules aimed at one target combine
with OR (server `forms_engine` + browser `og_form.js`), so "A and B, or C" = one rule per AND-group.

**My OG Account (legacy notes, superseded above)** (`account/portal_routes.py`, `account/routes.py`): Overview, My Applications
(+detail, snapshot-based, sensitive values masked), My Documents (owner-only download, no public
URL), My Courses (Academy untouched), Profile (name/phone/language/password). One identity for
Academy and applications. `_safe_next` keeps sign-in returns same-site only.

**Admin customers** (`admin/routes.py student_detail`): tabs Overview / Applications / Documents /
Courses (existing Academy tools) / Activity (filters) / Notes (`CustomerNote`, never shown to the
customer). Application review = `admin/forms_routes.py form_submission_detail`: version and
edition, progress, grouped answers with source refs, documents via `/admin/files/<id>`, status
change, "Request information" (customer-visible `SubmissionNote` + Waiting for Client), internal
notes. Activity = `activity.py` (`ActivityEvent`, `log_event`, `describe`, `timeline`): meaningful
events only, never page views or field values.

**Known limits:** no PDF/Part 14 export yet (answers are stored per question); real email transport now exists (see "Transactional Email system" above) but is NOT activated (`MAIL_ENABLED` unset — see `docs/TRANSACTIONAL_EMAIL_SETUP.md`), so no customer has actually received an email yet outside this session's live-browser tests,
no field-level encryption at rest for SSN/A-Number (masked in the customer UI, plain in DB; the Tax Return's refund bank details are the one exception — encrypted via `app/secure_store.py`),
in-process rate limiter, no payments (including tax preparation fees — `TaxCaseData.payment_status/payment_reference` are placeholders, no gateway is connected;
`DlCaseData.payment_status/payment_reference` are the same placeholders for Driver License services). The Tax Return terms/certification text (`app/tax/terms.py`) is OG's own
working draft and has not had legal review; so is the Driver License terms text (`app/driver_license/terms.py`). The Driver License rules engine (`app/driver_license/rules.py`)
and the Knowledge Test question bank (`app/driver_license/seed_questions.py`) both carry explicit SOURCE NOTE caveats — no official NJ MVC 6-Point document or Driver Manual was
supplied this session, so their specifics are OG's own understanding, not verified against a primary source; see the "NJ Driver License Assistance" section above.

**OG Academy** is a separate, untouched LMS (NJ Notary course, quizzes, certificates, QR
verification, Forensic Training demo). The abandoned Citizenship/N-400 practice system was
removed on 2026-09-18 (archive: `backups/2026-09-18_pre_redesign/`).

**Migrations are additive** except the Citizenship removal (`a1c0de5e0001`). Never seed over
production data; the seeders are guarded to run only on an empty table.
