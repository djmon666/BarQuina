from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ...auth_utils import admin_required
from ...extensions import db
from ...models import CashMovement, CashMovementType, CashSession

bp = Blueprint("cash", __name__)


@bp.before_request
@admin_required
def require_admin():
    pass


def _parse_amount(raw_value: str | None, default: float = 0.0) -> float:
    normalized = (raw_value or "").strip()
    if not normalized:
        return default
    normalized = normalized.replace(",", ".")
    return float(normalized)


@bp.route("/sessions", methods=["GET", "POST"])
def sessions():
    if request.method == "POST":
        try:
            opening_float = _parse_amount(request.form.get("opening_float"), default=0.0)
        except ValueError:
            flash("Introdueix un import vàlid per obrir caixa", "danger")
            return redirect(url_for("cash.sessions"))
        db.session.add(CashSession(opening_float=opening_float))
        db.session.commit()
        flash("Sessió de caixa oberta", "success")
        return redirect(url_for("cash.sessions"))

    sessions = CashSession.query.order_by(CashSession.opened_at.desc()).all()
    return render_template("cash/sessions.html", sessions=sessions)


@bp.route("/sessions/<int:session_id>/close", methods=["POST"])
def close_session(session_id: int):
    session = CashSession.query.get_or_404(session_id)
    try:
        closing_amount = _parse_amount(request.form.get("closing_amount"), default=0.0)
    except ValueError:
        flash("Introdueix un import final vàlid", "danger")
        return redirect(url_for("cash.sessions"))
    session.closing_amount = closing_amount
    session.is_open = False
    db.session.commit()
    flash("Sessió tancada", "success")
    return redirect(url_for("cash.sessions"))


@bp.route("/sessions/<int:session_id>/reopen", methods=["POST"])
def reopen_session(session_id: int):
    session = CashSession.query.get_or_404(session_id)
    session.is_open = True
    session.closing_amount = None
    session.closed_at = None
    db.session.commit()
    flash("Sessió reoberta", "success")
    return redirect(url_for("cash.sessions"))


@bp.route("/sessions/<int:session_id>/edit", methods=["POST"])
def edit_session(session_id: int):
    session = CashSession.query.get_or_404(session_id)
    try:
        opening_float = _parse_amount(request.form.get("opening_float"), default=None)
    except ValueError:
        flash("Introdueix un fons inicial vàlid", "danger")
        return redirect(url_for("cash.sessions"))
    if opening_float is None:
        flash("El fons inicial no pot quedar en blanc", "danger")
        return redirect(url_for("cash.sessions"))

    try:
        closing_amount = _parse_amount(request.form.get("closing_amount"), default=None)
    except ValueError:
        flash("Introdueix un import final vàlid", "danger")
        return redirect(url_for("cash.sessions"))

    override_fields = (
        ("deposits_override", "Entrades"),
        ("withdrawals_override", "Sortides"),
        ("adjustments_override", "Ajustos"),
    )
    override_values: dict[str, float | None] = {}
    for field, label in override_fields:
        try:
            override_values[field] = _parse_amount(request.form.get(field), default=None)
        except ValueError:
            flash(f"Introdueix un valor vàlid per {label.lower()}", "danger")
            return redirect(url_for("cash.sessions"))

    session.opening_float = opening_float
    session.closing_amount = closing_amount
    for field, _ in override_fields:
        setattr(session, field, override_values[field])
    db.session.commit()
    flash("Sessió actualitzada", "success")
    return redirect(url_for("cash.sessions"))


@bp.route("/sessions/<int:session_id>/movements", methods=["POST"])
def add_movement(session_id: int):
    session = CashSession.query.get_or_404(session_id)
    movement_type = CashMovementType(request.form.get("movement_type", CashMovementType.SALE.value))
    try:
        amount = _parse_amount(request.form.get("amount"), default=0.0)
    except ValueError:
        flash("Introdueix un import de moviment vàlid", "danger")
        return redirect(url_for("cash.sessions"))
    note = request.form.get("note", "")

    if amount <= 0:
        flash("Quantitat invàlida", "danger")
        return redirect(url_for("cash.sessions"))

    db.session.add(CashMovement(session_id=session.id, movement_type=movement_type, amount=amount, note=note))
    db.session.commit()
    flash("Moviment enregistrat", "success")
    return redirect(url_for("cash.sessions"))
