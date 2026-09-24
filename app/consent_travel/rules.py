"""Consenting-parent computation and document grouping for Consent to Travel — pure functions, never a legal/
eligibility determination (OG reviews every case before approving). Mirrors the style of
`app/driver_license/rules.py` (a centralized, pure classification, never scattered through templates).

Rules (per child, evaluated independently — siblings can have different fathers):
  traveling_with == "father" -> mother always consents (a birth certificate always lists the mother; the
                                 per-child "is father on the certificate?" question is never asked in this
                                 scenario, since it would be moot).
  traveling_with == "mother" -> father consents ONLY if he is on the birth certificate; otherwise nobody needs
                                 to consent for this child (no document is generated for it).
  traveling_with == "other"  -> mother always consents; father consents ADDITIONALLY if on the certificate.
An "unsure" answer to "is father on the certificate?" is treated the same as "no" for consent/pricing
purposes (the conservative, never-overcharge default) but is flagged for OG's review — never silently assumed.
"""


def consenting_parents_for_child(traveling_with, father_on_cert, mother_pid, father_pid):
    """frozenset of Person ids who must consent for this one child. Empty = no Consent to Travel document is
    needed for this child at all (traveling parent's own presence is sufficient)."""
    if traveling_with == "father":
        return frozenset({mother_pid}) if mother_pid else frozenset()
    if traveling_with == "mother":
        if father_on_cert == "yes" and father_pid:
            return frozenset({father_pid})
        return frozenset()
    if traveling_with == "other":
        s = {mother_pid} if mother_pid else set()
        if father_on_cert == "yes" and father_pid:
            s.add(father_pid)
        return frozenset(s)
    return frozenset()


def needs_review_flag(father_on_cert):
    return father_on_cert == "unsure"


def group_documents(children_info):
    """children_info: [{id, name, consenting: frozenset}]. -> [{consenting: frozenset, children: [child dicts]}],
    one group per distinct consenting-parents set (item: "mismo conjunto de consenting parent(s) ... = mismo
    documento"). A child whose consenting set is EMPTY gets its own group of size 1 with consenting=frozenset()
    — no document/charge is generated for it (see `pricing.py`), but it still appears so OG can see it."""
    groups = {}
    order = []
    for child in children_info:
        key = child["consenting"]
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(child)
    return [{"consenting": key, "children": groups[key]} for key in order]
