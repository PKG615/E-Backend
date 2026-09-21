from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class DateRangeInfo(BaseModel):
    period: str
    start_date: str
    end_date: str
    interval: str  # 'hourly', 'daily', 'weekly', 'monthly'

class SalesTimeSeriesPoint(BaseModel):
    date: str
    label: str
    orders_count: int
    gross_sales: float
    discounts: float
    tax: float
    shipping: float
    refunds: float
    net_sales: float
    average_order_value: float

class AnalyticsSalesResponse(BaseModel):
    date_range: DateRangeInfo
    gross_sales: float
    discounts: float
    tax: float
    shipping_revenue: float
    refunds: float
    net_sales: float
    average_order_value: float
    total_orders: int
    paid_orders_count: int
    cancelled_orders_count: int
    time_series: List[SalesTimeSeriesPoint]

class OrderStatusCount(BaseModel):
    status: str
    count: int
    percentage: float

class PaymentStatusCount(BaseModel):
    status: str
    count: int
    total_amount: float

class AnalyticsOrdersResponse(BaseModel):
    date_range: DateRangeInfo
    total_orders: int
    paid_orders: int
    pending_orders: int
    cancelled_orders: int
    returned_orders: int
    average_order_value: float
    status_distribution: List[OrderStatusCount]
    payment_status_distribution: List[PaymentStatusCount]
    orders_trend: List[SalesTimeSeriesPoint]

class TopCustomerItem(BaseModel):
    user_id: int
    name: str
    email: str
    phone: Optional[str] = None
    total_orders: int
    total_spend: float
    first_order_date: Optional[str] = None
    last_order_date: Optional[str] = None

class AnalyticsCustomersResponse(BaseModel):
    date_range: DateRangeInfo
    total_customers: int
    new_customers_in_period: int
    active_customers: int
    customers_with_orders: int
    customers_without_orders: int
    returning_customers: int
    average_customer_spend: float
    top_customers: List[TopCustomerItem]

class TopProductAnalyticsItem(BaseModel):
    product_id: int
    name: str
    sku: str
    image_url: Optional[str] = None
    category_name: Optional[str] = None
    brand_name: Optional[str] = None
    units_sold: int
    order_count: int
    gross_revenue: float
    discount_amount: float
    net_revenue: float
    current_stock: int

class AnalyticsProductsResponse(BaseModel):
    date_range: DateRangeInfo
    total_products: int
    active_products: int
    inactive_products: int
    out_of_stock_products: int
    low_stock_products: int
    products_with_sales: int
    products_without_sales: int
    top_products: List[TopProductAnalyticsItem]

class CategoryAnalyticsItem(BaseModel):
    category_id: int
    category_name: str
    slug: str
    parent_id: Optional[int] = None
    product_count: int
    units_sold: int
    order_count: int
    gross_sales: float
    discounts: float
    net_sales: float

class AnalyticsCategoriesResponse(BaseModel):
    date_range: DateRangeInfo
    categories: List[CategoryAnalyticsItem]

class BrandAnalyticsItem(BaseModel):
    brand_id: int
    brand_name: str
    slug: str
    logo_url: Optional[str] = None
    product_count: int
    units_sold: int
    order_count: int
    gross_sales: float
    discounts: float
    net_sales: float

class AnalyticsBrandsResponse(BaseModel):
    date_range: DateRangeInfo
    brands: List[BrandAnalyticsItem]

class LowStockInventoryItem(BaseModel):
    inventory_id: int
    product_id: int
    variant_id: Optional[int] = None
    product_name: str
    variant_title: Optional[str] = None
    sku: str
    on_hand_quantity: int
    reserved_quantity: int
    available_quantity: int
    low_stock_threshold: int
    status: str

class AnalyticsInventoryResponse(BaseModel):
    total_inventory_records: int
    total_on_hand_units: int
    total_reserved_units: int
    total_available_units: int
    in_stock_count: int
    low_stock_count: int
    out_of_stock_count: int
    estimated_inventory_value: float
    low_stock_items: List[LowStockInventoryItem]

