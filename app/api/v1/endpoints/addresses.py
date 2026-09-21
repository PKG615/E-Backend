from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.common import APIResponse
from app.schemas.address import (
    AddressCreate,
    AddressUpdate,
    AddressResponse
)
from app.services.address_service import (
    list_addresses,
    get_address_by_id,
    create_address,
    update_address,
    delete_address,
    set_default_address
)

router = APIRouter()

@router.get("", response_model=APIResponse[List[AddressResponse]])
def get_user_addresses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve all delivery addresses for the authenticated customer.
    """
    addresses = list_addresses(db, current_user.id)
    return APIResponse(
        success=True,
        message=f"Retrieved {len(addresses)} addresses",
        data=[AddressResponse.from_orm(a) for a in addresses]
    )

@router.post("", response_model=APIResponse[AddressResponse], status_code=status.HTTP_201_CREATED)
def add_new_address(
    payload: AddressCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Save a new customer delivery address.
    """
    new_addr = create_address(db, current_user.id, payload)
    return APIResponse(
        success=True,
        message="Delivery address saved successfully",
        data=AddressResponse.from_orm(new_addr)
    )

@router.get("/{address_id}", response_model=APIResponse[AddressResponse])
def get_single_address(
    address_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve details of a specific address.
    """
    addr = get_address_by_id(db, current_user.id, address_id)
    return APIResponse(
        success=True,
        message="Address details retrieved",
        data=AddressResponse.from_orm(addr)
    )

@router.put("/{address_id}", response_model=APIResponse[AddressResponse])
def update_existing_address(
    address_id: int,
    payload: AddressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update an existing delivery address.
    """
    updated_addr = update_address(db, current_user.id, address_id, payload)
    return APIResponse(
        success=True,
        message="Delivery address updated successfully",
        data=AddressResponse.from_orm(updated_addr)
    )

@router.delete("/{address_id}", response_model=APIResponse[dict])
def remove_address(
    address_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a delivery address.
    """
    delete_address(db, current_user.id, address_id)
    return APIResponse(
        success=True,
        message="Delivery address deleted",
        data={"address_id": address_id, "deleted": True}
    )

@router.put("/{address_id}/default", response_model=APIResponse[AddressResponse])
def mark_address_default(
    address_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Set an address as the default delivery address.
    """
    default_addr = set_default_address(db, current_user.id, address_id)
    return APIResponse(
        success=True,
        message="Address marked as default",
        data=AddressResponse.from_orm(default_addr)
    )
