from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.models.promotions import (
    Coupon, CouponProduct, CouponCategory, CouponBrand, CouponExclusion, CouponUsage,
    Offer, OfferProduct, OfferCategory, OfferBrand,
    FlashSale, FlashSaleItem
)
from app.models.product import Product, ProductVariant
from app.models.order import Cart, CartItem

@dataclass
class CalculatedItemPrice:
    item_id: Optional[int]
    product_id: int
    variant_id: Optional[int]
    quantity: int
    mrp: float
    selling_price: float # Base unit price before discounts
    flash_sale_discount: float = 0.0
    offer_discount: float = 0.0
    coupon_discount: float = 0.0
    final_unit_price: float = 0.0
    line_subtotal: float = 0.0 # selling_price * qty
    final_line_total: float = 0.0 # final_unit_price * qty
    tax_amount: float = 0.0
    is_flash_sale: bool = False
    applied_offer_title: Optional[str] = None
    applied_flash_sale_id: Optional[int] = None

@dataclass
class DiscountCalculationResult:
    items: List[CalculatedItemPrice] = field(default_factory=list)
    subtotal: float = 0.0 # Base items selling price total
    flash_sale_discount: float = 0.0
    offer_discount: float = 0.0
    coupon_discount: float = 0.0
    total_promotional_discount: float = 0.0
    mrp_savings: float = 0.0
    tax: float = 0.0
    shipping: float = 0.0
    total: float = 0.0
    coupon_code: Optional[str] = None
    coupon_id: Optional[int] = None
    applied_coupon_details: Optional[Dict[str, Any]] = None
    coupon_error: Optional[str] = None
    coupon_error_code: Optional[str] = None


