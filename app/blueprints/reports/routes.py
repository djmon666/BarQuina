from __future__ import annotations

from collections import defaultdict

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy import func

from ...extensions import db
from ...models import CashSession, OrderItem, Payment

bp = Blueprint("reports", __name__, url_prefix="/reports")


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


@bp.route("/")
def index():
    """Display profitability and sales statistics per cash session."""
    sessions = CashSession.query.order_by(CashSession.opened_at.desc()).limit(20).all()

    session_stats = []
    for session in sessions:
        # Obtenir tots els OrderItems pagats durant aquesta sessió
        from ...models import Product, OrderItemExtra, PaymentItem
        
        paid_items = (
            db.session.query(OrderItem)
            .join(OrderItem.payment_links)
            .join(Payment)
            .filter(Payment.cash_session_id == session.id)
            .all()
        )
        
        # Agrupar productes amb els seus extres
        product_combinations = defaultdict(int)
        
        for item in paid_items:
            # Obtenir nom del producte
            product = db.session.get(Product, item.product_id)
            if not product:
                continue
            
            product_name = product.name
            
            # Afegir extres si n'hi ha
            if item.extras:
                extras_labels = sorted([extra.label for extra in item.extras])
                if extras_labels:
                    product_name += " (" + ", ".join(extras_labels) + ")"
            
            # Sumar quantitat
            product_combinations[product_name] += item.quantity
        
        # Convertir a llista ordenada per quantitat
        products_sold = [
            {"name": name, "quantity": qty}
            for name, qty in sorted(product_combinations.items(), key=lambda x: -x[1])
        ]

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
