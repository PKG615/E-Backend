from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import APIResponse
from app.schemas.cms import (
    PublicHomepageResponse,
    NewsletterSubscriptionCreate,
    NewsletterSubscriptionResponse
)
from app.services.cms_service import (
    get_public_homepage_data,
    subscribe_newsletter
)

router = APIRouter()

@router.get("", response_model=APIResponse[PublicHomepageResponse])
def get_home_page(db: Session = Depends(get_db)):
    """Retrieve dynamic customer storefront homepage sections and SEO configuration."""
    data = get_public_homepage_data(db)
    return APIResponse(
        success=True,
        message="Storefront homepage retrieved successfully",
        data=data
    )

@router.post("/newsletter/subscribe", response_model=APIResponse[Dict[str, Any]])
def post_newsletter_subscribe(
    req: NewsletterSubscriptionCreate,
    db: Session = Depends(get_db)
):
    """Subscribe email to technical briefs and product drops."""
    if not req.email or "@" not in req.email:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid email format")
    result = subscribe_newsletter(db, req.email)
    return APIResponse(
        success=True,
        message="Subscribed to catalog newsletters successfully",
        data=result
    )
