from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

# -----------------
# COUPON SCHEMAS
# -----------------

class CouponExclusionSchema(BaseModel):
    exclusion_type: Literal["product", "category", "brand"]
    target_id: int

class CouponBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=50, description="Unique coupon code")
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    discount_type: Literal["percentage", "fixed_amount"]
    discount_value: float = Field(..., gt=0)
    max_discount_amount: Optional[float] = Field(None, ge=0)
    minimum_cart_value: float = Field(default=0.0, ge=0)
    maximum_cart_value: Optional[float] = Field(None, ge=0)
    usage_limit: Optional[int] = Field(None, ge=1)
    per_customer_limit: int = Field(default=1, ge=1)
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True

class CouponCreate(CouponBase):
    applicable_product_ids: List[int] = []
    applicable_category_ids: List[int] = []
    applicable_brand_ids: List[int] = []
    exclusions: List[CouponExclusionSchema] = []

class CouponUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=2, max_length=50)
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    discount_type: Optional[Literal["percentage", "fixed_amount"]] = None
    discount_value: Optional[float] = Field(None, gt=0)
    max_discount_amount: Optional[float] = Field(None, ge=0)
    minimum_cart_value: Optional[float] = Field(None, ge=0)
    maximum_cart_value: Optional[float] = Field(None, ge=0)
    usage_limit: Optional[int] = Field(None, ge=1)
    per_customer_limit: Optional[int] = Field(None, ge=1)
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    applicable_product_ids: Optional[List[int]] = None
    applicable_category_ids: Optional[List[int]] = None
    applicable_brand_ids: Optional[List[int]] = None
    exclusions: Optional[List[CouponExclusionSchema]] = None

class CouponResponse(CouponBase):
    id: int
    used_count: int
    applicable_product_ids: List[int] = []
    applicable_category_ids: List[int] = []
    applicable_brand_ids: List[int] = []
    exclusions: List[CouponExclusionSchema] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AvailableCouponResponse(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    discount_type: str
    discount_value: float
    max_discount_amount: Optional[float] = None
    minimum_cart_value: float = 0.0
    expires_at: Optional[datetime] = None
    is_eligible: bool = True
    ineligible_reason: Optional[str] = None

    class Config:
        from_attributes = True

class CouponUsageResponse(BaseModel):
    id: int
    coupon_id: int
    coupon_code: str
    user_id: int
    user_email: Optional[str] = None
    order_id: Optional[int] = None
    order_number: Optional[str] = None
    discount_amount: float
    status: str
    used_at: datetime

    class Config:
        from_attributes = True

class ApplyCouponRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)

class CouponValidationResponse(BaseModel):
    valid: bool
    code: str
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    discount_amount: float = 0.0
    message: str
    error_code: Optional[str] = None


# -----------------
# OFFER SCHEMAS
# -----------------

class OfferBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    offer_type: Literal["product_discount", "category_discount", "brand_discount", "cart_discount"]
    discount_type: Literal["percentage", "fixed_amount"]
    discount_value: float = Field(..., gt=0)
    max_discount_amount: Optional[float] = Field(None, ge=0)
    minimum_cart_value: Optional[float] = Field(None, ge=0)
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True
    priority: int = 0
    stackable: bool = False

class OfferCreate(OfferBase):
    applicable_product_ids: List[int] = []
    applicable_category_ids: List[int] = []
    applicable_brand_ids: List[int] = []

class OfferUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    offer_type: Optional[Literal["product_discount", "category_discount", "brand_discount", "cart_discount"]] = None
    discount_type: Optional[Literal["percentage", "fixed_amount"]] = None
    discount_value: Optional[float] = Field(None, gt=0)
    max_discount_amount: Optional[float] = Field(None, ge=0)
    minimum_cart_value: Optional[float] = Field(None, ge=0)
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    stackable: Optional[bool] = None
    applicable_product_ids: Optional[List[int]] = None
    applicable_category_ids: Optional[List[int]] = None
    applicable_brand_ids: Optional[List[int]] = None

class OfferResponse(OfferBase):
    id: int
    applicable_product_ids: List[int] = []
    applicable_category_ids: List[int] = []
    applicable_brand_ids: List[int] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# -----------------
# FLASH SALE SCHEMAS
# -----------------

class FlashSaleItemCreate(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    sale_price: float = Field(..., gt=0)
    quantity_limit: Optional[int] = Field(None, ge=1)

class FlashSaleItemResponse(BaseModel):
    id: int
    flash_sale_id: int
    product_id: int
    product_name: Optional[str] = None
    product_slug: Optional[str] = None
    product_image: Optional[str] = None
    regular_price: float = 0.0
    variant_id: Optional[int] = None
    variant_title: Optional[str] = None
    sale_price: float
    discount_percent: float = 0.0
    quantity_limit: Optional[int] = None
    sold_quantity: int = 0
    available_stock: int = 0
    is_in_stock: bool = True

    class Config:
        from_attributes = True

class FlashSaleBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    banner_image: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    is_active: bool = True
    priority: int = 0

class FlashSaleCreate(FlashSaleBase):
    items: List[FlashSaleItemCreate] = []

class FlashSaleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    banner_image: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    items: Optional[List[FlashSaleItemCreate]] = None

class FlashSaleResponse(FlashSaleBase):
    id: int
    items: List[FlashSaleItemResponse] = []
    is_live: bool = False
    is_upcoming: bool = False
    is_ended: bool = False
    time_remaining_seconds: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
