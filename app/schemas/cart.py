from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class CartItemAdd(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = Field(1, ge=1, le=50)

class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1, le=50)

class CartItemProductInfo(BaseModel):
    id: int
    name: str
    slug: str
    sku: str
    brand_name: Optional[str] = None
    category_name: Optional[str] = None
    is_active: bool
    status: str

    class Config:
        from_attributes = True

class CartItemVariantInfo(BaseModel):
    id: int
    title: str
    sku: str
    attributes: Optional[Dict[str, Any]] = None
    is_active: bool

    class Config:
        from_attributes = True

class CartItemResponse(BaseModel):
    id: int
    cart_id: int
    product_id: int
    product: CartItemProductInfo
    variant_id: Optional[int] = None
    variant: Optional[CartItemVariantInfo] = None
    image: Optional[str] = None
    quantity: int
    unit_price: float
    mrp: float
    discount: float
    line_subtotal: float
    available_quantity: int
    in_stock: bool
    price_changed: bool = False
    offer_discount: float = 0.0
    flash_sale_discount: float = 0.0
    coupon_discount: float = 0.0
    final_price: float = 0.0
    applied_offer_title: Optional[str] = None
    is_flash_sale: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CartResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    status: str = "active"
    item_count: int
    items: List[CartItemResponse]
    subtotal: float
    tax: float
    shipping: float
    discount: float
    coupon_code: Optional[str] = None
    coupon_discount: float = 0.0
    offer_discount: float = 0.0
    flash_sale_discount: float = 0.0
    applied_coupon: Optional[Dict[str, Any]] = None
    total: float

    class Config:
        from_attributes = True
