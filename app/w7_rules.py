"""Form W-7 evidence rules, transcribed from the supplied "Instructions for Form W-7 (Rev. December 2024)" (page numbers are of that PDF).

Nothing here is an IRS eligibility determination. It answers three DIFFERENT questions that are never mixed up:

  ACCEPTED BY THE IRS        which documents establish identity / foreign status (instructions p. 4 table) and which dependent residency evidence applies (p. 4)
  CAN OG (AS A CAA) VERIFY   p. 6: a CAA can verify originals for primary and secondary applicants (except foreign military ID); for DEPENDENTS only passports and
                             birth certificates
  ORIGINAL MUST BE PROVIDED  p. 3-4: original documents (or certified copies) must be provided; OG's workflow needs the physical original of every document that
                             supports the W-7 (a photo upload is only a pre-review copy)

The photo column is OG's practical reading: the table says "at least one document must contain your photograph"; it does not list which documents carry one.
Only the USCIS "photo identification" and the national ID ("must contain name, photograph, ...") say so in the table itself (`photo_source`). A CAA confirms the
photograph on the physical document.
"""

from datetime import date

# key -> (English, Spanish, foreign_status, identity, photo, photo_source, us_document)
#   foreign_status: True | "if_foreign" (the table's ** footnote: only when the document is foreign) | False
EVIDENCE = {
    "passport": ("Passport", "Pasaporte", True, True, True, False, False),
    "uscis_photo_id": ("USCIS photo identification", "Identificación con foto de USCIS", True, True, True, True, True),
    "us_visa": ("U.S. visa issued by the Department of State", "Visa de EE. UU. emitida por el Departamento de Estado", True, True, True, False, True),
    "us_dl": ("U.S. driver's license", "Licencia de conducir de EE. UU.", False, True, True, False, True),
    "us_military_id": ("U.S. military identification card", "Identificación militar de EE. UU.", False, True, True, False, True),
    "foreign_dl": ("Foreign driver's license", "Licencia de conducir extranjera", False, True, True, False, False),
    "foreign_military_id": ("Foreign military identification card", "Identificación militar extranjera", True, True, True, False, False),
    "national_id": ("National identification card (must contain name, photograph, address, date of birth and expiration date)",
                    "Cédula o documento nacional de identidad (debe tener nombre, fotografía, dirección, fecha de nacimiento y fecha de vencimiento)", True, True, True, True, False),
    "us_state_id": ("U.S. state identification card", "Identificación estatal de EE. UU.", False, True, True, False, True),
    "foreign_voter_card": ("Foreign voter's registration card", "Tarjeta de registro de votante extranjera", True, True, None, False, False),
    "birth_certificate": ("Civil birth certificate", "Acta de nacimiento civil", "if_foreign", True, False, False, False),
    "medical_record": ("Medical record (valid only for dependents under age 6)", "Registro médico (válido solo para dependientes menores de 6 años)", "if_foreign", True, False, False, False),
    "school_record": ("School record (valid only for a dependent under age 24, if a student)", "Registro escolar (válido solo para un dependiente menor de 24 años, si es estudiante)", "if_foreign", True, False, False, False),
}
# residency-only evidence for dependents 18+ (instructions p. 4): not in the identity table
RESIDENCY_ONLY = {
    "us_bank_statement": ("U.S. bank statement showing the applicant's name and U.S. address", "Estado de cuenta bancario de EE. UU. con el nombre y la dirección en EE. UU. del solicitante"),
    "us_rental_statement": ("U.S. rental statement for a U.S. property showing the applicant's name and U.S. address", "Recibo o contrato de alquiler de EE. UU. con el nombre y la dirección en EE. UU. del solicitante"),
    "us_utility_bill": ("U.S. utility bill for a U.S. property showing the applicant's name and U.S. address", "Factura de servicios de EE. UU. con el nombre y la dirección en EE. UU. del solicitante"),
}
ALL_DOC_LABELS = {**{k: (v[0], v[1]) for k, v in EVIDENCE.items()}, **RESIDENCY_ONLY}
PAGE = {"table": "Instructions p. 4", "caa": "Instructions p. 6", "residency": "Instructions p. 4", "medical_school": "Instructions p. 4 and 16"}

