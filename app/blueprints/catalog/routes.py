from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ...extensions import db
from ...models import InventoryEntry, Product

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
