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
    CashMovement,
    CashMovementType,
    CashSession,
    Extra,
    FulfillmentStatus,
    InventoryEntry,
    Order,
    OrderAuditLog,
    OrderItem,
    OrderItemExtra,
    OrderItemStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
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
    TestConfig.LOGIN_DISABLED = True  # Disable authentication for tests

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


def _login_mobile_user(client, user_id: int, user_name: str) -> None:
    with client.session_transaction() as session_state:
        session_state["mobile_user_id"] = user_id
        session_state["mobile_user_name"] = user_name


def test_homepage_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Quadre general" in response.data


def test_mobile_page_loads(client):
    response = client.get("/mobile/tables")
    assert response.status_code == 200


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


def test_mobile_stress_orders_and_status_churn(client):
    with client.application.app_context():
        staff = StaffUser(name="Stress", is_active=True)
        table = Table(name="Simulacre", seats=6)
        category = _get_category("Menjar", sort_order=10)
        product = Product(name="Stress Burger", price=9.5, category=category)
        db.session.add_all([staff, table, product])
        db.session.commit()
        staff_id = staff.id
        staff_name = staff.name
        table_id = table.id
        product_id = product.id

    _login_mobile_user(client, staff_id, staff_name)

    created_order_ids: list[int] = []
    for _ in range(10):
        response = client.post(f"/mobile/tables/{table_id}/orders")
        assert response.status_code == 302

    with client.application.app_context():
        created_order_ids = [order.id for order in Order.query.order_by(Order.id).all()]
        assert len(created_order_ids) == 10

    for order_id in created_order_ids:
        payload = {f"quantity_{product_id}": "1"}
        resp = client.post(f"/mobile/orders/{order_id}/add-items", data=payload, follow_redirects=False)
        assert resp.status_code == 302

    with client.application.app_context():
        order_item_pairs = []
        for order in Order.query.filter(Order.id.in_(created_order_ids)).all():
            assert order.items, "Each order should have at least one item after stress add"
            order_item_pairs.append((order.id, order.items[0].id))

    for order_id, item_id in order_item_pairs:
        # Rapidly toggle served/prepared states to mimic hectic service flow
        for _ in range(5):
            resp = client.post(f"/mobile/orders/{order_id}/items/{item_id}/toggle-served")
            assert resp.status_code == 302

    with client.application.app_context():
        refreshed_orders = Order.query.filter(Order.id.in_(created_order_ids)).all()
        assert len(refreshed_orders) == 10
        for order in refreshed_orders:
            assert order.items[0].status in {OrderItemStatus.PREPARED, OrderItemStatus.SERVED, OrderItemStatus.PAID}


def test_mobile_paid_order_blocks_additions_but_allows_toggle(client):
    with client.application.app_context():
        staff = StaffUser(name="Locked", is_active=True)
        table = Table(name="Taula Tancada", seats=2)
        category = _get_category("Begudes", sort_order=5)
        product = Product(name="Refresc", price=2.5, category=category)
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
        order.payment_status = PaymentStatus.PAID
        db.session.commit()
        order_id = order.id
        item_id = item.id
        product_id = product.id
        staff_id = staff.id
        staff_name = staff.name

    _login_mobile_user(client, staff_id, staff_name)

    add_attempt = client.post(
        f"/mobile/orders/{order_id}/add-items",
        data={f"quantity_{product_id}": "1"},
    )
    assert add_attempt.status_code == 302

    with client.application.app_context():
        refreshed_order = db.session.get(Order, order_id)
        assert refreshed_order is not None
        assert len(refreshed_order.items) == 1

    update_attempt = client.post(
        f"/mobile/orders/{order_id}/items/{item_id}/update",
        data={"change": "increment"},
    )
    assert update_attempt.status_code == 302

    toggle_attempt = client.post(f"/mobile/orders/{order_id}/items/{item_id}/toggle-served")
    assert toggle_attempt.status_code == 302

    with client.application.app_context():
        final_item = db.session.get(OrderItem, item_id)
        assert final_item.quantity == 1
        assert final_item.status == OrderItemStatus.SERVED

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


