from typing import Optional, List, Tuple
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status
from app.models.order import Cart, CartItem
from app.models.product import Product, ProductVariant, ProductImage
from app.models.category import Category, Brand
from app.services.inventory_service import (
    get_authoritative_product_stock,
    get_authoritative_variant_stock
)
from app.schemas.cart import (
    CartItemAdd,
    CartItemUpdate,
    CartItemResponse,
    CartItemProductInfo,
    CartItemVariantInfo,
    CartResponse
)
from app.services.discount_engine import DiscountEngine

def get_or_create_cart(
    db: Session, 
    user_id: Optional[int] = None, 
    session_id: Optional[str] = None
) -> Cart:
    """
    Retrieve or create the authoritative active cart for a customer or guest session.
    Enforces that a user has only one active cart.
    """
    cart = None
    if user_id:
        cart = (
            db.query(Cart)
            .filter(Cart.user_id == user_id, Cart.status == "active")
            .first()
        )
        if not cart:
            # Check if there is an unattached guest cart with this session_id to merge/claim
            if session_id:
                guest_cart = (
                    db.query(Cart)
                    .filter(Cart.session_id == session_id, Cart.user_id == None, Cart.status == "active")
                    .first()
                )
                if guest_cart:
                    guest_cart.user_id = user_id
                    db.commit()
                    db.refresh(guest_cart)
                    return guest_cart

            cart = Cart(user_id=user_id, status="active")
            db.add(cart)
            db.commit()
            db.refresh(cart)
    elif session_id:
        cart = (
            db.query(Cart)
            .filter(Cart.session_id == session_id, Cart.status == "active")
            .first()
        )
        if not cart:
            cart = Cart(session_id=session_id, status="active")
            db.add(cart)
            db.commit()
            db.refresh(cart)
    else:
        # Fallback guest cart
        cart = Cart(status="active")
        db.add(cart)
        db.commit()
        db.refresh(cart)

    return cart

def get_cart_with_items(db: Session, cart_id: int) -> Cart:
    """Fetch cart with eager-loaded items, product, variant, and images."""
    return (
        db.query(Cart)
        .options(
            joinedload(Cart.items)
            .joinedload(CartItem.product)
            .joinedload(Product.images),
            joinedload(Cart.items)
            .joinedload(CartItem.product)
            .joinedload(Product.category),
            joinedload(Cart.items)
            .joinedload(CartItem.product)
            .joinedload(Product.brand),
            joinedload(Cart.items)
            .joinedload(CartItem.variant)
        )
        .filter(Cart.id == cart_id)
        .first()
    )

