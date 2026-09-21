import json
import uuid
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app.models.order import Order, OrderStatusHistory
from app.models.user import User
from app.models.shipment import Shipment, ShipmentTrackingEvent
from app.schemas.shipment import (
    ShipmentCreateRequest,
    ShipmentUpdateRequest,
    ShipmentStatusUpdateRequest,
    TrackingEventCreateRequest,
    CustomerTrackingResponse,
    ShipmentResponse,
    ShipmentTrackingEventResponse
)
from app.services.shipping_provider import get_shipping_provider

VALID_SHIPMENT_STATUSES = [
    "pending",
    "processing",
    "packed",
    "shipped",
    "in_transit",
    "out_for_delivery",
    "delivered",
    "failed",
    "cancelled"
]

VALID_TRANSITIONS: Dict[str, List[str]] = {
    "pending": ["processing", "packed", "shipped", "cancelled"],
    "processing": ["packed", "shipped", "cancelled"],
    "packed": ["shipped", "cancelled"],
    "shipped": ["in_transit", "out_for_delivery", "delivered", "failed"],
    "in_transit": ["out_for_delivery", "delivered", "failed"],
    "out_for_delivery": ["delivered", "failed"],
    "failed": ["out_for_delivery", "shipped", "cancelled"],
    "delivered": [],
    "cancelled": []
}

def generate_shipment_number() -> str:
    """Generate unique server-side shipment tracking identifier."""
    date_str = datetime.utcnow().strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    return f"SHP-{date_str}-{unique_suffix}"

def calculate_estimated_delivery(shipping_method: str = "standard", from_date: Optional[datetime] = None) -> datetime:
    """Real business logic for calculating estimated delivery date based on method."""
    base_date = from_date or datetime.utcnow()
    method_lower = (shipping_method or "standard").lower()
    
    if "priority" in method_lower:
        delta_days = 2
    elif "express" in method_lower:
        delta_days = 3
    else: # standard
        delta_days = 6
        
    return base_date + timedelta(days=delta_days)

def create_shipment_for_order(
    db: Session,
    order_id: int,
    data: Optional[ShipmentCreateRequest] = None,
    current_user: Optional[User] = None
) -> Shipment:
    """
    Authoritatively create a shipment for a valid confirmed/paid order.
    Does NOT deduct inventory (already committed at checkout).
    Does NOT alter payment status.
    """
    order = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID {order_id} not found"
        )
        
    # Check order eligibility
    if order.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create shipment for a cancelled order"
        )
        
    # Check if order already has an active shipment
    existing_active = db.query(Shipment).filter(
        Shipment.order_id == order_id,
        Shipment.status != "cancelled"
    ).first()
    
    if existing_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Shipment already exists for order #{order.order_number} ({existing_active.shipment_number})"
        )
        
    shipping_method = data.shipping_method if data and data.shipping_method else "standard"
    carrier = data.carrier.strip() if data and data.carrier and data.carrier.strip() else None
    tracking_number = data.tracking_number.strip() if data and data.tracking_number and data.tracking_number.strip() else None
    notes = data.notes if data else None
    
    # Calculate real estimated delivery date if not explicitly specified
    if data and data.estimated_delivery_date:
        est_delivery = data.estimated_delivery_date
    else:
        est_delivery = calculate_estimated_delivery(shipping_method, order.placed_at or order.created_at)

    shipment_number = generate_shipment_number()
    
    shipment = Shipment(
        order_id=order.id,
        shipment_number=shipment_number,
        carrier=carrier,
        shipping_method=shipping_method,
        tracking_number=tracking_number,
        status="pending",
        shipping_cost=order.shipping_amount or 0.0,
        estimated_delivery_date=est_delivery,
        notes=notes
    )
    db.add(shipment)
    db.flush()
    
    # Append initial creation tracking event
    initial_event = ShipmentTrackingEvent(
        shipment_id=shipment.id,
        status="pending",
        location="Fulfillment Center",
        description="Shipment created. Order queued for packing and warehouse verification.",
        event_time=datetime.utcnow(),
        source="admin" if current_user and current_user.role == "admin" else "system"
    )
    db.add(initial_event)
    
    # If carrier & tracking number were provided immediately, log that milestone too
    if tracking_number:
        carrier_label = carrier or "Designated carrier"
        assign_event = ShipmentTrackingEvent(
            shipment_id=shipment.id,
            status="pending",
            location="Fulfillment Center",
            description=f"Tracking number {tracking_number} registered with {carrier_label}.",
            event_time=datetime.utcnow(),
            source="admin" if current_user else "system"
        )
        db.add(assign_event)

    db.commit()
    db.refresh(shipment)
    return shipment

