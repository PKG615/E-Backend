from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, categories, brands, products, content, home, me, cart, addresses, checkout,
    orders, admin_orders, admin_shipments, customer_returns, admin_returns, reviews,
    account, admin_support, admin_customers, admin_promotions, admin_search, collections
)
from app.api.v1.endpoints.admin import dashboard as admin_dashboard
from app.api.v1.endpoints.admin import categories as admin_categories
from app.api.v1.endpoints.admin import brands as admin_brands
from app.api.v1.endpoints.admin import products as admin_products
from app.api.v1.endpoints.admin import banners as admin_banners
from app.api.v1.endpoints.admin import attributes as admin_attributes
from app.api.v1.endpoints.admin import inventory as admin_inventory
from app.api.v1.endpoints.admin import homepage as admin_homepage
from app.api.v1.endpoints.admin import collections as admin_collections
from app.api.v1.endpoints.admin import reviews as admin_reviews
from app.api.v1.endpoints.admin import analytics as admin_analytics

api_router = APIRouter()

# Customer Public & User Endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(home.router, prefix="/home", tags=["Customer Homepage"])
api_router.include_router(home.router, prefix="/homepage", tags=["Customer Homepage Alias"])
api_router.include_router(home.router, prefix="/newsletter", tags=["Newsletter"])
api_router.include_router(collections.router, prefix="/collections", tags=["Customer Collections"])
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])
api_router.include_router(brands.router, prefix="/brands", tags=["Brands"])
api_router.include_router(products.router, prefix="/products", tags=["Products"])
api_router.include_router(content.router, prefix="/content", tags=["Content & CMS"])
api_router.include_router(me.router, prefix="/me", tags=["Customer Wishlist & Compare"])
api_router.include_router(cart.router, prefix="/me/cart", tags=["Customer Cart"])
api_router.include_router(addresses.router, prefix="/me/addresses", tags=["Customer Addresses"])
api_router.include_router(checkout.router, prefix="/me/checkout", tags=["Customer Checkout"])
api_router.include_router(orders.router, prefix="/me/orders", tags=["Customer Orders"])
api_router.include_router(customer_returns.router, prefix="/me/returns", tags=["Customer Returns"])
api_router.include_router(reviews.router, tags=["Customer Reviews & Q&A"])
api_router.include_router(account.router, prefix="/me", tags=["Customer Account & Profile & Notifications & Support"])

# Admin Control Endpoints
api_router.include_router(admin_dashboard.router, prefix="/admin/dashboard", tags=["Admin Dashboard"])
api_router.include_router(admin_orders.router, prefix="/admin/orders", tags=["Admin Orders"])
api_router.include_router(admin_shipments.router, prefix="/admin/shipments", tags=["Admin Shipments"])
api_router.include_router(admin_returns.router, prefix="/admin/returns", tags=["Admin Returns"])
api_router.include_router(admin_returns.refunds_router, prefix="/admin/refunds", tags=["Admin Refunds"])
api_router.include_router(admin_returns.replacements_router, prefix="/admin/replacements", tags=["Admin Replacements"])
api_router.include_router(admin_support.router, prefix="/admin/support", tags=["Admin Support"])
api_router.include_router(admin_categories.router, prefix="/admin/categories", tags=["Admin Categories"])
api_router.include_router(admin_brands.router, prefix="/admin/brands", tags=["Admin Brands"])
api_router.include_router(admin_products.router, prefix="/admin/products", tags=["Admin Products"])
api_router.include_router(admin_attributes.router, prefix="/admin/attributes", tags=["Admin Attributes"])
api_router.include_router(admin_banners.router, prefix="/admin/banners", tags=["Admin Banners"])
api_router.include_router(admin_inventory.router, prefix="/admin/inventory", tags=["Admin Inventory"])
api_router.include_router(admin_homepage.router, prefix="/admin/homepage", tags=["Admin Homepage CMS"])
api_router.include_router(admin_collections.router, prefix="/admin/collections", tags=["Admin Collections"])
api_router.include_router(admin_reviews.router, prefix="/admin/reviews", tags=["Admin Reviews"])
api_router.include_router(admin_reviews.questions_router, prefix="/admin/questions", tags=["Admin Product Q&A"])
api_router.include_router(admin_customers.router, prefix="/admin/customers", tags=["Admin Customers"])
api_router.include_router(admin_promotions.router, prefix="/admin/promotions", tags=["Admin Marketing & Promotions"])
api_router.include_router(admin_search.router, prefix="/admin/search", tags=["Admin Global Search"])
api_router.include_router(admin_analytics.router, prefix="/admin/analytics", tags=["Admin Analytics & Reports"])

