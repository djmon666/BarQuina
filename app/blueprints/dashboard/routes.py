from __future__ import annotations

from flask import Blueprint, render_template
from sqlalchemy import and_, or_

from ...models import CashSession, FulfillmentStatus, Order, PaymentStatus, Table

bp = Blueprint("dashboard", __name__)


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
        .order_by(Order.created_at.desc())
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