def build_cart_response(db: Session, cart: Cart) -> CartResponse:
    """
    Authoritative server-side calculation of cart items, pricing, inventory availability,
    taxes, discounts (including flash sales, catalog offers, and coupons), and order totals.
    """
    reloaded_cart = get_cart_with_items(db, cart.id)
    if not reloaded_cart:
        return CartResponse(
            id=cart.id,
            user_id=cart.user_id,
            session_id=cart.session_id,
            status=cart.status,
            item_count=0,
            items=[],
            subtotal=0.0,
            tax=0.0,
            shipping=0.0,
            discount=0.0,
            total=0.0
        )

    # Prepare items for authoritative DiscountEngine
    valid_items = [it for it in reloaded_cart.items if it.product]
    items_data = [
        {
            "item_id": it.id,
            "product": it.product,
            "variant": it.variant,
            "quantity": it.quantity
        }
        for it in valid_items
    ]

    pricing = DiscountEngine.calculate_pricing(
        db=db,
        items_data=items_data,
        user_id=reloaded_cart.user_id,
        coupon_code=reloaded_cart.coupon_code
    )

    # If the stored coupon is no longer valid, automatically detach it
    if reloaded_cart.coupon_code and pricing.coupon_error:
        reloaded_cart.coupon_code = None
        reloaded_cart.applied_coupon_id = None
        db.commit()

    response_items: List[CartItemResponse] = []
    total_items_count = 0

    for idx, item in enumerate(valid_items):
        product = item.product
        variant = item.variant
        calc_item = pricing.items[idx]

        # Primary or first image
        image_url = None
        if variant and variant.image_url:
            image_url = variant.image_url
        elif product.images:
            primary_imgs = [img.image_url for img in product.images if img.is_primary]
            if primary_imgs:
                image_url = primary_imgs[0]
            else:
                sorted_imgs = sorted(product.images, key=lambda x: (x.sort_order, x.id))
                image_url = sorted_imgs[0].image_url if sorted_imgs else None

        if not image_url:
            image_url = "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&q=80"

        # Authoritative inventory check
        if variant:
            available_qty, _ = get_authoritative_variant_stock(db, variant.id)
        else:
            available_qty, _ = get_authoritative_product_stock(db, product.id)

        in_stock = (available_qty >= item.quantity) and product.is_active and (variant.is_active if variant else True)
        total_items_count += item.quantity

        prod_info = CartItemProductInfo(
            id=product.id,
            name=product.name,
            slug=product.slug,
            sku=product.sku,
            brand_name=product.brand.name if product.brand else None,
            category_name=product.category.name if product.category else None,
            is_active=product.is_active,
            status=product.status
        )

        var_info = None
        if variant:
            var_info = CartItemVariantInfo(
                id=variant.id,
                title=variant.title,
                sku=variant.sku,
                attributes=variant.attributes or {},
                is_active=variant.is_active
            )

        response_items.append(
            CartItemResponse(
                id=item.id,
                cart_id=item.cart_id,
                product_id=product.id,
                product=prod_info,
                variant_id=variant.id if variant else None,
                variant=var_info,
                image=image_url,
                quantity=item.quantity,
                unit_price=calc_item.selling_price,
                mrp=calc_item.mrp,
                discount=round(calc_item.flash_sale_discount + calc_item.offer_discount + calc_item.coupon_discount, 2),
                line_subtotal=calc_item.line_subtotal,
                available_quantity=available_qty,
                in_stock=in_stock,
                price_changed=False,
                offer_discount=calc_item.offer_discount,
                flash_sale_discount=calc_item.flash_sale_discount,
                coupon_discount=calc_item.coupon_discount,
                final_price=calc_item.final_unit_price,
                applied_offer_title=calc_item.applied_offer_title,
                is_flash_sale=calc_item.is_flash_sale,
                created_at=item.created_at,
                updated_at=item.updated_at
            )
        )

    return CartResponse(
        id=reloaded_cart.id,
        user_id=reloaded_cart.user_id,
        session_id=reloaded_cart.session_id,
        status=reloaded_cart.status,
        item_count=total_items_count,
        items=response_items,
        subtotal=pricing.subtotal,
        tax=pricing.tax,
        shipping=pricing.shipping,
        discount=pricing.total_promotional_discount,
        coupon_code=pricing.coupon_code,
        coupon_discount=pricing.coupon_discount,
        offer_discount=pricing.offer_discount,
        flash_sale_discount=pricing.flash_sale_discount,
        applied_coupon=pricing.applied_coupon_details,
        total=pricing.total
    )

def apply_cart_coupon(db: Session, cart: Cart, coupon_code: str) -> CartResponse:
    """
    Validate and apply a coupon to the customer's active cart.
    Raises HTTPException if coupon is invalid or cart requirements are not met.
    """
    reloaded_cart = get_cart_with_items(db, cart.id)
    if not reloaded_cart or not reloaded_cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot apply coupon to an empty cart"
        )

    items_data = [
        {
            "item_id": it.id,
            "product": it.product,
            "variant": it.variant,
            "quantity": it.quantity
        }
        for it in reloaded_cart.items
        if it.product
    ]

    pricing = DiscountEngine.calculate_pricing(
        db=db,
        items_data=items_data,
        user_id=reloaded_cart.user_id,
        coupon_code=coupon_code
    )

    if pricing.coupon_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=pricing.coupon_error
        )

    cart.coupon_code = pricing.coupon_code
    cart.applied_coupon_id = pricing.coupon_id
    db.commit()
    db.refresh(cart)
    return build_cart_response(db, cart)

