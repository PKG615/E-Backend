import re
from typing import List, Optional, Dict, Any, Tuple
from fastapi import HTTPException, status as http_status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import asc, desc, or_

from app.models.product import (
    Product, 
    ProductVariant, 
    ProductAttribute, 
    ProductAttributeValue, 
    VariantAttributeValue
)
from app.models.order import OrderItem, CartItem
from app.models.inventory import Inventory, InventoryTransaction
from app.schemas.product import (
    ProductVariantCreate,
    ProductVariantUpdate,
    ProductVariantSchema,
    VariantAttributeDetail,
    AttributeCreate,
    AttributeUpdate,
    AttributeSchema,
    AttributeValueCreate,
    AttributeValueSchema
)

def slugify(text: str) -> str:
    """Normalize a string into a clean URL-safe slug."""
    s = re.sub(r'[^a-zA-Z0-9]+', '-', text.strip().lower()).strip('-')
    return s or "item"

def compute_combination_key(attr_pairs: List[Tuple[str, str]]) -> str:
    """
    Computes a deterministic, sorted combination key for duplicate prevention.
    e.g. [('color', 'red'), ('size', 'm')] -> 'color:red|size:m'
    """
    sorted_pairs = sorted(attr_pairs, key=lambda p: (p[0], p[1]))
    return "|".join([f"{slugify(k)}:{slugify(v)}" for k, v in sorted_pairs if k and v])

def format_variant_response(variant: ProductVariant) -> ProductVariantSchema:
    """Format SQLAlchemy ProductVariant into API schema with enriched attribute details and authoritative inventory stock."""
    price = float(variant.price or 0.0)
    mrp = float(variant.mrp or price)

    # Authoritative inventory stock
    inv = getattr(variant, 'inventory_record', None)
    if inv is not None and inv.is_active:
        stock = int(inv.available_quantity)
    else:
        stock = int(variant.stock or 0)

    title = variant.title or variant.sku

    # Retrieve attribute details
    attr_details: List[VariantAttributeDetail] = []
    if variant.attribute_value_links:
        for link in variant.attribute_value_links:
            val = link.attribute_value
            if val and val.attribute:
                attr_details.append(
                    VariantAttributeDetail(
                        attribute_id=val.attribute.id,
                        attribute_name=val.attribute.name,
                        attribute_slug=val.attribute.slug,
                        value_id=val.id,
                        value=val.value,
                        value_slug=val.slug
                    )
                )

    # Sort attribute details by attribute name
    attr_details = sorted(attr_details, key=lambda d: d.attribute_name.lower())

    return ProductVariantSchema(
        id=variant.id,
        product_id=variant.product_id,
        sku=variant.sku,
        title=title,
        name=title,
        price=price,
        selling_price=price,
        mrp=mrp,
        stock=stock,
        stock_quantity=stock,
        in_stock=stock > 0,
        attributes=variant.attributes or {},
        attribute_values=attr_details,
        image_url=variant.image_url,
        is_active=bool(variant.is_active),
        sort_order=int(variant.sort_order or 0),
        created_at=variant.created_at,
        updated_at=variant.updated_at
    )

# ==============================================================================
# ATTRIBUTES MANAGEMENT
# ==============================================================================

def get_all_attributes(db: Session) -> List[ProductAttribute]:
    """Retrieve all global product attributes with their values."""
    return db.query(ProductAttribute).options(
        joinedload(ProductAttribute.values)
    ).order_by(asc(ProductAttribute.name)).all()

def get_product_scoped_attributes(product_id: int, db: Session) -> List[Dict[str, Any]]:
    """
    Retrieve only the attributes and values actually used by the given product's variants.
    Requirement 11: Product-scoped attributes.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    # Find all attribute values associated with this product's variants
    variants = db.query(ProductVariant).filter(
        ProductVariant.product_id == product_id
    ).options(
        joinedload(ProductVariant.attribute_value_links).joinedload(VariantAttributeValue.attribute_value).joinedload(ProductAttributeValue.attribute)
    ).all()

    attr_map: Dict[int, Dict[str, Any]] = {}
    for v in variants:
        for link in v.attribute_value_links:
            val = link.attribute_value
            if val and val.attribute:
                attr = val.attribute
                if attr.id not in attr_map:
                    attr_map[attr.id] = {
                        "id": attr.id,
                        "name": attr.name,
                        "slug": attr.slug,
                        "values": {}
                    }
                attr_map[attr.id]["values"][val.id] = {
                    "id": val.id,
                    "attribute_id": attr.id,
                    "value": val.value,
                    "slug": val.slug
                }

    # Format result
    result = []
    for attr_id, data in sorted(attr_map.items(), key=lambda x: x[1]["name"].lower()):
        vals = sorted(data["values"].values(), key=lambda x: x["value"].lower())
        result.append({
            "id": data["id"],
            "name": data["name"],
            "slug": data["slug"],
            "values": vals
        })
    return result

def get_or_create_attribute(name: str, db: Session) -> ProductAttribute:
    """Find an existing attribute by name/slug or create it normalized."""
    cleaned_name = name.strip()
    slug = slugify(cleaned_name)
    attr = db.query(ProductAttribute).filter(
        or_(ProductAttribute.slug == slug, ProductAttribute.name.ilike(cleaned_name))
    ).first()
    if not attr:
        attr = ProductAttribute(name=cleaned_name, slug=slug)
        db.add(attr)
        db.commit()
        db.refresh(attr)
    return attr

def get_or_create_attribute_value(attribute: ProductAttribute, value_str: str, db: Session) -> ProductAttributeValue:
    """Find an existing attribute value or create it under the specified attribute."""
    cleaned_val = value_str.strip()
    slug = slugify(cleaned_val)
    val = db.query(ProductAttributeValue).filter(
        ProductAttributeValue.attribute_id == attribute.id,
        or_(ProductAttributeValue.slug == slug, ProductAttributeValue.value.ilike(cleaned_val))
    ).first()
    if not val:
        val = ProductAttributeValue(
            attribute_id=attribute.id,
            value=cleaned_val,
            slug=slug
        )
        db.add(val)
        db.commit()
        db.refresh(val)
    return val

def create_attribute_service(payload: AttributeCreate, db: Session) -> ProductAttribute:
    """Create a new reusable product attribute."""
    cleaned_name = payload.name.strip()
    slug = slugify(cleaned_name)
    existing = db.query(ProductAttribute).filter(ProductAttribute.slug == slug).first()
    if existing:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Attribute '{existing.name}' already exists"
        )
    attr = ProductAttribute(name=cleaned_name, slug=slug)
    db.add(attr)
    db.commit()
    db.refresh(attr)
    return attr

def create_attribute_value_service(attribute_id: int, payload: AttributeValueCreate, db: Session) -> ProductAttributeValue:
    """Add a value to an existing attribute."""
    attr = db.query(ProductAttribute).filter(ProductAttribute.id == attribute_id).first()
    if not attr:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Attribute with ID {attribute_id} not found"
        )
    cleaned_val = payload.value.strip()
    slug = slugify(cleaned_val)
    existing = db.query(ProductAttributeValue).filter(
        ProductAttributeValue.attribute_id == attribute_id,
        ProductAttributeValue.slug == slug
    ).first()
    if existing:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Value '{existing.value}' already exists for attribute '{attr.name}'"
        )
    val = ProductAttributeValue(
        attribute_id=attribute_id,
        value=cleaned_val,
        slug=slug
    )
    db.add(val)
    db.commit()
    db.refresh(val)
    return val

def delete_attribute_service(attribute_id: int, db: Session) -> bool:
    """Delete an attribute if not in use by active variants."""
    attr = db.query(ProductAttribute).filter(ProductAttribute.id == attribute_id).first()
    if not attr:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Attribute with ID {attribute_id} not found"
        )
    # Check if any values are linked to variants
    value_ids = [v.id for v in attr.values]
    if value_ids:
        in_use_count = db.query(VariantAttributeValue).filter(
            VariantAttributeValue.attribute_value_id.in_(value_ids)
        ).count()
        if in_use_count > 0:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete attribute '{attr.name}' because its values are assigned to {in_use_count} variant(s)."
            )
    db.delete(attr)
    db.commit()
    return True

# ==============================================================================
# VARIANT CRUD & BUSINESS LOGIC
# ==============================================================================

def get_product_variants(product_id: int, db: Session, active_only: bool = False) -> List[ProductVariant]:
    """Retrieve all variants for a product with full relational loads."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    query = db.query(ProductVariant).filter(
        ProductVariant.product_id == product_id
    ).options(
        joinedload(ProductVariant.attribute_value_links).joinedload(VariantAttributeValue.attribute_value).joinedload(ProductAttributeValue.attribute)
    )
    if active_only:
        query = query.filter(ProductVariant.is_active == True)
    
    return query.order_by(asc(ProductVariant.sort_order), asc(ProductVariant.id)).all()

def get_variant_by_id(product_id: int, variant_id: int, db: Session) -> ProductVariant:
    """Get variant by ID with strict product ownership verification."""
    variant = db.query(ProductVariant).filter(
        ProductVariant.id == variant_id,
        ProductVariant.product_id == product_id
    ).options(
        joinedload(ProductVariant.attribute_value_links).joinedload(VariantAttributeValue.attribute_value).joinedload(ProductAttributeValue.attribute)
    ).first()

    if not variant:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Variant with ID {variant_id} not found for product {product_id}"
        )
    return variant

def resolve_attribute_values(
    attribute_value_ids: Optional[List[int]],
    attributes_dict: Optional[Dict[str, str]],
    db: Session
) -> List[ProductAttributeValue]:
    """
    Resolve attribute values using either explicit value IDs or key-value dictionary,
    ensuring normalization and relational linkage.
    """
    resolved_values: List[ProductAttributeValue] = []

    # 1. Resolve by ID
    if attribute_value_ids:
        found_vals = db.query(ProductAttributeValue).options(
            joinedload(ProductAttributeValue.attribute)
        ).filter(ProductAttributeValue.id.in_(attribute_value_ids)).all()
        resolved_values.extend(found_vals)

    # 2. Resolve by dictionary key-values (e.g. {"Color": "Red", "Size": "M"})
    if attributes_dict:
        for attr_name, val_name in attributes_dict.items():
            if not attr_name or not val_name:
                continue
            attr = get_or_create_attribute(attr_name, db)
            val = get_or_create_attribute_value(attr, str(val_name), db)
            if val not in resolved_values:
                resolved_values.append(val)

    return resolved_values

def validate_unique_combination(
    product_id: int,
    attribute_values: List[ProductAttributeValue],
    db: Session,
    exclude_variant_id: Optional[int] = None
) -> None:
    """
    Requirement 12 & 13: Prevent duplicate active variant combinations for the same product.
    e.g. Color=Red + Size=M must not exist twice.
    """
    if not attribute_values:
        return

    new_pairs = [(v.attribute.slug, v.slug) for v in attribute_values if v.attribute]
    new_key = compute_combination_key(new_pairs)

    existing_variants = db.query(ProductVariant).filter(
        ProductVariant.product_id == product_id,
        ProductVariant.is_active == True
    ).options(
        joinedload(ProductVariant.attribute_value_links).joinedload(VariantAttributeValue.attribute_value).joinedload(ProductAttributeValue.attribute)
    ).all()

    for ev in existing_variants:
        if exclude_variant_id and ev.id == exclude_variant_id:
            continue
        ev_pairs = []
        for link in ev.attribute_value_links:
            val = link.attribute_value
            if val and val.attribute:
                ev_pairs.append((val.attribute.slug, val.slug))
        ev_key = compute_combination_key(ev_pairs)
        if ev_key and ev_key == new_key:
            readable_pairs = ", ".join([f"{v.attribute.name}: {v.value}" for v in attribute_values if v.attribute])
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"A variant with this exact attribute combination ({readable_pairs}) already exists for this product (SKU: {ev.sku})."
            )

