from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_admin
from app.schemas.common import APIResponse, PaginatedData
from app.schemas.inventory import (
    InventoryItemSchema,
    InventorySummarySchema,
    InventoryTransactionSchema,
    InventoryCreate,
    InventoryUpdate,
    InventoryAdjustRequest,
    InventoryDetailResponse
)
from app.services.inventory_service import (
    get_inventory_summary,
    list_inventory,
    get_inventory_detail,
    create_inventory_record,
    update_inventory_record,
    adjust_inventory_quantity,
    get_inventory_transactions
)

router = APIRouter()

@router.get("/summary", response_model=APIResponse[InventorySummarySchema])
def get_summary(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Retrieve summary inventory counts (total, in stock, low stock, out of stock)."""
    summary = get_inventory_summary(db)
    return APIResponse(
        success=True,
        message="Inventory summary retrieved successfully",
        data=summary
    )

@router.get("", response_model=APIResponse[PaginatedData[InventoryItemSchema]])
def get_inventory_list(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by SKU, product name, or variant title"),
    category_id: Optional[int] = Query(None, description="Filter by Category ID"),
    brand_id: Optional[int] = Query(None, description="Filter by Brand ID"),
    stock_status: Optional[str] = Query(None, description="Filter: IN_STOCK, LOW_STOCK, OUT_OF_STOCK"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    sort_by: str = Query("id", description="Sort by: id, sku, on_hand, available, updated_at"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """List inventory items with search, filters, and pagination."""
    items, total = list_inventory(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        category_id=category_id,
        brand_id=brand_id,
        stock_status=stock_status,
        is_active=is_active,
        sort_by=sort_by,
        sort_order=sort_order
    )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return APIResponse(
        success=True,
        message="Inventory list retrieved successfully",
        data=PaginatedData(
            items=items,
            total=total,
            page=page,
            limit=page_size,
            total_pages=total_pages
        )
    )

@router.get("/{inventory_id}", response_model=APIResponse[InventoryDetailResponse])
def get_inventory(
    inventory_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Retrieve detailed inventory item including recent ledger transactions."""
    detail = get_inventory_detail(db, inventory_id)
    return APIResponse(
        success=True,
        message=f"Inventory record #{inventory_id} retrieved",
        data=detail
    )

@router.post("", response_model=APIResponse[InventoryItemSchema], status_code=http_status.HTTP_201_CREATED)
def create_inventory(
    payload: InventoryCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Create a new authoritative inventory record for a product or variant."""
    created_by = getattr(admin, 'email', None) or getattr(admin, 'full_name', 'admin')
    item = create_inventory_record(db, payload, created_by=created_by)
    return APIResponse(
        success=True,
        message=f"Inventory created successfully for SKU {item.sku}",
        data=item
    )

@router.put("/{inventory_id}", response_model=APIResponse[InventoryItemSchema])
def update_inventory(
    inventory_id: int,
    payload: InventoryUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Update inventory low stock threshold or active status."""
    item = update_inventory_record(db, inventory_id, payload)
    return APIResponse(
        success=True,
        message=f"Inventory record #{inventory_id} updated",
        data=item
    )

@router.post("/{inventory_id}/adjust", response_model=APIResponse[InventoryItemSchema])
def adjust_inventory(
    inventory_id: int,
    payload: InventoryAdjustRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Perform an atomic stock adjustment on an inventory record.
    Creates an immutable audit transaction ledger entry.
    """
    performed_by = getattr(admin, 'email', None) or getattr(admin, 'full_name', 'admin')
    item, tx = adjust_inventory_quantity(
        db=db,
        inventory_id=inventory_id,
        payload=payload,
        performed_by=performed_by
    )

    action_text = f"increased by {payload.quantity_change}" if payload.quantity_change > 0 else f"decreased by {abs(payload.quantity_change)}"
    return APIResponse(
        success=True,
        message=f"Stock {action_text} units. New available quantity: {item.available_quantity}",
        data=item
    )

@router.get("/{inventory_id}/transactions", response_model=APIResponse[PaginatedData[InventoryTransactionSchema]])
def get_transactions(
    inventory_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Retrieve full chronological transaction ledger for an inventory record."""
    txs, total = get_inventory_transactions(
        db=db,
        inventory_id=inventory_id,
        page=page,
        page_size=page_size
    )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return APIResponse(
        success=True,
        message=f"Transactions for inventory #{inventory_id} retrieved",
        data=PaginatedData(
            items=txs,
            total=total,
            page=page,
            limit=page_size,
            total_pages=total_pages
        )
    )
