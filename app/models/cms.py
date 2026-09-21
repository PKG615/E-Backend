from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, Text, JSON, DateTime, asc
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class HomepageSection(BaseModel):
    __tablename__ = "homepage_sections"

    section_key = Column(String(100), unique=True, index=True, nullable=False)
    section_type = Column(String(50), index=True, nullable=False) # HERO_BANNER, CATEGORY_GRID, FEATURED_CATEGORIES, FEATURED_PRODUCTS, NEW_ARRIVALS, BEST_SELLERS, TRENDING_PRODUCTS, BRANDS, COLLECTION, OFFER, PROMOTIONAL_BANNER, TRUST_INFO, NEWSLETTER, FAQ, CUSTOM_CONTENT
    title = Column(String(255), nullable=False)
    subtitle = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    configuration = Column(JSON, default=dict, nullable=True)

    items = relationship(
        "HomepageSectionItem",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="asc(HomepageSectionItem.sort_order), asc(HomepageSectionItem.id)"
    )

class HomepageSectionItem(BaseModel):
    __tablename__ = "homepage_section_items"

    section_id = Column(Integer, ForeignKey("homepage_sections.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type = Column(String(50), nullable=False) # product, category, brand, banner, faq, trust_item, custom
    item_id = Column(Integer, nullable=True, index=True) # referenced product_id, category_id, brand_id, banner_id
    custom_title = Column(String(255), nullable=True)
    custom_content = Column(Text, nullable=True)
    custom_icon = Column(String(100), nullable=True)
    custom_url = Column(String(500), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    section = relationship("HomepageSection", back_populates="items")

class Collection(BaseModel):
    __tablename__ = "collections"

    title = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    seo_title = Column(String(255), nullable=True)
    seo_description = Column(Text, nullable=True)

    products = relationship(
        "CollectionProduct",
        back_populates="collection",
        cascade="all, delete-orphan",
        order_by="asc(CollectionProduct.sort_order), asc(CollectionProduct.id)"
    )

class CollectionProduct(BaseModel):
    __tablename__ = "collection_products"

    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order = Column(Integer, default=0, nullable=False)

    collection = relationship("Collection", back_populates="products")
    product = relationship("Product")

class NewsletterSubscription(BaseModel):
    __tablename__ = "newsletter_subscriptions"

    email = Column(String(255), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
