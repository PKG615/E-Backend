from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_admin
from app.schemas.common import APIResponse
from app.schemas.cms import (
    HomepageSectionResponse,
    HomepageSectionCreate,
    HomepageSectionUpdate,
    ReorderRequest,
    StatusToggleRequest
)
from app.services.cms_service import (
    list_admin_sections,
    get_admin_section,
    create_admin_section,
    update_admin_section,
    delete_admin_section,
    reorder_admin_sections,
    toggle_admin_section_status
)

router = APIRouter()

@router.get("/sections", response_model=APIResponse[List[HomepageSectionResponse]])
def get_all_sections(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """List all homepage sections in configured sort order."""
    sections = list_admin_sections(db)
    return APIResponse(
        success=True,
        message="Homepage sections retrieved successfully",
        data=sections
    )

@router.post("/sections", response_model=APIResponse[HomepageSectionResponse], status_code=http_status.HTTP_201_CREATED)
def create_section(
    section_in: HomepageSectionCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Create a new homepage section."""
    created = create_admin_section(db, section_in)
    return APIResponse(
        success=True,
        message="Homepage section created successfully",
        data=created
    )

@router.put("/sections/reorder", response_model=APIResponse[List[HomepageSectionResponse]])
def reorder_sections(
    req: ReorderRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Reorder homepage sections."""
    updated = reorder_admin_sections(db, req)
    return APIResponse(
        success=True,
        message="Sections reordered successfully",
        data=updated
    )

@router.get("/sections/{section_id}", response_model=APIResponse[HomepageSectionResponse])
def get_section_by_id(
    section_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get section details by ID."""
    section = get_admin_section(db, section_id)
    if not section:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Section not found")
    return APIResponse(
        success=True,
        message="Section retrieved successfully",
        data=section
    )

@router.put("/sections/{section_id}", response_model=APIResponse[HomepageSectionResponse])
def update_section(
    section_id: int,
    section_in: HomepageSectionUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Update section properties, configuration, or items."""
    updated = update_admin_section(db, section_id, section_in)
    if not updated:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Section not found")
    return APIResponse(
        success=True,
        message="Homepage section updated successfully",
        data=updated
    )

@router.put("/sections/{section_id}/status", response_model=APIResponse[HomepageSectionResponse])
def toggle_status(
    section_id: int,
    req: StatusToggleRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Toggle visibility status of a homepage section."""
    updated = toggle_admin_section_status(db, section_id, req.is_active)
    if not updated:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Section not found")
    return APIResponse(
        success=True,
        message=f"Section {'activated' if req.is_active else 'deactivated'} successfully",
        data=updated
    )

@router.delete("/sections/{section_id}", response_model=APIResponse[bool])
def delete_section(
    section_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Delete a homepage section."""
    success = delete_admin_section(db, section_id)
    if not success:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Section not found")
    return APIResponse(
        success=True,
        message="Section deleted successfully",
        data=True
    )
