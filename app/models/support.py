from datetime import datetime
from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, Text, DateTime
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class SupportTicket(BaseModel):
    __tablename__ = "support_tickets"

    ticket_number = Column(String(50), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    category = Column(String(100), default="general", nullable=False) # 'order', 'delivery', 'payment', 'return', 'product', 'account', 'general'
    priority = Column(String(50), default="medium", nullable=False) # 'low', 'medium', 'high', 'urgent'
    status = Column(String(50), default="open", nullable=False, index=True) # 'open', 'in_progress', 'waiting_for_customer', 'resolved', 'closed'
    description = Column(Text, nullable=False)

    # Relationships
    user = relationship("User", back_populates="support_tickets")
    messages = relationship("SupportMessage", back_populates="ticket", cascade="all, delete-orphan", order_by="SupportMessage.created_at.asc()")


class SupportMessage(BaseModel):
    __tablename__ = "support_messages"

    ticket_id = Column(Integer, ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sender_role = Column(String(50), default="customer", nullable=False) # 'customer', 'support', 'admin'
    sender_name = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False, nullable=False)

    # Relationships
    ticket = relationship("SupportTicket", back_populates="messages")
    sender = relationship("User")
