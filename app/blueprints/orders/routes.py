from __future__ import annotations

from collections import defaultdict

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ...extensions import db
from ...models import (
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


def _grouped_products() -> dict[str, list[Product]]:
    products = Product.query.filter_by(is_active=True).order_by(Product.category, Product.name).all()
    groups: dict[str, list[Product]] = defaultdict(list)
    for product in products:
        groups[product.category].append(product)
    return groups


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
    product_groups = _grouped_products()
    return render_template(
        "orders/table_detail.html",
        table=table,
        order=order,
        product_groups=product_groups,
        fulfillment_statuses=list(FulfillmentStatus),
        payment_statuses=list(PaymentStatus),
        item_statuses=list(OrderItemStatus),
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

    product = Product.query.get(product_id)
    if not product:
        flash("Producte inexistent", "danger")
        return redirect(url_for("orders.table_detail", table_id=order.table_id))

    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=quantity,
        unit_price=product.price,
        notes=notes,
    )
    db.session.add(item)
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

        product = Product.query.get(product_id)
        if not product:
            continue

        db.session.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=product.price,
            )
        )
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