def test_order_audit_logs_creation_and_status_change(client):
    with client.application.app_context():
        staff = StaffUser(name="Audit", is_active=True)
        table = Table(name="Taula Audit", seats=4)
        category = _get_category("Audit Cat", sort_order=5)
        product = Product(name="Audit Drink", price=2.5, category=category)
        db.session.add_all([staff, table, product])
        db.session.commit()
        staff_id = staff.id
        staff_name = staff.name
        table_id = table.id
        product_id = product.id

    _login_mobile_user(client, staff_id, staff_name)
    create_resp = client.post(f"/mobile/tables/{table_id}/orders")
    assert create_resp.status_code == 302

    with client.application.app_context():
        order = Order.query.order_by(Order.id.desc()).first()
        assert order is not None
        order_id = order.id
        logs = OrderAuditLog.query.filter_by(order_id=order_id).all()
        assert logs
        assert logs[0].action == "order_created"

    payload = {f"quantity_{product_id}": "1"}
    add_items_resp = client.post(f"/mobile/orders/{order_id}/add-items", data=payload)
    assert add_items_resp.status_code == 302

    status_resp = client.post(
        f"/orders/{order_id}/status",
        data={"fulfillment_status": FulfillmentStatus.SERVED.value},
    )
    assert status_resp.status_code == 302

    with client.application.app_context():
        logs = (
            OrderAuditLog.query.filter_by(order_id=order_id)
            .order_by(OrderAuditLog.created_at.asc())
            .all()
        )
        assert any(log.action == "order_status_updated" for log in logs)
        latest = logs[-1]
        assert latest.action == "order_status_updated"
        assert "fulfillment" in latest.details


def test_cash_close_accepts_blank_amount(client):
    with client.application.app_context():
        session = CashSession(opening_float=50.0)
        db.session.add(session)
        db.session.commit()
        session_id = session.id

    response = client.post(f"/cash/sessions/{session_id}/close", data={"closing_amount": ""})
    assert response.status_code == 302

    with client.application.app_context():
        refreshed = db.session.get(CashSession, session_id)
        assert refreshed is not None
        assert refreshed.closing_amount == 0
        assert refreshed.is_open is False