# documents a customer WITHOUT a passport may say they have (the source list; nothing is invented)
NO_PASSPORT_CHOICES = ["national_id", "birth_certificate", "foreign_dl", "us_dl", "us_state_id", "us_visa", "uscis_photo_id", "foreign_voter_card", "foreign_military_id", "us_military_id"]


def age_on(dob, on=None):
    on = on or date.today()
    if dob is None or dob > on:
        return None
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def age_band(age):
    if age is None:
        return ""
    return "u6" if age < 6 else ("6_17" if age < 18 else "18plus")


def photo_exempt(age, student):
    """p. 4: at least one document must contain a photograph, unless the applicant is a dependent under 14 (under 18 if a student)."""
    return age is not None and (age < 14 or (age < 18 and bool(student)))


def residency_options(age):
    """Evidence keys that can prove U.S. residency for a dependent of this age (p. 4), passport-with-entry-date aside."""
    if age is None:
        return []
    if age < 6:
        return ["medical_record", "school_record", "us_state_id", "us_visa"]
    if age < 18:
        return ["school_record", "us_state_id", "us_dl", "us_visa"]
    opts = ["us_state_id", "us_dl", "us_visa"] + list(RESIDENCY_ONLY)
    return (["school_record"] if age < 24 else []) + opts


def school_allowed(age):
    return age is not None and age < 24


def medical_allowed(age):
    return age is not None and age < 6


def caa_can_verify(doc_key, kind):
    """p. 6. `kind`: primary | spouse | dependent. Residency-only documents (bank/rental/utility) are not identity documents a CAA verifies."""
    if doc_key in RESIDENCY_ONLY:
        return False
    if kind == "dependent":
        return doc_key in ("passport", "birth_certificate")
    return doc_key != "foreign_military_id"


def _foreign(doc_key, birth_country_foreign):
    f = EVIDENCE[doc_key][2]
    if f == "if_foreign":
        return bool(birth_country_foreign) if doc_key == "birth_certificate" else False
    return bool(f)


def coverage(kind, age, student, docs, *, birth_country_foreign=None, passport_has_entry_date=None, residency_docs=(), residency_required=False, passport_current=True):
    """{identity, foreign_status, photo, residency, doc_types, ok}: each True / False / None (None = not applicable or OG must look at the physical document).

    A valid passport is the only stand-alone document (p. 4): with it no other document is needed for identity, foreign status or the photograph. A dependent
    who must prove U.S. residency also needs residency evidence unless the passport shows a date of entry into the United States (p. 4)."""
    docs = set(docs)
    out = {"identity": False, "foreign_status": False, "photo": False, "residency": None, "doc_types": len(docs), "stand_alone": False}
    has_passport = "passport" in docs and passport_current
    if has_passport:
        out.update(identity=True, foreign_status=True, photo=True, stand_alone=True)
    else:
        real = [d for d in docs if d in EVIDENCE]
        out["identity"] = any(EVIDENCE[d][3] for d in real)
        out["foreign_status"] = any(_foreign(d, birth_country_foreign) for d in real)
        photo_docs = [EVIDENCE[d][4] for d in real]
        out["photo"] = True if photo_exempt(age, student) else (True if any(p is True for p in photo_docs) else (None if any(p is None for p in photo_docs) else False))
    if residency_required:
        if has_passport and passport_has_entry_date:
            out["residency"] = True
        else:
            res = [d for d in set(residency_docs) | docs if d in residency_options(age)]
            out["residency"] = bool(res)
    ok = out["identity"] and out["foreign_status"] and out["photo"] in (True,) and out["residency"] in (True, None)
    if not has_passport:
        ok = ok and len([d for d in docs if d in EVIDENCE]) >= 2  # p. 4: "at least two types of documents" unless a valid passport is submitted
    out["ok"] = bool(ok)
    return out


def needs_us_residency(kind, age, nationality=None):
    """(required, review_note) — only dependents (p. 4). Exempt: dependents of U.S. military stationed overseas (out of OG's online scope), and applicants from
    Canada or Mexico claimed for an allowable tax benefit OTHER than the credit for other dependents (which tax benefit is OG's tax-preparation decision)."""
    if kind != "dependent":
        return False, ""
    nat = (nationality or "").strip().lower()
    if nat in ("canada", "mexico", "méxico", "canadá"):
        return True, "canada_mexico"
    return True, ""
