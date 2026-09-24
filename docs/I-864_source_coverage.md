# Form I-864 Smart Intake — source coverage audit

**Source of truth:** the supplied USCIS *Form I-864, Affidavit of Support Under Section 213A of the INA*, **Edition 08/24/26**
(OMB No. 1615-0075, expires 10/31/2027), 12 pages, Parts 1–11 (`Downloads/i-864.pdf`). Nothing here comes from memory or from another
edition. Item numbers are the ones printed on that PDF.

Intake: `app/seed_i864.py` (form `i-864-client-intake`, source form `I-864`, edition `08/24/26`, *Affidavit of Support* service, Immigration).
Every question stores its Part/Item in `FormField.source_ref` (admin-only); customers never see part/page/item numbers.

## Honest status vocabulary

| Status | Meaning |
|---|---|
| **COLLECTED** | the customer answers it (or reviews a value already known for that real Person and confirms/edits it), or a customer-facing default from central OG configuration is stored as an answer |
| **CONDITIONAL** | collected only when an earlier answer makes it applicable |
| **DERIVED** | never asked: the platform calculates it from other answers (arithmetic) or reads it from the existing case/Person data |
| **NOT COLLECTED — SIGNATURE EXECUTION** | a signature or the date of that signature. This intake never signs, e-signs or certifies for anyone; OG explains how and when each person signs |
| **NOT APPLICABLE TO SMART INTAKE** | not a customer-information item (USCIS-use boxes, attorney box, page/part/item cross-references OG assigns when transcribing) |

A Part/Item is listed as covered only when a field, calculation or explicit rule implements it (verified by the tests in *Verification* below).
“Send to OG” is never the USCIS signature, an e-signature or the sponsor's certification.

## What this pass found (Parts 8–10)

Earlier wording said every printed Part and Item was mapped, while also saying Part 10 data was “not collected”. That was inconsistent:
Part 10 Items 1–5 (preparer name, organization, telephone, mobile, email) are **information OG needs to prepare the form**, not a signature.
They are now collected (Part 10 page, defaults from `business_info.PREPARER_*`). Every signature and date of signature stays
NOT COLLECTED. Nothing else in Parts 8–10 was missing: Part 8 Items 1–5 and Part 9 Items 1–5 were already collected.

## Part 1 — Basis for filing

| Item | Field(s) | Status |
|---|---|---|
| 1.a Petitioner | `b_basis` = `1a` | COLLECTED |
| 1.b Alien worker petition, related as my … | `b_basis` = `1b`, `b_1b_rel` | COLLECTED (relationship CONDITIONAL on 1.b) |
| 1.c ≥5 % owner, business name, related as my … | `b_basis` = `1c`, `b_1c_business`, `b_1c_rel` | COLLECTED (follow-ups CONDITIONAL on 1.c) |
| 1.d Only joint sponsor | `b_basis` = `1d` | COLLECTED; adds the `joint_sponsor` role to the sponsor Person; flagged for OG review, no conclusion |
| 1.e First / second of two joint sponsors | `b_basis` = `1e`, `b_1e_which` | COLLECTED (which one CONDITIONAL on 1.e); `joint_sponsor` role |
| 1.f Substitute sponsor, the intending immigrant's … | `b_basis` = `1f`, `b_1f_rel` | COLLECTED (relationship CONDITIONAL on 1.f); `substitute_sponsor` role |
| (OG helper) “Not sure” | `b_basis` = `unsure` | workflow flag for OG review, not a form item |
| NOTE proof of status | `b_proof_note`; document request `i864.sponsor_status` | DERIVED (shown + document request, basis *stated on the official form*) |

## Part 2 — Sponsor

| Item | Field(s) | Status |
|---|---|---|
| 1 Full legal name | `s_family`, `s_given`, `s_middle` (block `sb_s_name`) | COLLECTED (reuse: asked once for the real Person, then confirmed) |
| 2 Current mailing address | `sm_*` | CONDITIONAL (only when Item 3 = No) |
| 3 Mailing = physical? | `s_mail_same` | COLLECTED |
| 4 Physical address | `sp_*` (block `sb_s_address`) | COLLECTED (reuse). When Item 3 = Yes the same address is what the form prints as Item 2 — OG maps it at preparation (DERIVED placement) |
| 5 Country of domicile | `s_domicile` | COLLECTED (asked once even when birth data is reused) |
| 6 Date of birth | `s_dob` (block `sb_s_birth`) | COLLECTED (reuse) |
| 7 Country of birth | `s_birth_country` | COLLECTED (reuse) |
| 8 U.S. Social Security Number | `s_ssn` (block `sb_s_ssn`) | COLLECTED (reuse; sensitive) |
| 9 Immigration status | `s_status` | COLLECTED |
| 10 A-Number | `s_anumber` (block `sb_s_ids`) | COLLECTED (reuse, optional) |
| 11 USCIS Online Account Number | `s_uscis` | COLLECTED (reuse, optional) |
| 12 Active duty military (petitioner sponsors only) | `s_military` | CONDITIONAL (Part 1 = 1.a or “not sure”) |

