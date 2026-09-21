from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_admin
from app.schemas.common import APIResponse
from app.schemas.returns import (
    ReturnStatusUpdateRequest,
    ReturnApproveRequest,
    ReturnRejectRequest,
    ReturnInspectRequest,
    RefundCreateRequest,
    RefundProcessRequest,
    ReplacementCreateRequest,
    ReplacementStatusUpdateRequest
)
from app.services.return_service import (
    get_return_by_id,
    list_admin_returns,
    approve_return_request,
    reject_return_request,
    inspect_return_items,
    transition_return_status,
    create_refund_for_return,
    process_refund_transaction,
    list_admin_refunds,
    format_refund_response,
    create_replacement_for_return,
    transition_replacement_status,
    list_admin_replacements,
    format_replacement_response,
    format_return_response
)
from app.models.returns import Refund, Replacement

router = APIRouter()

# -------------------------------------------------------------
# Admin Returns
# -------------------------------------------------------------
@router.get("", response_model=APIResponse[dict])
def list_returns(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: requested, approved, rejected, inspection, refunded, etc."),
    resolution_type: Optional[str] = Query(None, description="Filter by resolution: refund, replacement"),
    search: Optional[str] = Query(None, description="Search return number, order number, or customer name/email"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Search and filter customer return requests for warehouse and admin fulfillment.
    """
    returns, total = list_admin_returns(
        db=db,
        page=page,
        page_size=page_size,
        status_filter=status,
        resolution_type=resolution_type,
        search=search,
        start_date=start_date,
        end_date=end_date
    )
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
def get_return(
    return_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Retrieve full return record with items, timeline, linked refund and replacement.
    """
    ret = get_return_by_id(db, return_id=return_id)
    return APIResponse(
        success=True,
        message="Return retrieved",
        data=format_return_response(ret).dict()
    )

@router.put("/{return_id}/approve", response_model=APIResponse[dict])
def approve_return(
    return_id: int,
    payload: Optional[ReturnApproveRequest] = None,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Admin approval of a requested return.
    """
    ret = approve_return_request(db, return_id=return_id, admin_user=current_admin, data=payload)
    return APIResponse(
        success=True,
        message=f"Return #{ret.return_number} approved successfully",
        data=format_return_response(ret).dict()
    )

@router.put("/{return_id}/reject", response_model=APIResponse[dict])
def reject_return(
    return_id: int,
    payload: ReturnRejectRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Admin rejection of a return request with mandatory reason.
    """
    ret = reject_return_request(db, return_id=return_id, admin_user=current_admin, data=payload)
    return APIResponse(
        success=True,
        message=f"Return #{ret.return_number} rejected",
        data=format_return_response(ret).dict()
    )

@router.post("/{return_id}/inspect", response_model=APIResponse[dict])
def inspect_return(
    return_id: int,
    payload: ReturnInspectRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Warehouse inspection: marks item condition (resellable, damaged, defective).
    If condition is resellable and restock=True, authoritatively restores inventory stock
    and logs an InventoryTransaction.
    """
    ret = inspect_return_items(db, return_id=return_id, admin_user=current_admin, data=payload)
    return APIResponse(
        success=True,
        message=f"Return #{ret.return_number} inspection completed (Condition: {payload.condition}, Restocked: {payload.restock})",
        data=format_return_response(ret).dict()
    )

@router.put("/{return_id}/status", response_model=APIResponse[dict])
def update_return_status(
    return_id: int,
    payload: ReturnStatusUpdateRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Advance return lifecycle through controlled status transitions.
    """
    ret = transition_return_status(db, return_id=return_id, data=payload, admin_user=current_admin)
    return APIResponse(
        success=True,
        message=f"Return status updated to '{payload.status}'",
        data=format_return_response(ret).dict()
    )

@router.post("/{return_id}/create-refund", response_model=APIResponse[dict])
def create_refund_endpoint(
    return_id: int,
    payload: Optional[RefundCreateRequest] = None,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Generates an authoritative refund record tied to the return and order,
    enforcing maximum refundable amounts.
    """
    refund = create_refund_for_return(db, return_id=return_id, admin_user=current_admin, data=payload)
    return APIResponse(
        success=True,
        message=f"Refund #{refund.refund_number} created for ₹{refund.amount:.2f}",
        data=format_refund_response(refund).dict()
    )

@router.post("/{return_id}/create-replacement", response_model=APIResponse[dict])
def create_replacement_endpoint(
    return_id: int,
    payload: Optional[ReplacementCreateRequest] = None,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Generates an authoritative replacement record tied to the return and order,
    verifying stock availability in the inventory ledger.
    """
    rep = create_replacement_for_return(db, return_id=return_id, admin_user=current_admin, data=payload)
    return APIResponse(
        success=True,
        message=f"Replacement #{rep.replacement_number} initiated",
        data=format_replacement_response(rep).dict()
    )


# -------------------------------------------------------------
# Admin Refunds
# -------------------------------------------------------------
refunds_router = APIRouter()

@refunds_router.get("", response_model=APIResponse[dict])
def list_refunds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: requested, processing, completed, failed, cancelled"),
    search: Optional[str] = Query(None, description="Search refund number, order number, or customer email"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    refunds, total = list_admin_refunds(db, page=page, page_size=page_size, status_filter=status, search=search)
    formatted = [format_refund_response(r).dict() for r in refunds]
    return APIResponse(
        success=True,
        message="Refunds retrieved",
        data={
            "items": formatted,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )

@refunds_router.get("/{refund_id}", response_model=APIResponse[dict])
def get_refund(
    refund_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    refund = (
        db.query(Refund)
        .filter(Refund.id == refund_id)
        .first()
    )
    if not refund:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund not found")
    return APIResponse(
        success=True,
        message="Refund retrieved",
        data=format_refund_response(refund).dict()
    )

@refunds_router.post("/{refund_id}/process", response_model=APIResponse[dict])
def process_refund(
    refund_id: int,
    payload: Optional[RefundProcessRequest] = None,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Executes authoritative settlement of the refund.
    Validates limits, creates a RefundTransaction record, updates Order payment_status,
    and updates linked Return status to 'refunded'.
    """
    refund = process_refund_transaction(db, refund_id=refund_id, admin_user=current_admin, data=payload)
    return APIResponse(
        success=True,
        message=f"Refund #{refund.refund_number} of ₹{refund.amount:.2f} successfully settled",
        data=format_refund_response(refund).dict()
    )


# -------------------------------------------------------------
# Admin Replacements
# -------------------------------------------------------------
replacements_router = APIRouter()

@replacements_router.get("", response_model=APIResponse[dict])
def list_replacements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: requested, approved, processing, shipped, delivered, completed, cancelled"),
    search: Optional[str] = Query(None, description="Search replacement number, order number, or customer email"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    replacements, total = list_admin_replacements(db, page=page, page_size=page_size, status_filter=status, search=search)
    formatted = [format_replacement_response(r).dict() for r in replacements]
    return APIResponse(
        success=True,
        message="Replacements retrieved",
        data={
            "items": formatted,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )

@replacements_router.get("/{replacement_id}", response_model=APIResponse[dict])
def get_replacement(
    replacement_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    rep = (
        db.query(Replacement)
        .filter(Replacement.id == replacement_id)
        .first()
    )
    if not rep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Replacement not found")
    return APIResponse(
        success=True,
        message="Replacement retrieved",
        data=format_replacement_response(rep).dict()
    )

@replacements_router.put("/{replacement_id}/status", response_model=APIResponse[dict])
def update_replacement_status(
    replacement_id: int,
    payload: ReplacementStatusUpdateRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Advance replacement lifecycle:
    - requested -> approved -> processing (stock allocated) -> shipped (creates shipment) -> delivered -> completed
    """
    rep = transition_replacement_status(db, replacement_id=replacement_id, data=payload, admin_user=current_admin)
    return APIResponse(
        success=True,
        message=f"Replacement #{rep.replacement_number} transitioned to '{payload.status}'",
        data=format_replacement_response(rep).dict()
    )
