from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=72, description="Password must be between 6 and 72 characters")
    full_name: str = Field(..., min_length=2, max_length=100, description="Full name must be between 2 and 100 characters")
    phone: Optional[str] = Field(None, max_length=20)

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=72)

class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10)

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserResponse"

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True

TokenResponse.update_forward_refs()

class AdminCustomerListItem(BaseModel):
    id: int
    email: str
    full_name: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    order_count: int = 0
    total_spent: float = 0.0
    last_order_date: Optional[str] = None

    class Config:
        from_attributes = True

class AdminCustomerStatusUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    role: Optional[str] = None

class AdminCustomerDetail(BaseModel):
    id: int
    email: str
    full_name: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    order_count: int = 0
    total_spent: float = 0.0
    addresses: list = []
    recent_orders: list = []
    wishlist_count: int = 0
    reviews_count: int = 0
    returns_count: int = 0
    support_tickets: list = []
