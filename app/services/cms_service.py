from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, asc, desc

from app.models.cms import (
    HomepageSection,
    HomepageSectionItem,
    Collection,
    CollectionProduct,
    NewsletterSubscription
)
from app.models.order import Banner
from app.models.product import Product
from app.models.category import Category, Brand
from app.api.v1.endpoints.products import format_product_response
from app.schemas.cms import (
    HomepageSEO,
    PublicHomepageResponse,
    PublicHomepageSection,
    HomepageSectionResponse,
    HomepageSectionItemResponse,
    HomepageSectionCreate,
    HomepageSectionUpdate,
    BannerCreate,
    BannerUpdate,
    BannerResponse,
    ReorderRequest,
    CollectionResponse,
    CollectionCreate,
    CollectionUpdate,
    CollectionDetailResponse
)


def get_public_homepage_data(db: Session) -> PublicHomepageResponse:
    now = datetime.utcnow()
    
    # 1. Fetch active sections in sort order with scheduling check
    sections = (
        db.query(HomepageSection)
        .filter(HomepageSection.is_active == True)
        .filter(
            or_(HomepageSection.starts_at == None, HomepageSection.starts_at <= now),
            or_(HomepageSection.ends_at == None, HomepageSection.ends_at >= now)
        )
        .order_by(HomepageSection.sort_order.asc(), HomepageSection.id.asc())
        .all()
    )

    public_sections: List[PublicHomepageSection] = []

    for section in sections:
        sec_type = section.section_type.upper()
        config = section.configuration or {}
        data: Dict[str, Any] = {}

        # Fetch active section items
        active_items = [item for item in (section.items or []) if item.is_active]
        active_items.sort(key=lambda x: (x.sort_order, x.id))

        if sec_type == "HERO_BANNER":
            banners_query = db.query(Banner).filter(
                Banner.is_active == True,
                Banner.banner_type.in_(["hero", "slider", "main"])
            )
            # Apply schedule filtering
            banners_query = banners_query.filter(
                or_(Banner.start_at == None, Banner.start_at <= now),
                or_(Banner.end_at == None, Banner.end_at >= now)
            ).order_by(Banner.display_order.asc(), Banner.id.asc())
            
            banners = banners_query.all()
            data["banners"] = [
                {
                    "id": b.id,
                    "title": b.title,
                    "subtitle": b.subtitle,
                    "description": b.description,
                    "image_url": b.image_url,
                    "mobile_image_url": b.mobile_image_url or b.image_url,
                    "alt_text": b.alt_text or b.title,
                    "link_type": b.link_type or "custom",
                    "link_target": b.link_target,
                    "link_url": b.link_url,
                    "cta_label": b.cta_label or "Explore Now",
                    "cta_url": b.cta_url or b.link_url or "/catalog",
                    "banner_type": b.banner_type
                }
                for b in banners
            ]

        elif sec_type == "PROMOTIONAL_BANNER":
            promo_banners = db.query(Banner).filter(
                Banner.is_active == True,
                Banner.banner_type.in_(["promo", "flash_sale", "strip", "offer"])
            ).filter(
                or_(Banner.start_at == None, Banner.start_at <= now),
                or_(Banner.end_at == None, Banner.end_at >= now)
            ).order_by(Banner.display_order.asc(), Banner.id.asc()).all()

            # If specific banner_id is configured
            if config.get("banner_id"):
                targeted = db.query(Banner).filter(
                    Banner.id == config.get("banner_id"),
                    Banner.is_active == True
                ).first()
                if targeted:
                    promo_banners = [targeted]

            data["banners"] = [
                {
                    "id": b.id,
                    "title": b.title,
                    "subtitle": b.subtitle,
                    "description": b.description,
                    "image_url": b.image_url,
                    "mobile_image_url": b.mobile_image_url or b.image_url,
                    "alt_text": b.alt_text or b.title,
                    "link_type": b.link_type or "custom",
                    "link_target": b.link_target,
                    "link_url": b.link_url,
                    "cta_label": b.cta_label or "View Deals",
                    "cta_url": b.cta_url or b.link_url or "/catalog",
                    "banner_type": b.banner_type
                }
                for b in promo_banners
            ]

        elif sec_type in ["CATEGORY_GRID", "FEATURED_CATEGORIES"]:
            cat_ids = [item.item_id for item in active_items if item.item_type == "category" and item.item_id]
            limit = config.get("limit", 6)
            
            if cat_ids:
                categories = db.query(Category).filter(
                    Category.id.in_(cat_ids),
                    Category.is_active == True
                ).all()
                # Maintain sort order of items
                cat_map = {c.id: c for c in categories}
                sorted_categories = [cat_map[cid] for cid in cat_ids if cid in cat_map]
            else:
                sorted_categories = db.query(Category).filter(
                    Category.is_active == True,
                    Category.parent_id == None
                ).order_by(Category.sort_order.asc(), Category.id.asc()).limit(limit).all()

            data["categories"] = [
                {
                    "id": c.id,
                    "name": c.name,
                    "slug": c.slug,
                    "description": c.description,
                    "image_url": c.image or c.image_url or "https://images.unsplash.com/photo-1550009158-9ebf69173e03?auto=format&fit=crop&w=600&q=80",
                    "subcategories_count": len(c.subcategories) if c.subcategories else 0,
                    "subcategories": [
                        {"id": sub.id, "name": sub.name, "slug": sub.slug}
                        for sub in (c.subcategories or []) if sub.is_active
                    ]
                }
                for c in sorted_categories
            ]

        elif sec_type == "FEATURED_PRODUCTS":
            prod_ids = [item.item_id for item in active_items if item.item_type == "product" and item.item_id]
            limit = config.get("limit", 8)

            if prod_ids:
                prods = db.query(Product).filter(
                    Product.id.in_(prod_ids),
                    Product.is_active == True
                ).all()
                prod_map = {p.id: p for p in prods}
                sorted_prods = [prod_map[pid] for pid in prod_ids if pid in prod_map]
            else:
                sorted_prods = db.query(Product).filter(
                    Product.is_active == True,
                    Product.is_featured == True
                ).order_by(Product.sort_order.asc(), Product.id.desc()).limit(limit).all()

            data["products"] = [format_product_response(p) for p in sorted_prods]

        elif sec_type == "NEW_ARRIVALS":
            prod_ids = [item.item_id for item in active_items if item.item_type == "product" and item.item_id]
            limit = config.get("limit", 8)

            if prod_ids:
                prods = db.query(Product).filter(Product.id.in_(prod_ids), Product.is_active == True).all()
                prod_map = {p.id: p for p in prods}
                sorted_prods = [prod_map[pid] for pid in prod_ids if pid in prod_map]
            else:
                sorted_prods = db.query(Product).filter(
                    Product.is_active == True
                ).order_by(Product.created_at.desc(), Product.id.desc()).limit(limit).all()

            data["products"] = [format_product_response(p) for p in sorted_prods]

        elif sec_type == "BEST_SELLERS":
            prod_ids = [item.item_id for item in active_items if item.item_type == "product" and item.item_id]
            limit = config.get("limit", 8)

            if prod_ids:
                prods = db.query(Product).filter(Product.id.in_(prod_ids), Product.is_active == True).all()
                prod_map = {p.id: p for p in prods}
                sorted_prods = [prod_map[pid] for pid in prod_ids if pid in prod_map]
            else:
                sorted_prods = db.query(Product).filter(
                    Product.is_active == True,
                    Product.is_best_seller == True
                ).order_by(Product.sort_order.asc(), Product.id.desc()).limit(limit).all()
                
                # Fallback if none explicitly marked as best seller
                if not sorted_prods:
                    sorted_prods = db.query(Product).filter(
                        Product.is_active == True
                    ).order_by(Product.price.desc()).limit(limit).all()

            data["products"] = [format_product_response(p) for p in sorted_prods]

        elif sec_type == "TRENDING_PRODUCTS":
            limit = config.get("limit", 8)
            sorted_prods = db.query(Product).filter(
                Product.is_active == True,
                or_(Product.is_flash_sale == True, Product.is_featured == True)
            ).order_by(Product.id.desc()).limit(limit).all()
            data["products"] = [format_product_response(p) for p in sorted_prods]

        elif sec_type == "BRANDS":
            brand_ids = [item.item_id for item in active_items if item.item_type == "brand" and item.item_id]
            if brand_ids:
                brands = db.query(Brand).filter(Brand.id.in_(brand_ids), Brand.is_active == True).all()
                b_map = {b.id: b for b in brands}
                sorted_brands = [b_map[bid] for bid in brand_ids if bid in b_map]
            else:
                sorted_brands = db.query(Brand).filter(
                    Brand.is_active == True
                ).order_by(Brand.sort_order.asc(), Brand.id.asc()).all()

            data["brands"] = [
                {
                    "id": b.id,
                    "name": b.name,
                    "slug": b.slug,
                    "description": b.description,
                    "logo_url": b.logo_url or "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=200&q=80",
                    "website_url": b.website_url
                }
                for b in sorted_brands
            ]

        elif sec_type == "COLLECTION":
            collection_id = config.get("collection_id")
            collection_slug = config.get("collection_slug")
            
            coll_query = db.query(Collection).filter(Collection.is_active == True)
            if collection_id:
                coll_query = coll_query.filter(Collection.id == collection_id)
            elif collection_slug:
                coll_query = coll_query.filter(Collection.slug == collection_slug)
            
            coll = coll_query.first()
            if coll:
                prods = [cp.product for cp in coll.products if cp.product and cp.product.is_active]
                data["collection"] = {
                    "id": coll.id,
                    "title": coll.title,
                    "slug": coll.slug,
                    "description": coll.description,
                    "image_url": coll.image_url,
                    "products": [format_product_response(p) for p in prods]
                }
            else:
                data["collection"] = None

        elif sec_type == "TRUST_INFO":
            data["items"] = [
                {
                    "id": item.id,
                    "icon": item.custom_icon or "ShieldCheck",
                    "title": item.custom_title or "",
                    "content": item.custom_content or "",
                    "url": item.custom_url
                }
                for item in active_items
            ]

        elif sec_type == "FAQ":
            data["faqs"] = [
                {
                    "id": item.id,
                    "question": item.custom_title or "",
                    "answer": item.custom_content or ""
                }
                for item in active_items
            ]

        elif sec_type == "NEWSLETTER":
            data["placeholder"] = config.get("placeholder", "Enter your corporate email address...")
            data["button_text"] = config.get("button_text", "Subscribe")
            data["disclaimer"] = config.get("disclaimer", "Unsubscribe at any time. We never share enterprise contact details.")

        elif sec_type == "OFFER":
            data["offer_title"] = config.get("offer_title", section.title)
            data["offer_badge"] = config.get("offer_badge", "Limited Window")
            data["discount_text"] = config.get("discount_text", "Up to 35% Off Enterprise Hardware")
            data["cta_label"] = config.get("cta_label", "Claim Hardware Offer")
            data["cta_url"] = config.get("cta_url", "/catalog?badge=offer")

        else: # CUSTOM_CONTENT
            data["custom_html"] = config.get("html", "")
            data["custom_text"] = section.description or ""

        public_sections.append(
            PublicHomepageSection(
                id=section.id,
                section_key=section.section_key,
                section_type=section.section_type,
                title=section.title,
                subtitle=section.subtitle,
                description=section.description,
                sort_order=section.sort_order,
                configuration=section.configuration,
                data=data
            )
        )

    return PublicHomepageResponse(
        seo=HomepageSEO(),
        sections=public_sections
    )


