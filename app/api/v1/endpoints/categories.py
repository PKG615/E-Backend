from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from app.core.database import get_db

from app.models.category import Category, Brand

from app.models.product import Product

from app.schemas.category import CategoryResponse, CategorySummary, BrandResponse

from app.schemas.common import APIResponse

router = APIRouter()

def get_product_counts(db: Session) -> Dict[int, int]:
    """Efficiently fetch active product counts per category in a single aggregation query."""
    counts = db.query(Product.category_id, func.count(Product.id))\
        .filter(Product.is_active == True)\
        .group_by(Product.category_id).all()
    return {cat_id: count for cat_id, count in counts if cat_id is not None}

def to_public_category_response(
    cat: Category, 
    active_only: bool = True,
    counts_map: Optional[Dict[int, int]] = None
) -> CategoryResponse:
    subs = [
        CategorySummary(
            id=s.id,
            name=s.name,
            slug=s.slug,
            description=s.description,
            image=s.image or s.image_url,
            image_url=s.image_url or s.image,
            banner=s.banner,
            parent_id=s.parent_id,
            sort_order=s.sort_order,
            display_order=s.sort_order,
            is_active=s.is_active,
            seo_title=s.seo_title,
            seo_description=s.seo_description,
            products_count=counts_map.get(s.id, 0) if counts_map is not None else 0
        )
        for s in (cat.subcategories or [])
        if (not active_only or s.is_active)
    ]
    return CategoryResponse(
        id=cat.id,
        name=cat.name,
        slug=cat.slug,
        description=cat.description,
        image=cat.image or cat.image_url,
        image_url=cat.image_url or cat.image,
        banner=cat.banner,
        parent_id=cat.parent_id,
        parent_name=cat.parent.name if cat.parent else None,
        sort_order=cat.sort_order,
        display_order=cat.sort_order,
        is_active=cat.is_active,
        seo_title=cat.seo_title,
        seo_description=cat.seo_description,
        created_at=cat.created_at,
        updated_at=cat.updated_at,
        subcategories=subs,
        products_count=counts_map.get(cat.id, 0) if counts_map is not None else 0
    )

@router.get("", response_model=APIResponse[List[CategoryResponse]])
def get_categories(
    parent_only: bool = Query(False, description="Filter only top-level parent categories"),
    tree: bool = Query(False, description="Nest subcategories under top-level parent categories"),
    active_only: bool = Query(True, description="Only return active categories"),
    db: Session = Depends(get_db)
):
    """Public categories retrieval ordered by sort_order and name."""
    counts_map = get_product_counts(db)
    query = db.query(Category).options(selectinload(Category.subcategories))
    if active_only:
        query = query.filter(Category.is_active == True)
    if parent_only or tree:
        query = query.filter(Category.parent_id == None)
        
    categories = query.order_by(Category.sort_order.asc(), Category.name.asc()).all()
    response_list = [to_public_category_response(cat, active_only, counts_map) for cat in categories]
    
    return APIResponse(
        success=True,
        message="Categories retrieved successfully",
        data=response_list
    )

@router.get("/tree", response_model=APIResponse[List[CategoryResponse]])
def get_category_tree(db: Session = Depends(get_db)):
    """Returns top-level active root categories with active subcategories nested without loading full products."""
    counts_map = get_product_counts(db)
    roots = db.query(Category).options(
        selectinload(Category.subcategories)
    ).filter(
        Category.parent_id == None, 
        Category.is_active == True
    ).order_by(Category.sort_order.asc(), Category.name.asc()).all()
    
    result = [to_public_category_response(root, active_only=True, counts_map=counts_map) for root in roots]
    return APIResponse(success=True, message="Category tree retrieved", data=result)

@router.get("/brands", response_model=APIResponse[List[BrandResponse]])
def get_brands(db: Session = Depends(get_db)):
    brands = db.query(Brand).filter(Brand.is_active == True).order_by(Brand.name.asc()).all()
    return APIResponse(
        success=True,
        message="Brands retrieved successfully",
        data=[BrandResponse.from_orm(b) for b in brands]
    )

@router.get("/{slug}", response_model=APIResponse[CategoryResponse])
def get_category_by_slug(slug: str, db: Session = Depends(get_db)):
    """Retrieve public category by slug with SEO metadata, breadcrumbs, and active subcategories."""
    cat = db.query(Category).filter(Category.slug == slug, Category.is_active == True).first()
    if not cat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{slug}' not found or inactive"
        )
    
    return APIResponse(
        success=True,
        message="Category found",
        data=to_public_category_response(cat, active_only=True)
    )
