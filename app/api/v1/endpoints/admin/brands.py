from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.core.database import get_db
from app.models.category import Brand
from app.models.product import Product
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_admin
from app.schemas.brand import (
    BrandCreate,
    BrandUpdate,
    BrandResponse,
    clean_slug
)
from app.schemas.common import APIResponse

router = APIRouter()

def get_admin_brand_product_counts(db: Session) -> Dict[int, int]:
    """Efficiently count all products per brand (active and inactive) in a single aggregation query."""
    counts = db.query(Product.brand_id, func.count(Product.id))\
        .group_by(Product.brand_id).all()
    return {b_id: count for b_id, count in counts if b_id is not None}

def to_admin_brand_response(brand: Brand, count: int = 0) -> BrandResponse:
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
def list_admin_brands(
    search: Optional[str] = Query(None, description="Search by name, slug, or description"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: 'active', 'inactive', 'all'"),
    limit: Optional[int] = Query(None, ge=1, le=200, description="Optional pagination limit"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin Brand List with search, status filtering, and optional pagination."""
    query = db.query(Brand)
    
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Brand.name.ilike(search_pattern),
                Brand.slug.ilike(search_pattern),
                Brand.description.ilike(search_pattern)
            )
        )
        
    if status_filter:
        if status_filter.lower() == 'active':
            query = query.filter(Brand.is_active == True)
        elif status_filter.lower() == 'inactive':
            query = query.filter(Brand.is_active == False)
            
    query = query.order_by(Brand.sort_order.asc(), Brand.name.asc())
    if skip:
        query = query.offset(skip)
    if limit is not None:
        query = query.limit(limit)

    brands = query.all()
    counts_map = get_admin_brand_product_counts(db)
    res = [to_admin_brand_response(b, counts_map.get(b.id, 0)) for b in brands]
    return APIResponse(success=True, message="Admin brands retrieved", data=res)

@router.post("", response_model=APIResponse[BrandResponse], status_code=status.HTTP_201_CREATED)
def create_brand(
    brand_in: BrandCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Create a new Brand with validation and duplicate prevention."""
    target_slug = clean_slug(brand_in.slug) if brand_in.slug else clean_slug(brand_in.name)
    if not target_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brand slug cannot be empty or invalid"
        )

    # Check for duplicate slug
    existing_slug = db.query(Brand).filter(Brand.slug == target_slug).first()
    if existing_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A brand with slug '{target_slug}' already exists."
        )

    # Check for duplicate name
    existing_name = db.query(Brand).filter(func.lower(Brand.name) == func.lower(brand_in.name.strip())).first()
    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A brand with name '{brand_in.name.strip()}' already exists."
        )

    brand = Brand(
        name=brand_in.name.strip(),
        slug=target_slug,
        description=brand_in.description.strip() if brand_in.description else None,
        logo_url=brand_in.logo_url.strip() if brand_in.logo_url else None,
        website_url=brand_in.website_url.strip() if brand_in.website_url else None,
        sort_order=brand_in.sort_order if brand_in.sort_order is not None else 0,
        is_active=brand_in.is_active if brand_in.is_active is not None else True,
        seo_title=brand_in.seo_title.strip() if brand_in.seo_title else None,
        seo_description=brand_in.seo_description.strip() if brand_in.seo_description else None
    )

    db.add(brand)
    db.commit()
    db.refresh(brand)

    return APIResponse(
        success=True,
        message=f"Brand '{brand.name}' created successfully",
        data=to_admin_brand_response(brand, 0)
    )

@router.get("/{id}", response_model=APIResponse[BrandResponse])
def get_brand_by_id(
    id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Retrieve brand details by ID for admin editing."""
    brand = db.query(Brand).filter(Brand.id == id).first()
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Brand with ID {id} not found"
        )
    counts_map = get_admin_brand_product_counts(db)
    return APIResponse(
        success=True,
        message="Brand retrieved successfully",
        data=to_admin_brand_response(brand, counts_map.get(brand.id, 0))
    )

@router.put("/{id}", response_model=APIResponse[BrandResponse])
def update_brand(
    id: int,
    brand_in: BrandUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update brand information, slug, logo, website, SEO, status, or sort order."""
    brand = db.query(Brand).filter(Brand.id == id).first()
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Brand with ID {id} not found"
        )

    if brand_in.name is not None:
        trimmed_name = brand_in.name.strip()
        # Verify duplicate name on different ID
        duplicate_name = db.query(Brand).filter(
            func.lower(Brand.name) == func.lower(trimmed_name),
            Brand.id != id
        ).first()
        if duplicate_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A brand with name '{trimmed_name}' already exists."
            )
        brand.name = trimmed_name

    if brand_in.slug is not None:
        target_slug = clean_slug(brand_in.slug)
        if not target_slug:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Brand slug cannot be empty or invalid"
            )
        duplicate_slug = db.query(Brand).filter(
            Brand.slug == target_slug,
            Brand.id != id
        ).first()
        if duplicate_slug:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A brand with slug '{target_slug}' already exists."
            )
        brand.slug = target_slug

    if brand_in.description is not None:
        brand.description = brand_in.description.strip() if brand_in.description.strip() else None

    if brand_in.logo_url is not None:
        brand.logo_url = brand_in.logo_url.strip() if brand_in.logo_url.strip() else None

    if brand_in.website_url is not None:
        brand.website_url = brand_in.website_url.strip() if brand_in.website_url.strip() else None

    if brand_in.sort_order is not None:
        brand.sort_order = brand_in.sort_order

    if brand_in.is_active is not None:
        brand.is_active = brand_in.is_active

    if brand_in.seo_title is not None:
        brand.seo_title = brand_in.seo_title.strip() if brand_in.seo_title.strip() else None

    if brand_in.seo_description is not None:
        brand.seo_description = brand_in.seo_description.strip() if brand_in.seo_description.strip() else None

    db.commit()
    db.refresh(brand)

    counts_map = get_admin_brand_product_counts(db)
    return APIResponse(
        success=True,
        message=f"Brand '{brand.name}' updated successfully",
        data=to_admin_brand_response(brand, counts_map.get(brand.id, 0))
    )

@router.delete("/{id}", response_model=APIResponse[bool])
def delete_brand(
    id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Safely delete a brand if no products reference it."""
    brand = db.query(Brand).filter(Brand.id == id).first()
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Brand with ID {id} not found"
        )

    # Check whether products reference the brand
    product_count = db.query(func.count(Product.id)).filter(Product.brand_id == id).scalar() or 0
    if product_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete brand '{brand.name}' because {product_count} product(s) are associated with it. Please reassign or remove the products before deleting this brand."
        )

    brand_name = brand.name
    db.delete(brand)
    db.commit()

    return APIResponse(
        success=True,
        message=f"Brand '{brand_name}' deleted successfully",
        data=True
    )
