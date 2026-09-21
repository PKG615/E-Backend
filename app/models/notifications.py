from datetime import datetime
from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, Text, DateTime
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Notification(BaseModel):
    __tablename__ = "notifications"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False) # 'order', 'shipment', 'delivery', 'return', 'refund', 'review', 'promotion', 'support', 'system'
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    reference_type = Column(String(50), nullable=True) # 'order', 'return', 'review', 'ticket', 'coupon'
    reference_id = Column(String(100), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    read_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="notifications")


class NotificationPreference(BaseModel):
    __tablename__ = "notification_preferences"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    order_updates = Column(Boolean, default=True, nullable=False)
    shipment_updates = Column(Boolean, default=True, nullable=False)
    return_refund_updates = Column(Boolean, default=True, nullable=False)
    promotional_updates = Column(Boolean, default=True, nullable=False)
    email_notifications = Column(Boolean, default=True, nullable=False)
    in_app_notifications = Column(Boolean, default=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="notification_preferences")
