from __future__ import annotations

from random import choice, randint

from .extensions import db
from .models import Order, OrderItem, Product, StaffUser, Table


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
    db.session.commit()

    for table in tables[:3]:
        order = Order(table_id=table.id, created_by_id=choice(staff).id)
        order.sync_legacy_status()
        db.session.add(order)
        db.session.flush()

        for _ in range(randint(2, 4)):
            product = choice(products)
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=randint(1, 2),
                    unit_price=product.price,
                )
            )

    db.session.commit()
