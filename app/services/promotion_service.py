from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, desc
from fastapi import HTTPException, status

from app.models.promotions import (
    Coupon, CouponProduct, CouponCategory, CouponBrand, CouponExclusion, CouponUsage,
    Offer, OfferProduct, OfferCategory, OfferBrand,
    FlashSale, FlashSaleItem
)
from app.models.product import Product, ProductVariant
from app.models.category import Category
from app.models.brand import Brand
from app.models.inventory import Inventory
from app.schemas.promotions import (
    CouponCreate, CouponUpdate, CouponResponse, CouponUsageResponse, AvailableCouponResponse,
    OfferCreate, OfferUpdate, OfferResponse,
    FlashSaleCreate, FlashSaleUpdate, FlashSaleResponse, FlashSaleItemResponse
)

class PromotionService:

    # -----------------------------------------------------
    # COUPON MANAGEMENT
    # -----------------------------------------------------

    @staticmethod
    def list_coupons(
        db: Session,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[CouponResponse], int]:
        query = db.query(Coupon)
        if search:
            s = f"%{search.strip()}%"
            query = query.filter(or_(Coupon.code.ilike(s), Coupon.name.ilike(s)))
        if is_active is not None:
            query = query.filter(Coupon.is_active == is_active)

        total = query.count()
        coupons = query.order_by(Coupon.created_at.desc()).offset(skip).limit(limit).all()

        responses = []
        for c in coupons:
            prod_ids = [cp.product_id for cp in c.applicable_products]
            cat_ids = [cc.category_id for cc in c.applicable_categories]
            brand_ids = [cb.brand_id for cb in c.applicable_brands]
            exclusions = [
                {"exclusion_type": e.exclusion_type, "target_id": e.target_id}
                for e in c.exclusions
            ]
            responses.append(
                CouponResponse(
                    id=c.id,
                    code=c.code,
                    name=c.name,
                    description=c.description,
                    discount_type=c.discount_type,
                    discount_value=c.discount_value,
                    max_discount_amount=c.max_discount_amount,
                    minimum_cart_value=c.minimum_cart_value,
                    maximum_cart_value=c.maximum_cart_value,
                    usage_limit=c.usage_limit,
                    per_customer_limit=c.per_customer_limit,
                    used_count=c.used_count,
                    starts_at=c.starts_at,
                    expires_at=c.expires_at,
                    is_active=c.is_active,
                    applicable_product_ids=prod_ids,
                    applicable_category_ids=cat_ids,
                    applicable_brand_ids=brand_ids,
                    exclusions=exclusions,
                    created_at=c.created_at,
                    updated_at=c.updated_at
                )
            )
        return responses, total

    @staticmethod
    def get_coupon(db: Session, coupon_id: int) -> CouponResponse:
        c = db.query(Coupon).filter(Coupon.id == coupon_id).first()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")

        prod_ids = [cp.product_id for cp in c.applicable_products]
        cat_ids = [cc.category_id for cc in c.applicable_categories]
        brand_ids = [cb.brand_id for cb in c.applicable_brands]
        exclusions = [
            {"exclusion_type": e.exclusion_type, "target_id": e.target_id}
            for e in c.exclusions
        ]
        return CouponResponse(
            id=c.id,
            code=c.code,
            name=c.name,
            description=c.description,
            discount_type=c.discount_type,
            discount_value=c.discount_value,
            max_discount_amount=c.max_discount_amount,
            minimum_cart_value=c.minimum_cart_value,
            maximum_cart_value=c.maximum_cart_value,
            usage_limit=c.usage_limit,
            per_customer_limit=c.per_customer_limit,
            used_count=c.used_count,
            starts_at=c.starts_at,
            expires_at=c.expires_at,
            is_active=c.is_active,
            applicable_product_ids=prod_ids,
            applicable_category_ids=cat_ids,
            applicable_brand_ids=brand_ids,
            exclusions=exclusions,
            created_at=c.created_at,
            updated_at=c.updated_at
        )

    @staticmethod
    def create_coupon(db: Session, payload: CouponCreate) -> CouponResponse:
        code = payload.code.strip().upper()
        existing = db.query(Coupon).filter(Coupon.code == code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Coupon with code '{code}' already exists"
            )

        coupon = Coupon(
            code=code,
            name=payload.name.strip(),
            description=payload.description,
            discount_type=payload.discount_type,
            discount_value=payload.discount_value,
            max_discount_amount=payload.max_discount_amount,
            minimum_cart_value=payload.minimum_cart_value,
            maximum_cart_value=payload.maximum_cart_value,
            usage_limit=payload.usage_limit,
            per_customer_limit=payload.per_customer_limit,
            starts_at=payload.starts_at,
            expires_at=payload.expires_at,
            is_active=payload.is_active
        )
        db.add(coupon)
        db.flush()

        for pid in set(payload.applicable_product_ids):
            db.add(CouponProduct(coupon_id=coupon.id, product_id=pid))

        for cid in set(payload.applicable_category_ids):
            db.add(CouponCategory(coupon_id=coupon.id, category_id=cid))

        for bid in set(payload.applicable_brand_ids):
            db.add(CouponBrand(coupon_id=coupon.id, brand_id=bid))

        for exc in payload.exclusions:
            db.add(CouponExclusion(
                coupon_id=coupon.id,
                exclusion_type=exc.exclusion_type,
                target_id=exc.target_id
            ))

        db.commit()
        db.refresh(coupon)
        return PromotionService.get_coupon(db, coupon.id)

    @staticmethod
    def update_coupon(db: Session, coupon_id: int, payload: CouponUpdate) -> CouponResponse:
        coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
        if not coupon:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")

        if payload.code is not None:
            new_code = payload.code.strip().upper()
            if new_code != coupon.code:
                existing = db.query(Coupon).filter(Coupon.code == new_code, Coupon.id != coupon_id).first()
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Coupon code '{new_code}' is already taken"
                    )
                coupon.code = new_code

        if payload.name is not None:
            coupon.name = payload.name.strip()
        if payload.description is not None:
            coupon.description = payload.description
        if payload.discount_type is not None:
            coupon.discount_type = payload.discount_type
        if payload.discount_value is not None:
            coupon.discount_value = payload.discount_value
        if payload.max_discount_amount is not None:
            coupon.max_discount_amount = payload.max_discount_amount
        if payload.minimum_cart_value is not None:
            coupon.minimum_cart_value = payload.minimum_cart_value
        if payload.maximum_cart_value is not None:
            coupon.maximum_cart_value = payload.maximum_cart_value
        if payload.usage_limit is not None:
            coupon.usage_limit = payload.usage_limit
        if payload.per_customer_limit is not None:
            coupon.per_customer_limit = payload.per_customer_limit
        if payload.starts_at is not None:
            coupon.starts_at = payload.starts_at
        if payload.expires_at is not None:
            coupon.expires_at = payload.expires_at
        if payload.is_active is not None:
            coupon.is_active = payload.is_active

        if payload.applicable_product_ids is not None:
            db.query(CouponProduct).filter(CouponProduct.coupon_id == coupon_id).delete()
            for pid in set(payload.applicable_product_ids):
                db.add(CouponProduct(coupon_id=coupon_id, product_id=pid))

        if payload.applicable_category_ids is not None:
            db.query(CouponCategory).filter(CouponCategory.coupon_id == coupon_id).delete()
            for cid in set(payload.applicable_category_ids):
                db.add(CouponCategory(coupon_id=coupon_id, category_id=cid))

        if payload.applicable_brand_ids is not None:
            db.query(CouponBrand).filter(CouponBrand.coupon_id == coupon_id).delete()
            for bid in set(payload.applicable_brand_ids):
                db.add(CouponBrand(coupon_id=coupon_id, brand_id=bid))

        if payload.exclusions is not None:
            db.query(CouponExclusion).filter(CouponExclusion.coupon_id == coupon_id).delete()
            for exc in payload.exclusions:
                db.add(CouponExclusion(
                    coupon_id=coupon_id,
                    exclusion_type=exc.exclusion_type,
                    target_id=exc.target_id
                ))

        coupon.updated_at = datetime.utcnow()
        db.commit()
        return PromotionService.get_coupon(db, coupon_id)

    @staticmethod
    def delete_coupon(db: Session, coupon_id: int) -> bool:
        coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
        if not coupon:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")
        db.delete(coupon)
        db.commit()
        return True

    @staticmethod
    def list_available_coupons_for_customer(
        db: Session,
        user_id: Optional[int] = None,
        cart_subtotal: float = 0.0
    ) -> List[AvailableCouponResponse]:
        now = datetime.utcnow()
        coupons = (
            db.query(Coupon)
            .filter(
                Coupon.is_active == True,
                or_(Coupon.starts_at.is_(None), Coupon.starts_at <= now),
                or_(Coupon.expires_at.is_(None), Coupon.expires_at >= now)
            )
            .order_by(Coupon.created_at.desc())
            .all()
        )

        results: List[AvailableCouponResponse] = []
        for c in coupons:
            is_eligible = True
            ineligible_reason = None

            if c.usage_limit is not None and c.used_count >= c.usage_limit:
                is_eligible = False
                ineligible_reason = "Global usage limit reached"
            elif user_id and c.per_customer_limit:
                user_uses = (
                    db.query(CouponUsage)
                    .filter(
                        CouponUsage.coupon_id == c.id,
                        CouponUsage.user_id == user_id,
                        CouponUsage.status.in_(["consumed", "reserved"])
                    )
                    .count()
                )
                if user_uses >= c.per_customer_limit:
                    is_eligible = False
                    ineligible_reason = "Customer limit reached"
            elif c.minimum_cart_value and cart_subtotal < c.minimum_cart_value:
                is_eligible = False
                ineligible_reason = f"Min cart value ₹{c.minimum_cart_value:,.2f}"

            results.append(
                AvailableCouponResponse(
                    id=c.id,
                    code=c.code,
                    name=c.name,
                    description=c.description,
                    discount_type=c.discount_type,
                    discount_value=c.discount_value,
                    max_discount_amount=c.max_discount_amount,
                    minimum_cart_value=c.minimum_cart_value,
                    expires_at=c.expires_at,
                    is_eligible=is_eligible,
                    ineligible_reason=ineligible_reason
                )
            )
        return results

    @staticmethod
    def list_coupon_usages(
        db: Session,
        coupon_id: Optional[int] = None,
        user_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[CouponUsageResponse], int]:
        query = db.query(CouponUsage).options(
            joinedload(CouponUsage.coupon),
            joinedload(CouponUsage.user),
            joinedload(CouponUsage.order)
        )
        if coupon_id:
            query = query.filter(CouponUsage.coupon_id == coupon_id)
        if user_id:
            query = query.filter(CouponUsage.user_id == user_id)

        total = query.count()
        usages = query.order_by(CouponUsage.used_at.desc()).offset(skip).limit(limit).all()

        responses = [
            CouponUsageResponse(
                id=u.id,
                coupon_id=u.coupon_id,
                coupon_code=u.coupon.code if u.coupon else "",
                user_id=u.user_id,
                user_email=u.user.email if u.user else None,
                order_id=u.order_id,
                order_number=u.order.order_number if u.order else None,
                discount_amount=u.discount_amount,
                status=u.status,
                used_at=u.used_at
            )
            for u in usages
        ]
        return responses, total

    # -----------------------------------------------------
    # OFFER MANAGEMENT
    # -----------------------------------------------------

    @staticmethod
    def list_offers(
        db: Session,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[OfferResponse], int]:
        query = db.query(Offer)
        if search:
            s = f"%{search.strip()}%"
            query = query.filter(or_(Offer.name.ilike(s), Offer.description.ilike(s)))
        if is_active is not None:
            query = query.filter(Offer.is_active == is_active)

        total = query.count()
        offers = query.order_by(Offer.priority.desc(), Offer.created_at.desc()).offset(skip).limit(limit).all()

        responses = []
        for o in offers:
            prod_ids = [op.product_id for op in o.applicable_products]
            cat_ids = [oc.category_id for oc in o.applicable_categories]
            brand_ids = [ob.brand_id for ob in o.applicable_brands]
            responses.append(
                OfferResponse(
                    id=o.id,
                    name=o.name,
                    description=o.description,
                    offer_type=o.offer_type,
                    discount_type=o.discount_type,
                    discount_value=o.discount_value,
                    max_discount_amount=o.max_discount_amount,
                    minimum_cart_value=o.minimum_cart_value,
                    starts_at=o.starts_at,
                    expires_at=o.expires_at,
                    is_active=o.is_active,
                    priority=o.priority,
                    stackable=o.stackable,
                    applicable_product_ids=prod_ids,
                    applicable_category_ids=cat_ids,
                    applicable_brand_ids=brand_ids,
                    created_at=o.created_at,
                    updated_at=o.updated_at
                )
            )
        return responses, total

    @staticmethod
    def get_offer(db: Session, offer_id: int) -> OfferResponse:
        o = db.query(Offer).filter(Offer.id == offer_id).first()
        if not o:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")

        prod_ids = [op.product_id for op in o.applicable_products]
        cat_ids = [oc.category_id for oc in o.applicable_categories]
        brand_ids = [ob.brand_id for ob in o.applicable_brands]
        return OfferResponse(
            id=o.id,
            name=o.name,
            description=o.description,
            offer_type=o.offer_type,
            discount_type=o.discount_type,
            discount_value=o.discount_value,
            max_discount_amount=o.max_discount_amount,
            minimum_cart_value=o.minimum_cart_value,
            starts_at=o.starts_at,
            expires_at=o.expires_at,
            is_active=o.is_active,
            priority=o.priority,
            stackable=o.stackable,
            applicable_product_ids=prod_ids,
            applicable_category_ids=cat_ids,
            applicable_brand_ids=brand_ids,
            created_at=o.created_at,
            updated_at=o.updated_at
        )

    @staticmethod
    def create_offer(db: Session, payload: OfferCreate) -> OfferResponse:
        offer = Offer(
            name=payload.name.strip(),
            description=payload.description,
            offer_type=payload.offer_type,
            discount_type=payload.discount_type,
            discount_value=payload.discount_value,
            max_discount_amount=payload.max_discount_amount,
            minimum_cart_value=payload.minimum_cart_value,
            starts_at=payload.starts_at,
            expires_at=payload.expires_at,
            is_active=payload.is_active,
            priority=payload.priority,
            stackable=payload.stackable
        )
        db.add(offer)
        db.flush()

        for pid in set(payload.applicable_product_ids):
            db.add(OfferProduct(offer_id=offer.id, product_id=pid))

        for cid in set(payload.applicable_category_ids):
            db.add(OfferCategory(offer_id=offer.id, category_id=cid))

        for bid in set(payload.applicable_brand_ids):
            db.add(OfferBrand(offer_id=offer.id, brand_id=bid))

        db.commit()
        db.refresh(offer)
        return PromotionService.get_offer(db, offer.id)

    @staticmethod
    def update_offer(db: Session, offer_id: int, payload: OfferUpdate) -> OfferResponse:
        offer = db.query(Offer).filter(Offer.id == offer_id).first()
        if not offer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")

        if payload.name is not None:
            offer.name = payload.name.strip()
        if payload.description is not None:
            offer.description = payload.description
        if payload.offer_type is not None:
            offer.offer_type = payload.offer_type
        if payload.discount_type is not None:
            offer.discount_type = payload.discount_type
        if payload.discount_value is not None:
            offer.discount_value = payload.discount_value
        if payload.max_discount_amount is not None:
            offer.max_discount_amount = payload.max_discount_amount
        if payload.minimum_cart_value is not None:
            offer.minimum_cart_value = payload.minimum_cart_value
        if payload.starts_at is not None:
            offer.starts_at = payload.starts_at
        if payload.expires_at is not None:
            offer.expires_at = payload.expires_at
        if payload.is_active is not None:
            offer.is_active = payload.is_active
        if payload.priority is not None:
            offer.priority = payload.priority
        if payload.stackable is not None:
            offer.stackable = payload.stackable

        if payload.applicable_product_ids is not None:
            db.query(OfferProduct).filter(OfferProduct.offer_id == offer_id).delete()
            for pid in set(payload.applicable_product_ids):
                db.add(OfferProduct(offer_id=offer_id, product_id=pid))

        if payload.applicable_category_ids is not None:
            db.query(OfferCategory).filter(OfferCategory.offer_id == offer_id).delete()
            for cid in set(payload.applicable_category_ids):
                db.add(OfferCategory(offer_id=offer_id, category_id=cid))

        if payload.applicable_brand_ids is not None:
            db.query(OfferBrand).filter(OfferBrand.offer_id == offer_id).delete()
            for bid in set(payload.applicable_brand_ids):
                db.add(OfferBrand(offer_id=offer_id, brand_id=bid))

        offer.updated_at = datetime.utcnow()
        db.commit()
        return PromotionService.get_offer(db, offer_id)

    @staticmethod
    def delete_offer(db: Session, offer_id: int) -> bool:
        offer = db.query(Offer).filter(Offer.id == offer_id).first()
        if not offer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
        db.delete(offer)
        db.commit()
        return True

    # -----------------------------------------------------
    # FLASH SALE MANAGEMENT
    # -----------------------------------------------------

    @staticmethod
    def _build_flash_sale_response(db: Session, fs: FlashSale) -> FlashSaleResponse:
        now = datetime.utcnow()
        is_live = fs.is_active and (fs.starts_at <= now <= fs.ends_at)
        is_upcoming = fs.is_active and (now < fs.starts_at)
        is_ended = not fs.is_active or (now > fs.ends_at)
        time_rem = 0
        if is_live:
            time_rem = max(0, int((fs.ends_at - now).total_seconds()))

        item_responses: List[FlashSaleItemResponse] = []
        for it in fs.items:
            p = it.product
            v = it.variant
            reg_price = float(v.price) if v else float(p.price if p else 0.0)
            diff = max(0.0, reg_price - float(it.sale_price))
            pct = round((diff / reg_price) * 100.0, 1) if reg_price > 0 else 0.0

            # Stock check
            avail_stock = 0
            if v:
                inv = db.query(Inventory).filter(Inventory.product_id == p.id, Inventory.variant_id == v.id).first()
                avail_stock = inv.available_quantity if inv else (v.stock or 0)
            elif p:
                inv = db.query(Inventory).filter(Inventory.product_id == p.id, Inventory.variant_id.is_(None)).first()
                avail_stock = inv.available_quantity if inv else (p.stock or 0)

            # Check quantity limit
            if it.quantity_limit is not None:
                limit_remaining = max(0, it.quantity_limit - it.sold_quantity)
                avail_stock = min(avail_stock, limit_remaining)

            img = None
            if p and p.images:
                prim = [i.image_url for i in p.images if i.is_primary]
                img = prim[0] if prim else p.images[0].image_url
            if not img and p:
                img = p.thumbnail_url

            item_responses.append(
                FlashSaleItemResponse(
                    id=it.id,
                    flash_sale_id=it.flash_sale_id,
                    product_id=it.product_id,
                    product_name=p.name if p else "Product",
                    product_slug=p.slug if p else "",
                    product_image=img,
                    regular_price=reg_price,
                    variant_id=it.variant_id,
                    variant_title=v.title if v else None,
                    sale_price=it.sale_price,
                    discount_percent=pct,
                    quantity_limit=it.quantity_limit,
                    sold_quantity=it.sold_quantity,
                    available_stock=avail_stock,
                    is_in_stock=avail_stock > 0
                )
            )

        return FlashSaleResponse(
            id=fs.id,
            name=fs.name,
            description=fs.description,
            banner_image=fs.banner_image,
            starts_at=fs.starts_at,
            ends_at=fs.ends_at,
            is_active=fs.is_active,
            priority=fs.priority,
            items=item_responses,
            is_live=is_live,
            is_upcoming=is_upcoming,
            is_ended=is_ended,
            time_remaining_seconds=time_rem,
            created_at=fs.created_at,
            updated_at=fs.updated_at
        )

    @staticmethod
    def list_flash_sales(
        db: Session,
        is_active: Optional[bool] = None,
        only_live: bool = False,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[FlashSaleResponse], int]:
        now = datetime.utcnow()
        query = db.query(FlashSale).options(
            joinedload(FlashSale.items).joinedload(FlashSaleItem.product).joinedload(Product.images),
            joinedload(FlashSale.items).joinedload(FlashSaleItem.variant)
        )
        if is_active is not None:
            query = query.filter(FlashSale.is_active == is_active)
        if only_live:
            query = query.filter(
                FlashSale.is_active == True,
                FlashSale.starts_at <= now,
                FlashSale.ends_at >= now
            )

        total = query.count()
        sales = query.order_by(FlashSale.priority.desc(), FlashSale.starts_at.asc()).offset(skip).limit(limit).all()
        return [PromotionService._build_flash_sale_response(db, fs) for fs in sales], total

    @staticmethod
    def get_flash_sale(db: Session, flash_sale_id: int) -> FlashSaleResponse:
        fs = (
            db.query(FlashSale)
            .options(
                joinedload(FlashSale.items).joinedload(FlashSaleItem.product).joinedload(Product.images),
                joinedload(FlashSale.items).joinedload(FlashSaleItem.variant)
            )
            .filter(FlashSale.id == flash_sale_id)
            .first()
        )
        if not fs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flash sale not found")
        return PromotionService._build_flash_sale_response(db, fs)

    @staticmethod
    def create_flash_sale(db: Session, payload: FlashSaleCreate) -> FlashSaleResponse:
        if payload.ends_at <= payload.starts_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Flash sale end time must be strictly after start time"
            )

        fs = FlashSale(
            name=payload.name.strip(),
            description=payload.description,
            banner_image=payload.banner_image,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            is_active=payload.is_active,
            priority=payload.priority
        )
        db.add(fs)
        db.flush()

        for item_in in payload.items:
            # Validate product existence
            p = db.query(Product).filter(Product.id == item_in.product_id).first()
            if not p:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product with id {item_in.product_id} does not exist"
                )
            it = FlashSaleItem(
                flash_sale_id=fs.id,
                product_id=item_in.product_id,
                variant_id=item_in.variant_id,
                sale_price=item_in.sale_price,
                quantity_limit=item_in.quantity_limit,
                sold_quantity=0
            )
            db.add(it)

        db.commit()
        db.refresh(fs)
        return PromotionService.get_flash_sale(db, fs.id)

    @staticmethod
    def update_flash_sale(db: Session, flash_sale_id: int, payload: FlashSaleUpdate) -> FlashSaleResponse:
        fs = db.query(FlashSale).filter(FlashSale.id == flash_sale_id).first()
        if not fs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flash sale not found")

        if payload.name is not None:
            fs.name = payload.name.strip()
        if payload.description is not None:
            fs.description = payload.description
        if payload.banner_image is not None:
            fs.banner_image = payload.banner_image
        if payload.starts_at is not None:
            fs.starts_at = payload.starts_at
        if payload.ends_at is not None:
            fs.ends_at = payload.ends_at
        if payload.is_active is not None:
            fs.is_active = payload.is_active
        if payload.priority is not None:
            fs.priority = payload.priority

        if fs.ends_at <= fs.starts_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Flash sale end time must be strictly after start time"
            )

        if payload.items is not None:
            db.query(FlashSaleItem).filter(FlashSaleItem.flash_sale_id == flash_sale_id).delete()
            for item_in in payload.items:
                it = FlashSaleItem(
                    flash_sale_id=flash_sale_id,
                    product_id=item_in.product_id,
                    variant_id=item_in.variant_id,
                    sale_price=item_in.sale_price,
                    quantity_limit=item_in.quantity_limit,
                    sold_quantity=0
                )
                db.add(it)

        fs.updated_at = datetime.utcnow()
        db.commit()
        return PromotionService.get_flash_sale(db, flash_sale_id)

    @staticmethod
    def delete_flash_sale(db: Session, flash_sale_id: int) -> bool:
        fs = db.query(FlashSale).filter(FlashSale.id == flash_sale_id).first()
        if not fs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flash sale not found")
        db.delete(fs)
        db.commit()
        return True
