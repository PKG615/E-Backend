from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_admin, require_permission
from app.models.user import User
from app.schemas.common import APIResponse
from app.services.analytics_service import AnalyticsService
from app.schemas.analytics import (
    AnalyticsOverviewData,
    AnalyticsSalesResponse,
    AnalyticsOrdersResponse,
    AnalyticsCustomersResponse,
    AnalyticsProductsResponse,
    AnalyticsCategoriesResponse,
    AnalyticsBrandsResponse,
    AnalyticsInventoryResponse,
    AnalyticsPaymentsResponse,
    AnalyticsShippingResponse,
    AnalyticsReturnsResponse,
    AnalyticsPromotionsResponse,
    AnalyticsReviewsResponse,
    AnalyticsSupportResponse,
)

router = APIRouter()


@router.get("/overview", response_model=APIResponse[AnalyticsOverviewData])
def get_analytics_overview(
    period: Optional[str] = Query("30days", description="today, yesterday, 7days, 30days, 90days, this_month, last_month, this_year, custom"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD for custom range"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD for custom range"),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Comprehensive aggregated analytics overview for admin dashboard & executive reporting.
    """
    data = AnalyticsService.get_overview_analytics(db, period=period, start_date=start_date, end_date=end_date)
    return APIResponse(success=True, data=data, message="Analytics overview retrieved successfully")


@router.get("/sales", response_model=APIResponse[AnalyticsSalesResponse])
def get_sales_analytics(
    period: Optional[str] = Query("30days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Sales analytics: gross sales, net sales, discounts, tax, shipping revenue, refunds, and time series.
    """
    data = AnalyticsService.get_sales_analytics(db, period=period, start_date=start_date, end_date=end_date)
    return APIResponse(success=True, data=data, message="Sales analytics retrieved successfully")


@router.get("/orders", response_model=APIResponse[AnalyticsOrdersResponse])
def get_orders_analytics(
    period: Optional[str] = Query("30days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Orders analytics: lifecycle breakdown, payment status breakdown, average order value, trend.
    """
    data = AnalyticsService.get_orders_analytics(db, period=period, start_date=start_date, end_date=end_date)
    return APIResponse(success=True, data=data, message="Orders analytics retrieved successfully")


@router.get("/customers", response_model=APIResponse[AnalyticsCustomersResponse])
def get_customers_analytics(
    period: Optional[str] = Query("30days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Customer analytics: total, active, new in period, repeat customers, and top customers by spend.
    """
    data = AnalyticsService.get_customers_analytics(db, period=period, start_date=start_date, end_date=end_date, limit=limit)
    return APIResponse(success=True, data=data, message="Customer analytics retrieved successfully")


@router.get("/products", response_model=APIResponse[AnalyticsProductsResponse])
def get_products_analytics(
    period: Optional[str] = Query("30days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Product analytics: catalog status, stock health, products with/without sales, top selling products.
    """
    data = AnalyticsService.get_products_analytics(db, period=period, start_date=start_date, end_date=end_date, limit=limit)
    return APIResponse(success=True, data=data, message="Product analytics retrieved successfully")


@router.get("/categories", response_model=APIResponse[AnalyticsCategoriesResponse])
def get_categories_analytics(
    period: Optional[str] = Query("30days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Category performance analytics: units sold, gross/net sales, order counts per category.
    """
    data = AnalyticsService.get_categories_analytics(db, period=period, start_date=start_date, end_date=end_date)
    return APIResponse(success=True, data=data, message="Category analytics retrieved successfully")


@router.get("/brands", response_model=APIResponse[AnalyticsBrandsResponse])
def get_brands_analytics(
    period: Optional[str] = Query("30days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Brand performance analytics: units sold, gross/net sales, order counts per brand.
    """
    data = AnalyticsService.get_brands_analytics(db, period=period, start_date=start_date, end_date=end_date)
    return APIResponse(success=True, data=data, message="Brand analytics retrieved successfully")


@router.get("/inventory", response_model=APIResponse[AnalyticsInventoryResponse])
def get_inventory_analytics(
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Authoritative inventory analytics: on-hand, reserved, available, low-stock alerts, valuation.
    """
    data = AnalyticsService.get_inventory_analytics(db)
    return APIResponse(success=True, data=data, message="Inventory analytics retrieved successfully")


@router.get("/payments", response_model=APIResponse[AnalyticsPaymentsResponse])
def get_payments_analytics(
    period: Optional[str] = Query("30days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Payment analytics: status breakdown, volume, payment method performance.
    """
    data = AnalyticsService.get_payments_analytics(db, period=period, start_date=start_date, end_date=end_date)
    return APIResponse(success=True, data=data, message="Payment analytics retrieved successfully")


@router.get("/shipping", response_model=APIResponse[AnalyticsShippingResponse])
def get_shipping_analytics(
    period: Optional[str] = Query("30days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Shipping analytics: shipment statuses, carrier volume, average delivery duration.
    """
    data = AnalyticsService.get_shipping_analytics(db, period=period, start_date=start_date, end_date=end_date)
    return APIResponse(success=True, data=data, message="Shipping analytics retrieved successfully")


@router.get("/returns", response_model=APIResponse[AnalyticsReturnsResponse])
def get_returns_analytics(
    period: Optional[str] = Query("30days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Returns, refunds & replacement analytics.
    """
    data = AnalyticsService.get_returns_analytics(db, period=period, start_date=start_date, end_date=end_date)
    return APIResponse(success=True, data=data, message="Returns analytics retrieved successfully")


@router.get("/promotions", response_model=APIResponse[AnalyticsPromotionsResponse])
def get_promotions_analytics(
    period: Optional[str] = Query("30days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Promotions analytics: coupon performance, offer discounts, flash sale throughput.
    """
    data = AnalyticsService.get_promotions_analytics(db, period=period, start_date=start_date, end_date=end_date)
    return APIResponse(success=True, data=data, message="Promotions analytics retrieved successfully")


@router.get("/reviews", response_model=APIResponse[AnalyticsReviewsResponse])
def get_reviews_analytics(
    period: Optional[str] = Query("30days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Customer sentiment analytics: review ratings, moderation pipeline, Q&A status.
    """
    data = AnalyticsService.get_reviews_analytics(db, period=period, start_date=start_date, end_date=end_date)
    return APIResponse(success=True, data=data, message="Reviews analytics retrieved successfully")


@router.get("/support", response_model=APIResponse[AnalyticsSupportResponse])
def get_support_analytics(
    period: Optional[str] = Query("30days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Support operations analytics: ticket queue, priority, category volume.
    """
    data = AnalyticsService.get_support_analytics(db, period=period, start_date=start_date, end_date=end_date)
    return APIResponse(success=True, data=data, message="Support analytics retrieved successfully")


@router.get("/export")
def export_analytics_csv(
    report_type: str = Query("sales", description="sales, orders, products, customers, inventory, returns, categories, brands, coupons"),
    period: Optional[str] = Query("30days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Exports genuine database reports to CSV format.
    """
    csv_content, filename = AnalyticsService.export_csv_report(
        db,
        report_type=report_type,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )
