from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, Request, status as http_status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc, asc, func
from app.core.database import get_db
from app.models.product import Product, ProductImage, ProductVariant
from app.models.category import Category, Brand
from app.schemas.product import (
    ProductResponse, 
    ProductImageSchema, 
    ProductVariantSchema,
    SearchSuggestionsResponse
)
from app.schemas.common import APIResponse, PaginatedData
from app.services.variant_service import format_variant_response
from app.services.catalog_service import (
    build_catalog_query,
    get_catalog_facets,
    get_search_suggestions,
    parse_attribute_filters
)

router = APIRouter()

def format_product_response(product: Product, primary_only: bool = False, admin_view: bool = False) -> ProductResponse:
    all_imgs = product.images or []
    primary_imgs = [img for img in all_imgs if img.is_primary]
    secondary_imgs = [img for img in all_imgs if not img.is_primary]
    secondary_sorted = sorted(secondary_imgs, key=lambda x: (x.sort_order, x.id))
    ordered_imgs = primary_imgs + secondary_sorted if primary_imgs else sorted(all_imgs, key=lambda x: (x.sort_order, x.id))

    if primary_only:
        selected_imgs = [ordered_imgs[0]] if ordered_imgs else []
    else:
        selected_imgs = ordered_imgs

    images = [ProductImageSchema.from_orm(img) for img in selected_imgs]
    
    # Process variants (filter by active for public view)
    all_variants = product.variants or []
    if admin_view:
        active_variants = all_variants
    else:
        active_variants = [v for v in all_variants if v.is_active]

    sorted_variants = sorted(active_variants, key=lambda x: (x.sort_order or 0, x.id or 0))
    formatted_variants = [format_variant_response(v) for v in sorted_variants]

    # Compute available attributes summary
    available_attributes: dict = {}
    for v in sorted_variants:
        if v.attributes and isinstance(v.attributes, dict):
            for attr_name, attr_val in v.attributes.items():
                if attr_name and attr_val:
                    if attr_name not in available_attributes:
                        available_attributes[attr_name] = []
                    if str(attr_val) not in available_attributes[attr_name]:
                        available_attributes[attr_name].append(str(attr_val))
    
    price = float(product.price or 0.0)
    mrp = float(product.mrp or price)
    discount_pct = float(product.discount_percent or 0.0)
    if mrp > price and discount_pct <= 0.0:
        discount_pct = round(((mrp - price) / mrp) * 100, 2)

    # Authoritative stock calculation from inventory
    if product.variants:
        stock_val = sum(
            (v.inventory_record.available_quantity if getattr(v, 'inventory_record', None) and v.inventory_record.is_active else int(v.stock or 0))
            for v in active_variants
        )
    elif getattr(product, 'inventory_records', None):
        base_inv = [inv for inv in product.inventory_records if inv.variant_id is None and inv.is_active]
        if base_inv:
            stock_val = int(base_inv[0].available_quantity)
        else:
            stock_val = int(product.stock or 0)
    else:
        stock_val = int(product.stock or 0)
    product_status = product.status or ('active' if product.is_active else 'inactive')
    warranty_val = product.warranty or product.warranty_info
    seo_t = product.seo_title or product.meta_title
    seo_d = product.seo_description or product.meta_description

    # Calculate authentic rating aggregate from approved reviews
    approved_reviews = [r for r in (product.reviews or []) if getattr(r, 'status', 'approved') == 'approved']
    total_revs = len(approved_reviews)
    avg_rating = round(sum(r.rating for r in approved_reviews) / total_revs, 1) if total_revs > 0 else 0.0

    return ProductResponse(
        id=product.id,
        name=product.name,
        slug=product.slug,
        sku=product.sku,
        description=product.description or "",
        short_description=product.short_description,
        category_id=product.category_id,
        brand_id=product.brand_id,
        price=price,
        selling_price=price,
        mrp=mrp,
        discount_percent=discount_pct,
        discount_percentage=discount_pct,
        tax_percent=float(product.tax_percent or 18.0),
        tax_percentage=float(product.tax_percent or 18.0),
        stock=stock_val,
        stock_quantity=stock_val,
        in_stock=stock_val > 0,
        status=product_status,
        is_active=bool(product.is_active),
        is_featured=bool(product.is_featured),
        is_new_arrival=bool(getattr(product, 'is_new_arrival', False)),
        is_best_seller=bool(product.is_best_seller),
        is_flash_sale=bool(product.is_flash_sale),
        sort_order=int(getattr(product, 'sort_order', 0) or 0),
        weight=product.weight,
        length=product.length,
        width=product.width,
        height=product.height,
        video_url=product.video_url,
        warranty=warranty_val,
        warranty_info=warranty_val,
        return_policy=product.return_policy or "7-day return policy",
        specifications=product.specifications or {},
        attributes=product.attributes or {},
        seo_title=seo_t,
        seo_description=seo_d,
        meta_title=seo_t,
        meta_description=seo_d,
        created_at=product.created_at,
        updated_at=product.updated_at,
        images=images,
        variants=formatted_variants,
        available_attributes=available_attributes,
        category_name=product.category.name if product.category else None,
        brand_name=product.brand.name if product.brand else None,
        average_rating=avg_rating,
        total_reviews=total_revs
    )

