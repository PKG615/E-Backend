import re
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_, desc, asc, case, distinct

from app.models.product import (
    Product, 
    ProductImage, 
    ProductVariant, 
    ProductAttribute, 
    ProductAttributeValue, 
    VariantAttributeValue
)
from app.models.category import Category
from app.models.brand import Brand
from app.models.inventory import Inventory
from app.schemas.product import (
    ProductSuggestionItem,
    CategorySuggestionItem,
    BrandSuggestionItem,
    SearchSuggestionsResponse,
    CatalogFacets,
    FacetCategoryItem,
    FacetBrandItem,
    FacetAttribute,
    FacetAttributeValue
)

def normalize_search_query(q: Optional[str]) -> Optional[str]:
    """
    Normalizes search query:
    - strips leading and trailing whitespaces
    - reduces consecutive whitespace to single space
    - restricts max length to 100 characters
    - strips dangerous control characters
    """
    if not q:
        return None
    cleaned = re.sub(r'[\x00-\x1f\x7f]', '', q.strip())
    cleaned = re.sub(r'\s+', ' ', cleaned)
    if not cleaned:
        return None
    return cleaned[:100]

def parse_attribute_filters(raw_attributes: Optional[str], query_params: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Parses attribute filters from either:
    1. Dedicated 'attributes' string: e.g. 'color:silver;storage:1tb' or 'color=silver,storage=1tb'
    2. Query params prefixed with 'attr_' or 'attribute_': e.g. 'attr_color=silver', 'attribute_ram=16gb'
    Returns dict mapping normalized attribute slug -> list of normalized value slugs/strings.
    """
    filters: Dict[str, List[str]] = {}

    # 1. Parse string if present
    if raw_attributes:
        pairs = re.split(r'[;,]', raw_attributes)
        for pair in pairs:
            if ':' in pair:
                key, val = pair.split(':', 1)
            elif '=' in pair:
                key, val = pair.split('=', 1)
            else:
                continue
            k_slug = key.strip().lower()
            vals = [v.strip().lower() for v in val.split('|') if v.strip()]
            if k_slug and vals:
                filters.setdefault(k_slug, []).extend(vals)

    # 2. Parse query params like attr_color or attribute_color
    for param_name, param_val in query_params.items():
        attr_key = None
        if param_name.startswith('attribute_'):
            attr_key = param_name[len('attribute_'):].strip().lower()
        elif param_name.startswith('attr_'):
            attr_key = param_name[len('attr_'):].strip().lower()

        if attr_key and param_val:
            val_strs = [v.strip().lower() for v in str(param_val).split(',') if v.strip()]
            if val_strs:
                filters.setdefault(attr_key, []).extend(val_strs)

    # Deduplicate values
    for k in filters:
        filters[k] = list(set(filters[k]))

    return filters

def build_catalog_query(
    db: Session,
    search: Optional[str] = None,
    category_slug: Optional[str] = None,
    category_id: Optional[int] = None,
    subcategory_slug: Optional[str] = None,
    subcategory_id: Optional[int] = None,
    brand_slug: Optional[str] = None,
    brand_id: Optional[int] = None,
    brands: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_discount: Optional[float] = None,
    availability: Optional[str] = None,
    attribute_filters: Optional[Dict[str, List[str]]] = None,
    sort_by: Optional[str] = None,
    is_featured: Optional[bool] = None,
    is_new_arrival: Optional[bool] = None,
    is_best_seller: Optional[bool] = None,
    is_flash_sale: Optional[bool] = None
) -> Tuple[Any, Optional[Any]]:
    """
    Constructs server-authoritative SQLAlchemy query for products with all filters and sorting.
    Returns (query, relevance_score_expression_or_None).
    """
    query = db.query(Product).options(
        joinedload(Product.category),
        joinedload(Product.brand),
        joinedload(Product.images),
        joinedload(Product.variants)
    ).filter(
        Product.is_active == True,
        Product.status == "active"
    )

    clean_search = normalize_search_query(search)
    relevance_score = None

    # 1. Search with deterministic relevance scoring
    if clean_search:
        search_lower = clean_search.lower()
        search_pattern = f"%{clean_search}%"

        # Search filter conditions across product, brand, category, and variants
        query = query.outerjoin(Product.brand).outerjoin(Product.category).outerjoin(Product.variants)

        query = query.filter(
            or_(
                Product.name.ilike(search_pattern),
                Product.sku.ilike(search_pattern),
                Product.slug.ilike(search_pattern),
                Product.short_description.ilike(search_pattern),
                Product.description.ilike(search_pattern),
                Brand.name.ilike(search_pattern),
                Category.name.ilike(search_pattern),
                and_(
                    ProductVariant.is_active == True,
                    or_(
                        ProductVariant.title.ilike(search_pattern),
                        ProductVariant.sku.ilike(search_pattern)
                    )
                )
            )
        ).distinct()

        # Deterministic ranking expression
        relevance_score = case(
            (func.lower(Product.name) == search_lower, 100),
            (func.lower(Product.name).startswith(search_lower), 80),
            (func.lower(Product.sku) == search_lower, 70),
            (func.lower(Product.sku).startswith(search_lower), 60),
            (func.lower(Brand.name) == search_lower, 50),
            (func.lower(Category.name) == search_lower, 45),
            (Product.name.ilike(f"%{clean_search}%"), 40),
            (and_(ProductVariant.is_active == True, ProductVariant.title.ilike(f"%{clean_search}%")), 30),
            (Product.short_description.ilike(f"%{clean_search}%"), 20),
            (Product.description.ilike(f"%{clean_search}%"), 10),
            else_=0
        )

    # 2. Category & Subcategory Filter (with hierarchical child inclusion)
    if subcategory_slug or subcategory_id:
        sub_id = subcategory_id
        if not sub_id and subcategory_slug:
            sub = db.query(Category).filter(Category.slug == subcategory_slug.strip().lower()).first()
            sub_id = sub.id if sub else -1
        query = query.filter(Product.category_id == sub_id)
    elif category_slug or category_id:
        target_ids = []
        if category_id:
            cat = db.query(Category).filter(Category.id == category_id).first()
            if cat:
                target_ids = [cat.id] + [s.id for s in cat.subcategories]
            else:
                target_ids = [-1]
        elif category_slug:
            cat = db.query(Category).filter(Category.slug == category_slug.strip().lower()).first()
            if cat:
                target_ids = [cat.id] + [s.id for s in cat.subcategories]
            else:
                target_ids = [-1]
        query = query.filter(Product.category_id.in_(target_ids))

    # 3. Brand Filter (supports single slug, id, or multiple comma-separated slugs)
    target_brand_ids = set()
    if brands:
        slug_list = [s.strip().lower() for s in brands.split(',') if s.strip()]
        if slug_list:
            found_brands = db.query(Brand.id).filter(Brand.slug.in_(slug_list)).all()
            target_brand_ids.update([b.id for b in found_brands])
            if not target_brand_ids:
                target_brand_ids.add(-1)
    elif brand_slug:
        b = db.query(Brand).filter(Brand.slug == brand_slug.strip().lower()).first()
        target_brand_ids.add(b.id if b else -1)
    elif brand_id:
        target_brand_ids.add(brand_id)

    if target_brand_ids:
        query = query.filter(Product.brand_id.in_(list(target_brand_ids)))

    # 4. Price Filter (Decimal safe, variant aware)
    if min_price is not None and min_price >= 0:
        query = query.filter(
            or_(
                Product.price >= min_price,
                Product.id.in_(
                    db.query(ProductVariant.product_id).filter(
                        ProductVariant.is_active == True,
                        ProductVariant.price >= min_price
                    )
                )
            )
        )
    if max_price is not None and max_price >= 0:
        query = query.filter(
            or_(
                Product.price <= max_price,
                Product.id.in_(
                    db.query(ProductVariant.product_id).filter(
                        ProductVariant.is_active == True,
                        ProductVariant.price <= max_price
                    )
                )
            )
        )

    # 5. Discount Filter
    if min_discount is not None and min_discount > 0:
        query = query.filter(
            or_(
                Product.discount_percent >= min_discount,
                case(
                    (Product.mrp > Product.price, ((Product.mrp - Product.price) / Product.mrp) * 100.0),
                    else_=0.0
                ) >= min_discount
            )
        )

    # 6. Availability Filter (Authoritative Checkpoint 06 Inventory)
    if availability in ("in_stock", "out_of_stock"):
        # Subquery of total active available inventory per product
        inv_sub = db.query(
            Inventory.product_id,
            func.coalesce(func.sum(Inventory.available_quantity), 0).label("avail_sum")
        ).filter(
            Inventory.is_active == True
        ).group_by(
            Inventory.product_id
        ).subquery()

        if availability == "in_stock":
            # Product has inventory available_quantity > 0 OR product.stock > 0
            query = query.filter(
                or_(
                    Product.id.in_(
                        db.query(inv_sub.c.product_id).filter(inv_sub.c.avail_sum > 0)
                    ),
                    and_(
                        ~Product.id.in_(db.query(inv_sub.c.product_id)),
                        Product.stock > 0
                    )
                )
            )
        else: # out_of_stock
            query = query.filter(
                or_(
                    Product.id.in_(
                        db.query(inv_sub.c.product_id).filter(inv_sub.c.avail_sum <= 0)
                    ),
                    and_(
                        ~Product.id.in_(db.query(inv_sub.c.product_id)),
                        Product.stock <= 0
                    )
                )
            )

    # 7. Attribute Filters (Variant-aware & Normalized)
    if attribute_filters:
        for attr_slug, val_slugs in attribute_filters.items():
            if not val_slugs:
                continue

            # Check normalized attribute tables
            matching_product_ids = db.query(distinct(ProductVariant.product_id)).join(
                VariantAttributeValue, VariantAttributeValue.variant_id == ProductVariant.id
            ).join(
                ProductAttributeValue, ProductAttributeValue.id == VariantAttributeValue.attribute_value_id
            ).join(
                ProductAttribute, ProductAttribute.id == ProductAttributeValue.attribute_id
            ).filter(
                ProductVariant.is_active == True,
                or_(
                    func.lower(ProductAttribute.slug) == attr_slug,
                    func.lower(ProductAttribute.name) == attr_slug
                ),
                or_(
                    func.lower(ProductAttributeValue.slug).in_(val_slugs),
                    func.lower(ProductAttributeValue.value).in_(val_slugs)
                )
            ).all()

            matched_ids = [p[0] for p in matching_product_ids]

            # Also check text / json attribute fallbacks in variant title or product description
            variant_title_conditions = [
                ProductVariant.title.ilike(f"%{v}%") for v in val_slugs
            ]
            text_matching_prod_ids = db.query(distinct(ProductVariant.product_id)).filter(
                ProductVariant.is_active == True,
                or_(*variant_title_conditions)
            ).all()
            for p in text_matching_prod_ids:
                if p[0] not in matched_ids:
                    matched_ids.append(p[0])

            query = query.filter(Product.id.in_(matched_ids if matched_ids else [-1]))

    # 8. Feature / Promo Flags
    if is_featured is not None:
        query = query.filter(Product.is_featured == is_featured)
    if is_new_arrival is not None:
        query = query.filter(Product.is_new_arrival == is_new_arrival)
    if is_best_seller is not None:
        query = query.filter(Product.is_best_seller == is_best_seller)
    if is_flash_sale is not None:
        query = query.filter(Product.is_flash_sale == is_flash_sale)

    # 9. Sorting Strategy
    sort_choice = (sort_by or "").lower().strip()
    if sort_choice in ("price_asc", "price_low_high", "price_low_to_high"):
        query = query.order_by(asc(Product.price), asc(Product.id))
    elif sort_choice in ("price_desc", "price_high_low", "price_high_to_low"):
        query = query.order_by(desc(Product.price), desc(Product.id))
    elif sort_choice in ("name_asc", "name"):
        query = query.order_by(asc(Product.name), asc(Product.id))
    elif sort_choice in ("name_desc",):
        query = query.order_by(desc(Product.name), desc(Product.id))
    elif sort_choice in ("discount", "discount_desc", "discount_high_low"):
        query = query.order_by(desc(Product.discount_percent), desc(Product.id))
    elif sort_choice in ("popularity", "popular", "best_selling"):
        query = query.order_by(
            desc(Product.is_best_seller), 
            desc(Product.is_featured), 
            desc(Product.created_at), 
            asc(Product.id)
        )
    elif clean_search and relevance_score is not None:
        # Default for search: deterministic relevance score first, then newest
        query = query.order_by(
            desc(relevance_score),
            desc(Product.is_best_seller),
            desc(Product.created_at),
            asc(Product.id)
        )
    else: # newest
        query = query.order_by(asc(Product.sort_order), desc(Product.created_at), desc(Product.id))

    return query, relevance_score

def get_catalog_facets(db: Session) -> CatalogFacets:
    """
    Computes real dynamic filter facets directly from PostgreSQL:
    - categories with live active product counts
    - brands with live active product counts
    - price min/max range
    - inventory availability (in_stock vs out_of_stock)
    - dynamic product attributes with active variant values and counts
    """
    # 1. Category Facets
    cat_counts = db.query(
        Category.id,
        Category.name,
        Category.slug,
        func.count(Product.id).label("product_count")
    ).join(
        Product, Product.category_id == Category.id
    ).filter(
        Product.is_active == True,
        Product.status == "active",
        Category.is_active == True
    ).group_by(
        Category.id, Category.name, Category.slug
    ).order_by(
        desc("product_count"), Category.name.asc()
    ).all()

    category_facets = [
        FacetCategoryItem(id=c[0], name=c[1], slug=c[2], count=c[3])
        for c in cat_counts
    ]

    # 2. Brand Facets
    brand_counts = db.query(
        Brand.id,
        Brand.name,
        Brand.slug,
        func.count(Product.id).label("product_count")
    ).join(
        Product, Product.brand_id == Brand.id
    ).filter(
        Product.is_active == True,
        Product.status == "active",
        Brand.is_active == True
    ).group_by(
        Brand.id, Brand.name, Brand.slug
    ).order_by(
        desc("product_count"), Brand.name.asc()
    ).all()

    brand_facets = [
        FacetBrandItem(id=b[0], name=b[1], slug=b[2], count=b[3])
        for b in brand_counts
    ]

    # 3. Price Range
    price_stats = db.query(
        func.min(Product.price).label("min_price"),
        func.max(Product.price).label("max_price")
    ).filter(
        Product.is_active == True,
        Product.status == "active"
    ).first()

    min_p = float(price_stats.min_price) if price_stats and price_stats.min_price is not None else 0.0
    max_p = float(price_stats.max_price) if price_stats and price_stats.max_price is not None else 0.0

    # 4. Availability counts from Inventory
    inv_sub = db.query(
        Inventory.product_id,
        func.coalesce(func.sum(Inventory.available_quantity), 0).label("avail_sum")
    ).filter(
        Inventory.is_active == True
    ).group_by(
        Inventory.product_id
    ).subquery()

    # Active products with inventory
    total_active_prods = db.query(Product).filter(
        Product.is_active == True,
        Product.status == "active"
    ).count()

    in_stock_count = db.query(Product).filter(
        Product.is_active == True,
        Product.status == "active",
        or_(
            Product.id.in_(
                db.query(inv_sub.c.product_id).filter(inv_sub.c.avail_sum > 0)
            ),
            and_(
                ~Product.id.in_(db.query(inv_sub.c.product_id)),
                Product.stock > 0
            )
        )
    ).count()

    out_of_stock_count = max(0, total_active_prods - in_stock_count)

    # 5. Dynamic Attributes
    attribute_facets = []
    attributes = db.query(ProductAttribute).all()
    for attr in attributes:
        values_list = []
        for val in attr.values:
            # Count products with active variants having this attribute value
            val_count = db.query(distinct(ProductVariant.product_id)).join(
                VariantAttributeValue, VariantAttributeValue.variant_id == ProductVariant.id
            ).join(
                Product, Product.id == ProductVariant.product_id
            ).filter(
                Product.is_active == True,
                Product.status == "active",
                ProductVariant.is_active == True,
                VariantAttributeValue.attribute_value_id == val.id
            ).count()

            if val_count > 0:
                values_list.append(
                    FacetAttributeValue(
                        value=val.value,
                        slug=val.slug,
                        count=val_count
                    )
                )

        if values_list:
            attribute_facets.append(
                FacetAttribute(
                    name=attr.name,
                    slug=attr.slug,
                    values=values_list
                )
            )

    return CatalogFacets(
        categories=category_facets,
        brands=brand_facets,
        price_range={"min": min_p, "max": max_p},
        availability={"in_stock": in_stock_count, "out_of_stock": out_of_stock_count},
        attributes=attribute_facets
    )

def get_search_suggestions(db: Session, raw_q: Optional[str]) -> SearchSuggestionsResponse:
    """
    Returns deterministic, safe suggestions for search input:
    - Products: up to 5 matching products
    - Categories: up to 3 matching categories
    - Brands: up to 3 matching brands
    """
    clean_q = normalize_search_query(raw_q)
    if not clean_q or len(clean_q) < 1:
        return SearchSuggestionsResponse(products=[], categories=[], brands=[])

    search_pattern = f"%{clean_q}%"
    clean_lower = clean_q.lower()

    # 1. Products (limit 5)
    prod_query = db.query(Product).options(
        joinedload(Product.images),
        joinedload(Product.category),
        joinedload(Product.brand)
    ).filter(
        Product.is_active == True,
        Product.status == "active",
        or_(
            Product.name.ilike(search_pattern),
            Product.sku.ilike(search_pattern),
            Product.slug.ilike(search_pattern)
        )
    ).order_by(
        case(
            (func.lower(Product.name) == clean_lower, 100),
            (func.lower(Product.name).startswith(clean_lower), 80),
            (func.lower(Product.sku) == clean_lower, 70),
            else_=10
        ).desc(),
        Product.name.asc()
    ).limit(5).all()

    product_items = []
    for p in prod_query:
        primary_img = next((img.image_url for img in p.images if img.is_primary), None)
        if not primary_img and p.images:
            primary_img = p.images[0].image_url

        product_items.append(
            ProductSuggestionItem(
                id=p.id,
                name=p.name,
                slug=p.slug,
                price=float(p.price),
                mrp=float(p.mrp),
                image_url=primary_img,
                category_name=p.category.name if p.category else None,
                brand_name=p.brand.name if p.brand else None,
                discount_percent=float(p.discount_percent or 0.0)
            )
        )

    # 2. Categories (limit 3)
    cat_query = db.query(
        Category.id,
        Category.name,
        Category.slug,
        func.count(Product.id).label("cnt")
    ).outerjoin(
        Product, and_(Product.category_id == Category.id, Product.is_active == True, Product.status == "active")
    ).filter(
        Category.is_active == True,
        or_(
            Category.name.ilike(search_pattern),
            Category.slug.ilike(search_pattern)
        )
    ).group_by(
        Category.id, Category.name, Category.slug
    ).order_by(
        case(
            (func.lower(Category.name) == clean_lower, 100),
            (func.lower(Category.name).startswith(clean_lower), 80),
            else_=10
        ).desc(),
        desc("cnt"),
        Category.name.asc()
    ).limit(3).all()

    category_items = [
        CategorySuggestionItem(id=c[0], name=c[1], slug=c[2], product_count=c[3])
        for c in cat_query
    ]

    # 3. Brands (limit 3)
    brand_query = db.query(
        Brand.id,
        Brand.name,
        Brand.slug,
        func.count(Product.id).label("cnt")
    ).outerjoin(
        Product, and_(Product.brand_id == Brand.id, Product.is_active == True, Product.status == "active")
    ).filter(
        Brand.is_active == True,
        or_(
            Brand.name.ilike(search_pattern),
            Brand.slug.ilike(search_pattern)
        )
    ).group_by(
        Brand.id, Brand.name, Brand.slug
    ).order_by(
        case(
            (func.lower(Brand.name) == clean_lower, 100),
            (func.lower(Brand.name).startswith(clean_lower), 80),
            else_=10
        ).desc(),
        desc("cnt"),
        Brand.name.asc()
    ).limit(3).all()

    brand_items = [
        BrandSuggestionItem(id=b[0], name=b[1], slug=b[2], product_count=b[3])
        for b in brand_query
    ]

    return SearchSuggestionsResponse(
        products=product_items,
        categories=category_items,
        brands=brand_items
    )
