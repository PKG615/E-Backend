from datetime import datetime
from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, Float, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Coupon(BaseModel):
    __tablename__ = "coupons"

    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    discount_type = Column(String(50), nullable=False) # 'percentage', 'fixed_amount'
    discount_value = Column(Float, nullable=False)
    max_discount_amount = Column(Float, nullable=True)
    minimum_cart_value = Column(Float, default=0.0, nullable=False)
    maximum_cart_value = Column(Float, nullable=True)
    usage_limit = Column(Integer, nullable=True)
    per_customer_limit = Column(Integer, default=1, nullable=False)
    used_count = Column(Integer, default=0, nullable=False)
    starts_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    applicable_products = relationship("CouponProduct", back_populates="coupon", cascade="all, delete-orphan")
    applicable_categories = relationship("CouponCategory", back_populates="coupon", cascade="all, delete-orphan")
    applicable_brands = relationship("CouponBrand", back_populates="coupon", cascade="all, delete-orphan")
    exclusions = relationship("CouponExclusion", back_populates="coupon", cascade="all, delete-orphan")
    usages = relationship("CouponUsage", back_populates="coupon", cascade="all, delete-orphan")

class CouponProduct(BaseModel):
    __tablename__ = "coupon_products"

    coupon_id = Column(Integer, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)

    coupon = relationship("Coupon", back_populates="applicable_products")
    product = relationship("Product")

    __table_args__ = (
        UniqueConstraint("coupon_id", "product_id", name="uq_coupon_product"),
    )

class CouponCategory(BaseModel):
    __tablename__ = "coupon_categories"

    coupon_id = Column(Integer, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True)

    coupon = relationship("Coupon", back_populates="applicable_categories")
    category = relationship("Category")

    __table_args__ = (
        UniqueConstraint("coupon_id", "category_id", name="uq_coupon_category"),
    )

class CouponBrand(BaseModel):
    __tablename__ = "coupon_brands"

    coupon_id = Column(Integer, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)

    coupon = relationship("Coupon", back_populates="applicable_brands")
    brand = relationship("Brand")

    __table_args__ = (
        UniqueConstraint("coupon_id", "brand_id", name="uq_coupon_brand"),
    )

class CouponExclusion(BaseModel):
    __tablename__ = "coupon_exclusions"

    coupon_id = Column(Integer, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True)
    exclusion_type = Column(String(50), nullable=False) # 'product', 'category', 'brand'
    target_id = Column(Integer, nullable=False)

    coupon = relationship("Coupon", back_populates="exclusions")

class CouponUsage(BaseModel):
    __tablename__ = "coupon_usages"

    coupon_id = Column(Integer, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    discount_amount = Column(Float, default=0.0, nullable=False)
    status = Column(String(50), default="consumed", nullable=False, index=True) # 'reserved', 'consumed', 'cancelled'
    used_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    coupon = relationship("Coupon", back_populates="usages")
    user = relationship("User")
    order = relationship("Order")

class Offer(BaseModel):
    __tablename__ = "offers"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    offer_type = Column(String(50), nullable=False) # 'product_discount', 'category_discount', 'brand_discount', 'cart_discount'
    discount_type = Column(String(50), nullable=False) # 'percentage', 'fixed_amount'
    discount_value = Column(Float, nullable=False)
    max_discount_amount = Column(Float, nullable=True)
    minimum_cart_value = Column(Float, nullable=True)
    starts_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    priority = Column(Integer, default=0, nullable=False, index=True)
    stackable = Column(Boolean, default=False, nullable=False)

    applicable_products = relationship("OfferProduct", back_populates="offer", cascade="all, delete-orphan")
    applicable_categories = relationship("OfferCategory", back_populates="offer", cascade="all, delete-orphan")
    applicable_brands = relationship("OfferBrand", back_populates="offer", cascade="all, delete-orphan")

class OfferProduct(BaseModel):
    __tablename__ = "offer_products"

    offer_id = Column(Integer, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)

    offer = relationship("Offer", back_populates="applicable_products")
    product = relationship("Product")

    __table_args__ = (
        UniqueConstraint("offer_id", "product_id", name="uq_offer_product"),
    )

class OfferCategory(BaseModel):
    __tablename__ = "offer_categories"

    offer_id = Column(Integer, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True)

    offer = relationship("Offer", back_populates="applicable_categories")
    category = relationship("Category")

    __table_args__ = (
        UniqueConstraint("offer_id", "category_id", name="uq_offer_category"),
    )

class OfferBrand(BaseModel):
    __tablename__ = "offer_brands"

    offer_id = Column(Integer, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)

    offer = relationship("Offer", back_populates="applicable_brands")
    brand = relationship("Brand")

    __table_args__ = (
        UniqueConstraint("offer_id", "brand_id", name="uq_offer_brand"),
    )

class FlashSale(BaseModel):
    __tablename__ = "flash_sales"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    banner_image = Column(String(500), nullable=True)
    starts_at = Column(DateTime, nullable=False, index=True)
    ends_at = Column(DateTime, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    priority = Column(Integer, default=0, nullable=False)

    items = relationship("FlashSaleItem", back_populates="flash_sale", cascade="all, delete-orphan")

class FlashSaleItem(BaseModel):
    __tablename__ = "flash_sale_items"

    flash_sale_id = Column(Integer, ForeignKey("flash_sales.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True)
    sale_price = Column(Float, nullable=False)
    quantity_limit = Column(Integer, nullable=True)
    sold_quantity = Column(Integer, default=0, nullable=False)

    flash_sale = relationship("FlashSale", back_populates="items")
    product = relationship("Product")
    variant = relationship("ProductVariant")
