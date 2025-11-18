from __future__ import annotations

import pytest

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Extra, Order, OrderItem, OrderItemExtra, Product, ProductExtra, Table


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
