# Form I-751 Smart Intake — source coverage audit

**Source of truth:** the supplied USCIS *Form I-751, Petition to Remove Conditions on Residence*, **Edition 04/01/24** (OMB No. 1615-0038, expires
03/31/2027), **11 pages**, Parts 1–11 (`Downloads/i-751.pdf`). Nothing here comes from memory or from another edition. Item numbers are the ones printed
on that PDF.

Intake: `app/seed_i751.py` (form `i-751-client-intake`, source form `I-751`, edition `04/01/24`; service *Removal of Conditions on Residence (Form I-751)*,
slug `removal-of-conditions`, created if missing). Every question stores its Part/Item in `FormField.source_ref` (admin-only); customers never see
part/page/item numbers. Supporting modules: `i751_text.py` (verbatim texts + OG's courtesy Spanish), `i751_calc.py`, `i751_views.py`, `i751_docs.py`,
`i751_checks.py`. Tests: `e2e_i751a`–`c` and `verify_cov751` (session scratchpad).

## Status vocabulary

| Status | Meaning |
|---|---|
| **COLLECTED** | the customer answers it, or reviews a value OG already knows for that real Person and confirms/edits it (`reuse`), or a central-configuration default (OG's preparer/interpreter details) is stored as an answer |
| **CONDITIONAL** | collected only when an earlier answer makes it applicable |
| **DERIVED** | never asked: calculated from other answers, read from central configuration, or generated (Part 11 entries) |
| **SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE** | a signature or the date of that signature. The intake never signs, e-signs or certifies for anyone; “Send to OG” is not the USCIS signature |
| **NOT APPLICABLE TO SMART INTAKE** | not a customer-information item (USCIS-use boxes, the attorney/accredited-representative block and G-28 box, page/part/item cross-references OG assigns) |

A Part/Item is covered only when a field, calculation or explicit rule implements it (`verify_cov751.py`: every non-signature item of Parts 1–10 is named by a
field; every signature item is named by none).

## Interview order (differs from the printed order, traceability does not)

The customer answers **Part 3 (how they are filing) first**, because it drives what is asked next (Part 4 relationship, whether Part 8 applies, Item 21).
Every question still carries its own Part/Item reference. The filing basis is **never decided** by the intake: it stores exactly one joint-filing box, OR any
number of waiver / individual-filing boxes, OR “not sure — OG will review”. No timeliness, good-faith, hardship or eligibility conclusion is drawn anywhere.

## Case and identity architecture

* **A new case type, `removal_of_conditions`** (“Removal of Conditions on Residence”). `FORM_CASE_CONFIG["I-751"]["case_types"]` lists only that type, so an I-751 is
  never attached to an Adjustment of Status, Family Petition, Naturalization or Green Card Renewal case (`attach_application` raises `IncompatibleCase`), and
  no other form's setup offers this case.
* **Same real people, new case.** Setup (`/f/<slug>/setup`, `case_setup.apply_i864` driven by `setup_pair`) asks *whose conditional residence this petition is about* and *who
  the spouse (or parent's spouse) is*; both are picked from the customer's existing real People (or added). Person ids are re-read as the customer's own. A new
  CasePerson links to the SAME `Person` (no name matching), so Marisol's I-130/I-485/I-765 facts and Luis's I-130 facts are reused in the new case; the older
  cases and applications are never altered. The same person cannot be both resident and spouse.
* **Roles on the I-751 application:** `conditional_resident`, `relevant_individual`, plus time-aware `spouse` | `former_spouse` | `parent_spouse` (from Part 4 Item 1 and whether
  the marriage ended, Part 1 Item 13 / basis 1.c–1.d) and `joint_petitioner` (joint filing); children get role `child`.
* **Reuse scopes:** stable facts (name, date of birth, birth country, nationality, A-Number, SSN, USCIS account, other names) → review-and-confirm, differing values
  become conflicts; situational facts (marital status, address, address history, phone/email, ethnicity, race, height, weight, eye and hair color) → shown with
  their source and re-confirmed (“Is this still current?”); everything else is application-specific and asked.
* **Documents** stay in the case vault (same-case reuse only; a document in another case is never exposed).

## Part 1 — Information about you, the conditional resident

| Item | Field(s) | Status |
|---|---|---|
| 1.a–1.c Full legal name | `r_family`, `r_given`, `r_middle` (block `sb_identity`) | COLLECTED (reuse: “We already have {name}'s identity information” → confirm / edit; edits update the same real Person) |
| 2.a–2.c, 3.a–3.c Other names used (two name boxes) | `r_other_names` records (block `sb_othernames`) | COLLECTED (reuse); names 3+ → DERIVED Part 11 entry (Page 1, Part 1, Items 2–3) |
| 4 Date of birth | `r_dob` | COLLECTED (reuse) |
| 5 Country of birth | `r_birth_country` | COLLECTED (reuse) |
| 6 Country of citizenship or nationality (all that apply) | `r_citizenship` (comma-separated if several) | COLLECTED (reuse) |
| 7 A-Number | `r_anumber` (block `sb_ids`) | COLLECTED (reuse, masked) |
| 8 U.S. Social Security number | `r_ssn` (block `sb_ids`) | COLLECTED (reuse, masked) |
| 9 USCIS Online Account Number | `r_uscis` (block `sb_ids`) | COLLECTED (reuse) |
| 10 Marital status (Single / Married / Divorced / Widowed) | `r_marital` (block `sb_marital`) | COLLECTED (situational: re-confirmed) |
| 11 Date of marriage | `r_marriage_date` | COLLECTED |
| 12 Place of marriage | `r_marriage_place` | COLLECTED |
| 13 Date the marriage ended (divorce or death) | `r_marriage_ended` (OG helper: whether it ended) → `r_marriage_end_date` | CONDITIONAL (only when the marriage ended) |
| 14 Conditional residence expires on | `r_expires` | COLLECTED (stored as given; **no timeliness conclusion**, OG reviews the timing) |
| — *(not a numbered item)* date the customer became a permanent resident (“Resident Since”) | `r_resident_since` | COLLECTED as an **OG helper** only: it starts the residence-history window for Item 22 |
| 15.a–15.f Mailing address (In Care Of, street, unit, city, state, ZIP) | `ml_*` (`ml_in_care_of` … `ml_zip`) | CONDITIONAL (only when Item 16 = Yes; otherwise the mailing address is the physical one — DERIVED placement) |
| 16 Is your physical address different than your mailing address? | `m_diff` | COLLECTED |
| 17.a–17.f Physical address (In Care Of, street, unit, city, state, ZIP) | `ph_*` (block `sb_address`, U.S. addresses only) | COLLECTED (reuse: “Is this still where you live?”). Printed only when Item 16 = Yes; otherwise it fills Item 15 (DERIVED) |
| 18 In removal, deportation, or rescission proceedings? | `q18` | COLLECTED; Yes → CONDITIONAL required explanation `q18_details` (DERIVED Part 11 entry, private), document request `i751.proceedings` (basis: answer), OG-review flag |
| 19 Fee paid to anyone other than an attorney in connection with this petition? | `q19` (help notes that a non-attorney preparer's fee counts; OG reviews the answer with the customer) | COLLECTED; Yes → required `q19_details` (Part 11), request `i751.fee_receipts` (answer), OG-review flag |
| 20 Ever arrested, detained, charged, indicted, fined, or imprisoned … | `q20` (printed note shown when Yes) | COLLECTED; Yes → required `q20_details` (Part 11, private), request `i751.dispositions` (basis: answer; refers to the form's “What Initial Evidence Is Required” pointer, invents no rule), OG-review flag |
| 21 If married, is this a different marriage than the one through which conditional residence was gained? | `q21` | CONDITIONAL (only when Item 10 = Married); Yes → required `q21_details` (Part 11), request `i751.different_marriage` (answer), OG-review flag |
| 22 Resided at any other address since becoming a permanent resident? | `r_other_addr` → `r_history` (address builder) | COLLECTED; Yes → CONDITIONAL history from the resident-since date to today (see below); the full list is a DERIVED Part 11 entry (Item 22) |
| 23 Spouse or parent's spouse serving with/employed by the U.S. Government outside the U.S.? | `q23` | COLLECTED; Yes → required `q23_details` (Part 11), OG-review flag |

**Residence-history scope (Item 22).** The existing address builder gained an optional `timeline.since_field`: the analysis window starts at the date the customer became a
resident, not at a fixed number of years, and is re-computed by the server (`POST /f/<slug>/records/analyze` with `since`, review, completeness and Admin all agree).
Missing dates, reversed ranges, overlaps, gaps and duplicates are flagged; gaps never block Continue. If the resident-since date is not given, only the entered period is
checked (no window is invented). The N-400 builder is unchanged (fixed 5 years). A history OG already has for the person (for example from an I-485) is offered as a
starting point (“We already have addresses for {name}”); because it may not cover the whole period, the edit step is shown again until `c_hist` says the period is covered.

## Part 2 — Biographic information

| Item | Field | Status |
|---|---|---|
| 1 Ethnicity (only one box) | `r_ethnicity` (block `sb_bio`) | COLLECTED (reuse from N-400 / I-485 with confirmation; **never inferred**) |
| 2 Race (all applicable boxes) | `r_race` (multi-select) | COLLECTED (same) |
| 3 Height (feet, inches) | `r_height_ft`, `r_height_in` | COLLECTED (same) |
| 4 Weight (pounds) | `r_weight` | COLLECTED (same) |
| 5 Eye color | `r_eye` | COLLECTED (same) |
| 6 Hair color | `r_hair` | COLLECTED (same) |

## Part 3 — Basis for petition

| Item | Field | Status |
|---|---|---|
| Joint Filing 1.a My spouse | `b_route` = `joint`, `b_joint` = `1a` | COLLECTED (verbatim wording, one box) |
| Joint Filing 1.b My parent's spouse because I am unable to be included in a joint petition filed by my parent and my parent's spouse | `b_joint` = `1b` | COLLECTED (Part 8 contact details collected; OG confirms how the rest applies) |
| Waiver / Individual Filing 1.c My spouse is deceased | `b_route` = `waiver`, `b_waiver` contains `1c` | COLLECTED (multi-select: any number of boxes 1.c–1.g at once) |
| 1.d Marriage entered in good faith, terminated through divorce or annulment | `b_waiver` contains `1d` | COLLECTED |
| 1.e Entered the marriage in good faith and was battered / subject of extreme cruelty by the U.S. citizen or LPR spouse | `b_waiver` contains `1e` | COLLECTED, **private** |
| 1.f Parent entered the marriage in good faith and I was battered / subjected to extreme cruelty by the parent's spouse or conditional-resident parent | `b_waiver` contains `1f` | COLLECTED, **private** |
| 1.g Termination of status and removal would result in extreme hardship | `b_waiver` contains `1g` | COLLECTED, **private** |
| — *(OG addition)* “Not sure — OG will review” | `b_route` = `unsure`, or `unsure` inside `b_waiver` | COLLECTED (OG-review flag; Part 8 not asked until OG decides) |

Privacy of the filing basis: `b_route`, `b_joint`, `b_waiver`, the Part 6 answers and the private explanations carry `private` in `FormField.config_json` → the snapshot marks
them and *My Applications* shows “Private — shared only with OG” instead of the value; case titles, roles (`relevant_individual` is neutral), activity events, document titles
(`i751.basis_docs` is titled neutrally) and completeness messages never name a sensitive basis. Admin sees everything with a PRIVATE marker.

## Part 4 — The U.S. citizen or LPR spouse (or, for a child filing separately, the stepparent)

| Item | Field(s) | Status |
|---|---|---|
| 1.a Spouse or Former Spouse / 1.b Parent's Spouse or Former Spouse | `p4_rel` | COLLECTED; drives the time-aware role (`c_p4_role`) |
| 2.a–2.c Name | `s_family`, `s_given`, `s_middle` (block `sb_s_name`) | COLLECTED (reuse of the real Person, e.g. the I-130 petitioner, in a different case; no duplicate Person) |
| 3 Date of birth | `s_dob` (block `sb_s_birth`) | COLLECTED (reuse) |
| 4 U.S. Social Security number | `s_ssn` (block `sb_s_ids`) | COLLECTED (reuse, masked) |
| 5 A-Number | `s_anumber` (block `sb_s_ids`) | COLLECTED (reuse, masked) |
| 6.a–6.h Physical address (street, unit, city, state, ZIP, province, postal code, country) | `sa_*` (block `sb_s_address`, U.S. or foreign) | COLLECTED (situational: re-confirmed) |

Listing a person gives them no login (`CasePerson.student_id` stays empty).

## Part 5 — Information about your children

| Item | Field | Status |
|---|---|---|
| — *(OG helper)* any children? | `k_has` | COLLECTED |
| Child 1: 1.a–1.c name, 2 DOB, 3 A-Number, 4 living with you?, 5 applying with you?, 6.a–6.h physical address | `k_children` (record type `i751_child`), entry 1 | COLLECTED (repeatable; each child is a real Person: linked by an explicit “someone I already have” choice, or created; never merged by name — a name match is rejected when the known date of birth differs) |
| Child 2: Items 7–12 | entry 2 | COLLECTED |
| Child 3: Items 13–18 | entry 3 | COLLECTED |
| Child 4: Items 19–24 | entry 4 | COLLECTED |
| Child 5: Items 25–30 | entry 5 | COLLECTED |
| Children 6 and more | entries 6+ | COLLECTED (no five-row limit) → DERIVED Part 11 entries (“Child 6: …”), the customer is told OG adds them |
| “Living with you” Yes | `where = with_me` | COLLECTED; the printed physical address is then DERIVED from the petitioner's physical address (Part 1 Item 17) |
| “Living with you” No, physical address (6.a–6.h etc.) | `where = us | abroad` + address fields | CONDITIONAL |

## Part 6 — Accommodations for individuals with disabilities and/or impairments

| Item | Field | Status |
|---|---|---|
| 1 Accommodation because of your disabilities/impairments? | `acc_own` | COLLECTED (private) |
| 2 … because of your spouse's? | `acc_spouse` | CONDITIONAL (joint filing or “not sure”; not asked otherwise) |
| 3 … because of your included children's? | `acc_children` | CONDITIONAL (only when the customer has children) |
| 4.a Deaf / hard of hearing + accommodation (+ sign-language language) | `acc_types` contains `a`, `acc_a_text` | CONDITIONAL (any Yes to Items 1–3), private |
| 4.b Blind / low vision + accommodation | `acc_types` contains `b`, `acc_b_text` | CONDITIONAL, private |
| 4.c Another type of disability/impairment + accommodation | `acc_types` contains `c`, `acc_c_text` | CONDITIONAL, private |
| Information for each person (spouse / children) | `acc_persons` | CONDITIONAL → DERIVED Part 11 entry (private) |

## Part 7 — Petitioner's statement, contact, ASC acknowledgement, certification, signature

| Item | Field | Status |
|---|---|---|
| 1.a I can read and understand English … | `s_statement` = `english` | COLLECTED (verbatim; OG's courtesy Spanish) |
| 1.b The interpreter named in Part 9 also read to me … in {language} | `s_statement` = `interpreter`, `int_language` | COLLECTED (an interpreter is never assumed) → opens Part 9 |
| 2 I have requested the services of and consented to {name}, who is / is not an attorney or accredited representative, preparing this petition | `p7_prep_card` (dynamic text from `business_info.PREPARER_*`), `preparer_request` (request for preparation, not a signature) | DERIVED (OG is never defaulted to attorney/accredited) |
| 3 Daytime telephone / 4 Mobile / 5 Email | `r_phone`, `r_mobile`, `r_email` (block `sb_contact`) | COLLECTED (reuse) |
| Acknowledgement of Appointment at USCIS Application Support Center (text) | `asc_card` (verbatim, name filled) + `c_asc_ack` (reading acknowledgment — **not a signature**) | DERIVED text + customer acknowledgment |
| Petitioner's Certification (text, incl. the two NOTES) | `cert_1`–`cert_4` (verbatim) + `c_cert_ack` (reading acknowledgment — **not a signature**) | DERIVED text + customer acknowledgment |
| 6.a Petitioner's Signature | — | SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE |
| 6.b Date of Signature | — | SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE |

## Part 8 — Spouse's or individual's statement (if applicable)

Asked only for a **joint** petition (the form's note ties Part 8 to Box 1.a; Box 1.b collects the contact details and OG confirms the rest). Never for a waiver / individual filing.
The statement belongs to the Part 4 spouse: the petitioner records what they know; the spouse's certification and signature are never collected.

| Item | Field | Status |
|---|---|---|
| 1.a / 1.b Statement (English / interpreter + language) | `s8_statement` (`english` / `interpreter` / “I do not know — OG will ask them”), `s8_language` | CONDITIONAL (joint) |
| 2 Preparer statement | `p8_prep_card` (dynamic, from OG configuration) | DERIVED / CONDITIONAL |
| 3 Daytime telephone / 4 Mobile / 5 Email | `s_phone`, `s_mobile`, `s_email` (block `sb_s_contact`) | CONDITIONAL (reuse) |
| Acknowledgement of Appointment text and the Spouse's Certification text | `asc8_card` (verbatim), `p8_cert_note` | DERIVED text, shown for reading; **no acknowledgment is collected on the spouse's behalf** |
| 6.a Spouse's or Individual's Signature / 6.b Date | — | SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE |

## Part 9 — Interpreter

Asked only when the petitioner (Part 7 Item 1.b) or the spouse (Part 8 Item 1.b) used an interpreter; defaults come from `business_info.INTERPRETER_*` / `OFFICE_*`.

| Item | Field | Status |
|---|---|---|
| 1.a / 1.b Interpreter's name | `int_family`, `int_given` | CONDITIONAL |
| 2 Business or organization name | `int_org` | CONDITIONAL |
| 3.a–3.h Mailing address | `int_*` address fields | CONDITIONAL |
| 4 Daytime telephone / 5 Email | `int_phone`, `int_email` | CONDITIONAL |
| Interpreter's Certification (text) | `int_cert` (verbatim, language shown) | DERIVED text |
| 6.a Interpreter's Signature / 6.b Date | — | SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE |

## Part 10 — Preparer (OG)

| Item | Field | Status |
|---|---|---|
| 1.a / 1.b Preparer's name | `prep_family`, `prep_given` | COLLECTED (central default; OG) |
| 2 Business or organization name | `prep_org` | COLLECTED (central default) |
| 3.a–3.h Mailing address | `prep_*` address fields | COLLECTED (central default: OG office) |
| 4 Daytime telephone | `prep_phone` | COLLECTED (central default) |
| 5 Fax | `prep_fax` (`business_info.PREPARER_FAX`, empty unless configured) | COLLECTED (central default) |
| 6 Email | `prep_email` | COLLECTED (central default) |
| 7.a not an attorney or accredited representative / 7.b attorney or accredited representative (+ extends / does not extend) | `prep_status`, `prep_extends`, card `prep_statement_card` | DERIVED from `business_info.PREPARER_STATUS` (never a customer answer; OG is never defaulted to attorney/accredited) |
| Preparer's Certification (text) | `prep_cert` (verbatim) | DERIVED text |
| 8.a Preparer's Signature / 8.b Date | — | SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE |

## Part 11 — Additional Information

| Item | Field | Status |
|---|---|---|
| 1.a–1.c Your full name / 2 A-Number | Part 1 Items 1.a–1.c and 7 | DERIVED (OG puts them at the top of each page) |
| 3.a–7.d Page / Part / Item number + text (five entries) | `c_addl` (hidden calculated answer), `additional_information` | DERIVED entries generated from the answers (other names 3+, every address of Item 22, explanations for Items 18–21 and 23, children 6+, accommodation information for each person) plus the customer's own free text. The customer never types a page, part or item number; OG assigns the reference. Entries tied to a private answer are marked private. If more than five entries are needed OG uses more copies of the page |

## Not customer questions

| Printed element | Status |
|---|---|
| “For USCIS Use Only” block (Receipt, Action Block, Remarks, Reloc Sent / Received, Petitioner interviewed on, “Approved under INA 216(c)(4)(C)”) | NOT APPLICABLE TO SMART INTAKE |
| “To be completed by an attorney or accredited representative” block (Select this box if Form G-28 is attached, Attorney State Bar Number, USCIS Online Account Number of the attorney) | NOT APPLICABLE TO SMART INTAKE (OG is not shown as an attorney; G-28 is not collected) |
| Part 7 Item 6, Part 8 Item 6, Part 9 Item 6, Part 10 Item 8 (signatures and dates) | SIGNATURE EXECUTION — NOT PERFORMED BY INTAKE |

## Known limits (honest)

* The **Form I-751 Instructions** were not supplied, so the intake makes **no claim about which evidence USCIS requires**. Document requests are labelled by basis (`workflow` = OG's request,
  `answer` = triggered by an answer, `source` = the form itself says it — none applies, `admin` = added by OG) and OG confirms with the customer what applies.
* No eligibility, timeliness, good-faith, extreme-hardship or waiver conclusion exists anywhere; “please review” prompts only.
* Signatures, the spouse's certification and every date of signature are not collected; “Send to OG” is not a filing, an e-signature or the Petitioner's Certification.
* Spanish for the official texts is OG's courtesy translation; the English prevails.
* Documents are reused within the same case only; a document in another case is not exposed to the new case.
* No PDF / Part 11 export yet (answers are stored per question).
