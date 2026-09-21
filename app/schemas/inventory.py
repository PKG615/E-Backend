from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, validator

class InventoryTransactionSchema(BaseModel):
    id: int
    inventory_id: int
    transaction_type: str
    quantity_change: int
    quantity_before: int
    quantity_after: int
    reason: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    notes: Optional[str] = None
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class InventoryItemSchema(BaseModel):
    id: int
    product_id: int
    variant_id: Optional[int] = None
    sku: str
    on_hand_quantity: int
    reserved_quantity: int
    available_quantity: int
    low_stock_threshold: int
    is_active: bool
    stock_status: str

    # Joined and enriched presentation fields
    product_name: Optional[str] = None
    product_slug: Optional[str] = None
    product_image: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    brand_id: Optional[int] = None
    brand_name: Optional[str] = None
    variant_title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InventorySummarySchema(BaseModel):
    total_items: int
    in_stock_count: int
    low_stock_count: int
    out_of_stock_count: int
    total_on_hand: int
    total_reserved: int


class InventoryCreate(BaseModel):
    product_id: int = Field(..., description="ID of the parent product")
    variant_id: Optional[int] = Field(None, description="Optional ID of the variant")
    sku: str = Field(..., min_length=1, max_length=100, description="SKU identifier")
    on_hand_quantity: int = Field(0, ge=0, description="Initial on-hand quantity, must be >= 0")
    reserved_quantity: int = Field(0, ge=0, description="Reserved quantity, must be >= 0")
    low_stock_threshold: int = Field(5, ge=0, description="Low stock threshold alert value")
    is_active: bool = True

    @validator('sku')
    def validate_sku(cls, v):
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("SKU cannot be empty")
        return cleaned

    @validator('on_hand_quantity')
    def validate_on_hand(cls, v):
        if v < 0:
            raise ValueError("On-hand quantity cannot be negative")
        return v

    @validator('reserved_quantity')
    def validate_reserved(cls, v, values):
        if v < 0:
            raise ValueError("Reserved quantity cannot be negative")
        on_hand = values.get('on_hand_quantity', 0)
        if v > on_hand:
            raise ValueError("Reserved quantity cannot exceed on-hand quantity")
        return v


class InventoryUpdate(BaseModel):
    low_stock_threshold: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

    @validator('low_stock_threshold')
    def validate_threshold(cls, v):
        if v is not None and v < 0:
            raise ValueError("Low stock threshold cannot be negative")
        return v


class InventoryAdjustRequest(BaseModel):
    quantity_change: int = Field(..., description="Quantity delta (positive to receive, negative to reduce)")
    reason: str = Field(..., min_length=2, max_length=255, description="Reason for adjustment")
    reference_type: Optional[str] = Field(None, max_length=50)
    reference_id: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=1000)

    @validator('quantity_change')
    def validate_quantity_change(cls, v):
        if v == 0:
            raise ValueError("Adjustment quantity cannot be 0")
        return v

    @validator('reason')
    def validate_reason(cls, v):
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Adjustment reason is required")
        return cleaned


class InventoryDetailResponse(InventoryItemSchema):
    transactions: List[InventoryTransactionSchema] = []
