from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models import FulfillmentStatus, Order, OrderItem, OrderItemStatus, Product
from ...realtime import emit_order_update

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


@bp.post("/orders/<int:order_id>/items/<int:item_id>/served")
def mark_item_served(order_id: int, item_id: int):
    item = (
        OrderItem.query.options(
            joinedload(OrderItem.order).joinedload(Order.table),
            joinedload(OrderItem.product),
        )
        .filter_by(id=item_id)
        .first_or_404()
    )
    if item.order_id != order_id:
        flash("La línia no pertany a aquesta comanda", "danger")
        return redirect(url_for("bar.queue"))

    if item.status in {OrderItemStatus.SERVED, OrderItemStatus.PAID}:
        flash("Ja estava servida", "info")
        return redirect(url_for("bar.queue"))

    item.status = OrderItemStatus.SERVED

    order = item.order
    order.recalc_status()
    db.session.commit()
    emit_order_update(order)
    flash(f"'{item.product.name}' marcat com servit", "success")
    return redirect(url_for("bar.queue"))


@bp.post("/orders/<int:order_id>/all-served")
def mark_order_served(order_id: int):
    order = (
        Order.query.options(
            joinedload(Order.table),
            joinedload(Order.items).joinedload(OrderItem.product).joinedload(Product.category),
        )
        .filter_by(id=order_id)
        .first_or_404()
    )

    # Mark all auto-prepared items that are PREPARED as SERVED
    count = 0
    for item in order.items:
        if item.product.is_auto_prepared and item.status == OrderItemStatus.PREPARED:
            item.status = OrderItemStatus.SERVED
            count += 1

    if count > 0:
        order.recalc_status()
        db.session.commit()
        emit_order_update(order)
        flash(f"{count} producte{'s' if count > 1 else ''} de barra servit{'s' if count > 1 else ''}", "success")
    else:
        flash("No hi ha productes de barra pendents en aquesta comanda", "info")

    return redirect(url_for("bar.queue"))