def remove_cart_coupon(db: Session, cart: Cart) -> CartResponse:
    """Detach any applied coupon from the customer's cart."""
    cart.coupon_code = None
    cart.applied_coupon_id = None
    db.commit()
    db.refresh(cart)
    return build_cart_response(db, cart)

def add_cart_item(db: Session, cart: Cart, payload: CartItemAdd) -> CartResponse:
    """
    Validate product, variant, stock availability, and add or merge item in active cart.
    """
    # 1. Product validation
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product or not product.is_active or product.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product is currently unavailable or inactive"
        )

    # 2. Variant validation
    variant = None
    if payload.variant_id is not None:
        variant = db.query(ProductVariant).filter(ProductVariant.id == payload.variant_id).first()
        if not variant or not variant.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected product variant is unavailable or inactive"
            )
        if variant.product_id != product.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected variant does not belong to this product"
            )

    # 3. Stock validation
    if variant:
        available_qty, _ = get_authoritative_variant_stock(db, variant.id)
    else:
        available_qty, _ = get_authoritative_product_stock(db, product.id)

    if available_qty < payload.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient stock available. Only {available_qty} units available."
        )

    # 4. Check existing item in cart
    existing_item = (
        db.query(CartItem)
        .filter(
            CartItem.cart_id == cart.id,
            CartItem.product_id == payload.product_id,
            CartItem.variant_id == payload.variant_id
        )
        .first()
    )

    if existing_item:
        merged_qty = existing_item.quantity + payload.quantity
        if merged_qty > available_qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot add {payload.quantity} more. Current cart has {existing_item.quantity}, but only {available_qty} total are available in stock."
            )
        if merged_qty > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum allowable quantity per cart item is 50 units."
            )
        existing_item.quantity = merged_qty
    else:
        new_item = CartItem(
            cart_id=cart.id,
            product_id=payload.product_id,
            variant_id=payload.variant_id,
            quantity=payload.quantity
        )
        db.add(new_item)

    db.commit()
    return build_cart_response(db, cart)

def update_cart_item_quantity(
    db: Session, 
    cart: Cart, 
    item_id: int, 
    payload: CartItemUpdate
) -> CartResponse:
    """
    Update item quantity with authoritative stock validation.
    """
    item = (
        db.query(CartItem)
        .filter(CartItem.id == item_id, CartItem.cart_id == cart.id)
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cart item #{item_id} not found in this cart"
        )

    new_qty = payload.quantity
    if new_qty <= 0:
        db.delete(item)
        db.commit()
        return build_cart_response(db, cart)

    # Authoritative stock check
    if item.variant_id:
        available_qty, _ = get_authoritative_variant_stock(db, item.variant_id)
    else:
        available_qty, _ = get_authoritative_product_stock(db, item.product_id)

    if new_qty > available_qty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Requested quantity ({new_qty}) exceeds available stock ({available_qty})."
        )

    item.quantity = new_qty
    db.commit()
    return build_cart_response(db, cart)

def remove_cart_item(db: Session, cart: Cart, item_id: int) -> CartResponse:
    """Remove an item from the cart."""
    item = (
        db.query(CartItem)
        .filter(CartItem.id == item_id, CartItem.cart_id == cart.id)
        .first()
    )
    if item:
        db.delete(item)
        db.commit()
    return build_cart_response(db, cart)

def clear_cart(db: Session, cart: Cart) -> CartResponse:
    """Remove all items from the cart."""
    db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
    db.commit()
    return build_cart_response(db, cart)