def create_product_variant(
    product_id: int,
    payload: ProductVariantCreate,
    db: Session
) -> ProductVariant:
    """Create a new product variant with full validation and relational attribute linkage."""
    # 1. Product exists check
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    # 2. SKU uniqueness validation (across all variants and parent products)
    sku = payload.sku.strip().upper()
    existing_variant = db.query(ProductVariant).filter(ProductVariant.sku == sku).first()
    if existing_variant:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Variant with SKU '{sku}' already exists"
        )
    existing_product_sku = db.query(Product).filter(Product.sku == sku).first()
    if existing_product_sku and existing_product_sku.id != product_id:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"SKU '{sku}' is already in use by product '{existing_product_sku.name}'"
        )

    # 3. Pricing validation
    selling_price = round(float(payload.price), 2)
    mrp = round(float(payload.mrp), 2)
    if selling_price <= 0:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Variant selling price must be greater than 0"
        )
    if mrp < selling_price:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Variant MRP (₹{mrp}) must be greater than or equal to selling price (₹{selling_price})"
        )

    # 4. Stock validation
    stock = int(payload.stock if payload.stock is not None else (payload.stock_quantity or 0))
    if stock < 0:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Stock quantity cannot be negative"
        )

    # 5. Resolve attribute values
    resolved_values = resolve_attribute_values(
        payload.attribute_value_ids,
        payload.attributes,
        db
    )

    # 6. Duplicate combination check if active
    if payload.is_active:
        validate_unique_combination(product_id, resolved_values, db)

    # 7. Auto-generate title/name if omitted
    title = payload.title or payload.name
    if not title:
        if resolved_values:
            val_names = [v.value for v in sorted(resolved_values, key=lambda x: x.attribute.name if x.attribute else "")]
            title = " / ".join(val_names)
        else:
            title = f"{product.name} Variant"

    # Build cached attributes JSON
    attributes_json = {}
    for val in resolved_values:
        if val.attribute:
            attributes_json[val.attribute.name] = val.value

    # Determine sort order
    sort_order = payload.sort_order
    if sort_order == 0:
        max_sort = db.query(ProductVariant.sort_order).filter(
            ProductVariant.product_id == product_id
        ).order_by(desc(ProductVariant.sort_order)).first()
        sort_order = (max_sort[0] + 1) if max_sort else 0

    # 8. Create Variant instance
    variant = ProductVariant(
        product_id=product_id,
        sku=sku,
        title=title,
        price=selling_price,
        mrp=mrp,
        stock=stock,
        attributes=attributes_json,
        image_url=payload.image_url,
        is_active=payload.is_active,
        sort_order=sort_order
    )
    db.add(variant)
    db.flush()

    # 9. Link attribute values in relational association table
    for val in resolved_values:
        link = VariantAttributeValue(
            variant_id=variant.id,
            attribute_value_id=val.id
        )
        db.add(link)

    # 10. Automatically establish authoritative Inventory record
    inv = Inventory(
        product_id=product_id,
        variant_id=variant.id,
        sku=variant.sku,
        on_hand_quantity=stock,
        reserved_quantity=0,
        available_quantity=stock,
        low_stock_threshold=5,
        is_active=variant.is_active
    )
    db.add(inv)
    db.flush()

    if stock > 0:
        tx = InventoryTransaction(
            inventory_id=inv.id,
            transaction_type="RECEIVE",
            quantity_change=stock,
            quantity_before=0,
            quantity_after=stock,
            reason="Initial variant creation stock",
            created_by="admin"
        )
        db.add(tx)

    # Sync parent product stock
    parent_sum = db.query(ProductVariant.stock).filter(
        ProductVariant.product_id == product_id,
        ProductVariant.is_active == True
    ).all()
    total_var_stock = sum(s[0] for s in parent_sum if s[0] is not None)
    product.stock = total_var_stock

    db.commit()
    db.refresh(variant)
    return variant

