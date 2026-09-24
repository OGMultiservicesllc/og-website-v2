"""Tax Year 2025 configuration: the interview (steps, questions, wording EN/ES), the record flows (dependents, self-employment activities), the income / situation
routing and the lists the rules use. Document rules live in `docs.py` and price rules in `pricing.py`; a future year adds its own module and registers it in `registry.py`.

The customer is NOT a tax professional: nothing here asks about forms, schedules, credits or eligibility. Questions collect facts; OG decides tax treatment.
"""

from app.tax.questions import MONTHS, O, Opt, Q, Step, YN3

TAX_YEAR = 2025
YEAR_END = (2025, 12, 31)


def yn(key, label, **kw):
    return Q(key, "yn3", label, options=YN3, **kw)


# ------------------------------------------------------------------ helpers over the answers (all read through ctx.v: hidden answers never count)
def has_inc(c, v):
    return c.has("income", v)


def works_biz(c):
    return has_inc(c, "selfemp") or has_inc(c, "cash") or has_inc(c, "apps") or c.has("f1099_types", "nec")


def mod(c, name):
    """Is an income / situation module active? (the same fact can be chosen on the income screen, in the 1099 list or on the situations screen)."""
    t = {"unemployment": ("unemployment", "g"), "retirement": ("retirement", "r"), "ss": ("ss", None), "interest": ("interest", "int"), "invest": ("invest", "b"), "rental": ("rental", None)}[name]
    return has_inc(c, t[0]) or c.has("situations", t[0]) or (t[1] is not None and c.has("f1099_types", t[1]))


def any_income_module(c):
    return any(mod(c, m) for m in ("unemployment", "retirement", "ss", "interest", "invest", "rental")) or has_inc(c, "other")


def household_options(c):
    """Options naming everyone in the tax household (the taxpayer, the spouse, each potential dependent)."""
    out = [Opt("self", "Me", "Yo", "👤")]
    if c.v("marital") == "married" and c.tax is not None:
        out.append(Opt("spouse", "My spouse", "Mi esposo(a)", "💍"))
    for r in c.deps:
        info = c.info(r) if c.info else {}
        name = info.get("given") or ("Person" if c.lang != "es" else "Persona")
        out.append(Opt(f"dep:{r.id}", name, name, "👶"))
    return out


def has_young_dependent(c):
    """A dependent under 13 at the end of the tax year (from the date of birth OG already asked)."""
    for r in c.deps:
        dob = (c.info(r) if c.info else {}).get("dob")
        if dob and (YEAR_END[0] - dob.year - ((dob.month, dob.day) > (YEAR_END[1], YEAR_END[2]))) < 13:
            return True
    return False