def test_cash_close_rejects_invalid_amount(client):
    with client.application.app_context():
        session = CashSession(opening_float=25.0)
        db.session.add(session)
        db.session.commit()
        session_id = session.id

    response = client.post(
        f"/cash/sessions/{session_id}/close",
        data={"closing_amount": "abc"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with client.application.app_context():
        refreshed = db.session.get(CashSession, session_id)
        assert refreshed is not None
        assert refreshed.closing_amount is None
        assert refreshed.is_open is True


def test_cash_session_can_be_reopened(client):
    with client.application.app_context():
        session = CashSession(opening_float=80.0)
        db.session.add(session)
        db.session.commit()
        session_id = session.id

    close_resp = client.post(
        f"/cash/sessions/{session_id}/close",
        data={"closing_amount": "100.5"},
        follow_redirects=True,
    )
    assert close_resp.status_code == 200

    reopen_resp = client.post(f"/cash/sessions/{session_id}/reopen", follow_redirects=True)
    assert reopen_resp.status_code == 200

    with client.application.app_context():
        refreshed = db.session.get(CashSession, session_id)
        assert refreshed is not None
        assert refreshed.is_open is True
        assert refreshed.closing_amount is None


def test_cash_session_sales_include_order_payments(client):
    with client.application.app_context():
        session = CashSession(opening_float=25.0)
        db.session.add(session)
        table = Table(name="Sessió", seats=2)
        category = _get_category("Menjar Sessió", sort_order=5)
        product = Product(name="Bocata Sessió", price=12.5, category=category)
        db.session.add_all([table, product])
        db.session.flush()
        order = Order(table_id=table.id)
        order.sync_legacy_status()
        db.session.add(order)
        db.session.flush()
        item = OrderItem(order_id=order.id, product_id=product.id, quantity=1, unit_price=product.price)
        db.session.add(item)
        db.session.commit()
        session_id = session.id
        order_id = order.id
        item_id = item.id
        item_total = item.line_total()

    response = client.post(
        f"/orders/{order_id}/payments",
        data={
            "method": PaymentMethod.CASH.value,
            "item_ids": [str(item_id)],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with client.application.app_context():
        refreshed_session = db.session.get(CashSession, session_id)
        assert refreshed_session is not None
        assert refreshed_session.automatic_sales_total == pytest.approx(item_total)
        assert refreshed_session.total_sales == pytest.approx(item_total)
        payment = Payment.query.filter_by(order_id=order_id).one()
        assert payment.cash_session_id == session_id


def test_cash_session_admin_edit_overrides_totals(client):
    with client.application.app_context():
        session = CashSession(opening_float=25.0)
        db.session.add(session)
        db.session.flush()
        db.session.add_all(
            [
                CashMovement(session_id=session.id, movement_type=CashMovementType.DEPOSIT, amount=10.0),
                CashMovement(session_id=session.id, movement_type=CashMovementType.WITHDRAWAL, amount=2.0),
                CashMovement(session_id=session.id, movement_type=CashMovementType.ADJUSTMENT, amount=1.0),
            ]
        )
        db.session.commit()
        session_id = session.id

    response = client.post(
        f"/cash/sessions/{session_id}/edit",
        data={
            "opening_float": "50",
            "deposits_override": "40",
            "withdrawals_override": "",
            "adjustments_override": "2.5",
            "closing_amount": "95",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with client.application.app_context():
        updated = db.session.get(CashSession, session_id)
        assert updated is not None
        assert updated.opening_float == pytest.approx(50)
        assert updated.total_deposits == pytest.approx(40)
        assert updated.deposits_override == pytest.approx(40)
        # withdrawals override left blank, should fall back to movement total (2)
        assert updated.withdrawals_override is None
        assert updated.total_withdrawals == pytest.approx(2)
        assert updated.total_adjustments == pytest.approx(2.5)
        assert updated.closing_amount == pytest.approx(95)
        expected = updated.expected_closing_amount
        assert expected == pytest.approx(50 + updated.total_sales + 40 - 2 + 2.5)

def test_cash_session_totals_and_expected_amount(client):
    with client.application.app_context():
        session = CashSession(opening_float=100.0)
        db.session.add(session)
        db.session.flush()
        movements = [
            CashMovement(session_id=session.id, movement_type=CashMovementType.SALE, amount=50.0),
            CashMovement(session_id=session.id, movement_type=CashMovementType.DEPOSIT, amount=20.0),
            CashMovement(session_id=session.id, movement_type=CashMovementType.WITHDRAWAL, amount=10.0),
            CashMovement(session_id=session.id, movement_type=CashMovementType.ADJUSTMENT, amount=3.0),
        ]
        db.session.add_all(movements)
        session.closing_amount = 160.0
        db.session.commit()
        session_id = session.id

    with client.application.app_context():
        refreshed = db.session.get(CashSession, session_id)
        assert refreshed is not None
        assert refreshed.total_sales == pytest.approx(50.0)
        assert refreshed.total_deposits == pytest.approx(20.0)
        assert refreshed.total_withdrawals == pytest.approx(10.0)
        assert refreshed.total_adjustments == pytest.approx(3.0)
        assert refreshed.movement_net_total == pytest.approx(63.0)
        assert refreshed.expected_closing_amount == pytest.approx(163.0)
        assert refreshed.closing_difference == pytest.approx(-3.0)


def test_cash_sessions_page_displays_movement_net_and_difference(client):
    with client.application.app_context():
        session = CashSession(opening_float=41.23)
        db.session.add(session)
        db.session.flush()
        db.session.add_all(
            [
                CashMovement(session_id=session.id, movement_type=CashMovementType.SALE, amount=10.10),
                CashMovement(session_id=session.id, movement_type=CashMovementType.DEPOSIT, amount=5.50),
                CashMovement(session_id=session.id, movement_type=CashMovementType.WITHDRAWAL, amount=3.60),
                CashMovement(session_id=session.id, movement_type=CashMovementType.ADJUSTMENT, amount=0.75),
            ]
        )
        session.closing_amount = 52.50
        db.session.commit()

    response = client.get("/cash/sessions")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Mov. net" in html
    assert "€ 12.75" in html
    assert "€ 53.98" in html
    assert "€ -1.48" in html


def test_inventory_entry_links_to_cash_session(client):
    with client.application.app_context():
        session = CashSession(opening_float=100.0)
        db.session.add(session)
        db.session.commit()
        session_id = session.id

    response = client.post(
        "/catalog/inventory",
        data={
            "product_name": "Pa de motlle",
            "category": "menjar",
            "quantity": "10",
            "unit_cost": "2.5",
            "vendor": "Forn local",
            "cash_session_id": str(session_id),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with client.application.app_context():
        entry = InventoryEntry.query.filter_by(product_name="Pa de motlle").first()
        assert entry is not None
        assert entry.cash_session_id == session_id
        assert entry.total_cost == pytest.approx(25.0)
        refreshed_session = db.session.get(CashSession, session_id)
        assert refreshed_session.inventory_costs == pytest.approx(25.0)


def test_cash_session_net_profit_calculation(client):
    with client.application.app_context():
        session = CashSession(opening_float=50.0)
        db.session.add(session)
        db.session.flush()
        db.session.add_all(
            [
                CashMovement(session_id=session.id, movement_type=CashMovementType.SALE, amount=100.0),
                CashMovement(session_id=session.id, movement_type=CashMovementType.DEPOSIT, amount=20.0),
                InventoryEntry(
                    product_name="Ingredient A",
                    category="menjar",
                    quantity=5,
                    unit_cost=3.0,
                    cash_session_id=session.id,
                ),
                InventoryEntry(
                    product_name="Ingredient B",
                    category="menjar",
                    quantity=2,
                    unit_cost=10.0,
                    cash_session_id=session.id,
                ),
            ]
        )
        db.session.commit()
        session_id = session.id

    with client.application.app_context():
        refreshed = db.session.get(CashSession, session_id)
        assert refreshed is not None
        assert refreshed.movement_net_total == pytest.approx(120.0)
        assert refreshed.inventory_costs == pytest.approx(35.0)
        assert refreshed.net_profit == pytest.approx(85.0)


def test_inventory_entry_can_be_edited(client):
    with client.application.app_context():
        entry = InventoryEntry(
            product_name="Original",
            category="menjar",
            quantity=10,
            unit_cost=5.0,
        )
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

    response = client.post(
        f"/catalog/inventory/{entry_id}/edit",
        data={
            "product_name": "Actualitzat",
            "category": "beguda",
            "quantity": "15",
            "unit_cost": "3.5",
            "vendor": "Nou proveïdor",
            "cash_session_id": "",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with client.application.app_context():
        updated = db.session.get(InventoryEntry, entry_id)
        assert updated is not None
        assert updated.product_name == "Actualitzat"
        assert updated.category == "beguda"
        assert updated.quantity == 15
        assert updated.unit_cost == pytest.approx(3.5)
        assert updated.vendor == "Nou proveïdor"
        assert updated.total_cost == pytest.approx(52.5)


def test_inventory_entry_can_be_deleted(client):
    with client.application.app_context():
        entry = InventoryEntry(
            product_name="To Delete",
            category="menjar",
            quantity=5,
            unit_cost=2.0,
        )
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

    response = client.post(f"/catalog/inventory/{entry_id}/delete", follow_redirects=True)
    assert response.status_code == 200

    with client.application.app_context():
        deleted = db.session.get(InventoryEntry, entry_id)
        assert deleted is None


def test_bar_queue_shows_auto_prepared_items(client):
    """Test that bar queue shows auto-prepared items that are prepared but not served."""
    with client.application.app_context():
        table = Table(name="T1", seats=4)
        
        # Create auto-prepared category (drinks, etc.)
        drinks_category = _get_category("Begudes", auto_prepare=True)
        
        # Create products
        beer = Product(name="Cervesa", price=2.5, category=drinks_category)
        
        db.session.add_all([table, beer])
        db.session.commit()
        
        # Create order with auto-prepared item
        order = Order(table_id=table.id)
        db.session.add(order)
        db.session.flush()
        
        # Auto-prepared items start in PREPARED status
        item = OrderItem(
            order_id=order.id,
            product_id=beer.id,
            quantity=2,
            unit_price=beer.price,
            status=OrderItemStatus.PREPARED,
        )
        db.session.add(item)
        db.session.commit()
        
        order_id = order.id
        item_id = item.id
    
    # Bar queue should show this item
    response = client.get("/bar/")
    assert response.status_code == 200
    assert b"Cervesa" in response.data
    assert b"Per servir" in response.data
    
    # Mark item as served
    response = client.post(f"/bar/orders/{order_id}/items/{item_id}/served", follow_redirects=True)
    assert response.status_code == 200
    
    with client.application.app_context():
        item = db.session.get(OrderItem, item_id)
        assert item.status == OrderItemStatus.SERVED
    
    # Item should no longer appear in bar queue
    response = client.get("/bar/")
    assert response.status_code == 200
    assert b"No hi ha comandes pendents de barra" in response.data


def test_bar_mark_all_served(client):
    """Test marking all bar items in an order as served."""
    with client.application.app_context():
        table = Table(name="T2", seats=4)
        drinks_category = _get_category("Begudes", auto_prepare=True)
        
        beer = Product(name="Cervesa", price=2.5, category=drinks_category)
        wine = Product(name="Vi", price=3.0, category=drinks_category)
        
        db.session.add_all([table, beer, wine])
        db.session.commit()
        
        order = Order(table_id=table.id)
        db.session.add(order)
        db.session.flush()
        
        item1 = OrderItem(
            order_id=order.id,
            product_id=beer.id,
            quantity=2,
            unit_price=beer.price,
            status=OrderItemStatus.PREPARED,
        )
        item2 = OrderItem(
            order_id=order.id,
            product_id=wine.id,
            quantity=1,
            unit_price=wine.price,
            status=OrderItemStatus.PREPARED,
        )
        db.session.add_all([item1, item2])
        db.session.commit()
        
        order_id = order.id
    
    # Mark all items as served
    response = client.post(f"/bar/orders/{order_id}/all-served", follow_redirects=True)
    assert response.status_code == 200
    assert b"2 productes de barra servits" in response.data
    
    with client.application.app_context():
        order = db.session.get(Order, order_id)
        for item in order.items:
            assert item.status == OrderItemStatus.SERVED