class DiscountEngine:
    @staticmethod
    def get_active_flash_sales(db: Session, now: Optional[datetime] = None) -> List[FlashSale]:
        if not now:
            now = datetime.utcnow()
        return (
            db.query(FlashSale)
            .filter(
                FlashSale.is_active == True,
                FlashSale.starts_at <= now,
                FlashSale.ends_at >= now
            )
            .order_by(FlashSale.priority.desc(), FlashSale.created_at.desc())
            .all()
        )

    @staticmethod
    def get_active_offers(db: Session, now: Optional[datetime] = None) -> List[Offer]:
        if not now:
            now = datetime.utcnow()
        return (
            db.query(Offer)
            .filter(
                Offer.is_active == True,
                or_(Offer.starts_at.is_(None), Offer.starts_at <= now),
                or_(Offer.expires_at.is_(None), Offer.expires_at >= now)
            )
            .order_by(Offer.priority.desc(), Offer.created_at.desc())
            .all()
        )

    @staticmethod
    def validate_coupon(
        db: Session,
        coupon_code: str,
        user_id: Optional[int] = None,
        cart_subtotal: float = 0.0,
        now: Optional[datetime] = None
    ) -> Tuple[Optional[Coupon], Optional[str], Optional[str]]:
        """
        Validate coupon existence, active status, date range, global limit,
        and per-customer limit. Returns (coupon, error_message, error_code).
        """
        if not coupon_code:
            return None, "Coupon code is required", "COUPON_REQUIRED"

        normalized_code = coupon_code.strip().upper()
        if not now:
            now = datetime.utcnow()

        coupon = db.query(Coupon).filter(Coupon.code == normalized_code).first()
        if not coupon:
            return None, f"Coupon '{normalized_code}' is invalid", "COUPON_NOT_FOUND"

        if not coupon.is_active:
            return None, "This coupon is currently inactive", "COUPON_INACTIVE"

        if coupon.starts_at and coupon.starts_at > now:
            return None, "This coupon promotion has not started yet", "COUPON_NOT_STARTED"

        if coupon.expires_at and coupon.expires_at < now:
            return None, "This coupon has expired", "COUPON_EXPIRED"

        if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
            return None, "This coupon has reached its maximum global usage limit", "COUPON_LIMIT_REACHED"

        if user_id and coupon.per_customer_limit:
            user_uses = (
                db.query(func.count(CouponUsage.id))
                .filter(
                    CouponUsage.coupon_id == coupon.id,
                    CouponUsage.user_id == user_id,
                    CouponUsage.status.in_(["consumed", "reserved"])
                )
                .scalar() or 0
            )
            if user_uses >= coupon.per_customer_limit:
                return None, f"You have already used this coupon maximum allowed times ({coupon.per_customer_limit})", "COUPON_USER_LIMIT_REACHED"

        if coupon.minimum_cart_value and cart_subtotal < coupon.minimum_cart_value:
            return None, f"Minimum cart value of ₹{coupon.minimum_cart_value:,.2f} is required for this coupon", "COUPON_MIN_CART_VALUE"

        if coupon.maximum_cart_value and cart_subtotal > coupon.maximum_cart_value:
            return None, f"Maximum cart value of ₹{coupon.maximum_cart_value:,.2f} exceeded for this coupon", "COUPON_MAX_CART_VALUE"

        return coupon, None, None

    @classmethod
    def calculate_pricing(
        cls,
        db: Session,
        items_data: List[Dict[str, Any]], # [{item_id, product, variant, quantity}]
        user_id: Optional[int] = None,
        coupon_code: Optional[str] = None,
        now: Optional[datetime] = None
    ) -> DiscountCalculationResult:
        if not now:
            now = datetime.utcnow()

        result = DiscountCalculationResult()
        if not items_data:
            return result

        active_flash_sales = cls.get_active_flash_sales(db, now)
        active_offers = cls.get_active_offers(db, now)

        calculated_items: List[CalculatedItemPrice] = []
        base_subtotal = 0.0
        total_mrp_savings = 0.0
        total_tax = 0.0

        # Step 1: Base prices and Flash Sales & Catalog Offers
        for item in items_data:
            product: Product = item["product"]
            variant: Optional[ProductVariant] = item.get("variant")
            quantity: int = item.get("quantity", 1)
            item_id = item.get("item_id")

            if variant:
                selling_price = float(variant.price)
                mrp = float(variant.mrp if variant.mrp is not None else variant.price)
            else:
                selling_price = float(product.price)
                mrp = float(product.mrp if product.mrp is not None else product.price)

            mrp_savings_unit = max(0.0, mrp - selling_price)
            total_mrp_savings += round(mrp_savings_unit * quantity, 2)

            # Check Flash Sale applicability
            flash_discount_unit = 0.0
            is_flash = False
            applied_flash_id = None

            for fs in active_flash_sales:
                # Find matching item in this flash sale
                fs_item = (
                    db.query(FlashSaleItem)
                    .filter(
                        FlashSaleItem.flash_sale_id == fs.id,
                        FlashSaleItem.product_id == product.id,
                        or_(
                            FlashSaleItem.variant_id == (variant.id if variant else None),
                            FlashSaleItem.variant_id.is_(None)
                        )
                    )
                    .first()
                )
                if fs_item:
                    # Check quantity limit
                    if fs_item.quantity_limit is None or fs_item.sold_quantity < fs_item.quantity_limit:
                        if fs_item.sale_price < selling_price:
                            flash_discount_unit = round(selling_price - float(fs_item.sale_price), 2)
                            is_flash = True
                            applied_flash_id = fs.id
                            break

            # Current effective unit price after flash discount
            current_unit = round(selling_price - flash_discount_unit, 2)

            # Check Automatic Catalog Offers
            offer_discount_unit = 0.0
            applied_offer_title = None

            # Only apply regular catalog offers if item not in flash sale, or stackable
            for offer in active_offers:
                applies = False
                if offer.offer_type == "product_discount":
                    is_prod_match = (
                        db.query(OfferProduct)
                        .filter(OfferProduct.offer_id == offer.id, OfferProduct.product_id == product.id)
                        .first()
                    )
                    if is_prod_match:
                        applies = True
                elif offer.offer_type == "category_discount" and product.category_id:
                    is_cat_match = (
                        db.query(OfferCategory)
                        .filter(OfferCategory.offer_id == offer.id, OfferCategory.category_id == product.category_id)
                        .first()
                    )
                    if is_cat_match:
                        applies = True
                elif offer.offer_type == "brand_discount" and product.brand_id:
                    is_brand_match = (
                        db.query(OfferBrand)
                        .filter(OfferBrand.offer_id == offer.id, OfferBrand.brand_id == product.brand_id)
                        .first()
                    )
                    if is_brand_match:
                        applies = True

                if applies and (not is_flash or offer.stackable):
                    if offer.discount_type == "percentage":
                        disc = round((current_unit * offer.discount_value) / 100.0, 2)
                    else: # fixed_amount
                        disc = min(current_unit, float(offer.discount_value))

                    if offer.max_discount_amount:
                        disc = min(disc, float(offer.max_discount_amount))

                    if disc > offer_discount_unit:
                        offer_discount_unit = disc
                        applied_offer_title = offer.name
                        if not offer.stackable:
                            break

            line_sub = round(selling_price * quantity, 2)
            base_subtotal += line_sub

            # Calculate product tax
            tax_pct = float(product.tax_percent) if product.tax_percent is not None else 18.0
            effective_unit_before_coupon = max(0.0, round(current_unit - offer_discount_unit, 2))
            line_tax = round((effective_unit_before_coupon * quantity) * (tax_pct / 100.0), 2)
            total_tax += line_tax

            calc_item = CalculatedItemPrice(
                item_id=item_id,
                product_id=product.id,
                variant_id=variant.id if variant else None,
                quantity=quantity,
                mrp=mrp,
                selling_price=selling_price,
                flash_sale_discount=round(flash_discount_unit * quantity, 2),
                offer_discount=round(offer_discount_unit * quantity, 2),
                coupon_discount=0.0,
                final_unit_price=effective_unit_before_coupon,
                line_subtotal=line_sub,
                final_line_total=round(effective_unit_before_coupon * quantity, 2),
                tax_amount=line_tax,
                is_flash_sale=is_flash,
                applied_offer_title=applied_offer_title,
                applied_flash_sale_id=applied_flash_id
            )
            calculated_items.append(calc_item)

        base_subtotal = round(base_subtotal, 2)
        total_flash_discount = sum(ci.flash_sale_discount for ci in calculated_items)
        total_offer_discount = sum(ci.offer_discount for ci in calculated_items)

        # Step 2: Validate and Apply Coupon
        total_coupon_discount = 0.0
        applied_coupon_details = None

        if coupon_code:
            coupon, err, err_code = cls.validate_coupon(
                db=db,
                coupon_code=coupon_code,
                user_id=user_id,
                cart_subtotal=base_subtotal,
                now=now
            )
            if err:
                result.coupon_error = err
                result.coupon_error_code = err_code
            elif coupon:
                # Check Item-level applicability and exclusions
                applicable_prods = {cp.product_id for cp in coupon.applicable_products}
                applicable_cats = {cc.category_id for cc in coupon.applicable_categories}
                applicable_brands = {cb.brand_id for cb in coupon.applicable_brands}
                exclusions = coupon.exclusions

                has_inclusions = bool(applicable_prods or applicable_cats or applicable_brands)

                eligible_items: List[Tuple[CalculatedItemPrice, Dict[str, Any]]] = []
                for idx, calc_item in enumerate(calculated_items):
                    raw_item = items_data[idx]
                    p: Product = raw_item["product"]

                    # Check exclusion
                    is_excluded = False
                    for exc in exclusions:
                        if exc.exclusion_type == "product" and exc.target_id == p.id:
                            is_excluded = True
                            break
                        elif exc.exclusion_type == "category" and p.category_id == exc.target_id:
                            is_excluded = True
                            break
                        elif exc.exclusion_type == "brand" and p.brand_id == exc.target_id:
                            is_excluded = True
                            break

                    if is_excluded:
                        continue

                    # Check inclusion
                    is_included = True
                    if has_inclusions:
                        is_included = (
                            (p.id in applicable_prods) or
                            (p.category_id in applicable_cats) or
                            (p.brand_id in applicable_brands)
                        )

                    if is_included:
                        eligible_items.append((calc_item, raw_item))

                if not eligible_items:
                    result.coupon_error = "This coupon is not applicable to any items in your cart"
                    result.coupon_error_code = "COUPON_NOT_APPLICABLE"
                else:
                    eligible_subtotal = sum(ci.final_line_total for ci, _ in eligible_items)
                    if coupon.discount_type == "percentage":
                        coupon_disc = round((eligible_subtotal * coupon.discount_value) / 100.0, 2)
                        if coupon.max_discount_amount:
                            coupon_disc = min(coupon_disc, float(coupon.max_discount_amount))
                    else: # fixed_amount
                        coupon_disc = min(float(coupon.discount_value), eligible_subtotal)

                    coupon_disc = round(coupon_disc, 2)
                    total_coupon_discount = coupon_disc

                    # Distribute coupon discount proportionally among eligible items
                    distributed_sum = 0.0
                    for i, (ci, _) in enumerate(eligible_items):
                        if i == len(eligible_items) - 1:
                            # Last item takes remainder to prevent rounding drift
                            allocated = round(coupon_disc - distributed_sum, 2)
                        else:
                            ratio = ci.final_line_total / eligible_subtotal if eligible_subtotal > 0 else 0
                            allocated = round(coupon_disc * ratio, 2)
                            distributed_sum += allocated

                        ci.coupon_discount = allocated
                        ci.final_line_total = max(0.0, round(ci.final_line_total - allocated, 2))
                        ci.final_unit_price = round(ci.final_line_total / ci.quantity, 2)

                    result.coupon_code = coupon.code
                    result.coupon_id = coupon.id
                    applied_coupon_details = {
                        "id": coupon.id,
                        "code": coupon.code,
                        "name": coupon.name,
                        "discount_type": coupon.discount_type,
                        "discount_value": coupon.discount_value,
                        "max_discount_amount": coupon.max_discount_amount,
                        "savings": total_coupon_discount
                    }

        # Step 3: Compute final totals
        total_promo_discount = round(total_flash_discount + total_offer_discount + total_coupon_discount, 2)
        net_items_total = sum(ci.final_line_total for ci in calculated_items)

        # Standard shipping: free above ₹999 or empty cart, else ₹99
        shipping = 0.0 if (net_items_total >= 999.0 or net_items_total == 0) else 99.0
        final_total = max(0.0, round(net_items_total + total_tax + shipping, 2))

        result.items = calculated_items
        result.subtotal = base_subtotal
        result.flash_sale_discount = round(total_flash_discount, 2)
        result.offer_discount = round(total_offer_discount, 2)
        result.coupon_discount = round(total_coupon_discount, 2)
        result.total_promotional_discount = total_promo_discount
        result.mrp_savings = round(total_mrp_savings + total_promo_discount, 2)
        result.tax = round(total_tax, 2)
        result.shipping = shipping
        result.total = final_total
        result.applied_coupon_details = applied_coupon_details

        return result
