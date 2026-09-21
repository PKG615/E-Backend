import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator

class ProductImageSchema(BaseModel):
    id: Optional[int] = None
    product_id: Optional[int] = None
    image_url: str
    alt_text: Optional[str] = None
    is_primary: bool = False
    sort_order: int = 0
    display_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ProductImageCreate(BaseModel):
    image_url: str = Field(..., min_length=1, max_length=500, description="Image URL or relative path")
    alt_text: Optional[str] = Field(None, max_length=255, description="Descriptive alt text for accessibility and SEO")
    is_primary: bool = False
    sort_order: int = Field(0, ge=0, description="Non-negative sort order")
    display_order: Optional[int] = None

    @validator('image_url')
    def validate_image_url(cls, v):
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Image URL cannot be empty")
        if not (cleaned.startswith('http://') or cleaned.startswith('https://') or cleaned.startswith('/uploads/') or cleaned.startswith('/static/')):
            raise ValueError("Image URL must be a valid HTTP/HTTPS URL or /uploads/ path")
        return cleaned

    @validator('alt_text')
    def validate_alt_text(cls, v):
        if v is not None:
            cleaned = v.strip()
            return cleaned if cleaned else None
        return None

    @validator('sort_order')
    def validate_sort_order(cls, v):
        if v < 0:
            raise ValueError("Sort order must be non-negative")
        return v

class ProductImageUpdate(BaseModel):
    image_url: Optional[str] = Field(None, min_length=1, max_length=500)
    alt_text: Optional[str] = Field(None, max_length=255)
    is_primary: Optional[bool] = None
    sort_order: Optional[int] = Field(None, ge=0)
    display_order: Optional[int] = None

    @validator('image_url')
    def validate_image_url(cls, v):
        if v is not None:
            cleaned = v.strip()
            if not cleaned:
                raise ValueError("Image URL cannot be empty")
            if not (cleaned.startswith('http://') or cleaned.startswith('https://') or cleaned.startswith('/uploads/') or cleaned.startswith('/static/')):
                raise ValueError("Image URL must be a valid HTTP/HTTPS URL or /uploads/ path")
            return cleaned
        return v

    @validator('alt_text')
    def validate_alt_text(cls, v):
        if v is not None:
            cleaned = v.strip()
            return cleaned if cleaned else None
        return None

    @validator('sort_order')
    def validate_sort_order(cls, v):
        if v is not None and v < 0:
            raise ValueError("Sort order must be non-negative")
        return v

class ProductImageReorderItem(BaseModel):
    id: int
    sort_order: int = Field(..., ge=0)

class ProductImageReorderRequest(BaseModel):
    image_ids: Optional[List[int]] = None
    items: Optional[List[ProductImageReorderItem]] = None

# ==========================================
# ATTRIBUTE SCHEMAS
# ==========================================

class AttributeValueCreate(BaseModel):
    value: str = Field(..., min_length=1, max_length=100, description="Attribute value, e.g. 'Red', '128GB'")

    @validator('value')
    def validate_value(cls, v):
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Attribute value cannot be empty")
        return cleaned

class AttributeValueSchema(BaseModel):
    id: int
    attribute_id: int
    value: str
    slug: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AttributeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Attribute name, e.g. 'Color', 'Storage'")

    @validator('name')
    def validate_name(cls, v):
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Attribute name cannot be empty")
        return cleaned

class AttributeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)

    @validator('name')
    def validate_name(cls, v):
        if v is not None:
            cleaned = v.strip()
            if not cleaned:
                raise ValueError("Attribute name cannot be empty")
            return cleaned
        return v

class AttributeSchema(BaseModel):
    id: int
    name: str
    slug: str
    values: List[AttributeValueSchema] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# ==========================================
# PRODUCT VARIANT SCHEMAS
# ==========================================

class VariantAttributeDetail(BaseModel):
    attribute_id: int
    attribute_name: str
    attribute_slug: str
    value_id: int
    value: str
    value_slug: str

