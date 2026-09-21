from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class HomepageSEO(BaseModel):
    title: str = "Enterprise Electronic Systems & Official Hardware Catalog"
    meta_description: str = "Browse verified flagship electronics, workstations, audio equipment, and accessories backed by authorized warranties and live warehouse inventory."
    og_title: Optional[str] = "Next-Gen Enterprise Electronics & High-Performance Hardware"
    og_description: Optional[str] = "Shop authorized electronics with guaranteed manufacturer authenticity and live inventory."

class HomepageSectionItemBase(BaseModel):
    item_type: str # product, category, brand, banner, faq, trust_item, custom
    item_id: Optional[int] = None
    custom_title: Optional[str] = None
    custom_content: Optional[str] = None
    custom_icon: Optional[str] = None
    custom_url: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True

class HomepageSectionItemCreate(HomepageSectionItemBase):
    pass

class HomepageSectionItemUpdate(BaseModel):
    item_type: Optional[str] = None
    item_id: Optional[int] = None
    custom_title: Optional[str] = None
    custom_content: Optional[str] = None
    custom_icon: Optional[str] = None
    custom_url: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None

class HomepageSectionItemResponse(HomepageSectionItemBase):
    id: int
    section_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    details: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class HomepageSectionBase(BaseModel):
    section_key: str
    section_type: str
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    configuration: Optional[Dict[str, Any]] = None

class HomepageSectionCreate(HomepageSectionBase):
    item_ids: Optional[List[int]] = None
    items_data: Optional[List[HomepageSectionItemCreate]] = None

class HomepageSectionUpdate(BaseModel):
    section_key: Optional[str] = None
    section_type: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    configuration: Optional[Dict[str, Any]] = None
    item_ids: Optional[List[int]] = None
    items_data: Optional[List[HomepageSectionItemCreate]] = None

class HomepageSectionResponse(HomepageSectionBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    items: List[HomepageSectionItemResponse] = []

    class Config:
        from_attributes = True

class PublicHomepageSection(BaseModel):
    id: int
    section_key: str
    section_type: str
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    sort_order: int
    configuration: Optional[Dict[str, Any]] = None
    data: Dict[str, Any]

class PublicHomepageResponse(BaseModel):
    seo: HomepageSEO
    sections: List[PublicHomepageSection]

class BannerBase(BaseModel):
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    image_url: str
    mobile_image_url: Optional[str] = None
    alt_text: Optional[str] = None
    link_type: Optional[str] = "custom" # product, category, brand, collection, shop, custom
    link_target: Optional[str] = None
    link_url: Optional[str] = None
    cta_label: Optional[str] = "Explore Now"
    cta_url: Optional[str] = None
    banner_type: str = "hero" # hero, promo, flash_sale, strip
    is_active: bool = True
    display_order: int = 0
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

class BannerCreate(BannerBase):
    pass

class BannerUpdate(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    mobile_image_url: Optional[str] = None
    alt_text: Optional[str] = None
    link_type: Optional[str] = None
    link_target: Optional[str] = None
    link_url: Optional[str] = None
    cta_label: Optional[str] = None
    cta_url: Optional[str] = None
    banner_type: Optional[str] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

class BannerResponse(BannerBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Collections schemas
class CollectionProductItem(BaseModel):
    product_id: int
    sort_order: int = 0
    name: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    stock: Optional[int] = None

class CollectionBase(BaseModel):
    title: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None

class CollectionCreate(CollectionBase):
    product_ids: Optional[List[int]] = None

class CollectionUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    product_ids: Optional[List[int]] = None

class CollectionResponse(CollectionBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    products_count: int = 0
    products: List[Any] = []

    class Config:
        from_attributes = True

class CollectionDetailResponse(CollectionBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    products_count: int = 0
    products: List[Any] = []

    class Config:
        from_attributes = True

class ReorderItem(BaseModel):
    id: int
    sort_order: int

class ReorderRequest(BaseModel):
    items: List[ReorderItem]

class StatusToggleRequest(BaseModel):
    is_active: bool

class NewsletterSubscriptionCreate(BaseModel):
    email: str

class NewsletterSubscriptionResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
