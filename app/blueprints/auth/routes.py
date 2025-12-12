from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ...extensions import db
from ...models import StaffUser

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for("dashboard.home"))
        return redirect(url_for("mobile.tables"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        user = StaffUser.query.filter_by(name=username).first()
        
        if user and not user.is_active:
            flash("Usuari desactivat. Demana a administració que t'activin", "warning")
        elif user and user.check_password(password):
            login_user(user)
            next_page = request.args.get("next")
            if user.is_admin():
                return redirect(next_page if next_page else url_for("dashboard.home"))
            return redirect(url_for("mobile.tables"))
        else:
            flash("Usuari o contrasenya incorrectes", "danger")
    
    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sessió tancada correctament", "success")
    return redirect(url_for("auth.login"))
