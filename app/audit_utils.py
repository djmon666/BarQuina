from __future__ import annotations

from typing import Any

from .extensions import db
from .models import (
    FulfillmentStatus,
    Order,
    OrderAuditLog,
    PaymentStatus,
    StaffUser,
)


def _enum_value(value: Any) -> Any:
    if isinstance(value, (FulfillmentStatus, PaymentStatus)):
        return value.value
    return value


def log_order_event(
    order: Order,
    action: str,
    *,
    staff_user: StaffUser | None = None,
    actor_name: str | None = None,
    details: dict[str, Any] | None = None,
) -> OrderAuditLog:
    """Persist a generic order audit entry."""
    
    # Handle AnonymousUser case (when LOGIN_DISABLED in tests)
    staff_id = None
    staff_name = actor_name
    
    if staff_user and hasattr(staff_user, 'id'):
        staff_id = staff_user.id
        staff_name = actor_name or staff_user.name

    entry = OrderAuditLog(
        order_id=order.id,
        table_id=order.table_id,
        staff_user_id=staff_id,
        actor_name=staff_name,
        action=action,
        details=details or {},
    )
    db.session.add(entry)
    return entry


def log_order_status_change(
    order: Order,
    prev_fulfillment: FulfillmentStatus | None,
    prev_payment: PaymentStatus | None,
    *,
    staff_user: StaffUser | None = None,
    actor_name: str | None = None,
    details: dict[str, Any] | None = None,
) -> OrderAuditLog | None:
    """Log an entry if the order's fulfillment or payment status changes."""

    changes: dict[str, Any] = {}
    if prev_fulfillment != order.fulfillment_status:
        changes["fulfillment"] = {
            "from": _enum_value(prev_fulfillment),
            "to": _enum_value(order.fulfillment_status),
        }
    if prev_payment != order.payment_status:
        changes["payment"] = {
            "from": _enum_value(prev_payment),
            "to": _enum_value(order.payment_status),
        }

    if not changes:
        return None

    payload = {**changes, **(details or {})}
    return log_order_event(
        order,
        "order_status_updated",
        staff_user=staff_user,
        actor_name=actor_name,
        details=payload,
    )
