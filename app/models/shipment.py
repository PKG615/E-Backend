from sqlalchemy import Column, String, ForeignKey, Integer, Float, Text, DateTime
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Shipment(BaseModel):
    __tablename__ = "shipments"
    
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_number = Column(String(50), unique=True, index=True, nullable=False)
    carrier = Column(String(100), nullable=True) # e.g. BlueDart, Delhivery, FedEx, DTDC, India Post
    shipping_method = Column(String(50), default="standard", nullable=False) # standard, express, priority
    tracking_number = Column(String(100), nullable=True, index=True)
    status = Column(String(50), default="pending", nullable=False, index=True) 
    # Lifecycle: pending, processing, packed, shipped, in_transit, out_for_delivery, delivered, failed, cancelled
    shipping_cost = Column(Float, default=0.0, nullable=False)
    estimated_delivery_date = Column(DateTime, nullable=True)
    shipped_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    
    order = relationship("Order", back_populates="shipments")
    tracking_events = relationship(
        "ShipmentTrackingEvent", 
        back_populates="shipment", 
        cascade="all, delete-orphan", 
        order_by="asc(ShipmentTrackingEvent.event_time)"
    )

class ShipmentTrackingEvent(BaseModel):
    __tablename__ = "shipment_tracking_events"
    
    shipment_id = Column(Integer, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), nullable=False)
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=False)
    event_time = Column(DateTime, nullable=False, index=True)
    source = Column(String(50), default="system", nullable=False) # system, admin, carrier
    provider_event_id = Column(String(150), nullable=True, index=True) # For webhook idempotency
    
    shipment = relationship("Shipment", back_populates="tracking_events")
