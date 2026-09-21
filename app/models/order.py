from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, Float, Text, DateTime
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Banner(BaseModel):
    __tablename__ = "banners"
    
    title = Column(String(255), nullable=False)
    subtitle = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=False)
    mobile_image_url = Column(String(500), nullable=True)
    alt_text = Column(String(255), nullable=True)
    link_type = Column(String(50), default="custom", nullable=True) # product, category, brand, collection, shop, custom
    link_target = Column(String(255), nullable=True)
    link_url = Column(String(500), nullable=True)
    cta_label = Column(String(100), default="Explore Now", nullable=True)
    cta_url = Column(String(500), nullable=True)
    banner_type = Column(String(50), default="hero", nullable=False) # hero, promo, flash_sale
    is_active = Column(Boolean, default=True, nullable=False)
    display_order = Column(Integer, default=0, nullable=False)
    start_at = Column(DateTime, nullable=True)
    end_at = Column(DateTime, nullable=True)

class Cart(BaseModel):
    __tablename__ = "carts"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, unique=True)
    session_id = Column(String(100), nullable=True, index=True) # for guest carts
    status = Column(String(50), default="active", nullable=False, index=True) # active, abandoned, converted
    coupon_code = Column(String(50), nullable=True)
    applied_coupon_id = Column(Integer, ForeignKey("coupons.id", ondelete="SET NULL"), nullable=True)
    
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")
    applied_coupon = relationship("Coupon")

class CartItem(BaseModel):
    __tablename__ = "cart_items"
    
    cart_id = Column(Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    quantity = Column(Integer, default=1, nullable=False)
    
    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")
    variant = relationship("ProductVariant")

class Order(BaseModel):
    __tablename__ = "orders"
    
    order_number = Column(String(50), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    address_id = Column(Integer, ForeignKey("addresses.id", ondelete="SET NULL"), nullable=True)
    
    status = Column(String(50), default="pending", nullable=False, index=True) # pending, confirmed, processing, shipped, delivered, cancelled
    payment_status = Column(String(50), default="pending", nullable=False, index=True) # pending, processing, paid, failed, cancelled, refunded
    payment_method = Column(String(50), default="card", nullable=False) # card, upi, netbanking, cod
    payment_provider = Column(String(50), default="standard", nullable=False) # standard, razorpay, stripe
    currency = Column(String(10), default="INR", nullable=False)
    
    subtotal = Column(Float, nullable=False)
    tax_amount = Column(Float, default=0.0, nullable=False)
    shipping_amount = Column(Float, default=0.0, nullable=False)
    discount_amount = Column(Float, default=0.0, nullable=False)
    coupon_code = Column(String(50), nullable=True)
    coupon_discount = Column(Float, default=0.0, nullable=False)
    offer_discount = Column(Float, default=0.0, nullable=False)
    flash_sale_discount = Column(Float, default=0.0, nullable=False)
    total_amount = Column(Float, nullable=False)
    
    shipping_address_json = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)
    idempotency_key = Column(String(100), unique=True, index=True, nullable=True)
    placed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="orders")
    address = relationship("Address")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    status_history = relationship(
        "OrderStatusHistory", 
        back_populates="order", 
        cascade="all, delete-orphan", 
        order_by="desc(OrderStatusHistory.created_at)"
    )
    payments = relationship(
        "Payment", 
        back_populates="order", 
        cascade="all, delete-orphan", 
        order_by="desc(Payment.created_at)"
    )
    shipments = relationship(
        "Shipment",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="desc(Shipment.created_at)"
    )
    returns = relationship(
        "Return",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="desc(Return.created_at)"
    )
    refunds = relationship(
        "Refund",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="desc(Refund.created_at)"
    )
    replacements = relationship(
        "Replacement",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="desc(Replacement.created_at)"
    )

class OrderItem(BaseModel):
    __tablename__ = "order_items"
    
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True)
    
    product_name = Column(String(255), nullable=False)
    variant_title = Column(String(255), nullable=True)
    sku = Column(String(100), nullable=False)
    unit_price = Column(Float, nullable=False)
    mrp = Column(Float, default=0.0, nullable=False)
    discount_amount = Column(Float, default=0.0, nullable=False)
    offer_discount = Column(Float, default=0.0, nullable=False)
    flash_sale_discount = Column(Float, default=0.0, nullable=False)
    coupon_discount = Column(Float, default=0.0, nullable=False)
    final_price = Column(Float, default=0.0, nullable=False)
    tax_amount = Column(Float, default=0.0, nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    total_price = Column(Float, nullable=False)
    line_total = Column(Float, default=0.0, nullable=False)
    image_url = Column(String(500), nullable=True)
    
    order = relationship("Order", back_populates="items")
    product = relationship("Product")
    variant = relationship("ProductVariant")

class OrderStatusHistory(BaseModel):
    __tablename__ = "order_status_history"
    
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    changed_by = Column(String(100), default="system", nullable=False)
    reason = Column(Text, nullable=True)
    
    order = relationship("Order", back_populates="status_history")

class Payment(BaseModel):
    __tablename__ = "payments"
    
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), default="standard", nullable=False)
    method = Column(String(50), nullable=False) # card, upi, netbanking, cod
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR", nullable=False)
    status = Column(String(50), default="pending", nullable=False, index=True) # pending, processing, paid, failed, cancelled, refunded
    provider_payment_id = Column(String(150), unique=True, index=True, nullable=True)
    idempotency_key = Column(String(100), unique=True, index=True, nullable=True)
    
    order = relationship("Order", back_populates="payments")
    user = relationship("User")
    transactions = relationship(
        "PaymentTransaction", 
        back_populates="payment", 
        cascade="all, delete-orphan", 
        order_by="desc(PaymentTransaction.created_at)"
    )

class PaymentTransaction(BaseModel):
    __tablename__ = "payment_transactions"
    
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_type = Column(String(50), nullable=False) # payment_intent, charge, authorize, capture, refund
    provider_transaction_id = Column(String(150), unique=True, index=True, nullable=True)
    amount = Column(Float, nullable=False)
    status = Column(String(50), nullable=False) # pending, success, failed
    response_reference = Column(Text, nullable=True)
    
    payment = relationship("Payment", back_populates="transactions")

from app.models.reviews import Review