## Part 3 — Principal immigrant

| Item | Field(s) | Status |
|---|---|---|
| 1 Full legal name | `p_family`, `p_given`, `p_middle` (block `sb_p_name`) | COLLECTED (reuse) |
| 2 Current mailing address | `pm_*` | COLLECTED (the form has no physical address here) |
| 3 Country of citizenship or nationality | `p_citizenship` (block `sb_p_birth`) | COLLECTED (reuse) |
| 4 Date of birth | `p_dob` | COLLECTED (reuse) |
| 5 A-Number | `p_anumber` (block `sb_p_ids`) | COLLECTED (reuse, optional) |
| 6 USCIS Online Account Number | `p_uscis` | COLLECTED (reuse, optional) |
| 7 Daytime telephone | `p_phone` (block `sb_p_phone`) | COLLECTED (reuse; “Is it still current?”) |

## Part 4 — Immigrants being sponsored

| Item | Field(s) | Status |
|---|---|---|
| 1 Sponsoring the principal immigrant? | `i_principal` | COLLECTED |
| 2 Family members immigrating at the same time / within six months | `i_family_q`, `i_timing` = `same_time` | CONDITIONAL |
| 3 Family members immigrating more than six months later | `i_timing` = `later` | CONDITIONAL |
| 4–7 Family Members 1–4 (name, relationship, DOB, A-Number, USCIS account) | `i_family` records | CONDITIONAL (more than four: OG places the overflow in Part 11) |

## Part 5 — Household size

| Item | Field(s) | Status |
|---|---|---|
| 1 Total immigrants sponsored on this affidavit | `c_hh_1` | DERIVED (principal if Item 1 of Part 4 = Yes, plus the listed family members) |
| 2 Yourself | `c_hh_2` | DERIVED (1) |
| 3 Spouse (0 if already counted in Item 1) | `h_married`, `h_spouse`, `h_people`; `c_hh_3` | COLLECTED inputs; count DERIVED |
| 4 Dependent children | `h_people`; `c_hh_4` | COLLECTED inputs; count DERIVED |
| 5 Other dependents | `h_people`; `c_hh_5` | COLLECTED inputs; count DERIVED |
| 6 Previously sponsored, still obligated | `h_people`; `c_hh_6` | COLLECTED inputs; count DERIVED |
| 7 Siblings/parents/adult children combining income (I-864A) | `h_people`; `c_hh_7` | COLLECTED inputs; count DERIVED |
| 8 Household size | `c_hh_8` | DERIVED (sum of Items 1–7) |
| NOTE do not count anyone more than once | `i864_calc.household`, `intake_records` duplicate warning | DERIVED rule: a real person is counted once (Person link, or same normalized name without a contradicting date of birth); precedence spouse › dependent child › other dependent › combining income (I-864A) › previously sponsored; the reason is shown |

## Part 6 — Employment and income

| Item | Field(s) | Status |
|---|---|---|
| 1 Employed as a/an … | `e_status` (employed), `e_sources` (occupation) | COLLECTED |
| 2 Employer 1 / 3 Employer 2 | `e_sources` (employer name, several allowed) | CONDITIONAL (employed) |
| 4 Self-employed as … | `e_status`, `e_sources` (self-employed occupation) | CONDITIONAL |
| 5 Retired since | `e_retired_since` | CONDITIONAL (retired) |
| 6 Unemployed since | `e_unemployed_since` | CONDITIONAL (unemployed) |
| 7 Current individual annual income | `e_has_income`, `e_sources`; `c_inc_7` | COLLECTED inputs; total DERIVED |
| 8–11 Persons 1–4 (name, relationship, current income) | `hi_use`, `inc_people` records | CONDITIONAL (when the customer uses another person's income; a person's income is counted once) |
| 12 Current annual household income | `c_inc_12` | DERIVED (Items 7–11) |
| 13 Forms I-864A completed | `hi_i864a` | CONDITIONAL |
| 14 Intending immigrant with no accompanying dependents | `hi_i864a_exempt`, `hi_i864a_exempt_name` | CONDITIONAL |
| 15 Filed a return for each of the three most recent years? | `t_three` | COLLECTED |
| 16.a–16.c Tax year and “total income (adjusted gross income on IRS Form 1040EZ)” | `t_years` records (amount / “zero” / “N/A”; newest = 16.a) | COLLECTED (16.b/16.c CONDITIONAL: optional additional years); no hard-coded years |
| 17 Not required to file, evidence attached | `t_norequire` | COLLECTED; document request `i864.tax_exempt` |

