# DS-260 source coverage

Generated from the seeded intake (`Form.features["ceac"]`). The DS-260 is an online Department of State form (CEAC) with no edition number.

**Sources.** (A) DS-260 IV Application SAMPLE, Consular Systems and Technology, October 2019, 111 pp. (supplied, read page by page; the PDF is screenshots). (B) Newer official DOS material reached: Federal Register 30-day notice 2025-20231 (OMB 1405-0185), reginfo.gov ICR 202605-1405-003 / 202606-1405-004, DOS/NVC public pages mirrored on adoptions.state.gov. (C) Current DOS DS-260/CEAC instructions: only as far as (B) states them. **NOT verified:** the June 2023 official sample and the live CEAC screens (travel.state.gov blocks automated access from this environment). Newer official source wins where reached; the differences are in the tables.

Status legend: CURRENT — IMPLEMENTED · CURRENT — CONDITIONAL · CURRENT — DERIVED · SUPERSEDED · SOURCE DISCREPANCY — REVIEWED · SIGN/SUBMIT — CEAC ONLY · NOT APPLICABLE TO OG PREPARATION · NOT BUILT (honest gap).


## Personal 1

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Personal 1 | Surnames | pp. 7-9 | — | CURRENT — CONDITIONAL | short_answer `a_family` | yes (show rule) | `a_family` | name | Implemented |  |
| Personal 1 | Given Names | pp. 7-9 | — | CURRENT — CONDITIONAL | short_answer `a_given` | yes (show rule) | `a_given` | name | Implemented |  |
| Personal 1 | Full Name in Native Alphabet | pp. 7-9 | — | CURRENT — CONDITIONAL | short_answer `a_native` | yes (show rule) | `a_native` | native | Implemented | Does Not Apply when blank. |
| Personal 1 | Date of Birth | pp. 7-9 | — | CURRENT — CONDITIONAL | date `a_dob` | yes (show rule) | `a_dob` | date | Implemented |  |
| Personal 1 | Sex | pp. 7-9 | — | CURRENT — CONDITIONAL | single_choice `a_sex` | yes (show rule) | `a_sex` | choice | Implemented |  |
| Personal 1 | City of Birth | pp. 7-9 | — | CURRENT — CONDITIONAL | short_answer `a_birth_city` | yes (show rule) | `a_birth_city` | proper | Implemented |  |
| Personal 1 | State/Province of Birth | pp. 7-9 | — | CURRENT — CONDITIONAL | short_answer `a_birth_state` | yes (show rule) | `a_birth_state` | proper | Implemented | Does Not Apply when blank. |
| Personal 1 | Country/Region of Birth | pp. 7-9 | — | CURRENT — CONDITIONAL | short_answer `a_birth_country` | yes (show rule) | `a_birth_country` | proper | Implemented |  |
| Personal 1 | Country/Region of Origin (Nationality) | pp. 7-9 | — | CURRENT — CONDITIONAL | short_answer `a_nationality` | yes (show rule) | `a_nationality` | proper | Implemented |  |
| Personal 1 | Other Names Used (Other Surnames / Other Given Names) | pp. 7-9 | — | CURRENT — CONDITIONAL | record_list `a_other_names` | yes (show rule) | `a_other_names` | records | Implemented |  |
| Personal 1 | Current Marital Status | pp. 7-9 | — | CURRENT — CONDITIONAL | single_choice `a_marital` | yes (show rule) | `a_marital` | choice | Implemented |  |

## Personal 2

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Personal 2 | Document Type | pp. 10-13 | — | CURRENT — CONDITIONAL | single_choice `a_doc_type` | yes (show rule) | `a_doc_type` | choice | Implemented |  |
| Personal 2 | Document ID | pp. 10-13 | — | CURRENT — CONDITIONAL | short_answer `a_doc_number` | yes (show rule) | `a_doc_number` | proper | Implemented |  |
| Personal 2 | Country/Authority that Issued Document | pp. 10-13 | — | CURRENT — CONDITIONAL | short_answer `a_doc_country` | yes (show rule) | `a_doc_country` | proper | Implemented |  |
| Personal 2 | Issuance Date | pp. 10-13 | — | CURRENT — CONDITIONAL | date `a_doc_issued` | yes (show rule) | `a_doc_issued` | date | Implemented |  |
| Personal 2 | Expiration Date | pp. 10-13 | — | CURRENT — CONDITIONAL | date `a_doc_expiry` | yes (show rule) | `a_doc_expiry` | date | Implemented |  |
| Personal 2 | Do you hold or have you held any nationality other than the one you have indicated above? | pp. 10-13 | — | CURRENT — IMPLEMENTED | single_choice `a_other_nat` | always | `a_other_nat` | yn | Implemented |  |
| Personal 2 | Other Country/Region of Origin | pp. 10-13 | — | CURRENT — CONDITIONAL | short_answer `a_other_nat_country` | yes (show rule) | `a_other_nat_country` | proper | Implemented |  |
| Personal 2 | Do you hold a passport from that country? | pp. 10-13 | — | CURRENT — CONDITIONAL | single_choice `a_other_nat_passport` | yes (show rule) | `a_other_nat_passport` | yn | Implemented |  |
| Personal 2 | Passport Number | pp. 10-13 | — | CURRENT — CONDITIONAL | short_answer `a_other_nat_passport_no` | yes (show rule) | `a_other_nat_passport_no` | proper | Implemented |  |

## Address and Phone

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Address and Phone | Address is in the United States (OG helper) | pp. 14-17 | — | CURRENT — DERIVED | single_choice `pa_is_us` | yes (show rule) | `pa_is_us` | proper | Implemented | OG helper, not a CEAC question. |
| Address and Phone | Street Address (Line 1) | pp. 14-17 | — | CURRENT — CONDITIONAL | short_answer `pa_street` | yes (show rule) | `pa_street` | proper | Implemented |  |
| Address and Phone | Unit type | pp. 14-17 | — | CURRENT — CONDITIONAL | dropdown `pa_unit_type` | yes (show rule) | `pa_unit_type` | proper | Implemented |  |
| Address and Phone | Street Address (Line 2) | pp. 14-17 | — | CURRENT — CONDITIONAL | short_answer `pa_unit_number` | yes (show rule) | `pa_unit_number` | proper | Implemented |  |
| Address and Phone | City | pp. 14-17 | — | CURRENT — CONDITIONAL | short_answer `pa_city` | yes (show rule) | `pa_city` | proper | Implemented |  |
| Address and Phone | State | pp. 14-17 | — | CURRENT — CONDITIONAL | dropdown `pa_state` | yes (show rule) | `pa_state` | proper | Implemented |  |
| Address and Phone | Postal Zone / ZIP Code | pp. 14-17 | — | CURRENT — CONDITIONAL | short_answer `pa_zip` | yes (show rule) | `pa_zip` | proper | Implemented |  |
| Address and Phone | State / Province | pp. 14-17 | — | CURRENT — CONDITIONAL | short_answer `pa_province` | yes (show rule) | `pa_province` | proper | Implemented |  |
| Address and Phone | Postal Zone / ZIP Code | pp. 14-17 | — | CURRENT — CONDITIONAL | short_answer `pa_postal_code` | yes (show rule) | `pa_postal_code` | proper | Implemented |  |
| Address and Phone | Country / Region | pp. 14-17 | — | CURRENT — CONDITIONAL | short_answer `pa_country` | yes (show rule) | `pa_country` | proper | Implemented |  |
| Address and Phone | Started Living Here | pp. 14-17 | — | CURRENT — CONDITIONAL | date `pa_since` | yes (show rule) | `pa_since` | month_year | Implemented |  |
| Address and Phone | Previous addresses since the age of sixteen | pp. 14-17 | — | CURRENT — CONDITIONAL | record_list `a_addr_history` | yes (show rule) | `a_addr_history` | records | Implemented |  |

