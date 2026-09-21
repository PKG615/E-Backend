import json
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, or_, func
from fastapi import HTTPException, status

from app.models.user import User
from app.models.order import Order, OrderItem, OrderStatusHistory, Payment, PaymentTransaction
from app.models.product import Product, ProductVariant
from app.models.inventory import Inventory, InventoryTransaction
from app.models.shipment import Shipment, ShipmentTrackingEvent
from app.models.returns import (
    Return, ReturnItem, ReturnStatusHistory,
    Refund, RefundTransaction,
    Replacement, ReplacementItem, ReplacementStatusHistory
)
from app.schemas.returns import (
    RETURN_REASONS,
    RETURN_TRANSITIONS,
    REPLACEMENT_TRANSITIONS,
    REFUND_TRANSITIONS,
    ReturnCreateRequest,
    ReturnStatusUpdateRequest,
    ReturnApproveRequest,
    ReturnRejectRequest,
    ReturnInspectRequest,
    RefundCreateRequest,
    RefundProcessRequest,
    ReplacementCreateRequest,
    ReplacementStatusUpdateRequest,
    ReturnResponse,
    ReturnItemResponse,
    ReturnStatusHistoryResponse,
    RefundResponse,
    RefundTransactionResponse,
    ReplacementResponse,
    ReplacementItemResponse,
    ReplacementStatusHistoryResponse,
    ReturnEligibilityResponse,
    ReturnEligibilityItemResponse
)

DEFAULT_RETURN_WINDOW_DAYS = 15

def generate_return_number() -> str:
    date_str = datetime.utcnow().strftime("%Y%m%d")
    suffix = secrets.token_hex(3).upper()
    return f"RET-{date_str}-{suffix}"

def generate_refund_number() -> str:
    date_str = datetime.utcnow().strftime("%Y%m%d")
    suffix = secrets.token_hex(3).upper()
    return f"REF-{date_str}-{suffix}"

def generate_replacement_number() -> str:
    date_str = datetime.utcnow().strftime("%Y%m%d")
    suffix = secrets.token_hex(3).upper()
    return f"REP-{date_str}-{suffix}"


# -------------------------------------------------------------
# Return Eligibility Engine
# -------------------------------------------------------------
def evaluate_order_return_eligibility(
    db: Session, 
    order_id: int, 
    user_id: Optional[int] = None
) -> ReturnEligibilityResponse:
    """
    Authoritatively checks return window, delivered state, purchased quantities,
    and remaining returnable quantities per item.
    """
    query = (
        db.query(Order)
        .options(
            joinedload(Order.items),
            joinedload(Order.shipments),
            joinedload(Order.returns).joinedload(Return.items)
        )
        .filter(Order.id == order_id)
    )
    if user_id is not None:
        query = query.filter(Order.user_id == user_id)
    
    order = query.first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Order not found or unauthorized"
        )

    # Delivered status evaluation
    is_delivered = (order.status == "delivered")
    
    # Check latest delivered shipment date or fallback to order updated date
    delivered_at = None
    for shp in (order.shipments or []):
        if shp.delivered_at:
            delivered_at = shp.delivered_at
            break
    if not delivered_at and is_delivered:
        delivered_at = order.updated_at or order.placed_at or order.created_at

    return_window_days = DEFAULT_RETURN_WINDOW_DAYS
    window_expires_at = None
    window_expired = False

    if delivered_at:
        window_expires_at = delivered_at + timedelta(days=return_window_days)
        if datetime.utcnow() > window_expires_at:
            window_expired = True

    # Check active returns for item quantities
    # Returns in "rejected" or "cancelled" states do not lock items
    returned_quantities_by_item: Dict[int, int] = {}
    for ret in (order.returns or []):
        if ret.status not in ["rejected", "cancelled"]:
            for item in (ret.items or []):
                returned_quantities_by_item[item.order_item_id] = (
                    returned_quantities_by_item.get(item.order_item_id, 0) + item.quantity
                )

    order_eligible = True
    order_ineligible_reason = None

    if not is_delivered:
        order_eligible = False
        order_ineligible_reason = f"Order status is '{order.status}'. Returns are only eligible after delivery."
    elif window_expired:
        order_eligible = False
        order_ineligible_reason = f"The {return_window_days}-day return window expired on {window_expires_at.strftime('%Y-%m-%d')}."

    items_evaluation: List[ReturnEligibilityItemResponse] = []
    has_any_returnable_item = False

    for order_item in (order.items or []):
        purchased_qty = order_item.quantity
        already_returned_qty = returned_quantities_by_item.get(order_item.id, 0)
        returnable_qty = max(0, purchased_qty - already_returned_qty)

        item_eligible = order_eligible and (returnable_qty > 0)
        item_ineligibility_reason = None
        if not order_eligible:
            item_ineligibility_reason = order_ineligible_reason
        elif returnable_qty == 0:
            item_ineligibility_reason = "All purchased units of this item have already been returned or are in review."

        if item_eligible:
            has_any_returnable_item = True

        items_evaluation.append(
            ReturnEligibilityItemResponse(
                order_item_id=order_item.id,
                product_id=order_item.product_id,
                variant_id=order_item.variant_id,
                product_name=order_item.product_name,
                variant_title=order_item.variant_title,
                sku=order_item.sku,
                unit_price=order_item.unit_price,
                purchased_quantity=purchased_qty,
                already_returned_quantity=already_returned_qty,
                returnable_quantity=returnable_qty,
                is_eligible=item_eligible,
                ineligibility_reason=item_ineligibility_reason,
                image_url=order_item.image_url
            )
        )

    overall_eligible = order_eligible and has_any_returnable_item
    if order_eligible and not has_any_returnable_item and not order_ineligible_reason:
        order_ineligible_reason = "No items remaining available for return in this order."

    return ReturnEligibilityResponse(
        order_id=order.id,
        order_number=order.order_number,
        order_status=order.status,
        is_eligible=overall_eligible,
        ineligibility_reason=order_ineligible_reason,
        return_window_days=return_window_days,
        delivered_at=delivered_at,
        return_window_expires_at=window_expires_at,
        return_window_expired=window_expired,
        allowed_reasons=RETURN_REASONS,
        items=items_evaluation
    )


