from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.core.database import get_db

from app.models.category import Brand

from app.models.product import Product

from app.schemas.brand import BrandResponse

from app.schemas.common import APIResponse

router = APIRouter()

def get_active_brand_product_counts(db: Session) -> Dict[int, int]:
    """Efficiently fetch active product counts per brand in a single aggregation query."""
    counts = db.query(Product.brand_id, func.count(Product.id))\
        .filter(Product.is_active == True)\
        .group_by(Product.brand_id).all()
    return {b_id: count for b_id, count in counts if b_id is not None}

def to_brand_response(brand: Brand, count: int = 0) -> BrandResponse:
    return BrandResponse(
        id=brand.id,
        name=brand.name,
        slug=brand.slug,
        description=brand.description,
        logo_url=brand.logo_url,
        website_url=brand.website_url,
        sort_order=brand.sort_order or 0,
        is_active=brand.is_active,
        seo_title=brand.seo_title,
        seo_description=brand.seo_description,
        created_at=brand.created_at,
        updated_at=brand.updated_at,
        products_count=count
    )

@router.get("", response_model=APIResponse[List[BrandResponse]])
def get_brands(
    search: Optional[str] = Query(None, description="Search active brands by name or description"),
    db: Session = Depends(get_db)
):
    """Retrieve all active brands with real-time active product count."""
    query = db.query(Brand).filter(Brand.is_active == True)
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Brand.name.ilike(search_pattern),
                Brand.slug.ilike(search_pattern),
                Brand.description.ilike(search_pattern)
            )
        )
    brands = query.order_by(Brand.sort_order.asc(), Brand.name.asc()).all()
    counts_map = get_active_brand_product_counts(db)
    
    result = [to_brand_response(b, counts_map.get(b.id, 0)) for b in brands]
    return APIResponse(
        success=True,
        message="Brands retrieved successfully",
        data=result
    )

@router.get("/{slug}", response_model=APIResponse[BrandResponse])
def get_brand_by_slug(
    slug: str,
    db: Session = Depends(get_db)
):
    """Retrieve a single active brand by its unique URL slug."""
    brand = db.query(Brand).filter(
        Brand.slug == slug.strip().lower(),
        Brand.is_active == True
    ).first()
    
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Brand with slug '{slug}' not found or inactive"
        )
        
    counts_map = get_active_brand_product_counts(db)
    return APIResponse(
        success=True,
        message="Brand detail retrieved successfully",
        data=to_brand_response(brand, counts_map.get(brand.id, 0))
    )
