from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_, func

from app.core.database import get_db
from app.models.category import Category
from app.models.product import Product
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_admin
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CategorySummary,
    clean_slug
)
from app.schemas.common import APIResponse

router = APIRouter()

def get_product_counts(db: Session) -> Dict[int, int]:
    """Efficiently fetch product counts per category in a single aggregation query."""
    counts = db.query(Product.category_id, func.count(Product.id))\
        .group_by(Product.category_id).all()
    return {cat_id: count for cat_id, count in counts if cat_id is not None}

def to_category_response(cat: Category, counts_map: Optional[Dict[int, int]] = None) -> CategoryResponse:
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
def list_admin_categories(
    search: Optional[str] = Query(None, description="Search by name, slug, or description"),
    parent_id: Optional[str] = Query(None, description="Filter by parent ID, or 'root' / 'none' for top-level"),
    status: Optional[str] = Query(None, description="Filter by status: 'active', 'inactive', 'all'"),
    limit: Optional[int] = Query(None, ge=1, le=200, description="Optional pagination limit"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin Category List with search, parent filtering, status filtering, and optional pagination."""
    query = db.query(Category).options(selectinload(Category.subcategories))
    
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Category.name.ilike(search_pattern),
                Category.slug.ilike(search_pattern),
                Category.description.ilike(search_pattern)
            )
        )
        
    if parent_id is not None:
        if parent_id.lower() in ['root', 'none', 'null', '0']:
            query = query.filter(Category.parent_id == None)
        elif parent_id.isdigit():
            query = query.filter(Category.parent_id == int(parent_id))
            
    if status:
        if status.lower() == 'active':
            query = query.filter(Category.is_active == True)
        elif status.lower() == 'inactive':
            query = query.filter(Category.is_active == False)
            
    query = query.order_by(Category.sort_order.asc(), Category.name.asc())
    if skip:
        query = query.offset(skip)
    if limit is not None:
        query = query.limit(limit)

    categories = query.all()
    counts_map = get_product_counts(db)
    res = [to_category_response(cat, counts_map) for cat in categories]
    return APIResponse(success=True, message="Admin categories retrieved", data=res)

@router.post("", response_model=APIResponse[CategoryResponse], status_code=status.HTTP_201_CREATED)
def create_category(
    category_in: CategoryCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Create a new Category or Subcategory with validation and duplicate prevention."""
    target_slug = clean_slug(category_in.slug) if category_in.slug else clean_slug(category_in.name)
    if not target_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category name must produce a valid non-empty slug"
        )
        
    # Duplicate prevention
    existing = db.query(Category).filter(Category.slug == target_slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category with slug '{target_slug}' already exists"
        )
        
    # Validate parent if specified
    if category_in.parent_id is not None:
        parent = db.query(Category).filter(Category.id == category_in.parent_id).first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Parent category with id {category_in.parent_id} does not exist"
            )
            
    img = category_in.image or category_in.image_url
    sort_ord = category_in.sort_order if category_in.sort_order is not None else (category_in.display_order or 0)
    
    new_cat = Category(
        name=category_in.name.strip(),
        slug=target_slug,
        description=category_in.description,
        image=img,
        image_url=img,
        banner=category_in.banner,
        parent_id=category_in.parent_id,
        sort_order=sort_ord,
        display_order=sort_ord,
        is_active=category_in.is_active,
        seo_title=category_in.seo_title,
        seo_description=category_in.seo_description
    )
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    
    return APIResponse(
        success=True,
        message="Category created successfully",
        data=to_category_response(new_cat)
    )

@router.get("/{category_id}", response_model=APIResponse[CategoryResponse])
def get_admin_category_by_id(
    category_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Retrieve single category details by ID for editing or inspection."""
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with id {category_id} not found"
        )
    return APIResponse(success=True, message="Category retrieved", data=to_category_response(cat))

@router.put("/{category_id}", response_model=APIResponse[CategoryResponse])
def update_category(
    category_id: int,
    category_in: CategoryUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update category properties, parent hierarchy, active state, and SEO metadata."""
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with id {category_id} not found"
        )
        
    update_data = category_in.dict(exclude_unset=True)
    
    # 1. Circular dependency prevention
    if "parent_id" in update_data and update_data["parent_id"] is not None:
        target_pid = update_data["parent_id"]
        if target_pid == category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A category cannot be its own parent"
            )
        parent_cat = db.query(Category).filter(Category.id == target_pid).first()
        if not parent_cat:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Parent category with id {target_pid} does not exist"
            )
        # Check that target parent is not a descendant of this category
        curr = parent_cat
        while curr and curr.parent_id is not None:
            if curr.parent_id == category_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot set parent to a descendant category (circular hierarchy)"
                )
            curr = curr.parent

    # 2. Slug update validation & duplicate prevention
    if "slug" in update_data and update_data["slug"]:
        new_slug = clean_slug(update_data["slug"])
        existing = db.query(Category).filter(Category.slug == new_slug, Category.id != category_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category with slug '{new_slug}' already exists"
            )
        update_data["slug"] = new_slug

    # 3. Synchronize image / banner / sort_order aliases
    if "image" in update_data:
        update_data["image_url"] = update_data["image"]
    elif "image_url" in update_data:
        update_data["image"] = update_data["image_url"]
        
    if "sort_order" in update_data and update_data["sort_order"] is not None:
        update_data["display_order"] = update_data["sort_order"]
    elif "display_order" in update_data and update_data["display_order"] is not None:
        update_data["sort_order"] = update_data["display_order"]

    for field, value in update_data.items():
        setattr(cat, field, value)
        
    db.commit()
    db.refresh(cat)
    
    return APIResponse(
        success=True,
        message="Category updated successfully",
        data=to_category_response(cat)
    )

@router.delete("/{category_id}", response_model=APIResponse[bool])
def delete_category(
    category_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete a category with safe verification of products and subcategory preservation."""
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with id {category_id} not found"
        )
        
    # Safe check 1: Products assigned to this category
    if cat.products and len(cat.products) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete category '{cat.name}' because {len(cat.products)} product(s) are associated with it. Please reassign or delete the products first."
        )
        
    # Safe check 2: Subcategories handling - safely re-parent child categories to this category's parent
    for sub in list(cat.subcategories or []):
        sub.parent_id = cat.parent_id
        
    db.commit()
    db.delete(cat)
    db.commit()
    
    return APIResponse(
        success=True,
        message=f"Category '{cat.name}' deleted successfully",
        data=True
    )