# -------------------------------------------------------------
# Customer Return Creation
# -------------------------------------------------------------
def create_customer_return_request(
    db: Session,
    order_id: int,
    user: User,
    data: ReturnCreateRequest
) -> Return:
    """
    Submits a return request with server-side validation of order ownership,
    delivery state, return window, reasons, and individual item quantities.
    """
    if data.reason not in RETURN_REASONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid return reason '{data.reason}'. Allowed reasons: {RETURN_REASONS}"
        )

    if not data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one order item must be selected for return"
        )

    # Evaluate full authoritative eligibility
    eligibility = evaluate_order_return_eligibility(db, order_id=order_id, user_id=user.id)
    if not eligibility.is_eligible:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=eligibility.ineligibility_reason or "This order is not eligible for return."
        )

    order = db.query(Order).filter(Order.id == order_id).first()

    # Map eligible items by id
    eligible_map = {item.order_item_id: item for item in eligibility.items}

    # Validate each requested item
    requested_items_data = []
    for req_item in data.items:
        el_item = eligible_map.get(req_item.order_item_id)
        if not el_item:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order item {req_item.order_item_id} does not belong to this order"
            )

        if not el_item.is_eligible:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Item '{el_item.product_name}' is not eligible for return: {el_item.ineligibility_reason}"
            )

        if req_item.quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Return quantity for item '{el_item.product_name}' must be greater than zero"
            )

        if req_item.quantity > el_item.returnable_quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Requested quantity ({req_item.quantity}) exceeds remaining returnable quantity "
                    f"({el_item.returnable_quantity}) for '{el_item.product_name}'"
                )
            )

        # Calculate proportional refund amount: (line_total / purchased_quantity) * requested_quantity
        order_item = db.query(OrderItem).filter(OrderItem.id == req_item.order_item_id).first()
        unit_calc_price = (order_item.line_total / order_item.quantity) if order_item.quantity > 0 else order_item.unit_price
        item_refund_amount = round(unit_calc_price * req_item.quantity, 2)

        requested_items_data.append({
            "order_item": order_item,
            "quantity": req_item.quantity,
            "reason": req_item.reason or data.reason,
            "resolution": req_item.resolution or data.resolution_type or "refund",
            "refund_amount": item_refund_amount
        })

    # Generate unique return number
    return_number = generate_return_number()
    while db.query(Return).filter(Return.return_number == return_number).first():
        return_number = generate_return_number()

    # Create Return record
    return_order = Return(
        return_number=return_number,
        order_id=order.id,
        user_id=user.id,
        status="requested",
        resolution_type=data.resolution_type or "refund",
        reason=data.reason,
        customer_note=data.customer_note,
        requested_at=datetime.utcnow()
    )
    db.add(return_order)
    db.flush()

    # Create ReturnItem records
    for itm in requested_items_data:
        ret_item = ReturnItem(
            return_id=return_order.id,
            order_item_id=itm["order_item"].id,
            product_id=itm["order_item"].product_id,
            variant_id=itm["order_item"].variant_id,
            quantity=itm["quantity"],
            reason=itm["reason"],
            resolution=itm["resolution"],
            refund_amount=itm["refund_amount"],
            restocked=False
        )
        db.add(ret_item)

    # Initial Return Status History
    history = ReturnStatusHistory(
        return_id=return_order.id,
        old_status=None,
        new_status="requested",
        changed_by=user.email or f"customer_{user.id}",
        reason="Customer submitted return request"
    )
    db.add(history)

    db.commit()
    db.refresh(return_order)
    return return_order


