from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy.orm import validates

from .extensions import db


class FulfillmentStatus(str, Enum):
    PENDING_DELIVERY = "pendent_portar"
    SERVED = "servida"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ")


class PaymentStatus(str, Enum):
    PENDING_PAYMENT = "pendent_cobrar"
    PAID = "cobrada"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ")


class OrderItemStatus(str, Enum):
    PENDING = "pendent"
    PREPARED = "preparat"
    SERVED = "servida"
    PAID = "cobrada"

    @property
    def label(self) -> str:
        custom = {
            OrderItemStatus.PENDING: "Per preparar",
            OrderItemStatus.PREPARED: "Preparat",
        }
        return custom.get(self, self.value.replace("_", " "))


class PaymentMethod(str, Enum):
    CASH = "efectiu"
    CARD = "targeta"
    MIXED = "mixt"


class CashMovementType(str, Enum):
    SALE = "venda"
    DEPOSIT = "entrada"
    WITHDRAWAL = "sortida"
    ADJUSTMENT = "ajust"


class Table(db.Model):
    __tablename__ = "tables"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    seats = db.Column(db.Integer, default=4)
    orders = db.relationship("Order", back_populates="table", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"Table({self.name})"


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    auto_prepare = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    products = db.relationship("Product", back_populates="category")

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"Category({self.name})"


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    legacy_category = db.Column("category", db.String(30))
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    price = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    order_items = db.relationship("OrderItem", back_populates="product")
    product_extras = db.relationship(
        "ProductExtra",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="joined",
    )
    extras = db.relationship(
        "Extra",
        secondary="product_extras",
        viewonly=True,
        lazy="joined",
        order_by="Extra.name",
    )

    category = db.relationship("Category", back_populates="products", lazy="joined")

    @property
    def category_name(self) -> str:
        if self.category:
            return self.category.name
        return self.legacy_category or ""

    @property
    def is_auto_prepared(self) -> bool:
        return bool(self.category and self.category.auto_prepare)

    def initial_item_status(self) -> OrderItemStatus:
        return OrderItemStatus.PREPARED if self.is_auto_prepared else OrderItemStatus.PENDING

    @validates("category")
    def _sync_legacy_category(self, key: str, category: Category | None) -> Category | None:
        if category and category.name:
            self.legacy_category = category.name
        return category

    def __repr__(self) -> str:  # pragma: no cover
        return f"Product({self.name})"


class InventoryEntry(db.Model):
    __tablename__ = "inventory_entries"

    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(80), nullable=False)
    category = db.Column(db.String(30), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False)
    vendor = db.Column(db.String(80))
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)


class StaffUser(db.Model):
    __tablename__ = "staff_users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    orders = db.relationship("Order", back_populates="created_by")

    def __repr__(self) -> str:  # pragma: no cover
        return f"StaffUser({self.name})"


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey("tables.id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("staff_users.id"))
    status = db.Column(db.String(32), default=FulfillmentStatus.PENDING_DELIVERY.value, nullable=False)
    fulfillment_status = db.Column(
        db.Enum(FulfillmentStatus), default=FulfillmentStatus.PENDING_DELIVERY, nullable=False
    )
    payment_status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.PENDING_PAYMENT, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    table = db.relationship("Table", back_populates="orders")
    created_by = db.relationship("StaffUser", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = db.relationship("Payment", back_populates="order", cascade="all, delete-orphan")

    def subtotal(self) -> float:
        return sum(item.line_total() for item in self.items)

    def paid_total(self) -> float:
        return sum(payment.amount for payment in self.payments)

    def outstanding_total(self) -> float:
        return max(self.subtotal() - self.paid_total(), 0.0)

    def recalc_status(self) -> None:
        served_like_statuses = {OrderItemStatus.SERVED, OrderItemStatus.PAID}
        if self.items and all(item.status in served_like_statuses for item in self.items):
            self.fulfillment_status = FulfillmentStatus.SERVED
        else:
            self.fulfillment_status = FulfillmentStatus.PENDING_DELIVERY

        if self.subtotal() > 0 and self.outstanding_total() <= 0:
            self.payment_status = PaymentStatus.PAID
        else:
            self.payment_status = PaymentStatus.PENDING_PAYMENT

        self.sync_legacy_status()

    def sync_legacy_status(self) -> None:
        status = self.fulfillment_status or FulfillmentStatus.PENDING_DELIVERY
        if isinstance(status, str):
            self.status = status
        else:
            self.status = status.value

    @property
    def is_closed(self) -> bool:
        return self.fulfillment_status == FulfillmentStatus.SERVED and self.payment_status == PaymentStatus.PAID

    @property
    def is_open(self) -> bool:
        return not self.is_closed


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(OrderItemStatus), default=OrderItemStatus.PENDING, nullable=False)
    notes = db.Column(db.String(120))

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")
    payment_links = db.relationship("PaymentItem", back_populates="order_item", cascade="all, delete-orphan")
    extras = db.relationship("OrderItemExtra", back_populates="order_item", cascade="all, delete-orphan")

    def line_total(self) -> float:
        base_total = self.quantity * self.unit_price
        extras_total = sum(extra.price_delta * extra.quantity for extra in self.extras)
        return round(base_total + extras_total, 2)


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.Enum(PaymentMethod), default=PaymentMethod.CASH, nullable=False)
    note = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order = db.relationship("Order", back_populates="payments")
    items = db.relationship("PaymentItem", back_populates="payment", cascade="all, delete-orphan")


