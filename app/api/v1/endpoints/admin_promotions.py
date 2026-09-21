from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import datetime
from app.core.database import get_db
from app.api.v1.endpoints.auth import require_permission
from app.models.user import User
from app.models.promotions import Coupon, Offer, FlashSale, CouponUsage
from app.services.promotion_service import PromotionService
from app.schemas.promotions import (
    CouponCreate, CouponUpdate, CouponResponse,
    OfferCreate, OfferUpdate, OfferResponse,
    FlashSaleCreate, FlashSaleUpdate, FlashSaleResponse
)
from app.schemas.common import APIResponse

router = APIRouter()

# ----------------- COUPONS -----------------
@router.get("/coupons", response_model=APIResponse[List[CouponResponse]])
def list_coupons(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_admin: User = Depends(require_permission("coupons.read")),
    db: Session = Depends(get_db)
):
    coupons, total = PromotionService.list_coupons(
        db=db, search=search, is_active=is_active, skip=skip, limit=limit
    )
    return APIResponse(
        success=True,
        message=f"Retrieved {len(coupons)} coupons (total: {total})",
        data=coupons
    )

@router.post("/coupons", response_model=APIResponse[CouponResponse], status_code=status.HTTP_201_CREATED)
def create_coupon(
    payload: CouponCreate,
    current_admin: User = Depends(require_permission("coupons.create")),
    db: Session = Depends(get_db)
):
    coupon = PromotionService.create_coupon(db=db, coupon_in=payload)
    return APIResponse(
        success=True,
        message="Coupon created successfully",
        data=coupon
    )

@router.put("/coupons/{coupon_id}", response_model=APIResponse[CouponResponse])
def update_coupon(
    coupon_id: int,
    payload: CouponUpdate,
    current_admin: User = Depends(require_permission("coupons.update")),
    db: Session = Depends(get_db)
):
    coupon = PromotionService.update_coupon(db=db, coupon_id=coupon_id, coupon_in=payload)
    return APIResponse(
        success=True,
        message="Coupon updated successfully",
        data=coupon
    )

@router.delete("/coupons/{coupon_id}", response_model=APIResponse[dict])
def delete_coupon(
    coupon_id: int,
    current_admin: User = Depends(require_permission("coupons.update")),
    db: Session = Depends(get_db)
):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")
    db.delete(coupon)
    db.commit()
    return APIResponse(
        success=True,
        message="Coupon deleted successfully",
        data={"id": coupon_id}
    )

# ----------------- OFFERS -----------------
@router.get("/offers", response_model=APIResponse[List[OfferResponse]])
def list_offers(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_admin: User = Depends(require_permission("offers.read")),
    db: Session = Depends(get_db)
):
    offers, total = PromotionService.list_offers(
        db=db, search=search, is_active=is_active, skip=skip, limit=limit
    )
    return APIResponse(
        success=True,
        message=f"Retrieved {len(offers)} offers",
        data=offers
    )

@router.post("/offers", response_model=APIResponse[OfferResponse], status_code=status.HTTP_201_CREATED)
def create_offer(
    payload: OfferCreate,
    current_admin: User = Depends(require_permission("offers.create")),
    db: Session = Depends(get_db)
):
    offer = PromotionService.create_offer(db=db, offer_in=payload)
    return APIResponse(
        success=True,
        message="Offer created successfully",
        data=offer
    )

@router.delete("/offers/{offer_id}", response_model=APIResponse[dict])
def delete_offer(
    offer_id: int,
    current_admin: User = Depends(require_permission("offers.update")),
    db: Session = Depends(get_db)
):
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    db.delete(offer)
    db.commit()
    return APIResponse(
        success=True,
        message="Offer deleted successfully",
        data={"id": offer_id}
    )

# ----------------- FLASH SALES -----------------
@router.get("/flash-sales", response_model=APIResponse[List[FlashSaleResponse]])
def list_flash_sales(
    status_filter: Optional[str] = Query("all", description="all | active | upcoming | ended"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_admin: User = Depends(require_permission("flash_sales.read")),
    db: Session = Depends(get_db)
):
    flash_sales, total = PromotionService.list_flash_sales(
        db=db, status=status_filter, skip=skip, limit=limit
    )
    return APIResponse(
        success=True,
        message=f"Retrieved {len(flash_sales)} flash sales",
        data=flash_sales
    )

@router.post("/flash-sales", response_model=APIResponse[FlashSaleResponse], status_code=status.HTTP_201_CREATED)
def create_flash_sale(
    payload: FlashSaleCreate,
    current_admin: User = Depends(require_permission("flash_sales.create")),
    db: Session = Depends(get_db)
):
    fs = PromotionService.create_flash_sale(db=db, sale_in=payload)
    return APIResponse(
        success=True,
        message="Flash sale created successfully",
        data=fs
    )

@router.delete("/flash-sales/{sale_id}", response_model=APIResponse[dict])
def delete_flash_sale(
    sale_id: int,
    current_admin: User = Depends(require_permission("flash_sales.update")),
    db: Session = Depends(get_db)
):
    fs = db.query(FlashSale).filter(FlashSale.id == sale_id).first()
    if not fs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flash sale not found")
    db.delete(fs)
    db.commit()
    return APIResponse(
        success=True,
        message="Flash sale deleted successfully",
        data={"id": sale_id}
    )
