from typing import List
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_admin
from app.schemas.common import APIResponse
from app.schemas.product import (
    AttributeSchema,
    AttributeCreate,
    AttributeValueSchema,
    AttributeValueCreate
)
from app.services.variant_service import (
    get_all_attributes,
    create_attribute_service,
    create_attribute_value_service,
    delete_attribute_service
)

router = APIRouter()

@router.get("", response_model=APIResponse[List[AttributeSchema]])
def list_attributes(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """List all global reusable product attributes and their associated values."""
    attrs = get_all_attributes(db)
    return APIResponse(
        success=True,
        message=f"Retrieved {len(attrs)} attributes",
        data=[AttributeSchema.from_orm(a) for a in attrs]
    )

@router.post("", response_model=APIResponse[AttributeSchema], status_code=http_status.HTTP_201_CREATED)
def create_attribute(
    payload: AttributeCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Create a new reusable product attribute (e.g. 'Color', 'Size', 'Storage')."""
    attr = create_attribute_service(payload, db)
    return APIResponse(
        success=True,
        message=f"Attribute '{attr.name}' created successfully",
        data=AttributeSchema.from_orm(attr)
    )

@router.post("/{attribute_id}/values", response_model=APIResponse[AttributeValueSchema], status_code=http_status.HTTP_201_CREATED)
def create_attribute_value(
    attribute_id: int,
    payload: AttributeValueCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Add a new value to an existing attribute (e.g. 'Red' to 'Color', '256GB' to 'Storage')."""
    val = create_attribute_value_service(attribute_id, payload, db)
    return APIResponse(
        success=True,
        message=f"Value '{val.value}' added successfully",
        data=AttributeValueSchema.from_orm(val)
    )

@router.delete("/{attribute_id}", response_model=APIResponse[bool])
def delete_attribute(
    attribute_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete an attribute if not in use by any variants."""
    res = delete_attribute_service(attribute_id, db)
    return APIResponse(
        success=True,
        message="Attribute deleted successfully",
        data=res
    )
