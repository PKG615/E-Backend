import re
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Form, status as http_status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc, asc

from app.core.database import get_db
from app.models.product import Product, ProductImage, ProductVariant
from app.models.inventory import Inventory, InventoryTransaction
from app.models.category import Category, Brand
from app.models.order import OrderItem, CartItem
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_admin
from app.schemas.product import (
    ProductCreate, 
    ProductUpdate, 
    ProductResponse, 
    ProductImageSchema,
    ProductImageCreate,
    ProductImageUpdate,
    ProductImageReorderRequest,
    ProductVariantSchema,
    ProductVariantCreate,
    ProductVariantUpdate,
    ProductVariantReorderRequest
)
from app.schemas.common import APIResponse, PaginatedData
from app.api.v1.endpoints.products import format_product_response
from app.services.image_service import (
    get_product_images,
    add_product_image,
    upload_product_image,
    update_product_image,
    set_primary_image,
    reorder_product_images,
    delete_product_image
)
from app.services.variant_service import (
    get_product_variants,
    get_variant_by_id,
    create_product_variant,
    update_product_variant,
    delete_product_variant,
    reorder_product_variants,
    get_product_scoped_attributes,
    format_variant_response
)

router = APIRouter()

class PriceUpdateSchema(BaseModel):
    price: float = Field(..., gt=0, description="Selling price")
    mrp: Optional[float] = Field(None, gt=0, description="Maximum retail price")
    discount_percent: Optional[float] = None

    @validator('mrp')
    def validate_mrp(cls, v, values):
        if v is not None:
            price = values.get('price')
            if price is not None and v < price:
                raise ValueError('MRP must be greater than or equal to selling price')
        return v

class StockUpdateSchema(BaseModel):
    stock: int = Field(..., ge=0, description="Stock quantity")

def generate_unique_slug(name: str, db: Session, current_id: Optional[int] = None) -> str:
    """Generate a clean, URL-safe and unique product slug."""
    base_slug = re.sub(r'[^a-zA-Z0-9]+', '-', name.strip().lower()).strip('-')
    if not base_slug:
        base_slug = "product"
    slug = base_slug
    counter = 1
    while True:
        query = db.query(Product).filter(Product.slug == slug)
        if current_id:
            query = query.filter(Product.id != current_id)
        if not query.first():
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1

