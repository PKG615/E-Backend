from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db

from app.models.user import User

from app.models.product import Product

from app.models.wishlist import WishlistItem, CompareItem

from app.api.v1.endpoints.auth import get_current_user, get_current_user_optional

from app.api.v1.endpoints.products import format_product_response

from app.schemas.common import APIResponse

from app.schemas.wishlist import(
    WishlistAddRequest,
    WishlistItemResponse,
    WishlistResponse,
    WishlistCheckResponse,
    CompareAddRequest,
    CompareItemResponse,
    CompareResponse
)

router = APIRouter()

# ==========================================
# WISHLIST ENDPOINTS (AUTHENTICATED CUSTOMER)
# ==========================================

@router.get("/wishlist", response_model=APIResponse[WishlistResponse])
def get_my_wishlist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get customer wishlist items with real product details from PostgreSQL.
    """
    items = (
        db.query(WishlistItem)
        .options(
            joinedload(WishlistItem.product).joinedload(Product.category),
            joinedload(WishlistItem.product).joinedload(Product.brand),
            joinedload(WishlistItem.product).joinedload(Product.images),
            joinedload(WishlistItem.product).joinedload(Product.variants),
        )
        .filter(WishlistItem.user_id == current_user.id)
        .order_by(WishlistItem.created_at.desc())
        .all()
    )

    result_items = []
    for item in items:
        if item.product and item.product.is_active:
            result_items.append(
                WishlistItemResponse(
                    id=item.id,
                    user_id=item.user_id,
                    product_id=item.product_id,
                    variant_id=item.variant_id,
                    created_at=item.created_at,
                    product=format_product_response(item.product)
                )
            )

    return APIResponse(
        success=True,
        message=f"Retrieved {len(result_items)} wishlist items",
        data=WishlistResponse(
            items=result_items,
            total_count=len(result_items)
        )
    )

@router.post("/wishlist/items", response_model=APIResponse[WishlistItemResponse])
def add_to_wishlist(
    payload: WishlistAddRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a product to the customer's wishlist.
    """
    product = (
        db.query(Product)
        .options(
            joinedload(Product.category),
            joinedload(Product.brand),
            joinedload(Product.images),
            joinedload(Product.variants)
        )
        .filter(Product.id == payload.product_id)
        .first()
    )
    if not product or not product.is_active or product.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or currently unavailable"
        )

    existing = (
        db.query(WishlistItem)
        .filter(
            WishlistItem.user_id == current_user.id,
            WishlistItem.product_id == payload.product_id
        )
        .first()
    )
    if existing:
        if payload.variant_id and existing.variant_id != payload.variant_id:
            existing.variant_id = payload.variant_id
            db.commit()
            db.refresh(existing)
        return APIResponse(
            success=True,
            message="Product already in wishlist",
            data=WishlistItemResponse(
                id=existing.id,
                user_id=existing.user_id,
                product_id=existing.product_id,
                variant_id=existing.variant_id,
                created_at=existing.created_at,
                product=format_product_response(product)
            )
        )

    new_item = WishlistItem(
        user_id=current_user.id,
        product_id=payload.product_id,
        variant_id=payload.variant_id
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    return APIResponse(
        success=True,
        message="Product added to wishlist",
        data=WishlistItemResponse(
            id=new_item.id,
            user_id=new_item.user_id,
            product_id=new_item.product_id,
            variant_id=new_item.variant_id,
            created_at=new_item.created_at,
            product=format_product_response(product)
        )
    )

@router.delete("/wishlist/items/{product_id}", response_model=APIResponse[dict])
def remove_from_wishlist(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remove a product from the customer's wishlist.
    """
    item = (
        db.query(WishlistItem)
        .filter(
            WishlistItem.user_id == current_user.id,
            WishlistItem.product_id == product_id
        )
        .first()
    )
    if not item:
        # Idempotent response
        return APIResponse(
            success=True,
            message="Product not found in wishlist or already removed",
            data={"product_id": product_id, "removed": False}
        )

    db.delete(item)
    db.commit()

    return APIResponse(
        success=True,
        message="Product removed from wishlist",
        data={"product_id": product_id, "removed": True}
    )

@router.get("/wishlist/check/{product_id}", response_model=APIResponse[WishlistCheckResponse])
def check_wishlist_status(
    product_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Check whether a product is currently in the customer's wishlist.
    """
    if not current_user:
        return APIResponse(
            success=True,
            message="Guest user - not in wishlist",
            data=WishlistCheckResponse(product_id=product_id, in_wishlist=False)
        )

    existing = (
        db.query(WishlistItem)
        .filter(
            WishlistItem.user_id == current_user.id,
            WishlistItem.product_id == product_id
        )
        .first()
    )

    return APIResponse(
        success=True,
        message="Wishlist status verified",
        data=WishlistCheckResponse(product_id=product_id, in_wishlist=existing is not None)
    )


# ==========================================
# PRODUCT COMPARE ENDPOINTS
# ==========================================

@router.get("/compare", response_model=APIResponse[CompareResponse])
def get_compare_list(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Retrieve products in customer compare list.
    Supports authenticated users and guest sessions.
    """
    query = (
        db.query(CompareItem)
        .options(
            joinedload(CompareItem.product).joinedload(Product.category),
            joinedload(CompareItem.product).joinedload(Product.brand),
            joinedload(CompareItem.product).joinedload(Product.images),
            joinedload(CompareItem.product).joinedload(Product.variants),
        )
    )
    if current_user:
        items = query.filter(CompareItem.user_id == current_user.id).order_by(CompareItem.created_at.asc()).all()
    elif x_session_id:
        items = query.filter(CompareItem.session_id == x_session_id).order_by(CompareItem.created_at.asc()).all()
    else:
        items = []

    result_items = []
    for item in items:
        if item.product and item.product.is_active:
            result_items.append(
                CompareItemResponse(
                    id=item.id,
                    product_id=item.product_id,
                    created_at=item.created_at,
                    product=format_product_response(item.product)
                )
            )

    return APIResponse(
        success=True,
        message=f"Retrieved {len(result_items)} products for comparison",
        data=CompareResponse(
            items=result_items,
            total_count=len(result_items)
        )
    )

@router.post("/compare/items", response_model=APIResponse[CompareItemResponse])
def add_to_compare(
    payload: CompareAddRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Add a product to comparison list (limit 4 products).
    """
    product = (
        db.query(Product)
        .options(
            joinedload(Product.category),
            joinedload(Product.brand),
            joinedload(Product.images),
            joinedload(Product.variants)
        )
        .filter(Product.id == payload.product_id)
        .first()
    )
    if not product or not product.is_active or product.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or currently unavailable"
        )

    user_id = current_user.id if current_user else None
    sess_id = x_session_id or ("guest_" + str(current_user.id if current_user else "default"))

    # Check if already present
    if user_id:
        existing = db.query(CompareItem).filter(CompareItem.user_id == user_id, CompareItem.product_id == payload.product_id).first()
        count = db.query(CompareItem).filter(CompareItem.user_id == user_id).count()
    else:
        existing = db.query(CompareItem).filter(CompareItem.session_id == sess_id, CompareItem.product_id == payload.product_id).first()
        count = db.query(CompareItem).filter(CompareItem.session_id == sess_id).count()

    if existing:
        return APIResponse(
            success=True,
            message="Product already in compare list",
            data=CompareItemResponse(
                id=existing.id,
                product_id=existing.product_id,
                created_at=existing.created_at,
                product=format_product_response(product)
            )
        )

    if count >= 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum of 4 products can be compared simultaneously. Remove one before adding another."
        )

    new_item = CompareItem(
        user_id=user_id,
        session_id=sess_id if not user_id else None,
        product_id=payload.product_id
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    return APIResponse(
        success=True,
        message="Product added to compare list",
        data=CompareItemResponse(
            id=new_item.id,
            product_id=new_item.product_id,
            created_at=new_item.created_at,
            product=format_product_response(product)
        )
    )

@router.delete("/compare/items/{product_id}", response_model=APIResponse[dict])
def remove_from_compare(
    product_id: int,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Remove product from compare list.
    """
    if current_user:
        item = db.query(CompareItem).filter(CompareItem.user_id == current_user.id, CompareItem.product_id == product_id).first()
    elif x_session_id:
        item = db.query(CompareItem).filter(CompareItem.session_id == x_session_id, CompareItem.product_id == product_id).first()
    else:
        item = None

    if item:
        db.delete(item)
        db.commit()

    return APIResponse(
        success=True,
        message="Product removed from compare list",
        data={"product_id": product_id, "removed": True}
    )

@router.delete("/compare", response_model=APIResponse[dict])
def clear_compare_list(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Clear all products from compare list.
    """
    if current_user:
        deleted = db.query(CompareItem).filter(CompareItem.user_id == current_user.id).delete()
    elif x_session_id:
        deleted = db.query(CompareItem).filter(CompareItem.session_id == x_session_id).delete()
    else:
        deleted = 0
    db.commit()

    return APIResponse(
        success=True,
        message="Compare list cleared",
        data={"cleared_count": deleted}
    )
