from typing import Optional, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, or_, func

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user, get_current_user_optional
from app.models.product import Product, ProductImage, ProductVariant
from app.models.user import User
from app.schemas.common import APIResponse
from app.services.catalog_service import build_catalog_query, parse_attribute_filters, get_search_suggestions
from app.services.review_service import ReviewService
from app.schemas.reviews import ReviewCreate, ReviewUpdate, QuestionCreate, AnswerCreate

router = APIRouter()


def serialize_product(p: Product) -> dict:
    images = [
        {"id": i.id, "product_id": i.product_id, "image_url": i.image_url, "alt_text": i.alt_text,
         "is_primary": i.is_primary, "sort_order": i.sort_order, "display_order": i.display_order}
        for i in (p.images or [])
    ]
    variants = [
        {"id": v.id, "product_id": v.product_id, "sku": v.sku, "title": v.title,
         "name": v.title, "price": float(v.price), "mrp": float(v.mrp), "stock": v.stock,
         "stock_quantity": v.stock, "attributes": v.attributes or {}, "image_url": v.image_url,
         "is_active": v.is_active, "sort_order": v.sort_order}
        for v in (p.variants or []) if v.is_active
    ]
    return {
        "id": p.id, "name": p.name, "slug": p.slug, "sku": p.sku,
        "description": p.description, "short_description": p.short_description,
        "category_id": p.category_id, "brand_id": p.brand_id,
        "category_name": p.category.name if p.category else None,
        "brand_name": p.brand.name if p.brand else None,
        "price": float(p.price), "mrp": float(p.mrp),
        "selling_price": float(p.price), "discount_percent": float(p.discount_percent or 0),
        "discount_percentage": float(p.discount_percent or 0),
        "tax_percent": float(p.tax_percent or 0), "tax_percentage": float(p.tax_percent or 0),
        "stock": int(p.stock or 0), "stock_quantity": int(p.stock or 0), "in_stock": int(p.stock or 0) > 0,
        "status": p.status, "is_active": p.is_active, "is_featured": p.is_featured,
        "is_new_arrival": p.is_new_arrival, "is_best_seller": p.is_best_seller,
        "is_flash_sale": p.is_flash_sale, "sort_order": p.sort_order,
        "weight": p.weight, "length": p.length, "width": p.width, "height": p.height,
        "video_url": p.video_url, "warranty": p.warranty, "warranty_info": p.warranty_info,
        "return_policy": p.return_policy, "specifications": p.specifications or {}, "attributes": p.attributes or {},
        "seo_title": p.seo_title, "seo_description": p.seo_description,
        "meta_title": p.meta_title, "meta_description": p.meta_description,
        "images": images, "variants": variants, "available_attributes": p.attributes or {},
        "average_rating": 0.0, "total_reviews": 0,
        "created_at": p.created_at, "updated_at": p.updated_at,
    }


def product_query(db: Session):
    return db.query(Product).options(
        joinedload(Product.category), joinedload(Product.brand),
        joinedload(Product.images), joinedload(Product.variants)
    ).filter(Product.is_active == True, Product.status == "active")