# ------------------------------------------------------------------ option lists
CHANGES = [
    O("moved", "I moved", "Me mudé", "🏠"), O("family", "I got married, divorced or separated", "Me casé, divorcié o separé", "💍"),
    O("child", "I had or adopted a child", "Tuve o adopté un hijo", "👶"), O("job", "I changed jobs", "Cambié de trabajo", "💼"),
    O("selfemp", "I started or stopped working for myself", "Empecé o dejé de trabajar por mi cuenta", "🚗"), O("home", "I bought or sold a home", "Compré o vendí una casa", "🏡"),
    O("school", "Someone started college or university", "Alguien comenzó college o universidad", "🎓"), O("health", "My health insurance changed", "Cambió mi seguro médico", "🏥"),
    O("invest", "I started investing or using crypto", "Comencé a invertir o usar crypto", "📈"), O("retire", "I started receiving retirement or Social Security", "Comencé a recibir retiro o Social Security", "👴"),
    O("other", "Another change", "Otro cambio", "➕"), O("none", "Nothing important changed", "Nada importante cambió", "✅", exclusive=True),
]
INCOME = [
    O("w2", "I worked for a company and got a W-2", "Trabajé para una compañía y recibí W-2", "👔"),
    O("selfemp", "I worked for myself / did independent jobs", "Trabajé por mi cuenta / hice trabajos independientes", "🚗"),
    O("cash", "I was paid in cash", "Recibí pagos en efectivo", "💵"),
    O("apps", "Uber, Lyft, DoorDash or other apps", "Uber, Lyft, DoorDash u otras aplicaciones", "📱"),
    O("f1099", "I received one or more 1099 forms", "Recibí uno o más 1099", "📄"),
    O("unemployment", "I received unemployment", "Recibí unemployment", "💰"),
    O("retirement", "I received a pension or retirement income", "Recibí retiro o pensión", "👴"),
    O("ss", "I received Social Security", "Recibí Social Security", "👴"),
    O("interest", "I received interest or dividends", "Recibí intereses o dividendos", "🏦"),
    O("invest", "I sold investments", "Vendí inversiones", "📈"),
    O("rental", "I rented out a property", "Alquilé una propiedad", "🏠"),
    O("other", "Other income", "Otro ingreso", "➕"),
]
F1099_TYPES = [
    O("nec", "1099-NEC, 1099-MISC or 1099-K (work or app payments)", "1099-NEC, 1099-MISC o 1099-K (trabajo o pagos de aplicaciones)", "💼"),
    O("int", "1099-INT or 1099-DIV (interest, dividends)", "1099-INT o 1099-DIV (intereses, dividendos)", "🏦"),
    O("r", "1099-R (retirement)", "1099-R (retiro)", "👴"), O("g", "1099-G (unemployment)", "1099-G (unemployment)", "💰"),
    O("b", "1099-B (sale of investments)", "1099-B (venta de inversiones)", "📈"), O("other", "Another 1099 / not sure", "Otro 1099 / no estoy seguro", "❓"),
]
BIZ_TYPES = [
    O("uber", "Uber", "Uber", "🚗"), O("lyft", "Lyft", "Lyft", "🚗"), O("doordash", "DoorDash", "DoorDash", "🛵"), O("delivery", "Other delivery / apps", "Otras entregas / aplicaciones", "📱"),
    O("construction", "Construction / painting", "Construcción / pintura", "🏗️"), O("cleaning", "Cleaning", "Limpieza", "🧹"), O("barber", "Barber / beauty", "Barbería / belleza", "💈"),
    O("mechanic", "Mechanic", "Mecánica", "🔧"), O("sales", "Sales", "Ventas", "🛍️"), O("food", "Food preparation", "Preparación de comida", "🍲"), O("other", "Other", "Otro", "➕"),
]
PLATFORM_TYPES = ("uber", "lyft", "doordash", "delivery")
BIZ_SOURCES = [
    O("f1099", "1099", "1099", "📄"), O("cash", "Cash", "Efectivo", "💵"), O("zelle", "Zelle", "Zelle", "📲"), O("cashapp", "Cash App", "Cash App", "📲"), O("venmo", "Venmo", "Venmo", "📲"),
    O("checks", "Checks", "Cheques", "🧾"), O("platform", "Uber / DoorDash / Lyft / a platform", "Uber / DoorDash / Lyft / una plataforma", "📱"), O("other", "Other", "Otro", "➕"),
]
VEHICLE_COSTS = [
    O("gas", "Gasoline", "Gasolina", "⛽"), O("repairs", "Repairs and maintenance", "Reparaciones y mantenimiento", "🔧"), O("insurance", "Insurance", "Seguro", "🛡️"),
    O("registration", "Registration", "Registro", "🪪"), O("tolls", "Tolls", "Peajes", "🛣️"), O("parking", "Parking", "Estacionamiento", "🅿️"), O("other", "Other vehicle costs", "Otros costos del carro", "➕"),
]
EXPENSE_CATS = [
    O("materials", "Materials and supplies", "Materiales y suministros", "🧰"), O("tools", "Tools and equipment", "Herramientas y equipo", "🛠️"), O("phone", "Phone and internet", "Teléfono e internet", "📶"),
    O("advertising", "Advertising", "Publicidad", "📣"), O("insurance", "Business insurance", "Seguro del negocio", "🛡️"), O("fees", "Platform fees and commissions", "Cargos y comisiones de plataformas", "💳"),
    O("rent", "Rent", "Renta", "🏢"), O("workers", "Payments to workers or others", "Pagos a trabajadores u otras personas", "👥"), O("travel", "Travel", "Viajes", "✈️"),
    O("meals", "Business-related meals", "Comidas relacionadas con el trabajo", "🍽️"), O("other", "Other", "Otro", "➕"),
]
HEALTH_SOURCES = [
    O("employer", "My or my spouse's employer", "Mi empleo o el de mi esposo(a)", "🏢"), O("marketplace", "Marketplace / HealthCare.gov", "Marketplace / HealthCare.gov", "🏥"),
    O("medicaid", "Medicaid / CHIP", "Medicaid / CHIP", "🩺"), O("medicare", "Medicare", "Medicare", "🩺"), O("other", "Other", "Otro", "➕"), O("unsure", "Not sure", "No estoy seguro(a)", "❓", exclusive=True),
]
SITUATIONS = [
    O("rental", "I rented out a house or property", "Alquilé una casa o propiedad", "🏠"), O("invest", "I sold stocks or other investments", "Vendí stocks u otras inversiones", "📈"),
    O("crypto", "I bought, sold, received or exchanged crypto / digital assets", "Compré, vendí, recibí o intercambié crypto/digital assets", "🪙"),
    O("unemployment", "I received unemployment", "Recibí unemployment", "💰"), O("ss", "I received Social Security", "Recibí Social Security", "👴"),
    O("gambling", "I received prizes or gambling winnings", "Recibí premios o gambling winnings", "🎰"), O("foreign", "I had income or accounts outside the United States", "Tuve ingresos o cuentas fuera de Estados Unidos", "🌎"),
    O("medical", "I paid large medical expenses out of pocket", "Tuve gastos médicos importantes pagados de mi bolsillo", "🏥"), O("retire_contrib", "I contributed to a retirement account on my own", "Hice aportes a una cuenta de retiro por mi cuenta", "💼"),
    O("other", "I have another situation I want to explain to OG", "Tengo otra situación que quiero explicarle a OG", "❓"), O("none", "None of these", "Ninguna de estas", "✅", exclusive=True),
]
RELATIONS = [
    O("child", "Son or daughter", "Hijo(a)"), O("stepchild", "Stepchild", "Hijastro(a)"), O("foster", "Foster child", "Hijo(a) de crianza"), O("grandchild", "Grandchild", "Nieto(a)"),
    O("sibling", "Brother or sister", "Hermano(a)"), O("nephew", "Niece or nephew", "Sobrino(a)"), O("parent", "Parent", "Padre o madre"), O("other", "Another relative or person", "Otro familiar u otra persona"),
]
MONTHS_LIVED = [O(str(i), (f"{i} months" if i != 1 else "1 month") if i else "Not at all", (f"{i} meses" if i != 1 else "1 mes") if i else "Nada") for i in range(12, -1, -1)]
SELECT_MONTHS = [O(str(i), str(i), str(i)) for i in range(12, -1, -1)]

