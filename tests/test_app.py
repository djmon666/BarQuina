from __future__ import annotations

import warnings

import pytest
from sqlalchemy.exc import LegacyAPIWarning
import json

warnings.filterwarnings("ignore", category=LegacyAPIWarning)
warnings.filterwarnings("ignore", message=".*LegacyAPIWarning.*")
warnings.simplefilter("ignore", category=LegacyAPIWarning)

pytestmark = pytest.mark.filterwarnings("ignore:.*LegacyAPIWarning.*")

from app import create_app
from app.config import Config
from app.extensions import db
from typing import Any

from app.models import (
    Category,
    Extra,
    Order,
    OrderItem,
    OrderItemExtra,
    OrderItemStatus,
    Product,
    ProductExtra,
    StaffUser,
    Table,
)


class TestConfig(Config):
    TESTING = True


@pytest.fixture()
def client(tmp_path):
    TestConfig.SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'test.db'}"
    TestConfig.SECRET_KEY = "test"

    app = create_app(TestConfig)

    with app.app_context():
        db.create_all()

    with app.test_client() as test_client:
        yield test_client

    with app.app_context():
        db.drop_all()


def _get_category(name: str, **defaults: Any) -> Category:
    category = Category.query.filter_by(name=name).first()
    if category:
        for key, value in defaults.items():
            setattr(category, key, value)
        db.session.flush([category])
        return category

    category = Category(name=name, **defaults)
    db.session.add(category)
    db.session.flush([category])
    return category


def test_homepage_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Quadre general" in response.data


def test_mobile_page_loads(client):
    response = client.get("/mobile/")
    assert response.status_code == 200
    assert b"Qui ets" in response.data


def test_order_item_with_extras_affects_subtotal(client):
    with client.application.app_context():
        table = Table(name="Test", seats=4)
        category = _get_category("Menjar", sort_order=10)
        product = Product(name="Entrepas", price=4.0, category=category)
        extra = Extra(name="Formatge", price_delta=0.5)
        db.session.add_all([table, product, extra])
        db.session.flush()
        db.session.add(ProductExtra(product_id=product.id, extra_id=extra.id))
        order = Order(table_id=table.id)
        order.sync_legacy_status()
        db.session.add(order)
        db.session.flush()
        item = OrderItem(order_id=order.id, product_id=product.id, quantity=1, unit_price=product.price)
        item.extras.append(
            OrderItemExtra(extra_id=extra.id, label=extra.name, price_delta=extra.price_delta, quantity=1)
        )
        db.session.add(item)
        db.session.commit()

        assert item.line_total() == pytest.approx(4.5)
        assert order.subtotal() == pytest.approx(4.5)


def test_kitchen_page_loads(client):
    response = client.get("/kitchen/")
    assert response.status_code == 200
    assert b"Control de cuina" in response.data


def test_kitchen_mark_item_ready(client):
    with client.application.app_context():
        table = Table(name="Cuina", seats=4)
        category = _get_category("Menjar", sort_order=10)
        product = Product(name="Entrepas", price=6.0, category=category)
        db.session.add_all([table, product])
        db.session.flush()
        order = Order(table_id=table.id)
        order.sync_legacy_status()
        db.session.add(order)
        db.session.flush()
        item = OrderItem(order_id=order.id, product_id=product.id, quantity=1, unit_price=product.price)
        db.session.add(item)
        db.session.commit()
        order_id = order.id
        item_id = item.id

    response = client.post(f"/kitchen/orders/{order_id}/items/{item_id}/ready")
    assert response.status_code == 302

    with client.application.app_context():
        updated = db.session.get(OrderItem, item_id)
        assert updated.status == OrderItemStatus.PREPARED


def test_mobile_toggle_served_cycle(client):
    with client.application.app_context():
        staff = StaffUser(name="Mobile", is_active=True)
        table = Table(name="Taula 1", seats=4)
        category = _get_category("Begudes", sort_order=5, auto_prepare=True)
        product = Product(name="Cafe", price=2.0, category=category)
        db.session.add_all([staff, table, product])
        db.session.flush()
        order = Order(table_id=table.id, created_by=staff)
        order.sync_legacy_status()
        db.session.add(order)
        db.session.flush()
        item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=1,
            unit_price=product.price,
            status=OrderItemStatus.PREPARED,
        )
        db.session.add(item)
        db.session.commit()
        order_id = order.id
        item_id = item.id
        user_id = staff.id

    with client.session_transaction() as session_state:
        session_state["mobile_user_id"] = user_id
        session_state["mobile_user_name"] = "Mobile"

    first = client.post(f"/mobile/orders/{order_id}/items/{item_id}/toggle-served")
    assert first.status_code == 302

    with client.application.app_context():
        updated = db.session.get(OrderItem, item_id)
        assert updated.status == OrderItemStatus.SERVED

    second = client.post(f"/mobile/orders/{order_id}/items/{item_id}/toggle-served")
    assert second.status_code == 302

    with client.application.app_context():
        reverted = db.session.get(OrderItem, item_id)
        assert reverted.status == OrderItemStatus.PREPARED


