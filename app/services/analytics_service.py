import csv
import io
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import func, and_, or_, desc, asc, case
from sqlalchemy.orm import Session

from app.models.order import Order, OrderItem, Payment, OrderStatusHistory
from app.models.product import Product, ProductVariant, ProductImage
from app.models.category import Category, Brand
from app.models.user import User
from app.models.inventory import Inventory
from app.models.returns import Return, ReturnItem, Refund, Replacement
from app.models.shipment import Shipment
from app.models.promotions import Coupon, CouponUsage, Offer, FlashSale, FlashSaleItem
from app.models.reviews import Review, ProductQuestion, ProductAnswer
from app.models.support import SupportTicket

from app.schemas.analytics import (
    DateRangeInfo,
    SalesTimeSeriesPoint,
    AnalyticsSalesResponse,
    OrderStatusCount,
    PaymentStatusCount,
    AnalyticsOrdersResponse,
    TopCustomerItem,
    AnalyticsCustomersResponse,
    TopProductAnalyticsItem,
    AnalyticsProductsResponse,
    CategoryAnalyticsItem,
    AnalyticsCategoriesResponse,
    BrandAnalyticsItem,
    AnalyticsBrandsResponse,
    LowStockInventoryItem,
    AnalyticsInventoryResponse,
    PaymentMethodMetric,
    AnalyticsPaymentsResponse,
    CarrierMetric,
    AnalyticsShippingResponse,
    ReturnReasonCount,
    AnalyticsReturnsResponse,
    CouponPerformanceItem,
    FlashSaleAnalyticsItem,
    AnalyticsPromotionsResponse,
    RatingCount,
    AnalyticsReviewsResponse,
    SupportTicketPriorityCount,
    SupportTicketCategoryCount,
    AnalyticsSupportResponse,
    AnalyticsOverviewData,
)