## Part 7 — Assets

| Item | Field(s) | Status |
|---|---|---|
| (intro) Part 7 not required when income exceeds the poverty guidelines | `a_use` | COLLECTED as the customer's choice (or “not sure”); the guideline comparison is OG's review — **no poverty values implemented** |
| 1 Cash, savings, checking | `a_assets` (sponsor · cash); `c_ast_1` | CONDITIONAL on `a_use`; total DERIVED |
| 2 Net cash value of real estate | `a_assets`; `c_ast_2` | CONDITIONAL; DERIVED |
| 3 Stocks, bonds, CDs, other | `a_assets`; `c_ast_3` | CONDITIONAL; DERIVED |
| 4 Sum of Items 1–3 | `c_ast_4` | DERIVED |
| 5 Household members' assets (I-864A Part 4 Item 6) | `a_assets` (household + holder); `c_ast_5` | CONDITIONAL; DERIVED |
| 6–8 Principal immigrant's savings/checking, real estate, other | `a_assets` (principal); `c_ast_6`–`c_ast_8` | CONDITIONAL; DERIVED; warned if the principal immigrant is not sponsored |
| 9 Sum of Items 6–8 | `c_ast_9` | DERIVED |
| 10 Total value of assets | `c_ast_10` | DERIVED (Items 4, 5, 9) |

## Part 8 — Contract, statement, contact, certification, signature

| Item | Field(s) | Status |
|---|---|---|
| NOTE read the Penalties section | `c1_n0` | shown verbatim (DERIVED text, not a question) |
| Sponsor's Contract (all paragraphs) | `c1_*`, `c2_*`, `c3_*`; `c_read` | shown verbatim in English; `c_read` = customer acknowledgment only (COLLECTED, not a form item, not a signature) |
| Sponsor's Declaration and Certification (all paragraphs, A–F, consumer-report note, note to all sponsors) | `cc_1`, `cc_4`, `cc_1b`, `cc_2`, `cc_3`, `cc_5`, `cc_6`; `c_cert_ack` | shown in the printed order (C/E keep the printed “Form I-864EZ”); `c_cert_ack` = acknowledgment only. The certification itself is **NOT COLLECTED — SIGNATURE EXECUTION** |
| 1.A / 1.B Statement regarding the interpreter | `c_english_or_interpreter` | COLLECTED (no default; an interpreter is never assumed) |
| 1.B language | `int_language` | CONDITIONAL (interpreter chosen) |
| 2 Preparer prepared the affidavit at my request | `preparer_request`; preparer name from Part 10 (`prep_family`, `prep_given`) | COLLECTED (customer request only) + DERIVED name |
| 3 Sponsor's daytime telephone | `s_phone` (block `sb_s_contact`) | COLLECTED (reuse) |
| 4 Sponsor's mobile telephone | `s_mobile` | COLLECTED (reuse, optional) |
| 5 Sponsor's email | `s_email` | COLLECTED (reuse, optional) |
| 6 Sponsor's signature | — | **NOT COLLECTED — SIGNATURE EXECUTION** |
| 6 Date of signature | — | **NOT COLLECTED — SIGNATURE EXECUTION** (filled when the sponsor signs) |

## Part 9 — Interpreter

| Item | Field(s) | Status |
|---|---|---|
| 1 Interpreter's full name | `int_family`, `int_given` | CONDITIONAL (interpreter chosen in Part 8 Item 1.B); editable defaults from `business_info.INTERPRETER_*` |
| 2 Business or organization | `int_org` | CONDITIONAL |
| 3 Daytime telephone | `int_phone` | CONDITIONAL |
| 4 Mobile telephone | `int_mobile` | CONDITIONAL (optional) |
| 5 Email | `int_email` | CONDITIONAL (optional) |
| Certification: “fluent in English and [language]” | `int_language` | CONDITIONAL — the language is collected; the certification itself is **NOT COLLECTED — SIGNATURE EXECUTION** |
| 6 Interpreter's signature and date | — | **NOT COLLECTED — SIGNATURE EXECUTION** |

Switching the Part 8 statement back to “I can read and understand English” removes the interpreter answers (`purge_hidden_values`).

## Part 10 — Preparer (OG)

