from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.models.user import User

from app.api.v1.endpoints.auth import get_current_admin

from app.schemas.common import APIResponse

from app.schemas.shipment import(
    ShipmentCreateRequest,
    ShipmentUpdateRequest,
    ShipmentStatusUpdateRequest,
    TrackingEventCreateRequest,
    ShipmentResponse,
    ShipmentTrackingEventResponse
)
from app.services.shipping_service import (
    create_shipment_for_order,
    update_shipment_details,
    transition_shipment_status,
    add_tracking_event,
    list_admin_shipments
)
from app.models.shipment import Shipment

router = APIRouter()

@router.get("", response_model=APIResponse[Dict[str, Any]])
def get_all_shipments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: pending, processing, packed, shipped, in_transit, out_for_delivery, delivered, failed, cancelled"),
    carrier: Optional[str] = Query(None, description="Filter by carrier"),
    search: Optional[str] = Query(None, description="Search by shipment #, tracking #, order #, or customer name"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    List and filter store shipments with real PostgreSQL join data.
    """
    skip = (page - 1) * page_size
    items, total = list_admin_shipments(
        db=db,
        skip=skip,
        limit=page_size,
        status_filter=status,
        carrier_filter=carrier,
        search=search
    )
    return APIResponse(
        success=True,
        message="Shipments retrieved successfully",
        data={
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )

@router.get("/{shipment_id}", response_model=APIResponse[Dict[str, Any]])
def get_shipment_detail(
    shipment_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get detailed shipment record with order info and tracking history.
    """
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment with ID {shipment_id} not found"
        )
        
    order = shipment.order
    user = order.user if order else None
    
    data = {
        "id": shipment.id,
        "order_id": shipment.order_id,
        "shipment_number": shipment.shipment_number,
        "carrier": shipment.carrier,
        "shipping_method": shipment.shipping_method,
        "tracking_number": shipment.tracking_number,
        "status": shipment.status,
        "shipping_cost": shipment.shipping_cost,
        "estimated_delivery_date": shipment.estimated_delivery_date,
        "shipped_at": shipment.shipped_at,
        "delivered_at": shipment.delivered_at,
        "notes": shipment.notes,
        "created_at": shipment.created_at,
        "updated_at": shipment.updated_at,
        "order_number": order.order_number if order else None,
        "customer_name": user.full_name if user else "Customer",
        "customer_email": user.email if user else None,
        "shipping_address": order.shipping_address_json if order else None,
        "items": [
            {
                "id": item.id,
                "product_name": item.product_name,
                "variant_title": item.variant_title,
                "sku": item.sku,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "image_url": item.image_url
            }
            for item in (order.items if order else [])
        ],
        "tracking_events": [
            {
                "id": e.id,
                "shipment_id": e.shipment_id,
                "status": e.status,
                "location": e.location,
                "description": e.description,
                "event_time": e.event_time,
                "source": e.source,
                "created_at": e.created_at
            }
            for e in shipment.tracking_events
        ]
    }
    return APIResponse(
        success=True,
        message="Shipment detail retrieved",
        data=data
    )

@router.put("/{shipment_id}", response_model=APIResponse[Dict[str, Any]])
def update_shipment(
    shipment_id: int,
    payload: ShipmentUpdateRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Update carrier, tracking number, method, or estimated delivery date.
    """
    updated = update_shipment_details(
        db=db,
        shipment_id=shipment_id,
        data=payload,
        current_user=current_admin
    )
    return APIResponse(
        success=True,
        message="Shipment updated successfully",
        data={
            "id": updated.id,
            "shipment_number": updated.shipment_number,
            "carrier": updated.carrier,
            "tracking_number": updated.tracking_number,
            "status": updated.status,
            "estimated_delivery_date": updated.estimated_delivery_date
        }
    )

@router.put("/{shipment_id}/status", response_model=APIResponse[Dict[str, Any]])
def update_status(
    shipment_id: int,
    payload: ShipmentStatusUpdateRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Authoritative shipment status transition.
    Synchronizes order status and logs chronological tracking event.
    """
    updated = transition_shipment_status(
        db=db,
        shipment_id=shipment_id,
        data=payload,
        current_user=current_admin
    )
    return APIResponse(
        success=True,
        message=f"Shipment status transitioned to '{updated.status}'",
        data={
            "id": updated.id,
            "shipment_number": updated.shipment_number,
            "status": updated.status,
            "shipped_at": updated.shipped_at,
            "delivered_at": updated.delivered_at
        }
    )

@router.post("/{shipment_id}/tracking-events", response_model=APIResponse[Dict[str, Any]])
def create_tracking_event(
    shipment_id: int,
    payload: TrackingEventCreateRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Append an authoritative tracking milestone event.
    """
    event = add_tracking_event(
        db=db,
        shipment_id=shipment_id,
        data=payload,
        current_user=current_admin
    )
    return APIResponse(
        success=True,
        message="Tracking event added successfully",
        data={
            "id": event.id,
            "shipment_id": event.shipment_id,
            "status": event.status,
            "location": event.location,
            "description": event.description,
            "event_time": event.event_time,
            "source": event.source
        }
    )
