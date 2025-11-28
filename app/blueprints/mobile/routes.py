from __future__ import annotations

import json
from collections import defaultdict

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import login_required
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models import (
    Category,
    FulfillmentStatus,
    Order,
    OrderItem,
    OrderItemStatus,
    PaymentStatus,
    Product,
    StaffUser,
    Table,
)
from ...realtime import emit_order_update
from ...extras_utils import apply_extras_to_item, collect_extra_counts
from ...audit_utils import log_order_event, log_order_status_change

bp = Blueprint("mobile", __name__, url_prefix="/mobile")


@bp.before_request
@login_required
def require_login():
    pass


def _current_user() -> StaffUser | None:
    user_id = session.get("mobile_user_id")
    if not user_id:
        return None
    return db.session.get(StaffUser, user_id)


def _require_user() -> StaffUser | None:
    user = _current_user()
    if not user:
        flash("Identifica't per continuar", "warning")
        return None
    return user


def _active_orders(table_id: int) -> list[Order]:
    """Return orders that still requere servei at the table."""
    return (
        Order.query.filter(Order.table_id == table_id, Order.fulfillment_status != FulfillmentStatus.SERVED)
        .order_by(Order.created_at.desc())
        .all()
    )


@bp.route("/")
def landing():
    if _current_user():
        return redirect(url_for("mobile.tables"))

    users = StaffUser.query.filter_by(is_active=True).order_by(StaffUser.name).all()
    return render_template("mobile/login.html", users=users)


@bp.route("/select-user", methods=["POST"])
def select_user():
    user_id = request.form.get("user_id", type=int)
    user = db.session.get(StaffUser, user_id) if user_id else None
    if not user or not user.is_active:
        flash("Usuari invàlid", "danger")
        return redirect(url_for("mobile.landing"))

    session["mobile_user_id"] = user.id
    session["mobile_user_name"] = user.name
    flash(f"Sessió iniciada per {user.name}", "success")
    return redirect(url_for("mobile.tables"))


@bp.route("/logout")
def logout():
    session.pop("mobile_user_id", None)
    session.pop("mobile_user_name", None)
    flash("Sessió finalitzada", "info")
    return redirect(url_for("mobile.landing"))


@bp.route("/tables")
def tables():
    user = _require_user()
    if not user:
        return redirect(url_for("mobile.landing"))

    table_list = Table.query.order_by(Table.name).all()
    return render_template(
        "mobile/tables.html",
        user=user,
        tables=table_list,
        fulfillment_status=FulfillmentStatus,
        payment_status=PaymentStatus,
    )


@bp.route("/tables/<int:table_id>")
def table_orders(table_id: int):
    user = _require_user()
    if not user:
        return redirect(url_for("mobile.landing"))

    table = Table.query.get_or_404(table_id)
    orders = _active_orders(table.id)

    selected_order_id = request.args.get("order_id", type=int)
    selected_order = None
    if selected_order_id:
        selected_order = next((order for order in orders if order.id == selected_order_id), None)
        if not selected_order:
            flash("La comanda seleccionada no existeix o està tancada", "warning")
    if not selected_order and orders:
        selected_order = orders[0]

    product_groups: list[tuple[Category, list[Product]]] | None = None
    if selected_order:
        products = (
            Product.query.filter_by(is_active=True)
            .join(Product.category)
            .options(joinedload(Product.product_extras), joinedload(Product.category))
            .order_by(Category.sort_order, Category.name, Product.name)
            .all()
        )
        grouped: dict[int, list[Product]] = defaultdict(list)
        categories: list[Category] = []
        for product in products:
            category = product.category
            if not category or not category.is_active:
                continue
            if category.id not in grouped:
                categories.append(category)
            grouped[category.id].append(product)
        product_groups = [(category, grouped[category.id]) for category in categories]

    return render_template(
        "mobile/order.html",
        user=user,
        table=table,
        orders=orders,
        selected_order=selected_order,
        product_groups=product_groups or [],
        fulfillment_status=FulfillmentStatus,
        payment_status=PaymentStatus,
        item_status_enum=OrderItemStatus,
    )


@bp.route("/tables/<int:table_id>/orders", methods=["POST"])
def create_order(table_id: int):
    user = _require_user()
    if not user:
        return redirect(url_for("mobile.landing"))

    table = Table.query.get_or_404(table_id)
    order = Order(table_id=table.id, created_by=user)
    order.sync_legacy_status()
    db.session.add(order)
    db.session.flush()
    log_order_event(
        order,
        "order_created",
        staff_user=user,
        details={"source": "mobile", "table": table.name},
    )
    db.session.commit()
    emit_order_update(order)
    flash(f"Nova comanda #{order.id} creada", "success")
    return redirect(url_for("mobile.table_orders", table_id=table.id, order_id=order.id))


