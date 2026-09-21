from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.schemas.common import APIResponse

from app.schemas.cms import CollectionResponse

from app.services.cms_service import(
    list_public_collections,
    get_public_collection_by_slug
)

router = APIRouter()

@router.get("", response_model=APIResponse[List[CollectionResponse]])
def get_public_collections(db: Session = Depends(get_db)):
    """Retrieve all active public storefront collections."""
    colls = list_public_collections(db)
    return APIResponse(
        success=True,
        message="Active collections retrieved successfully",
        data=colls
    )

@router.get("/{slug}", response_model=APIResponse[Dict[str, Any]])
def get_public_collection_detail(slug: str, db: Session = Depends(get_db)):
    """Retrieve active storefront collection by slug with live products and SEO details."""
    coll = get_public_collection_by_slug(db, slug)
    if not coll:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Collection '{slug}' not found or inactive."
        )
    return APIResponse(
        success=True,
        message="Collection retrieved successfully",
        data=coll
    )
