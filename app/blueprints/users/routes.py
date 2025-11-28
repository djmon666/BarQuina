from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ...extensions import db
from ...models import StaffUser, UserRole

bp = Blueprint("users", __name__, url_prefix="/users")


@bp.before_request
def require_admin():
    from flask import current_app
    if current_app.config.get("LOGIN_DISABLED", False):
        return
    if not current_user.is_authenticated:
        flash("Cal iniciar sessió per accedir a aquesta pàgina.", "warning")
        return redirect(url_for("auth.login"))
    if not current_user.is_admin():
        flash("No tens permisos d'administrador.", "danger")
        return redirect(url_for("auth.login"))


@bp.route("/", methods=["GET", "POST"])
def manage_users():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "STAFF")
        
        if not name:
            flash("Cal proporcionar un nom", "danger")
        elif not password:
            flash("Cal proporcionar una contrasenya", "danger")
        elif len(password) < 4:
            flash("La contrasenya ha de tenir almenys 4 caràcters", "danger")
        elif StaffUser.query.filter_by(name=name).first():
            flash("Aquest nom ja existeix", "warning")
        else:
            user = StaffUser(
                name=name,
                role=UserRole.ADMIN if role == "ADMIN" else UserRole.STAFF,
                is_active=True
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash(f"Usuari {name} creat correctament", "success")
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


@bp.route("/<int:user_id>/edit", methods=["POST"])
def edit_user(user_id: int):
    user = StaffUser.query.get_or_404(user_id)
    
    name = request.form.get("name", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "STAFF")
    
    if not name:
        flash("Cal proporcionar un nom", "danger")
        return redirect(url_for("users.manage_users"))
    
    # Check name uniqueness (excluding current user)
    existing = StaffUser.query.filter(StaffUser.name == name, StaffUser.id != user_id).first()
    if existing:
        flash("Aquest nom ja existeix", "warning")
        return redirect(url_for("users.manage_users"))
    
    user.name = name
    user.role = UserRole.ADMIN if role == "ADMIN" else UserRole.STAFF
    
    # Update password only if provided
    if password:
        if len(password) < 4:
            flash("La contrasenya ha de tenir almenys 4 caràcters", "danger")
            return redirect(url_for("users.manage_users"))
        user.set_password(password)
    
    db.session.commit()
    flash(f"Usuari {name} actualitzat correctament", "success")
    return redirect(url_for("users.manage_users"))
