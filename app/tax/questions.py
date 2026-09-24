"""Question / step framework of the Tax Smart Intake (a dedicated module, not the generic Form Builder).

An interview is DATA: an ordered list of `Step`s made of `Q`uestions with `show` conditions over earlier answers. The stable interview architecture lives here; everything
that changes with a tax year (which questions exist, their wording, document rules, prices, terms) lives in a per-year config (`app/tax/y2025.py`).

Answers are stored language-independent (codes such as "yes" / "unsure" / "w2"); every label is an (English, Spanish) pair.

Routing is DERIVED from the answers each time (`Ctx.steps()`), never stored, so resuming after an earlier answer changed is always consistent. Answers of questions that are
no longer visible are KEPT (nothing is silently erased) but every consumer reads values through `Ctx.v()`, which ignores hidden questions.
"""

import re
from datetime import date, datetime

from app.forms_engine import is_valid_email, is_valid_phone


def pick(pair, lang):
    if pair is None:
        return ""
    return pair[1] if lang == "es" and len(pair) > 1 and pair[1] else pair[0]


class Opt:
    __slots__ = ("value", "label", "emoji", "exclusive")

    def __init__(self, value, en, es, emoji="", exclusive=False):
        self.value, self.label, self.emoji, self.exclusive = value, (en, es), emoji, exclusive


def O(value, en, es, emoji="", exclusive=False):
    return Opt(value, en, es, emoji, exclusive)


YN3 = [O("yes", "Yes", "Sí"), O("no", "No", "No"), O("unsure", "Not sure", "No estoy seguro(a)")]
STATES = [
    ("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"), ("AR", "Arkansas"), ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"), ("DE", "Delaware"),
    ("DC", "District of Columbia"), ("FL", "Florida"), ("GA", "Georgia"), ("HI", "Hawaii"), ("ID", "Idaho"), ("IL", "Illinois"), ("IN", "Indiana"), ("IA", "Iowa"),
    ("KS", "Kansas"), ("KY", "Kentucky"), ("LA", "Louisiana"), ("ME", "Maine"), ("MD", "Maryland"), ("MA", "Massachusetts"), ("MI", "Michigan"), ("MN", "Minnesota"),
    ("MS", "Mississippi"), ("MO", "Missouri"), ("MT", "Montana"), ("NE", "Nebraska"), ("NV", "Nevada"), ("NH", "New Hampshire"), ("NJ", "New Jersey"), ("NM", "New Mexico"),
    ("NY", "New York"), ("NC", "North Carolina"), ("ND", "North Dakota"), ("OH", "Ohio"), ("OK", "Oklahoma"), ("OR", "Oregon"), ("PA", "Pennsylvania"), ("PR", "Puerto Rico"),
    ("RI", "Rhode Island"), ("SC", "South Carolina"), ("SD", "South Dakota"), ("TN", "Tennessee"), ("TX", "Texas"), ("UT", "Utah"), ("VT", "Vermont"), ("VA", "Virginia"),
    ("WA", "Washington"), ("WV", "West Virginia"), ("WI", "Wisconsin"), ("WY", "Wyoming"),
]
STATE_CODES = {c for c, _n in STATES}
MONTHS = [O(str(i), en, es) for i, (en, es) in enumerate([("January", "enero"), ("February", "febrero"), ("March", "marzo"), ("April", "abril"), ("May", "mayo"), ("June", "junio"), ("July", "julio"),
                                                          ("August", "agosto"), ("September", "septiembre"), ("October", "octubre"), ("November", "noviembre"), ("December", "diciembre")], 1)]


