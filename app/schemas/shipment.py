from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class ShipmentTrackingEventResponse(BaseModel):
    id: int
    shipment_id: int
    status: str
    location: Optional[str] = None
    description: str
    event_time: datetime
    source: str = "system"
    created_at: datetime

    class Config:
        from_attributes = True

class ShipmentResponse(BaseModel):
    id: int
    order_id: int
    shipment_number: str
    carrier: Optional[str] = None
    shipping_method: str
    tracking_number: Optional[str] = None
    status: str
    shipping_cost: float
    estimated_delivery_date: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    tracking_events: List[ShipmentTrackingEventResponse] = []
    
    # Joined metadata for convenient admin & customer consumption
    order_number: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    items_count: Optional[int] = None

    class Config:
        from_attributes = True

class CustomerTrackingResponse(BaseModel):
    order_id: int
    order_number: str
    order_status: str
    shipping_address: Dict[str, Any]
    shipment: Optional[ShipmentResponse] = None
    tracking_events: List[ShipmentTrackingEventResponse] = []
    estimated_delivery_date: Optional[datetime] = None
    status_message: str
    items: List[Dict[str, Any]] = []

class ShipmentCreateRequest(BaseModel):
    carrier: Optional[str] = None
    shipping_method: str = Field(default="standard", description="standard, express, priority")
    tracking_number: Optional[str] = None
    estimated_delivery_date: Optional[datetime] = None
    notes: Optional[str] = None

class ShipmentUpdateRequest(BaseModel):
    carrier: Optional[str] = None
    shipping_method: Optional[str] = None
    tracking_number: Optional[str] = None
    estimated_delivery_date: Optional[datetime] = None
    notes: Optional[str] = None

class ShipmentStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Target status in lifecycle")
    location: Optional[str] = None
    description: Optional[str] = None

class TrackingEventCreateRequest(BaseModel):
    status: str
    location: Optional[str] = None
    description: str
    source: str = "admin"
    event_time: Optional[datetime] = None
