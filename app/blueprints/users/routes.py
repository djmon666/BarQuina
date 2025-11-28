from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ...auth_utils import admin_required
from ...extensions import db
from ...models import StaffUser

bp = Blueprint("users", __name__, url_prefix="/users")


@bp.before_request
@admin_required
def require_admin():
    pass


@bp.route("/", methods=["GET", "POST"])
def manage_users():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Cal proporcionar un nom", "danger")
        elif StaffUser.query.filter_by(name=name).first():
            flash("Aquest nom ja existeix", "warning")
        else:
            db.session.add(StaffUser(name=name))
            db.session.commit()
            flash("Usuari creat", "success")
        return redirect(url_for("users.manage_users"))

    users = StaffUser.query.order_by(StaffUser.name).all()
    return render_template("users/manage.html", users=users)


@bp.route("/<int:user_id>/toggle", methods=["POST"])
def toggle_user(user_id: int):
    user = StaffUser.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    flash("Estat actualitzat", "success")
    return redirect(url_for("users.manage_users"))
