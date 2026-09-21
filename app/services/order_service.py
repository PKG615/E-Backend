import json
import secrets
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, or_
from fastapi import HTTPException, status

from app.models.user import User, Address
from app.models.order import (
    Cart, CartItem, Order, OrderItem, OrderStatusHistory, Payment, PaymentTransaction
)
from app.models.product import Product, ProductVariant
from app.models.inventory import Inventory, InventoryTransaction
from app.schemas.order import OrderCreateRequest, OrderResponse, OrderItemResponse, OrderStatusHistoryResponse, OrderPaymentSummary

ALLOWED_TRANSITIONS = {
    "pending": ["confirmed", "cancelled"],
    "confirmed": ["processing", "cancelled"],
    "processing": ["shipped", "cancelled"],
    "shipped": ["delivered", "cancelled"],
    "delivered": [],
    "cancelled": []
}

def generate_order_number() -> str:
    date_str = datetime.utcnow().strftime("%Y%m%d")
    suffix = secrets.token_hex(3).upper()
    return f"ORD-{date_str}-{suffix}"

def create_order_from_cart(db: Session, user: User, data: OrderCreateRequest) -> Order:
    """
    Authoritatively creates an order from the user's active cart.
    Validates delivery address, stock levels, applies row locking,
    calculates pricing/taxes, deducts inventory, records ledger transactions,
    snapshots items and address, creates status history and payment records,
    and clears the customer cart.
    """
    # 1. Idempotency Check
    if data.idempotency_key:
        existing_order = (
            db.query(Order)
            .filter(Order.idempotency_key == data.idempotency_key, Order.user_id == user.id)
            .first()
        )
        if existing_order:
            return existing_order

    # 2. Address Validation & Historical Snapshot
    address = (
        db.query(Address)
        .filter(Address.id == data.address_id, Address.user_id == user.id)
        .first()
    )
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery address not found or does not belong to the user"
        )

    address_snapshot = {
        "full_name": address.full_name,
        "phone": address.phone,
        "address_line1": address.address_line1,
        "address_line2": address.address_line2,
        "landmark": address.landmark,
        "city": address.city,
        "state": address.state,
        "postal_code": address.postal_code,
        "country": address.country,
        "address_type": address.address_type
    }

    # 3. Active Cart Validation
    cart = (
        db.query(Cart)
        .options(joinedload(Cart.items))
        .filter(Cart.user_id == user.id, Cart.status == "active")
        .first()
    )
    if not cart or not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot place order: your cart is empty"
        )

    # 4. Item-by-item verification, stock check with lock, pricing calculations
    calculated_items = []
    subtotal = 0.0
    total_discount = 0.0

    for cart_item in cart.items:
        product = db.query(Product).filter(Product.id == cart_item.product_id).first()
        if not product or not product.is_active or product.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product '{cart_item.product_id}' is no longer active or available"
            )

        variant = None
        if cart_item.variant_id:
            variant = (
                db.query(ProductVariant)
                .filter(ProductVariant.id == cart_item.variant_id, ProductVariant.product_id == product.id)
                .first()
            )
            if not variant or not variant.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Selected product variant for '{product.name}' is no longer available"
                )

        # Inventory check with row lock
        if cart_item.variant_id:
            inv_query = db.query(Inventory).filter(
                Inventory.product_id == product.id,
                Inventory.variant_id == cart_item.variant_id
            )
        else:
            inv_query = db.query(Inventory).filter(
                Inventory.product_id == product.id,
                Inventory.variant_id.is_(None)
            )

        try:
            inv = inv_query.with_for_update().first()
        except Exception:
            inv = inv_query.first()

        if not inv:
            # Auto-provision initial inventory row from product stock
            inv = Inventory(
                product_id=product.id,
                variant_id=cart_item.variant_id,
                sku=variant.sku if (variant and variant.sku) else product.sku,
                on_hand_quantity=product.stock or 0,
                reserved_quantity=0,
                available_quantity=product.stock or 0,
                is_active=True
            )
            db.add(inv)
            db.flush()

        available_qty = inv.available_quantity
        if available_qty < cart_item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for '{product.name}'. Available: {available_qty}, Requested: {cart_item.quantity}"
            )

        # Authoritative pricing
        unit_price = float(variant.price if (variant and variant.price is not None) else product.price)
        mrp = float((variant.mrp if (variant and variant.mrp) else product.mrp) or unit_price)
        item_discount = max(0.0, mrp - unit_price)
        line_total = round(unit_price * cart_item.quantity, 2)
        item_tax = round(line_total - (line_total / 1.18), 2)

        subtotal += line_total
        total_discount += round(item_discount * cart_item.quantity, 2)

        # Image thumbnail selection
        image_url = None
        if product.images:
            primary_img = next((img.image_url for img in product.images if img.is_primary), None)
            image_url = primary_img or (product.images[0].image_url if product.images else None)
        if not image_url and product.thumbnail_url:
            image_url = product.thumbnail_url

        calculated_items.append({
            "product_id": product.id,
            "variant_id": variant.id if variant else None,
            "product_name": product.name,
            "variant_title": variant.title if variant else None,
            "sku": variant.sku if (variant and variant.sku) else product.sku,
            "unit_price": unit_price,
            "mrp": mrp,
            "discount_amount": item_discount,
            "tax_amount": item_tax,
            "quantity": cart_item.quantity,
            "total_price": line_total,
            "line_total": line_total,
            "image_url": image_url,
            "inventory_obj": inv
        })

    # Order level totals
    subtotal = round(subtotal, 2)
    tax_amount = round(subtotal - (subtotal / 1.18), 2)
    shipping_amount = 0.0 if subtotal >= 999.0 else 99.0
    total_amount = round(subtotal + shipping_amount, 2)

    # 5. Determine order status & payment status
    method = (data.payment_method or "card").lower()
    if method == "cod":
        initial_order_status = "confirmed"
        initial_payment_status = "pending"
    else:
        initial_order_status = "confirmed"
        initial_payment_status = "paid"

    # Generate unique order number
    order_number = generate_order_number()
    while db.query(Order).filter(Order.order_number == order_number).first():
        order_number = generate_order_number()

    # 6. Create Order record
    order = Order(
        order_number=order_number,
        user_id=user.id,
        address_id=address.id,
        status=initial_order_status,
        payment_status=initial_payment_status,
        payment_method=method,
        payment_provider=data.payment_provider or "standard",
        currency="INR",
        subtotal=subtotal,
        tax_amount=tax_amount,
        shipping_amount=shipping_amount,
        discount_amount=round(total_discount, 2),
        total_amount=total_amount,
        shipping_address_json=json.dumps(address_snapshot),
        notes=data.notes,
        idempotency_key=data.idempotency_key,
        placed_at=datetime.utcnow()
    )
    db.add(order)
    db.flush()

    # 7. Create OrderItems and Deduct Inventory
    for calc in calculated_items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=calc["product_id"],
            variant_id=calc["variant_id"],
            product_name=calc["product_name"],
            variant_title=calc["variant_title"],
            sku=calc["sku"],
            unit_price=calc["unit_price"],
            mrp=calc["mrp"],
            discount_amount=calc["discount_amount"],
            tax_amount=calc["tax_amount"],
            quantity=calc["quantity"],
            total_price=calc["total_price"],
            line_total=calc["line_total"],
            image_url=calc["image_url"]
        )
        db.add(order_item)

        # Deduct inventory stock
        inv = calc["inventory_obj"]
        qty_before = inv.on_hand_quantity
        inv.on_hand_quantity -= calc["quantity"]
        inv.available_quantity = max(0, inv.on_hand_quantity - inv.reserved_quantity)
        qty_after = inv.on_hand_quantity

        # Synchronize Product.stock
        prod_obj = db.query(Product).filter(Product.id == calc["product_id"]).first()
        if prod_obj:
            prod_obj.stock = max(0, prod_obj.stock - calc["quantity"])

        # Ledger record
        tx = InventoryTransaction(
            inventory_id=inv.id,
            transaction_type="ADJUSTMENT",
            quantity_change=-calc["quantity"],
            quantity_before=qty_before,
            quantity_after=qty_after,
            reference_type="order",
            reference_id=order.order_number,
            reason=f"Order {order.order_number} checkout placement",
            created_by=user.email or f"customer_{user.id}"
        )
        db.add(tx)

    # 8. Create Status History
    history_initial = OrderStatusHistory(
        order_id=order.id,
        old_status=None,
        new_status=initial_order_status,
        changed_by=user.email or f"customer_{user.id}",
        reason="Order placed and verified by customer"
    )
    db.add(history_initial)

    # 9. Payment Record
    if initial_payment_status == "paid":
        pay_id = f"PAY_{secrets.token_hex(6).upper()}"
        txn_id = f"TXN_{secrets.token_hex(8).upper()}"
        payment = Payment(
            order_id=order.id,
            user_id=user.id,
            provider=data.payment_provider or "standard",
            method=method,
            amount=total_amount,
            currency="INR",
            status="paid",
            provider_payment_id=pay_id,
            idempotency_key=data.idempotency_key
        )
        db.add(payment)
        db.flush()

        txn = PaymentTransaction(
            payment_id=payment.id,
            transaction_type="charge",
            provider_transaction_id=txn_id,
            amount=total_amount,
            status="success",
            response_reference=f"Payment captured via {method.upper()}"
        )
        db.add(txn)

        history_payment = OrderStatusHistory(
            order_id=order.id,
            old_status="pending_payment",
            new_status="paid",
            changed_by="payment_gateway",
            reason=f"Payment of ₹{total_amount:.2f} received via {method.upper()}"
        )
        db.add(history_payment)
    else:
        # COD pending payment
        payment = Payment(
            order_id=order.id,
            user_id=user.id,
            provider=data.payment_provider or "standard",
            method="cod",
            amount=total_amount,
            currency="INR",
            status="pending",
            provider_payment_id=f"COD_{secrets.token_hex(6).upper()}",
            idempotency_key=data.idempotency_key
        )
        db.add(payment)

    # 10. Clear Customer Cart
    db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
    
    db.commit()
    db.refresh(order)
    return order