## Mailing / Permanent

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Mailing / Permanent | Is your mailing address the same as your present address? | pp. 18-23 | — | CURRENT — IMPLEMENTED | single_choice `m_same` | always | `m_same` | yn | Implemented |  |
| Mailing / Permanent | Address is in the United States (OG helper) | pp. 18-23 | — | CURRENT — DERIVED | single_choice `ma_is_us` | yes (show rule) | `ma_is_us` | proper | Implemented | OG helper, not a CEAC question. |
| Mailing / Permanent | Street Address (Line 1) | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `ma_street` | yes (show rule) | `ma_street` | proper | Implemented |  |
| Mailing / Permanent | Unit type | pp. 18-23 | — | CURRENT — CONDITIONAL | dropdown `ma_unit_type` | yes (show rule) | `ma_unit_type` | proper | Implemented |  |
| Mailing / Permanent | Street Address (Line 2) | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `ma_unit_number` | yes (show rule) | `ma_unit_number` | proper | Implemented |  |
| Mailing / Permanent | City | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `ma_city` | yes (show rule) | `ma_city` | proper | Implemented |  |
| Mailing / Permanent | State | pp. 18-23 | — | CURRENT — CONDITIONAL | dropdown `ma_state` | yes (show rule) | `ma_state` | proper | Implemented |  |
| Mailing / Permanent | Postal Zone / ZIP Code | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `ma_zip` | yes (show rule) | `ma_zip` | proper | Implemented |  |
| Mailing / Permanent | State / Province | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `ma_province` | yes (show rule) | `ma_province` | proper | Implemented |  |
| Mailing / Permanent | Postal Zone / ZIP Code | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `ma_postal_code` | yes (show rule) | `ma_postal_code` | proper | Implemented |  |
| Mailing / Permanent | Country / Region | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `ma_country` | yes (show rule) | `ma_country` | proper | Implemented |  |
| Mailing / Permanent | Permanent Address in the U.S. | pp. 18-23 | — | CURRENT — DERIVED | single_choice `us_known` | always | `us_known` | yn | Implemented | OG helper, not a CEAC question. |
| Mailing / Permanent | Name of Person Currently Living at Address | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `us_person` | yes (show rule) | `us_person` | proper | Implemented | Does Not Apply when blank. |
| Mailing / Permanent | U.S. Street Address (Line 1) | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `us_street` | yes (show rule) | `us_street` | proper | Implemented |  |
| Mailing / Permanent | U.S. Street Address (Line 2) | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `us_street2` | yes (show rule) | `us_street2` | proper | Implemented |  |
| Mailing / Permanent | City | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `us_city` | yes (show rule) | `us_city` | proper | Implemented |  |
| Mailing / Permanent | State | pp. 18-23 | — | CURRENT — CONDITIONAL | dropdown `us_state` | yes (show rule) | `us_state` | choice | Implemented |  |
| Mailing / Permanent | ZIP Code | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `us_zip` | yes (show rule) | `us_zip` | proper | Implemented |  |
| Mailing / Permanent | Telephone | pp. 18-23 | — | CURRENT — CONDITIONAL | phone `us_phone` | yes (show rule) | `us_phone` | phone | Implemented | Does Not Apply when blank. |
| Mailing / Permanent | Is this address where you want your Green Card mailed? | pp. 18-23 | — | CURRENT — IMPLEMENTED | single_choice `gc_same` | always | `gc_same` | choice | Implemented |  |
| Mailing / Permanent | Contact Person Name | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `gc_person` | yes (show rule) | `gc_person` | proper | Implemented |  |
| Mailing / Permanent | Green Card Street Address (Line 1) | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `gc_street` | yes (show rule) | `gc_street` | proper | Implemented |  |
| Mailing / Permanent | Green Card Street Address (Line 2) | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `gc_street2` | yes (show rule) | `gc_street2` | proper | Implemented |  |
| Mailing / Permanent | City | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `gc_city` | yes (show rule) | `gc_city` | proper | Implemented |  |
| Mailing / Permanent | State | pp. 18-23 | — | CURRENT — CONDITIONAL | dropdown `gc_state` | yes (show rule) | `gc_state` | choice | Implemented |  |
| Mailing / Permanent | ZIP Code | pp. 18-23 | — | CURRENT — CONDITIONAL | short_answer `gc_zip` | yes (show rule) | `gc_zip` | proper | Implemented |  |
| Mailing / Permanent | Telephone | pp. 18-23 | — | CURRENT — CONDITIONAL | phone `gc_phone` | yes (show rule) | `gc_phone` | phone | Implemented | Does Not Apply when blank. |

## Address and Phone

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Address and Phone | Primary Phone Number | pp. 14-17 | — | CURRENT — CONDITIONAL | phone `a_phone_primary` | yes (show rule) | `a_phone_primary` | phone | Implemented |  |
| Address and Phone | Secondary Phone Number | pp. 14-17 | — | CURRENT — CONDITIONAL | phone `a_phone_secondary` | yes (show rule) | `a_phone_secondary` | phone | Implemented | Does Not Apply when blank. |
| Address and Phone | Work Phone Number | pp. 14-17 | — | CURRENT — CONDITIONAL | phone `a_phone_work` | yes (show rule) | `a_phone_work` | phone | Implemented | Does Not Apply when blank. |
| Address and Phone | Email Address | pp. 14-17 | — | CURRENT — CONDITIONAL | email `a_email` | yes (show rule) | `a_email` | raw | Implemented |  |
| Address and Phone | Have you used any other phone numbers in the last five years? | pp. 14-17 | — | CURRENT — IMPLEMENTED | single_choice `a_more_phones` | always | `a_more_phones` | yn | Implemented |  |
| Address and Phone | Additional Phone Number | pp. 14-17 | — | CURRENT — CONDITIONAL | record_list `a_other_phones` | yes (show rule) | `a_other_phones` | records | Implemented |  |
| Address and Phone | Have you used any other email addresses in the last five years? | pp. 14-17 | — | CURRENT — IMPLEMENTED | single_choice `a_more_emails` | always | `a_more_emails` | yn | Implemented |  |
| Address and Phone | Additional Email Address | pp. 14-17 | — | CURRENT — CONDITIONAL | record_list `a_other_emails` | yes (show rule) | `a_other_emails` | records | Implemented |  |
| Address and Phone | Social Media (select None if none) | pp. 14-17 | — | CURRENT — IMPLEMENTED | single_choice `a_social_has` | always | `a_social_has` | yn | Implemented |  |
| Address and Phone | Social Media Provider/Platform + Identifier | pp. 14-17 | Not in Federal Register notice (it covers DHS/USCIS forms) | CURRENT — CONDITIONAL | record_list `a_social` | yes (show rule) | `a_social` | records | Implemented | Provider list not visible in the sample: platform is free text, never an invented list. Rules from the 2019 sample only. |
| Address and Phone | Other Social Media | pp. 14-17 | — | CURRENT — IMPLEMENTED | single_choice `a_social_other_has` | always | `a_social_other_has` | yn | Implemented |  |
| Address and Phone | Other Social Media Provider/Platform + Identifier | pp. 14-17 | — | CURRENT — CONDITIONAL | record_list `a_social_other` | yes (show rule) | `a_social_other` | records | Implemented | 2019 sample only. |

## Family: Parents

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Family: Parents | Father | pp. 24-28 | — | CURRENT — IMPLEMENTED | record_list `pf_records` | always | `pf_records` | records | Implemented | Do Not Know permitted by the sample. |
| Family: Parents | Mother | pp. 24-28 | — | CURRENT — IMPLEMENTED | record_list `pm_records` | always | `pm_records` | records | Implemented | Do Not Know permitted by the sample. |

## Family: Spouse

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Family: Spouse | Current Spouse | pp. 29-32 | — | CURRENT — CONDITIONAL | record_list `s_records` | yes (show rule) | `s_records` | records | Implemented | Do Not Know permitted by the sample. |

## Family: Previous Spouse

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Family: Previous Spouse | Have you been married before? | pp. 33-34 | — | CURRENT — IMPLEMENTED | single_choice `ps_has` | always | `ps_has` | yn | Implemented |  |
| Family: Previous Spouse | Previous Spouse(s) | pp. 33-34 | — | CURRENT — CONDITIONAL | record_list `ps_records` | yes (show rule) | `ps_records` | records | Implemented |  |

## Family: Children

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Family: Children | Do you have any children? | pp. 35-37 | — | CURRENT — IMPLEMENTED | single_choice `k_has` | always | `k_has` | yn | Implemented |  |
| Family: Children | Children | pp. 35-37 | — | CURRENT — CONDITIONAL | record_list `k_children` | yes (show rule) | `k_children` | records | Implemented | Do Not Know permitted by the sample. |

