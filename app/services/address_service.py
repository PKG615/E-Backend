from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import Address
from app.schemas.address import AddressCreate, AddressUpdate

def list_addresses(db: Session, user_id: int) -> List[Address]:
    """Retrieve all addresses for an authenticated user, with default address first."""
    return (
        db.query(Address)
        .filter(Address.user_id == user_id)
        .order_by(Address.is_default.desc(), Address.created_at.desc())
        .all()
    )

def get_address_by_id(db: Session, user_id: int, address_id: int) -> Address:
    """Retrieve a single address and enforce user ownership."""
    address = (
        db.query(Address)
        .filter(Address.id == address_id, Address.user_id == user_id)
        .first()
    )
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Address #{address_id} not found or access denied"
        )
    return address

def create_address(db: Session, user_id: int, payload: AddressCreate) -> Address:
    """Create a new address. If marked as default or is first address, set as default."""
    existing_count = db.query(Address).filter(Address.user_id == user_id).count()
    is_default = payload.is_default or (existing_count == 0)

    if is_default:
        # Clear default flag on existing addresses for this user
        db.query(Address).filter(Address.user_id == user_id).update({"is_default": False})

    street_val = payload.address_line1
    if payload.address_line2:
        street_val = f"{payload.address_line1}, {payload.address_line2}"

    address = Address(
        user_id=user_id,
        full_name=payload.full_name.strip(),
        phone=payload.phone.strip(),
        address_line1=payload.address_line1.strip(),
        address_line2=payload.address_line2.strip() if payload.address_line2 else None,
        landmark=payload.landmark.strip() if payload.landmark else None,
        street=street_val,
        city=payload.city.strip(),
        state=payload.state.strip(),
        postal_code=payload.postal_code.strip(),
        country=payload.country.strip() if payload.country else "India",
        address_type=payload.address_type or "home",
        is_default=is_default
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return address

def update_address(db: Session, user_id: int, address_id: int, payload: AddressUpdate) -> Address:
    """Update an existing address with strict ownership validation."""
    address = get_address_by_id(db, user_id, address_id)

    update_data = payload.dict(exclude_unset=True)

    if "is_default" in update_data and update_data["is_default"]:
        # Unset others
        db.query(Address).filter(Address.user_id == user_id, Address.id != address_id).update({"is_default": False})
        address.is_default = True
    elif "is_default" in update_data and not update_data["is_default"]:
        # If this was default and user turns it off, ensure at least one default remains if multiple exist
        address.is_default = False

    for field, value in update_data.items():
        if field == "is_default":
            continue
        if value is not None and isinstance(value, str):
            setattr(address, field, value.strip())
        elif value is not None:
            setattr(address, field, value)

    # Sync street
    street_parts = [address.address_line1]
    if address.address_line2:
        street_parts.append(address.address_line2)
    address.street = ", ".join(street_parts)

    db.commit()
    db.refresh(address)
    return address

def delete_address(db: Session, user_id: int, address_id: int) -> bool:
    """Delete an address and reassign default if the deleted one was default."""
    address = get_address_by_id(db, user_id, address_id)
    was_default = address.is_default

    db.delete(address)
    db.commit()

    if was_default:
        # Promote the most recently updated remaining address to default
        remaining = (
            db.query(Address)
            .filter(Address.user_id == user_id)
            .order_by(Address.updated_at.desc())
            .first()
        )
        if remaining:
            remaining.is_default = True
            db.commit()

    return True

def set_default_address(db: Session, user_id: int, address_id: int) -> Address:
    """Atomically set an address as the customer's default address."""
    address = get_address_by_id(db, user_id, address_id)
    
    # Reset all user addresses
    db.query(Address).filter(Address.user_id == user_id).update({"is_default": False})
    
    address.is_default = True
    db.commit()
    db.refresh(address)
    return address
