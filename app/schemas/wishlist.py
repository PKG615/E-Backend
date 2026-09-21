from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.product import ProductResponse

class WishlistAddRequest(BaseModel):
    product_id: int = Field(..., description="ID of the product to add to wishlist")
    variant_id: Optional[int] = Field(None, description="Optional variant ID")

class WishlistItemResponse(BaseModel):
    id: int
    user_id: int
    product_id: int
    variant_id: Optional[int] = None
    created_at: datetime
    product: ProductResponse

    class Config:
        from_attributes = True

class WishlistResponse(BaseModel):
    items: List[WishlistItemResponse]
    total_count: int

class WishlistCheckResponse(BaseModel):
    product_id: int
    in_wishlist: bool

class CompareAddRequest(BaseModel):
    product_id: int = Field(..., description="ID of the product to add to compare")

class CompareItemResponse(BaseModel):
    id: int
    product_id: int
    created_at: datetime
    product: ProductResponse

    class Config:
        from_attributes = True

class CompareResponse(BaseModel):
    items: List[CompareItemResponse]
    total_count: int