def list_admin_sections(db: Session) -> List[HomepageSectionResponse]:
    sections = db.query(HomepageSection).order_by(HomepageSection.sort_order.asc(), HomepageSection.id.asc()).all()
    
    result: List[HomepageSectionResponse] = []
    for s in sections:
        items_resp: List[HomepageSectionItemResponse] = []
        for it in (s.items or []):
            item_data = HomepageSectionItemResponse(
                id=it.id,
                section_id=it.section_id,
                item_type=it.item_type,
                item_id=it.item_id,
                custom_title=it.custom_title,
                custom_content=it.custom_content,
                custom_icon=it.custom_icon,
                custom_url=it.custom_url,
                sort_order=it.sort_order,
                is_active=it.is_active,
                created_at=it.created_at,
                updated_at=it.updated_at
            )
            # Hydrate label if linked
            if it.item_type == "category" and it.item_id:
                cat = db.query(Category).filter(Category.id == it.item_id).first()
                if cat:
                    item_data.details = {"name": cat.name, "slug": cat.slug, "image": cat.image or cat.image_url}
            elif it.item_type == "product" and it.item_id:
                p = db.query(Product).filter(Product.id == it.item_id).first()
                if p:
                    item_data.details = {"name": p.name, "sku": p.sku, "price": p.price}
            elif it.item_type == "brand" and it.item_id:
                b = db.query(Brand).filter(Brand.id == it.item_id).first()
                if b:
                    item_data.details = {"name": b.name, "slug": b.slug, "logo": b.logo_url}
            elif it.item_type == "banner" and it.item_id:
                ban = db.query(Banner).filter(Banner.id == it.item_id).first()
                if ban:
                    item_data.details = {"title": ban.title, "type": ban.banner_type, "image_url": ban.image_url}

            items_resp.append(item_data)

        sec_resp = HomepageSectionResponse(
            id=s.id,
            section_key=s.section_key,
            section_type=s.section_type,
            title=s.title,
            subtitle=s.subtitle,
            description=s.description,
            sort_order=s.sort_order,
            is_active=s.is_active,
            starts_at=s.starts_at,
            ends_at=s.ends_at,
            configuration=s.configuration,
            created_at=s.created_at,
            updated_at=s.updated_at,
            items=items_resp
        )
        result.append(sec_resp)
    
    return result