class ProductVariantSchema(BaseModel):
    id: Optional[int] = None
    product_id: Optional[int] = None
    sku: str
    title: str
    name: Optional[str] = None
    price: float
    selling_price: Optional[float] = None
    mrp: float
    stock: int = 0
    stock_quantity: Optional[int] = None
    in_stock: bool = True
    attributes: Dict[str, Any] = {}
    attribute_values: List[VariantAttributeDetail] = []
    image_url: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ProductVariantCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=100, description="Unique variant SKU")
    title: Optional[str] = Field(None, max_length=255, description="Variant name/title e.g. 'Red / Medium'")
    name: Optional[str] = Field(None, max_length=255)
    price: float = Field(..., gt=0, description="Selling price, must be > 0")
    mrp: float = Field(..., gt=0, description="Maximum retail price, must be >= price")
    stock: int = Field(0, ge=0, description="Available stock quantity, must be >= 0")
    stock_quantity: Optional[int] = None
    is_active: bool = True
    sort_order: int = Field(0, ge=0)
    attribute_value_ids: Optional[List[int]] = Field(default=[], description="List of attribute value IDs")
    attributes: Optional[Dict[str, str]] = Field(default={}, description="Key-value attribute pairs")
    image_url: Optional[str] = Field(None, max_length=500)

    @validator('sku')
    def validate_sku(cls, v):
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("Variant SKU cannot be empty")
        return cleaned

    @validator('price')
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError("Variant selling price must be greater than 0")
        return round(float(v), 2)

    @validator('mrp')
    def validate_mrp(cls, v, values):
        if v <= 0:
            raise ValueError("Variant MRP must be greater than 0")
        price = values.get('price')
        if price is not None and v < price:
            raise ValueError("Variant MRP must be greater than or equal to selling price")
        return round(float(v), 2)

    @validator('stock')
    def validate_stock(cls, v):
        if v < 0:
            raise ValueError("Variant stock quantity cannot be negative")
        return int(v)

    @validator('sort_order')
    def validate_sort_order(cls, v):
        if v < 0:
            raise ValueError("Variant sort order must be non-negative")
        return v

class ProductVariantUpdate(BaseModel):
    sku: Optional[str] = Field(None, min_length=1, max_length=100)
    title: Optional[str] = Field(None, max_length=255)
    name: Optional[str] = Field(None, max_length=255)
    price: Optional[float] = Field(None, gt=0)
    mrp: Optional[float] = Field(None, gt=0)
    stock: Optional[int] = Field(None, ge=0)
    stock_quantity: Optional[int] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = Field(None, ge=0)
    attribute_value_ids: Optional[List[int]] = None
    attributes: Optional[Dict[str, str]] = None
    image_url: Optional[str] = None

    @validator('sku')
    def validate_sku(cls, v):
        if v is not None:
            cleaned = v.strip().upper()
            if not cleaned:
                raise ValueError("Variant SKU cannot be empty")
            return cleaned
        return v

    @validator('price')
    def validate_price(cls, v):
        if v is not None:
            if v <= 0:
                raise ValueError("Variant selling price must be greater than 0")
            return round(float(v), 2)
        return v

    @validator('mrp')
    def validate_mrp(cls, v):
        if v is not None:
            if v <= 0:
                raise ValueError("Variant MRP must be greater than 0")
            return round(float(v), 2)
        return v

    @validator('stock')
    def validate_stock(cls, v):
        if v is not None:
            if v < 0:
                raise ValueError("Variant stock quantity cannot be negative")
            return int(v)
        return v

    @validator('sort_order')
    def validate_sort_order(cls, v):
        if v is not None and v < 0:
            raise ValueError("Variant sort order must be non-negative")
        return v

class ProductVariantReorderRequest(BaseModel):
    variant_ids: List[int] = Field(..., min_items=1, description="Ordered list of variant IDs")

