from __future__ import annotations

from typing import Mapping

from .models import OrderItem, OrderItemExtra, Product


def _extra_field_name(product_id: int, extra_id: int) -> str:
    return f"extra_{product_id}_{extra_id}"


def collect_extra_counts(form_data: Mapping[str, str], product: Product) -> dict[int, int]:
    """Extract quantity per extra for the provided product from submitted form data."""
    if not product.product_extras:
        return {}
    counts: dict[int, int] = {}
    for link in product.product_extras:
        if not link.extra or not link.extra.is_active:
            continue
        field = _extra_field_name(product.id, link.extra_id)
        raw_value = form_data.get(field)
        if raw_value in (None, ""):
            continue
        try:
            quantity = max(int(raw_value), 0)
        except (ValueError, TypeError):
            continue
        if quantity > 0:
            counts[link.extra_id] = quantity
    return counts


def apply_extras_to_item(item: OrderItem, extra_counts: dict[int, int], product: Product | None = None) -> None:
    """Attach OrderItemExtra rows to the item using the provided counts."""
    if not extra_counts:
        return
    product_links = product.product_extras if product else []
    extras_lookup = {
        link.extra_id: link.extra
        for link in product_links
        if link.extra and link.extra.is_active
    }
    for extra_id, quantity in extra_counts.items():
        extra = extras_lookup.get(extra_id)
        if not extra:
            continue
        item.extras.append(
            OrderItemExtra(
                extra_id=extra.id,
                label=extra.name,
                price_delta=extra.price_delta,
                quantity=quantity,
            )
        )


def extra_field_name(product_id: int, extra_id: int) -> str:
    """Expose field naming convention for templates."""
    return _extra_field_name(product_id, extra_id)
