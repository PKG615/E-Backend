from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, desc, asc, func
from fastapi import HTTPException, status as http_status

from app.models.inventory import Inventory, InventoryTransaction
from app.models.product import Product, ProductVariant, ProductImage
from app.models.category import Category, Brand
from app.schemas.inventory import (
    InventoryItemSchema,
    InventorySummarySchema,
    InventoryTransactionSchema,
    InventoryCreate,
    InventoryUpdate,
    InventoryAdjustRequest,
    InventoryDetailResponse
)

def enrich_inventory_item(item: Inventory) -> InventoryItemSchema:
    """Format an Inventory model into an enriched InventoryItemSchema."""
    product = item.product
    variant = item.variant
    
    product_name = product.name if product else None
    product_slug = product.slug if product else None
    category_id = product.category_id if product else None
    category_name = product.category.name if (product and product.category) else None
    brand_id = product.brand_id if product else None
    brand_name = product.brand.name if (product and product.brand) else None
    variant_title = variant.title if variant else None

    # Primary or first image
    product_image = None
    if variant and variant.image_url:
        product_image = variant.image_url
    elif product and product.images:
        primary_imgs = [img.image_url for img in product.images if img.is_primary]
        if primary_imgs:
            product_image = primary_imgs[0]
        else:
            sorted_imgs = sorted(product.images, key=lambda x: (x.sort_order, x.id))
            product_image = sorted_imgs[0].image_url if sorted_imgs else None

    return InventoryItemSchema(
        id=item.id,
        product_id=item.product_id,
        variant_id=item.variant_id,
        sku=item.sku,
        on_hand_quantity=item.on_hand_quantity,
        reserved_quantity=item.reserved_quantity,
        available_quantity=item.available_quantity,
        low_stock_threshold=item.low_stock_threshold,
        is_active=item.is_active,
        stock_status=item.stock_status,
        product_name=product_name,
        product_slug=product_slug,
        product_image=product_image,
        category_id=category_id,
        category_name=category_name,
        brand_id=brand_id,
        brand_name=brand_name,
        variant_title=variant_title,
        created_at=item.created_at,
        updated_at=item.updated_at
    )

def get_inventory_summary(db: Session) -> InventorySummarySchema:
    """Compute aggregate counts and stock totals directly from the database."""
    items = db.query(Inventory).all()
    total_items = len(items)
    in_stock_count = 0
    low_stock_count = 0
    out_of_stock_count = 0
    total_on_hand = 0
    total_reserved = 0

    for it in items:
        total_on_hand += it.on_hand_quantity
        total_reserved += it.reserved_quantity
        status = it.stock_status
        if status == "IN_STOCK":
            in_stock_count += 1
        elif status == "LOW_STOCK":
            low_stock_count += 1
        else:
            out_of_stock_count += 1

    return InventorySummarySchema(
        total_items=total_items,
        in_stock_count=in_stock_count,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        total_on_hand=total_on_hand,
        total_reserved=total_reserved
    )

def list_inventory(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    brand_id: Optional[int] = None,
    stock_status: Optional[str] = None,
    is_active: Optional[bool] = None,
    sort_by: str = "id",
    sort_order: str = "desc"
) -> Tuple[List[InventoryItemSchema], int]:
    """Search, filter, and paginate inventory items."""
    query = db.query(Inventory).options(
        joinedload(Inventory.product).joinedload(Product.category),
        joinedload(Inventory.product).joinedload(Product.brand),
        joinedload(Inventory.product).joinedload(Product.images),
        joinedload(Inventory.variant)
    )

    # Search filter
    if search:
        s = f"%{search.strip().lower()}%"
        query = query.join(Inventory.product).outerjoin(Inventory.variant).filter(
            or_(
                func.lower(Inventory.sku).like(s),
                func.lower(Product.name).like(s),
                func.lower(Product.sku).like(s),
                func.lower(ProductVariant.title).like(s),
                func.lower(ProductVariant.sku).like(s)
            )
        )

    # Category filter
    if category_id:
        if not search:
            query = query.join(Inventory.product)
        query = query.filter(Product.category_id == category_id)

    # Brand filter
    if brand_id:
        if not search and not category_id:
            query = query.join(Inventory.product)
        query = query.filter(Product.brand_id == brand_id)

    # Active filter
    if is_active is not None:
        query = query.filter(Inventory.is_active == is_active)

    # Stock status filter
    if stock_status:
        st = stock_status.upper()
        if st == "OUT_OF_STOCK":
            query = query.filter(Inventory.available_quantity <= 0)
        elif st == "LOW_STOCK":
            query = query.filter(
                Inventory.available_quantity > 0,
                Inventory.available_quantity <= Inventory.low_stock_threshold
            )
        elif st == "IN_STOCK":
            query = query.filter(Inventory.available_quantity > Inventory.low_stock_threshold)

    # Sorting
    sort_col = Inventory.id
    if sort_by == "sku":
        sort_col = Inventory.sku
    elif sort_by == "on_hand":
        sort_col = Inventory.on_hand_quantity
    elif sort_by == "available":
        sort_col = Inventory.available_quantity
    elif sort_by == "updated_at":
        sort_col = Inventory.updated_at

    if sort_order.lower() == "asc":
        query = query.order_by(asc(sort_col))
    else:
        query = query.order_by(desc(sort_col))

    total = query.count()
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()

    return [enrich_inventory_item(it) for it in items], total

