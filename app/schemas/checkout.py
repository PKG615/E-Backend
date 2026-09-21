from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from app.schemas.cart import CartItemResponse
from app.schemas.address import AddressResponse

class CheckoutPreviewRequest(BaseModel):
    address_id: int

class CheckoutPreviewResponse(BaseModel):
    valid: bool
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
    address: Optional[AddressResponse] = None
    warnings: List[str] = []
    errors: List[str] = []
