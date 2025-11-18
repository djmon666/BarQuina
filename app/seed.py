from __future__ import annotations

from random import choice, randint

from .extensions import db
from .models import Extra, Order, OrderItem, OrderItemExtra, Product, ProductExtra, StaffUser, Table


def seed_demo_data() -> None:
    db.drop_all()
    db.create_all()

    tables = [Table(name=f"Taula {i}", seats=4) for i in range(1, 7)]
    db.session.add_all(tables)

    staff = [
        StaffUser(name="Anna"),
        StaffUser(name="Marc"),
        StaffUser(name="Júlia"),
    ]
    db.session.add_all(staff)

    products = [
        Product(name="Cafè", category="beguda", price=1.5),
        Product(name="Cervesa artesana", category="beguda", price=4.0),
        Product(name="Entrepà vegetarià", category="menjar", price=6.5),
        Product(name="Tapa braves", category="menjar", price=5.0),
    ]
    db.session.add_all(products)
    db.session.flush()

    extras = [
        Extra(name="Formatge", price_delta=0.5),
        Extra(name="Bacon", price_delta=1.0),
        Extra(name="Sense gluten", price_delta=0.3),
    ]
    db.session.add_all(extras)
    db.session.flush()

    food_products = [product for product in products if product.category == "menjar"]
    for product in food_products:
        for extra in extras:
            db.session.add(ProductExtra(product_id=product.id, extra_id=extra.id))

    db.session.commit()

    for table in tables[:3]:
        order = Order(table_id=table.id, created_by_id=choice(staff).id)
        order.sync_legacy_status()
        db.session.add(order)
        db.session.flush()

        for _ in range(randint(2, 4)):
            product = choice(products)
            quantity = randint(1, 2)
            item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=product.price,
            )
            db.session.add(item)
            db.session.flush()

            available_extras = [link.extra for link in product.product_extras]
            if available_extras and randint(0, 1):
                extra = choice(available_extras)
                db.session.add(
                    OrderItemExtra(
                        order_item_id=item.id,
                        extra_id=extra.id,
                        label=extra.name,
                        price_delta=extra.price_delta,
                        quantity=quantity,
                    )
                )

    db.session.commit()