def get_admin_section(db: Session, section_id: int) -> Optional[HomepageSectionResponse]:
    s = db.query(HomepageSection).filter(HomepageSection.id == section_id).first()
    if not s:
        return None
    
    items_resp: List[HomepageSectionItemResponse] = []
    for it in (s.items or []):
        item_data = HomepageSectionItemResponse(
            id=it.id,
            section_id=it.section_id,
            item_type=it.item_type,
            item_id=it.item_id,
            custom_title=it.custom_title,
            custom_content=it.custom_content,
            custom_icon=it.custom_icon,
            custom_url=it.custom_url,
            sort_order=it.sort_order,
            is_active=it.is_active,
            created_at=it.created_at,
            updated_at=it.updated_at
        )
        if it.item_type == "category" and it.item_id:
            cat = db.query(Category).filter(Category.id == it.item_id).first()
            if cat:
                item_data.details = {"name": cat.name, "slug": cat.slug}
        elif it.item_type == "product" and it.item_id:
            p = db.query(Product).filter(Product.id == it.item_id).first()
            if p:
                item_data.details = {"name": p.name, "sku": p.sku, "price": p.price}
        elif it.item_type == "brand" and it.item_id:
            b = db.query(Brand).filter(Brand.id == it.item_id).first()
            if b:
                item_data.details = {"name": b.name, "slug": b.slug}
        items_resp.append(item_data)

    return HomepageSectionResponse(
        id=s.id,
        section_key=s.section_key,
        section_type=s.section_type,
        title=s.title,
        subtitle=s.subtitle,
        description=s.description,
        sort_order=s.sort_order,
        is_active=s.is_active,
        starts_at=s.starts_at,
        ends_at=s.ends_at,
        configuration=s.configuration,
        created_at=s.created_at,
        updated_at=s.updated_at,
        items=items_resp
    )