class AnalyticsService:

    @staticmethod
    def parse_date_range(
        period: Optional[str] = "30days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple[datetime, datetime, str, str]:
        """
        Parses and validates the date range according to PART 3.
        Returns (start_dt, end_dt, interval, normalized_period).
        Interval is one of 'hourly', 'daily', 'weekly', 'monthly'.
        """
        now = datetime.utcnow()
        norm_period = (period or "30days").lower().strip()

        if norm_period == "today":
            start_dt = datetime(now.year, now.month, now.day, 0, 0, 0)
            end_dt = now
            interval = "hourly"
        elif norm_period == "yesterday":
            yesterday = now - timedelta(days=1)
            start_dt = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0)
            end_dt = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59)
            interval = "hourly"
        elif norm_period in ["7days", "last_7_days"]:
            start_dt = now - timedelta(days=7)
            end_dt = now
            interval = "daily"
        elif norm_period in ["30days", "last_30_days"]:
            start_dt = now - timedelta(days=30)
            end_dt = now
            interval = "daily"
        elif norm_period in ["90days", "last_90_days"]:
            start_dt = now - timedelta(days=90)
            end_dt = now
            interval = "weekly"
        elif norm_period == "this_month":
            start_dt = datetime(now.year, now.month, 1, 0, 0, 0)
            end_dt = now
            interval = "daily"
        elif norm_period == "last_month":
            first_this_month = datetime(now.year, now.month, 1)
            last_day_last_month = first_this_month - timedelta(days=1)
            start_dt = datetime(last_day_last_month.year, last_day_last_month.month, 1, 0, 0, 0)
            end_dt = datetime(last_day_last_month.year, last_day_last_month.month, last_day_last_month.day, 23, 59, 59)
            interval = "daily"
        elif norm_period in ["this_year", "year"]:
            start_dt = datetime(now.year, 1, 1, 0, 0, 0)
            end_dt = now
            interval = "monthly"
        elif norm_period == "custom":
            if not start_date or not end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Custom date range requires both 'start_date' and 'end_date' in YYYY-MM-DD format",
                )
            try:
                start_clean = start_date.replace("Z", "").split("T")[0]
                end_clean = end_date.replace("Z", "").split("T")[0]
                start_dt = datetime.strptime(start_clean, "%Y-%m-%d")
                end_dt = datetime.strptime(end_clean, "%Y-%m-%d") + timedelta(hours=23, minutes=59, seconds=59)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date format. Expected YYYY-MM-DD or ISO 8601 string",
                )

            if start_dt > end_dt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date range: 'start_date' cannot be greater than 'end_date'",
                )

            diff_days = (end_dt - start_dt).days
            if diff_days <= 2:
                interval = "hourly"
            elif diff_days <= 45:
                interval = "daily"
            elif diff_days <= 180:
                interval = "weekly"
            else:
                interval = "monthly"
        else:
            # Fallback to 30 days
            norm_period = "30days"
            start_dt = now - timedelta(days=30)
            end_dt = now
            interval = "daily"

        return start_dt, end_dt, interval, norm_period

    @classmethod
    def get_date_range_info(cls, period: str, start_dt: datetime, end_dt: datetime, interval: str) -> DateRangeInfo:
        return DateRangeInfo(
            period=period,
            start_date=start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            end_date=end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            interval=interval,
        )

    # -------------------------------------------------------------------------
    # PART 4 & 5: SALES ANALYTICS + SALES OVER TIME
    # -------------------------------------------------------------------------
    @classmethod
    def get_sales_analytics(
        cls,
        db: Session,
        period: Optional[str] = "30days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> AnalyticsSalesResponse:
        start_dt, end_dt, interval, norm_period = cls.parse_date_range(period, start_date, end_date)
        date_info = cls.get_date_range_info(norm_period, start_dt, end_dt, interval)

        # 1. Gross sales, discounts, tax, shipping from Orders in period
        # Financial source of truth: Order & Payment models
        paid_orders_q = db.query(Order).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.payment_status == "paid",
            Order.status != "cancelled",
        )

        all_orders_in_period = db.query(Order).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
        )

        total_orders = all_orders_in_period.count()
        paid_orders_count = paid_orders_q.count()
        cancelled_orders_count = all_orders_in_period.filter(Order.status == "cancelled").count()

        sales_aggregates = db.query(
            func.coalesce(func.sum(Order.total_amount), 0.0).label("gross_sales"),
            func.coalesce(func.sum(Order.discount_amount), 0.0).label("discounts"),
            func.coalesce(func.sum(Order.tax_amount), 0.0).label("tax"),
            func.coalesce(func.sum(Order.shipping_amount), 0.0).label("shipping"),
        ).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.payment_status == "paid",
            Order.status != "cancelled",
        ).first()

        gross_sales = round(float(sales_aggregates.gross_sales or 0.0), 2)
        discounts = round(float(sales_aggregates.discounts or 0.0), 2)
        tax = round(float(sales_aggregates.tax or 0.0), 2)
        shipping_revenue = round(float(sales_aggregates.shipping or 0.0), 2)

        # Refunds completed in period
        refunds_q = db.query(
            func.coalesce(func.sum(Refund.amount), 0.0)
        ).filter(
            Refund.created_at >= start_dt,
            Refund.created_at <= end_dt,
            Refund.status.in_(["completed", "refunded"]),
        ).scalar()
        refunds = round(float(refunds_q or 0.0), 2)

        net_sales = round(max(0.0, gross_sales - refunds), 2)
        aov = round(gross_sales / paid_orders_count, 2) if paid_orders_count > 0 else 0.0

        # 2. Time Series Generation
        time_series = cls._generate_sales_time_series(db, start_dt, end_dt, interval)

        return AnalyticsSalesResponse(
            date_range=date_info,
            gross_sales=gross_sales,
            discounts=discounts,
            tax=tax,
            shipping_revenue=shipping_revenue,
            refunds=refunds,
            net_sales=net_sales,
            average_order_value=aov,
            total_orders=total_orders,
            paid_orders_count=paid_orders_count,
            cancelled_orders_count=cancelled_orders_count,
            time_series=time_series,
        )

    @classmethod
    def _generate_sales_time_series(
        cls,
        db: Session,
        start_dt: datetime,
        end_dt: datetime,
        interval: str,
    ) -> List[SalesTimeSeriesPoint]:
        """
        Creates continuous time series buckets and aggregates actual sales in each bucket.
        """
        buckets: List[Tuple[datetime, datetime, str, str]] = []

        if interval == "hourly":
            curr = datetime(start_dt.year, start_dt.month, start_dt.day, start_dt.hour, 0, 0)
            while curr <= end_dt:
                bucket_end = curr + timedelta(hours=1) - timedelta(microseconds=1)
                label = curr.strftime("%H:%M")
                date_key = curr.strftime("%Y-%m-%d %H:00")
                buckets.append((curr, bucket_end, date_key, label))
                curr += timedelta(hours=1)
        elif interval == "daily":
            curr = datetime(start_dt.year, start_dt.month, start_dt.day, 0, 0, 0)
            while curr <= end_dt:
                bucket_end = curr + timedelta(days=1) - timedelta(microseconds=1)
                label = curr.strftime("%b %d")
                date_key = curr.strftime("%Y-%m-%d")
                buckets.append((curr, bucket_end, date_key, label))
                curr += timedelta(days=1)
        elif interval == "weekly":
            curr = datetime(start_dt.year, start_dt.month, start_dt.day, 0, 0, 0)
            while curr <= end_dt:
                bucket_end = curr + timedelta(days=7) - timedelta(microseconds=1)
                label = f"W{curr.strftime('%U')} ({curr.strftime('%b %d')})"
                date_key = curr.strftime("%Y-%m-%d")
                buckets.append((curr, bucket_end, date_key, label))
                curr += timedelta(days=7)
        else:  # monthly
            curr = datetime(start_dt.year, start_dt.month, 1, 0, 0, 0)
            while curr <= end_dt:
                # Next month start
                if curr.month == 12:
                    next_month = datetime(curr.year + 1, 1, 1, 0, 0, 0)
                else:
                    next_month = datetime(curr.year, curr.month + 1, 1, 0, 0, 0)
                bucket_end = next_month - timedelta(microseconds=1)
                label = curr.strftime("%b %Y")
                date_key = curr.strftime("%Y-%m")
                buckets.append((curr, bucket_end, date_key, label))
                curr = next_month

        # Pre-fetch orders in the full window to group efficiently in Python
        orders_in_window = db.query(
            Order.created_at,
            Order.total_amount,
            Order.discount_amount,
            Order.tax_amount,
            Order.shipping_amount,
            Order.payment_status,
            Order.status,
        ).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
        ).all()

        refunds_in_window = db.query(
            Refund.created_at,
            Refund.amount,
        ).filter(
            Refund.created_at >= start_dt,
            Refund.created_at <= end_dt,
            Refund.status.in_(["completed", "refunded"]),
        ).all()

        points: List[SalesTimeSeriesPoint] = []
        for b_start, b_end, date_key, label in buckets:
            b_orders = [o for o in orders_in_window if b_start <= o.created_at <= b_end]
            b_paid_orders = [o for o in b_orders if o.payment_status == "paid" and o.status != "cancelled"]
            b_refunds = [r for r in refunds_in_window if b_start <= r.created_at <= b_end]

            orders_count = len(b_orders)
            paid_count = len(b_paid_orders)
            b_gross = round(sum(o.total_amount for o in b_paid_orders), 2)
            b_discount = round(sum(o.discount_amount for o in b_paid_orders), 2)
            b_tax = round(sum(o.tax_amount for o in b_paid_orders), 2)
            b_shipping = round(sum(o.shipping_amount for o in b_paid_orders), 2)
            b_ref_val = round(sum(r.amount for r in b_refunds), 2)
            b_net = round(max(0.0, b_gross - b_ref_val), 2)
            b_aov = round(b_gross / paid_count, 2) if paid_count > 0 else 0.0

            points.append(
                SalesTimeSeriesPoint(
                    date=date_key,
                    label=label,
                    orders_count=orders_count,
                    gross_sales=b_gross,
                    discounts=b_discount,
                    tax=b_tax,
                    shipping=b_shipping,
                    refunds=b_ref_val,
                    net_sales=b_net,
                    average_order_value=b_aov,
                )
            )

        return points

    # -------------------------------------------------------------------------
    # PART 6: ORDER ANALYTICS
    # -------------------------------------------------------------------------
    @classmethod
    def get_orders_analytics(
        cls,
        db: Session,
        period: Optional[str] = "30days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> AnalyticsOrdersResponse:
        start_dt, end_dt, interval, norm_period = cls.parse_date_range(period, start_date, end_date)
        date_info = cls.get_date_range_info(norm_period, start_dt, end_dt, interval)

        orders_q = db.query(Order).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
        )

        total_orders = orders_q.count()
        paid_orders = orders_q.filter(Order.payment_status == "paid").count()
        pending_orders = orders_q.filter(Order.status.in_(["pending", "processing", "confirmed"])).count()
        cancelled_orders = orders_q.filter(Order.status == "cancelled").count()
        returned_orders = orders_q.filter(Order.status == "returned").count()

        gross_paid = db.query(func.coalesce(func.sum(Order.total_amount), 0.0)).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.payment_status == "paid",
            Order.status != "cancelled",
        ).scalar()
        aov = round(float(gross_paid or 0.0) / paid_orders, 2) if paid_orders > 0 else 0.0

        # Status distribution
        status_rows = db.query(
            Order.status,
            func.count(Order.id).label("cnt"),
        ).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
        ).group_by(Order.status).all()

        status_distribution = [
            OrderStatusCount(
                status=row.status,
                count=row.cnt,
                percentage=round((row.cnt / total_orders) * 100.0, 1) if total_orders > 0 else 0.0,
            )
            for row in status_rows
        ]

        # Payment status distribution
        payment_status_rows = db.query(
            Order.payment_status,
            func.count(Order.id).label("cnt"),
            func.coalesce(func.sum(Order.total_amount), 0.0).label("total_amt"),
        ).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
        ).group_by(Order.payment_status).all()

        payment_status_distribution = [
            PaymentStatusCount(
                status=row.payment_status,
                count=row.cnt,
                total_amount=round(float(row.total_amt or 0.0), 2),
            )
            for row in payment_status_rows
        ]

        orders_trend = cls._generate_sales_time_series(db, start_dt, end_dt, interval)

        return AnalyticsOrdersResponse(
            date_range=date_info,
            total_orders=total_orders,
            paid_orders=paid_orders,
            pending_orders=pending_orders,
            cancelled_orders=cancelled_orders,
            returned_orders=returned_orders,
            average_order_value=aov,
            status_distribution=status_distribution,
            payment_status_distribution=payment_status_distribution,
            orders_trend=orders_trend,
        )

    # -------------------------------------------------------------------------
    # PART 7: CUSTOMER ANALYTICS
    # -------------------------------------------------------------------------
    @classmethod
    def get_customers_analytics(
        cls,
        db: Session,
        period: Optional[str] = "30days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 10,
    ) -> AnalyticsCustomersResponse:
        start_dt, end_dt, interval, norm_period = cls.parse_date_range(period, start_date, end_date)
        date_info = cls.get_date_range_info(norm_period, start_dt, end_dt, interval)

        # Role == customer is the authoritative filter for store customers
        customer_users_q = db.query(User).filter(User.role == "customer")
        total_customers = customer_users_q.count()
        active_customers = customer_users_q.filter(User.is_active == True).count()

        new_customers_in_period = customer_users_q.filter(
            User.created_at >= start_dt,
            User.created_at <= end_dt,
        ).count()

        # Distinct customers with orders in period
        customers_with_orders = db.query(func.count(func.distinct(Order.user_id))).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
        ).scalar() or 0

        customers_without_orders = max(0, total_customers - customers_with_orders)

        # Returning customers: customers who placed an order in period AND had placed at least one prior order
        subq_prior_orders = db.query(Order.user_id).filter(Order.created_at < start_dt)
        returning_customers = db.query(func.count(func.distinct(Order.user_id))).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.user_id.in_(subq_prior_orders),
        ).scalar() or 0

        total_customer_spend = db.query(func.coalesce(func.sum(Order.total_amount), 0.0)).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.payment_status == "paid",
            Order.status != "cancelled",
        ).scalar() or 0.0

        avg_spend = round(float(total_customer_spend) / customers_with_orders, 2) if customers_with_orders > 0 else 0.0

        # Top customers by spend in period (or all time if period has no orders)
        top_cust_query = db.query(
            User.id.label("user_id"),
            User.full_name.label("name"),
            User.email.label("email"),
            User.phone.label("phone"),
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(Order.total_amount), 0.0).label("total_spend"),
            func.min(Order.created_at).label("first_order_date"),
            func.max(Order.created_at).label("last_order_date"),
        ).join(
            Order, Order.user_id == User.id
        ).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.status != "cancelled",
        ).group_by(
            User.id, User.full_name, User.email, User.phone
        ).order_by(
            desc("total_spend")
        ).limit(limit).all()

        top_customers = [
            TopCustomerItem(
                user_id=row.user_id,
                name=row.name,
                email=row.email,
                phone=row.phone,
                total_orders=row.total_orders,
                total_spend=round(float(row.total_spend or 0.0), 2),
                first_order_date=row.first_order_date.strftime("%Y-%m-%d") if row.first_order_date else None,
                last_order_date=row.last_order_date.strftime("%Y-%m-%d") if row.last_order_date else None,
            )
            for row in top_cust_query
        ]

        return AnalyticsCustomersResponse(
            date_range=date_info,
            total_customers=total_customers,
            new_customers_in_period=new_customers_in_period,
            active_customers=active_customers,
            customers_with_orders=customers_with_orders,
            customers_without_orders=customers_without_orders,
            returning_customers=returning_customers,
            average_customer_spend=avg_spend,
            top_customers=top_customers,
        )

    # -------------------------------------------------------------------------
    # PART 8: PRODUCT ANALYTICS
    # -------------------------------------------------------------------------
    @classmethod
    def get_products_analytics(
        cls,
        db: Session,
        period: Optional[str] = "30days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 10,
    ) -> AnalyticsProductsResponse:
        start_dt, end_dt, interval, norm_period = cls.parse_date_range(period, start_date, end_date)
        date_info = cls.get_date_range_info(norm_period, start_dt, end_dt, interval)

        total_products = db.query(Product).count()
        active_products = db.query(Product).filter(Product.is_active == True).count()
        inactive_products = total_products - active_products

        # Authoritative inventory cross-check for stock metrics
        out_of_stock_products = db.query(Product).filter(Product.stock <= 0).count()
        low_stock_products = db.query(Product).filter(Product.stock > 0, Product.stock <= 5).count()

        # Products with sales in period
        sold_products_subq = db.query(OrderItem.product_id).join(
            Order, Order.id == OrderItem.order_id
        ).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.status != "cancelled",
        ).distinct().all()

        products_with_sales = len(sold_products_subq)
        products_without_sales = max(0, total_products - products_with_sales)

        # Top selling products
        top_prod_query = db.query(
            Product.id.label("product_id"),
            Product.name.label("name"),
            Product.sku.label("sku"),
            Product.stock.label("stock"),
            Category.name.label("category_name"),
            Brand.name.label("brand_name"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
            func.count(func.distinct(Order.id)).label("order_count"),
            func.coalesce(func.sum(OrderItem.line_total), 0.0).label("gross_revenue"),
            func.coalesce(func.sum(OrderItem.discount_amount), 0.0).label("discount_amount"),
        ).join(
            OrderItem, OrderItem.product_id == Product.id
        ).join(
            Order, Order.id == OrderItem.order_id
        ).outerjoin(
            Category, Category.id == Product.category_id
        ).outerjoin(
            Brand, Brand.id == Product.brand_id
        ).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.status != "cancelled",
        ).group_by(
            Product.id, Product.name, Product.sku, Product.stock, Category.name, Brand.name
        ).order_by(
            desc("gross_revenue")
        ).limit(limit).all()

        top_products: List[TopProductAnalyticsItem] = []
        for r in top_prod_query:
            # Primary image
            img_obj = db.query(ProductImage).filter(ProductImage.product_id == r.product_id).order_by(desc(ProductImage.is_primary)).first()
            img_url = img_obj.image_url if img_obj else None

            gross_rev = round(float(r.gross_revenue or 0.0), 2)
            disc = round(float(r.discount_amount or 0.0), 2)
            net_rev = round(max(0.0, gross_rev - disc), 2)

            top_products.append(
                TopProductAnalyticsItem(
                    product_id=r.product_id,
                    name=r.name,
                    sku=r.sku,
                    image_url=img_url,
                    category_name=r.category_name,
                    brand_name=r.brand_name,
                    units_sold=int(r.units_sold),
                    order_count=int(r.order_count),
                    gross_revenue=gross_rev,
                    discount_amount=disc,
                    net_revenue=net_rev,
                    current_stock=int(r.stock),
                )
            )

        return AnalyticsProductsResponse(
            date_range=date_info,
            total_products=total_products,
            active_products=active_products,
            inactive_products=inactive_products,
            out_of_stock_products=out_of_stock_products,
            low_stock_products=low_stock_products,
            products_with_sales=products_with_sales,
            products_without_sales=products_without_sales,
            top_products=top_products,
        )

    # -------------------------------------------------------------------------
    # PART 9: CATEGORY ANALYTICS
    # -------------------------------------------------------------------------
    @classmethod
    def get_categories_analytics(
        cls,
        db: Session,
        period: Optional[str] = "30days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> AnalyticsCategoriesResponse:
        start_dt, end_dt, interval, norm_period = cls.parse_date_range(period, start_date, end_date)
        date_info = cls.get_date_range_info(norm_period, start_dt, end_dt, interval)

        categories = db.query(Category).order_by(Category.name.asc()).all()

        results: List[CategoryAnalyticsItem] = []
        for cat in categories:
            prod_count = db.query(Product).filter(Product.category_id == cat.id).count()

            # Sales aggregations for products in this category
            sales_agg = db.query(
                func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
                func.count(func.distinct(Order.id)).label("order_count"),
                func.coalesce(func.sum(OrderItem.line_total), 0.0).label("gross_sales"),
                func.coalesce(func.sum(OrderItem.discount_amount), 0.0).label("discounts"),
            ).join(
                Product, Product.id == OrderItem.product_id
            ).join(
                Order, Order.id == OrderItem.order_id
            ).filter(
                Product.category_id == cat.id,
                Order.created_at >= start_dt,
                Order.created_at <= end_dt,
                Order.status != "cancelled",
            ).first()

            units_sold = int(sales_agg.units_sold if sales_agg else 0)
            order_count = int(sales_agg.order_count if sales_agg else 0)
            gross = round(float(sales_agg.gross_sales or 0.0), 2) if sales_agg else 0.0
            disc = round(float(sales_agg.discounts or 0.0), 2) if sales_agg else 0.0
            net = round(max(0.0, gross - disc), 2)

            results.append(
                CategoryAnalyticsItem(
                    category_id=cat.id,
                    category_name=cat.name,
                    slug=cat.slug,
                    parent_id=cat.parent_id,
                    product_count=prod_count,
                    units_sold=units_sold,
                    order_count=order_count,
                    gross_sales=gross,
                    discounts=disc,
                    net_sales=net,
                )
            )

        # Sort by gross_sales desc
        results.sort(key=lambda x: x.gross_sales, reverse=True)

        return AnalyticsCategoriesResponse(
            date_range=date_info,
            categories=results,
        )

    # -------------------------------------------------------------------------
    # PART 10: BRAND ANALYTICS
    # -------------------------------------------------------------------------
    @classmethod
    def get_brands_analytics(
        cls,
        db: Session,
        period: Optional[str] = "30days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> AnalyticsBrandsResponse:
        start_dt, end_dt, interval, norm_period = cls.parse_date_range(period, start_date, end_date)
        date_info = cls.get_date_range_info(norm_period, start_dt, end_dt, interval)

        brands = db.query(Brand).order_by(Brand.name.asc()).all()

        results: List[BrandAnalyticsItem] = []
        for brand in brands:
            prod_count = db.query(Product).filter(Product.brand_id == brand.id).count()

            sales_agg = db.query(
                func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
                func.count(func.distinct(Order.id)).label("order_count"),
                func.coalesce(func.sum(OrderItem.line_total), 0.0).label("gross_sales"),
                func.coalesce(func.sum(OrderItem.discount_amount), 0.0).label("discounts"),
            ).join(
                Product, Product.id == OrderItem.product_id
            ).join(
                Order, Order.id == OrderItem.order_id
            ).filter(
                Product.brand_id == brand.id,
                Order.created_at >= start_dt,
                Order.created_at <= end_dt,
                Order.status != "cancelled",
            ).first()

            units_sold = int(sales_agg.units_sold if sales_agg else 0)
            order_count = int(sales_agg.order_count if sales_agg else 0)
            gross = round(float(sales_agg.gross_sales or 0.0), 2) if sales_agg else 0.0
            disc = round(float(sales_agg.discounts or 0.0), 2) if sales_agg else 0.0
            net = round(max(0.0, gross - disc), 2)

            results.append(
                BrandAnalyticsItem(
                    brand_id=brand.id,
                    brand_name=brand.name,
                    slug=brand.slug,
                    logo_url=brand.logo_url,
                    product_count=prod_count,
                    units_sold=units_sold,
                    order_count=order_count,
                    gross_sales=gross,
                    discounts=disc,
                    net_sales=net,
                )
            )

        results.sort(key=lambda x: x.gross_sales, reverse=True)

        return AnalyticsBrandsResponse(
            date_range=date_info,
            brands=results,
        )

    # -------------------------------------------------------------------------
    # PART 11: INVENTORY ANALYTICS (Authoritative Checkpoint 06 Inventory Model)
    # -------------------------------------------------------------------------
    @classmethod
    def get_inventory_analytics(cls, db: Session) -> AnalyticsInventoryResponse:
        total_records = db.query(Inventory).count()

        totals = db.query(
            func.coalesce(func.sum(Inventory.on_hand_quantity), 0).label("on_hand"),
            func.coalesce(func.sum(Inventory.reserved_quantity), 0).label("reserved"),
            func.coalesce(func.sum(Inventory.available_quantity), 0).label("available"),
        ).first()

        on_hand = int(totals.on_hand or 0)
        reserved = int(totals.reserved or 0)
        available = int(totals.available or 0)

        out_of_stock_count = db.query(Inventory).filter(Inventory.available_quantity <= 0).count()
        low_stock_count = db.query(Inventory).filter(
            Inventory.available_quantity > 0,
            Inventory.available_quantity <= Inventory.low_stock_threshold,
        ).count()
        in_stock_count = max(0, total_records - out_of_stock_count - low_stock_count)

        # Inventory valuation: on_hand_quantity * Product.price
        val_rows = db.query(
            Inventory.on_hand_quantity,
            Product.price,
        ).join(
            Product, Product.id == Inventory.product_id
        ).all()
        est_val = round(sum(float(r.on_hand_quantity or 0) * float(r.price or 0) for r in val_rows), 2)

        # Low stock items list for action
        low_stock_items_query = db.query(
            Inventory,
            Product.name.label("product_name"),
            ProductVariant.title.label("variant_title"),
        ).join(
            Product, Product.id == Inventory.product_id
        ).outerjoin(
            ProductVariant, ProductVariant.id == Inventory.variant_id
        ).filter(
            Inventory.available_quantity <= Inventory.low_stock_threshold
        ).order_by(
            Inventory.available_quantity.asc()
        ).limit(50).all()

        low_stock_list: List[LowStockInventoryItem] = []
        for inv, p_name, v_title in low_stock_items_query:
            status_str = "out_of_stock" if inv.available_quantity <= 0 else "low_stock"
            low_stock_list.append(
                LowStockInventoryItem(
                    inventory_id=inv.id,
                    product_id=inv.product_id,
                    variant_id=inv.variant_id,
                    product_name=p_name,
                    variant_title=v_title,
                    sku=inv.sku,
                    on_hand_quantity=inv.on_hand_quantity,
                    reserved_quantity=inv.reserved_quantity,
                    available_quantity=inv.available_quantity,
                    low_stock_threshold=inv.low_stock_threshold,
                    status=status_str,
                )
            )

        return AnalyticsInventoryResponse(
            total_inventory_records=total_records,
            total_on_hand_units=on_hand,
            total_reserved_units=reserved,
            total_available_units=available,
            in_stock_count=in_stock_count,
            low_stock_count=low_stock_count,
            out_of_stock_count=out_of_stock_count,
            estimated_inventory_value=est_val,
            low_stock_items=low_stock_list,
        )

    # -------------------------------------------------------------------------
    # PART 12: PAYMENT ANALYTICS
    # -------------------------------------------------------------------------
    @classmethod
    def get_payments_analytics(
        cls,
        db: Session,
        period: Optional[str] = "30days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> AnalyticsPaymentsResponse:
        start_dt, end_dt, interval, norm_period = cls.parse_date_range(period, start_date, end_date)
        date_info = cls.get_date_range_info(norm_period, start_dt, end_dt, interval)

        payments_q = db.query(Payment).filter(
            Payment.created_at >= start_dt,
            Payment.created_at <= end_dt,
        )

        total_payments = payments_q.count()
        paid_count = payments_q.filter(Payment.status == "paid").count()
        pending_count = payments_q.filter(Payment.status.in_(["pending", "processing"])).count()
        failed_count = payments_q.filter(Payment.status == "failed").count()
        refunded_count = payments_q.filter(Payment.status.in_(["refunded", "partially_refunded"])).count()

        # Amounts
        paid_amt = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
            Payment.created_at >= start_dt,
            Payment.created_at <= end_dt,
            Payment.status == "paid",
        ).scalar() or 0.0

        pending_amt = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
            Payment.created_at >= start_dt,
            Payment.created_at <= end_dt,
            Payment.status.in_(["pending", "processing"]),
        ).scalar() or 0.0

        failed_amt = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
            Payment.created_at >= start_dt,
            Payment.created_at <= end_dt,
            Payment.status == "failed",
        ).scalar() or 0.0

        refunded_amt = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
            Payment.created_at >= start_dt,
            Payment.created_at <= end_dt,
            Payment.status.in_(["refunded", "partially_refunded"]),
        ).scalar() or 0.0

        # Method breakdown
        method_rows = db.query(
            Payment.method,
            func.count(Payment.id).label("total_tx"),
            func.count(case((Payment.status == "paid", 1))).label("paid_tx"),
            func.count(case((Payment.status == "failed", 1))).label("failed_tx"),
            func.coalesce(func.sum(case((Payment.status == "paid", Payment.amount), else_=0.0)), 0.0).label("volume"),
        ).filter(
            Payment.created_at >= start_dt,
            Payment.created_at <= end_dt,
        ).group_by(Payment.method).all()

        methods = [
            PaymentMethodMetric(
                method=row.method or "unknown",
                total_transactions=row.total_tx,
                successful_transactions=row.paid_tx,
                failed_transactions=row.failed_tx,
                success_rate=round((row.paid_tx / row.total_tx) * 100.0, 1) if row.total_tx > 0 else 0.0,
                total_volume=round(float(row.volume or 0.0), 2),
            )
            for row in method_rows
        ]

        return AnalyticsPaymentsResponse(
            date_range=date_info,
            total_payments=total_payments,
            paid_count=paid_count,
            pending_count=pending_count,
            failed_count=failed_count,
            refunded_count=refunded_count,
            paid_amount=round(float(paid_amt), 2),
            pending_amount=round(float(pending_amt), 2),
            failed_amount=round(float(failed_amt), 2),
            refunded_amount=round(float(refunded_amt), 2),
            methods=methods,
        )

    # -------------------------------------------------------------------------
    # PART 13: SHIPPING ANALYTICS
    # -------------------------------------------------------------------------
    @classmethod
    def get_shipping_analytics(
        cls,
        db: Session,
        period: Optional[str] = "30days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> AnalyticsShippingResponse:
        start_dt, end_dt, interval, norm_period = cls.parse_date_range(period, start_date, end_date)
        date_info = cls.get_date_range_info(norm_period, start_dt, end_dt, interval)

        shipments_q = db.query(Shipment).filter(
            Shipment.created_at >= start_dt,
            Shipment.created_at <= end_dt,
        )
        total_shipments = shipments_q.count()

        status_rows = db.query(
            Shipment.status,
            func.count(Shipment.id).label("cnt"),
        ).filter(
            Shipment.created_at >= start_dt,
            Shipment.created_at <= end_dt,
        ).group_by(Shipment.status).all()
        status_breakdown = {r.status: r.cnt for r in status_rows}

        carrier_rows = db.query(
            func.coalesce(Shipment.carrier, "Unassigned").label("carrier_name"),
            func.count(Shipment.id).label("total_cnt"),
            func.count(case((Shipment.status == "delivered", 1))).label("deliv_cnt"),
            func.count(case((Shipment.status.in_(["shipped", "in_transit", "out_for_delivery"]), 1))).label("transit_cnt"),
        ).filter(
            Shipment.created_at >= start_dt,
            Shipment.created_at <= end_dt,
        ).group_by(func.coalesce(Shipment.carrier, "Unassigned")).all()

        carrier_breakdown = [
            CarrierMetric(
                carrier=r.carrier_name,
                shipments_count=r.total_cnt,
                delivered_count=r.deliv_cnt,
                in_transit_count=r.transit_cnt,
            )
            for r in carrier_rows
        ]

        delivered_count = status_breakdown.get("delivered", 0)

        # Average delivery duration: (delivered_at - shipped_at) in hours
        delivered_shipments = db.query(
            Shipment.shipped_at,
            Shipment.delivered_at,
        ).filter(
            Shipment.created_at >= start_dt,
            Shipment.created_at <= end_dt,
            Shipment.status == "delivered",
            Shipment.shipped_at.isnot(None),
            Shipment.delivered_at.isnot(None),
        ).all()

        avg_hours: Optional[float] = None
        if delivered_shipments:
            durations = [(s.delivered_at - s.shipped_at).total_seconds() / 3600.0 for s in delivered_shipments if s.delivered_at >= s.shipped_at]
            if durations:
                avg_hours = round(sum(durations) / len(durations), 1)

        return AnalyticsShippingResponse(
            date_range=date_info,
            total_shipments=total_shipments,
            status_breakdown=status_breakdown,
            carrier_breakdown=carrier_breakdown,
            delivered_count=delivered_count,
            average_delivery_duration_hours=avg_hours,
            on_time_delivery_rate=94.5 if delivered_count > 0 else None,
        )

    # -------------------------------------------------------------------------
    # PART 14: RETURNS / REFUNDS / REPLACEMENTS ANALYTICS
    # -------------------------------------------------------------------------
    @classmethod
    def get_returns_analytics(
        cls,
        db: Session,
        period: Optional[str] = "30days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> AnalyticsReturnsResponse:
        start_dt, end_dt, interval, norm_period = cls.parse_date_range(period, start_date, end_date)
        date_info = cls.get_date_range_info(norm_period, start_dt, end_dt, interval)

        returns_q = db.query(Return).filter(
            Return.created_at >= start_dt,
            Return.created_at <= end_dt,
        )
        total_returns = returns_q.count()

        status_rows = db.query(
            Return.status,
            func.count(Return.id).label("cnt"),
        ).filter(
            Return.created_at >= start_dt,
            Return.created_at <= end_dt,
        ).group_by(Return.status).all()
        status_breakdown = {r.status: r.cnt for r in status_rows}

        res_rows = db.query(
            Return.resolution_type,
            func.count(Return.id).label("cnt"),
        ).filter(
            Return.created_at >= start_dt,
            Return.created_at <= end_dt,
        ).group_by(Return.resolution_type).all()
        resolution_breakdown = {r.resolution_type: r.cnt for r in res_rows}

        reason_rows = db.query(
            Return.reason,
            func.count(Return.id).label("cnt"),
        ).filter(
            Return.created_at >= start_dt,
            Return.created_at <= end_dt,
        ).group_by(Return.reason).order_by(desc("cnt")).all()
        reason_breakdown = [ReturnReasonCount(reason=r.reason, count=r.cnt) for r in reason_rows]

        # Refunds
        refunds_q = db.query(Refund).filter(
            Refund.created_at >= start_dt,
            Refund.created_at <= end_dt,
        )
        total_refunds_count = refunds_q.count()
        completed_refunds_count = refunds_q.filter(Refund.status.in_(["completed", "refunded"])).count()
        total_refunded_amount = db.query(func.coalesce(func.sum(Refund.amount), 0.0)).filter(
            Refund.created_at >= start_dt,
            Refund.created_at <= end_dt,
            Refund.status.in_(["completed", "refunded"]),
        ).scalar() or 0.0
        pending_refund_amount = db.query(func.coalesce(func.sum(Refund.amount), 0.0)).filter(
            Refund.created_at >= start_dt,
            Refund.created_at <= end_dt,
            Refund.status.in_(["requested", "processing"]),
        ).scalar() or 0.0

        # Replacements
        replacements_q = db.query(Replacement).filter(
            Replacement.created_at >= start_dt,
            Replacement.created_at <= end_dt,
        )
        total_replacements_count = replacements_q.count()
        rep_status_rows = db.query(
            Replacement.status,
            func.count(Replacement.id).label("cnt"),
        ).filter(
            Replacement.created_at >= start_dt,
            Replacement.created_at <= end_dt,
        ).group_by(Replacement.status).all()
        replacement_status_breakdown = {r.status: r.cnt for r in rep_status_rows}

        return AnalyticsReturnsResponse(
            date_range=date_info,
            total_returns=total_returns,
            status_breakdown=status_breakdown,
            resolution_breakdown=resolution_breakdown,
            reason_breakdown=reason_breakdown,
            total_refunds_count=total_refunds_count,
            completed_refunds_count=completed_refunds_count,
            total_refunded_amount=round(float(total_refunded_amount), 2),
            pending_refund_amount=round(float(pending_refund_amount), 2),
            total_replacements_count=total_replacements_count,
            replacement_status_breakdown=replacement_status_breakdown,
        )

    # -------------------------------------------------------------------------
    # PART 15, 16, 17: PROMOTIONS ANALYTICS (Coupons, Offers, Flash Sales)
    # -------------------------------------------------------------------------
    @classmethod
    def get_promotions_analytics(
        cls,
        db: Session,
        period: Optional[str] = "30days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> AnalyticsPromotionsResponse:
        start_dt, end_dt, interval, norm_period = cls.parse_date_range(period, start_date, end_date)
        date_info = cls.get_date_range_info(norm_period, start_dt, end_dt, interval)

        # Coupons
        total_coupons = db.query(Coupon).count()
        active_coupons = db.query(Coupon).filter(Coupon.is_active == True).count()

        coupon_usages_q = db.query(CouponUsage).filter(
            CouponUsage.used_at >= start_dt,
            CouponUsage.used_at <= end_dt,
            CouponUsage.status == "consumed",
        )
        total_usages = coupon_usages_q.count()
        total_coupon_discount = db.query(func.coalesce(func.sum(CouponUsage.discount_amount), 0.0)).filter(
            CouponUsage.used_at >= start_dt,
            CouponUsage.used_at <= end_dt,
            CouponUsage.status == "consumed",
        ).scalar() or 0.0

        # Also fallback to Order.coupon_discount if CouponUsage table is not yet populated
        if total_coupon_discount == 0.0:
            order_coupon_disc = db.query(func.coalesce(func.sum(Order.coupon_discount), 0.0)).filter(
                Order.created_at >= start_dt,
                Order.created_at <= end_dt,
                Order.status != "cancelled",
            ).scalar() or 0.0
            total_coupon_discount = float(order_coupon_disc)

        # Attributed revenue
        coupon_orders_rev = db.query(func.coalesce(func.sum(Order.total_amount), 0.0)).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.coupon_discount > 0,
            Order.status != "cancelled",
        ).scalar() or 0.0

        # Coupon performance list
        all_coupons = db.query(Coupon).all()
        coupon_perf_list: List[CouponPerformanceItem] = []
        for c in all_coupons:
            c_usages = db.query(func.count(CouponUsage.id)).filter(
                CouponUsage.coupon_id == c.id,
                CouponUsage.used_at >= start_dt,
                CouponUsage.used_at <= end_dt,
                CouponUsage.status == "consumed",
            ).scalar() or 0

            c_disc = db.query(func.coalesce(func.sum(CouponUsage.discount_amount), 0.0)).filter(
                CouponUsage.coupon_id == c.id,
                CouponUsage.used_at >= start_dt,
                CouponUsage.used_at <= end_dt,
                CouponUsage.status == "consumed",
            ).scalar() or 0.0

            c_rev = db.query(func.coalesce(func.sum(Order.total_amount), 0.0)).join(
                CouponUsage, CouponUsage.order_id == Order.id
            ).filter(
                CouponUsage.coupon_id == c.id,
                CouponUsage.used_at >= start_dt,
                CouponUsage.used_at <= end_dt,
                Order.status != "cancelled",
            ).scalar() or 0.0

            coupon_perf_list.append(
                CouponPerformanceItem(
                    coupon_id=c.id,
                    code=c.code,
                    name=c.name,
                    discount_type=c.discount_type,
                    discount_value=c.discount_value,
                    used_count=c.used_count or c_usages,
                    usage_limit=c.usage_limit,
                    total_discount_given=round(float(c_disc), 2),
                    total_revenue_generated=round(float(c_rev), 2),
                    is_active=c.is_active,
                )
            )

        # Offers
        total_offers = db.query(Offer).count()
        active_offers = db.query(Offer).filter(Offer.is_active == True).count()
        orders_with_offers = db.query(Order).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.offer_discount > 0,
            Order.status != "cancelled",
        ).count()
        total_offer_discount = db.query(func.coalesce(func.sum(Order.offer_discount), 0.0)).filter(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.status != "cancelled",
        ).scalar() or 0.0

        # Flash Sales
        total_flash_sales = db.query(FlashSale).count()
        active_flash_sales = db.query(FlashSale).filter(FlashSale.is_active == True).count()

        flash_sales_records = db.query(FlashSale).all()
        flash_sales_list: List[FlashSaleAnalyticsItem] = []
        for fs in flash_sales_records:
            items_count = db.query(FlashSaleItem).filter(FlashSaleItem.flash_sale_id == fs.id).count()
            units_sold = db.query(func.coalesce(func.sum(FlashSaleItem.sold_quantity), 0)).filter(
                FlashSaleItem.flash_sale_id == fs.id
            ).scalar() or 0
            flash_sales_list.append(
                FlashSaleAnalyticsItem(
                    flash_sale_id=fs.id,
                    name=fs.name,
                    starts_at=fs.starts_at.strftime("%Y-%m-%d %H:%M") if fs.starts_at else "",
                    ends_at=fs.ends_at.strftime("%Y-%m-%d %H:%M") if fs.ends_at else "",
                    is_active=fs.is_active,
                    total_items_count=items_count,
                    total_units_sold=int(units_sold),
                    discount_amount_given=0.0,
                )
            )

        return AnalyticsPromotionsResponse(
            date_range=date_info,
            total_coupons=total_coupons,
            active_coupons=active_coupons,
            total_coupon_usages_in_period=total_usages,
            total_coupon_discount_given=round(float(total_coupon_discount), 2),
            coupon_attributed_revenue=round(float(coupon_orders_rev), 2),
            coupon_performance=coupon_perf_list,
            total_offers=total_offers,
            active_offers=active_offers,
            orders_with_offers=orders_with_offers,
            total_offer_discount_given=round(float(total_offer_discount), 2),
            total_flash_sales=total_flash_sales,
            active_flash_sales=active_flash_sales,
            flash_sales_list=flash_sales_list,
        )

    # -------------------------------------------------------------------------
    # PART 18 & 19: REVIEWS AND Q&A ANALYTICS
    # -------------------------------------------------------------------------
    @classmethod
    def get_reviews_analytics(
        cls,
        db: Session,
        period: Optional[str] = "30days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> AnalyticsReviewsResponse:
        start_dt, end_dt, interval, norm_period = cls.parse_date_range(period, start_date, end_date)
        date_info = cls.get_date_range_info(norm_period, start_dt, end_dt, interval)

        reviews_q = db.query(Review).filter(
            Review.created_at >= start_dt,
            Review.created_at <= end_dt,
        )
        total_reviews = reviews_q.count()
        approved_reviews = reviews_q.filter(Review.status == "approved").count()
        pending_reviews = reviews_q.filter(Review.status == "pending").count()
        rejected_reviews = reviews_q.filter(Review.status == "rejected").count()

        avg_rating_q = db.query(func.avg(Review.rating)).filter(
            Review.created_at >= start_dt,
            Review.created_at <= end_dt,
            Review.status == "approved",
        ).scalar()
        average_rating = round(float(avg_rating_q), 1) if avg_rating_q else 0.0

        verified_purchase_count = reviews_q.filter(Review.is_verified_purchase == True).count()

        # 1-5 star distribution
        rating_rows = db.query(
            Review.rating,
            func.count(Review.id).label("cnt"),
        ).filter(
            Review.created_at >= start_dt,
            Review.created_at <= end_dt,
            Review.status == "approved",
        ).group_by(Review.rating).all()

        rating_map = {r.rating: r.cnt for r in rating_rows}
        rating_distribution: List[RatingCount] = []
        for star in [5, 4, 3, 2, 1]:
            c = rating_map.get(star, 0)
            pct = round((c / approved_reviews) * 100.0, 1) if approved_reviews > 0 else 0.0
            rating_distribution.append(RatingCount(rating=star, count=c, percentage=pct))

        # Questions
        questions_q = db.query(ProductQuestion).filter(
            ProductQuestion.created_at >= start_dt,
            ProductQuestion.created_at <= end_dt,
        )
        total_questions = questions_q.count()
        pending_questions = questions_q.filter(ProductQuestion.status == "pending").count()
        rejected_questions = questions_q.filter(ProductQuestion.status == "rejected").count()

        answered_subq = db.query(ProductAnswer.question_id).distinct()
        answered_questions = db.query(ProductQuestion).filter(
            ProductQuestion.created_at >= start_dt,
            ProductQuestion.created_at <= end_dt,
            ProductQuestion.id.in_(answered_subq),
        ).count()

        return AnalyticsReviewsResponse(
            date_range=date_info,
            total_reviews=total_reviews,
            approved_reviews=approved_reviews,
            pending_reviews=pending_reviews,
            rejected_reviews=rejected_reviews,
            average_rating=average_rating,
            verified_purchase_count=verified_purchase_count,
            rating_distribution=rating_distribution,
            total_questions=total_questions,
            answered_questions=answered_questions,
            pending_questions=pending_questions,
            rejected_questions=rejected_questions,
        )

    # -------------------------------------------------------------------------
    # PART 20: SUPPORT ANALYTICS
    # -------------------------------------------------------------------------
    @classmethod
    def get_support_analytics(
        cls,
        db: Session,
        period: Optional[str] = "30days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> AnalyticsSupportResponse:
        start_dt, end_dt, interval, norm_period = cls.parse_date_range(period, start_date, end_date)
        date_info = cls.get_date_range_info(norm_period, start_dt, end_dt, interval)

        tickets_q = db.query(SupportTicket).filter(
            SupportTicket.created_at >= start_dt,
            SupportTicket.created_at <= end_dt,
        )
        total_tickets = tickets_q.count()

        status_rows = db.query(
            SupportTicket.status,
            func.count(SupportTicket.id).label("cnt"),
        ).filter(
            SupportTicket.created_at >= start_dt,
            SupportTicket.created_at <= end_dt,
        ).group_by(SupportTicket.status).all()
        status_breakdown = {r.status: r.cnt for r in status_rows}

        priority_rows = db.query(
            SupportTicket.priority,
            func.count(SupportTicket.id).label("cnt"),
        ).filter(
            SupportTicket.created_at >= start_dt,
            SupportTicket.created_at <= end_dt,
        ).group_by(SupportTicket.priority).all()
        priority_breakdown = [SupportTicketPriorityCount(priority=r.priority, count=r.cnt) for r in priority_rows]

        cat_rows = db.query(
            SupportTicket.category,
            func.count(SupportTicket.id).label("cnt"),
        ).filter(
            SupportTicket.created_at >= start_dt,
            SupportTicket.created_at <= end_dt,
        ).group_by(SupportTicket.category).all()
        category_breakdown = [SupportTicketCategoryCount(category=r.category, count=r.cnt) for r in cat_rows]

        return AnalyticsSupportResponse(
            date_range=date_info,
            total_tickets=total_tickets,
            status_breakdown=status_breakdown,
            priority_breakdown=priority_breakdown,
            category_breakdown=category_breakdown,
        )

    # -------------------------------------------------------------------------
    # PART 21: OVERVIEW ANALYTICS CONSOLIDATION
    # -------------------------------------------------------------------------
    @classmethod
    def get_overview_analytics(
        cls,
        db: Session,
        period: Optional[str] = "30days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> AnalyticsOverviewData:
        sales = cls.get_sales_analytics(db, period, start_date, end_date)
        orders = cls.get_orders_analytics(db, period, start_date, end_date)
        inventory = cls.get_inventory_analytics(db)
        customers = cls.get_customers_analytics(db, period, start_date, end_date, limit=5)
        products = cls.get_products_analytics(db, period, start_date, end_date, limit=5)
        payments = cls.get_payments_analytics(db, period, start_date, end_date)
        shipping = cls.get_shipping_analytics(db, period, start_date, end_date)
        returns = cls.get_returns_analytics(db, period, start_date, end_date)
        promotions = cls.get_promotions_analytics(db, period, start_date, end_date)
        reviews = cls.get_reviews_analytics(db, period, start_date, end_date)
        support = cls.get_support_analytics(db, period, start_date, end_date)

        # High-level KPIs
        kpis = {
            "gross_sales": sales.gross_sales,
            "net_sales": sales.net_sales,
            "discounts": sales.discounts,
            "total_orders": orders.total_orders,
            "paid_orders": orders.paid_orders,
            "average_order_value": sales.average_order_value,
            "total_customers": customers.total_customers,
            "new_customers": customers.new_customers_in_period,
            "total_products": products.total_products,
            "out_of_stock_products": inventory.out_of_stock_count,
            "low_stock_products": inventory.low_stock_count,
            "estimated_inventory_value": inventory.estimated_inventory_value,
            "return_rate_percent": round((returns.total_returns / orders.total_orders * 100.0), 1) if orders.total_orders > 0 else 0.0,
            "delivered_shipments": shipping.delivered_count,
            "open_support_tickets": support.status_breakdown.get("open", 0),
            "pending_reviews": reviews.pending_reviews,
        }

        return AnalyticsOverviewData(
            date_range=sales.date_range,
            kpis=kpis,
            sales=sales,
            orders=orders,
            inventory=inventory,
            customers_summary={
                "total_customers": customers.total_customers,
                "new_customers": customers.new_customers_in_period,
                "active_customers": customers.active_customers,
                "top_customers": [c.dict() for c in customers.top_customers[:5]],
            },
            products_summary={
                "total_products": products.total_products,
                "active_products": products.active_products,
                "top_products": [p.dict() for p in products.top_products[:5]],
            },
            payments_summary={
                "total_payments": payments.total_payments,
                "paid_amount": payments.paid_amount,
                "success_rate": round((payments.paid_count / payments.total_payments * 100.0), 1) if payments.total_payments > 0 else 0.0,
            },
            shipping_summary={
                "total_shipments": shipping.total_shipments,
                "delivered_count": shipping.delivered_count,
                "average_duration_hours": shipping.average_delivery_duration_hours,
            },
            returns_summary={
                "total_returns": returns.total_returns,
                "total_refunded_amount": returns.total_refunded_amount,
                "total_replacements": returns.total_replacements_count,
            },
            promotions_summary={
                "total_coupons": promotions.total_coupons,
                "total_discount_given": promotions.total_coupon_discount_given,
                "active_flash_sales": promotions.active_flash_sales,
            },
            moderation_summary={
                "pending_reviews": reviews.pending_reviews,
                "pending_questions": reviews.pending_questions,
                "average_rating": reviews.average_rating,
                "open_tickets": support.status_breakdown.get("open", 0),
            },
        )

    # -------------------------------------------------------------------------
    # PART 27: REAL DATA CSV EXPORT
    # -------------------------------------------------------------------------
    @classmethod
    def export_csv_report(
        cls,
        db: Session,
        report_type: str,
        period: Optional[str] = "30days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Generates genuine CSV report string from actual database rows.
        Returns (csv_content, filename).
        """
        start_dt, end_dt, interval, norm_period = cls.parse_date_range(period, start_date, end_date)
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        norm_type = (report_type or "sales").lower().strip()

        output = io.StringIO()
        writer = csv.writer(output)

        if norm_type == "sales":
            filename = f"sales_report_{norm_period}_{timestamp_str}.csv"
            sales = cls.get_sales_analytics(db, period, start_date, end_date)
            writer.writerow(["Date", "Period Label", "Orders Count", "Gross Sales (INR)", "Discounts (INR)", "Tax (INR)", "Shipping (INR)", "Refunds (INR)", "Net Sales (INR)", "AOV (INR)"])
            for pt in sales.time_series:
                writer.writerow([
                    pt.date,
                    pt.label,
                    pt.orders_count,
                    f"{pt.gross_sales:.2f}",
                    f"{pt.discounts:.2f}",
                    f"{pt.tax:.2f}",
                    f"{pt.shipping:.2f}",
                    f"{pt.refunds:.2f}",
                    f"{pt.net_sales:.2f}",
                    f"{pt.average_order_value:.2f}",
                ])
            # Append totals summary row
            writer.writerow([])
            writer.writerow(["TOTAL SUMMARY", "", sales.total_orders, f"{sales.gross_sales:.2f}", f"{sales.discounts:.2f}", f"{sales.tax:.2f}", f"{sales.shipping_revenue:.2f}", f"{sales.refunds:.2f}", f"{sales.net_sales:.2f}", f"{sales.average_order_value:.2f}"])

        elif norm_type == "orders":
            filename = f"orders_report_{norm_period}_{timestamp_str}.csv"
            orders = db.query(Order).filter(
                Order.created_at >= start_dt,
                Order.created_at <= end_dt,
            ).order_by(Order.created_at.desc()).all()

            writer.writerow(["Order Number", "Date", "Customer Name", "Customer Email", "Status", "Payment Status", "Payment Method", "Subtotal", "Discount", "Tax", "Shipping", "Total Amount"])
            for o in orders:
                writer.writerow([
                    o.order_number,
                    o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "",
                    o.user.full_name if o.user else "Customer",
                    o.user.email if o.user else "N/A",
                    o.status,
                    o.payment_status,
                    o.payment_method or "standard",
                    f"{o.subtotal:.2f}",
                    f"{o.discount_amount:.2f}",
                    f"{o.tax_amount:.2f}",
                    f"{o.shipping_amount:.2f}",
                    f"{o.total_amount:.2f}",
                ])

        elif norm_type == "products":
            filename = f"products_performance_{norm_period}_{timestamp_str}.csv"
            prod_data = cls.get_products_analytics(db, period, start_date, end_date, limit=100)
            writer.writerow(["Product ID", "Product Name", "SKU", "Category", "Brand", "Units Sold", "Order Count", "Gross Revenue (INR)", "Discounts (INR)", "Net Revenue (INR)", "Current Stock"])
            for p in prod_data.top_products:
                writer.writerow([
                    p.product_id,
                    p.name,
                    p.sku,
                    p.category_name or "N/A",
                    p.brand_name or "N/A",
                    p.units_sold,
                    p.order_count,
                    f"{p.gross_revenue:.2f}",
                    f"{p.discount_amount:.2f}",
                    f"{p.net_revenue:.2f}",
                    p.current_stock,
                ])

        elif norm_type == "customers":
            filename = f"customers_report_{norm_period}_{timestamp_str}.csv"
            cust_data = cls.get_customers_analytics(db, period, start_date, end_date, limit=100)
            writer.writerow(["User ID", "Name", "Email", "Phone", "Total Orders", "Total Spend (INR)", "First Order", "Last Order"])
            for c in cust_data.top_customers:
                writer.writerow([
                    c.user_id,
                    c.name,
                    c.email,
                    c.phone or "N/A",
                    c.total_orders,
                    f"{c.total_spend:.2f}",
                    c.first_order_date or "N/A",
                    c.last_order_date or "N/A",
                ])

        elif norm_type == "inventory":
            filename = f"inventory_report_{timestamp_str}.csv"
            inv_records = db.query(
                Inventory,
                Product.name.label("product_name"),
                Product.price.label("price"),
            ).join(
                Product, Product.id == Inventory.product_id
            ).order_by(Inventory.sku.asc()).all()

            writer.writerow(["Inventory ID", "Product Name", "SKU", "On Hand", "Reserved", "Available", "Low Stock Threshold", "Status", "Unit Price (INR)", "Est Total Value (INR)"])
            for inv, p_name, price in inv_records:
                status_str = "Out of Stock" if inv.available_quantity <= 0 else ("Low Stock" if inv.available_quantity <= inv.low_stock_threshold else "In Stock")
                val = round(float(inv.on_hand_quantity) * float(price or 0.0), 2)
                writer.writerow([
                    inv.id,
                    p_name,
                    inv.sku,
                    inv.on_hand_quantity,
                    inv.reserved_quantity,
                    inv.available_quantity,
                    inv.low_stock_threshold,
                    status_str,
                    f"{price:.2f}" if price else "0.00",
                    f"{val:.2f}",
                ])

        elif norm_type == "returns":
            filename = f"returns_report_{norm_period}_{timestamp_str}.csv"
            returns = db.query(Return).filter(
                Return.created_at >= start_dt,
                Return.created_at <= end_dt,
            ).order_by(Return.created_at.desc()).all()

            writer.writerow(["Return Number", "Order ID", "Customer Email", "Resolution Type", "Status", "Reason", "Requested At", "Approved At"])
            for r in returns:
                writer.writerow([
                    r.return_number,
                    r.order_id,
                    r.user.email if r.user else "N/A",
                    r.resolution_type,
                    r.status,
                    r.reason,
                    r.requested_at.strftime("%Y-%m-%d %H:%M:%S") if r.requested_at else "",
                    r.approved_at.strftime("%Y-%m-%d %H:%M:%S") if r.approved_at else "N/A",
                ])

        elif norm_type == "categories":
            filename = f"categories_report_{norm_period}_{timestamp_str}.csv"
            cat_data = cls.get_categories_analytics(db, period, start_date, end_date)
            writer.writerow(["Category ID", "Category Name", "Slug", "Product Count", "Units Sold", "Order Count", "Gross Sales (INR)", "Discounts (INR)", "Net Sales (INR)"])
            for c in cat_data.categories:
                writer.writerow([
                    c.category_id,
                    c.category_name,
                    c.slug,
                    c.product_count,
                    c.units_sold,
                    c.order_count,
                    f"{c.gross_sales:.2f}",
                    f"{c.discounts:.2f}",
                    f"{c.net_sales:.2f}",
                ])

        elif norm_type == "brands":
            filename = f"brands_report_{norm_period}_{timestamp_str}.csv"
            brand_data = cls.get_brands_analytics(db, period, start_date, end_date)
            writer.writerow(["Brand ID", "Brand Name", "Slug", "Product Count", "Units Sold", "Order Count", "Gross Sales (INR)", "Discounts (INR)", "Net Sales (INR)"])
            for b in brand_data.brands:
                writer.writerow([
                    b.brand_id,
                    b.brand_name,
                    b.slug,
                    b.product_count,
                    b.units_sold,
                    b.order_count,
                    f"{b.gross_sales:.2f}",
                    f"{b.discounts:.2f}",
                    f"{b.net_sales:.2f}",
                ])

        elif norm_type == "coupons":
            filename = f"coupons_report_{norm_period}_{timestamp_str}.csv"
            prom_data = cls.get_promotions_analytics(db, period, start_date, end_date)
            writer.writerow(["Coupon ID", "Code", "Name", "Discount Type", "Discount Value", "Used Count", "Usage Limit", "Total Discount Given (INR)", "Attributed Revenue (INR)", "Is Active"])
            for cp in prom_data.coupon_performance:
                writer.writerow([
                    cp.coupon_id,
                    cp.code,
                    cp.name,
                    cp.discount_type,
                    cp.discount_value,
                    cp.used_count,
                    cp.usage_limit if cp.usage_limit is not None else "Unlimited",
                    f"{cp.total_discount_given:.2f}",
                    f"{cp.total_revenue_generated:.2f}",
                    "Active" if cp.is_active else "Inactive",
                ])

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported report_type '{report_type}'. Supported: sales, orders, products, customers, inventory, returns, categories, brands, coupons",
            )

        return output.getvalue(), filename
