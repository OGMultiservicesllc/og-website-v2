# Form W-7 (Rev. December 2024) — source coverage for OG's online ITIN intake

Sources supplied by OG: **Form W-7 (Rev. December 2024)** and **Instructions for Form W-7 (Rev. December 2024)** (16 pages). Page numbers below are of the Instructions PDF.

This is an audit of OG's ACTUAL online ITIN workflow, not of a line-by-line digital W-7. The customer never sees or chooses a reason code; OG staff confirm the W-7 reason
before "Ready for IRS". OG Multiservices does not approve or deny ITIN applications; the IRS makes the final decision. Sending the intake to OG is not a W-7 signature,
filing, IRS receipt, ITIN approval, return filing or CAA certification.

**Operational scope (OG's rule, not an IRS eligibility decision):** applicant physically in the U.S., a valid U.S. mailing address, and an ITIN tied to a federal return OG
prepares. Anything else shows "This type of ITIN request is not currently handled through OG's online ITIN intake. Please contact OG Multiservices for assistance." and creates nothing.

**NOT IMPLEMENTED BY CURRENT OG ONLINE WORKFLOW: Exceptions 1–5** (Instructions p. 8 and the Exceptions Tables, p. 11–15): passive income / third-party withholding (1), other income (2),
mortgage interest (3), dispositions of U.S. real property (4), Treasury Decision 9363 (5). No question, document rule, flag or admin control exists for them; the same goes for
reasons **a** (treaty benefit) and **f** (nonresident student, professor or researcher) and line **6g**, which only apply with those reasons or exceptions.

Status vocabulary: **COLLECTED** (asked once, or reused from the real Person) · **CONFIRMED** (read from the passport and confirmed by the customer) · **DERIVED** (computed by OG) ·
**CANDIDATE** (derived, staff must confirm) · **STAFF** (entered or recorded by OG staff) · **NOT COLLECTED — SIGNATURE** · **NOT IMPLEMENTED**.

## 1. Form W-7 line by line

| W-7 line | Source requirement | OG field / component | Document rule | Conditional rule | Status | Notes |
|---|---|---|---|---|---|---|
| Application type | New ITIN / Renew (Form) | ITIN case setup (`ItinCaseData.request_kind`), admin case view | — | "Not sure" is allowed; staff decide | COLLECTED | Case level, not per person |
| Reason (a–h) | Reason for submitting the W-7 (Form; Instructions p. 1–3) | `W7Application.reason_candidate` (derived), `reason_confirmed` (staff) | — | primary → b or c; spouse → e (taxpayer is a citizen/resident) or b/c/g; dependent → d (citizen/resident), d or g (not), review (unknown). `w7_calc.reason_candidate` | CANDIDATE → STAFF | The customer never chooses it. Confirmation is required before Ready for IRS |
| Reason d — relationship | Enter relationship to the U.S. citizen/resident alien (Form) | `dep_rel` | — | Dependents; asked on the dependent page | COLLECTED | Flag `relationship_missing` if empty |
| Reason d / e — name and SSN/ITIN of the citizen/resident | Form | Taxpayer = the customer's own Person; `taxpayer_ssn_itin` (sensitive) | — | Page shown only when the candidate reason is d or e | COLLECTED | Flag `taxpayer_id_missing` (OG REVIEW — ADDITIONAL W-7 INFORMATION REQUIRED); masked outside the W-7 Preparation View |
| Reasons a, f, h; treaty country / article | Form; Instructions p. 1–3 | — | — | — | NOT IMPLEMENTED | Reason a and f (and Exceptions) are outside the online workflow; staff may confirm h |
| 1a Name (first, middle, last) | Instructions p. 8: legal name as on identifying documents | `a_given`, `a_middle`, `a_family` — confirmed from the passport; typed only when there is no passport | Passport | Identity edit step required only when there is no passport | CONFIRMED / COLLECTED | Reuses the real Person; a different confirmed value becomes a visible conflict, never an overwrite |
| 1a note — legal name changed (renewal) | Instructions p. 8: renewal + name change needs a marriage certificate or court order | `hist_name_changed` | `w7.name_change` (irs_w7 basis, copy) | Asked when a previous ITIN exists | COLLECTED | |
| 1b Name at birth | Instructions p. 8 | `a_birth_name` | — | Optional | COLLECTED | Blank = same name |
| 2 Mailing address | Instructions p. 8: complete mailing address; a P.O. box or "in care of" is not allowed when only a country is entered on line 3 (p. 9) | `ua_street`, `ua_unit_type`, `ua_unit_number`, `ua_city`, `ua_state`, `ua_zip` (shared block `sb_address`, U.S. only) | — | Help text on the street field | COLLECTED | Reused from the Person; "Is this still current?" |
| 3 Foreign address | Instructions p. 8–9: full foreign address; only the country if no foreign residence remains; full address for reason b | `a_foreign_res`, `a_prior_country` | — | Country only. Flags `line3_foreign_address`, `foreign_residence` | COLLECTED (country) | OG REVIEW — ADDITIONAL W-7 INFORMATION REQUIRED when the full foreign address is needed |
| 4 Date of birth; country and city of birth | Instructions p. 9 | `a_dob`, `a_birth_country`, `a_birth_city` | Passport / birth certificate | Confirmed from the passport (city and country typed at confirmation; the MRZ does not carry them) | CONFIRMED | |
| 5 Sex | Form | `a_sex` | Passport | | CONFIRMED | |
| 6a Country(ies) of citizenship | Instructions p. 9: complete country name | `a_nationality` | Passport | | CONFIRMED | |
| 6b Foreign tax I.D. number | Instructions p. 9: only if the country of residence issued one | `a_foreign_tin` (sensitive) | — | Optional | COLLECTED | |
| 6c Type of U.S. visa, number, expiration | Instructions p. 9: nonimmigrant visa only | `visa_entered`, `visa_class`, `visa_number`, `visa_expiry` | `w7.visa_page` (digital; answer basis) | Fields shown only when the customer entered with a visa; may be left to the visa page | COLLECTED | Flag `visa_details` when incomplete |
| 6d Identification document(s) submitted | Instructions p. 3–4, 9: passport (stand-alone) or two document types | Passport: `a_pp_number`, `a_pp_country`, `a_pp_issued`, `a_pp_expiry`. No passport: `alt_docs` + evidence matrix | `w7.passport` (original required, OG can verify); `w7.alt.<key>` | pp_status have / later / none | CONFIRMED / COLLECTED | Only the first document is entered on the line; staff attach a sheet for the rest |
| 6d Date of entry into the U.S. | Instructions p. 9: full entry date | `a_entry_date` (shared block `sb_entry`) | — | A passport without an entry date is not a stand-alone document for dependents (p. 9, p. 4): `dep_entry_stamp` | COLLECTED | "Never entered" does not apply (physically in the U.S. is a scope rule) |
| 6e Previous ITIN / IRSN? | Instructions p. 9–10 | `hist_itin` (yes / no / I do not know) | — | | COLLECTED | Flag `renew_itin_missing` for renewals |
| 6f ITIN / IRSN and name issued under | Instructions p. 10 | `hist_itin_num` (sensitive), `hist_itin_name` | — | Only when 6e is yes | COLLECTED | Multiple IRSNs are attached by staff |
| 6g College / company, city and state, length of stay | Instructions p. 10: reason f / business visitors | — | — | — | NOT IMPLEMENTED | Reason f and Exceptions are outside the online workflow |
| Sign Here — applicant signature and date | Instructions p. 10: original signature; parent/guardian for a dependent under 18; Form 2848 rules | `W7Application.signature_state` (staff records) | — | | NOT COLLECTED — SIGNATURE | The intake never collects or applies a signature; who signs and how is handled by OG staff |
| Sign Here — phone number | Form | `a_phone` (shared block `sb_contact`) | — | | COLLECTED | |
| Delegate name and relationship | Instructions p. 9–10 | — | — | — | NOT COLLECTED — SIGNATURE | Staff, with the signature |
| Acceptance Agent's Use ONLY | Instructions p. 10: signature, date, name/title, company, EIN, PTIN, office code, phone, fax | `app/business_info.py` (`CAA_COMPANY`, `CAA_PHONE`, `CAA_FAX`, `CAA_EIN`, `CAA_PTIN`, `CAA_OFFICE_CODE`), W-7 Preparation View | — | Empty identifiers are shown as missing, never guessed | STAFF | OG's IRS identifiers must be entered into the configuration by OG |

## 2. Instructions requirements

| Instructions topic (page) | Requirement | OG component | Status | Notes |
|---|---|---|---|---|
| Who must apply / who cannot (p. 1–3) | Do not file with an SSN, or if eligible for or applied for one | `ssn_status`; flag `ssn_status`; neutral customer text (`w7_text.SSN_NOTE`) | COLLECTED | OG review; no eligibility conclusion |
| Filing with a tax return (p. 3, 5) | Reasons b–g require a federal return unless an Exception applies | Scope question "will OG prepare the return"; case tax year | COLLECTED | Exceptions are not implemented |
| Supporting documents — the table (p. 4) | Documents that prove foreign status and identity; passport stands alone; otherwise at least two types, one with a photo | `w7_rules.EVIDENCE`, `w7_rules.coverage`, admin coverage matrix | DERIVED | Model keeps three questions apart: accepted by the IRS · OG (CAA) can certify · original must be provided |
| Photograph exemption (p. 4) | Dependent under 14 (under 18 if a student) may not need a photo document | `w7_rules.photo_exempt` | DERIVED | |
| Dependents' U.S. residency evidence by age (p. 4) | Medical record only under 6; school record under 24 if a student; other listed documents | `w7_rules.residency_options`, `res_u6`, `res_6_17`, `res_18`, `dep_student`, `dep_entry_stamp` | CONDITIONAL | Canada / Mexico dependents: OG review note (`canada_mexico`) |
| Medical and school record contents (p. 4, 16) | Named contents (dates, names, addresses, provider/school) | `w7_text.MEDICAL_HELP`, `SCHOOL_HELP` shown in the documents step | DERIVED | Help text only; OG reviews the actual document |
| Original documents (p. 3–4) | Originals or certified copies must be provided | `ItinDocTrack` (original required / mail / in person / received / CAA verified / ready to return / returned) | STAFF | A photo upload never counts as the original |
| Where to apply / mail the package (p. 6) | Package mailed to the IRS | `ItinCaseData` (`usps_tracking`, mailed / delivered dates), admin case view, customer "Track Package" | STAFF | USPS delivery is not IRS processing and not an approval |
| Certifying Acceptance Agent (p. 6) | A CAA can verify originals: dependents only passports and birth certificates; others everything except a foreign military ID | `w7_rules.caa_can_verify`; admin "Record CAA verification" (who / when / document version) | STAFF | Explicit staff action only; never automatic |
| Processing times (p. 6) | About 7 weeks; 9–11 weeks in peak periods | `w7_text.PROCESSING` (EN/ES) on the review and My Account | DERIVED | Copy supplied by OG; not a promise |
| Signature — who can sign (p. 9–10) | Applicant, parent / court-appointed guardian, power of attorney | `W7Application.signature_state` | NOT COLLECTED — SIGNATURE | Staff handle it |
| Renewal (p. 9–10) | Include the previous ITIN and the name it was issued under | `hist_itin_num`, `hist_itin_name` | COLLECTED | |
| Exceptions 1–5 and the Exceptions Tables (p. 8, 11–15) | Filing-requirement exceptions | — | **NOT IMPLEMENTED BY CURRENT OG ONLINE WORKFLOW: Exceptions 1–5** | Out of scope by design |

## 3. OG workflow additions (not printed on the W-7)

| Item | Component | Notes |
|---|---|---|
| Passport-first | `pp_status` (have / later / none), `/f/<slug>/passport` (upload, "We found this information on the passport.", confirm or correct) | Reading: local MRZ parser (`w7_passport.parse_mrz`), optional local tesseract, staff reading, customer typing. No document ever goes to a third party |
| Upload later never blocks | Requirement `w7.passport`, flags `passport_needed`, `identity_pending`, My Account "Passport Needed / Upload Passport" | Later upload → reading → confirmation → Person facts → completeness; no duplicate application |
| Household in one case | One `W7Application` (a `FormSubmission` of the W-7 form) per ITIN applicant Person; all in one `itin_application` case | Spouse and dependents are real Persons; no universal "spouse must have income" rule is stated |
| Marriage certificate | `w7.marriage_cert` (OG workflow, digital) | Spouse applicants |
| Birth certificate | `w7.birth_cert` (IRS original if under 18 with no passport, otherwise OG workflow) | |
| Income records | `w7.income_records` (OG workflow, digital, optional: a warning, never a Ready-for-IRS blocker) | Self-employed, both or other income; no Schedule C, no tax calculation |
| Visa page | `w7.visa_page` (digital), typed `visa_class`, `visa_number`, `visa_expiry` | The visa page is not machine-read (only the passport MRZ is); staff compare it with the typed details |
| W-2 | `w7.w2`, flag `w2_identifier` ("W-2 / taxpayer identifier requires OG review") | Collected as issued; no accusation, no rejection, no reassurance |
| Statuses | Intake Started · Waiting for Documents · Waiting for Original Documents · Ready for OG Review · OG Reviewing · Tax Preparation · Ready for Signature · Ready for IRS · Sent to IRS · IRS Processing · IRS Response Received · Completed | Processing is never inferred from USPS delivery; the IRS response is recorded by staff |
| Originals delivery | OG Multiservices LLC, 145 Presidential Blvd, STE 2, Paterson, NJ 07522, or in person (`app/business_info.py`) | Never a private residence |