def create_admin_section(db: Session, data: HomepageSectionCreate) -> HomepageSectionResponse:
    # Next sort_order if 0
    sort_val = data.sort_order
    if sort_val == 0:
        max_order = db.query(HomepageSection.sort_order).order_by(HomepageSection.sort_order.desc()).first()
        sort_val = (max_order[0] + 1) if max_order else 1

    section = HomepageSection(
        section_key=data.section_key,
        section_type=data.section_type.upper(),
        title=data.title,
        subtitle=data.subtitle,
        description=data.description,
        sort_order=sort_val,
        is_active=data.is_active,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        configuration=data.configuration or {}
    )
    db.add(section)
    db.flush()

    # If item_ids provided, create items
    if data.item_ids:
        default_item_type = "product"
        if "CATEGORY" in data.section_type.upper():
            default_item_type = "category"
        elif "BRAND" in data.section_type.upper():
            default_item_type = "brand"

        for idx, item_id in enumerate(data.item_ids, start=1):
            sec_item = HomepageSectionItem(
                section_id=section.id,
                item_type=default_item_type,
                item_id=item_id,
                sort_order=idx,
                is_active=True
            )
            db.add(sec_item)

    if data.items_data:
        for idx, it in enumerate(data.items_data, start=1):
            sec_item = HomepageSectionItem(
                section_id=section.id,
                item_type=it.item_type,
                item_id=it.item_id,
                custom_title=it.custom_title,
                custom_content=it.custom_content,
                custom_icon=it.custom_icon,
                custom_url=it.custom_url,
                sort_order=it.sort_order or idx,
                is_active=it.is_active
            )
            db.add(sec_item)

    db.commit()
    db.refresh(section)
    return get_admin_section(db, section.id) # type: ignore


