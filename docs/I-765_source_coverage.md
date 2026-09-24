# Form I-765 Smart Intake — source coverage audit

**Source of truth:** the supplied USCIS *Form I-765, Application for Employment Authorization*, **Edition 08/21/25** (OMB No. 1615-0040, expires
08/31/2027), **7 pages**, Parts 1–6 (`Downloads/i-765.pdf`). Nothing here comes from memory or from another edition. Item numbers are the ones
printed on that PDF (for example the printed “Other Names Used” boxes 2.a–4.c sit beside Part 1 on page 1 but are **Part 2 Items 2–4**, because Part 2
Item 1 is the full legal name).

Intake: `app/seed_i765.py` (form `i-765-client-intake`, source form `I-765`, edition `08/21/25`; services *Employment Authorization (Form I-765)
Preparation* and the existing *Work Permit (EAD) Renewal*). Every question stores its Part/Item in `FormField.source_ref` (admin-only); customers never see
part/page/item numbers. Tests: `e2e_i765a`–`c` and `verify_cov765` (session scratchpad).

## Status vocabulary

| Status | Meaning |
|---|---|
| **COLLECTED** | the customer answers it, or reviews a value OG already knows for that real Person and confirms/edits it (`reuse`), or a central-configuration default (OG's preparer/interpreter details) is stored as an answer |
| **CONDITIONAL** | collected only when an earlier answer makes it applicable |
| **DERIVED** | never asked: calculated from other answers, read from central configuration, or generated (Part 6 entries) |
| **SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE** | a signature or the date of that signature. The intake never signs, e-signs or certifies for anyone; “Send to OG” is not the USCIS signature |
| **NOT APPLICABLE TO SMART INTAKE** | not a customer-information item (USCIS-use boxes, G-28 box, page/part/item cross-references OG assigns) |

A Part/Item is covered only when a field, calculation or explicit rule implements it (`verify_cov765.py`: every non-signature item of Parts 1–5 is named by a
field; the three signature items are named by none).

## Part 1 — Reason for applying

| Item | Field | Status |
|---|---|---|
| 1.a Initial permission to accept employment | `r_reason` = `1a` | COLLECTED (radio card; never inferred from OG history) |
| 1.b Replacement of lost, stolen, or damaged EAD, or correction NOT DUE to USCIS error | `r_reason` = `1b`; help text (`r_note_1b`) shown only for 1.b | COLLECTED; document request `i765.replaced_ead` (OG workflow) |
| 1.c Renewal (attach a copy of your previous EAD) | `r_reason` = `1c`; help text (`r_note_1c`) | COLLECTED; document request `i765.prior_ead` (basis: **stated on the official form**) |

## Part 2 — Information about you

| Item | Field(s) | Status |
|---|---|---|
| 1.a–1.c Full legal name | `a_family`, `a_given`, `a_middle` (block `sb_identity`) | COLLECTED (reuse: “We already have {name}'s identity information” → confirm / edit; edits update the same real Person) |
| 2–4 Other names used (three name boxes each 2.a–4.c) | `a_other_names` records (block `sb_othernames`) | COLLECTED (reuse); names 4+ → DERIVED Part 6 entry at Page 1, Part 2, Item 4 |
| 5.a–5.f U.S. mailing address (In Care Of, street, unit, city, state, ZIP) | `ml_*` | CONDITIONAL (only when Item 6 = No; otherwise the mailing address is the physical one — DERIVED placement) |
| 6 Mailing address same as physical? | `m_same` | COLLECTED |
| 7.a–7.e U.S. physical address | `ph_*` (block `sb_address`; situational: “Is this still where you live?”) | COLLECTED (reuse; a foreign or older address is never offered as the U.S. address) |
| 8 A-Number | `a_anumber` (block `sb_ids`) | COLLECTED (reuse, optional, masked in summaries) |
| 9 USCIS Online Account Number | `a_uscis_account` (block `sb_ids`) | COLLECTED (reuse, optional) |
| 10 Sex | `a_sex` (block `sb_identity`) | COLLECTED (reuse) |
| 11 Marital status (Single / Married / Divorced / Widowed) | `a_marital` (block `sb_marital`; situational: “Marital status can change. Is this still correct?”) | COLLECTED (reuse; a stored value this form has no option for — e.g. “separated” — is never offered; never inferred from an I-130) |
| 12 Have you previously filed Form I-765? | `p_prior` | COLLECTED — **always asked**, never pre-answered or derived from OG's records. OG's own I-765s are shown only as context (`prior_card`) |
| 12 (Yes) extra detail | `p_prior_details` (OG helper, optional) | CONDITIONAL → DERIVED Part 6 entry at Page 2, Part 2, Item 12; document request `i765.prior_notices` (basis: answer) |
| 13 Social Security number (if known) | `a_ssn` (block `sb_ids`) | COLLECTED (reuse, optional, sensitive, masked) |
| 14.a Country of citizenship or nationality | `a_citizenship` (block `sb_identity`) | COLLECTED (reuse) |
| 14.b Second country | `a_more_countries`, `a_countries_more` records | CONDITIONAL; countries 3+ → DERIVED Part 6 entry at Page 2, Part 2, Item 14.b |
| 15.a City/town/village of birth | `a_birth_city` (block `sb_identity`) | COLLECTED (reuse) |
| 15.b State/province of birth | `a_birth_state` (block `sb_identity`) | COLLECTED — when the rest of the birthplace is known, ONLY this missing detail is asked (`sb_identity_missing`) |
| 15.c Country of birth | `a_birth_country` | COLLECTED (reuse) |
| 16 Date of birth | `a_dob` | COLLECTED (reuse) |
| 17 Form I-94 number (if any) | `a_i94_number` (block `sb_arrival`) | COLLECTED (reuse, optional); document request `i765.i94` (shares the I-485's request when one exists) |
| 18 Passport number of the most recently issued passport | `a_passport` (block `sb_docs`) | COLLECTED. A “passport OR travel document at last arrival” from another application (I-485 Item 10) is a *different concept*: it is offered only after the applicant says which it is (`d_kind`) |
| 19 Travel document number (if any) | `a_travel_doc` | COLLECTED (kept separate from Item 18) |
| 20 Country that issued the passport or travel document | `a_doc_country` | COLLECTED |
| 21 Expiration date for passport or travel document | `a_doc_expiry` | COLLECTED |
| 22 Date of last arrival | `a_arr_date` (block `sb_arrival`) | COLLECTED (reuse, situational) |
| 23 Place of last arrival | `a_arr_place` | COLLECTED (reuse; composed from the I-485's city + state) |
| 24 Immigration status at last arrival | `a_arr_status` | COLLECTED (reuse of the class of admission) |
| 25 Current immigration status or category | `a_current_status` | COLLECTED (reuse only if stated; an empty answer elsewhere is never read as “unchanged”) |
| 26 SEVIS number (if any) | `has_sevis`, `a_sevis` | CONDITIONAL (asked as Yes/No; the number only when Yes; never derived) |
| 27 Eligibility category | `e_known`, `e_cat_a`, `e_cat_b`, `e_cat_c` (the three printed boxes) | COLLECTED exactly as given, or “Not sure — OG will review”. Syntax validated (letter, number, optional third part); never decided, suggested (configuration hook `CATEGORY_SUGGESTIONS` is empty) or derived |
| 27 normalized text / branch | `c_category`, `c_branch` | DERIVED (`i765_calc`): `(c)(3)(C)`; which of Items 28–31 apply |
| 28.a Degree | `x_degree` | CONDITIONAL — only when Item 27 is exactly `(c)(3)(C)` |
| 28.b Employer's name as listed in E-Verify | `x_everify_name` | CONDITIONAL — `(c)(3)(C)` |
| 28.c E-Verify Company ID or valid E-Verify Client Company ID | `x_everify_id` | CONDITIONAL — `(c)(3)(C)` |
| 29 Receipt number of H-1B spouse's most recent I-797 (Form I-129) | `x_c26_receipt` | CONDITIONAL — `(c)(26)`; document request `i765.c26_notice` (OG workflow) |
| 30 Ever arrested and/or convicted of any crime? | `x_c8_arrest` (+ optional `x_c8_details`) | CONDITIONAL — `(c)(8)`. A Yes only flags the application for OG review and creates a “court dispositions — OG will tell you what is needed” request (basis: answer); no eligibility statement |
| 31.a (c)(35) receipt number of Form I-797 for Form I-140 | `x_c35_receipt` | CONDITIONAL — `(c)(35)` only |
| 31.a (c)(36) receipt number of spouse's/parent's Form I-797 for Form I-140 | `x_c36_receipt` | CONDITIONAL — `(c)(36)` only (a separate field: the two are never merged) |
| 31.b Ever arrested and/or convicted? | `x_c3536_arrest` (+ optional `x_c3536_details`) | CONDITIONAL — `(c)(35)` or `(c)(36)`; same handling as Item 30 |

## Part 3 — Applicant's statement, contact information, certification, signature

| Item | Field | Status |
|---|---|---|
| NOTE read the Penalties section / must file while in the U.S. | help text of `s_statement` | shown (DERIVED text, not a question) |
| 1.a / 1.b Statement (English / interpreter) | `s_statement` | COLLECTED (no default; an interpreter is never assumed) |
| 2 Preparer prepared this application at my request | `preparer_request` | COLLECTED (customer request only) |
| 3 Daytime telephone | `a_phone` (block `sb_contact`) | COLLECTED (reuse, situational) |
| 4 Mobile telephone | `a_mobile` | COLLECTED (reuse, optional) |
| 5 Email | `a_email` | COLLECTED (reuse, optional) |
| 6 ABC settlement agreement box | `a_abc` (Yes / No / Not sure) | CONDITIONAL — asked only when a country of citizenship or birth reads as El Salvador or Guatemala (`c_abc_rel`); never concluded; Yes/Not sure flagged for OG review |
| Applicant's Certification (all paragraphs, biometrics oath, NOTE TO ALL APPLICANTS) | `cert_1`–`cert_4`; `c_cert_ack` | shown verbatim in English (Spanish = OG courtesy translation); `c_cert_ack` is an acknowledgment only. The certification itself is **SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE** |
| 7.a Applicant's signature | — | **SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE** |
| 7.b Date of signature | — | **SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE** (belongs to the act of signing) |

## Part 4 — Interpreter (only when Part 3 Item 1.b is chosen)

| Item | Field | Status |
|---|---|---|
| 1.a / 1.b Interpreter's family / given name | `int_family`, `int_given` | CONDITIONAL (defaults from `business_info.INTERPRETER_*`, the same mechanism as every other intake) |
| 2 Business or organization | `int_org` | CONDITIONAL |
| 3.a–3.h Mailing address (street, unit, city, state, ZIP, province, postal code, country) | `int_*` | CONDITIONAL (defaults `OFFICE_*`) |
| 4 / 5 / 6 Daytime phone / mobile / email | `int_phone`, `int_mobile`, `int_email` | CONDITIONAL |
| Certification: “fluent in English and [language]” | `int_language` (also Part 3 Item 1.b) | CONDITIONAL — language collected; the certification (`int_cert`, shown verbatim) is **SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE** |
| 7.a / 7.b Interpreter's signature and date | — | **SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE** |

Switching Part 3 back to “I can read and understand English” removes the interpreter answers.

## Part 5 — Preparer (OG)

| Item | Field | Status |
|---|---|---|
| 1.a / 1.b Preparer's name | `prep_family`, `prep_given` | COLLECTED (defaults `business_info.PREPARER_*`) |
| 2 Business or organization | `prep_org` | COLLECTED (default `PREPARER_ORG`) |
| 3.a–3.h Mailing address | `prep_*` | COLLECTED (defaults `OFFICE_*`) |
| 4 / 5 / 6 Phone / mobile / email | `prep_phone`, `prep_mobile`, `prep_email` | COLLECTED (defaults `PREPARER_*`) |
| 7.a I am not an attorney or accredited representative… / 7.b I am an attorney or accredited representative… (extends / does not extend) | `prep_status`, `prep_extends` (`business_info.PREPARER_STATUS`, `PREPARER_REPRESENTATION_EXTENDS`) | **DERIVED** from central configuration — never a customer answer and never defaulted to attorney/accredited status (OG is not a law firm: `not_attorney` → 7.a) |
| Preparer's Certification | `prep_cert` (shown verbatim) | **SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE** |
| 8.a / 8.b Preparer's signature and date | — | **SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE** |

## Part 6 — Additional information

| Item | Field | Status |
|---|---|---|
| 1.a–1.c Name and 2 A-Number (top of the sheet) | from Part 2 | DERIVED |
| 3–7 Page / Part / Item / text entries | `c_addl` (generated) + `additional_information` (free text) | **DERIVED**: entries are generated automatically when structured answers exceed the printed space (other names 4+, countries 3+) or carry extra text (previous-I-765 details, arrest details, the applicant's own note); each keeps Page/Part/Item; Admin reviews them in the I-765 panel. The customer is never asked for a page, part or item number |
| more than five entries | — | NOT APPLICABLE TO SMART INTAKE (OG attaches a separate sheet when transcribing) |
| “sign and date each sheet” | — | **SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE** |

## Front matter and boxes

| Element | Status |
|---|---|
| “For USCIS Use Only” blocks (Authorization/Extension Valid From/Through, Fee Stamp, Action Block, Remarks, A-Number box) | NOT APPLICABLE TO SMART INTAKE |
| “To be completed by an Attorney or Accredited Representative” box (Form G-28 attached, State Bar Number, USCIS account) | NOT APPLICABLE TO SMART INTAKE (OG is not a law firm) |

## Reuse, provenance and case behaviour (not form items)

* **Case compatibility:** `FORM_CASE_CONFIG["I-765"]["case_types"]` = `employment_authorization` (its own case) and `adjustment_of_status`. It is not architected as “always part of an AoS package”: with no compatible case it creates an employment-authorization case; it joins an existing AoS case only by the customer's explicit choice in the setup step (source context is shown: the case's other applications). Family-petition, naturalization and every other case are neither offered nor accepted.
* **Applicant:** the customer's existing real Person (offered “Already in this case” / “Already in your other cases”) or a new one; the same Person as an I-130 beneficiary / I-485 applicant. A petitioner-only person is not offered. A second I-765 for the same person is allowed (initial then renewal); only an unfinished draft blocks another.
* **Reuse through the Person layer**, never direct copying of another application's fields: stable facts (name, birth, sex, citizenship, A-Number, USCIS account, SSN) → reuse + confirm; situational facts (address, marital status, arrival, I-94, status, contact) → shown with their date and “Is this still current?”; conflicts use the existing `/conflicts` step. Explicit mappings added for the I-485 (place of last arrival composed from city + state; status; document facts) and N-400 (marital status). The I-485's *passport-or-travel-document at last arrival* is stored under its own fact keys (`arrival_document_*`) and used only after the applicant identifies the document.
* **Smart Start** (`smart_start` step): a compact “We already have most of your information” summary (Name ✓, Date of birth ✓, Birthplace ✓, Citizenship ✓, A-Number ✓, Address ✓, Last U.S. arrival ✓ …) before the per-group confirmations; after “correct” only the details the person's data cannot supply are asked.
* **Documents:** Case Document Vault only (`app/i765_docs.py`): each request carries its basis (*stated on the official form* / *OG workflow* / *triggered by an answer*); the passport and I-94 requests are shared with an existing I-485 request instead of duplicated; requests of every active I-765 in a case are computed together. The Form I-765 Instructions are not in the supplied PDF, so no request claims USCIS requires anything beyond what the form itself says.
* **Consistency prompts** (`app/i765_checks.py`, “please review”, never a conclusion): malformed category, “not sure” category, arrest/conviction Yes, ABC yes/not sure, replacement/renewal with “never filed”, missing passport/travel document, dates in the future, expired passport.

## Known limits

* The Form I-765 Instructions (Who May File, required documents, court dispositions) were not supplied: nothing is built from them, and no category-to-case suggestion is configured.
* No signature, e-signature or certification is executed or collected (Parts 3, 4, 5, 6).
* The Spanish is OG's translation (courtesy only) for the certification and certification-like text; English is official.
* No PDF/official-form export.
