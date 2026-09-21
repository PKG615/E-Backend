from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, DateTime, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Inventory(BaseModel):
    __tablename__ = "inventory"

    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=True, index=True)
    sku = Column(String(100), nullable=False, index=True)
    on_hand_quantity = Column(Integer, default=0, nullable=False)
    reserved_quantity = Column(Integer, default=0, nullable=False)
    available_quantity = Column(Integer, default=0, nullable=False)
    low_stock_threshold = Column(Integer, default=5, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    product = relationship("Product", back_populates="inventory_records")
    variant = relationship("ProductVariant", back_populates="inventory_record")
    transactions = relationship(
        "InventoryTransaction", 
        back_populates="inventory", 
        cascade="all, delete-orphan", 
        order_by="desc(InventoryTransaction.created_at), desc(InventoryTransaction.id)"
    )

    @property
    def stock_status(self) -> str:
        """
        Authoritative derived inventory status:
        - OUT_OF_STOCK: available <= 0
        - LOW_STOCK: 0 < available <= low_stock_threshold
        - IN_STOCK: available > low_stock_threshold
        """
        if self.available_quantity <= 0:
            return "OUT_OF_STOCK"
        elif self.available_quantity <= self.low_stock_threshold:
            return "LOW_STOCK"
        else:
            return "IN_STOCK"


class InventoryTransaction(BaseModel):
    __tablename__ = "inventory_transactions"

    inventory_id = Column(Integer, ForeignKey("inventory.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_type = Column(String(50), nullable=False, index=True) # RECEIVE, ADJUSTMENT, RESERVE, RELEASE
    quantity_change = Column(Integer, nullable=False)
    quantity_before = Column(Integer, nullable=False)
    quantity_after = Column(Integer, nullable=False)
    reason = Column(String(255), nullable=False)
    reference_type = Column(String(50), nullable=True)
    reference_id = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String(100), default="system", nullable=False)

    inventory = relationship("Inventory", back_populates="transactions")