class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = Field(None, max_length=255)
    sku: Optional[str] = Field(None, max_length=100)
    description: str
    short_description: Optional[str] = Field(None, max_length=500)
    
    category_id: int
    brand_id: Optional[int] = None
    
    price: float = Field(..., description="Selling price")
    mrp: float = Field(..., description="Maximum retail price")
    discount_percent: float = 0.0
    tax_percent: float = 18.0
    stock: int = 0
    
    status: str = "active" # 'draft' | 'active' | 'inactive'
    is_active: bool = True
    is_featured: bool = False
    is_new_arrival: bool = False
    is_best_seller: bool = False
    is_flash_sale: bool = False
    sort_order: int = 0
    
    weight: Optional[float] = None
    length: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    
    video_url: Optional[str] = None
    warranty: Optional[str] = None
    warranty_info: Optional[str] = None
    return_policy: Optional[str] = "7-day return policy"
    specifications: Dict[str, Any] = {}
    attributes: Dict[str, Any] = {}
    
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

    @validator('price')
    def validate_price(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Selling price must be greater than 0')
        return round(float(v), 2)

    @validator('mrp')
    def validate_mrp(cls, v, values):
        if v is not None and v <= 0:
            raise ValueError('MRP must be greater than 0')
        price = values.get('price')
        if price is not None and v < price:
            raise ValueError('MRP must be greater than or equal to selling price')
        return round(float(v), 2)

    @validator('tax_percent')
    def validate_tax(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Tax percentage must be between 0 and 100')
        return round(float(v), 2)

    @validator('stock')
    def validate_stock(cls, v):
        if v is not None and v < 0:
            raise ValueError('Stock quantity cannot be negative')
        return int(v)

    @validator('status')
    def validate_status(cls, v):
        normalized = (v or 'active').strip().lower()
        if normalized not in ('draft', 'active', 'inactive'):
            raise ValueError("Status must be one of: 'draft', 'active', 'inactive'")
        return normalized

    @validator('sku')
    def validate_sku(cls, v):
        if v:
            return v.strip().upper()
        return v

    @validator('slug')
    def validate_slug(cls, v):
        if v:
            cleaned = re.sub(r'[^a-zA-Z0-9-_]', '-', v.strip().lower())
            return re.sub(r'-+', '-', cleaned).strip('-')
        return v

    @validator('weight', 'length', 'width', 'height')
    def validate_dimensions(cls, v):
        if v is not None and v < 0:
            raise ValueError('Physical dimensions and weight must be non-negative')
        return v

class ProductCreate(ProductBase):
    images: List[ProductImageSchema] = []
    variants: List[ProductVariantSchema] = []

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    price: Optional[float] = None
    mrp: Optional[float] = None
    discount_percent: Optional[float] = None
    tax_percent: Optional[float] = None
    stock: Optional[int] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    is_new_arrival: Optional[bool] = None
    is_best_seller: Optional[bool] = None
    is_flash_sale: Optional[bool] = None
    sort_order: Optional[int] = None
    weight: Optional[float] = None
    length: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    video_url: Optional[str] = None
    warranty: Optional[str] = None
    warranty_info: Optional[str] = None
    return_policy: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

    @validator('price')
    def validate_price(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Selling price must be greater than 0')
        return round(float(v), 2) if v is not None else None

    @validator('mrp')
    def validate_mrp(cls, v):
        if v is not None and v <= 0:
            raise ValueError('MRP must be greater than 0')
        return round(float(v), 2) if v is not None else None

    @validator('tax_percent')
    def validate_tax(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Tax percentage must be between 0 and 100')
        return round(float(v), 2) if v is not None else None

    @validator('stock')
    def validate_stock(cls, v):
        if v is not None and v < 0:
            raise ValueError('Stock quantity cannot be negative')
        return int(v) if v is not None else None

    @validator('status')
    def validate_status(cls, v):
        if v is not None:
            normalized = v.strip().lower()
            if normalized not in ('draft', 'active', 'inactive'):
                raise ValueError("Status must be one of: 'draft', 'active', 'inactive'")
            return normalized
        return v

    @validator('sku')
    def validate_sku(cls, v):
        if v:
            return v.strip().upper()
        return v

    @validator('slug')
    def validate_slug(cls, v):
        if v:
            cleaned = re.sub(r'[^a-zA-Z0-9-_]', '-', v.strip().lower())
            return re.sub(r'-+', '-', cleaned).strip('-')
        return v

    @validator('weight', 'length', 'width', 'height')
    def validate_dimensions(cls, v):
        if v is not None and v < 0:
            raise ValueError('Physical dimensions and weight must be non-negative')
        return v

class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    # Authoritative calculated & convenience aliases
    selling_price: float
    discount_percentage: float
    tax_percentage: float
    stock_quantity: int
    in_stock: bool
    
    images: List[ProductImageSchema] = []
    variants: List[ProductVariantSchema] = []
    available_attributes: Dict[str, List[str]] = {}
    category_name: Optional[str] = None
    brand_name: Optional[str] = None
    average_rating: float = 4.5
    total_reviews: int = 0

    class Config:
        from_attributes = True


# ==========================================
# SEARCH SUGGESTION & FACET SCHEMAS
# ==========================================

class ProductSuggestionItem(BaseModel):
    id: int
    name: str
    slug: str
    price: float
    mrp: float
    image_url: Optional[str] = None
    category_name: Optional[str] = None
    brand_name: Optional[str] = None
    discount_percent: float = 0.0

class CategorySuggestionItem(BaseModel):
    id: int
    name: str
    slug: str
    product_count: int = 0

class BrandSuggestionItem(BaseModel):
    id: int
    name: str
    slug: str
    product_count: int = 0

class SearchSuggestionsResponse(BaseModel):
    products: List[ProductSuggestionItem] = []
    categories: List[CategorySuggestionItem] = []
    brands: List[BrandSuggestionItem] = []

class FacetCategoryItem(BaseModel):
    id: int
    name: str
    slug: str
    count: int

class FacetBrandItem(BaseModel):
    id: int
    name: str
    slug: str
    count: int

class FacetAttributeValue(BaseModel):
    value: str
    slug: str
    count: int

class FacetAttribute(BaseModel):
    name: str
    slug: str
    values: List[FacetAttributeValue] = []

class CatalogFacets(BaseModel):
    categories: List[FacetCategoryItem] = []
    brands: List[FacetBrandItem] = []
    price_range: Dict[str, float] = {"min": 0.0, "max": 0.0}
    availability: Dict[str, int] = {"in_stock": 0, "out_of_stock": 0}
    attributes: List[FacetAttribute] = []