class PaymentMethodMetric(BaseModel):
    method: str
    total_transactions: int
    successful_transactions: int
    failed_transactions: int
    success_rate: float
    total_volume: float

class AnalyticsPaymentsResponse(BaseModel):
    date_range: DateRangeInfo
    total_payments: int
    paid_count: int
    pending_count: int
    failed_count: int
    refunded_count: int
    paid_amount: float
    pending_amount: float
    failed_amount: float
    refunded_amount: float
    methods: List[PaymentMethodMetric]

class CarrierMetric(BaseModel):
    carrier: str
    shipments_count: int
    delivered_count: int
    in_transit_count: int

class AnalyticsShippingResponse(BaseModel):
    date_range: DateRangeInfo
    total_shipments: int
    status_breakdown: Dict[str, int]
    carrier_breakdown: List[CarrierMetric]
    delivered_count: int
    average_delivery_duration_hours: Optional[float] = None
    on_time_delivery_rate: Optional[float] = None

class ReturnReasonCount(BaseModel):
    reason: str
    count: int

class AnalyticsReturnsResponse(BaseModel):
    date_range: DateRangeInfo
    total_returns: int
    status_breakdown: Dict[str, int]
    resolution_breakdown: Dict[str, int]
    reason_breakdown: List[ReturnReasonCount]
    total_refunds_count: int
    completed_refunds_count: int
    total_refunded_amount: float
    pending_refund_amount: float
    total_replacements_count: int
    replacement_status_breakdown: Dict[str, int]

class CouponPerformanceItem(BaseModel):
    coupon_id: int
    code: str
    name: str
    discount_type: str
    discount_value: float
    used_count: int
    usage_limit: Optional[int] = None
    total_discount_given: float
    total_revenue_generated: float
    is_active: bool

class FlashSaleAnalyticsItem(BaseModel):
    flash_sale_id: int
    name: str
    starts_at: str
    ends_at: str
    is_active: bool
    total_items_count: int
    total_units_sold: int
    discount_amount_given: float

class AnalyticsPromotionsResponse(BaseModel):
    date_range: DateRangeInfo
    total_coupons: int
    active_coupons: int
    total_coupon_usages_in_period: int
    total_coupon_discount_given: float
    coupon_attributed_revenue: float
    coupon_performance: List[CouponPerformanceItem]
    total_offers: int
    active_offers: int
    orders_with_offers: int
    total_offer_discount_given: float
    total_flash_sales: int
    active_flash_sales: int
    flash_sales_list: List[FlashSaleAnalyticsItem]

class RatingCount(BaseModel):
    rating: int
    count: int
    percentage: float

class AnalyticsReviewsResponse(BaseModel):
    date_range: DateRangeInfo
    total_reviews: int
    approved_reviews: int
    pending_reviews: int
    rejected_reviews: int
    average_rating: float
    verified_purchase_count: int
    rating_distribution: List[RatingCount]
    total_questions: int
    answered_questions: int
    pending_questions: int
    rejected_questions: int

class SupportTicketCategoryCount(BaseModel):
    category: str
    count: int

class SupportTicketPriorityCount(BaseModel):
    priority: str
    count: int

class AnalyticsSupportResponse(BaseModel):
    date_range: DateRangeInfo
    total_tickets: int
    status_breakdown: Dict[str, int]
    priority_breakdown: List[SupportTicketPriorityCount]
    category_breakdown: List[SupportTicketCategoryCount]

class AnalyticsOverviewData(BaseModel):
    date_range: DateRangeInfo
    kpis: Dict[str, Any]
    sales: AnalyticsSalesResponse
    orders: AnalyticsOrdersResponse
    inventory: AnalyticsInventoryResponse
    customers_summary: Dict[str, Any]
    products_summary: Dict[str, Any]
    payments_summary: Dict[str, Any]
    shipping_summary: Dict[str, Any]
    returns_summary: Dict[str, Any]
    promotions_summary: Dict[str, Any]
    moderation_summary: Dict[str, Any]
