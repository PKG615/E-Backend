from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

# Return Reasons controlled list
RETURN_REASONS = [
    "damaged",
    "defective",
    "wrong_item",
    "missing_item",
    "not_as_expected",
    "other"
]

# Return Status lifecycle:
# requested -> approved / rejected
# approved -> pickup_pending -> picked_up -> received -> inspection
# inspection -> approved_for_refund -> refund_processing -> refunded -> closed
# OR inspection -> replacement_processing -> replacement_shipped -> replacement_delivered -> closed
# cancellation: allowed from requested, approved, pickup_pending -> cancelled
RETURN_TRANSITIONS = {
    "requested": ["approved", "rejected", "cancelled"],
    "approved": ["pickup_pending", "received", "rejected", "cancelled"],
    "pickup_pending": ["picked_up", "cancelled"],
    "picked_up": ["received"],
    "received": ["inspection"],
    "inspection": ["approved_for_refund", "replacement_processing", "rejected"],
    "approved_for_refund": ["refund_processing", "refunded"],
    "refund_processing": ["refunded"],
    "refunded": ["closed"],
    "replacement_processing": ["replacement_shipped", "cancelled"],
    "replacement_shipped": ["replacement_delivered"],
    "replacement_delivered": ["closed"],
    "rejected": [],
    "cancelled": [],
    "closed": []
}

# Replacement Status lifecycle:
REPLACEMENT_TRANSITIONS = {
    "requested": ["approved", "cancelled"],
    "approved": ["processing", "cancelled"],
    "processing": ["shipped", "cancelled"],
    "shipped": ["delivered"],
    "delivered": ["completed"],
    "cancelled": [],
    "completed": []
}

# Refund Status lifecycle:
REFUND_TRANSITIONS = {
    "requested": ["processing", "cancelled"],
    "processing": ["completed", "failed"],
    "failed": ["processing", "cancelled"],
    "completed": [],
    "cancelled": []
}

# ----------------- Customer & Admin Requests -----------------

class ReturnItemCreateRequest(BaseModel):
    order_item_id: int
    quantity: int = Field(gt=0, description="Quantity to return must be > 0")
    reason: Optional[str] = None
    resolution: Optional[str] = Field("refund", description="Resolution: refund or replacement")


class ReturnCreateRequest(BaseModel):
    reason: str = Field(description="Return reason: damaged, defective, wrong_item, missing_item, not_as_expected, other")
    items: List[ReturnItemCreateRequest]
    resolution_type: Optional[str] = Field("refund", description="Primary resolution: refund or replacement")
    customer_note: Optional[str] = None


class ReturnStatusUpdateRequest(BaseModel):
    status: str
    reason: Optional[str] = None
    notes: Optional[str] = None


class ReturnApproveRequest(BaseModel):
    admin_note: Optional[str] = None


class ReturnRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=3, description="Mandatory reason for rejecting customer return")
    admin_note: Optional[str] = None


class ReturnInspectRequest(BaseModel):
    condition: str = Field("resellable", description="resellable, damaged, defective, wrong_item_returned")
    inspection_note: Optional[str] = None
    restock: bool = Field(False, description="If true and condition is resellable, restore inventory")


class RefundCreateRequest(BaseModel):
    amount: Optional[float] = Field(None, gt=0, description="Custom refund amount, or None to auto-calculate")
    reason: Optional[str] = None


class RefundProcessRequest(BaseModel):
    provider_transaction_id: Optional[str] = None
    notes: Optional[str] = None


class ReplacementCreateRequest(BaseModel):
    reason: Optional[str] = None
    notes: Optional[str] = None


class ReplacementStatusUpdateRequest(BaseModel):
    status: str
    reason: Optional[str] = None
    notes: Optional[str] = None


# ----------------- Response Schemas -----------------

class ReturnItemResponse(BaseModel):
    id: int
    return_id: int
    order_item_id: int
    product_id: int
    variant_id: Optional[int] = None
    product_name: str
    variant_title: Optional[str] = None
    sku: str
    unit_price: float
    quantity: int
    reason: Optional[str] = None
    condition: Optional[str] = None
    resolution: str
    refund_amount: float
    restocked: bool
    restocked_at: Optional[datetime] = None
    image_url: Optional[str] = None

    model_config = {"from_attributes": True}


class ReturnStatusHistoryResponse(BaseModel):
    id: int
    return_id: int
    old_status: Optional[str] = None
    new_status: str
    changed_by: str
    reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RefundTransactionResponse(BaseModel):
    id: int
    refund_id: int
    provider: str
    provider_transaction_id: Optional[str] = None
    amount: float
    status: str
    response_reference: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RefundResponse(BaseModel):
    id: int
    refund_number: str
    order_id: int
    return_id: Optional[int] = None
    payment_id: Optional[int] = None
    user_id: int
    amount: float
    currency: str
    status: str
    reason: Optional[str] = None
    provider: str
    provider_refund_id: Optional[str] = None
    requested_at: datetime
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    transactions: List[RefundTransactionResponse] = []

    model_config = {"from_attributes": True}


class ReplacementItemResponse(BaseModel):
    id: int
    replacement_id: int
    original_order_item_id: int
    product_id: int
    variant_id: Optional[int] = None
    product_name: str
    variant_title: Optional[str] = None
    sku: str
    quantity: int
    allocated: bool
    image_url: Optional[str] = None

    model_config = {"from_attributes": True}


class ReplacementStatusHistoryResponse(BaseModel):
    id: int
    replacement_id: int
    old_status: Optional[str] = None
    new_status: str
    changed_by: str
    reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReplacementResponse(BaseModel):
    id: int
    replacement_number: str
    return_id: int
    order_id: int
    user_id: int
    shipment_id: Optional[int] = None
    status: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[ReplacementItemResponse] = []
    status_history: List[ReplacementStatusHistoryResponse] = []
    # Linked shipment details if available
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    shipment_status: Optional[str] = None

    model_config = {"from_attributes": True}


class ReturnResponse(BaseModel):
    id: int
    return_number: str
    order_id: int
    order_number: str
    user_id: int
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    status: str
    resolution_type: str
    reason: str
    customer_note: Optional[str] = None
    admin_note: Optional[str] = None
    rejection_reason: Optional[str] = None
    inspection_condition: Optional[str] = None
    inspection_note: Optional[str] = None
    inspected_by: Optional[str] = None
    inspected_at: Optional[datetime] = None
    requested_at: datetime
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    items: List[ReturnItemResponse] = []
    status_history: List[ReturnStatusHistoryResponse] = []
    refund: Optional[RefundResponse] = None
    replacement: Optional[ReplacementResponse] = None

    model_config = {"from_attributes": True}


# Eligibility helper response
class ReturnEligibilityItemResponse(BaseModel):
    order_item_id: int
    product_id: int
    variant_id: Optional[int] = None
    product_name: str
    variant_title: Optional[str] = None
    sku: str
    unit_price: float
    purchased_quantity: int
    already_returned_quantity: int
    returnable_quantity: int
    is_eligible: bool
    ineligibility_reason: Optional[str] = None
    image_url: Optional[str] = None


class ReturnEligibilityResponse(BaseModel):
    order_id: int
    order_number: str
    order_status: str
    is_eligible: bool
    ineligibility_reason: Optional[str] = None
    return_window_days: int
    delivered_at: Optional[datetime] = None
    return_window_expires_at: Optional[datetime] = None
    return_window_expired: bool
    allowed_reasons: List[str]
    items: List[ReturnEligibilityItemResponse]
