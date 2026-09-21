from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class AddressBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., min_length=5, max_length=20)
    address_line1: str = Field(..., min_length=2, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    landmark: Optional[str] = Field(None, max_length=255)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    postal_code: str = Field(..., min_length=3, max_length=20)
    country: str = Field("India", max_length=100)
    address_type: str = Field("home", pattern="^(home|work|other)$")
    is_default: bool = False

class AddressCreate(AddressBase):
    pass

class AddressUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = Field(None, min_length=5, max_length=20)
    address_line1: Optional[str] = Field(None, min_length=2, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    landmark: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    state: Optional[str] = Field(None, min_length=2, max_length=100)
    postal_code: Optional[str] = Field(None, min_length=3, max_length=20)
    country: Optional[str] = Field(None, max_length=100)
    address_type: Optional[str] = Field(None, pattern="^(home|work|other)$")
    is_default: Optional[bool] = None

class AddressResponse(AddressBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