# -------------------------------------------------------------
# Customer Return Cancellation
# -------------------------------------------------------------
def cancel_customer_return(
    db: Session,
    return_id: int,
    user_id: int,
    reason: Optional[str] = None
) -> Return:
    return_order = (
        db.query(Return)
        .filter(Return.id == return_id, Return.user_id == user_id)
        .first()
    )
    if not return_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Return request not found"
        )

    # Cancellation allowed only during initial stages
    cancellable_statuses = ["requested", "approved", "pickup_pending"]
    if return_order.status not in cancellable_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot cancel return in '{return_order.status}' status. "
                f"Cancellation is only permitted while status is one of: {cancellable_statuses}"
            )
        )

    old_status = return_order.status
    return_order.status = "cancelled"
    
    history = ReturnStatusHistory(
        return_id=return_order.id,
        old_status=old_status,
        new_status="cancelled",
        changed_by=f"customer_{user_id}",
        reason=reason or "Cancelled by customer"
    )
    db.add(history)

    db.commit()
    db.refresh(return_order)
    return return_order


# -------------------------------------------------------------
# Admin Return Approval / Rejection / Inspection
# -------------------------------------------------------------
def approve_return_request(
    db: Session,
    return_id: int,
    admin_user: User,
    data: Optional[ReturnApproveRequest] = None
) -> Return:
    return_order = (
        db.query(Return)
        .options(joinedload(Return.items), joinedload(Return.order))
        .filter(Return.id == return_id)
        .first()
    )
    if not return_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")

    if return_order.status != "requested":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve return in '{return_order.status}' status. Only 'requested' returns can be approved."
        )

    # Revalidate eligibility at approval time
    eligibility = evaluate_order_return_eligibility(db, order_id=return_order.order_id)
    if not eligibility.is_eligible and return_order.order.status != "delivered":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order is no longer eligible for return: {eligibility.ineligibility_reason}"
        )

    old_status = return_order.status
    return_order.status = "approved"
    return_order.approved_at = datetime.utcnow()
    if data and data.admin_note:
        return_order.admin_note = (return_order.admin_note + "\n" if return_order.admin_note else "") + f"[Approval] {data.admin_note}"

    history = ReturnStatusHistory(
        return_id=return_order.id,
        old_status=old_status,
        new_status="approved",
        changed_by=admin_user.email or f"admin_{admin_user.id}",
        reason=(data.admin_note if data else None) or "Return request approved by administrator"
    )
    db.add(history)

    db.commit()
    db.refresh(return_order)
    return return_order


def reject_return_request(
    db: Session,
    return_id: int,
    admin_user: User,
    data: ReturnRejectRequest
) -> Return:
    return_order = db.query(Return).filter(Return.id == return_id).first()
    if not return_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")

    rejectable_statuses = ["requested", "approved", "inspection"]
    if return_order.status not in rejectable_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject return in '{return_order.status}' status. Allowed states: {rejectable_statuses}"
        )

    old_status = return_order.status
    return_order.status = "rejected"
    return_order.rejected_at = datetime.utcnow()
    return_order.rejection_reason = data.rejection_reason
    if data.admin_note:
        return_order.admin_note = (return_order.admin_note + "\n" if return_order.admin_note else "") + f"[Rejection] {data.admin_note}"

    history = ReturnStatusHistory(
        return_id=return_order.id,
        old_status=old_status,
        new_status="rejected",
        changed_by=admin_user.email or f"admin_{admin_user.id}",
        reason=data.rejection_reason
    )
    db.add(history)

    db.commit()
    db.refresh(return_order)
    return return_order


def inspect_return_items(
    db: Session,
    return_id: int,
    admin_user: User,
    data: ReturnInspectRequest
) -> Return:
    """
    Records warehouse inspection condition. If items are resellable and restock=True,
    authoritatively increases Inventory stock and logs an InventoryTransaction.
    """
    return_order = (
        db.query(Return)
        .options(joinedload(Return.items))
        .filter(Return.id == return_id)
        .first()
    )
    if not return_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")

    # Update inspection fields
    return_order.inspection_condition = data.condition
    return_order.inspection_note = data.inspection_note
    return_order.inspected_by = admin_user.email or f"admin_{admin_user.id}"
    return_order.inspected_at = datetime.utcnow()

    # If currently in 'received', transition to 'inspection'
    if return_order.status == "received":
        old_status = return_order.status
        return_order.status = "inspection"
        history = ReturnStatusHistory(
            return_id=return_order.id,
            old_status=old_status,
            new_status="inspection",
            changed_by=admin_user.email or f"admin_{admin_user.id}",
            reason=f"Inspection completed: Condition marked as '{data.condition}'"
        )
        db.add(history)

    # If restock requested and condition is resellable, restore inventory
    if data.restock and data.condition == "resellable":
        for ret_item in return_order.items:
            if not ret_item.restocked:
                ret_item.condition = "resellable"
                ret_item.restocked = True
                ret_item.restocked_at = datetime.utcnow()

                # Find inventory record
                if ret_item.variant_id:
                    inv = (
                        db.query(Inventory)
                        .filter(Inventory.product_id == ret_item.product_id, Inventory.variant_id == ret_item.variant_id)
                        .first()
                    )
                else:
                    inv = (
                        db.query(Inventory)
                        .filter(Inventory.product_id == ret_item.product_id, Inventory.variant_id.is_(None))
                        .first()
                    )
                if inv:
                    qty_before = inv.on_hand_quantity
                    inv.on_hand_quantity += ret_item.quantity
                    inv.available_quantity = max(0, inv.on_hand_quantity - inv.reserved_quantity)
                    qty_after = inv.on_hand_quantity

                    # Update Product general stock counter
                    prod = db.query(Product).filter(Product.id == ret_item.product_id).first()
                    if prod:
                        prod.stock += ret_item.quantity

                    # Log authoritative ledger transaction
                    tx = InventoryTransaction(
                        inventory_id=inv.id,
                        transaction_type="RECEIVE",
                        quantity_change=ret_item.quantity,
                        quantity_before=qty_before,
                        quantity_after=qty_after,
                        reference_type="return_restock",
                        reference_id=return_order.return_number,
                        reason=f"Restock from inspected return {return_order.return_number}",
                        created_by=admin_user.email or f"admin_{admin_user.id}"
                    )
                    db.add(tx)

    db.commit()
    db.refresh(return_order)
    return return_order


