from __future__ import annotations

import warnings

import pytest
from sqlalchemy.exc import LegacyAPIWarning

warnings.filterwarnings("ignore", category=LegacyAPIWarning)
warnings.filterwarnings("ignore", message=".*LegacyAPIWarning.*")
warnings.simplefilter("ignore", category=LegacyAPIWarning)

pytestmark = pytest.mark.filterwarnings("ignore:.*LegacyAPIWarning.*")

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Extra, Order, OrderItem, OrderItemExtra, OrderItemStatus, Product, ProductExtra, StaffUser, Table


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
        product = Product(name="Entrepas", category="menjar", price=4.0)
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
        product = Product(name="Entrepas", category="Menjar", price=6.0)
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
        product = Product(name="Cafe", category="Beure", price=2.0)
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
