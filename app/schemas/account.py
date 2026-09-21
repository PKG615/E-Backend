from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

# Profile Schemas
class UserProfileResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True

class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

# Dashboard Schemas
class AccountDashboardResponse(BaseModel):
    customer_name: str
    email: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    member_since: datetime
    profile_completion_percent: int
    profile_completion_items: List[Dict[str, Any]]
    stats: Dict[str, int]
    recent_orders: List[Dict[str, Any]]
    recent_notifications: List[Dict[str, Any]]
    open_tickets: List[Dict[str, Any]]

# Notification Schemas
class NotificationResponse(BaseModel):
    id: int
    user_id: int
    type: str
    title: str
    message: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationPreferencesResponse(BaseModel):
    order_updates: bool = True
    shipment_updates: bool = True
    return_refund_updates: bool = True
    promotional_updates: bool = True
    email_notifications: bool = True
    in_app_notifications: bool = True

    class Config:
        from_attributes = True

class NotificationPreferencesUpdate(BaseModel):
    order_updates: Optional[bool] = None
    shipment_updates: Optional[bool] = None
    return_refund_updates: Optional[bool] = None
    promotional_updates: Optional[bool] = None
    email_notifications: Optional[bool] = None
    in_app_notifications: Optional[bool] = None

# Support Schemas
class SupportMessageResponse(BaseModel):
    id: int
    ticket_id: int
    sender_user_id: Optional[int] = None
    sender_role: str
    sender_name: str
    message: str
    is_internal: bool = False
    created_at: datetime

    class Config:
        from_attributes = True

class SupportTicketResponse(BaseModel):
    id: int
    ticket_number: str
    user_id: int
    subject: str
    category: str
    priority: str
    status: str
    description: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True

class SupportTicketDetailResponse(BaseModel):
    id: int
    ticket_number: str
    user_id: int
    customer_name: str
    customer_email: str
    subject: str
    category: str
    priority: str
    status: str
    description: str
    created_at: datetime
    updated_at: datetime
    messages: List[SupportMessageResponse] = []

    class Config:
        from_attributes = True

class SupportTicketCreate(BaseModel):
    subject: str = Field(..., min_length=5, max_length=255)
    category: str = Field("general", description="order, delivery, payment, return, product, account, general")
    priority: str = Field("medium", description="low, medium, high, urgent")
    description: str = Field(..., min_length=10)

class SupportMessageCreate(BaseModel):
    message: str = Field(..., min_length=2)

class SupportStatusUpdate(BaseModel):
    status: str = Field(..., description="open, in_progress, waiting_for_customer, resolved, closed")