@router.get("", response_model=APIResponse[PaginatedData[ProductResponse]])
def get_products(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    q: Optional[str] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    category_slug: Optional[str] = None,
    category_id: Optional[int] = None,
    subcategory: Optional[str] = None,
    subcategory_slug: Optional[str] = None,
    subcategory_id: Optional[int] = None,
    brand: Optional[str] = None,
    brand_slug: Optional[str] = None,
    brand_id: Optional[int] = None,
    brands: Optional[str] = None,
    status: Optional[str] = None,
    featured: Optional[bool] = None,
    is_featured: Optional[bool] = None,
    new_arrival: Optional[bool] = None,
    is_new_arrival: Optional[bool] = None,
    best_seller: Optional[bool] = None,
    is_best_seller: Optional[bool] = None,
    is_flash_sale: Optional[bool] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_discount: Optional[float] = None,
    discount_min: Optional[float] = None,
    availability: Optional[str] = None,
    in_stock: Optional[bool] = None,
    attributes: Optional[str] = None,
    sort: Optional[str] = None,
    sort_by: Optional[str] = None,
    include_facets: bool = True,
    db: Session = Depends(get_db)
):
    """
    Public Product Catalog List API.
    Server-authoritative, paginated, multi-facet filtered, and deterministically sorted query.
    Only shows active products on public storefront.
    """
    search_term = q or search
    cat_slug = category_slug or (category if category and not category.isdigit() else None)
    cat_id = category_id or (int(category) if category and category.isdigit() else None)
    sub_slug = subcategory_slug or (subcategory if subcategory and not subcategory.isdigit() else None)
    sub_id = subcategory_id or (int(subcategory) if subcategory and subcategory.isdigit() else None)
    br_slug = brand_slug or (brand if brand and not brand.isdigit() else None)
    br_id = brand_id or (int(brand) if brand and brand.isdigit() else None)
    discount_val = min_discount if min_discount is not None else discount_min
    avail_val = availability
    if in_stock is True and not avail_val:
        avail_val = "in_stock"
    elif in_stock is False and not avail_val:
        avail_val = "out_of_stock"

    # Dynamic attribute filters from query params
    qp = dict(request.query_params)
    parsed_attrs = parse_attribute_filters(attributes, qp)

    # Sorting
    effective_sort = sort or sort_by

    # Feature flags
    feat_filter = featured if featured is not None else is_featured
    new_filter = new_arrival if new_arrival is not None else is_new_arrival
    best_filter = best_seller if best_seller is not None else is_best_seller

    # Build filtered query
    query, _ = build_catalog_query(
        db=db,
        search=search_term,
        category_slug=cat_slug,
        category_id=cat_id,
        subcategory_slug=sub_slug,
        subcategory_id=sub_id,
        brand_slug=br_slug,
        brand_id=br_id,
        brands=brands,
        min_price=min_price,
        max_price=max_price,
        min_discount=discount_val,
        availability=avail_val,
        attribute_filters=parsed_attrs,
        sort_by=effective_sort,
        is_featured=feat_filter,
        is_new_arrival=new_filter,
        is_best_seller=best_filter,
        is_flash_sale=is_flash_sale
    )

    total = query.count()
    offset = (page - 1) * limit
    products = query.offset(offset).limit(limit).all()

    items = [format_product_response(p, primary_only=True) for p in products]
    total_pages = (total + limit - 1) // limit if total > 0 else 1

    facets_data = None
    if include_facets:
        facets_data = get_catalog_facets(db).dict()

    return APIResponse(
        success=True,
        message="Products retrieved successfully",
        data=PaginatedData(
            items=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
            facets=facets_data
        )
    )

