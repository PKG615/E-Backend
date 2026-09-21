from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.schemas.category import CategoryResponse
from app.schemas.product import ProductResponse

class BannerResponse(BaseModel):
    id: int
    title: str
    subtitle: Optional[str] = None
    image_url: str
    link_url: Optional[str] = None
    banner_type: str
    is_active: bool
    display_order: int

    class Config:
        from_attributes = True

class BannerCreate(BaseModel):
    title: str
    subtitle: Optional[str] = None
    image_url: str
    link_url: Optional[str] = None
    banner_type: str = "hero"
    is_active: bool = True
    display_order: int = 0

class DashboardMetrics(BaseModel):
    total_revenue: float
    total_orders: int
    total_products: int
    total_customers: int
    low_stock_products: int
    recent_orders: List[Dict[str, Any]]
    sales_trend: List[Dict[str, Any]]

# Comprehensive Admin Dashboard Overview Schemas
class SalesSummary(BaseModel):
    gross_sales: float
    discounts: float
    tax: float
    shipping: float
    net_order_value: float
    paid_amount: float
    pending_amount: float

class OrderStatusBreakdown(BaseModel):
    total: int
    pending: int
    confirmed: int
    processing: int
    shipped: int
    delivered: int
    cancelled: int
    returned: int

class CustomerMetricsSummary(BaseModel):
    total_customers: int
    active_customers: int
    new_customers_in_period: int
    customers_with_orders: int
    customers_without_orders: int

class ProductMetricsSummary(BaseModel):
    total_products: int
    active_products: int
    inactive_products: int
    low_stock_products: int
    out_of_stock_products: int
    total_inventory_units: int

class InventoryAlertItem(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    sku: str
    product_name: str
    variant_title: Optional[str] = None
    stock: int
    safety_stock: int
    status: str  # 'out_of_stock' | 'low_stock'

class PaymentMetricsSummary(BaseModel):
    total_payments: int
    paid_count: int
    pending_count: int
    failed_count: int
    refunded_count: int
    paid_amount: float
    pending_amount: float
    failed_amount: float
    refunded_amount: float

class ShippingMetricsSummary(BaseModel):
    total_shipments: int
    pending: int
    processing: int
    packed: int
    shipped: int
    in_transit: int
    out_for_delivery: int
    delivered: int
    failed_cancelled: int

class ReturnsMetricsSummary(BaseModel):
    total_returns: int
    pending_returns: int
    awaiting_inspection: int
    approved_for_refund: int
    rejected: int
    refund_processing: int
    refunded: int
    refund_failed: int
    replacement_processing: int
    replacement_shipped: int

class MarketingMetricsSummary(BaseModel):
    total_coupons: int
    active_coupons: int
    expiring_soon_coupons: int
    total_coupon_usages: int
    active_offers: int
    active_flash_sales: int

class ModerationMetricsSummary(BaseModel):
    pending_reviews: int
    approved_reviews: int
    rejected_reviews: int
    total_reviews: int
    pending_questions: int
    answered_questions: int
    total_questions: int
    open_support_tickets: int
    urgent_support_tickets: int
    waiting_customer_tickets: int
    resolved_tickets: int

class SalesChartPoint(BaseModel):
    label: str
    date: str
    sales: float
    orders: int
    average_order_value: float

class SalesChartData(BaseModel):
    period: str
    labels: List[str]
    sales: List[float]
    orders: List[int]
    points: List[SalesChartPoint]

class RecentOrderItem(BaseModel):
    id: int
    order_number: str
    customer_name: str
    customer_email: str
    total_amount: float
    status: str
    payment_status: str
    created_at: str

class TopProductItem(BaseModel):
    product_id: int
    product_name: str
    sku: str
    image_url: Optional[str] = None
    units_sold: int
    revenue: float
    order_count: int

class CategoryPerformanceItem(BaseModel):
    category_id: int
    category_name: str
    product_count: int
    units_sold: int
    revenue: float

class OperationalAlert(BaseModel):
    id: str
    type: str  # 'warning' | 'danger' | 'info' | 'success'
    category: str
    title: str
    message: str
    count: int
    action_label: str
    action_tab: str

class DashboardOverviewResponse(BaseModel):
    period: str
    sales: SalesSummary
    orders: OrderStatusBreakdown
    customers: CustomerMetricsSummary
    products: ProductMetricsSummary
    inventory_alerts: List[InventoryAlertItem]
    payments: PaymentMetricsSummary
    shipments: ShippingMetricsSummary
    returns: ReturnsMetricsSummary
    marketing: MarketingMetricsSummary
    moderation: ModerationMetricsSummary
    chart: SalesChartData
    recent_orders: List[RecentOrderItem]
    top_products: List[TopProductItem]
    category_performance: List[CategoryPerformanceItem]
    alerts: List[OperationalAlert]

class HomepageContent(BaseModel):
    banners: List[BannerResponse]
    featured_categories: List[CategoryResponse]
    flash_sale_products: List[ProductResponse]
    new_arrivals: List[ProductResponse]
    best_sellers: List[ProductResponse]
