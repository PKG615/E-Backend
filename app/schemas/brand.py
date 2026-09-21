from typing import Optional
from datetime import datetime
import re
from pydantic import BaseModel, Field, field_validator

def clean_slug(val: str) -> str:
    cleaned = val.strip().lower()
    cleaned = re.sub(r'[^a-z0-9\-]+', '-', cleaned)
    cleaned = re.sub(r'-+', '-', cleaned).strip('-')
    return cleaned

class BrandBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Brand name")
    slug: Optional[str] = Field(None, max_length=255, description="URL-friendly brand slug")
    description: Optional[str] = Field(None, description="Detailed brand overview or history")
    logo_url: Optional[str] = Field(None, max_length=500, description="Brand logo image URL")
    website_url: Optional[str] = Field(None, max_length=500, description="Official brand website URL")
    sort_order: int = Field(0, ge=0, description="Display priority weight (lower numbers first)")
    is_active: bool = Field(True, description="Whether brand is active and publicly visible")
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
                raise ValueError("Brand name must be at least 2 characters long")
        return v

class BrandCreate(BrandBase):
    pass

class BrandUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    slug: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    sort_order: Optional[int] = Field(None, ge=0)
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
                raise ValueError("Brand name must be at least 2 characters long")
        return v

class BrandResponse(BrandBase):
    id: int
    created_at: datetime
    updated_at: datetime
    products_count: int = 0

    class Config:
        from_attributes = True
