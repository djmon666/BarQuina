from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models import Category, Extra, InventoryEntry, Product, ProductExtra

bp = Blueprint("catalog", __name__)


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


def _ordered_categories(include_inactive: bool = False) -> list[Category]:
    query = Category.query
    if not include_inactive:
        query = query.filter_by(is_active=True)
    return query.order_by(Category.sort_order, Category.name).all()


@bp.route("/products", methods=["GET", "POST"])
def products():
    categories = _ordered_categories()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price_raw = request.form.get("price")
        category_id = request.form.get("category_id", type=int)
        category = Category.query.get(category_id) if category_id else (categories[0] if categories else None)
        try:
            price = float(price_raw)
        except (TypeError, ValueError):
            price = 0.0
        if not name or price <= 0 or not category:
            flash("Nom, preu i categoria són obligatoris", "danger")
        else:
            product = Product(name=name, price=price, category=category)
            product.legacy_category = category.name
            db.session.add(product)
            db.session.commit()
            flash("Producte creat", "success")
        return redirect(url_for("catalog.products"))

    products = (
        Product.query.options(joinedload(Product.category))
        .join(Product.category)
        .order_by(Category.sort_order, Category.name, Product.name)
        .all()
    )
    return render_template("catalog/products.html", products=products, categories=categories)


@bp.route("/products/<int:product_id>/update", methods=["POST"])
def update_product(product_id: int):
    product = Product.query.get_or_404(product_id)
    name = request.form.get("name", "").strip()
    price_raw = request.form.get("price")
    category_id = request.form.get("category_id", type=int)
    category = Category.query.get(category_id)

    try:
        price = float(price_raw)
    except (TypeError, ValueError):
        price = 0.0

    if not name or price <= 0 or not category:
        flash("Nom, preu i categoria vàlids són obligatoris", "danger")
    else:
        product.name = name
        product.category = category
        product.legacy_category = category.name
        product.price = price
        db.session.commit()
        flash("Producte actualitzat", "success")

    return redirect(url_for("catalog.products"))


@bp.route("/products/<int:product_id>/toggle", methods=["POST"])
def toggle_product(product_id: int):
    product = Product.query.get_or_404(product_id)
    product.is_active = not product.is_active
    db.session.commit()
    return redirect(url_for("catalog.products"))


@bp.route("/inventory", methods=["GET", "POST"])
def inventory():
    if request.method == "POST":
        session_id_raw = request.form.get("cash_session_id", "").strip()
        session_id = int(session_id_raw) if session_id_raw else None
        entry = InventoryEntry(
            product_name=request.form.get("product_name", "").strip(),
            category=request.form.get("category", "").strip() or "menjar",
            quantity=int(request.form.get("quantity", 1)),
            unit_cost=float(request.form.get("unit_cost", 0)),
            vendor=request.form.get("vendor", ""),
            cash_session_id=session_id,
        )
        if not entry.product_name or entry.unit_cost <= 0:
            flash("Falten dades d'inventari", "danger")
        else:
            db.session.add(entry)
            db.session.commit()
            flash("Compra registrada", "success")
        return redirect(url_for("catalog.inventory"))

    from ...models import CashSession

    entries = InventoryEntry.query.order_by(InventoryEntry.purchased_at.desc()).limit(50).all()
    sessions = CashSession.query.order_by(CashSession.opened_at.desc()).limit(20).all()
    return render_template("catalog/inventory.html", entries=entries, sessions=sessions)


@bp.route("/inventory/<int:entry_id>/assign-session", methods=["POST"])
def assign_inventory_session(entry_id: int):
    entry = InventoryEntry.query.get_or_404(entry_id)
    session_id_raw = request.form.get("cash_session_id", "").strip()
    entry.cash_session_id = int(session_id_raw) if session_id_raw else None
    db.session.commit()
    flash("Sessió actualitzada", "success")
    return redirect(url_for("catalog.inventory"))


