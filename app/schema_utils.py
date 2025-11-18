from __future__ import annotations

from typing import Iterable

from sqlalchemy import inspect, text

from .extensions import db
from .models import Category, FulfillmentStatus, PaymentStatus, Product


LEGACY_FULFILLED_VALUES: set[str] = {"servida", "served", "cobrada", "paid"}
LEGACY_PAID_VALUES: set[str] = {"cobrada", "paid"}

DEFAULT_CATEGORIES: tuple[tuple[str, bool, int], ...] = (
    ("Begudes", True, 10),
    ("Aperitius", True, 20),
    ("Menjar", False, 30),
    ("Postres", False, 40),
    ("Altres", False, 50),
)

CATEGORY_ALIASES: dict[str, str] = {
    "beguda": "Begudes",
    "begudes": "Begudes",
    "beure": "Begudes",
    "aperitiu": "Aperitius",
    "aperitius": "Aperitius",
    "menjar": "Menjar",
    "postre": "Postres",
    "postres": "Postres",
    "altres": "Altres",
}


def ensure_legacy_schema() -> None:
    """Add new columns to legacy databases when missing."""
    db.create_all()
    engine = db.engine

    with engine.connect() as connection:
        inspector = inspect(connection)
        orders_columns: set[str] = set()
        products_columns: set[str] = set()
        if engine.dialect.has_table(connection, "orders"):
            orders_columns = {column["name"] for column in inspector.get_columns("orders")}
        if engine.dialect.has_table(connection, "products"):
            products_columns = {column["name"] for column in inspector.get_columns("products")}

    if orders_columns:
        _ensure_order_status_columns(orders_columns)
    _ensure_category_defaults()
    _ensure_product_category_links(products_columns)


def _ensure_order_status_columns(existing_columns: set[str]) -> None:
    statements: list[str] = []
    added_columns = False
    if "fulfillment_status" not in existing_columns:
        statements.append(
            f"ALTER TABLE orders ADD COLUMN fulfillment_status VARCHAR(32) NOT NULL DEFAULT '{FulfillmentStatus.PENDING_DELIVERY.name}'"
        )
        added_columns = True
    if "payment_status" not in existing_columns:
        statements.append(
            f"ALTER TABLE orders ADD COLUMN payment_status VARCHAR(32) NOT NULL DEFAULT '{PaymentStatus.PENDING_PAYMENT.name}'"
        )
        added_columns = True

    if statements:
        _apply_ddl(statements)
        existing_columns.update({"fulfillment_status", "payment_status"})

    if "status" in existing_columns and added_columns:
        _backfill_from_legacy_status()

    if {"fulfillment_status", "payment_status"}.issubset(existing_columns):
        _normalize_status_columns()


def _apply_ddl(statements: Iterable[str]) -> None:
    with db.engine.begin() as connection:
        for stmt in statements:
            connection.execute(text(stmt))


def _backfill_from_legacy_status() -> None:
    with db.engine.begin() as connection:
        rows = connection.execute(text("SELECT id, status FROM orders")).fetchall()
        for order_id, legacy_status in rows:
            fulfillment, payment = _map_legacy_status(str(legacy_status or ""))
            connection.execute(
                text(
                    "UPDATE orders SET fulfillment_status=:fulfillment, payment_status=:payment WHERE id=:order_id"
                ),
                {"fulfillment": fulfillment, "payment": payment, "order_id": order_id},
            )


def _map_legacy_status(raw_value: str) -> tuple[str, str]:
    normalized = raw_value.strip().lower()
    fulfillment = FulfillmentStatus.PENDING_DELIVERY.name
    payment = PaymentStatus.PENDING_PAYMENT.name

    if normalized in LEGACY_FULFILLED_VALUES:
        fulfillment = FulfillmentStatus.SERVED.name
    if normalized in LEGACY_PAID_VALUES:
        payment = PaymentStatus.PAID.name

    return fulfillment, payment


def _normalize_status_columns() -> None:
    replacements = {
        "fulfillment_status": {member.value: member.name for member in FulfillmentStatus},
        "payment_status": {member.value: member.name for member in PaymentStatus},
    }

    with db.engine.begin() as connection:
        for column, mapping in replacements.items():
            for raw_value, canonical in mapping.items():
                connection.execute(
                    text(f"UPDATE orders SET {column}=:canonical WHERE {column}=:raw"),
                    {"canonical": canonical, "raw": raw_value},
                )


def _ensure_category_defaults() -> None:
    existing_names = {name for name, *_ in db.session.query(Category.name).all()}
    created = False
    for name, auto_prepare, sort_order in DEFAULT_CATEGORIES:
        if name not in existing_names:
            db.session.add(
                Category(name=name, auto_prepare=auto_prepare, sort_order=sort_order, is_active=True)
            )
            created = True
    if created:
        db.session.commit()


def _ensure_product_category_links(product_columns: set[str]) -> None:
    if not product_columns:
        return

    if "category_id" not in product_columns:
        _apply_ddl(["ALTER TABLE products ADD COLUMN category_id INTEGER"])
        product_columns.add("category_id")

    pending = Product.query.filter(Product.category_id.is_(None)).all()
    if not pending:
        return

    categories = {category.name.lower(): category for category in Category.query.all()}
    default_category = categories.get("altres") or next(iter(categories.values()), None)
    if not default_category:
        return

    updated = False
    for product in pending:
        candidate = (product.legacy_category or "").strip().lower()
        mapped_name = CATEGORY_ALIASES.get(candidate, None)
        target = None
        if candidate and candidate in categories:
            target = categories[candidate]
        elif mapped_name and mapped_name.lower() in categories:
            target = categories[mapped_name.lower()]
        else:
            target = default_category

        if not target:
            continue

        product.category_id = target.id
        if not product.legacy_category:
            product.legacy_category = target.name.lower()
        updated = True

    if updated:
        db.session.commit()
