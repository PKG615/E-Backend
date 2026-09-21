from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_id: int
    variant_id: Optional[int] = None
    product_name: str
    variant_title: Optional[str] = None
    sku: str
    unit_price: float
    mrp: float = 0.0
    discount_amount: float = 0.0
    offer_discount: float = 0.0
    flash_sale_discount: float = 0.0
    coupon_discount: float = 0.0
    final_price: float = 0.0
    tax_amount: float = 0.0
    quantity: int
    total_price: float
    line_total: float
    image_url: Optional[str] = None

    class Config:
        from_attributes = True

class OrderStatusHistoryResponse(BaseModel):
    id: int
    order_id: int
    old_status: Optional[str] = None
    new_status: str
    changed_by: str
    reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class OrderPaymentSummary(BaseModel):
    id: int
    provider: str
    method: str
    amount: float
    currency: str
    status: str
    provider_payment_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class OrderCreateRequest(BaseModel):
    address_id: int
    payment_method: str = Field(default="card", description="Payment method: card, upi, netbanking, cod")
    payment_provider: str = Field(default="standard", description="Payment provider: standard, razorpay, stripe")
    notes: Optional[str] = None
    idempotency_key: Optional[str] = None

class OrderResponse(BaseModel):
    id: int
    order_number: str
    user_id: int
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    address_id: Optional[int] = None
    status: str
    payment_status: str
    payment_method: str
    payment_provider: str
    currency: str = "INR"
    subtotal: float
    tax_amount: float
    shipping_amount: float
    discount_amount: float
    coupon_code: Optional[str] = None
    coupon_discount: float = 0.0
    offer_discount: float = 0.0
    flash_sale_discount: float = 0.0
    total_amount: float
    shipping_address: Dict[str, Any]
    notes: Optional[str] = None
    placed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse] = []
    status_history: List[OrderStatusHistoryResponse] = []
    payments: List[OrderPaymentSummary] = []

    class Config:
        from_attributes = True

class OrderListResponse(BaseModel):
    items: List[OrderResponse]
    total: int
    page: int
    page_size: int

class AdminOrderStatusUpdate(BaseModel):
    status: str = Field(..., description="Target status: confirmed, processing, shipped, delivered, cancelled")
    reason: Optional[str] = Field(default=None, description="Reason for status change")
    notes: Optional[str] = None
