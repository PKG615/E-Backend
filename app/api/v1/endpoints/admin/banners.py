from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.order import Banner
from app.models.user import User
from app.models.product import Product
from app.models.category import Category, Brand
from app.models.cms import Collection
from app.api.v1.endpoints.auth import get_current_admin
from app.schemas.cms import (
    BannerResponse,
    BannerCreate,
    BannerUpdate,
    ReorderRequest,
    StatusToggleRequest
)
from app.schemas.common import APIResponse

router = APIRouter()

def validate_and_resolve_banner_link(db: Session, link_type: Optional[str], link_target: Optional[str], link_url: Optional[str]):
    resolved_url = link_url
    if not link_type or link_type == "custom":
        return resolved_url or "/shop"

    if link_type == "shop":
        return "/shop"

    if not link_target:
        return resolved_url or "/shop"

    target_clean = str(link_target).strip()

    if link_type == "product":
        prod = None
        if target_clean.isdigit():
            prod = db.query(Product).filter(Product.id == int(target_clean)).first()
        if not prod:
            prod = db.query(Product).filter(Product.slug == target_clean).first()
        if not prod:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"Target product '{target_clean}' does not exist.")
        resolved_url = f"/product/{prod.id}"

    elif link_type == "category":
        cat = None
        if target_clean.isdigit():
            cat = db.query(Category).filter(Category.id == int(target_clean)).first()
        if not cat:
            cat = db.query(Category).filter(Category.slug == target_clean).first()
        if not cat:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"Target category '{target_clean}' does not exist.")
        resolved_url = f"/shop?category={cat.slug}"

    elif link_type == "brand":
        br = None
        if target_clean.isdigit():
            br = db.query(Brand).filter(Brand.id == int(target_clean)).first()
        if not br:
            br = db.query(Brand).filter(Brand.slug == target_clean).first()
        if not br:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"Target brand '{target_clean}' does not exist.")
        resolved_url = f"/shop?brand={br.slug}"

    elif link_type == "collection":
        coll = None
        if target_clean.isdigit():
            coll = db.query(Collection).filter(Collection.id == int(target_clean)).first()
        if not coll:
            coll = db.query(Collection).filter(Collection.slug == target_clean).first()
        if not coll:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"Target collection '{target_clean}' does not exist.")
        resolved_url = f"/collections/{coll.slug}"

    return resolved_url

@router.get("", response_model=APIResponse[List[BannerResponse]])
def list_banners(
    banner_type: Optional[str] = Query(None, description="Filter by banner type (hero, promo, flash_sale, strip)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    query = db.query(Banner)
    if banner_type:
        query = query.filter(Banner.banner_type == banner_type)
    if is_active is not None:
        query = query.filter(Banner.is_active == is_active)
    banners = query.order_by(Banner.display_order.asc(), Banner.id.asc()).all()
    return APIResponse(
        success=True,
        message="Banners retrieved successfully",
        data=[BannerResponse.from_orm(b) for b in banners]
    )

@router.get("/{banner_id}", response_model=APIResponse[BannerResponse])
def get_banner(
    banner_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if not banner:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Banner not found")
    return APIResponse(success=True, message="Banner retrieved", data=BannerResponse.from_orm(banner))

@router.post("", response_model=APIResponse[BannerResponse], status_code=http_status.HTTP_201_CREATED)
def create_banner(
    banner_in: BannerCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    # Resolve and validate link
    resolved_link = validate_and_resolve_banner_link(db, banner_in.link_type, banner_in.link_target, banner_in.link_url)

    # Determine display order if 0
    display_ord = banner_in.display_order
    if display_ord == 0:
        max_order = db.query(Banner.display_order).order_by(Banner.display_order.desc()).first()
        display_ord = (max_order[0] + 1) if max_order else 1

    banner = Banner(
        title=banner_in.title,
        subtitle=banner_in.subtitle,
        description=banner_in.description,
        image_url=banner_in.image_url,
        mobile_image_url=banner_in.mobile_image_url,
        alt_text=banner_in.alt_text or banner_in.title,
        link_type=banner_in.link_type or "custom",
        link_target=banner_in.link_target,
        link_url=resolved_link,
        cta_label=banner_in.cta_label or "Explore Now",
        cta_url=banner_in.cta_url or resolved_link,
        banner_type=banner_in.banner_type,
        is_active=banner_in.is_active,
        display_order=display_ord,
        start_at=banner_in.start_at,
        end_at=banner_in.end_at
    )
    db.add(banner)
    db.commit()
    db.refresh(banner)
    return APIResponse(success=True, message="Banner created successfully", data=BannerResponse.from_orm(banner))

@router.put("/reorder", response_model=APIResponse[List[BannerResponse]])
def reorder_banners(
    req: ReorderRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    for item in req.items:
        db.query(Banner).filter(Banner.id == item.id).update({"display_order": item.sort_order})
    db.commit()
    banners = db.query(Banner).order_by(Banner.display_order.asc()).all()
    return APIResponse(success=True, message="Banners reordered successfully", data=[BannerResponse.from_orm(b) for b in banners])

@router.put("/{banner_id}", response_model=APIResponse[BannerResponse])
def update_banner(
    banner_id: int,
    banner_in: BannerUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if not banner:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Banner not found")

    update_data = banner_in.dict(exclude_unset=True)

    # If link type or link target updated, validate and resolve
    if "link_type" in update_data or "link_target" in update_data:
        l_type = update_data.get("link_type", banner.link_type)
        l_target = update_data.get("link_target", banner.link_target)
        l_url = update_data.get("link_url", banner.link_url)
        resolved = validate_and_resolve_banner_link(db, l_type, l_target, l_url)
        update_data["link_url"] = resolved
        if "cta_url" not in update_data or not update_data["cta_url"]:
            update_data["cta_url"] = resolved

    for field, value in update_data.items():
        setattr(banner, field, value)

    db.commit()
    db.refresh(banner)
    return APIResponse(success=True, message="Banner updated successfully", data=BannerResponse.from_orm(banner))

@router.put("/{banner_id}/status", response_model=APIResponse[BannerResponse])
def toggle_banner_status(
    banner_id: int,
    req: StatusToggleRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if not banner:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Banner not found")

    banner.is_active = req.is_active
    db.commit()
    db.refresh(banner)
    return APIResponse(
        success=True,
        message=f"Banner {'activated' if req.is_active else 'deactivated'} successfully",
        data=BannerResponse.from_orm(banner)
    )

@router.delete("/{banner_id}", response_model=APIResponse[bool])
def delete_banner(
    banner_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if not banner:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Banner not found")
    db.delete(banner)
    db.commit()
    return APIResponse(success=True, message="Banner deleted successfully", data=True)
