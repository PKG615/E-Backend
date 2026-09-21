from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Category(BaseModel):
    __tablename__ = "categories"
    
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    image = Column(String(500), nullable=True)
    image_url = Column(String(500), nullable=True)  # Synced alias for backwards-compatibility
    banner = Column(String(500), nullable=True)
    parent_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    display_order = Column(Integer, default=0, nullable=False)  # Synced alias for backwards-compatibility
    is_active = Column(Boolean, default=True, nullable=False)
    seo_title = Column(String(255), nullable=True)
    seo_description = Column(Text, nullable=True)
    
    # Self-referential hierarchical relationship
    parent = relationship("Category", remote_side="Category.id", back_populates="subcategories")
    subcategories = relationship("Category", back_populates="parent", order_by="Category.sort_order")
    
    # Products relationship
    products = relationship("Product", back_populates="category")

class Brand(BaseModel):
    __tablename__ = "brands"
    
    name = Column(String(255), unique=True, nullable=False)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    logo_url = Column(String(500), nullable=True)
    website_url = Column(String(500), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    seo_title = Column(String(255), nullable=True)
    seo_description = Column(Text, nullable=True)
    
    products = relationship("Product", back_populates="brand")
