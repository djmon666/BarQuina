from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ...extensions import db
from ...models import CashMovement, CashMovementType, CashSession

bp = Blueprint("cash", __name__)


@bp.route("/sessions", methods=["GET", "POST"])
def sessions():
    if request.method == "POST":
        opening_float = float(request.form.get("opening_float", 0))
        db.session.add(CashSession(opening_float=opening_float))
        db.session.commit()
        flash("Sessió de caixa oberta", "success")
        return redirect(url_for("cash.sessions"))

    sessions = CashSession.query.order_by(CashSession.opened_at.desc()).all()
    return render_template("cash/sessions.html", sessions=sessions)


@bp.route("/sessions/<int:session_id>/close", methods=["POST"])
def close_session(session_id: int):
    session = CashSession.query.get_or_404(session_id)
    closing_amount = float(request.form.get("closing_amount", 0))
    session.closing_amount = closing_amount
    session.is_open = False
    db.session.commit()
    flash("Sessió tancada", "success")
    return redirect(url_for("cash.sessions"))


@bp.route("/sessions/<int:session_id>/movements", methods=["POST"])
def add_movement(session_id: int):
    session = CashSession.query.get_or_404(session_id)
    movement_type = CashMovementType(request.form.get("movement_type", CashMovementType.SALE.value))
    amount = float(request.form.get("amount", 0))
    note = request.form.get("note", "")

    if amount <= 0:
        flash("Quantitat invàlida", "danger")
        return redirect(url_for("cash.sessions"))

    db.session.add(CashMovement(session_id=session.id, movement_type=movement_type, amount=amount, note=note))
    db.session.commit()
    flash("Moviment enregistrat", "success")
    return redirect(url_for("cash.sessions"))