@router.get("/suggestions", response_model=APIResponse[SearchSuggestionsResponse])
def get_suggestions(
    q: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Search suggestions for storefront global search:
    - Matching products (limit: 5)
    - Matching categories (limit: 3)
    - Matching brands (limit: 3)
    """
    query_str = q or search or ""
    data = get_search_suggestions(db, query_str)
    return APIResponse(
        success=True,
        message="Search suggestions retrieved",
        data=data
    )

@router.get("/flash-deals", response_model=APIResponse[List[ProductResponse]])
def get_flash_deals(db: Session = Depends(get_db)):
    deals = db.query(Product).options(
        joinedload(Product.category),
        joinedload(Product.brand),
        joinedload(Product.images),
        joinedload(Product.variants)
    ).filter(
        Product.is_active == True,
        Product.status == "active",
        or_(Product.is_flash_sale == True, Product.discount_percent >= 15.0)
    ).order_by(desc(Product.discount_percent)).limit(8).all()
    
    return APIResponse(
        success=True,
        message="Flash deals retrieved",
        data=[format_product_response(p) for p in deals]
    )

@router.get("/featured", response_model=APIResponse[List[ProductResponse]])
def get_featured(db: Session = Depends(get_db)):
    featured = db.query(Product).options(
        joinedload(Product.category),
        joinedload(Product.brand),
        joinedload(Product.images),
        joinedload(Product.variants)
    ).filter(
        Product.is_active == True,
        Product.status == "active",
        Product.is_featured == True
    ).order_by(desc(Product.created_at)).limit(8).all()
    
    return APIResponse(
        success=True,
        message="Featured products retrieved",
        data=[format_product_response(p) for p in featured]
    )

@router.get("/recently-viewed", response_model=APIResponse[List[ProductResponse]])
def get_recently_viewed(
    ids: str = Query(..., description="Comma-separated product IDs"),
    db: Session = Depends(get_db)
):
    """
    Get real products recently viewed by customer, preserving requested view order.
    """
    if not ids:
        return APIResponse(success=True, message="No product IDs provided", data=[])
    
    try:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
    except Exception:
        id_list = []

    if not id_list:
        return APIResponse(success=True, message="No valid product IDs", data=[])

    id_list = id_list[:12]

    products = (
        db.query(Product)
        .options(
            joinedload(Product.category),
            joinedload(Product.brand),
            joinedload(Product.images),
            joinedload(Product.variants)
        )
        .filter(
            Product.id.in_(id_list),
            Product.is_active == True,
            Product.status == "active"
        )
        .all()
    )

    prod_map = {p.id: p for p in products}
    ordered = [prod_map[pid] for pid in id_list if pid in prod_map]

    return APIResponse(
        success=True,
        message=f"Retrieved {len(ordered)} recently viewed products",
        data=[format_product_response(p, primary_only=True) for p in ordered]
    )

@router.get("/{slug_or_id}", response_model=APIResponse[ProductResponse])
def get_product_by_slug_or_id(slug_or_id: str, db: Session = Depends(get_db)):
    """
    Public Product Detail API.
    Looks up by slug or numeric ID.
    Returns 404 if product does not exist or is not active.
    """
    query = db.query(Product).options(
        joinedload(Product.category),
        joinedload(Product.brand),
        joinedload(Product.images),
        joinedload(Product.variants)
    )
    if slug_or_id.isdigit():
        product = query.filter(Product.id == int(slug_or_id)).first()
    else:
        product = query.filter(Product.slug == slug_or_id.strip().lower()).first()

    if not product or not product.is_active or product.status != "active":
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Product not found or currently unavailable"
        )

    return APIResponse(
        success=True,
        message="Product details retrieved",
        data=format_product_response(product)
    )

@router.get("/{slug_or_id}/images", response_model=APIResponse[List[ProductImageSchema]])
def get_public_product_images(slug_or_id: str, db: Session = Depends(get_db)):
    """
    Public Product Image Gallery API.
    Returns real images in deterministic gallery order.
    """
    if slug_or_id.isdigit():
        product = db.query(Product).filter(Product.id == int(slug_or_id)).first()
    else:
        product = db.query(Product).filter(Product.slug == slug_or_id.strip().lower()).first()

    if not product or not product.is_active or product.status != "active":
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Product not found or currently unavailable"
        )

    all_imgs = product.images or []
    primary_imgs = [img for img in all_imgs if img.is_primary]
    secondary_imgs = [img for img in all_imgs if not img.is_primary]
    secondary_sorted = sorted(secondary_imgs, key=lambda x: (x.sort_order, x.id))
    ordered_imgs = primary_imgs + secondary_sorted if primary_imgs else sorted(all_imgs, key=lambda x: (x.sort_order, x.id))

    return APIResponse(
        success=True,
        message=f"Retrieved {len(ordered_imgs)} images for product",
        data=[ProductImageSchema.from_orm(img) for img in ordered_imgs]
    )

@router.get("/{slug_or_id}/variants", response_model=APIResponse[List[ProductVariantSchema]])
def get_public_product_variants(slug_or_id: str, db: Session = Depends(get_db)):
    """
    Public Product Variants API.
    Returns active purchasable variants for a product ordered by sort_order and ID.
    Only active variants are returned to customers.
    """
    if slug_or_id.isdigit():
        product = db.query(Product).filter(Product.id == int(slug_or_id)).first()
    else:
        product = db.query(Product).filter(Product.slug == slug_or_id.strip().lower()).first()

    if not product or not product.is_active or product.status != "active":
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Product not found or currently unavailable"
        )

    all_variants = product.variants or []
    active_variants = [v for v in all_variants if v.is_active]
    sorted_variants = sorted(active_variants, key=lambda x: (x.sort_order or 0, x.id or 0))

    return APIResponse(
        success=True,
        message=f"Retrieved {len(sorted_variants)} active variants",
        data=[format_variant_response(v) for v in sorted_variants]
    )

@router.get("/{slug_or_id}/related", response_model=APIResponse[List[ProductResponse]])
def get_related_products(
    slug_or_id: str,
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """
    Related products foundation:
    Fetches active products in the same category or brand, excluding current product.
    Prioritizes same category first, then same brand, sorted by best seller and created_at.
    """
    if slug_or_id.isdigit():
        curr = db.query(Product).filter(Product.id == int(slug_or_id)).first()
    else:
        curr = db.query(Product).filter(Product.slug == slug_or_id.strip().lower()).first()

    if not curr:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    conditions = []
    if curr.category_id:
        conditions.append(Product.category_id == curr.category_id)
    if curr.brand_id:
        conditions.append(Product.brand_id == curr.brand_id)

    query = (
        db.query(Product)
        .options(
            joinedload(Product.category),
            joinedload(Product.brand),
            joinedload(Product.images),
            joinedload(Product.variants)
        )
        .filter(
            Product.id != curr.id,
            Product.is_active == True,
            Product.status == "active"
        )
    )

    if conditions:
        query = query.filter(or_(*conditions))

    related = (
        query
        .order_by(
            desc(Product.category_id == curr.category_id),
            desc(Product.is_best_seller),
            desc(Product.is_featured),
            desc(Product.created_at)
        )
        .limit(limit)
        .all()
    )

    return APIResponse(
        success=True,
        message=f"Retrieved {len(related)} related products",
        data=[format_product_response(p, primary_only=True) for p in related]
    )


