from typing import Optional
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session
from app.core.database import get_db

from app.models.user import User

from app.api.v1.endpoints.auth import get_current_user_optional

from app.schemas.common import APIResponse

from app.schemas.cart import(
    CartItemAdd,
    CartItemUpdate,
    CartResponse
)
from app.services.cart_service import (
    get_or_create_cart,
    build_cart_response,
    add_cart_item,
    update_cart_item_quantity,
    remove_cart_item,
    clear_cart
)

router = APIRouter()

@router.get("", response_model=APIResponse[CartResponse])
def get_cart(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Retrieve current customer active cart with authoritative pricing and inventory status.
    Supports authenticated users and guest sessions.
    """
    user_id = current_user.id if current_user else None
    cart = get_or_create_cart(db, user_id=user_id, session_id=x_session_id)
    cart_data = build_cart_response(db, cart)

    return APIResponse(
        success=True,
        message="Active cart retrieved",
        data=cart_data
    )

@router.post("/items", response_model=APIResponse[CartResponse])
def add_item_to_cart(
    payload: CartItemAdd,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Add a product/variant to the active cart with inventory validation.
    """
    user_id = current_user.id if current_user else None
    cart = get_or_create_cart(db, user_id=user_id, session_id=x_session_id)
    updated_cart = add_cart_item(db, cart, payload)

    return APIResponse(
        success=True,
        message="Item added to cart successfully",
        data=updated_cart
    )

@router.put("/items/{item_id}", response_model=APIResponse[CartResponse])
def update_item_quantity(
    item_id: int,
    payload: CartItemUpdate,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Update item quantity in cart with authoritative stock validation.
    """
    user_id = current_user.id if current_user else None
    cart = get_or_create_cart(db, user_id=user_id, session_id=x_session_id)
    updated_cart = update_cart_item_quantity(db, cart, item_id, payload)

    return APIResponse(
        success=True,
        message="Cart item quantity updated",
        data=updated_cart
    )

@router.delete("/items/{item_id}", response_model=APIResponse[CartResponse])
def remove_item(
    item_id: int,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Remove an item from the cart.
    """
    user_id = current_user.id if current_user else None
    cart = get_or_create_cart(db, user_id=user_id, session_id=x_session_id)
    updated_cart = remove_cart_item(db, cart, item_id)

    return APIResponse(
        success=True,
        message="Item removed from cart",
        data=updated_cart
    )

@router.delete("", response_model=APIResponse[CartResponse])
def empty_cart(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Clear all items from the active cart.
    """
    user_id = current_user.id if current_user else None
    cart = get_or_create_cart(db, user_id=user_id, session_id=x_session_id)
    updated_cart = clear_cart(db, cart)

    return APIResponse(
        success=True,
        message="Cart cleared successfully",
        data=updated_cart
    )
