from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db

from app.models.order import Banner

from app.models.category import Category

from app.models.product import Product

from app.schemas.dashboard import HomepageContent, BannerResponse

from app.schemas.category import CategoryResponse, CategorySummary

from app.schemas.common import APIResponse

from app.api.v1.endpoints.products import format_product_response

router = APIRouter()

@router.get("/homepage", response_model=APIResponse[HomepageContent])
def get_homepage_content(db: Session = Depends(get_db)):
    banners = db.query(Banner).filter(Banner.is_active == True).order_by(Banner.display_order.asc()).all()
    
    categories = db.query(Category).filter(
        Category.parent_id == None, 
        Category.is_active == True
    ).order_by(Category.display_order.asc()).limit(6).all()
    
    cat_responses = []
    for c in categories:
        subs = [CategorySummary.from_orm(s) for s in c.subcategories if s.is_active]
        cat_responses.append(CategoryResponse(
            id=c.id,
            name=c.name,
            slug=c.slug,
            description=c.description,
            image_url=c.image_url,
            parent_id=c.parent_id,
            is_active=c.is_active,
            display_order=c.display_order,
            created_at=c.created_at,
            updated_at=c.updated_at,
            subcategories=subs
        ))
        
    flash_products = db.query(Product).filter(
        Product.is_active == True,
        Product.is_flash_sale == True
    ).limit(6).all()
    
    new_arrivals = db.query(Product).filter(
        Product.is_active == True
    ).order_by(Product.created_at.desc()).limit(8).all()
    
    best_sellers = db.query(Product).filter(
        Product.is_active == True,
        Product.is_best_seller == True
    ).limit(8).all()
    
    return APIResponse(
        success=True,
        message="Homepage dynamic content retrieved",
        data=HomepageContent(
            banners=[BannerResponse.from_orm(b) for b in banners],
            featured_categories=cat_responses,
            flash_sale_products=[format_product_response(p) for p in flash_products],
            new_arrivals=[format_product_response(p) for p in new_arrivals],
            best_sellers=[format_product_response(p) for p in best_sellers]
        )
    )