@bp.route("/orders/<int:order_id>/add-items", methods=["POST"])
def add_items(order_id: int):
    user = _require_user()
    if not user:
        return redirect(url_for("mobile.landing"))

    order = Order.query.get_or_404(order_id)
    prev_fulfillment = order.fulfillment_status
    prev_payment = order.payment_status
    if order.payment_status == PaymentStatus.PAID:
        flash("Aquesta comanda ja està cobrada", "danger")
        return redirect(url_for("mobile.table_orders", table_id=order.table_id))

    added_items = 0
    product_cache: dict[int, Product | None] = {}

    def load_product(product_id: int) -> Product | None:
        if product_id in product_cache:
            return product_cache[product_id]
        product_cache[product_id] = (
            Product.query.options(joinedload(Product.product_extras), joinedload(Product.category))
            .filter_by(id=product_id, is_active=True)
            .first()
        )
        return product_cache[product_id]

    def create_item(product: Product, quantity: int, extra_counts: dict[int, int] | None = None) -> None:
        nonlocal added_items
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=quantity,
            unit_price=product.price,
            status=product.initial_item_status(),
        )
        db.session.add(order_item)
        db.session.flush()
        apply_extras_to_item(order_item, extra_counts or {}, product)
        added_items += quantity

    payload_ids: set[int] = set()
    food_payload_raw = request.form.get("food_payload")
    if food_payload_raw:
        try:
            payload_entries = json.loads(food_payload_raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            payload_entries = []
        for entry in payload_entries:
            if not isinstance(entry, dict):
                continue
            product_id = entry.get("product_id")
            if not isinstance(product_id, int):
                continue
            product = load_product(product_id)
            if not product:
                continue
            payload_ids.add(product.id)
            extras_list = entry.get("extras") or []
            extra_counts: dict[int, int] = {}
            for extra_id in extras_list:
                try:
                    extra_key = int(extra_id)
                except (TypeError, ValueError):
                    continue
                extra_counts[extra_key] = extra_counts.get(extra_key, 0) + 1
            create_item(product, 1, extra_counts)

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

        if product_id in payload_ids:
            continue

        product = load_product(product_id)
        if not product or not product.is_active:
            continue

        extra_counts = collect_extra_counts(request.form, product)
        create_item(product, quantity, extra_counts)

    if added_items:
        order.recalc_status()
        log_order_status_change(
            order,
            prev_fulfillment,
            prev_payment,
            staff_user=user,
            details={"source": "mobile/add_items", "added_items": added_items},
        )
        db.session.commit()
        emit_order_update(order)
        flash(f"Afegits {added_items} articles", "success")
    else:
        flash("Cap producte seleccionat", "warning")

    return redirect(url_for("mobile.table_orders", table_id=order.table_id, order_id=order.id))


@bp.route("/orders/<int:order_id>/items/<int:item_id>/update", methods=["POST"])
def update_item(order_id: int, item_id: int):
    user = _require_user()
    if not user:
        return redirect(url_for("mobile.landing"))

    order = Order.query.get_or_404(order_id)
    prev_fulfillment = order.fulfillment_status
    prev_payment = order.payment_status
    item = OrderItem.query.get_or_404(item_id)
    if item.order_id != order.id:
        flash("La línia no pertany a aquesta comanda", "danger")
        return redirect(url_for("mobile.table_orders", table_id=order.table_id, order_id=order.id))

    if order.payment_status == PaymentStatus.PAID:
        flash("No es pot modificar una comanda cobrada", "danger")
        return redirect(url_for("mobile.table_orders", table_id=order.table_id, order_id=order.id))

    if request.form.get("action") == "delete":
        quantity = 0
    else:
        change = request.form.get("change")
        if change in {"increment", "decrement"}:
            delta = 1 if change == "increment" else -1
            quantity = item.quantity + delta
        else:
            quantity = request.form.get("quantity", type=int)

    if quantity is None:
        flash("Quantitat invàlida", "danger")
        return redirect(url_for("mobile.table_orders", table_id=order.table_id, order_id=order.id))

    if quantity <= 0:
        db.session.delete(item)
    else:
        item.quantity = quantity

    order.recalc_status()
    log_order_status_change(
        order,
        prev_fulfillment,
        prev_payment,
        staff_user=user,
        details={
            "source": "mobile/update_item",
            "item_id": item.id,
            "new_quantity": quantity,
        },
    )
    db.session.commit()
    emit_order_update(order)
    return redirect(url_for("mobile.table_orders", table_id=order.table_id, order_id=order.id))


@bp.route("/orders/<int:order_id>/items/<int:item_id>/toggle-served", methods=["POST"])
def toggle_item_served(order_id: int, item_id: int):
    user = _require_user()
    if not user:
        return redirect(url_for("mobile.landing"))

    order = Order.query.get_or_404(order_id)
    prev_fulfillment = order.fulfillment_status
    prev_payment = order.payment_status

    item = OrderItem.query.get_or_404(item_id)
    if item.order_id != order.id:
        flash("La línia no pertany a aquesta comanda", "danger")
        return redirect(url_for("mobile.table_orders", table_id=order.table_id, order_id=order.id))

    if item.status == OrderItemStatus.PAID:
        flash("Aquesta línia ja està cobrada", "info")
        return redirect(url_for("mobile.table_orders", table_id=order.table_id, order_id=order.id))

    if item.status == OrderItemStatus.SERVED:
        next_status = OrderItemStatus.PREPARED
    elif item.status == OrderItemStatus.PREPARED:
        next_status = OrderItemStatus.SERVED
    else:
        next_status = OrderItemStatus.SERVED

    if next_status == OrderItemStatus.SERVED and item.payment_links:
        item.status = OrderItemStatus.PAID
    else:
        item.status = next_status
    order.recalc_status()
    log_order_status_change(
        order,
        prev_fulfillment,
        prev_payment,
        staff_user=user,
        details={"source": "mobile/toggle_item_served", "item_id": item.id},
    )
    db.session.commit()
    emit_order_update(order)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return ("", 204)

    return redirect(url_for("mobile.table_orders", table_id=order.table_id, order_id=order.id))