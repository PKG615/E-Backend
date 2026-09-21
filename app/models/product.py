from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, Float, Text, JSON, UniqueConstraint, asc
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class ProductAttribute(BaseModel):
    __tablename__ = "product_attributes"

    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)

    values = relationship("ProductAttributeValue", back_populates="attribute", cascade="all, delete-orphan", order_by="asc(ProductAttributeValue.id)")

class ProductAttributeValue(BaseModel):
    __tablename__ = "product_attribute_values"

    attribute_id = Column(Integer, ForeignKey("product_attributes.id", ondelete="CASCADE"), nullable=False, index=True)
    value = Column(String(100), nullable=False)
    slug = Column(String(100), index=True, nullable=False)

    attribute = relationship("ProductAttribute", back_populates="values")
    variant_links = relationship("VariantAttributeValue", back_populates="attribute_value", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("attribute_id", "slug", name="uq_attribute_value_slug"),
    )

class VariantAttributeValue(BaseModel):
    __tablename__ = "variant_attribute_values"

    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False, index=True)
    attribute_value_id = Column(Integer, ForeignKey("product_attribute_values.id", ondelete="RESTRICT"), nullable=False, index=True)

    variant = relationship("ProductVariant", back_populates="attribute_value_links")
    attribute_value = relationship("ProductAttributeValue", back_populates="variant_links")

    __table_args__ = (
        UniqueConstraint("variant_id", "attribute_value_id", name="uq_variant_attribute_value"),
    )

class Product(BaseModel):
    __tablename__ = "products"
    
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    sku = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=False)
    short_description = Column(String(500), nullable=True)
    
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True)
    
    price = Column(Float, nullable=False) # Selling price
    mrp = Column(Float, nullable=False)   # Maximum Retail Price
    discount_percent = Column(Float, default=0.0, nullable=False)
    tax_percent = Column(Float, default=18.0, nullable=False)
    stock = Column(Integer, default=0, nullable=False)
    
    status = Column(String(50), default="active", nullable=False, index=True) # draft, active, inactive
    is_active = Column(Boolean, default=True, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False, index=True)
    is_new_arrival = Column(Boolean, default=False, nullable=False, index=True)
    is_best_seller = Column(Boolean, default=False, nullable=False)
    is_flash_sale = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False, index=True)
    
    weight = Column(Float, nullable=True)
    length = Column(Float, nullable=True)
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    
    video_url = Column(String(500), nullable=True)
    warranty = Column(String(255), nullable=True)
    warranty_info = Column(String(255), nullable=True)
    return_policy = Column(String(255), default="7-day return policy", nullable=True)
    specifications = Column(JSON, default=dict, nullable=True) # key-value pairs
    attributes = Column(JSON, default=dict, nullable=True)     # e.g. {"sizes": ["S", "M", "L"], "colors": ["Red", "Black"]}
    
    seo_title = Column(String(255), nullable=True)
    seo_description = Column(Text, nullable=True)
    meta_title = Column(String(255), nullable=True)
    meta_description = Column(Text, nullable=True)
    
    # Relationships
    category = relationship("Category", back_populates="products")
    brand = relationship("Brand", back_populates="products")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan", order_by="asc(ProductImage.sort_order), asc(ProductImage.id)")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan", order_by="asc(ProductVariant.sort_order), asc(ProductVariant.id)")
    reviews = relationship("Review", back_populates="product", cascade="all, delete-orphan")
    questions = relationship("ProductQuestion", back_populates="product", cascade="all, delete-orphan")
    inventory_records = relationship("Inventory", back_populates="product", cascade="all, delete-orphan")

class ProductImage(BaseModel):
    __tablename__ = "product_images"
    
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    image_url = Column(String(500), nullable=False)
    alt_text = Column(String(255), nullable=True)
    is_primary = Column(Boolean, default=False, nullable=False, index=True)
    sort_order = Column(Integer, default=0, nullable=False, index=True)
    display_order = Column(Integer, default=0, nullable=False)
    
    product = relationship("Product", back_populates="images")

class ProductVariant(BaseModel):
    __tablename__ = "product_variants"
    
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False) # e.g. "Space Black / 256GB"
    price = Column(Float, nullable=False)
    mrp = Column(Float, nullable=False)
    stock = Column(Integer, default=0, nullable=False)
    attributes = Column(JSON, default=dict, nullable=False) # e.g. {"color": "Space Black", "storage": "256GB"}
    image_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    sort_order = Column(Integer, default=0, nullable=False, index=True)
    
    product = relationship("Product", back_populates="variants")
    attribute_value_links = relationship("VariantAttributeValue", back_populates="variant", cascade="all, delete-orphan")
    inventory_record = relationship("Inventory", back_populates="variant", uselist=False, cascade="all, delete-orphan")

    @property
    def name(self) -> str:
        return self.title

    @name.setter
    def name(self, value: str):
        self.title = value

    @property
    def stock_quantity(self) -> int:
        return self.stock

    @stock_quantity.setter
    def stock_quantity(self, value: int):
        self.stock = value

