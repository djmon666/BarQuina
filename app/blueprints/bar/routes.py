from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy.orm import joinedload

from ...models import FulfillmentStatus, Order, OrderItem, OrderItemStatus, Product

bp = Blueprint("bar", __name__, url_prefix="/bar")


@bp.before_request
def require_login():
    from flask import current_app
    if current_app.config.get("LOGIN_DISABLED", False):
        return
    if not current_user.is_authenticated:
        flash("Cal iniciar sessió per accedir a aquesta pàgina.", "warning")
        return redirect(url_for("auth.login"))


def _pending_bar_groups() -> list[tuple[Order, list[OrderItem]]]:
    """Return orders that have auto-prepared items still marked as prepared but not served."""
    orders = (
        Order.query.options(
            joinedload(Order.table),
            joinedload(Order.items).joinedload(OrderItem.product).joinedload(Product.category),
            joinedload(Order.items).joinedload(OrderItem.extras),
        )
        .filter(Order.fulfillment_status != FulfillmentStatus.SERVED)
        .order_by(Order.created_at.asc())
        .all()
    )
    pending: list[tuple[Order, list[OrderItem]]] = []
    for order in orders:
        # Filter items that are auto-prepared and in PREPARED status (pending to serve)
        items = [
            item for item in order.items
            if item.product.is_auto_prepared and item.status == OrderItemStatus.PREPARED
        ]
        if items:
            pending.append((order, items))
    return pending


@bp.route("/")
def queue():
    pending_orders = _pending_bar_groups()
    total_pending_items = sum(len(items) for _, items in pending_orders)
    return render_template(
        "bar/queue.html",
        pending_orders=pending_orders,
        total_pending_items=total_pending_items,
    )