def get_inventory_detail(db: Session, inventory_id: int) -> InventoryDetailResponse:
    """Fetch complete inventory item with historical ledger transactions."""
    item = db.query(Inventory).options(
        joinedload(Inventory.product).joinedload(Product.category),
        joinedload(Inventory.product).joinedload(Product.brand),
        joinedload(Inventory.product).joinedload(Product.images),
        joinedload(Inventory.variant),
        joinedload(Inventory.transactions)
    ).filter(Inventory.id == inventory_id).first()

    if not item:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Inventory record #{inventory_id} not found"
        )

    base = enrich_inventory_item(item)
    txs = [InventoryTransactionSchema.from_orm(t) for t in (item.transactions or [])]

    return InventoryDetailResponse(
        **base.dict(),
        transactions=txs
    )

def create_inventory_record(db: Session, payload: InventoryCreate, created_by: str = "system") -> InventoryItemSchema:
    """
    Create a new inventory record for a product or variant.
    Enforces product/variant validation and uniqueness.
    """
    # 1. Validate product existence
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Product #{payload.product_id} not found"
        )

    # 2. Validate variant if provided
    variant = None
    if payload.variant_id is not None:
        variant = db.query(ProductVariant).filter(ProductVariant.id == payload.variant_id).first()
        if not variant:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Variant #{payload.variant_id} not found"
            )
        # CRITICAL VALIDATION: variant must belong to specified product
        if variant.product_id != product.id:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Variant #{variant.id} belongs to Product #{variant.product_id}, not Product #{product.id}"
            )

        # Check existing inventory for this variant
        existing_v = db.query(Inventory).filter(Inventory.variant_id == variant.id).first()
        if existing_v:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"Inventory record already exists for Variant #{variant.id} (SKU: {existing_v.sku})"
            )
    else:
        # Check existing non-variant inventory for this product
        existing_p = db.query(Inventory).filter(
            Inventory.product_id == product.id,
            Inventory.variant_id == None
        ).first()
        if existing_p:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"Base inventory record already exists for Product #{product.id} (SKU: {existing_p.sku})"
            )

    # Check unique SKU
    sku_conflict = db.query(Inventory).filter(Inventory.sku == payload.sku).first()
    if sku_conflict:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"Inventory record with SKU '{payload.sku}' already exists"
        )

    available = payload.on_hand_quantity - payload.reserved_quantity
    new_inv = Inventory(
        product_id=product.id,
        variant_id=payload.variant_id,
        sku=payload.sku,
        on_hand_quantity=payload.on_hand_quantity,
        reserved_quantity=payload.reserved_quantity,
        available_quantity=available,
        low_stock_threshold=payload.low_stock_threshold,
        is_active=payload.is_active
    )
    db.add(new_inv)
    db.flush()

    # Initial transaction
    tx = InventoryTransaction(
        inventory_id=new_inv.id,
        transaction_type="RECEIVE" if payload.on_hand_quantity > 0 else "ADJUSTMENT",
        quantity_change=payload.on_hand_quantity,
        quantity_before=0,
        quantity_after=payload.on_hand_quantity,
        reason="Initial inventory creation",
        created_by=created_by
    )
    db.add(tx)

    # Sync back to product / variant
    if variant:
        variant.stock = available
        # Sync parent product stock as sum of all variant stocks
        sync_parent_product_stock_from_variants(db, product.id)
    else:
        product.stock = available

    db.commit()
    db.refresh(new_inv)
    return enrich_inventory_item(new_inv)

def update_inventory_record(db: Session, inventory_id: int, payload: InventoryUpdate) -> InventoryItemSchema:
    """Update inventory threshold or active status."""
    inv = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if not inv:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Inventory record #{inventory_id} not found"
        )

    if payload.low_stock_threshold is not None:
        inv.low_stock_threshold = payload.low_stock_threshold
    if payload.is_active is not None:
        inv.is_active = payload.is_active

    db.commit()
    db.refresh(inv)
    return enrich_inventory_item(inv)

