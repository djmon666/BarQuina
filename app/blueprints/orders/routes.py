from __future__ import annotations

from collections import defaultdict

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models import (
    Category,
    FulfillmentStatus,
    Order,
    OrderItem,
    OrderItemStatus,
    Payment,
    PaymentItem,
    PaymentMethod,
    PaymentStatus,
    Product,
    Table,
)
from ...realtime import emit_order_update
from ...extras_utils import apply_extras_to_item, collect_extra_counts

bp = Blueprint("orders", __name__, url_prefix="")


def _get_or_create_open_order(table: Table) -> Order:
    order = Order.query.filter_by(table_id=table.id).order_by(Order.created_at.desc()).first()
    if order and order.payment_status != PaymentStatus.PAID:
        return order

    order = Order(table_id=table.id)
    order.sync_legacy_status()
    db.session.add(order)
    db.session.commit()
    emit_order_update(order)
    return order


def _grouped_products() -> list[tuple[Category, list[Product]]]:
    products = (
        Product.query.filter_by(is_active=True)
        .join(Product.category)
        .options(joinedload(Product.product_extras), joinedload(Product.category))
        .order_by(Category.sort_order, Category.name, Product.name)
        .all()
    )
    groups: dict[int, list[Product]] = defaultdict(list)
    ordered_categories: list[Category] = []
    for product in products:
        category = product.category
        if not category or not category.is_active:
            continue
        if category.id not in groups:
            ordered_categories.append(category)
        groups[category.id].append(product)
    return [(category, groups[category.id]) for category in ordered_categories]


def _product_with_extras(product_id: int) -> Product | None:
    return (
        Product.query.options(joinedload(Product.product_extras), joinedload(Product.category))
        .filter_by(id=product_id, is_active=True)
        .first()
    )


@bp.route("/tables", methods=["GET", "POST"])
def tables():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        seats = request.form.get("seats", 4)
        if not name:
            flash("El nom de la taula és obligatori", "danger")
        else:
            table = Table(name=name, seats=int(seats or 4))
            db.session.add(table)
            db.session.commit()
            flash("Taula creada", "success")
        return redirect(url_for("orders.tables"))

    tables = Table.query.order_by(Table.name).all()
    return render_template("orders/tables.html", tables=tables)


@bp.route("/tables/<int:table_id>")
def table_detail(table_id: int):
    table = Table.query.get_or_404(table_id)
    requested_order_id = request.args.get("order_id", type=int)
    order = None
    if requested_order_id:
        order = Order.query.filter_by(id=requested_order_id, table_id=table.id).first()
        if not order:
            flash("No hem trobat la comanda indicada", "warning")
    if not order:
        order = (
            Order.query.filter_by(table_id=table.id)
            .order_by(Order.created_at.desc())
            .first()
        )
    pending_orders = (
        Order.query.filter(Order.table_id == table.id, Order.payment_status != PaymentStatus.PAID)
        .order_by(Order.created_at.desc())
        .all()
    )
    pending_prev_id: int | None = None
    pending_next_id: int | None = None
    pending_position: int | None = None
    if order and pending_orders:
        for idx, pending in enumerate(pending_orders):
            if pending.id != order.id:
                continue
            pending_position = idx
            if idx > 0:
                pending_prev_id = pending_orders[idx - 1].id
            if idx < len(pending_orders) - 1:
                pending_next_id = pending_orders[idx + 1].id
            break
    product_groups = _grouped_products()
    return render_template(
        "orders/table_detail.html",
        table=table,
        order=order,
        product_groups=product_groups,
        fulfillment_statuses=list(FulfillmentStatus),
        payment_statuses=list(PaymentStatus),
        item_statuses=list(OrderItemStatus),
        pending_orders=pending_orders,
        pending_prev_id=pending_prev_id,
        pending_next_id=pending_next_id,
        pending_position=pending_position,
    )


@bp.route("/tables/<int:table_id>/orders", methods=["POST"])
def create_order(table_id: int):
    table = Table.query.get_or_404(table_id)
    order = Order(table_id=table.id)
    order.sync_legacy_status()
    db.session.add(order)
    db.session.commit()
    emit_order_update(order)
    flash("Comanda creada", "success")
    return redirect(url_for("orders.table_detail", table_id=table.id))


@bp.route("/orders/<int:order_id>/items", methods=["POST"])
def add_item(order_id: int):
    order = Order.query.get_or_404(order_id)
    product_id = request.form.get("product_id", type=int)
    quantity = max(int(request.form.get("quantity", 1)), 1)
    notes = request.form.get("notes", "")

    product = _product_with_extras(product_id)
    if not product:
        flash("Producte inexistent", "danger")
        return redirect(url_for("orders.table_detail", table_id=order.table_id))

    extra_counts = collect_extra_counts(request.form, product)
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=quantity,
        unit_price=product.price,
        status=product.initial_item_status(),
        notes=notes,
    )
    db.session.add(item)
    db.session.flush()
    apply_extras_to_item(item, extra_counts, product)
    order.fulfillment_status = FulfillmentStatus.PENDING_DELIVERY
    order.payment_status = PaymentStatus.PENDING_PAYMENT
    order.sync_legacy_status()
    db.session.commit()
    emit_order_update(order)
    flash("Producte afegit", "success")
    return redirect(url_for("orders.table_detail", table_id=order.table_id))