@router.get("")
def list_products(
    search: Optional[str] = None, q: Optional[str] = None,
    category_slug: Optional[str] = None, category_id: Optional[int] = None,
    subcategory_slug: Optional[str] = None, subcategory_id: Optional[int] = None,
    brand_slug: Optional[str] = None, brand_id: Optional[int] = None, brands: Optional[str] = None,
    min_price: Optional[float] = None, max_price: Optional[float] = None,
    min_discount: Optional[float] = None, availability: Optional[str] = None,
    attributes: Optional[str] = None, sort_by: Optional[str] = None, sort: Optional[str] = None,
    is_featured: Optional[bool] = None, featured: Optional[bool] = None,
    is_new_arrival: Optional[bool] = None, new_arrival: Optional[bool] = None,
    is_best_seller: Optional[bool] = None, best_seller: Optional[bool] = None,
    is_flash_sale: Optional[bool] = None, page: int = Query(1, ge=1), limit: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db)
):
    attr_filters = parse_attribute_filters(attributes, {})
    query, _ = build_catalog_query(db, search=search or q, category_slug=category_slug, category_id=category_id,
        subcategory_slug=subcategory_slug, subcategory_id=subcategory_id, brand_slug=brand_slug,
        brand_id=brand_id, brands=brands, min_price=min_price, max_price=max_price,
        min_discount=min_discount, availability=availability, attribute_filters=attr_filters,
        sort_by=sort_by or sort, is_featured=is_featured if is_featured is not None else featured,
        is_new_arrival=is_new_arrival if is_new_arrival is not None else new_arrival,
        is_best_seller=is_best_seller if is_best_seller is not None else best_seller,
        is_flash_sale=is_flash_sale)
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return APIResponse(success=True, data={"items": [serialize_product(p) for p in items], "total": total,
        "page": page, "limit": limit, "total_pages": max(1, (total + limit - 1) // limit)})


@router.get("/suggestions")
def product_suggestions(q: Optional[str] = None, db: Session = Depends(get_db)):
    return APIResponse(success=True, data=get_search_suggestions(db, q))


@router.get("/{product_id_or_slug}")
def get_product(product_id_or_slug: str, db: Session = Depends(get_db)):
    p = product_query(db).filter(or_(Product.slug == product_id_or_slug, Product.id == int(product_id_or_slug) if product_id_or_slug.isdigit() else -1)).first()
    if not p:
        raise HTTPException(404, "Product not found")
    return APIResponse(success=True, data=serialize_product(p))


@router.get("/{product_id_or_slug}/related")
def related_products(product_id_or_slug: str, limit: int = Query(6, ge=1, le=20), db: Session = Depends(get_db)):
    p = product_query(db).filter(or_(Product.slug == product_id_or_slug, Product.id == int(product_id_or_slug) if product_id_or_slug.isdigit() else -1)).first()
    if not p:
        raise HTTPException(404, "Product not found")
    query = product_query(db).filter(Product.id != p.id)
    if p.category_id:
        query = query.filter(Product.category_id == p.category_id)
    items = query.order_by(Product.sort_order, desc(Product.created_at)).limit(limit).all()
    return APIResponse(success=True, data=[serialize_product(x) for x in items])


@router.get("/{product_id_or_slug}/images")
def get_images(product_id_or_slug: str, db: Session = Depends(get_db)):
    p = product_query(db).filter(or_(Product.slug == product_id_or_slug, Product.id == int(product_id_or_slug) if product_id_or_slug.isdigit() else -1)).first()
    if not p: raise HTTPException(404, "Product not found")
    return APIResponse(success=True, data=[{"id":i.id,"product_id":i.product_id,"image_url":i.image_url,"alt_text":i.alt_text,"is_primary":i.is_primary,"sort_order":i.sort_order,"display_order":i.display_order} for i in p.images])


@router.get("/{product_id_or_slug}/variants")
def get_variants(product_id_or_slug: str, db: Session = Depends(get_db)):
    p = product_query(db).filter(or_(Product.slug == product_id_or_slug, Product.id == int(product_id_or_slug) if product_id_or_slug.isdigit() else -1)).first()
    if not p: raise HTTPException(404, "Product not found")
    return APIResponse(success=True, data=serialize_product(p)["variants"])


@router.get("/{product_id_or_slug}/attributes")
def get_attributes(product_id_or_slug: str, db: Session = Depends(get_db)):
    p = product_query(db).filter(or_(Product.slug == product_id_or_slug, Product.id == int(product_id_or_slug) if product_id_or_slug.isdigit() else -1)).first()
    if not p: raise HTTPException(404, "Product not found")
    return APIResponse(success=True, data=p.attributes or {})


@router.get("/featured")
def featured(db: Session = Depends(get_db)):
    items = product_query(db).filter(Product.is_featured == True).order_by(Product.sort_order, desc(Product.created_at)).limit(20).all()
    return APIResponse(success=True, data=[serialize_product(p) for p in items])

@router.get("/flash-deals")
def flash_deals(db: Session = Depends(get_db)):
    items = product_query(db).filter(Product.is_flash_sale == True).order_by(Product.sort_order, desc(Product.created_at)).limit(20).all()
    return APIResponse(success=True, data=[serialize_product(p) for p in items])

@router.get("/recently-viewed")
def recently_viewed(ids: Optional[str] = None, db: Session = Depends(get_db)):
    ids_list = [int(x) for x in (ids or "").split(",") if x.strip().isdigit()][:30]
    if not ids_list: return APIResponse(success=True, data=[])
    products = product_query(db).filter(Product.id.in_(ids_list)).all()
    by_id = {p.id:p for p in products}
    return APIResponse(success=True, data=[serialize_product(by_id[i]) for i in ids_list if i in by_id])

# Reviews / Q&A public + authenticated actions
@router.get("/{product_id_or_slug}/reviews")
def list_reviews(product_id_or_slug: str, page:int=1, limit:int=10, sort:str="newest", rating:Optional[int]=None, verified_only:bool=False, current_user:Optional[User]=Depends(get_current_user_optional), db:Session=Depends(get_db)):
    items,total=ReviewService.get_product_reviews(db,product_id_or_slug,page,limit,sort,rating,verified_only,current_user.id if current_user else None)
    return APIResponse(success=True,data={"items":items,"total":total,"page":page,"limit":limit,"total_pages":max(1,(total+limit-1)//limit)})

@router.get("/{product_id_or_slug}/reviews/aggregate")
def review_aggregate(product_id_or_slug:str, db:Session=Depends(get_db)):
    return APIResponse(success=True,data=ReviewService.get_product_aggregate(db,product_id_or_slug))

@router.get("/{product_id_or_slug}/reviews/eligibility")
def review_eligibility(product_id_or_slug:str,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return APIResponse(success=True,data=ReviewService.get_review_eligibility(db,current_user.id,product_id_or_slug))

@router.post("/{product_id_or_slug}/reviews")
def create_review(product_id_or_slug:str,data:ReviewCreate,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return APIResponse(success=True,data=ReviewService.create_review(db,current_user,product_id_or_slug,data))

@router.post("/reviews/{review_id}/helpful")
def helpful(review_id:int,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return APIResponse(success=True,data=ReviewService.vote_helpful(db,current_user,review_id))

@router.get("/{product_id_or_slug}/questions")
def list_questions(product_id_or_slug:str,page:int=1,limit:int=10,current_user:Optional[User]=Depends(get_current_user_optional),db:Session=Depends(get_db)):
    items,total=ReviewService.get_product_questions(db,product_id_or_slug,page,limit,current_user.id if current_user else None)
    return APIResponse(success=True,data={"items":items,"total":total,"page":page,"limit":limit,"total_pages":max(1,(total+limit-1)//limit)})

@router.post("/{product_id_or_slug}/questions")
def create_question(product_id_or_slug:str,data:QuestionCreate,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return APIResponse(success=True,data=ReviewService.create_question(db,current_user,product_id_or_slug,data))

@router.post("/questions/{question_id}/answers")
def answer_question(question_id:int,data:AnswerCreate,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return APIResponse(success=True,data=ReviewService.create_answer(db,current_user,question_id,data))

# Static routes must precede dynamic /{product_id_or_slug} routes in Starlette matching.
router.routes.sort(key=lambda r: (getattr(r, 'path', '').count('{'), -len(getattr(r, 'path', ''))))
