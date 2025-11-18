from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ...extensions import db
from ...models import Extra, InventoryEntry, Product, ProductExtra

bp = Blueprint("catalog", __name__)


@bp.route("/products", methods=["GET", "POST"])
def products():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip() or "beguda"
        price = float(request.form.get("price", 0))
        if not name or price <= 0:
            flash("Nom i preu són obligatoris", "danger")
        else:
            db.session.add(Product(name=name, category=category, price=price))
            db.session.commit()
            flash("Producte creat", "success")
        return redirect(url_for("catalog.products"))

    products = Product.query.order_by(Product.category, Product.name).all()
    return render_template("catalog/products.html", products=products)


@bp.route("/products/<int:product_id>/toggle", methods=["POST"])
def toggle_product(product_id: int):
    product = Product.query.get_or_404(product_id)
    product.is_active = not product.is_active
    db.session.commit()
    return redirect(url_for("catalog.products"))


@bp.route("/inventory", methods=["GET", "POST"])
def inventory():
    if request.method == "POST":
        entry = InventoryEntry(
            product_name=request.form.get("product_name", "").strip(),
            category=request.form.get("category", "").strip() or "menjar",
            quantity=int(request.form.get("quantity", 1)),
            unit_cost=float(request.form.get("unit_cost", 0)),
            vendor=request.form.get("vendor", ""),
        )
        if not entry.product_name or entry.unit_cost <= 0:
            flash("Falten dades d'inventari", "danger")
        else:
            db.session.add(entry)
            db.session.commit()
            flash("Compra registrada", "success")
        return redirect(url_for("catalog.inventory"))

    entries = InventoryEntry.query.order_by(InventoryEntry.purchased_at.desc()).limit(50).all()
    return render_template("catalog/inventory.html", entries=entries)


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
    products = Product.query.order_by(Product.category, Product.name).all()
    return render_template("catalog/extras.html", extras=extras_list, products=products)
