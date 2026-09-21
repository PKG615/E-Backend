from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, Float, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel

class Return(BaseModel):
    __tablename__ = "returns"

    return_number = Column(String(50), unique=True, index=True, nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # State lifecycle:
    # requested -> approved / rejected
    # approved -> pickup_pending -> picked_up -> received -> inspection
    # inspection -> approved_for_refund -> refund_processing -> refunded -> closed
    # OR inspection -> replacement_processing -> replacement_shipped -> replacement_delivered -> closed
    # Can also be cancelled (if pending/approved/pickup_pending)
    status = Column(String(50), default="requested", nullable=False, index=True)
    resolution_type = Column(String(50), default="refund", nullable=False) # refund, replacement
    reason = Column(String(100), nullable=False) # damaged, defective, wrong_item, missing_item, not_as_expected, other
    
    customer_note = Column(Text, nullable=True)
    admin_note = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Inspection foundation
    inspection_condition = Column(String(50), nullable=True) # resellable, damaged, defective, wrong_item_returned
    inspection_note = Column(Text, nullable=True)
    inspected_by = Column(String(100), nullable=True)
    inspected_at = Column(DateTime, nullable=True)
    
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    order = relationship("Order", back_populates="returns")
    user = relationship("User")
    items = relationship("ReturnItem", back_populates="return_order", cascade="all, delete-orphan")
    status_history = relationship(
        "ReturnStatusHistory", 
        back_populates="return_order", 
        cascade="all, delete-orphan", 
        order_by="desc(ReturnStatusHistory.created_at)"
    )
    refund = relationship("Refund", back_populates="return_order", uselist=False, cascade="all, delete-orphan")
    replacement = relationship("Replacement", back_populates="return_order", uselist=False, cascade="all, delete-orphan")


class ReturnItem(BaseModel):
    __tablename__ = "return_items"

    return_id = Column(Integer, ForeignKey("returns.id", ondelete="CASCADE"), nullable=False, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True)
    
    quantity = Column(Integer, default=1, nullable=False)
    reason = Column(String(100), nullable=True)
    condition = Column(String(50), nullable=True) # resellable, damaged, opened, etc.
    resolution = Column(String(50), default="refund", nullable=False) # refund, replacement
    refund_amount = Column(Float, default=0.0, nullable=False)
    
    restocked = Column(Boolean, default=False, nullable=False)
    restocked_at = Column(DateTime, nullable=True)

    # Relationships
    return_order = relationship("Return", back_populates="items")
    order_item = relationship("OrderItem")
    product = relationship("Product")
    variant = relationship("ProductVariant")


class ReturnStatusHistory(BaseModel):
    __tablename__ = "return_status_history"

    return_id = Column(Integer, ForeignKey("returns.id", ondelete="CASCADE"), nullable=False, index=True)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    changed_by = Column(String(100), default="system", nullable=False)
    reason = Column(Text, nullable=True)

    return_order = relationship("Return", back_populates="status_history")


class Refund(BaseModel):
    __tablename__ = "refunds"

    refund_number = Column(String(50), unique=True, index=True, nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    return_id = Column(Integer, ForeignKey("returns.id", ondelete="SET NULL"), nullable=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR", nullable=False)
    status = Column(String(50), default="requested", nullable=False, index=True) # requested, processing, completed, failed, cancelled
    reason = Column(String(255), nullable=True)
    provider = Column(String(50), default="standard", nullable=False)
    provider_refund_id = Column(String(150), unique=True, index=True, nullable=True)
    idempotency_key = Column(String(100), unique=True, index=True, nullable=True)
    
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    # Relationships
    order = relationship("Order", back_populates="refunds")
    return_order = relationship("Return", back_populates="refund")
    payment = relationship("Payment")
    user = relationship("User")
    transactions = relationship(
        "RefundTransaction", 
        back_populates="refund", 
        cascade="all, delete-orphan", 
        order_by="desc(RefundTransaction.created_at)"
    )


class RefundTransaction(BaseModel):
    __tablename__ = "refund_transactions"

    refund_id = Column(Integer, ForeignKey("refunds.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    provider_transaction_id = Column(String(150), unique=True, index=True, nullable=True)
    amount = Column(Float, nullable=False)
    status = Column(String(50), nullable=False) # pending, success, failed
    response_reference = Column(Text, nullable=True)

    refund = relationship("Refund", back_populates="transactions")


class Replacement(BaseModel):
    __tablename__ = "replacements"

    replacement_number = Column(String(50), unique=True, index=True, nullable=False)
    return_id = Column(Integer, ForeignKey("returns.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # State lifecycle: requested, approved, processing, shipped, delivered, cancelled, completed
    status = Column(String(50), default="requested", nullable=False, index=True)
    reason = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    return_order = relationship("Return", back_populates="replacement")
    order = relationship("Order", back_populates="replacements")
    user = relationship("User")
    shipment = relationship("Shipment")
    items = relationship("ReplacementItem", back_populates="replacement", cascade="all, delete-orphan")
    status_history = relationship(
        "ReplacementStatusHistory", 
        back_populates="replacement", 
        cascade="all, delete-orphan", 
        order_by="desc(ReplacementStatusHistory.created_at)"
    )


class ReplacementItem(BaseModel):
    __tablename__ = "replacement_items"

    replacement_id = Column(Integer, ForeignKey("replacements.id", ondelete="CASCADE"), nullable=False, index=True)
    original_order_item_id = Column(Integer, ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True)
    
    quantity = Column(Integer, default=1, nullable=False)
    allocated = Column(Boolean, default=False, nullable=False)

    replacement = relationship("Replacement", back_populates="items")
    original_order_item = relationship("OrderItem")
    product = relationship("Product")
    variant = relationship("ProductVariant")


class ReplacementStatusHistory(BaseModel):
    __tablename__ = "replacement_status_history"

    replacement_id = Column(Integer, ForeignKey("replacements.id", ondelete="CASCADE"), nullable=False, index=True)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    changed_by = Column(String(100), default="system", nullable=False)
    reason = Column(Text, nullable=True)

    replacement = relationship("Replacement", back_populates="status_history")