@router.get("", response_model=APIResponse[PaginatedData[ProductResponse]])
def list_admin_products(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    brand_id: Optional[int] = None,
    status: Optional[str] = Query(None, description="'all', 'active', 'inactive', 'draft'"),
    is_featured: Optional[bool] = None,
    is_new_arrival: Optional[bool] = None,
    is_best_seller: Optional[bool] = None,
    stock_filter: Optional[str] = Query(None, description="'all', 'in_stock', 'out_of_stock', 'low_stock'"),
    sort_by: Optional[str] = None,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Admin Product List API.
    Server-authoritative, full-featured search, filters, pagination, and sorting.
    """
    query = db.query(Product).options(
        joinedload(Product.category),
        joinedload(Product.brand),
        joinedload(Product.images),
        joinedload(Product.variants)
    )

    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Product.name.ilike(search_term),
                Product.description.ilike(search_term),
                Product.short_description.ilike(search_term),
                Product.sku.ilike(search_term)
            )
        )

    if category_id is not None and category_id > 0:
        query = query.filter(Product.category_id == category_id)

    if brand_id is not None and brand_id > 0:
        query = query.filter(Product.brand_id == brand_id)

    # Status filter
    if status and status.lower() != "all":
        st = status.strip().lower()
        if st in ('active', 'inactive', 'draft'):
            query = query.filter(Product.status == st)

    # Flags
    if is_featured is not None:
        query = query.filter(Product.is_featured == is_featured)
    if is_new_arrival is not None:
        query = query.filter(Product.is_new_arrival == is_new_arrival)
    if is_best_seller is not None:
        query = query.filter(Product.is_best_seller == is_best_seller)

    # Stock filter
    if stock_filter and stock_filter != "all":
        if stock_filter == "in_stock":
            query = query.filter(Product.stock > 0)
        elif stock_filter == "out_of_stock":
            query = query.filter(Product.stock <= 0)
        elif stock_filter == "low_stock":
            query = query.filter(Product.stock > 0, Product.stock <= 5)

    # Sorting
    if sort_by == "price_asc":
        query = query.order_by(asc(Product.price))
    elif sort_by == "price_desc":
        query = query.order_by(desc(Product.price))
    elif sort_by == "name_asc":
        query = query.order_by(asc(Product.name))
    elif sort_by == "stock_asc":
        query = query.order_by(asc(Product.stock))
    else:
        query = query.order_by(desc(Product.created_at))

    total = query.count()
    offset = (page - 1) * limit
    products = query.offset(offset).limit(limit).all()

    items = [format_product_response(p) for p in products]
    total_pages = (total + limit - 1) // limit if total > 0 else 1

    return APIResponse(
        success=True,
        message="Admin products retrieved successfully",
        data=PaginatedData(
            items=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages
        )
    )

@router.get("/{product_id}", response_model=APIResponse[ProductResponse])
def get_admin_product(
    product_id: int, 
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get single product detail for admin inspection or editing."""
    product = db.query(Product).options(
        joinedload(Product.category),
        joinedload(Product.brand),
        joinedload(Product.images),
        joinedload(Product.variants)
    ).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    return APIResponse(
        success=True,
        message="Product details retrieved",
        data=format_product_response(product)
    )

@router.post("", response_model=APIResponse[ProductResponse], status_code=http_status.HTTP_201_CREATED)
def create_product(
    product_in: ProductCreate, 
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new product with complete server-authoritative validations:
    - SKU uniqueness
    - Slug normalization & uniqueness
    - Category existence & active verification
    - Brand existence verification
    - Price & MRP rule (mrp >= price > 0)
    - Authoritative discount calculation
    """
    # 1. Validate Category
    category = db.query(Category).filter(Category.id == product_in.category_id).first()
    if not category:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Category with ID {product_in.category_id} does not exist"
        )
    if not category.is_active:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Category '{category.name}' is currently inactive. Products cannot be added to inactive categories."
        )

    # 2. Validate Brand if provided
    if product_in.brand_id:
        brand = db.query(Brand).filter(Brand.id == product_in.brand_id).first()
        if not brand:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Brand with ID {product_in.brand_id} does not exist"
            )

    # 3. Validate SKU
    sku_val = (product_in.sku or f"SKU-{re.sub(r'[^A-Z0-9]', '', product_in.name.upper())[:6]}-{int(db.query(Product).count()) + 1}").strip().upper()
    existing_sku = db.query(Product).filter(Product.sku == sku_val).first()
    if existing_sku:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Product with SKU '{sku_val}' already exists. SKU must be unique."
        )

    # 4. Slug resolution and uniqueness
    if product_in.slug:
        slug_val = re.sub(r'[^a-zA-Z0-9-_]', '-', product_in.slug.strip().lower())
        slug_val = re.sub(r'-+', '-', slug_val).strip('-')
        existing_slug = db.query(Product).filter(Product.slug == slug_val).first()
        if existing_slug:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Product with slug '{slug_val}' already exists. Please choose a distinct slug."
            )
    else:
        slug_val = generate_unique_slug(product_in.name, db)

    # 5. Price & Discount rules
    selling_price = float(product_in.price)
    mrp = float(product_in.mrp)
    if selling_price <= 0:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Selling price must be greater than zero"
        )
    if mrp < selling_price:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"MRP (₹{mrp}) cannot be less than selling price (₹{selling_price})"
        )

    # Authoritative discount calculation
    calculated_discount = round(((mrp - selling_price) / mrp) * 100, 2) if mrp > 0 else 0.0

    # 6. Status and visibility synchronization
    status_val = (product_in.status or "active").strip().lower()
    is_active_val = (status_val == "active")

    warranty_val = product_in.warranty or product_in.warranty_info
    seo_t = product_in.seo_title or product_in.meta_title or product_in.name
    seo_d = product_in.seo_description or product_in.meta_description or product_in.short_description

    product = Product(
        name=product_in.name.strip(),
        slug=slug_val,
        sku=sku_val,
        description=product_in.description.strip(),
        short_description=product_in.short_description.strip() if product_in.short_description else None,
        category_id=product_in.category_id,
        brand_id=product_in.brand_id,
        price=selling_price,
        mrp=mrp,
        discount_percent=calculated_discount,
        tax_percent=float(product_in.tax_percent or 18.0),
        stock=int(product_in.stock or 0),
        status=status_val,
        is_active=is_active_val,
        is_featured=bool(product_in.is_featured),
        is_new_arrival=bool(product_in.is_new_arrival),
        is_best_seller=bool(product_in.is_best_seller),
        is_flash_sale=bool(product_in.is_flash_sale),
        sort_order=int(product_in.sort_order or 0),
        weight=product_in.weight,
        length=product_in.length,
        width=product_in.width,
        height=product_in.height,
        video_url=product_in.video_url,
        warranty=warranty_val,
        warranty_info=warranty_val,
        return_policy=product_in.return_policy or "7-day return policy",
        specifications=product_in.specifications or {},
        attributes=product_in.attributes or {},
        seo_title=seo_t,
        seo_description=seo_d,
        meta_title=seo_t,
        meta_description=seo_d
    )
    db.add(product)
    db.flush()

    # Images
    for idx, img_in in enumerate(product_in.images):
        img = ProductImage(
            product_id=product.id,
            image_url=img_in.image_url,
            alt_text=img_in.alt_text or product.name,
            is_primary=img_in.is_primary or (idx == 0),
            display_order=img_in.display_order or idx
        )
        db.add(img)

    # Variants
    created_variants = []
    for v_in in product_in.variants:
        var = ProductVariant(
            product_id=product.id,
            sku=v_in.sku,
            title=v_in.title,
            price=v_in.price,
            mrp=v_in.mrp,
            stock=v_in.stock,
            attributes=v_in.attributes,
            image_url=v_in.image_url,
            is_active=v_in.is_active
        )
        db.add(var)
        created_variants.append(var)
    db.flush()

    performed_by = getattr(current_admin, 'email', None) or 'admin'
    if created_variants:
        for var in created_variants:
            inv = Inventory(
                product_id=product.id,
                variant_id=var.id,
                sku=var.sku,
                on_hand_quantity=var.stock,
                reserved_quantity=0,
                available_quantity=var.stock,
                low_stock_threshold=5,
                is_active=var.is_active
            )
            db.add(inv)
            db.flush()
            if var.stock > 0:
                tx = InventoryTransaction(
                    inventory_id=inv.id,
                    transaction_type="RECEIVE",
                    quantity_change=var.stock,
                    quantity_before=0,
                    quantity_after=var.stock,
                    reason="Initial variant creation stock",
                    created_by=performed_by
                )
                db.add(tx)
        product.stock = sum(v.stock for v in created_variants if v.is_active)
    else:
        # Non-variant product base inventory
        inv = Inventory(
            product_id=product.id,
            variant_id=None,
            sku=product.sku,
            on_hand_quantity=product.stock,
            reserved_quantity=0,
            available_quantity=product.stock,
            low_stock_threshold=5,
            is_active=product.is_active
        )
        db.add(inv)
        db.flush()
        if product.stock > 0:
            tx = InventoryTransaction(
                inventory_id=inv.id,
                transaction_type="RECEIVE",
                quantity_change=product.stock,
                quantity_before=0,
                quantity_after=product.stock,
                reason="Initial product creation stock",
                created_by=performed_by
            )
            db.add(tx)

    db.commit()
    db.refresh(product)
    return APIResponse(
        success=True, 
        message=f"Product '{product.name}' created successfully", 
        data=format_product_response(product)
    )

@router.put("/{product_id}", response_model=APIResponse[ProductResponse])
def update_product(
    product_id: int, 
    product_in: ProductUpdate, 
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Update an existing product with validation on changed fields.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    update_data = product_in.dict(exclude_unset=True)

    # Validate SKU uniqueness if SKU is being updated
    if "sku" in update_data and update_data["sku"]:
        new_sku = update_data["sku"].strip().upper()
        existing = db.query(Product).filter(Product.sku == new_sku, Product.id != product_id).first()
        if existing:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Product with SKU '{new_sku}' already exists"
            )
        update_data["sku"] = new_sku

    # Validate Slug uniqueness if slug is being updated
    if "slug" in update_data and update_data["slug"]:
        new_slug = re.sub(r'[^a-zA-Z0-9-_]', '-', update_data["slug"].strip().lower())
        new_slug = re.sub(r'-+', '-', new_slug).strip('-')
        existing = db.query(Product).filter(Product.slug == new_slug, Product.id != product_id).first()
        if existing:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Product with slug '{new_slug}' already exists"
            )
        update_data["slug"] = new_slug

    # Validate Category if changed
    if "category_id" in update_data and update_data["category_id"] is not None:
        cat = db.query(Category).filter(Category.id == update_data["category_id"]).first()
        if not cat:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Category with ID {update_data['category_id']} does not exist"
            )
        if not cat.is_active:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Category '{cat.name}' is currently inactive"
            )

    # Validate Brand if changed
    if "brand_id" in update_data and update_data["brand_id"] is not None:
        brand = db.query(Brand).filter(Brand.id == update_data["brand_id"]).first()
        if not brand:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Brand with ID {update_data['brand_id']} does not exist"
            )

    # Validate Price & MRP relationship
    next_price = float(update_data.get("price", product.price))
    next_mrp = float(update_data.get("mrp", product.mrp))

    if next_price <= 0:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Selling price must be greater than zero"
        )
    if next_mrp < next_price:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"MRP (₹{next_mrp}) cannot be less than selling price (₹{next_price})"
        )

    # Recalculate discount
    update_data["discount_percent"] = round(((next_mrp - next_price) / next_mrp) * 100, 2) if next_mrp > 0 else 0.0

    # Synchronize status and is_active
    if "status" in update_data and update_data["status"]:
        st = update_data["status"].strip().lower()
        update_data["status"] = st
        update_data["is_active"] = (st == "active")
    elif "is_active" in update_data:
        update_data["status"] = "active" if update_data["is_active"] else "inactive"

    # Synchronize warranty
    if "warranty" in update_data:
        update_data["warranty_info"] = update_data["warranty"]
    elif "warranty_info" in update_data:
        update_data["warranty"] = update_data["warranty_info"]

    # Synchronize SEO
    if "seo_title" in update_data:
        update_data["meta_title"] = update_data["seo_title"]
    elif "meta_title" in update_data:
        update_data["seo_title"] = update_data["meta_title"]

    if "seo_description" in update_data:
        update_data["meta_description"] = update_data["seo_description"]
    elif "meta_description" in update_data:
        update_data["seo_description"] = update_data["meta_description"]

    for field, value in update_data.items():
        if hasattr(product, field):
            setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return APIResponse(
        success=True, 
        message="Product updated successfully", 
        data=format_product_response(product)
    )

@router.put("/{product_id}/price", response_model=APIResponse[ProductResponse])
def update_product_price(
    product_id: int, 
    payload: PriceUpdateSchema, 
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Quick update for product price & MRP."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    next_price = float(payload.price)
    next_mrp = float(payload.mrp) if payload.mrp is not None else float(product.mrp)

    if next_mrp < next_price:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"MRP (₹{next_mrp}) cannot be less than selling price (₹{next_price})"
        )

    product.price = next_price
    product.mrp = next_mrp
    product.discount_percent = round(((next_mrp - next_price) / next_mrp) * 100, 2) if next_mrp > 0 else 0.0

    db.commit()
    db.refresh(product)
    return APIResponse(
        success=True, 
        message=f"Product price updated to ₹{product.price}", 
        data=format_product_response(product)
    )

@router.put("/{product_id}/stock", response_model=APIResponse[ProductResponse])
def update_product_stock(
    product_id: int, 
    payload: StockUpdateSchema, 
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Quick update for product stock inventory."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    # Sync with authoritative inventory record
    performed_by = getattr(current_admin, 'email', None) or 'admin'
    inv = db.query(Inventory).filter(
        Inventory.product_id == product_id,
        Inventory.variant_id == None
    ).first()

    if not inv:
        inv = Inventory(
            product_id=product.id,
            variant_id=None,
            sku=product.sku,
            on_hand_quantity=payload.stock,
            reserved_quantity=0,
            available_quantity=payload.stock,
            low_stock_threshold=5,
            is_active=product.is_active
        )
        db.add(inv)
        db.flush()
        tx = InventoryTransaction(
            inventory_id=inv.id,
            transaction_type="RECEIVE" if payload.stock > 0 else "ADJUSTMENT",
            quantity_change=payload.stock,
            quantity_before=0,
            quantity_after=payload.stock,
            reason="Inventory created via product stock update",
            created_by=performed_by
        )
        db.add(tx)
    else:
        delta = payload.stock - inv.on_hand_quantity
        if delta != 0:
            tx = InventoryTransaction(
                inventory_id=inv.id,
                transaction_type="RECEIVE" if delta > 0 else "ADJUSTMENT",
                quantity_change=delta,
                quantity_before=inv.on_hand_quantity,
                quantity_after=payload.stock,
                reason="Stock quick-update from product catalog",
                created_by=performed_by
            )
            db.add(tx)
            inv.on_hand_quantity = payload.stock
            inv.available_quantity = payload.stock - inv.reserved_quantity

    product.stock = payload.stock
    db.commit()
    db.refresh(product)
    return APIResponse(
        success=True, 
        message=f"Product stock updated to {product.stock} units", 
        data=format_product_response(product)
    )

@router.delete("/{product_id}", response_model=APIResponse[bool])
def delete_product(
    product_id: int, 
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Safely delete a product.
    Referential Protection: Prevents deleting products referenced in customer orders.
    Cleans up associated cart items before deletion.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    # Check order dependencies
    orders_count = db.query(OrderItem).filter(OrderItem.product_id == product_id).count()
    if orders_count > 0:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot delete product '{product.name}' because it is part of {orders_count} customer order(s). "
                f"To prevent breaking order histories, please change its status to 'inactive' or 'draft' instead."
            )
        )

    # Safe to remove from active carts
    db.query(CartItem).filter(CartItem.product_id == product_id).delete()

    db.delete(product)
    db.commit()
    return APIResponse(
        success=True, 
        message=f"Product '{product.name}' deleted successfully", 
        data=True
    )

# ==========================================
# PRODUCT IMAGES MANAGEMENT (CHECKPOINT 04)
# ==========================================

@router.get("/{product_id}/images", response_model=APIResponse[List[ProductImageSchema]])
def list_product_images(
    product_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    List all images for a product in deterministic order (sort_order ASC, id ASC).
    Requires Admin authentication.
    """
    images = get_product_images(product_id=product_id, db=db)
    return APIResponse(
        success=True,
        message=f"Retrieved {len(images)} images for product {product_id}",
        data=[ProductImageSchema.from_orm(img) for img in images]
    )

@router.post("/{product_id}/images", response_model=APIResponse[ProductImageSchema], status_code=http_status.HTTP_201_CREATED)
def create_product_image(
    product_id: int,
    payload: ProductImageCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Add a new image to a product by URL/reference.
    Transactionally enforces primary image rules and non-negative sort order.
    """
    new_image = add_product_image(product_id=product_id, payload=payload, db=db)
    return APIResponse(
        success=True,
        message="Product image added successfully",
        data=ProductImageSchema.from_orm(new_image)
    )

@router.post("/{product_id}/images/upload", response_model=APIResponse[ProductImageSchema], status_code=http_status.HTTP_201_CREATED)
async def upload_product_image_endpoint(
    product_id: int,
    file: UploadFile = File(...),
    alt_text: Optional[str] = Form(None),
    is_primary: bool = Form(False),
    sort_order: int = Form(0),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Upload an image file directly for a product.
    Validates file MIME type, magic bytes, extension, and file size (<= 5MB).
    Saves file with safe sanitized naming and stores metadata in PostgreSQL.
    """
    new_image = await upload_product_image(
        product_id=product_id,
        file=file,
        alt_text=alt_text,
        is_primary=is_primary,
        sort_order=sort_order,
        db=db
    )
    return APIResponse(
        success=True,
        message="Product image uploaded successfully",
        data=ProductImageSchema.from_orm(new_image)
    )

@router.put("/{product_id}/images/reorder", response_model=APIResponse[List[ProductImageSchema]])
def reorder_images_endpoint(
    product_id: int,
    payload: ProductImageReorderRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Transactionally reorder product images.
    Updates sort_order in PostgreSQL. Persists order across sessions.
    """
    updated_images = reorder_product_images(product_id=product_id, payload=payload, db=db)
    return APIResponse(
        success=True,
        message="Product images reordered successfully",
        data=[ProductImageSchema.from_orm(img) for img in updated_images]
    )

@router.put("/{product_id}/images/{image_id}/primary", response_model=APIResponse[ProductImageSchema])
@router.put("/{product_id}/images/{image_id}/set-primary", response_model=APIResponse[ProductImageSchema])
def set_primary_image_endpoint(
    product_id: int,
    image_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Designate an image as the product's primary image.
    Transactionally sets old primary to false, new primary to true.
    """
    primary_image = set_primary_image(product_id=product_id, image_id=image_id, db=db)
    return APIResponse(
        success=True,
        message="Primary image updated successfully",
        data=ProductImageSchema.from_orm(primary_image)
    )

@router.put("/{product_id}/images/{image_id}", response_model=APIResponse[ProductImageSchema])
def update_product_image_endpoint(
    product_id: int,
    image_id: int,
    payload: ProductImageUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Update image metadata (alt_text, URL, sort_order, primary status).
    Strict ownership verification prevents cross-product modification.
    """
    updated_image = update_product_image(
        product_id=product_id,
        image_id=image_id,
        payload=payload,
        db=db
    )
    return APIResponse(
        success=True,
        message="Product image updated successfully",
        data=ProductImageSchema.from_orm(updated_image)
    )

@router.delete("/{product_id}/images/{image_id}", response_model=APIResponse[bool])
def delete_product_image_endpoint(
    product_id: int,
    image_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Safely delete a product image.
    If the deleted image was primary, automatically designates the next available image as primary.
    """
    result = delete_product_image(product_id=product_id, image_id=image_id, db=db)
    return APIResponse(
        success=True,
        message="Product image deleted successfully",
        data=result
    )

# ==============================================================================
# PRODUCT VARIANTS & ATTRIBUTES MANAGEMENT (ADMIN)
# ==============================================================================

@router.get("/{product_id}/variants", response_model=APIResponse[List[ProductVariantSchema]])
def list_product_variants(
    product_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """List all variants for a given product with attributes and order."""
    variants = get_product_variants(product_id, db, active_only=False)
    formatted = [format_variant_response(v) for v in variants]
    return APIResponse(
        success=True,
        message=f"Retrieved {len(formatted)} variants",
        data=formatted
    )

@router.post("/{product_id}/variants", response_model=APIResponse[ProductVariantSchema], status_code=http_status.HTTP_201_CREATED)
def create_variant(
    product_id: int,
    payload: ProductVariantCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new variant for a product with full validations:
    - Unique SKU
    - Pricing constraint (mrp >= price > 0)
    - Non-negative stock
    - Normalized attribute value mapping
    - Unique attribute combination check
    """
    variant = create_product_variant(product_id, payload, db)
    return APIResponse(
        success=True,
        message=f"Variant '{variant.sku}' created successfully",
        data=format_variant_response(variant)
    )

@router.put("/{product_id}/variants/reorder", response_model=APIResponse[List[ProductVariantSchema]])
def reorder_variants(
    product_id: int,
    payload: ProductVariantReorderRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Reorder product variants deterministically."""
    updated = reorder_product_variants(product_id, payload.variant_ids, db)
    return APIResponse(
        success=True,
        message="Variants reordered successfully",
        data=[format_variant_response(v) for v in updated]
    )

@router.get("/{product_id}/variants/{variant_id}", response_model=APIResponse[ProductVariantSchema])
def get_variant(
    product_id: int,
    variant_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Retrieve single variant details with ownership validation."""
    variant = get_variant_by_id(product_id, variant_id, db)
    return APIResponse(
        success=True,
        message="Variant details retrieved",
        data=format_variant_response(variant)
    )

@router.put("/{product_id}/variants/{variant_id}", response_model=APIResponse[ProductVariantSchema])
def update_variant(
    product_id: int,
    variant_id: int,
    payload: ProductVariantUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update variant details (SKU, pricing, stock, attributes, status, sort order)."""
    variant = update_product_variant(product_id, variant_id, payload, db)
    return APIResponse(
        success=True,
        message="Variant updated successfully",
        data=format_variant_response(variant)
    )

@router.delete("/{product_id}/variants/{variant_id}", response_model=APIResponse[bool])
def delete_variant(
    product_id: int,
    variant_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Safely delete variant.
    Blocks deletion if referenced in completed customer orders, prompting deactivation instead.
    """
    result = delete_product_variant(product_id, variant_id, db)
    return APIResponse(
        success=True,
        message="Variant deleted successfully",
        data=result
    )

@router.get("/{product_id}/attributes", response_model=APIResponse[List[dict]])
def get_product_attributes_endpoint(
    product_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Requirement 11: Product-scoped attributes.
    Returns only the attributes and values actually used by this product's variants.
    """
    attrs = get_product_scoped_attributes(product_id, db)
    return APIResponse(
        success=True,
        message=f"Retrieved {len(attrs)} attributes for product {product_id}",
        data=attrs
    )