def get_order_by_id(db: Session, order_id: int, user_id: Optional[int] = None) -> Order:
    query = (
        db.query(Order)
        .options(
            joinedload(Order.user),
            joinedload(Order.items),
            joinedload(Order.status_history),
            joinedload(Order.payments).joinedload(Payment.transactions)
        )
        .filter(Order.id == order_id)
    )
    if user_id is not None:
        query = query.filter(Order.user_id == user_id)
    order = query.first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order

def list_customer_orders(
    db: Session, 
    user_id: int, 
    page: int = 1, 
    page_size: int = 20
) -> Tuple[List[Order], int]:
    query = (
        db.query(Order)
        .options(
            joinedload(Order.items),
            joinedload(Order.status_history),
            joinedload(Order.payments)
        )
        .filter(Order.user_id == user_id)
        .order_by(desc(Order.created_at))
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total

def list_admin_orders(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    payment_status: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Tuple[List[Order], int]:
    query = (
        db.query(Order)
        .join(Order.user)
        .options(
            joinedload(Order.user),
            joinedload(Order.items),
            joinedload(Order.status_history),
            joinedload(Order.payments)
        )
    )

    if status_filter:
        query = query.filter(Order.status == status_filter)
    if payment_status:
        query = query.filter(Order.payment_status == payment_status)
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Order.order_number.ilike(search_fmt),
                User.email.ilike(search_fmt),
                User.full_name.ilike(search_fmt)
            )
        )
    if start_date:
        query = query.filter(Order.created_at >= start_date)
    if end_date:
        query = query.filter(Order.created_at <= end_date)

    total = query.count()
    items = query.order_by(desc(Order.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    return items, total

def update_order_status(
    db: Session,
    order_id: int,
    new_status: str,
    admin_user: User,
    reason: Optional[str] = None,
    notes: Optional[str] = None
) -> Order:
    order = get_order_by_id(db, order_id=order_id)
    
    current_status = order.status
    if new_status == current_status:
        return order

    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid order status transition from '{current_status}' to '{new_status}'. Allowed transitions: {allowed}"
        )

    # Handle Cancellation -> Restore Inventory
    if new_status == "cancelled" and current_status in ["confirmed", "processing", "shipped"]:
        for item in order.items:
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
            if inv:
                qty_before = inv.on_hand_quantity
                inv.on_hand_quantity += item.quantity
                inv.available_quantity = max(0, inv.on_hand_quantity - inv.reserved_quantity)
                qty_after = inv.on_hand_quantity

                prod = db.query(Product).filter(Product.id == item.product_id).first()
                if prod:
                    prod.stock += item.quantity

                tx = InventoryTransaction(
                    inventory_id=inv.id,
                    transaction_type="RELEASE",
                    quantity_change=item.quantity,
                    quantity_before=qty_before,
                    quantity_after=qty_after,
                    reference_type="order_cancellation",
                    reference_id=order.order_number,
                    reason=f"Order {order.order_number} cancelled: {reason or 'Admin cancellation'}",
                    created_by=admin_user.email or f"admin_{admin_user.id}"
                )
                db.add(tx)

    # Handle Delivery -> mark payment paid if COD
    if new_status == "delivered" and order.payment_method == "cod" and order.payment_status != "paid":
        order.payment_status = "paid"
        for p in order.payments:
            if p.status != "paid":
                p.status = "paid"

    old_status = order.status
    order.status = new_status
    if notes:
        order.notes = (order.notes + "\n" if order.notes else "") + f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {notes}"

    # Status history entry
    history = OrderStatusHistory(
        order_id=order.id,
        old_status=old_status,
        new_status=new_status,
        changed_by=admin_user.email or f"admin_{admin_user.id}",
        reason=reason or f"Status updated by admin to {new_status}"
    )
    db.add(history)

    db.commit()
    db.refresh(order)
    return order

def format_order_response(order: Order) -> OrderResponse:
    try:
        shipping_addr = json.loads(order.shipping_address_json) if order.shipping_address_json else {}
    except Exception:
        shipping_addr = {}

    items_resp = [
        OrderItemResponse(
            id=item.id,
            order_id=item.order_id,
            product_id=item.product_id,
            variant_id=item.variant_id,
            product_name=item.product_name,
            variant_title=item.variant_title,
            sku=item.sku,
            unit_price=item.unit_price,
            mrp=item.mrp or item.unit_price,
            discount_amount=item.discount_amount or 0.0,
            tax_amount=item.tax_amount or 0.0,
            quantity=item.quantity,
            total_price=item.total_price,
            line_total=item.line_total or item.total_price,
            image_url=item.image_url
        )
        for item in (order.items or [])
    ]

    history_resp = [
        OrderStatusHistoryResponse(
            id=h.id,
            order_id=h.order_id,
            old_status=h.old_status,
            new_status=h.new_status,
            changed_by=h.changed_by,
            reason=h.reason,
            created_at=h.created_at
        )
        for h in (order.status_history or [])
    ]

    payments_resp = [
        OrderPaymentSummary(
            id=p.id,
            provider=p.provider,
            method=p.method,
            amount=p.amount,
            currency=p.currency,
            status=p.status,
            provider_payment_id=p.provider_payment_id,
            created_at=p.created_at
        )
        for p in (order.payments or [])
    ]

    customer_name = order.user.full_name if order.user else shipping_addr.get("full_name")
    customer_email = order.user.email if order.user else None

    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        user_id=order.user_id,
        customer_name=customer_name,
        customer_email=customer_email,
        address_id=order.address_id,
        status=order.status,
        payment_status=order.payment_status,
        payment_method=order.payment_method,
        payment_provider=order.payment_provider,
        currency=order.currency or "INR",
        subtotal=order.subtotal,
        tax_amount=order.tax_amount,
        shipping_amount=order.shipping_amount,
        discount_amount=order.discount_amount,
        total_amount=order.total_amount,
        shipping_address=shipping_addr,
        notes=order.notes,
        placed_at=order.placed_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=items_resp,
        status_history=history_resp,
        payments=payments_resp
    )
