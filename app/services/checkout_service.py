from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User, Address
from app.models.order import Cart
from app.services.cart_service import get_or_create_cart, build_cart_response
from app.schemas.address import AddressResponse
from app.schemas.checkout import CheckoutPreviewResponse

def preview_checkout(
    db: Session, 
    user: User, 
    address_id: int
) -> CheckoutPreviewResponse:
    """
    Simulate and validate customer checkout with authoritative pricing,
    inventory availability, address ownership, and delivery rules.
    Does NOT modify stock or create an order.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Validate Address
    address = (
        db.query(Address)
        .filter(Address.id == address_id, Address.user_id == user.id)
        .first()
    )
    if not address:
        errors.append("Selected delivery address was not found or does not belong to your account.")
        address_resp = None
    else:
        address_resp = AddressResponse.from_orm(address)

    # 2. Validate Cart
    cart = get_or_create_cart(db, user_id=user.id)
    cart_resp = build_cart_response(db, cart)

    if not cart_resp.items:
        errors.append("Your shopping cart is empty. Please add items before proceeding to checkout.")

    # 3. Item-by-item stock and status verification
    for item in cart_resp.items:
        if not item.product.is_active or item.product.status != "active":
            errors.append(f"'{item.product.name}' is no longer active or available.")
            continue

        if item.variant and not item.variant.is_active:
            errors.append(f"Variant '{item.variant.title}' for '{item.product.name}' is no longer active.")
            continue

        if item.available_quantity <= 0:
            errors.append(f"'{item.product.name}' is currently out of stock.")
        elif item.available_quantity < item.quantity:
            errors.append(
                f"Insufficient stock for '{item.product.name}': only {item.available_quantity} available, but {item.quantity} are in your cart."
            )

        if item.available_quantity <= 3 and item.available_quantity >= item.quantity:
            warnings.append(f"Hurry! Only {item.available_quantity} units left of '{item.product.name}'.")

    is_valid = (len(errors) == 0) and (len(cart_resp.items) > 0) and (address_resp is not None)

    return CheckoutPreviewResponse(
        valid=is_valid,
        items=cart_resp.items,
        subtotal=cart_resp.subtotal,
        tax=cart_resp.tax,
        shipping=cart_resp.shipping,
        discount=cart_resp.discount,
        coupon_code=cart_resp.coupon_code,
        coupon_discount=cart_resp.coupon_discount,
        offer_discount=cart_resp.offer_discount,
        flash_sale_discount=cart_resp.flash_sale_discount,
        applied_coupon=cart_resp.applied_coupon,
        total=cart_resp.total,
        address=address_resp,
        warnings=warnings,
        errors=errors
    )