def transition_return_status(
    db: Session,
    return_id: int,
    data: ReturnStatusUpdateRequest,
    admin_user: User
) -> Return:
    return_order = db.query(Return).filter(Return.id == return_id).first()
    if not return_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")

    current_status = return_order.status
    target_status = data.status

    if current_status == target_status:
        return return_order

    allowed = RETURN_TRANSITIONS.get(current_status, [])
    if target_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition return from '{current_status}' to '{target_status}'. Allowed transitions: {allowed}"
        )

    old_status = current_status
    return_order.status = target_status

    if target_status == "received" and not return_order.received_at:
        return_order.received_at = datetime.utcnow()
    elif target_status in ["closed", "refunded"] and not return_order.completed_at:
        return_order.completed_at = datetime.utcnow()

    if data.notes:
        return_order.admin_note = (return_order.admin_note + "\n" if return_order.admin_note else "") + f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {data.notes}"

    history = ReturnStatusHistory(
        return_id=return_order.id,
        old_status=old_status,
        new_status=target_status,
        changed_by=admin_user.email or f"admin_{admin_user.id}",
        reason=data.reason or f"Status transitioned to '{target_status}'"
    )
    db.add(history)

    db.commit()
    db.refresh(return_order)
    return return_order


# -------------------------------------------------------------
# Refund Service & Lifecycle
# -------------------------------------------------------------
def calculate_order_refundable_amount(db: Session, order_id: int) -> Tuple[float, float, float]:
    """
    Returns (order_total, total_already_refunded, remaining_refundable)
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    completed_refunds = (
        db.query(Refund)
        .filter(Refund.order_id == order_id, Refund.status == "completed")
        .all()
    )
    already_refunded = sum(r.amount for r in completed_refunds)
    remaining = max(0.0, round(order.total_amount - already_refunded, 2))
    return order.total_amount, already_refunded, remaining


def create_refund_for_return(
    db: Session,
    return_id: int,
    admin_user: User,
    data: Optional[RefundCreateRequest] = None
) -> Refund:
    """
    Creates a refund request record tied to a return and order.
    Revalidates against over-refund limits.
    """
    return_order = (
        db.query(Return)
        .options(joinedload(Return.items), joinedload(Return.order), joinedload(Return.refund))
        .filter(Return.id == return_id)
        .first()
    )
    if not return_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")

    if return_order.refund:
        return return_order.refund

    order = return_order.order
    order_total, already_refunded, max_refundable = calculate_order_refundable_amount(db, order.id)

    # Determine requested refund amount
    if data and data.amount is not None:
        refund_amount = round(data.amount, 2)
    else:
        # Sum items refund amount
        calculated_sum = sum(item.refund_amount for item in return_order.items)
        refund_amount = round(min(calculated_sum, max_refundable), 2)

    if refund_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calculated refund amount must be greater than zero."
        )

    if refund_amount > max_refundable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Requested refund amount ₹{refund_amount:.2f} exceeds remaining refundable limit "
                f"₹{max_refundable:.2f} for Order #{order.order_number}."
            )
        )

    # Find matching payment record
    payment = (
        db.query(Payment)
        .filter(Payment.order_id == order.id, Payment.status == "paid")
        .first()
    )
    if not payment:
        # Check any payment
        payment = db.query(Payment).filter(Payment.order_id == order.id).first()

    refund_number = generate_refund_number()
    while db.query(Refund).filter(Refund.refund_number == refund_number).first():
        refund_number = generate_refund_number()

    refund = Refund(
        refund_number=refund_number,
        order_id=order.id,
        return_id=return_order.id,
        payment_id=payment.id if payment else None,
        user_id=return_order.user_id,
        amount=refund_amount,
        currency="INR",
        status="requested",
        reason=(data.reason if data else None) or f"Refund for approved return {return_order.return_number}",
        provider=payment.provider if payment else "standard",
        requested_at=datetime.utcnow()
    )
    db.add(refund)

    # Automatically transition return to approved_for_refund if in inspection
    if return_order.status in ["inspection", "received", "approved"]:
        old_status = return_order.status
        return_order.status = "approved_for_refund"
        history = ReturnStatusHistory(
            return_id=return_order.id,
            old_status=old_status,
            new_status="approved_for_refund",
            changed_by=admin_user.email or f"admin_{admin_user.id}",
            reason=f"Refund #{refund_number} generated for ₹{refund_amount:.2f}"
        )
        db.add(history)

    db.commit()
    db.refresh(refund)
    return refund


def process_refund_transaction(
    db: Session,
    refund_id: int,
    admin_user: User,
    data: Optional[RefundProcessRequest] = None
) -> Refund:
    """
    Executes authoritative settlement of the refund.
    Validates limits, creates a RefundTransaction record, updates Order payment_status,
    and updates linked Return status to 'refunded'.
    """
    refund = (
        db.query(Refund)
        .options(joinedload(Refund.order), joinedload(Refund.return_order))
        .filter(Refund.id == refund_id)
        .first()
    )
    if not refund:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund not found")

    if refund.status == "completed":
        return refund

    if refund.status not in ["requested", "processing", "failed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot process refund in '{refund.status}' status."
        )

    # Re-verify against over-refund limits
    order = refund.order
    _, already_refunded, max_refundable = calculate_order_refundable_amount(db, order.id)
    if refund.amount > (max_refundable + (refund.amount if refund.status == "completed" else 0.0)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Over-refund protection: Refund amount ₹{refund.amount:.2f} exceeds remaining refundable limit."
        )

    provider_tx_id = (data.provider_transaction_id if data else None) or f"REF_TXN_{secrets.token_hex(8).upper()}"
    
    # Create transaction log
    tx = RefundTransaction(
        refund_id=refund.id,
        provider=refund.provider,
        provider_transaction_id=provider_tx_id,
        amount=refund.amount,
        status="success",
        response_reference=f"Authoritative settlement via {refund.provider.upper()}"
    )
    db.add(tx)

    refund.status = "completed"
    refund.provider_refund_id = provider_tx_id
    refund.processed_at = datetime.utcnow()

    # Update Order payment status
    total_order_amount, new_already_refunded, remaining = calculate_order_refundable_amount(db, order.id)
    total_after_this = new_already_refunded + refund.amount
    if total_after_this >= order.total_amount:
        order.payment_status = "refunded"
    else:
        order.payment_status = "partially_refunded"

    # Order history entry
    hist = OrderStatusHistory(
        order_id=order.id,
        old_status=order.status,
        new_status=order.status,
        changed_by=admin_user.email or f"admin_{admin_user.id}",
        reason=f"Refund #{refund.refund_number} completed: ₹{refund.amount:.2f} credited to customer"
    )
    db.add(hist)

    # Update linked return if present
    if refund.return_order:
        ret = refund.return_order
        if ret.status not in ["refunded", "closed"]:
            old_ret_status = ret.status
            ret.status = "refunded"
            ret.completed_at = datetime.utcnow()
            ret_hist = ReturnStatusHistory(
                return_id=ret.id,
                old_status=old_ret_status,
                new_status="refunded",
                changed_by=admin_user.email or f"admin_{admin_user.id}",
                reason=f"Refund #{refund.refund_number} successfully settled"
            )
            db.add(ret_hist)

    db.commit()
    db.refresh(refund)
    return refund


# -------------------------------------------------------------
# Replacement Service & Lifecycle
# -------------------------------------------------------------
def create_replacement_for_return(
    db: Session,
    return_id: int,
    admin_user: User,
    data: Optional[ReplacementCreateRequest] = None
) -> Replacement:
    """
    Creates a replacement request record tied to a return and order.
    Validates replacement stock availability in authoritative Inventory.
    """
    return_order = (
        db.query(Return)
        .options(joinedload(Return.items), joinedload(Return.order), joinedload(Return.replacement))
        .filter(Return.id == return_id)
        .first()
    )
    if not return_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")

    if return_order.replacement:
        return return_order.replacement

    order = return_order.order

    # Validate stock availability for replacement items
    for item in return_order.items:
        if item.variant_id:
            inv = (
                db.query(Inventory)
                .filter(Inventory.product_id == item.product_id, Inventory.variant_id == item.variant_id)
                .first()
            )
        else:
            inv = (
                db.query(Inventory)
                .filter(Inventory.product_id == item.product_id, Inventory.variant_id.is_(None))
                .first()
            )
        if not inv or inv.available_quantity < item.quantity:
            prod_name = item.order_item.product_name if item.order_item else "Product"
            avail = inv.available_quantity if inv else 0
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot create replacement: Insufficient stock for '{prod_name}' (available: {avail}, requested: {item.quantity})"
            )

    replacement_number = generate_replacement_number()
    while db.query(Replacement).filter(Replacement.replacement_number == replacement_number).first():
        replacement_number = generate_replacement_number()

    replacement = Replacement(
        replacement_number=replacement_number,
        return_id=return_order.id,
        order_id=order.id,
        user_id=return_order.user_id,
        status="requested",
        reason=(data.reason if data else None) or f"Replacement for return {return_order.return_number}",
        notes=data.notes if data else None
    )
    db.add(replacement)
    db.flush()

    for item in return_order.items:
        rep_item = ReplacementItem(
            replacement_id=replacement.id,
            original_order_item_id=item.order_item_id,
            product_id=item.product_id,
            variant_id=item.variant_id,
            quantity=item.quantity,
            allocated=False
        )
        db.add(rep_item)

    rep_hist = ReplacementStatusHistory(
        replacement_id=replacement.id,
        old_status=None,
        new_status="requested",
        changed_by=admin_user.email or f"admin_{admin_user.id}",
        reason="Replacement request created"
    )
    db.add(rep_hist)

    # Transition return to replacement_processing
    if return_order.status in ["inspection", "received", "approved"]:
        old_status = return_order.status
        return_order.status = "replacement_processing"
        ret_hist = ReturnStatusHistory(
            return_id=return_order.id,
            old_status=old_status,
            new_status="replacement_processing",
            changed_by=admin_user.email or f"admin_{admin_user.id}",
            reason=f"Replacement #{replacement_number} initiated"
        )
        db.add(ret_hist)

    db.commit()
    db.refresh(replacement)
    return replacement


def transition_replacement_status(
    db: Session,
    replacement_id: int,
    data: ReplacementStatusUpdateRequest,
    admin_user: User
) -> Replacement:
    """
    Controlled replacement lifecycle transition:
    - requested -> approved -> processing (allocates stock) -> shipped (creates shipment) -> delivered -> completed
    """
    replacement = (
        db.query(Replacement)
        .options(
            joinedload(Replacement.items),
            joinedload(Replacement.order),
            joinedload(Replacement.return_order)
        )
        .filter(Replacement.id == replacement_id)
        .first()
    )
    if not replacement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Replacement not found")

    current_status = replacement.status
    target_status = data.status

    if current_status == target_status:
        return replacement

    allowed = REPLACEMENT_TRANSITIONS.get(current_status, [])
    if target_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition replacement from '{current_status}' to '{target_status}'. Allowed transitions: {allowed}"
        )

    # If transitioning to 'processing' or 'shipped', perform authoritative stock deduction if not already allocated
    if target_status in ["processing", "shipped"]:
        for rep_item in replacement.items:
            if not rep_item.allocated:
                if rep_item.variant_id:
                    inv = (
                        db.query(Inventory)
                        .filter(Inventory.product_id == rep_item.product_id, Inventory.variant_id == rep_item.variant_id)
                        .first()
                    )
                else:
                    inv = (
                        db.query(Inventory)
                        .filter(Inventory.product_id == rep_item.product_id, Inventory.variant_id.is_(None))
                        .first()
                    )
                if not inv or inv.available_quantity < rep_item.quantity:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Insufficient stock to fulfill replacement order item"
                    )

                qty_before = inv.on_hand_quantity
                inv.on_hand_quantity -= rep_item.quantity
                inv.available_quantity = max(0, inv.on_hand_quantity - inv.reserved_quantity)
                qty_after = inv.on_hand_quantity

                prod = db.query(Product).filter(Product.id == rep_item.product_id).first()
                if prod:
                    prod.stock = max(0, prod.stock - rep_item.quantity)

                tx = InventoryTransaction(
                    inventory_id=inv.id,
                    transaction_type="ADJUSTMENT",
                    quantity_change=-rep_item.quantity,
                    quantity_before=qty_before,
                    quantity_after=qty_after,
                    reference_type="replacement",
                    reference_id=replacement.replacement_number,
                    reason=f"Stock deduction for replacement {replacement.replacement_number}",
                    created_by=admin_user.email or f"admin_{admin_user.id}"
                )
                db.add(tx)
                rep_item.allocated = True

    # If transitioning to 'shipped', automatically create a replacement Shipment if not exists
    if target_status == "shipped" and not replacement.shipment_id:
        shp_number = f"SHP-{datetime.utcnow().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        tracking_number = f"REP-{secrets.token_hex(5).upper()}"
        shipment = Shipment(
            order_id=replacement.order_id,
            shipment_number=shp_number,
            carrier="Express Replacement Dispatch",
            shipping_method="express",
            tracking_number=tracking_number,
            status="shipped",
            shipped_at=datetime.utcnow(),
            notes=f"Replacement shipment for {replacement.replacement_number}"
        )
        db.add(shipment)
        db.flush()

        evt = ShipmentTrackingEvent(
            shipment_id=shipment.id,
            status="shipped",
            location="Fulfillment Center",
            description=f"Replacement package dispatched under {tracking_number}",
            event_time=datetime.utcnow(),
            source="admin"
        )
        db.add(evt)
        replacement.shipment_id = shipment.id

    # If transitioning to 'delivered' or 'completed', close return
    if target_status in ["delivered", "completed"] and replacement.return_order:
        ret = replacement.return_order
        if ret.status not in ["closed", "refunded"]:
            old_ret_status = ret.status
            ret.status = "closed"
            ret.completed_at = datetime.utcnow()
            ret_hist = ReturnStatusHistory(
                return_id=ret.id,
                old_status=old_ret_status,
                new_status="closed",
                changed_by=admin_user.email or f"admin_{admin_user.id}",
                reason=f"Replacement #{replacement.replacement_number} delivered"
            )
            db.add(ret_hist)

    old_status = replacement.status
    replacement.status = target_status
    if data.notes:
        replacement.notes = (replacement.notes + "\n" if replacement.notes else "") + f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {data.notes}"

    rep_hist = ReplacementStatusHistory(
        replacement_id=replacement.id,
        old_status=old_status,
        new_status=target_status,
        changed_by=admin_user.email or f"admin_{admin_user.id}",
        reason=data.reason or f"Status transitioned to '{target_status}'"
    )
    db.add(rep_hist)

    db.commit()
    db.refresh(replacement)
    return replacement


# -------------------------------------------------------------
# Query & Format Helpers
# -------------------------------------------------------------
def get_return_by_id(db: Session, return_id: int, user_id: Optional[int] = None) -> Return:
    query = (
        db.query(Return)
        .options(
            joinedload(Return.order),
            joinedload(Return.user),
            joinedload(Return.items).joinedload(ReturnItem.order_item),
            joinedload(Return.status_history),
            joinedload(Return.refund).joinedload(Refund.transactions),
            joinedload(Return.replacement).joinedload(Replacement.items).joinedload(ReplacementItem.original_order_item),
            joinedload(Return.replacement).joinedload(Replacement.status_history),
            joinedload(Return.replacement).joinedload(Replacement.shipment)
        )
        .filter(Return.id == return_id)
    )
    if user_id is not None:
        query = query.filter(Return.user_id == user_id)
    ret = query.first()
    if not ret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")
    return ret


def list_customer_returns(
    db: Session,
    user_id: int,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[Return], int]:
    query = (
        db.query(Return)
        .options(
            joinedload(Return.order),
            joinedload(Return.items).joinedload(ReturnItem.order_item),
            joinedload(Return.status_history),
            joinedload(Return.refund),
            joinedload(Return.replacement)
        )
        .filter(Return.user_id == user_id)
        .order_by(desc(Return.created_at))
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def list_admin_returns(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    resolution_type: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Tuple[List[Return], int]:
    query = (
        db.query(Return)
        .join(Return.order)
        .join(Return.user)
        .options(
            joinedload(Return.order),
            joinedload(Return.user),
            joinedload(Return.items).joinedload(ReturnItem.order_item),
            joinedload(Return.status_history),
            joinedload(Return.refund),
            joinedload(Return.replacement)
        )
    )

    if status_filter:
        query = query.filter(Return.status == status_filter)
    if resolution_type:
        query = query.filter(Return.resolution_type == resolution_type)
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Return.return_number.ilike(search_fmt),
                Order.order_number.ilike(search_fmt),
                User.email.ilike(search_fmt),
                User.full_name.ilike(search_fmt)
            )
        )
    if start_date:
        query = query.filter(Return.created_at >= start_date)
    if end_date:
        query = query.filter(Return.created_at <= end_date)

    total = query.count()
    items = query.order_by(desc(Return.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def list_admin_refunds(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    search: Optional[str] = None
) -> Tuple[List[Refund], int]:
    query = (
        db.query(Refund)
        .join(Refund.order)
        .join(Refund.user)
        .options(
            joinedload(Refund.order),
            joinedload(Refund.user),
            joinedload(Refund.return_order),
            joinedload(Refund.transactions)
        )
    )
    if status_filter:
        query = query.filter(Refund.status == status_filter)
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Refund.refund_number.ilike(search_fmt),
                Order.order_number.ilike(search_fmt),
                User.email.ilike(search_fmt)
            )
        )
    total = query.count()
    items = query.order_by(desc(Refund.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def list_admin_replacements(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    search: Optional[str] = None
) -> Tuple[List[Replacement], int]:
    query = (
        db.query(Replacement)
        .join(Replacement.order)
        .join(Replacement.user)
        .options(
            joinedload(Replacement.order),
            joinedload(Replacement.user),
            joinedload(Replacement.return_order),
            joinedload(Replacement.items).joinedload(ReplacementItem.original_order_item),
            joinedload(Replacement.shipment)
        )
    )
    if status_filter:
        query = query.filter(Replacement.status == status_filter)
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Replacement.replacement_number.ilike(search_fmt),
                Order.order_number.ilike(search_fmt),
                User.email.ilike(search_fmt)
            )
        )
    total = query.count()
    items = query.order_by(desc(Replacement.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def format_refund_response(refund: Refund) -> RefundResponse:
    txs = [
        RefundTransactionResponse(
            id=t.id,
            refund_id=t.refund_id,
            provider=t.provider,
            provider_transaction_id=t.provider_transaction_id,
            amount=t.amount,
            status=t.status,
            response_reference=t.response_reference,
            created_at=t.created_at
        )
        for t in (refund.transactions or [])
    ]
    return RefundResponse(
        id=refund.id,
        refund_number=refund.refund_number,
        order_id=refund.order_id,
        return_id=refund.return_id,
        payment_id=refund.payment_id,
        user_id=refund.user_id,
        amount=refund.amount,
        currency=refund.currency or "INR",
        status=refund.status,
        reason=refund.reason,
        provider=refund.provider,
        provider_refund_id=refund.provider_refund_id,
        requested_at=refund.requested_at,
        processed_at=refund.processed_at,
        created_at=refund.created_at,
        updated_at=refund.updated_at,
        transactions=txs
    )


def format_replacement_response(replacement: Replacement) -> ReplacementResponse:
    items = [
        ReplacementItemResponse(
            id=i.id,
            replacement_id=i.replacement_id,
            original_order_item_id=i.original_order_item_id,
            product_id=i.product_id,
            variant_id=i.variant_id,
            product_name=i.original_order_item.product_name if i.original_order_item else "Product",
            variant_title=i.original_order_item.variant_title if i.original_order_item else None,
            sku=i.original_order_item.sku if i.original_order_item else "",
            quantity=i.quantity,
            allocated=i.allocated,
            image_url=i.original_order_item.image_url if i.original_order_item else None
        )
        for i in (replacement.items or [])
    ]
    history = [
        ReplacementStatusHistoryResponse(
            id=h.id,
            replacement_id=h.replacement_id,
            old_status=h.old_status,
            new_status=h.new_status,
            changed_by=h.changed_by,
            reason=h.reason,
            created_at=h.created_at
        )
        for h in (replacement.status_history or [])
    ]
    tracking_no = replacement.shipment.tracking_number if replacement.shipment else None
    carrier = replacement.shipment.carrier if replacement.shipment else None
    shipment_status = replacement.shipment.status if replacement.shipment else None

    return ReplacementResponse(
        id=replacement.id,
        replacement_number=replacement.replacement_number,
        return_id=replacement.return_id,
        order_id=replacement.order_id,
        user_id=replacement.user_id,
        shipment_id=replacement.shipment_id,
        status=replacement.status,
        reason=replacement.reason,
        notes=replacement.notes,
        created_at=replacement.created_at,
        updated_at=replacement.updated_at,
        items=items,
        status_history=history,
        tracking_number=tracking_no,
        carrier=carrier,
        shipment_status=shipment_status
    )


def format_return_response(ret: Return) -> ReturnResponse:
    items = [
        ReturnItemResponse(
            id=i.id,
            return_id=i.return_id,
            order_item_id=i.order_item_id,
            product_id=i.product_id,
            variant_id=i.variant_id,
            product_name=i.order_item.product_name if i.order_item else "Product",
            variant_title=i.order_item.variant_title if i.order_item else None,
            sku=i.order_item.sku if i.order_item else "",
            unit_price=i.order_item.unit_price if i.order_item else 0.0,
            quantity=i.quantity,
            reason=i.reason,
            condition=i.condition,
            resolution=i.resolution,
            refund_amount=i.refund_amount,
            restocked=i.restocked,
            restocked_at=i.restocked_at,
            image_url=i.order_item.image_url if i.order_item else None
        )
        for i in (ret.items or [])
    ]
    history = [
        ReturnStatusHistoryResponse(
            id=h.id,
            return_id=h.return_id,
            old_status=h.old_status,
            new_status=h.new_status,
            changed_by=h.changed_by,
            reason=h.reason,
            created_at=h.created_at
        )
        for h in (ret.status_history or [])
    ]

    refund_resp = format_refund_response(ret.refund) if ret.refund else None
    replacement_resp = format_replacement_response(ret.replacement) if ret.replacement else None

    return ReturnResponse(
        id=ret.id,
        return_number=ret.return_number,
        order_id=ret.order_id,
        order_number=ret.order.order_number if ret.order else f"ORD-{ret.order_id}",
        user_id=ret.user_id,
        customer_name=ret.user.full_name if ret.user else None,
        customer_email=ret.user.email if ret.user else None,
        status=ret.status,
        resolution_type=ret.resolution_type,
        reason=ret.reason,
        customer_note=ret.customer_note,
        admin_note=ret.admin_note,
        rejection_reason=ret.rejection_reason,
        inspection_condition=ret.inspection_condition,
        inspection_note=ret.inspection_note,
        inspected_by=ret.inspected_by,
        inspected_at=ret.inspected_at,
        requested_at=ret.requested_at,
        approved_at=ret.approved_at,
        rejected_at=ret.rejected_at,
        received_at=ret.received_at,
        completed_at=ret.completed_at,
        created_at=ret.created_at,
        updated_at=ret.updated_at,
        items=items,
        status_history=history,
        refund=refund_resp,
        replacement=replacement_resp
    )