def adjust_inventory_quantity(
    db: Session,
    inventory_id: int,
    payload: InventoryAdjustRequest,
    performed_by: str = "admin"
) -> Tuple[InventoryItemSchema, InventoryTransactionSchema]:
    """
    Atomic transaction-safe stock adjustment with ledger traceability.
    Prevents negative inventory and preserves audit history.
    """
    # 1. Fetch with row-level locking
    # with_for_update() ensures atomic execution in PostgreSQL
    inv = db.query(Inventory).filter(Inventory.id == inventory_id).with_for_update().first()
    if not inv:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Inventory record #{inventory_id} not found"
        )

    qty_change = payload.quantity_change
    qty_before = inv.on_hand_quantity
    qty_after = qty_before + qty_change

    if qty_after < 0:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient inventory. Current on-hand is {qty_before}, cannot reduce by {abs(qty_change)}."
        )

    new_available = qty_after - inv.reserved_quantity
    if new_available < 0:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Adjustment would violate reserved stock. Available cannot be negative (On-hand: {qty_after}, Reserved: {inv.reserved_quantity})."
        )

    # 2. Determine transaction type
    tx_type = "RECEIVE" if qty_change > 0 else "ADJUSTMENT"

    # 3. Update inventory
    inv.on_hand_quantity = qty_after
    inv.available_quantity = new_available

    # 4. Insert transaction ledger entry
    tx = InventoryTransaction(
        inventory_id=inv.id,
        transaction_type=tx_type,
        quantity_change=qty_change,
        quantity_before=qty_before,
        quantity_after=qty_after,
        reason=payload.reason.strip(),
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        notes=payload.notes.strip() if payload.notes else None,
        created_by=performed_by
    )
    db.add(tx)

    # 5. Authoritative sync to Product / Variant
    if inv.variant_id:
        variant = db.query(ProductVariant).filter(ProductVariant.id == inv.variant_id).first()
        if variant:
            variant.stock = new_available
        sync_parent_product_stock_from_variants(db, inv.product_id)
    else:
        product = db.query(Product).filter(Product.id == inv.product_id).first()
        if product:
            product.stock = new_available

    db.commit()
    db.refresh(inv)
    db.refresh(tx)

    return enrich_inventory_item(inv), InventoryTransactionSchema.from_orm(tx)

def get_inventory_transactions(
    db: Session,
    inventory_id: int,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[InventoryTransactionSchema], int]:
    """Retrieve chronological ledger transactions for an inventory record."""
    inv = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if not inv:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Inventory record #{inventory_id} not found"
        )

    q = db.query(InventoryTransaction).filter(
        InventoryTransaction.inventory_id == inventory_id
    ).order_by(desc(InventoryTransaction.created_at), desc(InventoryTransaction.id))

    total = q.count()
    offset = (page - 1) * page_size
    items = q.offset(offset).limit(page_size).all()

    return [InventoryTransactionSchema.from_orm(t) for t in items], total

def sync_parent_product_stock_from_variants(db: Session, product_id: int) -> None:
    """Calculates total available stock across all active variants and syncs to Product.stock."""
    sum_stock = db.query(func.sum(Inventory.available_quantity)).filter(
        Inventory.product_id == product_id,
        Inventory.variant_id != None,
        Inventory.is_active == True
    ).scalar() or 0

    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        product.stock = int(sum_stock)

def get_authoritative_product_stock(db: Session, product_id: int) -> Tuple[int, bool]:
    """
    Returns (available_stock, in_stock) from the authoritative inventory table.
    """
    # Check if product has variants
    variant_invs = db.query(Inventory).filter(
        Inventory.product_id == product_id,
        Inventory.variant_id != None,
        Inventory.is_active == True
    ).all()

    if variant_invs:
        total_available = sum(v.available_quantity for v in variant_invs)
        return total_available, total_available > 0

    # Non-variant product
    base_inv = db.query(Inventory).filter(
        Inventory.product_id == product_id,
        Inventory.variant_id == None,
        Inventory.is_active == True
    ).first()

    if base_inv:
        return base_inv.available_quantity, base_inv.available_quantity > 0

    return 0, False

def get_authoritative_variant_stock(db: Session, variant_id: int) -> Tuple[int, bool]:
    """
    Returns (available_stock, in_stock) for a specific variant from the authoritative inventory table.
    """
    var_inv = db.query(Inventory).filter(
        Inventory.variant_id == variant_id,
        Inventory.is_active == True
    ).first()

    if var_inv:
        return var_inv.available_quantity, var_inv.available_quantity > 0

    return 0, False
