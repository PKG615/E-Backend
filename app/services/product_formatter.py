from typing import Any

from app.schemas.product import ProductResponse


def format_product_response(product: Any) -> ProductResponse:
    """
    Convert a Product SQLAlchemy model into the public ProductResponse schema.

    This formatter is intentionally kept outside the endpoint modules so that
    products, admin products, CMS, cart/wishlist, and other endpoints can
    share the same response structure without circular imports.
    """

    # Product relationships
    images = list(getattr(product, "images", None) or [])
    variants = list(getattr(product, "variants", None) or [])

    # Product-level stock remains authoritative unless your existing business
    # logic explicitly updates Product.stock from variants.
    stock_quantity = int(getattr(product, "stock", 0) or 0)

    price = float(getattr(product, "price", 0) or 0)
    mrp = float(getattr(product, "mrp", 0) or 0)

    # Use the persisted product discount when available.
    discount_percentage = float(
        getattr(product, "discount_percent", 0) or 0
    )

    # If no persisted discount is available, calculate it from MRP/price.
    if discount_percentage <= 0 and mrp > 0 and price < mrp:
        discount_percentage = round(((mrp - price) / mrp) * 100, 2)

    tax_percentage = float(
        getattr(product, "tax_percent", 0) or 0
    )

    # Product attributes are already stored as JSON.
    available_attributes = {}

    raw_attributes = getattr(product, "attributes", None)

    if isinstance(raw_attributes, dict):
        available_attributes = {
            str(key): list(value) if isinstance(value, (list, tuple, set)) else [value]
            for key, value in raw_attributes.items()
            if value is not None
        }

    # Also collect attributes from active variants when available.
    for variant in variants:
        if not getattr(variant, "is_active", True):
            continue

        variant_attributes = getattr(variant, "attributes", None)

        if not isinstance(variant_attributes, dict):
            continue

        for key, value in variant_attributes.items():
            if value is None:
                continue

            values = (
                list(value)
                if isinstance(value, (list, tuple, set))
                else [value]
            )

            existing = available_attributes.setdefault(str(key), [])

            for item in values:
                if item not in existing:
                    existing.append(item)

    # Only approved/visible reviews should contribute to public rating data.
    reviews = list(getattr(product, "reviews", None) or [])

    approved_reviews = [
        review
        for review in reviews
        if getattr(review, "is_approved", True)
        and str(getattr(review, "status", "approved")).lower() == "approved"
    ]

    ratings = [
        int(review.rating)
        for review in approved_reviews
        if getattr(review, "rating", None) is not None
    ]

    total_reviews = len(ratings)

    average_rating = (
        round(sum(ratings) / total_reviews, 2)
        if total_reviews
        else 0.0
    )

    # Preserve ProductResponse's ORM-compatible fields.
    data = {
        "id": product.id,
        "created_at": product.created_at,
        "updated_at": product.updated_at,

        "name": product.name,
        "slug": product.slug,
        "sku": product.sku,
        "description": product.description,
        "short_description": product.short_description,

        "category_id": product.category_id,
        "brand_id": product.brand_id,

        "price": price,
        "mrp": mrp,
        "discount_percent": float(
            getattr(product, "discount_percent", 0) or 0
        ),
        "tax_percent": tax_percentage,
        "stock": stock_quantity,

        "status": product.status,
        "is_active": product.is_active,
        "is_featured": product.is_featured,
        "is_new_arrival": product.is_new_arrival,
        "is_best_seller": product.is_best_seller,
        "is_flash_sale": product.is_flash_sale,
        "sort_order": product.sort_order,

        "weight": product.weight,
        "length": product.length,
        "width": product.width,
        "height": product.height,

        "video_url": product.video_url,
        "warranty": product.warranty,
        "warranty_info": product.warranty_info,
        "return_policy": product.return_policy,

        "specifications": product.specifications or {},
        "attributes": product.attributes or {},

        "seo_title": product.seo_title,
        "seo_description": product.seo_description,
        "meta_title": product.meta_title,
        "meta_description": product.meta_description,

        # ProductResponse convenience fields
        "selling_price": price,
        "discount_percentage": discount_percentage,
        "tax_percentage": tax_percentage,
        "stock_quantity": stock_quantity,
        "in_stock": stock_quantity > 0,

        "images": images,
        "variants": variants,
        "available_attributes": available_attributes,

        "category_name": (
            getattr(product.category, "name", None)
            if getattr(product, "category", None)
            else None
        ),

        "brand_name": (
            getattr(product.brand, "name", None)
            if getattr(product, "brand", None)
            else None
        ),

        "average_rating": average_rating,
        "total_reviews": total_reviews,
    }

    return ProductResponse.model_validate(data)