@bp.route("/inventory/<int:entry_id>/edit", methods=["POST"])
def edit_inventory(entry_id: int):
    entry = InventoryEntry.query.get_or_404(entry_id)
    entry.product_name = request.form.get("product_name", "").strip()
    entry.category = request.form.get("category", "").strip() or "menjar"
    entry.quantity = int(request.form.get("quantity", 1))
    entry.unit_cost = float(request.form.get("unit_cost", 0))
    entry.vendor = request.form.get("vendor", "")
    session_id_raw = request.form.get("cash_session_id", "").strip()
    entry.cash_session_id = int(session_id_raw) if session_id_raw else None
    
    if not entry.product_name or entry.unit_cost <= 0:
        flash("Falten dades d'inventari", "danger")
    else:
        db.session.commit()
        flash("Entrada actualitzada", "success")
    return redirect(url_for("catalog.inventory"))


@bp.route("/inventory/<int:entry_id>/delete", methods=["POST"])
def delete_inventory(entry_id: int):
    entry = InventoryEntry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    flash("Entrada esborrada", "success")
    return redirect(url_for("catalog.inventory"))


@bp.route("/extras", methods=["GET", "POST"])
def extras():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            name = request.form.get("name", "").strip()
            price = request.form.get("price", type=float) or 0.0
            description = request.form.get("description", "").strip()
            if not name or price < 0:
                flash("Nom i preu vàlids són obligatoris", "danger")
            else:
                db.session.add(Extra(name=name, price_delta=price, description=description))
                db.session.commit()
                flash("Extra creat", "success")
        elif action == "toggle":
            extra_id = request.form.get("extra_id", type=int)
            extra = Extra.query.get_or_404(extra_id)
            extra.is_active = not extra.is_active
            db.session.commit()
            flash("Estat de l'extra actualitzat", "info")
        elif action == "assign":
            product_id = request.form.get("product_id", type=int)
            product = Product.query.get_or_404(product_id)
            selected_ids: set[int] = set()
            for value in request.form.getlist("extra_ids"):
                try:
                    selected_ids.add(int(value))
                except (TypeError, ValueError):
                    continue
            product.product_extras = [ProductExtra(product_id=product.id, extra_id=extra_id) for extra_id in selected_ids]
            db.session.commit()
            flash("Extres actualitzats", "success")
        return redirect(url_for("catalog.extras"))

    extras_list = Extra.query.order_by(Extra.name).all()
    products = (
        Product.query.options(joinedload(Product.category))
        .join(Product.category)
        .order_by(Category.sort_order, Category.name, Product.name)
        .all()
    )
    return render_template("catalog/extras.html", extras=extras_list, products=products)


@bp.route("/categories", methods=["GET", "POST"])
def categories():
    if request.method == "POST":
        action = request.form.get("action", "create")
        if action == "create":
            name = request.form.get("name", "").strip()
            sort_order = request.form.get("sort_order", type=int)
            auto_prepare = bool(request.form.get("auto_prepare"))
            if not name:
                flash("El nom és obligatori", "danger")
            elif Category.query.filter(func.lower(Category.name) == name.lower()).first():
                flash("Ja existeix una categoria amb aquest nom", "warning")
            else:
                category = Category(
                    name=name,
                    sort_order=sort_order or 0,
                    auto_prepare=auto_prepare,
                    is_active=True,
                )
                db.session.add(category)
                db.session.commit()
                flash("Categoria creada", "success")
        elif action == "update":
            category_id = request.form.get("category_id", type=int)
            category = Category.query.get_or_404(category_id)
            new_name = request.form.get("name", category.name).strip()
            if new_name and new_name.lower() != category.name.lower():
                conflict = (
                    Category.query.filter(func.lower(Category.name) == new_name.lower(), Category.id != category.id)
                    .first()
                )
                if conflict:
                    flash("Ja existeix una categoria amb aquest nom", "warning")
                    return redirect(url_for("catalog.categories"))
                category.name = new_name
            category.sort_order = request.form.get("sort_order", type=int) or category.sort_order
            category.auto_prepare = bool(request.form.get("auto_prepare"))
            category.is_active = bool(request.form.get("is_active", "0"))
            db.session.commit()
            flash("Categoria actualitzada", "success")
        return redirect(url_for("catalog.categories"))

    categories = _ordered_categories(include_inactive=True)
    return render_template("catalog/categories.html", categories=categories)
