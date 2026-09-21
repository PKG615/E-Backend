from sqlalchemy import Column, Integer, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class WishlistItem(BaseModel):
    __tablename__ = "wishlist_items"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    user = relationship("User", back_populates="wishlist_items")
    product = relationship("Product")
    variant = relationship("ProductVariant")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_user_product_wishlist"),
    )

class CompareItem(BaseModel):
    __tablename__ = "compare_items"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    session_id = Column(String(100), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="compare_items")
    product = relationship("Product")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_user_product_compare"),
    )
