from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.models.user import User

from app.api.v1.endpoints.auth import get_current_user

from app.schemas.common import APIResponse

from app.schemas.returns import(
    ReturnCreateRequest,
    ReturnResponse,
    ReturnEligibilityResponse,
    ReplacementResponse,
    RefundResponse
)
from app.services.return_service import (
    evaluate_order_return_eligibility,
    create_customer_return_request,
    cancel_customer_return,
    get_return_by_id,
    list_customer_returns,
    format_return_response,
    format_replacement_response,
    format_refund_response
)
from app.models.returns import Replacement

router = APIRouter()

@router.get("", response_model=APIResponse[dict])
def list_my_returns(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List returns submitted by the authenticated customer.
    """
    returns, total = list_customer_returns(db, current_user.id, page=page, page_size=page_size)
    formatted = [format_return_response(r).dict() for r in returns]
    return APIResponse(
        success=True,
        message="Returns retrieved",
        data={
            "items": formatted,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )

@router.get("/{return_id}", response_model=APIResponse[dict])
def get_return_detail(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed status, returned items, and resolution for customer's return.
    """
    ret = get_return_by_id(db, return_id=return_id, user_id=current_user.id)
    return APIResponse(
        success=True,
        message="Return retrieved",
        data=format_return_response(ret).dict()
    )

@router.post("/{return_id}/cancel", response_model=APIResponse[dict])
def cancel_my_return(
    return_id: int,
    payload: Optional[dict] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Customer self-service cancellation for pending return request.
    Allowed only if return status is in ['requested', 'approved', 'pickup_pending'].
    """
    reason = payload.get("reason") if payload else "Cancelled by customer"
    ret = cancel_customer_return(db, return_id=return_id, user_id=current_user.id, reason=reason)
    return APIResponse(
        success=True,
        message="Return request cancelled successfully",
        data=format_return_response(ret).dict()
    )

@router.get("/{return_id}/refund", response_model=APIResponse[Optional[dict]])
def get_return_refund(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get refund breakdown and settlement status for customer's return.
    """
    ret = get_return_by_id(db, return_id=return_id, user_id=current_user.id)
    if not ret.refund:
        return APIResponse(
            success=True,
            message="No refund record associated with this return yet",
            data=None
        )
    return APIResponse(
        success=True,
        message="Refund details retrieved",
        data=format_refund_response(ret.refund).dict()
    )

@router.get("/{return_id}/replacement", response_model=APIResponse[Optional[dict]])
def get_return_replacement(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get replacement item and shipment dispatch details for customer's return.
    """
    ret = get_return_by_id(db, return_id=return_id, user_id=current_user.id)
    if not ret.replacement:
        return APIResponse(
            success=True,
            message="No replacement record associated with this return yet",
            data=None
        )
    return APIResponse(
        success=True,
        message="Replacement details retrieved",
        data=format_replacement_response(ret.replacement).dict()
    )