def update_admin_section(db: Session, section_id: int, data: HomepageSectionUpdate) -> Optional[HomepageSectionResponse]:
    section = db.query(HomepageSection).filter(HomepageSection.id == section_id).first()
    if not section:
        return None

    if data.section_key is not None:
        section.section_key = data.section_key
    if data.section_type is not None:
        section.section_type = data.section_type.upper()
    if data.title is not None:
        section.title = data.title
    if data.subtitle is not None:
        section.subtitle = data.subtitle
    if data.description is not None:
        section.description = data.description
    if data.sort_order is not None:
        section.sort_order = data.sort_order
    if data.is_active is not None:
        section.is_active = data.is_active
    if data.starts_at is not None:
        section.starts_at = data.starts_at
    if data.ends_at is not None:
        section.ends_at = data.ends_at
    if data.configuration is not None:
        section.configuration = data.configuration

    # If item_ids or items_data supplied, replace items
    if data.item_ids is not None:
        db.query(HomepageSectionItem).filter(HomepageSectionItem.section_id == section.id).delete()
        default_item_type = "product"
        if "CATEGORY" in section.section_type.upper():
            default_item_type = "category"
        elif "BRAND" in section.section_type.upper():
            default_item_type = "brand"

        for idx, item_id in enumerate(data.item_ids, start=1):
            sec_item = HomepageSectionItem(
                section_id=section.id,
                item_type=default_item_type,
                item_id=item_id,
                sort_order=idx,
                is_active=True
            )
            db.add(sec_item)

    elif data.items_data is not None:
        db.query(HomepageSectionItem).filter(HomepageSectionItem.section_id == section.id).delete()
        for idx, it in enumerate(data.items_data, start=1):
            sec_item = HomepageSectionItem(
                section_id=section.id,
                item_type=it.item_type,
                item_id=it.item_id,
                custom_title=it.custom_title,
                custom_content=it.custom_content,
                custom_icon=it.custom_icon,
                custom_url=it.custom_url,
                sort_order=it.sort_order or idx,
                is_active=it.is_active
            )
            db.add(sec_item)

    db.commit()
    db.refresh(section)
    return get_admin_section(db, section.id)


def delete_admin_section(db: Session, section_id: int) -> bool:
    section = db.query(HomepageSection).filter(HomepageSection.id == section_id).first()
    if not section:
        return False
    db.delete(section)
    db.commit()
    return True


def reorder_admin_sections(db: Session, req: ReorderRequest) -> List[HomepageSectionResponse]:
    for item in req.items:
        db.query(HomepageSection).filter(HomepageSection.id == item.id).update(
            {"sort_order": item.sort_order}
        )
    db.commit()
    return list_admin_sections(db)


