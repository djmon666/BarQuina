from __future__ import annotations

from typing import Iterable

from sqlalchemy import inspect, text

from .extensions import db
from .models import FulfillmentStatus, PaymentStatus


LEGACY_FULFILLED_VALUES: set[str] = {"servida", "served", "cobrada", "paid"}
LEGACY_PAID_VALUES: set[str] = {"cobrada", "paid"}


def ensure_legacy_schema() -> None:
    """Add new columns to legacy databases when missing."""
    db.create_all()
    engine = db.engine

    with engine.connect() as connection:
        if not engine.dialect.has_table(connection, "orders"):
            return
        inspector = inspect(connection)
        column_names = {column["name"] for column in inspector.get_columns("orders")}

    statements: list[str] = []
    added_columns = False
    if "fulfillment_status" not in column_names:
        statements.append(
            f"ALTER TABLE orders ADD COLUMN fulfillment_status VARCHAR(32) NOT NULL DEFAULT '{FulfillmentStatus.PENDING_DELIVERY.name}'"
        )
        added_columns = True
    if "payment_status" not in column_names:
        statements.append(
            f"ALTER TABLE orders ADD COLUMN payment_status VARCHAR(32) NOT NULL DEFAULT '{PaymentStatus.PENDING_PAYMENT.name}'"
        )
        added_columns = True

    if statements:
        _apply_ddl(statements)
        column_names.update({"fulfillment_status", "payment_status"})

    if "status" in column_names and added_columns:
        _backfill_from_legacy_status()

    if {"fulfillment_status", "payment_status"}.issubset(column_names):
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