# ------------------------------------------------------------------ the interview
STEPS = [
    Step("intro", ("Let's prepare your taxes", "Preparemos tus taxes"), "📄", [], kind="special"),
    Step("changes", ("Did anything important change during 2025?", "¿Hubo algún cambio importante durante 2025?"), "🔄", [
        Q("changes", "multi", ("Check everything that applies.", "Marca todo lo que aplique."), options=CHANGES, req=True, miss=("choose at least one option.", "elige al menos una opción.")),
    ], show=lambda c: c.returning),
    Step("about", ("About you", "Sobre ti"), "👤", [
        Q("about_note", "note", ("We already have some of your information. Check that it is still correct and fix anything that changed.", "Ya tenemos parte de tu información. Revisa que siga correcta y corrige lo que haya cambiado."), show=lambda c: c.returning),
        Q("a_given", "text", ("First name", "Nombre"), bind="given_name", req=True, width="half", miss=("your first name.", "tu nombre.")),
        Q("a_family", "text", ("Last name", "Apellido"), bind="family_name", req=True, width="half", miss=("your last name.", "tu apellido.")),
        Q("a_dob", "date", ("Date of birth", "Fecha de nacimiento"), bind="date_of_birth", req=True, width="half", miss=("your date of birth.", "tu fecha de nacimiento.")),
        Q("a_ssn", "ssn", ("Social Security number or ITIN", "Número de Seguro Social o ITIN"), bind="ssn", req="soft", sens=True, width="half",
          help=("If you do not have one yet, leave it blank. OG will help you.", "Si todavía no tienes uno, déjalo en blanco. OG te ayudará.")),
        Q("a_email", "email", ("Email", "Correo electrónico"), bind="email", req=True, width="half", miss=("your email.", "tu correo electrónico.")),
        Q("a_phone", "phone", ("Phone", "Teléfono"), bind="phone_daytime", req=True, width="half", miss=("your phone number.", "tu teléfono.")),
        Q("a_street", "text", ("Street address", "Dirección (calle y número)"), bind="address.street", req=True, miss=("your street address.", "tu dirección.")),
        Q("a_unit", "text", ("Apt / unit (if any)", "Apto / unidad (si tiene)"), bind="address.unit_number", width="half"),
        Q("a_city", "text", ("City", "Ciudad"), bind="address.city", req=True, width="half", miss=("your city.", "tu ciudad.")),
        Q("a_state", "state", ("State", "Estado"), bind="address.state", req=True, width="half", miss=("your state.", "tu estado.")),
        Q("a_zip", "text", ("ZIP code", "Código postal (ZIP)"), bind="address.zip", req=True, width="half", maxlen=10, miss=("your ZIP code.", "tu código postal.")),
        Q("occupation", "text", ("What is your occupation?", "¿Cuál es tu ocupación?"), req="soft", ph=("Example: cleaner, driver, cashier", "Ejemplo: limpieza, chofer, cajera")),
        Q("id_kind", "choice", ("Do you have a photo ID?", "¿Tienes una identificación con foto?"), req="soft", options=[
            O("license", "Driver's license", "Licencia de conducir", "🪪"), O("state_id", "State ID", "State ID", "🪪"), O("other", "Another valid ID", "Otra identificación válida", "🪪"), O("none", "Not right now", "Ahora no", "⏰")]),
        Q("id_docs", "docs", ("Upload a photo of it if you can. It is optional.", "Sube una foto si puedes. Es opcional."), docs=("tax.id.",), show=lambda c: c.v("id_kind") in ("license", "state_id", "other")),
        Q("moved", "choice", ("Did you move during 2025?", "¿Te mudaste durante 2025?"), req=True, miss=("tell us if you moved.", "dinos si te mudaste."), options=[
            O("no", "No", "No", "🏠"), O("same", "Yes, within the same state", "Sí, dentro del mismo estado", "🏠"), O("other", "Yes, to a different state", "Sí, a otro estado", "🚚"), O("unsure", "Not sure", "No estoy seguro(a)", "❓")]),
        Q("moved_from", "state", ("Which state did you live in before?", "¿En qué estado vivías antes?"), show=lambda c: c.v("moved") == "other", req="soft"),
        Q("moved_month", "select", ("Around which month did you move?", "¿Más o menos en qué mes te mudaste?"), options=MONTHS, show=lambda c: c.v("moved") in ("same", "other")),
    ]),
    Step("prior", ("Last year's tax return", "Tus taxes del año pasado"), "📄", [
        Q("prior_return", "choice", ("Do you have a copy of last year's tax return?", "¿Tienes una copia de tus taxes del año pasado?"), req=True, miss=("choose one option.", "elige una opción."), options=[
            O("now", "Upload now", "Subir ahora", "📄"), O("later", "I will upload it later", "Lo subiré después", "⏰"), O("none", "I don't have it", "No los tengo", "🚫")]),
        Q("prior_docs", "docs", ("Upload it here.", "Súbelo aquí."), docs=("tax.prior_return",), show=lambda c: c.v("prior_return") in ("now", "later")),
    ], show=lambda c: not c.returning),
    Step("status", ("Your situation on December 31, 2025", "Tu situación al 31 de diciembre de 2025"), "👨‍👩‍👧‍👦", [
        Q("marital", "choice", ("What was your situation on December 31, 2025?", "¿Cuál era tu situación al 31 de diciembre de 2025?"), req=True, miss=("choose one option.", "elige una opción."), options=[
            O("single", "Single", "Soltero(a)", "🙂"), O("married", "Married", "Casado(a)", "💍"), O("divorced", "Divorced", "Divorciado(a)", "🙂"), O("separated", "Separated", "Separado(a)", "🙂"), O("widowed", "Widowed", "Viudo(a)", "🙂")]),
    ]),
    Step("spouse", ("Your spouse", "Tu esposo(a)"), "💍", [
        Q("s_pick", "person_pick", ("Someone OG already knows", "Alguien que OG ya conoce")),
        Q("s_given", "text", ("First name", "Nombre"), bind="given_name", req=True, width="half", miss=("your spouse's first name.", "el nombre de tu esposo(a).")),
        Q("s_family", "text", ("Last name", "Apellido"), bind="family_name", req=True, width="half", miss=("your spouse's last name.", "el apellido de tu esposo(a).")),
        Q("s_dob", "date", ("Date of birth", "Fecha de nacimiento"), bind="date_of_birth", req=True, width="half", miss=("your spouse's date of birth.", "la fecha de nacimiento de tu esposo(a).")),
        Q("s_ssn", "ssn", ("Social Security number or ITIN", "Número de Seguro Social o ITIN"), bind="ssn", req="soft", sens=True, width="half",
          help=("If your spouse does not have one yet, leave it blank.", "Si tu esposo(a) todavía no tiene uno, déjalo en blanco.")),
    ], show=lambda c: c.v("marital") == "married", scope="spouse"),
    Step("deps_gate", ("Children and other people", "Hijos y otras personas"), "👶", [
        yn("has_deps", ("Do you have children or other people you think you can include in your taxes?", "¿Tienes hijos u otras personas que crees que puedes incluir en tus taxes?"), req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
    ]),
    Step("deps", ("Who lives with you or depends on you?", "¿Quiénes viven contigo o dependen de ti?"), "👶", [
        Q("deps_list", "records", ("Add each person one by one. OG decides what applies. You only tell us the facts.", "Agrega a cada persona una por una. OG decide qué aplica. Tú solo nos das los datos."), record="dependent"),
    ], show=lambda c: c.v("has_deps") in ("yes", "unsure"), kind="records", record="dependent"),
    Step("income", ("How did you receive money in 2025?", "Durante 2025, ¿cómo recibiste dinero?"), "💼", [
        Q("income", "multi", ("Check everything that applies.", "Marca todo lo que aplique."), options=INCOME, req=True, miss=("choose at least one option.", "elige al menos una opción."),
          help=("If you had no income at all, choose “Other income” and tell OG.", "Si no tuviste ningún ingreso, elige “Otro ingreso” y cuéntale a OG.")),
        Q("f1099_types", "multi", ("Which 1099 forms did you receive?", "¿Qué formularios 1099 recibiste?"), options=F1099_TYPES, show=lambda c: has_inc(c, "f1099"), req="soft"),
    ]),
    Step("w2", ("Your W-2", "Tu W-2"), "👔", [
        Q("w2_count", "count", ("How many W-2s did you receive in total?", "¿Cuántos W-2 recibiste en total?"), req=True, maxv=12, width="half",
          miss=("how many W-2s you received.", "cuántos W-2 recibiste."), help=("If you are married, count your spouse's too. Not sure? Write your best guess.", "Si estás casado(a), cuenta también los de tu esposo(a). ¿No estás seguro(a)? Escribe tu mejor cálculo.")),
        Q("w2_docs", "docs", ("Upload each W-2 now, or later. A clear photo is enough.", "Sube cada W-2 ahora o después. Una foto clara basta."), docs=("tax.w2.",)),
    ], show=lambda c: has_inc(c, "w2")),
    Step("business", ("Your own work", "Tu trabajo por cuenta propia"), "🚗", [
        Q("biz_list", "records", ("Add each kind of work you did on your own. Different jobs go separately.", "Agrega cada tipo de trabajo que hiciste por tu cuenta. Los trabajos diferentes van por separado."), record="business"),
    ], show=works_biz, kind="records", record="business"),
    Step("income_more", ("More about your income", "Más sobre tus ingresos"), "💰", [
        Q("rental_count", "count", ("How many properties did you rent out?", "¿Cuántas propiedades alquilaste?"), req=True, maxv=20, width="half", show=lambda c: mod(c, "rental")),
        Q("invest_size", "choice", ("How many investment sales did you have?", "¿Cuántas ventas de inversiones tuviste?"), show=lambda c: mod(c, "invest"), req=True, miss=("choose one option.", "elige una opción."), options=[
            O("few", "A few simple sales", "Pocas ventas sencillas", "📈"), O("many", "Many sales", "Muchas ventas", "📈"), O("unsure", "Not sure", "No estoy seguro(a)", "❓")]),
        Q("other_income_text", "textarea", ("Tell us about your other income.", "Cuéntanos sobre tu otro ingreso."), show=lambda c: has_inc(c, "other"), req="soft"),
        yn("state_other", ("Did you earn income in a different state than where you live?", "¿Recibiste ingresos en un estado diferente al que vives?"), req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        Q("income_more_docs", "docs", ("Upload these documents if you have them. You can do it later.", "Sube estos documentos si los tienes. Puedes hacerlo después."),
          docs=("tax.f1099g", "tax.f1099r", "tax.ssa1099", "tax.f1099int", "tax.f1099b", "tax.f1099x", "tax.rental.")),
    ], show=lambda c: any_income_module(c) or (works_biz(c) or has_inc(c, "w2"))),
    Step("health", ("Health insurance in 2025", "Seguro médico en 2025"), "🏥", [
        Q("h_cover", "choice", ("During 2025, did you have health insurance?", "Durante 2025, ¿tuviste seguro médico?"), req=True, miss=("choose one option.", "elige una opción."), options=[
            O("full", "Yes, all year", "Sí, todo el año", "✅"), O("part", "Yes, part of the year", "Sí, parte del año", "🗓️"), O("no", "No", "No", "🚫"), O("unsure", "Not sure", "No estoy seguro(a)", "❓")]),
        Q("h_sources", "multi", ("Where did your insurance come from?", "¿De dónde era tu seguro?"), options=HEALTH_SOURCES, show=lambda c: c.v("h_cover") in ("full", "part"), req="soft"),
        Q("h_who", "multi", ("Who was covered?", "¿Quiénes tuvieron seguro?"), options=household_options, show=lambda c: c.v("h_cover") in ("full", "part") and (c.v("marital") == "married" or len(c.deps) > 0)),
        Q("h_1095_count", "count", ("How many Form 1095-A did you receive?", "¿Cuántos Formularios 1095-A recibiste?"), maxv=6, width="half", show=lambda c: c.has("h_sources", "marketplace"),
          help=("Not sure? Write 1.", "¿No estás seguro(a)? Escribe 1.")),
        Q("h_docs", "docs", ("📄 If you received a Form 1095-A from the Marketplace / HealthCare.gov, upload it here.", "📄 Si recibiste un Form 1095-A del Marketplace / HealthCare.gov, súbelo aquí."), docs=("tax.1095a.",), show=lambda c: c.has("h_sources", "marketplace")),
    ]),
    Step("childcare", ("Childcare", "Cuidado de niños"), "👶", [
        yn("cc_paid", ("👶 Did you pay for care for your children so you could work? For example: daycare, babysitter or after-school care.", "👶 ¿Pagaste por el cuidado de tus hijos para poder trabajar? Por ejemplo: daycare, babysitter o after-school care."), req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        Q("cc_who", "multi", ("For which children?", "¿Para cuáles hijos?"), options=lambda c: [o for o in household_options(c) if o.value.startswith("dep:")], show=lambda c: c.v("cc_paid") == "yes"),
        Q("cc_provider", "text", ("Who did you pay? (name of the daycare or person)", "¿A quién le pagaste? (nombre de la guardería o persona)"), show=lambda c: c.v("cc_paid") == "yes", req="soft"),
        Q("cc_amount", "money", ("About how much did you pay in 2025?", "¿Aproximadamente cuánto pagaste en 2025?"), show=lambda c: c.v("cc_paid") == "yes", req="soft", width="half"),
        Q("cc_docs", "docs", ("If you have the provider's information or receipts, upload them. It is optional.", "Si tienes la información o los recibos del proveedor, súbelos. Es opcional."), docs=("tax.childcare",), show=lambda c: c.v("cc_paid") == "yes"),
    ], show=lambda c: has_young_dependent(c) and (has_inc(c, "w2") or works_biz(c))),
    Step("education", ("Education", "Educación"), "🎓", [
        yn("e_student", ("🎓 During 2025, did you, your spouse or any of your children or dependents study at a college, university or other school after high school?", "🎓 ¿Tú, tu esposo(a) o alguno de tus hijos/dependientes estudió en college, university u otra institución postsecundaria durante 2025?"), req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        Q("e_who", "multi", ("Who studied?", "¿Quién estudió?"), options=household_options, show=lambda c: c.v("e_student") == "yes", req=True, miss=("choose who studied.", "elige quién estudió.")),
        Q("e_docs", "docs", ("Upload the Form 1098-T if you have it. You can do it later.", "Sube el Form 1098-T si lo tienes. Puedes hacerlo después."), docs=("tax.1098t.",), show=lambda c: c.v("e_student") == "yes"),
        yn("e_loan", ("Did you pay interest on a student loan during 2025?", "¿Pagaste intereses de un préstamo estudiantil durante 2025?"), req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        Q("e_loan_docs", "docs", ("Upload the Form 1098-E if you have it.", "Sube el Form 1098-E si lo tienes."), docs=("tax.1098e",), show=lambda c: c.v("e_loan") == "yes"),
    ]),
    Step("home", ("Your home", "Tu casa"), "🏠", [
        yn("o_own", ("🏠 Did you own a home during 2025?", "🏠 ¿Eras dueño de una casa durante 2025?"), req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        yn("o_mortgage", ("Did you pay mortgage interest?", "¿Pagaste intereses de hipoteca (mortgage)?"), show=lambda c: c.v("o_own") == "yes", req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        Q("o_docs", "docs", ("Upload the Form 1098 from your lender if you have it.", "Sube el Form 1098 de tu prestamista si lo tienes."), docs=("tax.1098",), show=lambda c: c.v("o_mortgage") == "yes"),
    ]),
    Step("charity", ("Donations", "Donaciones"), "🙏", [
        yn("ch_gave", ("Did you give money or things to a church or a charity during 2025?", "¿Donaste dinero o cosas a una iglesia u organización sin fines de lucro durante 2025?"), req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        Q("ch_types", "multi", ("What did you give?", "¿Qué donaste?"), options=[O("money", "Money", "Dinero", "💵"), O("goods", "Clothes, furniture or other things", "Ropa, muebles u otras cosas", "👕")], show=lambda c: c.v("ch_gave") == "yes"),
        Q("ch_amount", "money", ("About how much in total?", "¿Aproximadamente cuánto en total?"), show=lambda c: c.v("ch_gave") == "yes", req="soft", width="half"),
        Q("ch_docs", "docs", ("Upload your receipts if you have them. It is optional.", "Sube tus recibos si los tienes. Es opcional."), docs=("tax.charity",), show=lambda c: c.v("ch_gave") == "yes"),
    ]),
    Step("estimated", ("Payments you made ahead of time", "Pagos que hiciste por adelantado"), "💰", [
        yn("ep_paid", ("💰 Did you make payments to the IRS during 2025 ahead of time for your taxes? We do not mean what was taken out of a W-2.", "💰 ¿Hiciste pagos al IRS durante 2025 por adelantado para tus taxes? No nos referimos a lo que te descontaron de un W-2."), req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        Q("ep_fed", "money", ("About how much did you pay the IRS in total?", "¿Aproximadamente cuánto le pagaste al IRS en total?"), show=lambda c: c.v("ep_paid") == "yes", req="soft", width="half"),
        Q("ep_state", "money", ("Did you also pay your state? How much?", "¿También le pagaste a tu estado? ¿Cuánto?"), show=lambda c: c.v("ep_paid") == "yes", width="half"),
        Q("ep_docs", "docs", ("Upload proof of the payments if you have it. It is optional.", "Sube el comprobante de los pagos si lo tienes. Es opcional."), docs=("tax.estimated",), show=lambda c: c.v("ep_paid") == "yes"),
    ]),
    Step("situations", ("Anything else that happened in 2025?", "¿Te pasó algo más durante 2025?"), "🧾", [
        Q("situations", "multi", ("Check the ones that apply.", "Marca las que apliquen."), options=SITUATIONS, req=True, miss=("choose at least one option.", "elige al menos una opción."), after=lambda c, o: not (o.value in ("rental", "invest", "unemployment", "ss") and has_inc(c, o.value))),
        Q("cr_size", "choice", ("How much crypto activity did you have?", "¿Cuánta actividad de crypto tuviste?"), show=lambda c: c.has("situations", "crypto"), req=True, miss=("choose one option.", "elige una opción."), options=[
            O("simple", "A few simple transactions", "Pocas operaciones sencillas", "🪙"), O("complex", "Many or complicated ones", "Muchas o complicadas", "🪙"), O("unsure", "Not sure", "No estoy seguro(a)", "❓")]),
        Q("fo_text", "textarea", ("Tell us briefly about the income or accounts outside the United States.", "Cuéntanos brevemente sobre los ingresos o cuentas fuera de Estados Unidos."), show=lambda c: c.has("situations", "foreign"), req="soft"),
        Q("gm_amount", "money", ("About how much did you win?", "¿Aproximadamente cuánto ganaste?"), show=lambda c: c.has("situations", "gambling"), req="soft", width="half"),
        Q("med_amount", "money", ("About how much did you pay out of pocket?", "¿Aproximadamente cuánto pagaste de tu bolsillo?"), show=lambda c: c.has("situations", "medical"), req="soft", width="half"),
        Q("rc_amount", "money", ("About how much did you contribute?", "¿Aproximadamente cuánto aportaste?"), show=lambda c: c.has("situations", "retire_contrib"), req="soft", width="half"),
        Q("ot_text", "textarea", ("Tell OG about it.", "Cuéntale a OG."), show=lambda c: c.has("situations", "other"), req="soft"),
    ]),
    Step("notes", ("Anything we did not ask?", "¿Algo que no te preguntamos?"), "🤔", [
        Q("notes_text", "textarea", ("🤔 Is there anything about your taxes that we did not ask? Tell us here anything you think OG should know.", "🤔 ¿Hay algo sobre tus taxes que no te preguntamos? Cuéntanos aquí cualquier situación que creas que OG debería conocer."), maxlen=2000),
    ]),
    Step("payment_pref", ("If you owe the IRS", "Si le debes al IRS"), "💳", [
        Q("pay_pref", "choice", ("💳 If it turns out you have to pay the IRS when your taxes are done, how would you prefer to do it?", "💳 Si al terminar tus taxes resulta que tienes que pagarle al IRS, ¿cómo preferirías hacerlo?"), req=True, miss=("choose one option.", "elige una opción."), options=[
            O("debit", "Direct debit from my bank account", "Débito directo de mi cuenta bancaria", "🏦"), O("self", "I will send / pay it myself", "Yo lo enviaré / pagaré por mi cuenta", "✉️"),
            O("agreement", "I want information about a payment agreement", "Quiero información sobre un acuerdo de pago", "🤝"), O("later", "I will decide later", "Lo decidiré después", "⏰")],
          help=("We do not know yet if you will owe anything. This only helps OG plan.", "Todavía no sabemos si vas a deber algo. Esto solo ayuda a OG a planear.")),
    ]),
    Step("refund", ("If you get a refund", "Si te toca reembolso"), "🏦", [
        yn("dd_want", ("Do you want your refund by direct deposit?", "¿Quieres recibir tu reembolso por depósito directo?"), req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        Q("dd_type", "choice", ("Type of account", "Tipo de cuenta"), show=lambda c: c.v("dd_want") == "yes", req=True, miss=("the type of account.", "el tipo de cuenta."), options=[O("checking", "Checking", "Cheques (checking)", "🏦"), O("savings", "Savings", "Ahorros (savings)", "🏦")]),
        Q("dd_routing", "secret", ("Routing number (9 digits)", "Número de ruta (9 dígitos)"), show=lambda c: c.v("dd_want") == "yes", req=True, sens=True, width="half", miss=("the routing number.", "el número de ruta.")),
        Q("dd_account", "secret", ("Account number", "Número de cuenta"), show=lambda c: c.v("dd_want") == "yes", req=True, sens=True, width="half", miss=("the account number.", "el número de cuenta.")),
        Q("dd_account2", "secret", ("Type the account number again", "Escribe el número de cuenta otra vez"), show=lambda c: c.v("dd_want") == "yes", req=True, sens=True, width="half", miss=("the account number again.", "el número de cuenta otra vez.")),
    ]),
    Step("documents", ("Your documents", "Tus documentos"), "📄", [], kind="docs"),
    Step("price", ("Your estimated price", "Tu precio estimado"), "💵", [], kind="special"),
    Step("review", ("Review your information", "Revisa tu información"), "✅", [], kind="special"),
    Step("send", ("Send to OG", "Enviar a OG"), "📨", [], kind="special"),
]

# ------------------------------------------------------------------ record flows
def _dep_is_student_age(c):
    dob = c.info(c.record).get("dob") if (c.info and c.record is not None) else None
    if dob is None:
        return True
    age = YEAR_END[0] - dob.year - ((dob.month, dob.day) > (YEAR_END[1], YEAR_END[2]))
    return 17 <= age <= 26


DEP_STEPS = [
    Step("dep_who", ("Who is this person?", "¿Quién es esta persona?"), "👶", [
        Q("d_given", "text", ("First name", "Nombre"), bind="given_name", req=True, width="half", miss=("their first name.", "su nombre.")),
        Q("d_family", "text", ("Last name", "Apellido"), bind="family_name", req=True, width="half", miss=("their last name.", "su apellido.")),
        Q("d_dob", "date", ("Date of birth", "Fecha de nacimiento"), bind="date_of_birth", req=True, width="half", miss=("their date of birth.", "su fecha de nacimiento.")),
        Q("d_rel", "select", ("How is this person related to you?", "¿Qué relación tiene contigo?"), options=RELATIONS, req=True, width="half", miss=("how they are related to you.", "qué relación tiene contigo.")),
        Q("d_ssn_status", "choice", ("Social Security number or ITIN", "Número de Seguro Social o ITIN"), req=True, miss=("choose one option.", "elige una opción."), options=[
            O("have", "They have one", "Sí tiene", "✅"), O("pending", "It is in process", "Está en trámite", "⏰"), O("none", "They do not have one yet", "Todavía no tiene", "🚫")]),
        Q("d_ssn", "ssn", ("Number", "Número"), bind="ssn", sens=True, width="half", show=lambda c: c.v("d_ssn_status") == "have", req="soft"),
    ], kind="record_step", scope="record"),
    Step("dep_life", ("During 2025", "Durante 2025"), "🏠", [
        Q("d_months", "select", ("How many months did this person live with you in 2025?", "¿Cuántos meses vivió esta persona contigo en 2025?"), options=MONTHS_LIVED, req=True, width="half", miss=("how many months they lived with you.", "cuántos meses vivió contigo.")),
        yn("d_student", ("Was this person a full-time student in 2025?", "¿Esta persona fue estudiante de tiempo completo en 2025?"), show=_dep_is_student_age, req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        yn("d_disabled", ("Does this person have a permanent disability?", "¿Esta persona tiene una discapacidad permanente?"), req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        yn("d_other_claim", ("Could someone else include this person in their taxes?", "¿Otra persona podría incluir a esta persona en sus taxes?"), req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
    ], kind="record_step", scope="record"),
    Step("dep_docs", ("Documents", "Documentos"), "📄", [
        Q("d_res_kind", "choice", ("🏠 We need proof of where this person lived during 2025. The easiest is usually a school or doctor document showing their name and address.", "🏠 Necesitamos una prueba de dónde vivió esta persona durante 2025. Lo más fácil normalmente es un documento de la escuela o del médico que muestre su nombre y su dirección."), options=[
            O("school", "School", "Escuela", "🏫"), O("doctor", "Doctor", "Médico", "🩺"), O("other", "Other", "Otro", "📄"), O("later", "I will upload it later", "Lo subiré después", "⏰")], req="soft"),
        Q("d_docs", "docs", ("👶 Birth certificate and proof of residence", "👶 Acta de nacimiento y prueba de residencia"), docs=("tax.dep.",)),
    ], kind="record_step", scope="record"),
]

BIZ_STEPS = [
    Step("biz_what", ("What type of work was it?", "¿Qué tipo de trabajo hiciste?"), "💼", [
        Q("b_type", "choice", ("Choose the one that fits best.", "Elige el que mejor se parezca."), options=BIZ_TYPES, req=True, miss=("the type of work.", "el tipo de trabajo.")),
        Q("b_desc", "text", ("Tell us a little about the work", "Cuéntanos un poco sobre el trabajo"), req=True, miss=("a short description of the work.", "una breve descripción del trabajo."), ph=("Example: I paint houses", "Ejemplo: pinto casas")),
        Q("b_name", "text", ("Business name (if you have one)", "Nombre del negocio (si tiene)")),
        Q("b_start", "date", ("Around when did you start? (optional)", "¿Más o menos cuándo empezaste? (opcional)"), flag="future_ok"),
    ], kind="record_step", scope="record"),
    Step("biz_income", ("Money you received", "Dinero que recibiste"), "💰", [
        Q("b_receipts", "money", ("💰 How much money did you receive for this work during 2025?", "💰 ¿Cuánto dinero recibiste por este trabajo durante 2025?"), req=True, width="half", miss=("about how much you received for this work.", "aproximadamente cuánto recibiste por este trabajo."),
          help=("Include ALL the money, even if you did not receive a 1099. If you got a 1099, its amount is usually already part of this total, so do not add it again.", "Incluye TODO el dinero, aunque no hayas recibido un 1099. Si recibiste un 1099, ese monto normalmente ya es parte de este total, así que no lo sumes otra vez.")),
        Q("b_sources", "multi", ("How were you paid? Check all that apply.", "¿Cómo te pagaron? Marca todo lo que aplique."), options=BIZ_SOURCES, req=True, miss=("how you were paid.", "cómo te pagaron.")),
        Q("b_undoc", "money", ("Of that total, about how much is NOT on any 1099 or platform report? (if you know)", "Del total, ¿aproximadamente cuánto NO aparece en ningún 1099 ni reporte de plataforma? (si lo sabes)"), width="half", show=lambda c: bool(c.rec.get("b_sources"))),
    ], kind="record_step", scope="record"),
    Step("biz_vehicle", ("Vehicle", "Vehículo"), "🚗", [
        yn("b_vehicle", ("🚗 Did you use a car for this work?", "🚗 ¿Usaste un carro para este trabajo?"), req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        Q("b_miles", "count", ("About how many miles did you drive for this work in 2025?", "¿Aproximadamente cuántas millas manejaste para este trabajo en 2025?"), maxv=999999, width="half", req=True, miss=("about how many miles you drove. If you don't know, write 0 and tell OG.", "aproximadamente cuántas millas manejaste. Si no lo sabes, escribe 0 y avísale a OG."),
          show=lambda c: c.rec.get("b_vehicle") == "yes", help=("Look at your app reports or your notes. A rough number is fine.", "Mira los reportes de tu aplicación o tus notas. Un número aproximado basta.")),
        Q("b_vcosts", "multi", ("Which car costs did you pay? (optional)", "¿Qué costos del carro pagaste? (opcional)"), options=VEHICLE_COSTS, show=lambda c: c.rec.get("b_vehicle") == "yes"),
        *[Q(f"b_v_{o.value}", "money", (f"{o.label[0]}: about how much?", f"{o.label[1]}: ¿aproximadamente cuánto?"), width="half", show=(lambda v: (lambda c: c.rec.get("b_vehicle") == "yes" and v in (c.rec.get("b_vcosts") or [])))(o.value)) for o in VEHICLE_COSTS],
    ], kind="record_step", scope="record"),
    Step("biz_expenses", ("Expenses", "Gastos"), "💳", [
        yn("b_exp", ("💳 Did you spend money to do this work?", "💳 ¿Gastaste dinero para hacer este trabajo?"), req=True, miss=("choose yes, no or not sure.", "elige sí, no o no estoy seguro.")),
        Q("b_exp_cats", "multi", ("What did you spend money on? Check all that apply.", "¿En qué gastaste? Marca todo lo que aplique."), options=EXPENSE_CATS, show=lambda c: c.rec.get("b_exp") == "yes", req=True, miss=("what you spent money on.", "en qué gastaste.")),
        *[Q(f"b_x_{o.value}", "money", (f"{o.label[0]}: about how much?", f"{o.label[1]}: ¿aproximadamente cuánto?"), width="half", show=(lambda v: (lambda c: c.rec.get("b_exp") == "yes" and v in (c.rec.get("b_exp_cats") or [])))(o.value)) for o in EXPENSE_CATS],
        Q("b_exp_docs", "choice", ("Do you have documents or records of these expenses? Statements, reports, receipts or spreadsheets all work.", "¿Tienes documentos o registros de estos gastos? Sirven estados de cuenta, reportes, recibos u hojas de cálculo."), show=lambda c: c.rec.get("b_exp") == "yes", options=[
            O("upload", "Upload documents", "Subir documentos", "📄"), O("later", "Upload later", "Subir después", "⏰"), O("none", "I don't have documents to upload", "No tengo documentos para subir", "🚫")]),
    ], kind="record_step", scope="record"),
    Step("biz_docs", ("Documents for this work", "Documentos de este trabajo"), "📄", [
        Q("b_docs", "docs", ("📄 Upload what you have now, or come back later.", "📄 Sube lo que tengas ahora o vuelve después."), docs=("tax.biz.",)),
    ], kind="record_step", scope="record"),
]

RECORD_FLOWS = {"dependent": DEP_STEPS, "business": BIZ_STEPS}


class Config:
    year = TAX_YEAR
    steps = STEPS
    record_flows = RECORD_FLOWS

    def __init__(self):
        self._index, self.step_of, self.record_keys = {}, {}, set()
        for s in STEPS:
            for q in s.questions:
                self._index[q.key] = q
                self.step_of[q.key] = s
        for kind, steps in RECORD_FLOWS.items():
            for s in steps:
                for q in s.questions:
                    self._index[q.key] = q
                    self.step_of[q.key] = s
                    self.record_keys.add(q.key)
        self.step_by_key = {s.key: s for s in STEPS}
        self.record_step_by_key = {s.key: (kind, s) for kind, steps in RECORD_FLOWS.items() for s in steps}

    def index(self):
        return self._index


CONFIG = Config()
