from __future__ import annotations

from random import choice, randint

from .extensions import db
from .models import Category, Extra, Order, OrderItem, OrderItemExtra, Product, ProductExtra, StaffUser, Table


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

    categories = [
        Category(name="Begudes", sort_order=10, auto_prepare=True, is_active=True),
        Category(name="Aperitius", sort_order=20, auto_prepare=True, is_active=True),
        Category(name="Menjar", sort_order=30, auto_prepare=False, is_active=True),
        Category(name="Altres", sort_order=40, auto_prepare=False, is_active=True),
    ]
    db.session.add_all(categories)
    db.session.flush()
    category_map = {category.name: category for category in categories}

    products = [
        Product(name="Cafè", price=1.5, category=category_map["Begudes"]),
        Product(name="Cervesa artesana", price=4.0, category=category_map["Begudes"]),
        Product(name="Entrepà vegetarià", price=6.5, category=category_map["Menjar"]),
        Product(name="Tapa braves", price=5.0, category=category_map["Menjar"]),
    ]
    for product in products:
        product.legacy_category = product.category.name
    db.session.add_all(products)
    db.session.flush()

    extras = [
        Extra(name="Formatge", price_delta=0.5),
        Extra(name="Bacon", price_delta=1.0),
        Extra(name="Sense gluten", price_delta=0.3),
    ]
    db.session.add_all(extras)
    db.session.flush()

    food_products = [product for product in products if product.category and not product.category.auto_prepare]
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
                status=product.initial_item_status(),
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