class Q:
    """One question. `kind`: text textarea number money count date select choice multi yn3 ssn phone email state note docs records secret.
    `req`: True blocks Continue; "soft" never blocks but the missing answer is listed for OG. `bind`: a Person fact ("given_name", "address.street"...) instead of an answer."""

    def __init__(self, key, kind, label, *, help=None, options=(), req=False, show=None, miss=None, bind=None, sens=False, docs=(), ph=None, maxlen=None, minv=None, maxv=None,
                 record=None, flag=None, width="full", after=None):
        self.key, self.kind, self.label, self.help = key, kind, label, help
        self.options = options if callable(options) else list(options)
        self.req, self.show, self.miss, self.bind, self.sens, self.docs, self.ph = req, show, miss, bind, sens, docs, ph
        self.maxlen, self.minv, self.maxv, self.record, self.flag, self.width, self.after = maxlen, minv, maxv, record, flag, width, after

    def opts(self, ctx=None):
        """The options to show: a fixed list, or a function of the answers (household members, filtered lists)."""
        base = self.options(ctx) if callable(self.options) else self.options
        return [o for o in base if self.after is None or ctx is None or self.after(ctx, o)]

    def option(self, value, opts=None):
        return next((o for o in (self.options if opts is None else opts) if o.value == value), None)


class Step:
    def __init__(self, key, title, icon, questions, *, show=None, kind="form", scope="self", lead=None, record=None, button=None):
        self.key, self.title, self.icon, self.questions, self.show, self.kind, self.scope, self.lead, self.record, self.button = key, title, icon, list(questions), show, kind, scope, lead, record, button


class Ctx:
    """Read-only view of a tax case for the rules: gated answers, records, people. `bound` = callable(scope, bind) -> value for Person-bound questions."""

    def __init__(self, tax, cfg, lang="en", record=None, bound=None, info=None):
        self.tax, self.cfg, self.lang, self.record, self.bound, self.info = tax, cfg, lang, record, bound, info
        self.g = tax.answers if tax is not None else {}
        self.rec = record.data if record is not None else {}
        self._cache, self._stack = {}, []
        self._index = cfg.index()

    # ------------------------------------------------ values
    def raw(self, key, scope="self"):
        q = self._index.get(key)
        if q is not None and q.bind:
            return self.bound(self._scope_of(key, scope), q.bind) if self.bound else None
        return self.rec.get(key) if (scope == "record" or (self.record is not None and key in self.cfg.record_keys)) else self.g.get(key)

    def _scope_of(self, key, scope):
        step = self.cfg.step_of.get(key)
        return step.scope if step is not None else scope

    def visible(self, key):
        if key in self._cache:
            return self._cache[key]
        if key in self._stack:  # a condition that (wrongly) refers to itself: treat as hidden rather than loop
            return False
        self._stack.append(key)
        try:
            step = self.cfg.step_of.get(key)
            q = self._index.get(key)
            ok = True
            if q is None:
                ok = True
            else:
                if step is not None and step.show is not None and step.kind != "record_step" and not step.show(self):
                    ok = False
                if ok and q.show is not None and not q.show(self):
                    ok = False
            self._cache[key] = ok
            return ok
        finally:
            self._stack.pop()

    def v(self, key):
        """The current answer, or None when its question is hidden by the answers before it."""
        if not self.visible(key):
            return None
        val = self.raw(key)
        return None if val in ("", []) else val

    def has(self, key, value):
        val = self.v(key)
        return isinstance(val, list) and value in val

    def num(self, key, default=0.0):
        val = self.v(key)
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    # ------------------------------------------------ people / records
    def _records(self, kind):
        """Records of this kind, but only while their list step is still on the active path: a branch the customer backed out of (e.g. unchecked
        self-employment) stops counting for documents/pricing/flags even though the rows stay in the database (nothing is erased, see `service.remove_record`)."""
        if self.tax is None:
            return []
        step = next((s for s in self.cfg.steps if s.kind == "records" and s.record == kind), None)
        if step is not None and step.show is not None and not step.show(self):
            return []
        return [r for r in self.tax.records if r.kind == kind]

    @property
    def deps(self):
        return self._records("dependent")

    @property
    def bizs(self):
        return self._records("business")

    @property
    def returning(self):
        return bool(self.tax is not None and self.tax.is_returning)

    def steps(self):
        return [s for s in self.cfg.steps if s.show is None or s.show(self)]


# ------------------------------------------------------------------ coercion + validation
_MONEY = re.compile(r"[^\d.]")


def parse_money(text):
    s = str(text or "").strip().replace(",", "")
    s = s.lstrip("$").strip()
    if not s:
        return None
    if not re.fullmatch(r"\d{1,9}(\.\d{1,2})?", s):
        raise ValueError
    n = float(s)
    return str(int(n)) if n == int(n) else f"{n:.2f}"