def update_shipment_details(
    db: Session,
    shipment_id: int,
    data: ShipmentUpdateRequest,
    current_user: Optional[User] = None
) -> Shipment:
    """Update carrier, tracking number, method, and ETA."""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment with ID {shipment_id} not found"
        )
        
    old_tracking = shipment.tracking_number
    old_carrier = shipment.carrier

    if data.carrier is not None:
        shipment.carrier = data.carrier.strip() if data.carrier.strip() else None
    if data.shipping_method is not None:
        shipment.shipping_method = data.shipping_method
    if data.tracking_number is not None:
        shipment.tracking_number = data.tracking_number.strip() if data.tracking_number.strip() else None
    if data.estimated_delivery_date is not None:
        shipment.estimated_delivery_date = data.estimated_delivery_date
    if data.notes is not None:
        shipment.notes = data.notes

    # If tracking number was added or changed, log an event
    if shipment.tracking_number and shipment.tracking_number != old_tracking:
        carrier_label = shipment.carrier or "Carrier"
        event = ShipmentTrackingEvent(
            shipment_id=shipment.id,
            status=shipment.status,
            location="Logistics Hub",
            description=f"Tracking identifier assigned: {shipment.tracking_number} ({carrier_label}).",
            event_time=datetime.utcnow(),
            source="admin" if current_user else "system"
        )
        db.add(event)

    db.commit()
    db.refresh(shipment)
    return shipment

def transition_shipment_status(
    db: Session,
    shipment_id: int,
    data: ShipmentStatusUpdateRequest,
    current_user: Optional[User] = None
) -> Shipment:
    """
    Controlled lifecycle transition:
    pending -> processing -> packed -> shipped -> in_transit -> out_for_delivery -> delivered
    Synchronizes Order status authoritatively:
      - shipped -> order.status = 'shipped'
      - delivered -> order.status = 'delivered'
      - packed -> order.status = 'processing' (if still confirmed)
    """
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment with ID {shipment_id} not found"
        )
        
    new_status = data.status.lower()
    if new_status not in VALID_SHIPMENT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid shipment status '{new_status}'. Allowed: {', '.join(VALID_SHIPMENT_STATUSES)}"
        )
        
    current_status = shipment.status
    if current_status == new_status:
        return shipment # No-op
        
    allowed_next = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed_next:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition shipment from '{current_status}' to '{new_status}'. Allowed transitions: {', '.join(allowed_next) if allowed_next else 'None (Terminal state)'}"
        )
        
    # State update
    shipment.status = new_status
    now = datetime.utcnow()
    
    if new_status == "shipped" and not shipment.shipped_at:
        shipment.shipped_at = now
    elif new_status == "delivered" and not shipment.delivered_at:
        shipment.delivered_at = now
        
    # Generate default description if not provided
    default_descriptions = {
        "processing": "Order items are being picked and verified at fulfillment center.",
        "packed": "Items securely packed, labeled, and staged for carrier handoff.",
        "shipped": f"Package dispatched via {shipment.carrier or 'courier'}." + (f" Tracking: {shipment.tracking_number}." if shipment.tracking_number else ""),
        "in_transit": f"Package in transit through courier logistics network." + (f" Location: {data.location}" if data.location else ""),
        "out_for_delivery": "Package is out for delivery with the local courier agent.",
        "delivered": "Package was successfully delivered to the customer.",
        "failed": "Delivery attempt failed. Courier will re-attempt or contact customer.",
        "cancelled": "Shipment has been cancelled."
    }
    
    desc = data.description or default_descriptions.get(new_status, f"Shipment status updated to {new_status}.")
    
    tracking_event = ShipmentTrackingEvent(
        shipment_id=shipment.id,
        status=new_status,
        location=data.location or ("Customer Delivery Address" if new_status == "delivered" else "Logistics Hub"),
        description=desc,
        event_time=now,
        source="admin" if current_user and current_user.role == "admin" else "system"
    )
    db.add(tracking_event)
    
    # Synchronize Order status
    order = db.query(Order).filter(Order.id == shipment.order_id).first()
    if order:
        order_status_map = {
            "packed": "processing",
            "shipped": "shipped",
            "in_transit": "shipped",
            "out_for_delivery": "shipped",
            "delivered": "delivered"
        }
        target_order_status = order_status_map.get(new_status)
        if target_order_status and order.status != target_order_status:
            old_order_status = order.status
            order.status = target_order_status
            
            # Record audit history
            status_history = OrderStatusHistory(
                order_id=order.id,
                old_status=old_order_status,
                new_status=target_order_status,
                changed_by=current_user.full_name if current_user and current_user.full_name else "shipping_service",
                reason=f"Synchronized from shipment #{shipment.shipment_number} ({new_status})"
            )
            db.add(status_history)

    db.commit()
    db.refresh(shipment)
    return shipment