def toggle_admin_section_status(db: Session, section_id: int, is_active: bool) -> Optional[HomepageSectionResponse]:
    section = db.query(HomepageSection).filter(HomepageSection.id == section_id).first()
    if not section:
        return None
    section.is_active = is_active
    db.commit()
    db.refresh(section)
    return get_admin_section(db, section.id)


def subscribe_newsletter(db: Session, email: str) -> Dict[str, Any]:
    clean_email = email.strip().lower()
    existing = db.query(NewsletterSubscription).filter(NewsletterSubscription.email == clean_email).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.commit()
        return {"id": existing.id, "email": existing.email, "message": "Subscription renewed successfully."}
    
    sub = NewsletterSubscription(email=clean_email, is_active=True)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return {"id": sub.id, "email": sub.email, "message": "Subscribed successfully."}


# =========================================================================
# COLLECTION SERVICES
# =========================================================================

def _format_collection_response(coll: Collection, include_products: bool = True) -> CollectionResponse:
    prods_data: List[Dict[str, Any]] = []
    if include_products and coll.products:
        sorted_cp = sorted(coll.products, key=lambda x: (x.sort_order, x.id))
        for cp in sorted_cp:
            p = cp.product
            if p:
                img = None
                if p.images and len(p.images) > 0:
                    primary_img = next((i for i in p.images if getattr(i, 'is_primary', False)), p.images[0])
                    img = primary_img.image_url if hasattr(primary_img, 'image_url') else getattr(primary_img, 'url', None)
                prods_data.append({
                    "product_id": p.id,
                    "sort_order": cp.sort_order,
                    "name": p.name,
                    "slug": p.slug,
                    "sku": p.sku,
                    "price": float(p.price) if p.price is not None else 0.0,
                    "sale_price": float(p.sale_price) if getattr(p, 'sale_price', None) is not None else None,
                    "image_url": img,
                    "is_active": p.is_active,
                    "stock": p.stock_quantity if hasattr(p, 'stock_quantity') else 0
                })

    return CollectionResponse(
        id=coll.id,
        title=coll.title,
        slug=coll.slug,
        description=coll.description,
        image_url=coll.image_url,
        sort_order=coll.sort_order,
        is_active=coll.is_active,
        seo_title=coll.seo_title,
        seo_description=coll.seo_description,
        created_at=coll.created_at,
        updated_at=coll.updated_at,
        products_count=len(coll.products) if coll.products else 0,
        products=prods_data
    )


def list_admin_collections(
    db: Session,
    search: Optional[str] = None,
    is_active: Optional[bool] = None
) -> List[CollectionResponse]:
    query = db.query(Collection)
    if search:
        s = f"%{search.strip().lower()}%"
        query = query.filter(or_(Collection.title.ilike(s), Collection.slug.ilike(s), Collection.description.ilike(s)))
    if is_active is not None:
        query = query.filter(Collection.is_active == is_active)
    
    colls = query.order_by(Collection.sort_order.asc(), Collection.id.asc()).all()
    return [_format_collection_response(c, include_products=True) for c in colls]


def get_admin_collection(db: Session, collection_id: int) -> Optional[CollectionResponse]:
    coll = db.query(Collection).filter(Collection.id == collection_id).first()
    if not coll:
        return None
    return _format_collection_response(coll, include_products=True)


def create_admin_collection(db: Session, data: CollectionCreate) -> CollectionResponse:
    # Ensure unique slug
    base_slug = data.slug.strip().lower() if data.slug else data.title.strip().lower().replace(" ", "-")
    existing = db.query(Collection).filter(Collection.slug == base_slug).first()
    if existing:
        base_slug = f"{base_slug}-{int(datetime.utcnow().timestamp())}"

    sort_val = data.sort_order
    if sort_val == 0:
        max_order = db.query(Collection.sort_order).order_by(Collection.sort_order.desc()).first()
        sort_val = (max_order[0] + 1) if max_order else 1

    coll = Collection(
        title=data.title,
        slug=base_slug,
        description=data.description,
        image_url=data.image_url,
        sort_order=sort_val,
        is_active=data.is_active,
        seo_title=data.seo_title,
        seo_description=data.seo_description
    )
    db.add(coll)
    db.flush()

    if data.product_ids:
        for idx, pid in enumerate(data.product_ids, start=1):
            prod = db.query(Product).filter(Product.id == pid).first()
            if prod:
                cp = CollectionProduct(
                    collection_id=coll.id,
                    product_id=prod.id,
                    sort_order=idx
                )
                db.add(cp)

    db.commit()
    db.refresh(coll)
    return _format_collection_response(coll, include_products=True)