def parse_date(text):
    try:
        d = datetime.strptime(str(text or "").strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        raise ValueError
    if d.year < 1900:
        raise ValueError
    return d


def routing_ok(digits):
    if not re.fullmatch(r"\d{9}", digits or ""):
        return False
    d = [int(c) for c in digits]
    return (3 * (d[0] + d[3] + d[6]) + 7 * (d[1] + d[4] + d[7]) + (d[2] + d[5] + d[8])) % 10 == 0


ERR = {
    "money": ("Type just the number, for example 500.", "Escribe solo el número, por ejemplo 500."),
    "count": ("Type a whole number, for example 2.", "Escribe un número entero, por ejemplo 2."),
    "date": ("Choose a valid date.", "Elige una fecha válida."),
    "future": ("That date is in the future.", "Esa fecha todavía no ha llegado."),
    "email": ("That email does not look right.", "Ese correo no parece correcto."),
    "phone": ("Type a phone number with area code.", "Escribe un teléfono con código de área."),
    "ssn": ("A Social Security number or ITIN has 9 digits.", "Un Seguro Social o ITIN tiene 9 dígitos."),
    "state": ("Choose a state.", "Elige un estado."),
    "choice": ("Please choose one of the options.", "Elige una de las opciones."),
    "routing": ("That routing number does not look right. It has 9 digits.", "Ese número de ruta no parece correcto. Tiene 9 dígitos."),
    "account": ("Type the account number (4 to 17 digits).", "Escribe el número de cuenta (de 4 a 17 dígitos)."),
    "range": ("That number is too big.", "Ese número es demasiado grande."),
}


def missing_message(q, lang):
    hint = pick(q.miss, lang) if q.miss else ("Answer this question to continue." if lang != "es" else "Responde esta pregunta para continuar.")
    return ("😊 One small thing is missing: " if lang != "es" else "😊 Nos falta una cosita: ") + hint


def coerce(q, form, lang, opts=None):
    """(value, error). `value` is the language-independent canonical value ('' / [] when empty). `opts` = the options actually offered (dynamic lists). Never raises."""
    k = q.key
    opts = opts if opts is not None else (q.options if not callable(q.options) else [])
    if q.kind == "multi":
        vals = [x for x in form.getlist(k) if q.option(x, opts) is not None]
        excl = next((o.value for o in opts if o.exclusive and o.value in vals), None)
        if excl:
            vals = [excl]
        return vals, None
    raw = (form.get(k) or "").strip()
    if raw == "":
        return "", None
    try:
        if q.kind in ("text", "textarea"):
            return raw[: (q.maxlen or (2000 if q.kind == "textarea" else 200))], None
        if q.kind == "money":
            return parse_money(raw), None
        if q.kind == "count":
            n = int(raw)
            if not 0 <= n <= (q.maxv if q.maxv is not None else 99):
                raise ValueError
            return str(n), None
        if q.kind == "number":
            return raw[:20], None
        if q.kind == "date":
            d = parse_date(raw)
            if d > date.today() and q.flag != "future_ok":
                return "", pick(ERR["future"], lang)
            return d.isoformat(), None
        if q.kind in ("select", "choice", "yn3"):
            return (raw, None) if q.option(raw, opts) is not None else ("", pick(ERR["choice"], lang))
        if q.kind == "state":
            return (raw.upper(), None) if raw.upper() in STATE_CODES else ("", pick(ERR["state"], lang))
        if q.kind == "email":
            return (raw[:120], None) if is_valid_email(raw) else ("", pick(ERR["email"], lang))
        if q.kind == "phone":
            return (raw[:30], None) if is_valid_phone(raw) and sum(c.isdigit() for c in raw) >= 10 else ("", pick(ERR["phone"], lang))
        if q.kind == "ssn":
            digits = re.sub(r"\D", "", raw)
            if len(digits) != 9:
                return "", pick(ERR["ssn"], lang)
            return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}", None
        if q.kind == "secret":
            return raw[:40], None
    except ValueError:
        return "", pick(ERR["money" if q.kind == "money" else ("count" if q.kind == "count" else "date")], lang)
    return raw[:200], None