def add_tracking_event(
    db: Session,
    shipment_id: int,
    data: TrackingEventCreateRequest,
    current_user: Optional[User] = None
) -> ShipmentTrackingEvent:
    """Manually add an audit tracking event to a shipment."""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment with ID {shipment_id} not found"
        )
        
    event = ShipmentTrackingEvent(
        shipment_id=shipment.id,
        status=data.status,
        location=data.location,
        description=data.description,
        event_time=data.event_time or datetime.utcnow(),
        source=data.source or ("admin" if current_user else "system")
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

def get_shipment_for_order(
    db: Session,
    order_id: int,
    user_id: Optional[int] = None
) -> Optional[Shipment]:
    """Retrieve active shipment for an order with customer ownership check."""
    query = db.query(Order).filter(Order.id == order_id)
    if user_id is not None:
        query = query.filter(Order.user_id == user_id)
        
    order = query.first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found or unauthorized access"
        )
        
    shipment = db.query(Shipment).options(
        joinedload(Shipment.tracking_events)
    ).filter(
        Shipment.order_id == order_id,
        Shipment.status != "cancelled"
    ).order_by(Shipment.created_at.desc()).first()
    
    return shipment

def get_customer_tracking_details(
    db: Session,
    order_id: int,
    user_id: Optional[int] = None
) -> CustomerTrackingResponse:
    """
    Returns structured, safe tracking details for the customer's own order.
    Exposes no internal provider secrets or backend errors.
    """
    query = db.query(Order).options(
        joinedload(Order.items)
    ).filter(
        Order.id == order_id
    )
    if user_id is not None:
        query = query.filter(Order.user_id == user_id)
        
    order = query.first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found or access denied"
        )
        
    try:
        shipping_address = json.loads(order.shipping_address_json) if order.shipping_address_json else {}
    except Exception:
        shipping_address = {}

    shipment = db.query(Shipment).options(
        joinedload(Shipment.tracking_events)
    ).filter(
        Shipment.order_id == order.id,
        Shipment.status != "cancelled"
    ).order_by(Shipment.created_at.desc()).first()
    
    items_list = [
        {
            "id": item.id,
            "product_id": item.product_id,
            "product_name": item.product_name,
            "variant_title": item.variant_title,
            "sku": item.sku,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "image_url": item.image_url
        }
        for item in order.items
    ]
    
    if not shipment:
        return CustomerTrackingResponse(
            order_id=order.id,
            order_number=order.order_number,
            order_status=order.status,
            shipping_address=shipping_address,
            shipment=None,
            tracking_events=[],
            estimated_delivery_date=calculate_estimated_delivery("standard", order.placed_at or order.created_at),
            status_message="Shipment is being prepared by our fulfillment team.",
            items=items_list
        )
        
    status_messages = {
        "pending": "Shipment registered. Warehouse preparing package.",
        "processing": "Items are being picked and verified.",
        "packed": "Package packed and ready for carrier pickup.",
        "shipped": f"Shipped with {shipment.carrier or 'Courier'}. In transit to destination.",
        "in_transit": "Package is in transit across logistics network.",
        "out_for_delivery": "Out for delivery! Your package will arrive today.",
        "delivered": f"Delivered successfully.",
        "failed": "Delivery attempt failed. Courier will reschedule.",
        "cancelled": "Shipment was cancelled."
    }
    
    shipment_resp = ShipmentResponse(
        id=shipment.id,
        order_id=shipment.order_id,
        shipment_number=shipment.shipment_number,
        carrier=shipment.carrier,
        shipping_method=shipment.shipping_method,
        tracking_number=shipment.tracking_number,
        status=shipment.status,
        shipping_cost=shipment.shipping_cost,
        estimated_delivery_date=shipment.estimated_delivery_date,
        shipped_at=shipment.shipped_at,
        delivered_at=shipment.delivered_at,
        notes=shipment.notes,
        created_at=shipment.created_at,
        updated_at=shipment.updated_at,
        tracking_events=[
            ShipmentTrackingEventResponse.model_validate(e) for e in shipment.tracking_events
        ],
        order_number=order.order_number,
        items_count=len(order.items)
    )
    
    return CustomerTrackingResponse(
        order_id=order.id,
        order_number=order.order_number,
        order_status=order.status,
        shipping_address=shipping_address,
        shipment=shipment_resp,
        tracking_events=shipment_resp.tracking_events,
        estimated_delivery_date=shipment.estimated_delivery_date,
        status_message=status_messages.get(shipment.status, "In progress"),
        items=items_list
    )