def update_admin_collection(
    db: Session,
    collection_id: int,
    data: CollectionUpdate
) -> Optional[CollectionResponse]:
    coll = db.query(Collection).filter(Collection.id == collection_id).first()
    if not coll:
        return None

    if data.title is not None:
        coll.title = data.title
    if data.slug is not None:
        slug_clean = data.slug.strip().lower()
        existing = db.query(Collection).filter(Collection.slug == slug_clean, Collection.id != collection_id).first()
        if not existing:
            coll.slug = slug_clean
    if data.description is not None:
        coll.description = data.description
    if data.image_url is not None:
        coll.image_url = data.image_url
    if data.sort_order is not None:
        coll.sort_order = data.sort_order
    if data.is_active is not None:
        coll.is_active = data.is_active
    if data.seo_title is not None:
        coll.seo_title = data.seo_title
    if data.seo_description is not None:
        coll.seo_description = data.seo_description

    if data.product_ids is not None:
        db.query(CollectionProduct).filter(CollectionProduct.collection_id == coll.id).delete()
        for idx, pid in enumerate(data.product_ids, start=1):
            prod = db.query(Product).filter(Product.id == pid).first()
            if prod:
                cp = CollectionProduct(
                    collection_id=coll.id,
                    product_id=prod.id,
                    sort_order=idx
                )
                db.add(cp)

    db.commit()
    db.refresh(coll)
    return _format_collection_response(coll, include_products=True)


def delete_admin_collection(db: Session, collection_id: int) -> bool:
    coll = db.query(Collection).filter(Collection.id == collection_id).first()
    if not coll:
        return False
    db.delete(coll)
    db.commit()
    return True


def reorder_admin_collections(db: Session, req: ReorderRequest) -> List[CollectionResponse]:
    for item in req.items:
        db.query(Collection).filter(Collection.id == item.id).update({"sort_order": item.sort_order})
    db.commit()
    return list_admin_collections(db)


def toggle_admin_collection_status(db: Session, collection_id: int, is_active: bool) -> Optional[CollectionResponse]:
    coll = db.query(Collection).filter(Collection.id == collection_id).first()
    if not coll:
        return None
    coll.is_active = is_active
    db.commit()
    db.refresh(coll)
    return _format_collection_response(coll, include_products=True)


def list_public_collections(db: Session) -> List[CollectionResponse]:
    colls = (
        db.query(Collection)
        .filter(Collection.is_active == True)
        .order_by(Collection.sort_order.asc(), Collection.id.asc())
        .all()
    )
    return [_format_collection_response(c, include_products=False) for c in colls]


def get_public_collection_by_slug(db: Session, slug: str) -> Optional[Dict[str, Any]]:
    coll = (
        db.query(Collection)
        .filter(Collection.slug == slug.strip().lower(), Collection.is_active == True)
        .first()
    )
    if not coll:
        return None

    # Get active products in sort order
    active_products = []
    if coll.products:
        sorted_cp = sorted(coll.products, key=lambda x: (x.sort_order, x.id))
        for cp in sorted_cp:
            if cp.product and cp.product.is_active:
                active_products.append(format_product_response(cp.product))

    return {
        "id": coll.id,
        "title": coll.title,
        "slug": coll.slug,
        "description": coll.description,
        "image_url": coll.image_url,
        "seo_title": coll.seo_title or coll.title,
        "seo_description": coll.seo_description or coll.description,
        "products_count": len(active_products),
        "products": active_products
    }

