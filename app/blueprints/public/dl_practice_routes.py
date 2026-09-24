"""NJ Knowledge Test Practice Center: free, but an OG Account is required to start (never anonymous). Practicing never
creates a Driver License Case on its own — it only links to one if the student already has one, informationally."""

from flask import abort, redirect, render_template, request, url_for

from app.auth import validate_csrf
from app.blueprints.public.routes import public_bp
from app.driver_license import quiz
from app.models import DL_TOPICS
from app.student_auth import current_student, student_required

TOPIC_LABELS = {
    "road_signs": ("Road Signs", "Señales de Tránsito"), "traffic_signals": ("Traffic Signals", "Semáforos"), "right_of_way": ("Right of Way", "Derecho de Paso"),
    "speed_limits": ("Speed Limits", "Límites de Velocidad"), "parking": ("Parking", "Estacionamiento"), "passing": ("Passing", "Rebasar"),
    "defensive_driving": ("Defensive Driving", "Manejo Defensivo"), "dui": ("Alcohol / Drugs / DUI", "Alcohol / Drogas / DUI"),
    "sharing_road": ("Sharing the Road", "Compartir la Carretera"), "pedestrians": ("Pedestrians", "Peatones"), "school_buses": ("School Buses", "Autobuses Escolares"),
    "emergency_vehicles": ("Emergency Vehicles", "Vehículos de Emergencia"), "seat_belts": ("Seat Belts / Child Safety", "Cinturones / Seguridad Infantil"),
    "driving_conditions": ("Driving Conditions", "Condiciones de Manejo"), "vehicle_safety": ("Vehicle Safety", "Seguridad del Vehículo"), "nj_laws": ("NJ Driver Laws", "Leyes de Conducir de NJ"),
}


def _topic_label(key, lang):
    row = TOPIC_LABELS.get(key, (key, key))
    return row[1] if lang == "es" else row[0]


def _csrf():
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)


# ------------------------------------------------------------------ public: explains the simulator (no login needed to read)
@public_bp.route("/nj-driver-license/practice")
def dl_practice_home(lang):
    return render_template("driver_license/practice_home.html")


# ------------------------------------------------------------------ account required from here on
@public_bp.route("/nj-driver-license/practice/modes")
@student_required
def dl_practice_modes(lang):
    student = current_student()
    counts = {t: quiz.bank_size(t) for t in DL_TOPICS}
    topics = [{"key": t, "label": _topic_label(t, lang), "count": counts[t]} for t in DL_TOPICS if counts[t] > 0]
    from app.driver_license import service as dl_service

    has_case = dl_service.active_case(student) is not None
    return render_template("driver_license/practice_modes.html", topics=topics, best=quiz.best_score(student), history=quiz.history(student, 5),
                           total_bank=quiz.bank_size(), has_case=has_case, quick_n=quiz.MODE_COUNTS["quick"], full_n=quiz.MODE_COUNTS["full"], pass_pct=quiz.PASS_PERCENT)


@public_bp.route("/nj-driver-license/practice/start", methods=["POST"])
@student_required
def dl_practice_start(lang):
    _csrf()
    student = current_student()
    mode = request.form.get("mode")
    topic = request.form.get("topic") or None
    if mode not in ("quick", "topic", "full") or (mode == "topic" and topic not in DL_TOPICS):
        abort(400)
    from app.driver_license import service as dl_service

    active = dl_service.active_case(student)
    attempt = quiz.start_attempt(student, mode, lang, topic=topic, dl_case_id=active.id if active else None)
    if attempt.total == 0:
        abort(404)
    return redirect(url_for("public.dl_practice_question", lang=lang, attempt_id=attempt.id, n=1))


def _owned_attempt(attempt_id):
    a = quiz.owned_attempt(current_student(), attempt_id)
    if a is None:
        abort(404)
    return a


@public_bp.route("/nj-driver-license/practice/<int:attempt_id>/q/<int:n>", methods=["GET", "POST"])
@student_required
def dl_practice_question(lang, attempt_id, n):
    attempt = _owned_attempt(attempt_id)
    if attempt.completed_at is not None:
        return redirect(url_for("public.dl_practice_results", lang=lang, attempt_id=attempt.id))
    resp = quiz.current_response(attempt, n)
    if resp is None:
        if n > attempt.total:
            quiz.complete(attempt)
            return redirect(url_for("public.dl_practice_results", lang=lang, attempt_id=attempt.id))
        abort(404)
    if request.method == "POST":
        _csrf()
        option_id = request.form.get("option_id", type=int)
        quiz.answer(attempt, n, option_id)
        show_feedback = attempt.mode in ("quick", "topic") and request.form.get("reveal") != "1"
        if show_feedback:
            return redirect(url_for("public.dl_practice_question", lang=lang, attempt_id=attempt.id, n=n, reveal=1))
        if n >= attempt.total:
            quiz.complete(attempt)
            return redirect(url_for("public.dl_practice_results", lang=lang, attempt_id=attempt.id))
        return redirect(url_for("public.dl_practice_question", lang=lang, attempt_id=attempt.id, n=n + 1))
    q = resp.question
    opts = list(q.options)
    reveal = request.args.get("reveal") == "1" and attempt.mode in ("quick", "topic") and resp.selected_option_id is not None
    return render_template("driver_license/practice_question.html", attempt=attempt, n=n, q=q, opts=opts, resp=resp, reveal=reveal, topic_label=_topic_label(q.topic, lang))


@public_bp.route("/nj-driver-license/practice/<int:attempt_id>/results")
@student_required
def dl_practice_results(lang, attempt_id):
    attempt = _owned_attempt(attempt_id)
    if attempt.completed_at is None:
        quiz.complete(attempt)
    perf = quiz.topic_performance(attempt)
    rows = [{"topic": t, "label": _topic_label(t, lang), "correct": v["correct"], "total": v["total"]} for t, v in perf.items()]
    rows.sort(key=lambda r: r["label"])
    return render_template("driver_license/practice_results.html", attempt=attempt, topic_rows=rows, pass_pct=quiz.PASS_PERCENT)


@public_bp.route("/nj-driver-license/practice/<int:attempt_id>/review")
@student_required
def dl_practice_review(lang, attempt_id):
    attempt = _owned_attempt(attempt_id)
    if attempt.completed_at is None:
        abort(404)
    wrong = [r for r in sorted(attempt.responses, key=lambda r: r.sort_order) if not r.is_correct]
    return render_template("driver_license/practice_review.html", attempt=attempt, rows=wrong)
