from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class PaymentInitiateRequest(BaseModel):
    order_id: int
    method: str = Field(..., description="card, upi, netbanking, cod")
    provider: str = Field(default="standard", description="standard, razorpay, stripe")
    idempotency_key: Optional[str] = None

class PaymentConfirmRequest(BaseModel):
    order_id: int
    payment_id: Optional[int] = None
    provider_payment_id: Optional[str] = None
    status: str = Field(default="paid", description="paid, failed")
    reason: Optional[str] = None

class PaymentTransactionResponse(BaseModel):
    id: int
    payment_id: int
    transaction_type: str
    provider_transaction_id: Optional[str] = None
    amount: float
    status: str
    response_reference: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PaymentResponse(BaseModel):
    id: int
    order_id: int
    user_id: int
    order_number: Optional[str] = None
    amount: float
    currency: str
    provider: str
    method: str
    status: str
    provider_payment_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    transactions: List[PaymentTransactionResponse] = []

    class Config:
        from_attributes = True