| Item | Field(s) | Status |
|---|---|---|
| 1 Preparer's full name | `prep_family`, `prep_given` | COLLECTED (default `business_info.PREPARER_LAST_NAME` / `PREPARER_FIRST_NAME`) |
| 2 Business or organization | `prep_org` | COLLECTED (default `PREPARER_ORG`) |
| 3 Daytime telephone | `prep_phone` | COLLECTED (default `PREPARER_PHONE`) |
| 4 Mobile telephone | `prep_mobile` | COLLECTED, optional (default `PREPARER_MOBILE`, empty) |
| 5 Email | `prep_email` | COLLECTED, optional (default `PREPARER_EMAIL`) |
| Preparer's certification | — | **NOT COLLECTED — SIGNATURE EXECUTION** (OG certifies, separately) |
| 6 Preparer's signature and date | — | **NOT COLLECTED — SIGNATURE EXECUTION** |

The Part 10 page is shown to every customer (OG prepares every affidavit). The values come from the central OG configuration
(`app/business_info.py`, `PREPARER_*`, the same mechanism as the interpreter's `@biz:` defaults); they are never hard-coded in the form.
The preparer constants currently point at the same OG person/office as the interpreter defaults and can be changed independently.

## Part 11 — Additional information

| Item | Field(s) | Status |
|---|---|---|
| 1 Name (top of the sheet) | from Part 2 | DERIVED |
| 2 A-Number | from Part 2 Item 10 | DERIVED |
| 3–6 The extra answer | `additional_information` (free text, “tell us which question it is about”) | COLLECTED |
| 3–6 Page / Part / Item cross-reference numbers | — | NOT APPLICABLE TO SMART INTAKE (OG assigns them when transcribing; the customer is never asked for page/part/item numbers) |

## Front matter and boxes

| Element | Status |
|---|---|
| “For USCIS Use Only” blocks (Submitter, Section 213A Review, Number of Support Affidavits, Remarks, Reviewed By/Office/Date) | NOT APPLICABLE TO SMART INTAKE |
| Attorney / Accredited Representative box (Form G-28/G-28I, State Bar Number, USCIS account) | NOT APPLICABLE TO SMART INTAKE (OG is not a law firm; no representation) |
| Poverty Guideline table (household size / poverty line / household income / remarks) | NOT APPLICABLE TO SMART INTAKE (USCIS use; no threshold values implemented) |

## Spanish contract / certification

The English wording is the official text (as printed on edition 08/24/26) and prevails. The Spanish is **OG's courtesy translation**, identified as such:
* on the page itself, in Spanish (“…traducción de cortesía hecha por OG; no es un texto oficial de USCIS. El texto oficial es el del formulario en inglés y es el que prevalece”, or the short form on the two middle contract pages);
* internally, in `FormField.source_note` of every contract/certification paragraph and both acknowledgments (`OFFICIAL TEXT = the English … courtesy translation only (not USCIS text); the English prevails.`), visible to admins.
`seed_i864.ensure_i864_refinements()` applied this in place to the already deployed form.

## Platform behaviour (not form items)

* **Who is who:** `Person` → `CasePerson` → `ApplicationRole` (`sponsor`, `principal_immigrant`, plus `joint_sponsor` / `substitute_sponsor` from Part 1). Each affidavit has ONE sponsor; a joint sponsor is a different real Person with their own affidavit.
* **Compatibility:** `FORM_CASE_CONFIG["I-864"]["case_types"]` = adjustment_of_status, family_petition.
* **Application-only data:** income, tax, assets, household and calculated totals stay in the I-864 answers (never Person facts), so two affidavits in one case never mix.
* **Documents:** `app/i864_docs.py` → vault requirements per (rule, Person); person-less requirements are scoped to their affidavit; syncing one affidavit never withdraws another's; a shared requirement (for example the principal immigrant's own assets) lists exactly the affidavits that want it; a requirement that belongs to nobody is never satisfied by one person's file.
* **Consistency prompts (never conclusions):** `app/i864_checks.py`.

## Verification (session tests on database copies)

`e2e_i864a`–`e2e_i864f`: Part 10/9 behaviour and defaults, joint-sponsor isolation, household double count, courtesy-translation labelling, in-place refinement of a deployed form, conflicts, security, Spanish, reopen/resubmit, documents.

## Known limits

* Form I-864A, I-864P and the Form I-864 Instructions were not supplied; nothing is built from them.
* No poverty-guideline thresholds; no statement that a household, income or assets are sufficient, or that a joint sponsor is or is not needed.
* The Spanish is OG's translation (courtesy only).
* No PDF/official-form export.
* No signature of any kind is executed or collected (Parts 8, 9, 10).
