from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_admin
from app.schemas.common import APIResponse
from app.schemas.order import (
    OrderResponse,
    OrderListResponse,
    AdminOrderStatusUpdate
)
from app.services.order_service import (
    get_order_by_id,
    list_admin_orders,
    update_order_status,
    format_order_response
)

router = APIRouter()

@router.get("", response_model=APIResponse[OrderListResponse])
def get_admin_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: pending, confirmed, processing, shipped, delivered, cancelled"),
    payment_status: Optional[str] = Query(None, description="Filter by payment status: pending, paid, failed, refunded"),
    search: Optional[str] = Query(None, description="Search order number or customer name/email"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Search and filter all store orders for the administrator dashboard.
    """
    orders, total = list_admin_orders(
        db=db,
        page=page,
        page_size=page_size,
        status_filter=status,
        payment_status=payment_status,
        search=search,
        start_date=start_date,
        end_date=end_date
    )
    formatted = [format_order_response(o) for o in orders]
    return APIResponse(
        success=True,
        message="Admin orders retrieved",
        data=OrderListResponse(
            items=formatted,
            total=total,
            page=page,
            page_size=page_size
        )
    )

@router.get("/{order_id}", response_model=APIResponse[OrderResponse])
def get_admin_order_details(
    order_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Retrieve single order by ID for the admin panel.
    """
    order = get_order_by_id(db, order_id=order_id)
    return APIResponse(
        success=True,
        message="Order details retrieved",
        data=format_order_response(order)
    )

@router.put("/{order_id}/status", response_model=APIResponse[OrderResponse])
def update_admin_order_status_endpoint(
    order_id: int,
    payload: AdminOrderStatusUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Transition order status. Restores inventory if cancelled.
    Records audit entry in order status history.
    """
    updated_order = update_order_status(
        db=db,
        order_id=order_id,
        new_status=payload.status.lower(),
        admin_user=current_admin,
        reason=payload.reason,
        notes=payload.notes
    )
    return APIResponse(
        success=True,
        message=f"Order status updated to {payload.status}",
        data=format_order_response(updated_order)
    )

@router.post("/{order_id}/shipment", response_model=APIResponse[dict])
def create_shipment_for_order_endpoint(
    order_id: int,
    payload: Optional[dict] = None,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Authoritatively creates a shipment record for an eligible order.
    Does NOT duplicate inventory deduction or alter payment totals.
    """
    from app.schemas.shipment import ShipmentCreateRequest
    from app.services.shipping_service import create_shipment_for_order
    
    req_data = None
    if payload:
        req_data = ShipmentCreateRequest(**payload)
        
    shipment = create_shipment_for_order(
        db=db,
        order_id=order_id,
        data=req_data,
        current_user=current_admin
    )
    return APIResponse(
        success=True,
        message="Shipment created successfully",
        data={
            "id": shipment.id,
            "order_id": shipment.order_id,
            "shipment_number": shipment.shipment_number,
            "carrier": shipment.carrier,
            "tracking_number": shipment.tracking_number,
            "status": shipment.status,
            "estimated_delivery_date": shipment.estimated_delivery_date
        }
    )

