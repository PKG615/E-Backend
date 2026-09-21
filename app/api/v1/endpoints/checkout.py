from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db

from app.models.user import User

from app.api.v1.endpoints.auth import get_current_user

from app.schemas.common import APIResponse

from app.schemas.checkout import(
    CheckoutPreviewRequest,
    CheckoutPreviewResponse
)
from app.services.checkout_service import preview_checkout

router = APIRouter()

@router.post("/preview", response_model=APIResponse[CheckoutPreviewResponse])
def get_checkout_preview(
    payload: CheckoutPreviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Run authoritative validation and calculate preview summary for checkout.
    Does NOT finalize payment or create permanent order records.
    """
    preview_data = preview_checkout(db, current_user, payload.address_id)
    return APIResponse(
        success=True,
        message="Checkout preview generated",
        data=preview_data
    )