def update_product_variant(
    product_id: int,
    variant_id: int,
    payload: ProductVariantUpdate,
    db: Session
) -> ProductVariant:
    """Update an existing variant with ownership protection and duplicate checking."""
    variant = get_variant_by_id(product_id, variant_id, db)

    # 1. Update SKU if changed
    if payload.sku:
        new_sku = payload.sku.strip().upper()
        if new_sku != variant.sku:
            existing = db.query(ProductVariant).filter(
                ProductVariant.sku == new_sku,
                ProductVariant.id != variant_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"Variant with SKU '{new_sku}' already exists"
                )
            variant.sku = new_sku

    # 2. Update Pricing
    new_price = round(float(payload.price), 2) if payload.price is not None else variant.price
    new_mrp = round(float(payload.mrp), 2) if payload.mrp is not None else variant.mrp
    if new_price <= 0:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Variant selling price must be greater than 0"
        )
    if new_mrp < new_price:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Variant MRP (₹{new_mrp}) must be greater than or equal to selling price (₹{new_price})"
        )
    variant.price = new_price
    variant.mrp = new_mrp

    # 3. Update Stock & sync authoritative Inventory
    new_stock_val = None
    if payload.stock is not None:
        if payload.stock < 0:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Stock quantity cannot be negative"
            )
        new_stock_val = payload.stock
    elif payload.stock_quantity is not None:
        if payload.stock_quantity < 0:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Stock quantity cannot be negative"
            )
        new_stock_val = payload.stock_quantity

    if new_stock_val is not None:
        variant.stock = new_stock_val
        # Sync with Inventory record
        inv = db.query(Inventory).filter(Inventory.variant_id == variant.id).first()
        if not inv:
            inv = Inventory(
                product_id=product_id,
                variant_id=variant.id,
                sku=variant.sku,
                on_hand_quantity=new_stock_val,
                reserved_quantity=0,
                available_quantity=new_stock_val,
                low_stock_threshold=5,
                is_active=variant.is_active
            )
            db.add(inv)
            db.flush()
            tx = InventoryTransaction(
                inventory_id=inv.id,
                transaction_type="RECEIVE" if new_stock_val > 0 else "ADJUSTMENT",
                quantity_change=new_stock_val,
                quantity_before=0,
                quantity_after=new_stock_val,
                reason="Inventory created via variant update",
                created_by="admin"
            )
            db.add(tx)
        else:
            delta = new_stock_val - inv.on_hand_quantity
            if delta != 0:
                tx_type = "RECEIVE" if delta > 0 else "ADJUSTMENT"
                tx = InventoryTransaction(
                    inventory_id=inv.id,
                    transaction_type=tx_type,
                    quantity_change=delta,
                    quantity_before=inv.on_hand_quantity,
                    quantity_after=new_stock_val,
                    reason="Stock updated via variant edit",
                    created_by="admin"
                )
                db.add(tx)
                inv.on_hand_quantity = new_stock_val
                inv.available_quantity = new_stock_val - inv.reserved_quantity

        # Sync parent product stock
        parent_sum = db.query(ProductVariant.stock).filter(
            ProductVariant.product_id == product_id,
            ProductVariant.is_active == True
        ).all()
        total_var_stock = sum(s[0] for s in parent_sum if s[0] is not None)
        parent_prod = db.query(Product).filter(Product.id == product_id).first()
        if parent_prod:
            parent_prod.stock = total_var_stock

    # 4. Update basic fields
    if payload.title is not None:
        variant.title = payload.title
    elif payload.name is not None:
        variant.title = payload.name

    if payload.is_active is not None:
        variant.is_active = payload.is_active

    if payload.sort_order is not None:
        variant.sort_order = payload.sort_order

    if payload.image_url is not None:
        variant.image_url = payload.image_url

    # 5. Update attribute values if provided
    if payload.attribute_value_ids is not None or payload.attributes is not None:
        resolved_values = resolve_attribute_values(
            payload.attribute_value_ids,
            payload.attributes,
            db
        )

        # Validate duplicate combination
        if variant.is_active:
            validate_unique_combination(product_id, resolved_values, db, exclude_variant_id=variant.id)

        # Re-link relational association table
        db.query(VariantAttributeValue).filter(
            VariantAttributeValue.variant_id == variant.id
        ).delete()

        for val in resolved_values:
            link = VariantAttributeValue(
                variant_id=variant.id,
                attribute_value_id=val.id
            )
            db.add(link)

        # Update cached attributes JSON
        attributes_json = {}
        for val in resolved_values:
            if val.attribute:
                attributes_json[val.attribute.name] = val.value
        variant.attributes = attributes_json

    db.commit()
    db.refresh(variant)
    return variant

def delete_product_variant(product_id: int, variant_id: int, db: Session) -> bool:
    """
    Safely delete a variant.
    Requirement 19: Inspect existing dependencies:
    - cart items
    - order items
    If order items reference the variant, do NOT cascade-delete! Raise business error instructing deactivation.
    """
    variant = get_variant_by_id(product_id, variant_id, db)

    # 1. Inspect OrderItem dependencies
    order_count = db.query(OrderItem).filter(OrderItem.variant_id == variant_id).count()
    if order_count > 0:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot delete variant '{variant.sku}' because it is referenced in {order_count} customer order(s). "
                f"To preserve order history, please deactivate this variant (set is_active=False) instead."
            )
        )

    # 2. Clean up active cart items
    db.query(CartItem).filter(CartItem.variant_id == variant_id).delete()

    # 3. Clean up variant attribute values
    db.query(VariantAttributeValue).filter(VariantAttributeValue.variant_id == variant_id).delete()

    # 4. Delete the variant
    db.delete(variant)
    db.commit()
    return True

def reorder_product_variants(product_id: int, variant_ids: List[int], db: Session) -> List[ProductVariant]:
    """Reorder variants deterministically for a product."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    existing_variants = db.query(ProductVariant).filter(
        ProductVariant.product_id == product_id,
        ProductVariant.id.in_(variant_ids)
    ).all()

    variant_map = {v.id: v for v in existing_variants}
    updated_variants = []

    for index, var_id in enumerate(variant_ids):
        if var_id in variant_map:
            variant_map[var_id].sort_order = index
            updated_variants.append(variant_map[var_id])

    db.commit()
    return get_product_variants(product_id, db)