class PaymentItem(db.Model):
    __tablename__ = "payment_items"

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=False)
    order_item_id = db.Column(db.Integer, db.ForeignKey("order_items.id"), nullable=False)

    payment = db.relationship("Payment", back_populates="items")
    order_item = db.relationship("OrderItem", back_populates="payment_links")


class CashSession(db.Model):
    __tablename__ = "cash_sessions"

    id = db.Column(db.Integer, primary_key=True)
    opened_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime)
    opening_float = db.Column(db.Float, nullable=False, default=0.0)
    closing_amount = db.Column(db.Float)
    is_open = db.Column(db.Boolean, default=True)

    movements = db.relationship("CashMovement", back_populates="session", cascade="all, delete-orphan")


class CashMovement(db.Model):
    __tablename__ = "cash_movements"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("cash_sessions.id"), nullable=False)
    movement_type = db.Column(db.Enum(CashMovementType), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    note = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship("CashSession", back_populates="movements")


class Extra(db.Model):
    __tablename__ = "extras"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    price_delta = db.Column(db.Float, nullable=False, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.String(160))

    product_links = db.relationship("ProductExtra", back_populates="extra", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"Extra({self.name}, +{self.price_delta})"


class ProductExtra(db.Model):
    __tablename__ = "product_extras"

    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    extra_id = db.Column(db.Integer, db.ForeignKey("extras.id", ondelete="CASCADE"), primary_key=True)
    is_default = db.Column(db.Boolean, default=False)
    max_quantity = db.Column(db.Integer)

    product = db.relationship("Product", back_populates="product_extras")
    extra = db.relationship("Extra", back_populates="product_links", lazy="joined")


class OrderItemExtra(db.Model):
    __tablename__ = "order_item_extras"

    id = db.Column(db.Integer, primary_key=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey("order_items.id"), nullable=False)
    extra_id = db.Column(db.Integer, db.ForeignKey("extras.id", ondelete="SET NULL"))
    label = db.Column(db.String(80), nullable=False)
    price_delta = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    order_item = db.relationship("OrderItem", back_populates="extras")
    extra = db.relationship("Extra")

    def total(self) -> float:
        return round(self.price_delta * self.quantity, 2)


class OrderAuditLog(db.Model):
    __tablename__ = "order_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    table_id = db.Column(db.Integer, db.ForeignKey("tables.id"), nullable=False)
    staff_user_id = db.Column(db.Integer, db.ForeignKey("staff_users.id"))
    actor_name = db.Column(db.String(120))
    action = db.Column(db.String(64), nullable=False)
    details = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    order = db.relationship("Order", backref="audit_logs")
    table = db.relationship("Table")
    staff_user = db.relationship("StaffUser")

    def __repr__(self) -> str:  # pragma: no cover
        return f"OrderAuditLog(order={self.order_id}, action={self.action})"
