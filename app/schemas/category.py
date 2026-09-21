from typing import Optional, List
from datetime import datetime
import re
from pydantic import BaseModel, Field, field_validator

def clean_slug(val: str) -> str:
    cleaned = val.strip().lower()
    cleaned = re.sub(r'[^a-z0-9\-]+', '-', cleaned)
    cleaned = re.sub(r'-+', '-', cleaned).strip('-')
    return cleaned

class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Category name")
    slug: Optional[str] = Field(None, max_length=255, description="URL-friendly identifier")
    description: Optional[str] = Field(None, description="Detailed category overview")
    image: Optional[str] = Field(None, max_length=500, description="Thumbnail / cover image URL")
    image_url: Optional[str] = Field(None, max_length=500, description="Backwards-compatible cover image URL")
    banner: Optional[str] = Field(None, max_length=500, description="Promotional category banner URL")
    parent_id: Optional[int] = Field(None, description="Parent category ID for hierarchical nesting")
    sort_order: int = Field(0, ge=0, description="Sort order display weight (lower numbers first)")
    display_order: Optional[int] = Field(None, ge=0, description="Backwards-compatible display order")
    is_active: bool = Field(True, description="Whether category is publicly visible")
    seo_title: Optional[str] = Field(None, max_length=255, description="SEO Meta Title")
    seo_description: Optional[str] = Field(None, max_length=500, description="SEO Meta Description")

    @field_validator("slug", mode="before")
    @classmethod
    def validate_slug(cls, v):
        if v is not None and isinstance(v, str):
            v_clean = clean_slug(v)
            if not v_clean:
                raise ValueError("Slug must contain valid alphanumeric characters")
            return v_clean
        return v

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if len(v) < 2:
                raise ValueError("Category name must be at least 2 characters long")
        return v

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    slug: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    image: Optional[str] = None
    image_url: Optional[str] = None
    banner: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = Field(None, ge=0)
    display_order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None

    @field_validator("slug", mode="before")
    @classmethod
    def validate_slug(cls, v):
        if v is not None and isinstance(v, str):
            v_clean = clean_slug(v)
            if not v_clean:
                raise ValueError("Slug must contain valid alphanumeric characters")
            return v_clean
        return v

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v):
        if v is not None and isinstance(v, str):
            v = v.strip()
            if len(v) < 2:
                raise ValueError("Category name must be at least 2 characters long")
        return v

class CategorySummary(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    image: Optional[str] = None
    image_url: Optional[str] = None
    banner: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: int = 0
    display_order: int = 0
    is_active: bool
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    products_count: Optional[int] = 0

    class Config:
        from_attributes = True

class CategoryResponse(CategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime
    parent_name: Optional[str] = None
    subcategories: List[CategorySummary] = []
    products_count: int = 0

    class Config:
        from_attributes = True

from app.schemas.brand import (
    BrandBase,
    BrandCreate,
    BrandUpdate,
    BrandResponse
)
