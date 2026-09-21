from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.models.user import User

from app.api.v1.endpoints.auth import get_current_user

from app.schemas.common import APIResponse

from app.schemas.order import (
    OrderCreateRequest,
    OrderResponse,
    OrderListResponse
)
from app.services.order_service import (
    create_order_from_cart,
    get_order_by_id,
    list_customer_orders,
    format_order_response
)

router = APIRouter()

@router.post("", response_model=APIResponse[OrderResponse])
def create_order(
    payload: OrderCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Authoritatively creates an order from the authenticated user's active cart.
    Deducts inventory with transaction records, generates unique order number,
    creates payment record, and clears the cart.
    """
    order = create_order_from_cart(db, current_user, payload)
    formatted = format_order_response(order)
    return APIResponse(
        success=True,
        message="Order placed successfully",
        data=formatted
    )

@router.get("", response_model=APIResponse[OrderListResponse])
def list_my_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve paginated order history for the authenticated customer.
    """
    orders, total = list_customer_orders(db, current_user.id, page=page, page_size=page_size)
    formatted_orders = [format_order_response(o) for o in orders]
    return APIResponse(
        success=True,
        message="Orders retrieved",
        data=OrderListResponse(
            items=formatted_orders,
            total=total,
            page=page,
            page_size=page_size
        )
    )

@router.get("/{order_id}", response_model=APIResponse[OrderResponse])
def get_order_details(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve full order details for a specific order belonging to the customer.
    """
    order = get_order_by_id(db, order_id=order_id, user_id=current_user.id)
    return APIResponse(
        success=True,
        message="Order details retrieved",
        data=format_order_response(order)
    )

@router.get("/{order_id}/payment", response_model=APIResponse[dict])
def get_order_payment(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve payment status and transaction summary for an order.
    """
    order = get_order_by_id(db, order_id=order_id, user_id=current_user.id)
    payment_data = {
        "order_id": order.id,
        "order_number": order.order_number,
        "payment_status": order.payment_status,
        "payment_method": order.payment_method,
        "amount": order.total_amount,
        "currency": order.currency,
        "payments": [
            {
                "id": p.id,
                "provider": p.provider,
                "method": p.method,
                "status": p.status,
                "provider_payment_id": p.provider_payment_id,
                "created_at": p.created_at
            }
            for p in order.payments
        ]
    }
    return APIResponse(
        success=True,
        message="Payment info retrieved",
        data=payment_data
    )

@router.get("/{order_id}/shipment", response_model=APIResponse[dict])
def get_order_shipment_endpoint(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve active shipment for customer's own order.
    """
    from app.services.shipping_service import get_shipment_for_order
    shipment = get_shipment_for_order(db=db, order_id=order_id, user_id=current_user.id)
    if not shipment:
        return APIResponse(
            success=True,
            message="No active shipment found for this order yet",
            data=None
        )
    return APIResponse(
        success=True,
        message="Shipment retrieved",
        data={
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
            "tracking_events": [
                {
                    "id": e.id,
                    "status": e.status,
                    "location": e.location,
                    "description": e.description,
                    "event_time": e.event_time,
                    "source": e.source
                }
                for e in shipment.tracking_events
            ]
        }
    )

@router.get("/{order_id}/tracking", response_model=APIResponse[dict])
def get_order_tracking_endpoint(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Customer-safe tracking endpoint returning current shipment milestones,
    chronological tracking events, and address snapshot.
    """
    from app.services.shipping_service import get_customer_tracking_details
    tracking_data = get_customer_tracking_details(db=db, order_id=order_id, user_id=current_user.id)
    return APIResponse(
        success=True,
        message="Tracking milestones retrieved",
        data=tracking_data.dict()
    )

@router.get("/{order_id}/return-eligibility", response_model=APIResponse[dict])
def get_order_return_eligibility_endpoint(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Authoritatively checks delivered state, return window, purchased quantities,
    and remaining returnable quantities per item for customer's order.
    """
    from app.services.return_service import evaluate_order_return_eligibility
    eligibility = evaluate_order_return_eligibility(db=db, order_id=order_id, user_id=current_user.id)
    return APIResponse(
        success=True,
        message="Return eligibility calculated",
        data=eligibility.dict()
    )

@router.post("/{order_id}/returns", response_model=APIResponse[dict])
def create_order_return_endpoint(
    order_id: int,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit customer return request for an eligible delivered order.
    """
    from app.schemas.returns import ReturnCreateRequest
    from app.services.return_service import create_customer_return_request, format_return_response
    
    req_data = ReturnCreateRequest(**payload)
    ret = create_customer_return_request(db=db, order_id=order_id, user=current_user, data=req_data)
    return APIResponse(
        success=True,
        message=f"Return request #{ret.return_number} submitted successfully",
        data=format_return_response(ret).dict()
    )