## Previous U.S. Travel

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Previous U.S. Travel | Have you ever been in the U.S.? | pp. 38-39 | — | CURRENT — IMPLEMENTED | single_choice `t_been` | always | `t_been` | yn | Implemented |  |
| Previous U.S. Travel | Were you issued an Alien Registration Number by the Department of Homeland Security? | pp. 38-39 | — | CURRENT — CONDITIONAL | single_choice `t_arn` | yes (show rule) | `t_arn` | choice | Implemented |  |
| Previous U.S. Travel | Information on your last five U.S. visits | pp. 38-39 | — | CURRENT — CONDITIONAL | record_list `t_visits` | yes (show rule) | `t_visits` | records | Implemented |  |
| Previous U.S. Travel | Have you ever been issued a U.S. Visa? | pp. 38-39 | — | CURRENT — IMPLEMENTED | single_choice `t_visa` | always | `t_visa` | yn | Implemented |  |
| Previous U.S. Travel | Date Visa Was Issued | pp. 38-39 | — | CURRENT — CONDITIONAL | date `t_visa_date` | yes (show rule) | `t_visa_date` | date | Implemented |  |
| Previous U.S. Travel | Visa Classification | pp. 38-39 | — | CURRENT — CONDITIONAL | short_answer `t_visa_class` | yes (show rule) | `t_visa_class` | proper | Implemented | Do Not Know permitted by the sample. |
| Previous U.S. Travel | Visa Number | pp. 38-39 | — | CURRENT — CONDITIONAL | short_answer `t_visa_number` | yes (show rule) | `t_visa_number` | proper | Implemented | Do Not Know permitted by the sample. |
| Previous U.S. Travel | Have any of your U.S. visas ever been lost or stolen? | pp. 38-39 | — | CURRENT — CONDITIONAL | single_choice `t_visa_lost` | yes (show rule) | `t_visa_lost` | yn | Implemented |  |
| Previous U.S. Travel | Have any of your U.S. visas ever been cancelled or revoked? | pp. 38-39 | — | CURRENT — CONDITIONAL | single_choice `t_visa_cancel` | yes (show rule) | `t_visa_cancel` | yn | Implemented |  |
| Previous U.S. Travel | Have you ever been refused a U.S. Visa, been refused admission to the United States, or withdrawn your application for admission at the port of entry? | pp. 38-39 | — | CURRENT — IMPLEMENTED | single_choice `t_refused` | always | `t_refused` | yn | Implemented |  |
| Previous U.S. Travel | Explain | pp. 38-39 | — | CURRENT — CONDITIONAL | long_answer `t_refused_explain` | yes (show rule) | `t_refused_explain` | free | Implemented |  |

## Work/Education/Training: Present

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Work/Education/Training: Present | Primary Occupation | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | dropdown `w_occ` | yes (show rule) | `w_occ` | choice | Implemented |  |
| Work/Education/Training: Present | Specify Other | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | short_answer `w_occ_other` | yes (show rule) | `w_occ_other` | free | Implemented |  |
| Work/Education/Training: Present | Present Employer or School Name | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | short_answer `w_employer` | yes (show rule) | `w_employer` | proper | Implemented |  |
| Work/Education/Training: Present | Address is in the United States (OG helper) | pp. 40-47 (DV variants 48-50) | — | CURRENT — DERIVED | single_choice `pw_is_us` | yes (show rule) | `pw_is_us` | proper | Implemented | OG helper, not a CEAC question. |
| Work/Education/Training: Present | Street Address (Line 1) | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | short_answer `pw_street` | yes (show rule) | `pw_street` | proper | Implemented |  |
| Work/Education/Training: Present | Unit type | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | dropdown `pw_unit_type` | yes (show rule) | `pw_unit_type` | proper | Implemented |  |
| Work/Education/Training: Present | Street Address (Line 2) | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | short_answer `pw_unit_number` | yes (show rule) | `pw_unit_number` | proper | Implemented |  |
| Work/Education/Training: Present | City | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | short_answer `pw_city` | yes (show rule) | `pw_city` | proper | Implemented |  |
| Work/Education/Training: Present | State | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | dropdown `pw_state` | yes (show rule) | `pw_state` | proper | Implemented |  |
| Work/Education/Training: Present | Postal Zone / ZIP Code | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | short_answer `pw_zip` | yes (show rule) | `pw_zip` | proper | Implemented |  |
| Work/Education/Training: Present | State / Province | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | short_answer `pw_province` | yes (show rule) | `pw_province` | proper | Implemented |  |
| Work/Education/Training: Present | Postal Zone / ZIP Code | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | short_answer `pw_postal_code` | yes (show rule) | `pw_postal_code` | proper | Implemented |  |
| Work/Education/Training: Present | Country / Region | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | short_answer `pw_country` | yes (show rule) | `pw_country` | proper | Implemented |  |
| Work/Education/Training: Present | Start Date | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | date `w_start` | yes (show rule) | `w_start` | date | Implemented | Does Not Apply when blank. |
| Work/Education/Training: Present | Monthly Income in Local Currency | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | short_answer `w_income` | yes (show rule) | `w_income` | raw | Implemented | Does Not Apply when blank. |
| Work/Education/Training: Present | Briefly Describe Your Duties | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | long_answer `w_duties` | yes (show rule) | `w_duties` | free | Implemented |  |
| Work/Education/Training: Present | In which occupation do you intend to work in the U.S.? | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | dropdown `w_intend` | yes (show rule) | `w_intend` | choice | Implemented |  |
| Work/Education/Training: Present | Specify Other | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | short_answer `w_intend_other` | yes (show rule) | `w_intend_other` | free | Implemented |  |
| Work/Education/Training: Present | Do you have other occupations? | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | single_choice `w_other_has` | yes (show rule) | `w_other_has` | yn | Implemented |  |
| Work/Education/Training: Present | Other Occupation | pp. 40-47 (DV variants 48-50) | — | CURRENT — CONDITIONAL | record_list `w_other_occ` | yes (show rule) | `w_other_occ` | records | Implemented |  |

## Work/Education/Training: Previous

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Work/Education/Training: Previous | Were you previously employed? | pp. 51-58 | — | CURRENT — CONDITIONAL | single_choice `pv_has_job` | yes (show rule) | `pv_has_job` | yn | Implemented | UNVERIFIED: shown only to some applicants in the 2019 sample (visibility rule unverified) |
| Work/Education/Training: Previous | Previous employers (last ten years) | pp. 51-58 | — | CURRENT — CONDITIONAL | record_list `pv_jobs` | yes (show rule) | `pv_jobs` | records | Implemented | Do Not Know permitted by the sample. |
| Work/Education/Training: Previous | Have you attended any educational institutions at a secondary level or above? | pp. 51-58 | — | CURRENT — CONDITIONAL | single_choice `pv_has_school` | yes (show rule) | `pv_has_school` | yn | Implemented |  |
| Work/Education/Training: Previous | Educational institutions attended | pp. 51-58 | — | CURRENT — CONDITIONAL | record_list `pv_schools` | yes (show rule) | `pv_schools` | records | Implemented |  |

## Work/Education/Training: Additional

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Work/Education/Training: Additional | Have you traveled to any countries/regions, other than the United States, within the last fifteen years? | pp. 59-66 | Federal Register 2025-20231: fifteen years (sample: five) | SOURCE DISCREPANCY — REVIEWED | single_choice `aw_travel` | yes (show rule) | `aw_travel` | yn | Implemented | Newer official source used; live CEAC wording not retrievable. |
| Work/Education/Training: Additional | Countries/Regions Visited | pp. 59-66 | Federal Register 2025-20231: fifteen years | SOURCE DISCREPANCY — REVIEWED | record_list `aw_countries` | yes (show rule) | `aw_countries` | records | Implemented | List of countries visited follows the fifteen-year question. |
| Work/Education/Training: Additional | Have you ever served in the military? | pp. 59-66 | — | CURRENT — CONDITIONAL | single_choice `aw_mil` | yes (show rule) | `aw_mil` | yn | Implemented |  |
| Work/Education/Training: Additional | Military service (country, branch, rank, specialty, dates) | pp. 59-66 | — | CURRENT — CONDITIONAL | record_list `aw_mil_rec` | yes (show rule) | `aw_mil_rec` | records | Implemented |  |
| Work/Education/Training: Additional | Have you belonged to, contributed to, or worked for any professional, social, or charitable organization? | pp. 59-66 | — | CURRENT — CONDITIONAL | single_choice `aw_org` | yes (show rule) | `aw_org` | yn | Implemented | UNVERIFIED: shown only to some applicants in the 2019 sample |
| Work/Education/Training: Additional | Organization Name | pp. 59-66 | — | CURRENT — CONDITIONAL | record_list `aw_org_rec` | yes (show rule) | `aw_org_rec` | records | Implemented |  |
| Work/Education/Training: Additional | Do you have any specialized skills or training, such as firearms, explosives, nuclear, biological, or chemical experience? | pp. 59-66 | — | CURRENT — CONDITIONAL | single_choice `aw_skills` | yes (show rule) | `aw_skills` | yn | Implemented | UNVERIFIED: shown only to some applicants in the 2019 sample |
| Work/Education/Training: Additional | Explain Skills or Training | pp. 59-66 | — | CURRENT — CONDITIONAL | long_answer `aw_skills_explain` | yes (show rule) | `aw_skills_explain` | free | Implemented |  |
| Work/Education/Training: Additional | Have you ever served in, been a member of, or been involved with a paramilitary unit, vigilante unit, rebel group, guerrilla group, or insurgent organization? | pp. 59-66 | — | CURRENT — CONDITIONAL | single_choice `aw_para` | yes (show rule) | `aw_para` | yn | Implemented | UNVERIFIED: shown only to some applicants in the 2019 sample |
| Work/Education/Training: Additional | Explain | pp. 59-66 | — | CURRENT — CONDITIONAL | long_answer `aw_para_explain` | yes (show rule) | `aw_para_explain` | free | Implemented |  |
| Work/Education/Training: Additional | Can you speak and/or read languages other than your native language? | pp. 59-66 | — | CURRENT — CONDITIONAL | single_choice `aw_lang` | yes (show rule) | `aw_lang` | yn | Implemented | UNVERIFIED: shown only to some applicants in the 2019 sample |
| Work/Education/Training: Additional | List the languages that you speak and/or read | pp. 59-66 | — | CURRENT — CONDITIONAL | long_answer `aw_languages` | yes (show rule) | `aw_languages` | free | Implemented |  |