@bp.route("/orders/<int:order_id>/items/bulk", methods=["POST"])
def add_items_bulk(order_id: int):
    order = Order.query.get_or_404(order_id)
    added_items = 0
    for key, value in request.form.items():
        if not key.startswith("quantity_"):
            continue
        try:
            product_id = int(key.split("_", 1)[1])
            quantity = max(int(value), 0)
        except (ValueError, TypeError):
            continue

        if quantity <= 0:
            continue

        product = _product_with_extras(product_id)
        if not product:
            continue

        extra_counts = collect_extra_counts(request.form, product)
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=quantity,
            unit_price=product.price,
            status=product.initial_item_status(),
        )
        db.session.add(order_item)
        db.session.flush()
        apply_extras_to_item(order_item, extra_counts, product)
        added_items += quantity

    if added_items:
        order.fulfillment_status = FulfillmentStatus.PENDING_DELIVERY
        order.payment_status = PaymentStatus.PENDING_PAYMENT
        order.sync_legacy_status()
        db.session.commit()
        emit_order_update(order)
        flash(f"Afegits {added_items} articles", "success")
    else:
        flash("Cap producte seleccionat", "warning")

    return redirect(url_for("orders.table_detail", table_id=order.table_id, order_id=order.id))


@bp.route("/orders/<int:order_id>/items/<int:item_id>/status", methods=["POST"])
def update_item_status(order_id: int, item_id: int):
    order = Order.query.get_or_404(order_id)
    item = OrderItem.query.get_or_404(item_id)
    status = request.form.get("status")
    try:
        item.status = OrderItemStatus(status)
    except ValueError:
        abort(400)
    db.session.commit()
    order.recalc_status()
    db.session.commit()
    emit_order_update(order)
    flash("Estat actualitzat", "success")
    return redirect(url_for("orders.table_detail", table_id=order.table_id))


@bp.route("/orders/<int:order_id>/status", methods=["POST"])
def update_order_status(order_id: int):
    order = Order.query.get_or_404(order_id)
    fulfillment_value = request.form.get("fulfillment_status")
    payment_value = request.form.get("payment_status")
    try:
        if fulfillment_value:
            order.fulfillment_status = FulfillmentStatus(fulfillment_value)
        if payment_value:
            order.payment_status = PaymentStatus(payment_value)
    except ValueError:
        abort(400)
    order.sync_legacy_status()
    db.session.commit()
    emit_order_update(order)
    flash("Comanda actualitzada", "success")
    return redirect(url_for("orders.table_detail", table_id=order.table_id))


@bp.route("/orders/<int:order_id>/payments", methods=["POST"])
def add_payment(order_id: int):
    order = Order.query.get_or_404(order_id)
    method = request.form.get("method", PaymentMethod.CASH.value)
    item_ids = [int(item_id) for item_id in request.form.getlist("item_ids")]
    note = request.form.get("note", "")

    if not item_ids:
        flash("Cal seleccionar com a mínim una línia", "warning")
        return redirect(url_for("orders.table_detail", table_id=order.table_id))

    selected_items = (
        OrderItem.query.filter(OrderItem.id.in_(item_ids), OrderItem.order_id == order.id).all()
    )
    if not selected_items:
        flash("La selecció no és vàlida", "danger")
        return redirect(url_for("orders.table_detail", table_id=order.table_id))

    unpaid_items = [item for item in selected_items if not item.payment_links]
    if not unpaid_items:
        flash("Les línies seleccionades ja estan cobrades", "warning")
        return redirect(url_for("orders.table_detail", table_id=order.table_id))

    ignored = len(selected_items) - len(unpaid_items)
    if ignored:
        flash("Algunes línies seleccionades ja estaven cobrades i s'han omès", "info")

    amount = sum(item.line_total() for item in unpaid_items)

    payment = Payment(order_id=order.id, amount=amount, method=PaymentMethod(method), note=note)
    db.session.add(payment)
    db.session.flush()

    for item in unpaid_items:
        if item.status == OrderItemStatus.SERVED:
            item.status = OrderItemStatus.PAID
        db.session.add(PaymentItem(payment_id=payment.id, order_item_id=item.id))

    order.recalc_status()
    db.session.commit()
    emit_order_update(order)
    flash("Pagament registrat", "success")
    return redirect(url_for("orders.table_detail", table_id=order.table_id))
