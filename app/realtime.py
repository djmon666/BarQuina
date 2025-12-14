from __future__ import annotations

from typing import Protocol

from .extensions import socketio


class SupportsOrderLike(Protocol):
    id: int
    table_id: int

    def subtotal(self) -> float: ...

    def outstanding_total(self) -> float: ...

    fulfillment_status: any
    payment_status: any


def emit_order_update(order: SupportsOrderLike) -> None:
    payload = {
        "order_id": order.id,
        "table_id": order.table_id,
        "fulfillment_status": getattr(order.fulfillment_status, "value", str(order.fulfillment_status)),
        "payment_status": getattr(order.payment_status, "value", str(order.payment_status)),
        "subtotal": order.subtotal(),
        "outstanding_total": order.outstanding_total(),
    }
    socketio.emit("order_updated", payload)


def emit_order_created(order: SupportsOrderLike) -> None:
    payload = {
        "order_id": order.id,
        "table_id": order.table_id,
        "fulfillment_status": getattr(order.fulfillment_status, "value", str(order.fulfillment_status)),
        "payment_status": getattr(order.payment_status, "value", str(order.payment_status)),
        "subtotal": order.subtotal(),
        "outstanding_total": order.outstanding_total(),
    }
    socketio.emit("order_created", payload)


def emit_print_request(content: str, print_type: str = "receipt") -> None:
    """
    Envia una petició d'impressió via websocket
    
    Args:
        content: Contingut a imprimir
        print_type: Tipus d'impressió ('receipt', 'kitchen', etc.)
    """
    payload = {
        "content": content,
        "type": print_type
    }
    socketio.emit("print_request", payload)