## Petitioner

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Petitioner | Petitioner is my | pp. 67-70 | — | CURRENT — IMPLEMENTED | dropdown `pt_relation` | always | `pt_relation` | choice | Implemented |  |
| Petitioner | Specify Other | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pt_other` | yes (show rule) | `pt_other` | free | Implemented |  |
| Petitioner | Petitioner Surnames | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pt_family` | yes (show rule) | `pt_family` | name | Implemented |  |
| Petitioner | Petitioner Given Names | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pt_given` | yes (show rule) | `pt_given` | name | Implemented |  |
| Petitioner | Address is in the United States (OG helper) | pp. 67-70 | — | CURRENT — DERIVED | single_choice `pta_is_us` | yes (show rule) | `pta_is_us` | proper | Implemented | OG helper, not a CEAC question. |
| Petitioner | Street Address (Line 1) | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pta_street` | yes (show rule) | `pta_street` | proper | Implemented |  |
| Petitioner | Unit type | pp. 67-70 | — | CURRENT — CONDITIONAL | dropdown `pta_unit_type` | yes (show rule) | `pta_unit_type` | proper | Implemented |  |
| Petitioner | Street Address (Line 2) | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pta_unit_number` | yes (show rule) | `pta_unit_number` | proper | Implemented |  |
| Petitioner | City | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pta_city` | yes (show rule) | `pta_city` | proper | Implemented |  |
| Petitioner | State | pp. 67-70 | — | CURRENT — CONDITIONAL | dropdown `pta_state` | yes (show rule) | `pta_state` | proper | Implemented |  |
| Petitioner | Postal Zone / ZIP Code | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pta_zip` | yes (show rule) | `pta_zip` | proper | Implemented |  |
| Petitioner | State / Province | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pta_province` | yes (show rule) | `pta_province` | proper | Implemented |  |
| Petitioner | Postal Zone / ZIP Code | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pta_postal_code` | yes (show rule) | `pta_postal_code` | proper | Implemented |  |
| Petitioner | Country / Region | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pta_country` | yes (show rule) | `pta_country` | proper | Implemented |  |
| Petitioner | Telephone | pp. 67-70 | — | CURRENT — CONDITIONAL | phone `pt_phone` | yes (show rule) | `pt_phone` | phone | Implemented |  |
| Petitioner | Mobile/Cell Telephone | pp. 67-70 | — | CURRENT — CONDITIONAL | phone `pt_mobile` | yes (show rule) | `pt_mobile` | phone | Implemented | Does Not Apply when blank. |
| Petitioner | Email Address | pp. 67-70 | — | CURRENT — CONDITIONAL | email `pt_email` | yes (show rule) | `pt_email` | raw | Implemented | Does Not Apply when blank. |
| Petitioner | Organization Name | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pt_org` | yes (show rule) | `pt_org` | proper | Implemented |  |
| Petitioner | Address is in the United States (OG helper) | pp. 67-70 | — | CURRENT — DERIVED | single_choice `pto_is_us` | yes (show rule) | `pto_is_us` | proper | Implemented | OG helper, not a CEAC question. |
| Petitioner | Street Address (Line 1) | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pto_street` | yes (show rule) | `pto_street` | proper | Implemented |  |
| Petitioner | Unit type | pp. 67-70 | — | CURRENT — CONDITIONAL | dropdown `pto_unit_type` | yes (show rule) | `pto_unit_type` | proper | Implemented |  |
| Petitioner | Street Address (Line 2) | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pto_unit_number` | yes (show rule) | `pto_unit_number` | proper | Implemented |  |
| Petitioner | City | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pto_city` | yes (show rule) | `pto_city` | proper | Implemented |  |
| Petitioner | State | pp. 67-70 | — | CURRENT — CONDITIONAL | dropdown `pto_state` | yes (show rule) | `pto_state` | proper | Implemented |  |
| Petitioner | Postal Zone / ZIP Code | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pto_zip` | yes (show rule) | `pto_zip` | proper | Implemented |  |
| Petitioner | State / Province | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pto_province` | yes (show rule) | `pto_province` | proper | Implemented |  |
| Petitioner | Postal Zone / ZIP Code | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pto_postal_code` | yes (show rule) | `pto_postal_code` | proper | Implemented |  |
| Petitioner | Country / Region | pp. 67-70 | — | CURRENT — CONDITIONAL | short_answer `pto_country` | yes (show rule) | `pto_country` | proper | Implemented |  |
| Petitioner | Telephone | pp. 67-70 | — | CURRENT — CONDITIONAL | phone `pto_phone` | yes (show rule) | `pto_phone` | phone | Implemented |  |
| Petitioner | Mobile/Cell Telephone | pp. 67-70 | — | CURRENT — CONDITIONAL | phone `pto_mobile` | yes (show rule) | `pto_mobile` | phone | Implemented | Does Not Apply when blank. |
| Petitioner | Email Address | pp. 67-70 | — | CURRENT — CONDITIONAL | email `pto_email` | yes (show rule) | `pto_email` | raw | Implemented | Does Not Apply when blank. |

## Security and Background: Medical and Health

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Security and Background: Medical and Health | Do you have a communicable disease of public health significance such as tuberculosis (TB)? | pp. 71-73 | — | CURRENT — IMPLEMENTED | single_choice `sec_med_1` | always | `sec_med_1` | yn | Implemented |  |
| Security and Background: Medical and Health | Explain | pp. 71-73 | — | CURRENT — CONDITIONAL | long_answer `sec_med_1_x` | yes (show rule) | `sec_med_1_x` | free | Implemented |  |
| Security and Background: Medical and Health | Do you have documentation to establish that you have received vaccinations in accordance with U.S. law? | pp. 71-73 | — | CURRENT — CONDITIONAL | single_choice `sec_med_2` | always | `sec_med_2` | yn | Implemented | Inverted polarity: explanation when the answer is No. |
| Security and Background: Medical and Health | Explain | pp. 71-73 | — | CURRENT — CONDITIONAL | long_answer `sec_med_2_x` | yes (show rule) | `sec_med_2_x` | free | Implemented |  |
| Security and Background: Medical and Health | Do you have a mental or physical disorder that poses or is likely to pose a threat to the safety or welfare of yourself or others? | pp. 71-73 | — | CURRENT — IMPLEMENTED | single_choice `sec_med_3` | always | `sec_med_3` | yn | Implemented |  |
| Security and Background: Medical and Health | Explain | pp. 71-73 | — | CURRENT — CONDITIONAL | long_answer `sec_med_3_x` | yes (show rule) | `sec_med_3_x` | free | Implemented |  |
| Security and Background: Medical and Health | Are you or have you ever been a drug abuser or addict? | pp. 71-73 | — | CURRENT — IMPLEMENTED | single_choice `sec_med_4` | always | `sec_med_4` | yn | Implemented |  |
| Security and Background: Medical and Health | Explain | pp. 71-73 | — | CURRENT — CONDITIONAL | long_answer `sec_med_4_x` | yes (show rule) | `sec_med_4_x` | free | Implemented |  |

## Security and Background: Criminal

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Security and Background: Criminal | Have you ever been arrested or convicted for any offense or crime, even though subject of a pardon, amnesty, or other similar action? | pp. 74-75 | — | CURRENT — IMPLEMENTED | single_choice `sec_crim_1` | always | `sec_crim_1` | yn | Implemented |  |
| Security and Background: Criminal | Explain | pp. 74-75 | — | CURRENT — CONDITIONAL | long_answer `sec_crim_1_x` | yes (show rule) | `sec_crim_1_x` | free | Implemented |  |
| Security and Background: Criminal | Have you ever violated, or engaged in a conspiracy to violate, any law relating to controlled substances? | pp. 74-75 | — | CURRENT — IMPLEMENTED | single_choice `sec_crim_2` | always | `sec_crim_2` | yn | Implemented |  |
| Security and Background: Criminal | Explain | pp. 74-75 | — | CURRENT — CONDITIONAL | long_answer `sec_crim_2_x` | yes (show rule) | `sec_crim_2_x` | free | Implemented |  |
| Security and Background: Criminal | Are you the spouse, son, or daughter of an individual who has violated any controlled substance trafficking law, and have knowingly benefited from the trafficking activities in the past five years? | pp. 74-75 | — | CURRENT — IMPLEMENTED | single_choice `sec_crim_3` | always | `sec_crim_3` | yn | Implemented |  |
| Security and Background: Criminal | Explain | pp. 74-75 | — | CURRENT — CONDITIONAL | long_answer `sec_crim_3_x` | yes (show rule) | `sec_crim_3_x` | free | Implemented |  |
| Security and Background: Criminal | Are you coming to the United States to engage in prostitution or unlawful commercialized vice or have you been engaged in prostitution or procuring prostitutes within the past 10 years? | pp. 74-75 | — | CURRENT — IMPLEMENTED | single_choice `sec_crim_4` | always | `sec_crim_4` | yn | Implemented |  |
| Security and Background: Criminal | Explain | pp. 74-75 | — | CURRENT — CONDITIONAL | long_answer `sec_crim_4_x` | yes (show rule) | `sec_crim_4_x` | free | Implemented |  |
| Security and Background: Criminal | Have you ever been involved in, or do you seek to engage in, money laundering? | pp. 74-75 | — | CURRENT — IMPLEMENTED | single_choice `sec_crim_5` | always | `sec_crim_5` | yn | Implemented |  |
| Security and Background: Criminal | Explain | pp. 74-75 | — | CURRENT — CONDITIONAL | long_answer `sec_crim_5_x` | yes (show rule) | `sec_crim_5_x` | free | Implemented |  |
| Security and Background: Criminal | Have you ever committed or conspired to commit a human trafficking offense in the United States or outside the United States? | pp. 74-75 | — | CURRENT — IMPLEMENTED | single_choice `sec_crim_6` | always | `sec_crim_6` | yn | Implemented |  |
| Security and Background: Criminal | Explain | pp. 74-75 | — | CURRENT — CONDITIONAL | long_answer `sec_crim_6_x` | yes (show rule) | `sec_crim_6_x` | free | Implemented |  |
| Security and Background: Criminal | Have you ever knowingly aided, abetted, assisted, or colluded with an individual who has been identified by the President of the United States as a person who plays a significant role in a severe form of trafficking in persons? | pp. 74-75 | — | CURRENT — IMPLEMENTED | single_choice `sec_crim_7` | always | `sec_crim_7` | yn | Implemented |  |
| Security and Background: Criminal | Explain | pp. 74-75 | — | CURRENT — CONDITIONAL | long_answer `sec_crim_7_x` | yes (show rule) | `sec_crim_7_x` | free | Implemented |  |
| Security and Background: Criminal | Are you the spouse, son, or daughter of an individual who has committed or conspired to commit a human trafficking offense in the United States or outside the United States and have you within the last five years, knowingly benefited from the trafficking activities? | pp. 74-75 | — | CURRENT — IMPLEMENTED | single_choice `sec_crim_8` | always | `sec_crim_8` | yn | Implemented |  |
| Security and Background: Criminal | Explain | pp. 74-75 | — | CURRENT — CONDITIONAL | long_answer `sec_crim_8_x` | yes (show rule) | `sec_crim_8_x` | free | Implemented |  |

## Security and Background: Security 1

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Security and Background: Security 1 | Do you seek to engage in espionage, sabotage, export control violations, or any other illegal activity while in the United States? | pp. 76-78 | — | CURRENT — IMPLEMENTED | single_choice `sec_s1_1` | always | `sec_s1_1` | yn | Implemented |  |
| Security and Background: Security 1 | Explain | pp. 76-78 | — | CURRENT — CONDITIONAL | long_answer `sec_s1_1_x` | yes (show rule) | `sec_s1_1_x` | free | Implemented |  |
| Security and Background: Security 1 | Do you seek to engage in terrorist activities while in the United States or have you ever engaged in terrorist activities? | pp. 76-78 | — | CURRENT — IMPLEMENTED | single_choice `sec_s1_2` | always | `sec_s1_2` | yn | Implemented |  |
| Security and Background: Security 1 | Explain | pp. 76-78 | — | CURRENT — CONDITIONAL | long_answer `sec_s1_2_x` | yes (show rule) | `sec_s1_2_x` | free | Implemented |  |
| Security and Background: Security 1 | Have you ever or do you intend to provide financial assistance or other support to terrorists or terrorist organizations? | pp. 76-78 | — | CURRENT — IMPLEMENTED | single_choice `sec_s1_3` | always | `sec_s1_3` | yn | Implemented |  |
| Security and Background: Security 1 | Explain | pp. 76-78 | — | CURRENT — CONDITIONAL | long_answer `sec_s1_3_x` | yes (show rule) | `sec_s1_3_x` | free | Implemented |  |
| Security and Background: Security 1 | Are you the spouse, son, or daughter of an individual who has engaged in terrorist activity, including providing financial assistance or other support to terrorists or terrorist organizations, in the last five years? | pp. 76-78 | — | SOURCE DISCREPANCY — REVIEWED | single_choice `sec_s1_4` | always | `sec_s1_4` | yn | Implemented | Present on the sample's No screen (p.77), missing on its Yes screen (p.78); kept. |
| Security and Background: Security 1 | Explain | pp. 76-78 | — | CURRENT — CONDITIONAL | long_answer `sec_s1_4_x` | yes (show rule) | `sec_s1_4_x` | free | Implemented |  |
| Security and Background: Security 1 | Are you a member or representative of a terrorist organization? | pp. 76-78 | — | CURRENT — IMPLEMENTED | single_choice `sec_s1_5` | always | `sec_s1_5` | yn | Implemented |  |
| Security and Background: Security 1 | Explain | pp. 76-78 | — | CURRENT — CONDITIONAL | long_answer `sec_s1_5_x` | yes (show rule) | `sec_s1_5_x` | free | Implemented |  |
| Security and Background: Security 1 | Have you ever ordered, incited, committed, assisted, or otherwise participated in genocide? | pp. 76-78 | — | CURRENT — IMPLEMENTED | single_choice `sec_s1_6` | always | `sec_s1_6` | yn | Implemented |  |
| Security and Background: Security 1 | Explain | pp. 76-78 | — | CURRENT — CONDITIONAL | long_answer `sec_s1_6_x` | yes (show rule) | `sec_s1_6_x` | free | Implemented |  |
| Security and Background: Security 1 | Have you ever committed, ordered, incited, assisted, or otherwise participated in torture? | pp. 76-78 | — | CURRENT — IMPLEMENTED | single_choice `sec_s1_7` | always | `sec_s1_7` | yn | Implemented |  |
| Security and Background: Security 1 | Explain | pp. 76-78 | — | CURRENT — CONDITIONAL | long_answer `sec_s1_7_x` | yes (show rule) | `sec_s1_7_x` | free | Implemented |  |
| Security and Background: Security 1 | Have you committed, ordered, incited, assisted, or otherwise participated in extrajudicial killings, political killings, or other acts of violence? | pp. 76-78 | — | CURRENT — IMPLEMENTED | single_choice `sec_s1_8` | always | `sec_s1_8` | yn | Implemented |  |
| Security and Background: Security 1 | Explain | pp. 76-78 | — | CURRENT — CONDITIONAL | long_answer `sec_s1_8_x` | yes (show rule) | `sec_s1_8_x` | free | Implemented |  |
| Security and Background: Security 1 | Have you ever engaged in the recruitment of or the use of child soldiers? | pp. 76-78 | — | CURRENT — IMPLEMENTED | single_choice `sec_s1_9` | always | `sec_s1_9` | yn | Implemented |  |
| Security and Background: Security 1 | Explain | pp. 76-78 | — | CURRENT — CONDITIONAL | long_answer `sec_s1_9_x` | yes (show rule) | `sec_s1_9_x` | free | Implemented |  |
| Security and Background: Security 1 | Have you, while serving as a government official, been responsible for or directly carried out, at any time, particularly severe violations of religious freedom? | pp. 76-78 | — | CURRENT — IMPLEMENTED | single_choice `sec_s1_10` | always | `sec_s1_10` | yn | Implemented |  |
| Security and Background: Security 1 | Explain | pp. 76-78 | — | CURRENT — CONDITIONAL | long_answer `sec_s1_10_x` | yes (show rule) | `sec_s1_10_x` | free | Implemented |  |

## Security and Background: Security 2

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Security and Background: Security 2 | Are you a member of or affiliated with the Communist or other totalitarian party? | pp. 79-80 | — | CURRENT — IMPLEMENTED | single_choice `sec_s2_1` | always | `sec_s2_1` | yn | Implemented |  |
| Security and Background: Security 2 | Explain | pp. 79-80 | — | CURRENT — CONDITIONAL | long_answer `sec_s2_1_x` | yes (show rule) | `sec_s2_1_x` | free | Implemented |  |
| Security and Background: Security 2 | Have you ever directly or indirectly assisted or supported any of the groups in Colombia known as the Revolutionary Armed Forces of Colombia (FARC), National Liberation Army (ELN), or United Self-Defense Forces of Colombia (AUC)? | pp. 79-80 | — | CURRENT — IMPLEMENTED | single_choice `sec_s2_2` | always | `sec_s2_2` | yn | Implemented |  |
| Security and Background: Security 2 | Explain | pp. 79-80 | — | CURRENT — CONDITIONAL | long_answer `sec_s2_2_x` | yes (show rule) | `sec_s2_2_x` | free | Implemented |  |
| Security and Background: Security 2 | Have you ever, through abuse of governmental or political position converted for personal gain, confiscated or expropriated property in a foreign nation to which a United States national had claim of ownership? | pp. 79-80 | — | CURRENT — IMPLEMENTED | single_choice `sec_s2_3` | always | `sec_s2_3` | yn | Implemented |  |
| Security and Background: Security 2 | Explain | pp. 79-80 | — | CURRENT — CONDITIONAL | long_answer `sec_s2_3_x` | yes (show rule) | `sec_s2_3_x` | free | Implemented |  |
| Security and Background: Security 2 | Are you the spouse, minor child, or agent of an individual who has through abuse of governmental or political position converted for personal gain, confiscated or expropriated property in a foreign nation to which a United States national had claim of ownership? | pp. 79-80 | — | CURRENT — IMPLEMENTED | single_choice `sec_s2_4` | always | `sec_s2_4` | yn | Implemented |  |
| Security and Background: Security 2 | Explain | pp. 79-80 | — | CURRENT — CONDITIONAL | long_answer `sec_s2_4_x` | yes (show rule) | `sec_s2_4_x` | free | Implemented |  |
| Security and Background: Security 2 | Have you ever been directly involved in the establishment or enforcement of population controls forcing a woman to undergo an abortion against her free choice or a man or a woman to undergo sterilization against his or her free choice? | pp. 79-80 | — | CURRENT — IMPLEMENTED | single_choice `sec_s2_5` | always | `sec_s2_5` | yn | Implemented |  |
| Security and Background: Security 2 | Explain | pp. 79-80 | — | CURRENT — CONDITIONAL | long_answer `sec_s2_5_x` | yes (show rule) | `sec_s2_5_x` | free | Implemented |  |
| Security and Background: Security 2 | Have you ever disclosed or trafficked in confidential U.S. business information obtained in connection with U.S. participation in the Chemical Weapons Convention? | pp. 79-80 | — | CURRENT — IMPLEMENTED | single_choice `sec_s2_6` | always | `sec_s2_6` | yn | Implemented |  |
| Security and Background: Security 2 | Explain | pp. 79-80 | — | CURRENT — CONDITIONAL | long_answer `sec_s2_6_x` | yes (show rule) | `sec_s2_6_x` | free | Implemented |  |
| Security and Background: Security 2 | Are you the spouse, minor child, or agent of an individual who has disclosed or trafficked in confidential U.S. business information obtained in connection with U.S. participation in the Chemical Weapons Convention? | pp. 79-80 | — | CURRENT — IMPLEMENTED | single_choice `sec_s2_7` | always | `sec_s2_7` | yn | Implemented |  |
| Security and Background: Security 2 | Explain | pp. 79-80 | — | CURRENT — CONDITIONAL | long_answer `sec_s2_7_x` | yes (show rule) | `sec_s2_7_x` | free | Implemented |  |

## Security and Background: Immigration Law Violations 1

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Security and Background: Immigration Law Violations 1 | Have you ever sought to obtain or assist others to obtain a visa, entry into the United States, or any other United States immigration benefit by fraud or willful misrepresentation or other unlawful means? | pp. 81-85 | — | CURRENT — IMPLEMENTED | single_choice `sec_i1_1` | always | `sec_i1_1` | yn | Implemented |  |
| Security and Background: Immigration Law Violations 1 | Explain | pp. 81-85 | — | CURRENT — CONDITIONAL | long_answer `sec_i1_1_x` | yes (show rule) | `sec_i1_1_x` | free | Implemented |  |
| Security and Background: Immigration Law Violations 1 | Have you ever been removed or deported from any country? | pp. 81-85 | — | CURRENT — IMPLEMENTED | single_choice `sec_i1_2` | always | `sec_i1_2` | yn | Implemented |  |
| Security and Background: Immigration Law Violations 1 | Explain | pp. 81-85 | — | CURRENT — CONDITIONAL | long_answer `sec_i1_2_x` | yes (show rule) | `sec_i1_2_x` | free | Implemented |  |
| Security and Background: Immigration Law Violations 1 | Have you ever been the subject of a removal or deportation hearing? | pp. 81-85 | — | CURRENT — CONDITIONAL | single_choice `sec_i1_3` | yes (show rule) | `sec_i1_3` | yn | Implemented |  |
| Security and Background: Immigration Law Violations 1 | Explain | pp. 81-85 | — | CURRENT — CONDITIONAL | long_answer `sec_i1_3_x` | yes (show rule) | `sec_i1_3_x` | free | Implemented |  |
| Security and Background: Immigration Law Violations 1 | Have you failed to attend a hearing on removability or inadmissibility within the last five years? | pp. 81-85 | — | CURRENT — CONDITIONAL | single_choice `sec_i1_4` | yes (show rule) | `sec_i1_4` | yn | Implemented |  |
| Security and Background: Immigration Law Violations 1 | Explain | pp. 81-85 | — | CURRENT — CONDITIONAL | long_answer `sec_i1_4_x` | yes (show rule) | `sec_i1_4_x` | free | Implemented |  |
| Security and Background: Immigration Law Violations 1 | Have you ever been unlawfully present, overstayed the amount of time granted by an immigration official or otherwise violated the terms of a U.S. visa? | pp. 81-85 | — | CURRENT — CONDITIONAL | single_choice `sec_i1_5` | yes (show rule) | `sec_i1_5` | yn | Implemented |  |
| Security and Background: Immigration Law Violations 1 | Explain | pp. 81-85 | — | CURRENT — CONDITIONAL | long_answer `sec_i1_5_x` | yes (show rule) | `sec_i1_5_x` | free | Implemented |  |
| Security and Background: Immigration Law Violations 1 | Are you subject to a civil penalty under INA 274C? | pp. 81-85 | — | CURRENT — CONDITIONAL | single_choice `sec_i1_6` | yes (show rule) | `sec_i1_6` | yn | Implemented |  |
| Security and Background: Immigration Law Violations 1 | Explain | pp. 81-85 | — | CURRENT — CONDITIONAL | long_answer `sec_i1_6_x` | yes (show rule) | `sec_i1_6_x` | free | Implemented |  |
| Security and Background: Immigration Law Violations 1 | Have you been ordered removed from the U.S. during the last five years? | pp. 81-85 | — | CURRENT — CONDITIONAL | single_choice `sec_i1_7` | yes (show rule) | `sec_i1_7` | yn | Implemented |  |
| Security and Background: Immigration Law Violations 1 | Explain | pp. 81-85 | — | CURRENT — CONDITIONAL | long_answer `sec_i1_7_x` | yes (show rule) | `sec_i1_7_x` | free | Implemented |  |
| Security and Background: Immigration Law Violations 1 | Have you been ordered removed from the U.S. for a second time within the last 20 years? | pp. 81-85 | — | CURRENT — CONDITIONAL | single_choice `sec_i1_8` | yes (show rule) | `sec_i1_8` | yn | Implemented |  |
| Security and Background: Immigration Law Violations 1 | Explain | pp. 81-85 | — | CURRENT — CONDITIONAL | long_answer `sec_i1_8_x` | yes (show rule) | `sec_i1_8_x` | free | Implemented |  |

## Security and Background: Immigration Law Violations 2

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Security and Background: Immigration Law Violations 2 | Have you ever been unlawfully present and ordered removed from the U.S. during the last ten years? | pp. 86-87 | — | CURRENT — CONDITIONAL | single_choice `sec_i2_1` | yes (show rule) | `sec_i2_1` | yn | Implemented |  |
| Security and Background: Immigration Law Violations 2 | Explain | pp. 86-87 | — | CURRENT — CONDITIONAL | long_answer `sec_i2_1_x` | yes (show rule) | `sec_i2_1_x` | free | Implemented |  |
| Security and Background: Immigration Law Violations 2 | Have you ever been convicted of an aggravated felony and been ordered removed from the U.S.? | pp. 86-87 | — | CURRENT — CONDITIONAL | single_choice `sec_i2_2` | yes (show rule) | `sec_i2_2` | yn | Implemented |  |
| Security and Background: Immigration Law Violations 2 | Explain | pp. 86-87 | — | CURRENT — CONDITIONAL | long_answer `sec_i2_2_x` | yes (show rule) | `sec_i2_2_x` | free | Implemented |  |
| Security and Background: Immigration Law Violations 2 | Have you ever been unlawfully present in the U.S. for more than 180 days (but no more than one year) and have voluntarily departed the U.S. within the last three years? | pp. 86-87 | — | CURRENT — CONDITIONAL | single_choice `sec_i2_3` | yes (show rule) | `sec_i2_3` | yn | Implemented |  |
| Security and Background: Immigration Law Violations 2 | Explain | pp. 86-87 | — | CURRENT — CONDITIONAL | long_answer `sec_i2_3_x` | yes (show rule) | `sec_i2_3_x` | free | Implemented |  |
| Security and Background: Immigration Law Violations 2 | Have you ever been unlawfully present in the U.S. for more than one year or more than one year in the aggregate at any time during the last 10 years? | pp. 86-87 | — | CURRENT — CONDITIONAL | single_choice `sec_i2_4` | yes (show rule) | `sec_i2_4` | yn | Implemented |  |
| Security and Background: Immigration Law Violations 2 | Explain | pp. 86-87 | — | CURRENT — CONDITIONAL | long_answer `sec_i2_4_x` | yes (show rule) | `sec_i2_4_x` | free | Implemented |  |

## Security and Background: Miscellaneous 1

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Security and Background: Miscellaneous 1 | Have you ever withheld custody of a U.S. citizen child outside the United States from a person granted legal custody by a U.S. court? | pp. 88-89 | — | CURRENT — IMPLEMENTED | single_choice `sec_m1_1` | always | `sec_m1_1` | yn | Implemented |  |
| Security and Background: Miscellaneous 1 | Explain | pp. 88-89 | — | CURRENT — CONDITIONAL | long_answer `sec_m1_1_x` | yes (show rule) | `sec_m1_1_x` | free | Implemented |  |
| Security and Background: Miscellaneous 1 | Have you ever intentionally assisted another person in withholding custody of a U.S. citizen child outside the United States from a person granted legal custody by a U.S. court? | pp. 88-89 | — | CURRENT — IMPLEMENTED | single_choice `sec_m1_2` | always | `sec_m1_2` | yn | Implemented |  |
| Security and Background: Miscellaneous 1 | Explain | pp. 88-89 | — | CURRENT — CONDITIONAL | long_answer `sec_m1_2_x` | yes (show rule) | `sec_m1_2_x` | free | Implemented |  |
| Security and Background: Miscellaneous 1 | Have you voted in the United States in violation of any law or regulation? | pp. 88-89 | — | CURRENT — IMPLEMENTED | single_choice `sec_m1_3` | always | `sec_m1_3` | yn | Implemented |  |
| Security and Background: Miscellaneous 1 | Explain | pp. 88-89 | — | CURRENT — CONDITIONAL | long_answer `sec_m1_3_x` | yes (show rule) | `sec_m1_3_x` | free | Implemented |  |
| Security and Background: Miscellaneous 1 | Have you ever renounced United States citizenship for the purpose of avoiding taxation? | pp. 88-89 | — | CURRENT — IMPLEMENTED | single_choice `sec_m1_4` | always | `sec_m1_4` | yn | Implemented |  |
| Security and Background: Miscellaneous 1 | Explain | pp. 88-89 | — | CURRENT — CONDITIONAL | long_answer `sec_m1_4_x` | yes (show rule) | `sec_m1_4_x` | free | Implemented |  |
| Security and Background: Miscellaneous 1 | Have you attended a public elementary school or a public secondary school on student (F) status after November 30, 1996 without reimbursing the school? | pp. 88-89 | — | CURRENT — IMPLEMENTED | single_choice `sec_m1_5` | always | `sec_m1_5` | yn | Implemented |  |
| Security and Background: Miscellaneous 1 | Explain | pp. 88-89 | — | CURRENT — CONDITIONAL | long_answer `sec_m1_5_x` | yes (show rule) | `sec_m1_5_x` | free | Implemented |  |
| Security and Background: Miscellaneous 1 | Do you seek to enter the United States for the purpose of performing skilled or unskilled labor but have not yet been certified by the Secretary of Labor? | pp. 88-89 | — | CURRENT — IMPLEMENTED | single_choice `sec_m1_6` | always | `sec_m1_6` | yn | Implemented |  |
| Security and Background: Miscellaneous 1 | Explain | pp. 88-89 | — | CURRENT — CONDITIONAL | long_answer `sec_m1_6_x` | yes (show rule) | `sec_m1_6_x` | free | Implemented |  |
| Security and Background: Miscellaneous 1 | Are you a graduate of a foreign medical school seeking to perform medical services in the United States but have not yet passed the National Board of Medical Examiners examination or its equivalent? | pp. 88-89 | — | CURRENT — IMPLEMENTED | single_choice `sec_m1_7` | always | `sec_m1_7` | yn | Implemented |  |
| Security and Background: Miscellaneous 1 | Explain | pp. 88-89 | — | CURRENT — CONDITIONAL | long_answer `sec_m1_7_x` | yes (show rule) | `sec_m1_7_x` | free | Implemented |  |

## Security and Background: Miscellaneous 2

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Security and Background: Miscellaneous 2 | Are you a health care worker seeking to perform such work in the United States but have not yet received certification from the Commission on Graduates of Foreign Nursing Schools or from an equivalent approved independent credentialing organization? | pp. 90-93 | — | CURRENT — IMPLEMENTED | single_choice `sec_m2_1` | always | `sec_m2_1` | yn | Implemented |  |
| Security and Background: Miscellaneous 2 | Explain | pp. 90-93 | — | CURRENT — CONDITIONAL | long_answer `sec_m2_1_x` | yes (show rule) | `sec_m2_1_x` | free | Implemented |  |
| Security and Background: Miscellaneous 2 | Are you permanently ineligible for U.S. citizenship? | pp. 90-93 | — | CURRENT — IMPLEMENTED | single_choice `sec_m2_2` | always | `sec_m2_2` | yn | Implemented |  |
| Security and Background: Miscellaneous 2 | Explain | pp. 90-93 | — | CURRENT — CONDITIONAL | long_answer `sec_m2_2_x` | yes (show rule) | `sec_m2_2_x` | free | Implemented |  |
| Security and Background: Miscellaneous 2 | Have you ever departed the United States in order to evade military service during a time of war? | pp. 90-93 | — | CURRENT — IMPLEMENTED | single_choice `sec_m2_3` | always | `sec_m2_3` | yn | Implemented |  |
| Security and Background: Miscellaneous 2 | Explain | pp. 90-93 | — | CURRENT — CONDITIONAL | long_answer `sec_m2_3_x` | yes (show rule) | `sec_m2_3_x` | free | Implemented |  |
| Security and Background: Miscellaneous 2 | Are you coming to the U.S. to practice polygamy? | pp. 90-93 | — | CURRENT — IMPLEMENTED | single_choice `sec_m2_4` | always | `sec_m2_4` | yn | Implemented |  |
| Security and Background: Miscellaneous 2 | Explain | pp. 90-93 | — | CURRENT — CONDITIONAL | long_answer `sec_m2_4_x` | yes (show rule) | `sec_m2_4_x` | free | Implemented |  |
| Security and Background: Miscellaneous 2 | Are you a former exchange visitor (J) who has not yet fulfilled the two-year foreign residence requirement? | pp. 90-93 | — | CURRENT — IMPLEMENTED | single_choice `sec_m2_5` | always | `sec_m2_5` | yn | Implemented |  |
| Security and Background: Miscellaneous 2 | Explain | pp. 90-93 | — | CURRENT — CONDITIONAL | long_answer `sec_m2_5_x` | yes (show rule) | `sec_m2_5_x` | free | Implemented |  |
| Security and Background: Miscellaneous 2 | Has an immigration judge or the Board of Immigration Appeals ever determined that you knowingly made a frivolous application for asylum? | pp. 90-93 | Federal Register 2025-20231: immigration judge or Board of Immigration Appeals (sample: Secretary of Homeland Security) | SOURCE DISCREPANCY — REVIEWED | single_choice `sec_m2_6` | always | `sec_m2_6` | yn | Implemented | Exact CEAC sentence unverified; staff read the live question. |
| Security and Background: Miscellaneous 2 | Explain | pp. 90-93 | — | CURRENT — CONDITIONAL | long_answer `sec_m2_6_x` | yes (show rule) | `sec_m2_6_x` | free | Implemented |  |
| Security and Background: Miscellaneous 2 | Are you likely to become a public charge after you are admitted to the United States? | pp. 90-93 | — | CURRENT — IMPLEMENTED | single_choice `sec_m2_7` | always | `sec_m2_7` | yn | Implemented |  |
| Security and Background: Miscellaneous 2 | Explain | pp. 90-93 | — | CURRENT — CONDITIONAL | long_answer `sec_m2_7_x` | yes (show rule) | `sec_m2_7_x` | free | Implemented |  |

## Social Security Number

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Social Security Number | Have you ever applied for a Social Security number? | pp. 94-96 | — | CURRENT — IMPLEMENTED | single_choice `ssn_applied` | always | `ssn_applied` | yn | Implemented |  |
| Social Security Number | Were you issued a number? | pp. 94-96 | — | CURRENT — CONDITIONAL | single_choice `ssn_issued` | yes (show rule) | `ssn_issued` | yn | Implemented |  |
| Social Security Number | Social Security Number | pp. 94-96 | — | CURRENT — CONDITIONAL | short_answer `ssn_number` | yes (show rule) | `ssn_number` | ssn | Implemented | Do Not Know permitted by the sample. |
| Social Security Number | Do Not Know (Social Security number) | pp. 94-96 | — | CURRENT — CONDITIONAL | multi_choice `ssn_dk` | yes (show rule) | `ssn_dk` | choice | Implemented |  |
| Social Security Number | Do you need a new card issued? | pp. 94-96 | — | CURRENT — CONDITIONAL | single_choice `ssn_card` | yes (show rule) | `ssn_card` | yn | Implemented |  |
| Social Security Number | Do you want the Social Security Administration to issue a Social Security number and a card? | pp. 94-96 | — | CURRENT — CONDITIONAL | single_choice `ssn_want` | yes (show rule) | `ssn_want` | yn | Implemented |  |
| Social Security Number | Do you authorize disclosure of information from this form to the Department of Homeland Security, the Social Security Administration...? | pp. 94-96 | — | CURRENT — IMPLEMENTED | single_choice `ssn_consent` | always | `ssn_consent` | yn | Implemented |  |

## Sign and Submit (preparer of application)

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Sign and Submit (preparer of application) | Did anyone assist you in filling out this application? | pp. 97-103 | — | CURRENT — IMPLEMENTED | single_choice `as_helped` | always | `as_helped` | choice | Implemented |  |
| Sign and Submit (preparer of application) | Preparer (other) | pp. 97-103 | — | CURRENT — CONDITIONAL | short_answer `as_other_name` | yes (show rule) | `as_other_name` | name | Implemented |  |
| Sign and Submit (preparer of application) | Relationship to You | pp. 97-103 | — | CURRENT — CONDITIONAL | short_answer `as_other_rel` | yes (show rule) | `as_other_rel` | free | Implemented |  |

## CEAC-only, not applicable, not built and discrepancies

| Section | Question | 2019 Sample | Newer Official Source | Current status | OG component | Conditional rule | Canonical key | CEAC-ready mapping | Implementation status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Getting Started | Instructions, English-characters notice, INA 222(e) notice, acknowledgement checkbox | pp. 6 | — | NOT APPLICABLE TO OG PREPARATION | Static text on the intake intro | n/a | — | — | Implemented (informational) | The English/English-characters rule is explained to the customer; the checkbox is CEAC's. |
| Sign in / Summary | Sign-in pages, case summary page | pp. 2-5 | — | NOT APPLICABLE TO OG PREPARATION | — | n/a | — | — | n/a | OG never signs in to CEAC and never stores CEAC credentials. |
| Sign and Submit | Read-before-signing text, E-Signature and certification, Sign and Submit Application | pp. 97-103 | FR 2025-20231 adds a Medical Examination Disclosure and Consent | SIGN/SUBMIT — CEAC ONLY | Explained on the intake (assist_cert) and in the CEAC view | n/a | — | — | Never collected | Applicant only, in CEAC. |
| Sign and Submit | NVC case number, passport number and CAPTCHA entered at signing | pp. 99, 103 | — | SIGN/SUBMIT — CEAC ONLY | — | n/a | — | — | Never collected | Case number is stored only as masked case data, never as an answer. |
| Sign and Submit | FGM/C fact-sheet certification (2019 list of 30 countries) | p. 102 | not verifiable | SOURCE DISCREPANCY — REVIEWED | Flag `c_fgmc` in the admin view | 2019 nationality list | `c_fgmc` | — | Flag only | Newer country list unverified; never used to hide or add a customer question. |
| Sign and Submit | Selective Service notice (male 18-25) | p. 103 | — | SIGN/SUBMIT — CEAC ONLY | Informational text only | n/a | — | — | Informational | Nothing collected. |
| Sign and Submit | Did anyone assist you? — preparer surnames, given names, organization, address, relationship | pp. 97-99 | — | CURRENT — CONDITIONAL | `as_helped`, `as_other_*`, preparer defaults from `business_info.PREPARER_*` | yes | `as_helped` | choice | Implemented | Never states attorney/accredited status. |
| Confirmation | Confirmation page (print/email) | pp. 104-108 | — | NOT APPLICABLE TO OG PREPARATION | — | n/a | — | — | n/a | CEAC only. |
| Legal pages | Copyright, Disclaimer, Paperwork Reduction Act | pp. 109-111 | — | NOT APPLICABLE TO OG PREPARATION | — | n/a | — | — | n/a |  |
| Work/Education/Training | Diversity-Visa principal-only work pages | pp. 48-50, 56-58 | — | NOT BUILT | — | DV principal + occupation rules | — | — | Not built | Read from captions only; DV is out of the scope of this phase. Must be reviewed before DV cases are accepted. |
| Work/Education/Training | Afghanistan / Iraq nationality-specific additional questions | pp. 53-55, 61-62 | — | NOT BUILT | — | nationality rule (2019) | — | — | Not built | Read from captions only; these follow-ups were not viewed in detail. OG asks the general additional questions of everyone. |
| Personal 1/2 | Dropdown values (marital status, document type, visa classes, relationships, termination reasons) | pp. 7-13, 29-34, 38-39 | — | SOURCE DISCREPANCY — REVIEWED | Option lists in `ds260_text.py` | — | — | choice | Implemented | Dropdown lists were collapsed in the sample; OG lists are working lists and staff select the live CEAC value. |

## Totals

276 customer-facing questions mapped to CEAC. CURRENT — CONDITIONAL: 206; CURRENT — DERIVED: 6; CURRENT — IMPLEMENTED: 60; SOURCE DISCREPANCY — REVIEWED: 4.

Calculated/system values (age, address-history start, section-visibility hints, Security review counts, preparer defaults, FGM/C flag) are CURRENT — DERIVED and are never questions.