def test_product_initial_status_respects_category_flag(client):
    with client.application.app_context():
        auto_category = _get_category("Begudes", sort_order=5, auto_prepare=True)
        manual_category = _get_category("Menjar", sort_order=10, auto_prepare=False)
        auto_product = Product(name="Refresc", price=2.0, category=auto_category)
        manual_product = Product(name="Entrepas", price=5.0, category=manual_category)
        db.session.add_all([auto_category, manual_category, auto_product, manual_product])
        db.session.flush()

        assert auto_product.initial_item_status() == OrderItemStatus.PREPARED
        assert manual_product.initial_item_status() == OrderItemStatus.PENDING

def test_mobile_add_items_with_food_payload(client):
    with client.application.app_context():
        staff = StaffUser(name="Payload User", is_active=True)
        table = Table(name="Taula Payload", seats=4)
        category = _get_category("Menjar", sort_order=10)
        product = Product(name="Entrepà Payload", price=7.0, category=category)
        extra_one = Extra(name="Formatge", price_delta=0.5)
        extra_two = Extra(name="Tomata", price_delta=0.3)
        db.session.add_all([staff, table, product, extra_one, extra_two])
        db.session.flush()
        db.session.add_all([
            ProductExtra(product_id=product.id, extra_id=extra_one.id),
            ProductExtra(product_id=product.id, extra_id=extra_two.id),
        ])
        order = Order(table_id=table.id, created_by=staff)
        order.sync_legacy_status()
        db.session.add(order)
        db.session.commit()
        order_id = order.id
        staff_id = staff.id
        product_id = product.id
        extra_one_id = extra_one.id
        extra_two_id = extra_two.id
        extra_one_name = extra_one.name
        extra_two_name = extra_two.name

    with client.session_transaction() as session_state:
        session_state["mobile_user_id"] = staff_id
        session_state["mobile_user_name"] = "Payload User"

    payload = [
        {"product_id": product_id, "extras": []},
        {"product_id": product_id, "extras": [extra_one_id, extra_two_id]},
    ]

    response = client.post(
        f"/mobile/orders/{order_id}/add-items",
        data={"food_payload": json.dumps(payload)},
    )
    assert response.status_code == 302

    with client.application.app_context():
        refreshed = db.session.get(Order, order_id)
        assert refreshed is not None
        assert len(refreshed.items) == 2
        for item in refreshed.items:
            assert item.quantity == 1
        extra_sets = [sorted(extra.label for extra in item.extras) for item in refreshed.items]
        assert [] in extra_sets
        assert sorted([extra_one_name, extra_two_name]) in extra_sets


def test_mobile_add_items_mixed_payload_and_quantities(client):
    with client.application.app_context():
        staff = StaffUser(name="Mixt", is_active=True)
        table = Table(name="Taula Mixta", seats=4)
        food_category = _get_category("Menjar", sort_order=10)
        drink_category = _get_category("Begudes", sort_order=5)
        food_product = Product(name="Entrepà Mixt", price=6.0, category=food_category)
        drink_product = Product(name="Begueta", price=2.5, category=drink_category)
        db.session.add_all([staff, table, food_product, drink_product])
        db.session.flush()
        order = Order(table_id=table.id, created_by=staff)
        order.sync_legacy_status()
        db.session.add(order)
        db.session.commit()
        order_id = order.id
        staff_id = staff.id
        food_product_id = food_product.id
        drink_product_id = drink_product.id

    with client.session_transaction() as session_state:
        session_state["mobile_user_id"] = staff_id
        session_state["mobile_user_name"] = "Mixt"

    payload = [{"product_id": food_product_id, "extras": []}]
    form_data = {
        "food_payload": json.dumps(payload),
        f"quantity_{drink_product_id}": "2",
    }

    response = client.post(f"/mobile/orders/{order_id}/add-items", data=form_data)
    assert response.status_code == 302

    with client.application.app_context():
        refreshed = db.session.get(Order, order_id)
        assert refreshed is not None
        assert len(refreshed.items) == 2
        quantities = {item.product_id: item.quantity for item in refreshed.items}
        assert quantities.get(food_product_id) == 1
        assert quantities.get(drink_product_id) == 2
