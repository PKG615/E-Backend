from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.models.user import User
from app.models.product import Product
from app.api.v1.endpoints.auth import get_current_admin
from app.schemas.common import APIResponse
from app.schemas.cms import (
    CollectionResponse,
    CollectionCreate,
    CollectionUpdate,
    ReorderRequest,
    StatusToggleRequest
)
from app.services.cms_service import (
    list_admin_collections,
    get_admin_collection,
    create_admin_collection,
    update_admin_collection,
    delete_admin_collection,
    reorder_admin_collections,
    toggle_admin_collection_status
)

router = APIRouter()

@router.get("", response_model=APIResponse[List[CollectionResponse]])
def get_collections(
    search: Optional[str] = Query(None, description="Search by title, slug, description"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """List all collections with product counts and product items."""
    collections = list_admin_collections(db, search=search, is_active=is_active)
    return APIResponse(
        success=True,
        message="Collections retrieved successfully",
        data=collections
    )

@router.get("/products/search", response_model=APIResponse[List[Dict[str, Any]]])
def search_products_for_collection(
    q: Optional[str] = Query("", description="Product name or SKU"),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Bounded product search endpoint for admin collection product assignment."""
    query = db.query(Product).filter(Product.is_active == True)
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        query = query.filter(or_(Product.name.ilike(term), Product.sku.ilike(term)))
    
    products = query.order_by(Product.name.asc()).limit(limit).all()
    result = []
    for p in products:
        img = None
        if p.images and len(p.images) > 0:
            primary_img = next((i for i in p.images if getattr(i, 'is_primary', False)), p.images[0])
            img = primary_img.image_url if hasattr(primary_img, 'image_url') else getattr(primary_img, 'url', None)
        result.append({
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "sku": p.sku,
            "price": float(p.price) if p.price is not None else 0.0,
            "sale_price": float(p.sale_price) if getattr(p, 'sale_price', None) is not None else None,
            "stock": p.stock_quantity if hasattr(p, 'stock_quantity') else 0,
            "is_active": p.is_active,
            "image_url": img
        })

    return APIResponse(
        success=True,
        message="Products retrieved for collection selection",
        data=result
    )

@router.post("", response_model=APIResponse[CollectionResponse], status_code=http_status.HTTP_201_CREATED)
def create_collection(
    data_in: CollectionCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Create a new collection with optional product assignments."""
    created = create_admin_collection(db, data_in)
    return APIResponse(
        success=True,
        message="Collection created successfully",
        data=created
    )

@router.put("/reorder", response_model=APIResponse[List[CollectionResponse]])
def reorder_collections(
    req: ReorderRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Reorder collections display sequence."""
    updated = reorder_admin_collections(db, req)
    return APIResponse(
        success=True,
        message="Collections reordered successfully",
        data=updated
    )

@router.get("/{collection_id}", response_model=APIResponse[CollectionResponse])
def get_collection(
    collection_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get single collection by ID with full product details."""
    coll = get_admin_collection(db, collection_id)
    if not coll:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return APIResponse(
        success=True,
        message="Collection retrieved successfully",
        data=coll
    )

@router.put("/{collection_id}", response_model=APIResponse[CollectionResponse])
def update_collection(
    collection_id: int,
    data_in: CollectionUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Update collection metadata, SEO tags, or product membership."""
    updated = update_admin_collection(db, collection_id, data_in)
    if not updated:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return APIResponse(
        success=True,
        message="Collection updated successfully",
        data=updated
    )

@router.put("/{collection_id}/status", response_model=APIResponse[CollectionResponse])
def toggle_status(
    collection_id: int,
    req: StatusToggleRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Toggle collection active status."""
    updated = toggle_admin_collection_status(db, collection_id, req.is_active)
    if not updated:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return APIResponse(
        success=True,
        message=f"Collection {'activated' if req.is_active else 'deactivated'} successfully",
        data=updated
    )

@router.delete("/{collection_id}", response_model=APIResponse[bool])
def delete_collection(
    collection_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Delete a collection safely."""
    success = delete_admin_collection(db, collection_id)
    if not success:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return APIResponse(
        success=True,
        message="Collection deleted successfully",
        data=True
    )
