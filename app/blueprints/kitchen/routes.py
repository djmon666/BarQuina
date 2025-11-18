from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models import FulfillmentStatus, Order, OrderItem, OrderItemStatus
from ...realtime import emit_order_update

bp = Blueprint("kitchen", __name__, url_prefix="/kitchen")


def _pending_order_groups() -> list[tuple[Order, list[OrderItem]]]:
    """Return orders that still have pending kitchen items."""
    orders = (
        Order.query.options(
            joinedload(Order.table),
            joinedload(Order.items).joinedload(OrderItem.product),
            joinedload(Order.items).joinedload(OrderItem.extras),
        )
        .filter(Order.fulfillment_status != FulfillmentStatus.SERVED)
        .order_by(Order.created_at.asc())
        .all()
    )
    pending: list[tuple[Order, list[OrderItem]]] = []
    for order in orders:
        items = [item for item in order.items if item.status == OrderItemStatus.PENDING]
        if items:
            pending.append((order, items))
    return pending


@bp.route("/")
def queue():
    pending_orders = _pending_order_groups()
    total_pending_items = sum(len(items) for _, items in pending_orders)
    return render_template(
        "kitchen/queue.html",
        pending_orders=pending_orders,
        total_pending_items=total_pending_items,
    )


@bp.post("/orders/<int:order_id>/items/<int:item_id>/ready")
def mark_item_ready(order_id: int, item_id: int):
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
        return redirect(url_for("kitchen.queue"))

    if item.status in {OrderItemStatus.PREPARED, OrderItemStatus.SERVED, OrderItemStatus.PAID}:
        flash("Ja estava preparada o servida", "info")
        return redirect(url_for("kitchen.queue"))

    item.status = OrderItemStatus.PREPARED

    order = item.order
    order.recalc_status()
    db.session.commit()
    emit_order_update(order)
    flash(f"'{item.product.name}' marcat com servit", "success")
    return redirect(url_for("kitchen.queue"))


@bp.post("/orders/<int:order_id>/ready-all")
def mark_order_ready(order_id: int):
    order = (
        Order.query.options(
            joinedload(Order.items).joinedload(OrderItem.product),
        )
        .filter_by(id=order_id)
        .first_or_404()
    )
    pending_items = [item for item in order.items if item.status == OrderItemStatus.PENDING]
    if not pending_items:
        flash("No hi ha línies pendents en aquesta comanda", "info")
        return redirect(url_for("kitchen.queue"))

    for item in pending_items:
        item.status = OrderItemStatus.PREPARED

    order.recalc_status()
    db.session.commit()
    emit_order_update(order)
    flash(f"{len(pending_items)} línies marcades com servides", "success")
    return redirect(url_for("kitchen.queue"))