def list_admin_shipments(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = None,
    carrier_filter: Optional[str] = None,
    search: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """Admin shipment querying with joins, search, and pagination."""
    query = db.query(Shipment).join(Order, Shipment.order_id == Order.id).outerjoin(User, Order.user_id == User.id)
    
    if status_filter and status_filter.strip():
        query = query.filter(Shipment.status == status_filter.strip())
        
    if carrier_filter and carrier_filter.strip():
        query = query.filter(Shipment.carrier.ilike(f"%{carrier_filter.strip()}%"))
        
    if search and search.strip():
        s = f"%{search.strip()}%"
        query = query.filter(
            (Shipment.shipment_number.ilike(s)) |
            (Shipment.tracking_number.ilike(s)) |
            (Order.order_number.ilike(s)) |
            (User.full_name.ilike(s)) |
            (User.email.ilike(s))
        )
        
    total = query.count()
    shipments = query.options(
        joinedload(Shipment.order).joinedload(Order.user),
        joinedload(Shipment.tracking_events)
    ).order_by(Shipment.created_at.desc()).offset(skip).limit(limit).all()
    
    results = []
    for shp in shipments:
        order = shp.order
        user = order.user if order else None
        
        results.append({
            "id": shp.id,
            "order_id": shp.order_id,
            "shipment_number": shp.shipment_number,
            "carrier": shp.carrier,
            "shipping_method": shp.shipping_method,
            "tracking_number": shp.tracking_number,
            "status": shp.status,
            "shipping_cost": shp.shipping_cost,
            "estimated_delivery_date": shp.estimated_delivery_date,
            "shipped_at": shp.shipped_at,
            "delivered_at": shp.delivered_at,
            "notes": shp.notes,
            "created_at": shp.created_at,
            "updated_at": shp.updated_at,
            "order_number": order.order_number if order else None,
            "customer_name": user.full_name if user else "Guest / Customer",
            "customer_email": user.email if user else None,
            "items_count": len(order.items) if order and order.items else 0,
            "tracking_events": [ShipmentTrackingEventResponse.model_validate(e) for e in shp.tracking_events]
        })
        
    return results, total
