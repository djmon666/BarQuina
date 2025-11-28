from __future__ import annotations

from collections import defaultdict

from flask import Blueprint, render_template
from sqlalchemy import func

from ...auth_utils import admin_required
from ...extensions import db
from ...models import CashSession, OrderItem, Payment

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.before_request
@admin_required
def require_admin():
    pass


@bp.route("/")
def index():
    """Display profitability and sales statistics per cash session."""
    sessions = CashSession.query.order_by(CashSession.opened_at.desc()).limit(20).all()

    session_stats = []
    for session in sessions:
        # Aggregate product quantities sold during this session
        product_sales = (
            db.session.query(
                OrderItem.product_id,
                func.sum(OrderItem.quantity).label("total_quantity"),
            )
            .join(OrderItem.payment_links)
            .join(Payment)
            .filter(Payment.cash_session_id == session.id)
            .group_by(OrderItem.product_id)
            .all()
        )

        # Build product summary with names
        products_sold = []
        for product_id, qty in product_sales:
            from ...models import Product

            product = db.session.get(Product, product_id)
            if product:
                products_sold.append({"name": product.name, "quantity": qty})

        session_stats.append(
            {
                "session": session,
                "products_sold": products_sold,
                "revenue": session.movement_net_total,
                "costs": session.inventory_costs,
                "profit": session.net_profit,
            }
        )

    return render_template("reports/index.html", session_stats=session_stats)
