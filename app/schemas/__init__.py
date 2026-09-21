from app.schemas.common import APIResponse, PaginatedData
from app.schemas.user import UserRegister, UserLogin, TokenResponse, UserResponse
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse, BrandCreate, BrandUpdate, BrandResponse
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse, ProductVariantSchema, ProductImageSchema
from app.schemas.dashboard import DashboardMetrics, HomepageContent, BannerResponse, BannerCreate

__all__ = [
    "APIResponse",
    "PaginatedData",
    "UserRegister",
    "UserLogin",
    "TokenResponse",
    "UserResponse",
    "CategoryCreate",
    "CategoryUpdate",
    "CategoryResponse",
    "BrandCreate",
    "BrandUpdate",
    "BrandResponse",
    "ProductCreate",
    "ProductUpdate",
    "ProductResponse",
    "ProductVariantSchema",
    "ProductImageSchema",
    "DashboardMetrics",
    "HomepageContent",
    "BannerResponse",
    "BannerCreate"
]
