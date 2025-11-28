from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy import and_, or_

from ...models import CashSession, FulfillmentStatus, Order, PaymentStatus, Table

bp = Blueprint("dashboard", __name__)


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


@bp.route("/")
def home():
    tables = Table.query.order_by(Table.name).all()
    open_orders = (
        Order.query.filter(
            or_(
                Order.fulfillment_status != FulfillmentStatus.SERVED,
                Order.payment_status != PaymentStatus.PAID,
            )
        )
        .order_by(Order.created_at.asc())
        .all()
    )
    closed_orders = (
        Order.query.filter(
            and_(
                Order.fulfillment_status == FulfillmentStatus.SERVED,
                Order.payment_status == PaymentStatus.PAID,
            )
        )
        .order_by(Order.updated_at.desc())
        .limit(20)
        .all()
    )
    active_session = CashSession.query.filter_by(is_open=True).order_by(CashSession.id.desc()).first()

    totals = {
        "sales": sum(order.subtotal() for order in open_orders),
        "pending": sum(order.outstanding_total() for order in open_orders),
    }

    return render_template(
        "dashboard.html",
        tables=tables,
        open_orders=open_orders,
        active_session=active_session,
        closed_orders=closed_orders,
        totals=totals,
        fulfillment_status_enum=FulfillmentStatus,
        payment_status_enum=PaymentStatus,
    )
