from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, desc, or_, and_
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_admin, require_permission
from app.models.user import User
from app.models.product import Product
from app.models.order import Order, OrderItem, Payment
from app.models.category import Category
from app.models.shipment import Shipment
from app.models.returns import Return, Refund, Replacement
from app.models.promotions import Coupon, Offer, FlashSale, CouponUsage
from app.models.reviews import Review, ProductQuestion
from app.models.support import SupportTicket
from app.schemas.dashboard import (
    DashboardMetrics,
    DashboardOverviewResponse,
    SalesSummary,
    OrderStatusBreakdown,
    CustomerMetricsSummary,
    ProductMetricsSummary,
    InventoryAlertItem,
    PaymentMetricsSummary,
    ShippingMetricsSummary,
    ReturnsMetricsSummary,
    MarketingMetricsSummary,
    ModerationMetricsSummary,
    SalesChartData,
    SalesChartPoint,
    RecentOrderItem,
    TopProductItem,
    CategoryPerformanceItem,
    OperationalAlert
)
from app.schemas.common import APIResponse

router = APIRouter()

def get_period_bounds(period: str, custom_start: Optional[str] = None, custom_end: Optional[str] = None):
    now = datetime.utcnow()
    if period == "today":
        start_date = datetime(now.year, now.month, now.day)
        end_date = now
    elif period == "7days":
        start_date = now - timedelta(days=7)
        end_date = now
    elif period == "30days":
        start_date = now - timedelta(days=30)
        end_date = now
    elif period == "90days":
        start_date = now - timedelta(days=90)
        end_date = now
    elif period == "custom" and custom_start and custom_end:
        try:
            start_date = datetime.fromisoformat(custom_start)
            end_date = datetime.fromisoformat(custom_end)
        except Exception:
            start_date = now - timedelta(days=30)
            end_date = now
    else:
        start_date = now - timedelta(days=7)
        end_date = now
    return start_date, end_date

@router.get("/overview", response_model=APIResponse[DashboardOverviewResponse])
def get_dashboard_overview(
    period: str = Query("7days", description="today | 7days | 30days | 90days | custom"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_admin: User = Depends(require_permission("dashboard.read")),
    db: Session = Depends(get_db)
):
    start_dt, end_dt = get_period_bounds(period, start_date, end_date)

    # 1. SALES SUMMARY (Real financial data from Orders and Payments)
    paid_orders = db.query(Order).filter(
        Order.created_at >= start_dt,
        Order.created_at <= end_dt,
        Order.payment_status == "paid"
    ).all()

    gross_sales = float(sum(o.total_amount for o in paid_orders))
    discounts = float(sum(o.discount_amount for o in paid_orders))
    tax = float(sum(o.tax_amount for o in paid_orders))
    shipping = float(sum(o.shipping_amount for o in paid_orders))
    net_order_value = float(sum(o.subtotal for o in paid_orders))

    all_period_orders = db.query(Order).filter(
        Order.created_at >= start_dt,
        Order.created_at <= end_dt
    ).all()

    paid_amount = gross_sales
    pending_amount = float(sum(o.total_amount for o in all_period_orders if o.payment_status in ["pending", "processing"]))

    sales_summary = SalesSummary(
        gross_sales=round(gross_sales, 2),
        discounts=round(discounts, 2),
        tax=round(tax, 2),
        shipping=round(shipping, 2),
        net_order_value=round(net_order_value, 2),
        paid_amount=round(paid_amount, 2),
        pending_amount=round(pending_amount, 2)
    )

    # 2. ORDER SUMMARY (Using actual order model statuses)
    order_status_counts: Dict[str, int] = {}
    for o in all_period_orders:
        order_status_counts[o.status] = order_status_counts.get(o.status, 0) + 1

    orders_summary = OrderStatusBreakdown(
        total=len(all_period_orders),
        pending=order_status_counts.get("pending", 0),
        confirmed=order_status_counts.get("confirmed", 0),
        processing=order_status_counts.get("processing", 0),
        shipped=order_status_counts.get("shipped", 0),
        delivered=order_status_counts.get("delivered", 0),
        cancelled=order_status_counts.get("cancelled", 0),
        returned=order_status_counts.get("returned", 0)
    )

    # 3. CUSTOMER SUMMARY
    total_customers = db.query(User).filter(User.role == "customer").count()
    active_customers = db.query(User).filter(User.role == "customer", User.is_active == True).count()
    new_customers = db.query(User).filter(
        User.role == "customer",
        User.created_at >= start_dt,
        User.created_at <= end_dt
    ).count()
    customer_ids_with_orders = db.query(distinct(Order.user_id)).scalar_subquery()
    customers_with_orders = db.query(User).filter(
        User.role == "customer",
        User.id.in_(customer_ids_with_orders)
    ).count()
    customers_without_orders = max(0, total_customers - customers_with_orders)

    customers_summary = CustomerMetricsSummary(
        total_customers=total_customers,
        active_customers=active_customers,
        new_customers_in_period=new_customers,
        customers_with_orders=customers_with_orders,
        customers_without_orders=customers_without_orders
    )

    # 4. PRODUCT & INVENTORY SUMMARY
    all_products = db.query(Product).all()
    total_products = len(all_products)
    active_products = sum(1 for p in all_products if p.is_active)
    inactive_products = total_products - active_products
    low_stock_products = sum(1 for p in all_products if 0 < p.stock <= 5)
    out_of_stock_products = sum(1 for p in all_products if p.stock <= 0)
    total_inventory_units = sum(p.stock for p in all_products)

    products_summary = ProductMetricsSummary(
        total_products=total_products,
        active_products=active_products,
        inactive_products=inactive_products,
        low_stock_products=low_stock_products,
        out_of_stock_products=out_of_stock_products,
        total_inventory_units=total_inventory_units
    )

    # Inventory Alerts list
    inventory_alert_items = []
    alert_prods = [p for p in all_products if p.stock <= 5]
    for p in alert_prods[:15]:
        inventory_alert_items.append(
            InventoryAlertItem(
                product_id=p.id,
                variant_id=None,
                sku=p.sku,
                product_name=p.name,
                variant_title=None,
                stock=p.stock,
                safety_stock=5,
                status="out_of_stock" if p.stock <= 0 else "low_stock"
            )
        )

    # 5. PAYMENT SUMMARY
    payments_in_period = db.query(Payment).filter(
        Payment.created_at >= start_dt,
        Payment.created_at <= end_dt
    ).all()
    paid_count = sum(1 for py in payments_in_period if py.status == "paid")
    pending_count = sum(1 for py in payments_in_period if py.status in ["pending", "processing"])
    failed_count = sum(1 for py in payments_in_period if py.status == "failed")
    refunded_count = sum(1 for py in payments_in_period if py.status == "refunded")

    payment_summary = PaymentMetricsSummary(
        total_payments=len(payments_in_period),
        paid_count=paid_count,
        pending_count=pending_count,
        failed_count=failed_count,
        refunded_count=refunded_count,
        paid_amount=round(sum(py.amount for py in payments_in_period if py.status == "paid"), 2),
        pending_amount=round(sum(py.amount for py in payments_in_period if py.status in ["pending", "processing"]), 2),
        failed_amount=round(sum(py.amount for py in payments_in_period if py.status == "failed"), 2),
        refunded_amount=round(sum(py.amount for py in payments_in_period if py.status == "refunded"), 2)
    )

    # 6. SHIPPING SUMMARY
    shipments_in_period = db.query(Shipment).filter(
        Shipment.created_at >= start_dt,
        Shipment.created_at <= end_dt
    ).all()
    shipment_status_map: Dict[str, int] = {}
    for s in shipments_in_period:
        shipment_status_map[s.status] = shipment_status_map.get(s.status, 0) + 1

    shipping_summary = ShippingMetricsSummary(
        total_shipments=len(shipments_in_period),
        pending=shipment_status_map.get("pending", 0),
        processing=shipment_status_map.get("processing", 0),
        packed=shipment_status_map.get("packed", 0),
        shipped=shipment_status_map.get("shipped", 0),
        in_transit=shipment_status_map.get("in_transit", 0),
        out_for_delivery=shipment_status_map.get("out_for_delivery", 0),
        delivered=shipment_status_map.get("delivered", 0),
        failed_cancelled=shipment_status_map.get("failed", 0) + shipment_status_map.get("cancelled", 0)
    )

    # 7. RETURNS, REFUNDS & REPLACEMENTS
    returns_in_period = db.query(Return).filter(Return.created_at >= start_dt).all()
    refunds_in_period = db.query(Refund).filter(Refund.created_at >= start_dt).all()
    replacements_in_period = db.query(Replacement).filter(Replacement.created_at >= start_dt).all()

    returns_summary = ReturnsMetricsSummary(
        total_returns=len(returns_in_period),
        pending_returns=sum(1 for r in returns_in_period if r.status in ["requested", "pickup_pending", "picked_up"]),
        awaiting_inspection=sum(1 for r in returns_in_period if r.status == "received"),
        approved_for_refund=sum(1 for r in returns_in_period if r.status == "approved_for_refund"),
        rejected=sum(1 for r in returns_in_period if r.status == "rejected"),
        refund_processing=sum(1 for rf in refunds_in_period if rf.status in ["requested", "processing"]),
        refunded=sum(1 for rf in refunds_in_period if rf.status == "completed"),
        refund_failed=sum(1 for rf in refunds_in_period if rf.status == "failed"),
        replacement_processing=sum(1 for rp in replacements_in_period if rp.status in ["requested", "approved", "processing"]),
        replacement_shipped=sum(1 for rp in replacements_in_period if rp.status in ["shipped", "delivered"])
    )

    # 8. MARKETING SUMMARY
    now = datetime.utcnow()
    all_coupons = db.query(Coupon).all()
    active_coupons = sum(1 for c in all_coupons if c.is_active and (c.expires_at is None or c.expires_at > now))
    expiring_soon = sum(1 for c in all_coupons if c.is_active and c.expires_at and now < c.expires_at <= now + timedelta(days=7))
    total_coupon_usages = db.query(CouponUsage).count()
    active_offers = db.query(Offer).filter(Offer.is_active == True, (Offer.expires_at.is_(None)) | (Offer.expires_at > now)).count()
    active_flash_sales = db.query(FlashSale).filter(FlashSale.is_active == True, (FlashSale.ends_at.is_(None)) | (FlashSale.ends_at > now)).count()

    marketing_summary = MarketingMetricsSummary(
        total_coupons=len(all_coupons),
        active_coupons=active_coupons,
        expiring_soon_coupons=expiring_soon,
        total_coupon_usages=total_coupon_usages,
        active_offers=active_offers,
        active_flash_sales=active_flash_sales
    )

    # 9. REVIEWS & SUPPORT MODERATION SUMMARY
    reviews = db.query(Review).all()
    questions = db.query(ProductQuestion).all()
    tickets = db.query(SupportTicket).all()

    moderation_summary = ModerationMetricsSummary(
        pending_reviews=sum(1 for r in reviews if r.status == "pending"),
        approved_reviews=sum(1 for r in reviews if r.status == "approved"),
        rejected_reviews=sum(1 for r in reviews if r.status == "rejected"),
        total_reviews=len(reviews),
        pending_questions=sum(1 for q in questions if q.status == "pending" or not q.answers),
        answered_questions=sum(1 for q in questions if len(q.answers) > 0),
        total_questions=len(questions),
        open_support_tickets=sum(1 for t in tickets if t.status in ["open", "in_progress"]),
        urgent_support_tickets=sum(1 for t in tickets if t.status in ["open", "in_progress"] and t.priority in ["high", "urgent"]),
        waiting_customer_tickets=sum(1 for t in tickets if t.status == "waiting_for_customer"),
        resolved_tickets=sum(1 for t in tickets if t.status in ["resolved", "closed"])
    )

    # 10. REAL SALES CHART TIME-SERIES DATA
    # Group actual orders by calendar day in the selected period
    num_days = max(1, (end_dt.date() - start_dt.date()).days + 1)
    if num_days > 90:
        num_days = 90
    
    chart_points: List[SalesChartPoint] = []
    labels: List[str] = []
    sales_arr: List[float] = []
    orders_arr: List[int] = []

    for i in range(num_days):
        current_day = start_dt.date() + timedelta(days=i)
        day_start = datetime(current_day.year, current_day.month, current_day.day, 0, 0, 0)
        day_end = datetime(current_day.year, current_day.month, current_day.day, 23, 59, 59)

        day_orders = [o for o in all_period_orders if day_start <= o.created_at <= day_end]
        day_paid_orders = [o for o in day_orders if o.payment_status == "paid"]

        day_sales = float(sum(o.total_amount for o in day_paid_orders))
        day_order_count = len(day_orders)
        aov = round(day_sales / day_order_count, 2) if day_order_count > 0 else 0.0

        label_str = current_day.strftime("%b %d")
        labels.append(label_str)
        sales_arr.append(round(day_sales, 2))
        orders_arr.append(day_order_count)

        chart_points.append(
            SalesChartPoint(
                label=label_str,
                date=current_day.isoformat(),
                sales=round(day_sales, 2),
                orders=day_order_count,
                average_order_value=aov
            )
        )

    chart_data = SalesChartData(
        period=period,
        labels=labels,
        sales=sales_arr,
        orders=orders_arr,
        points=chart_points
    )

    # 11. RECENT ORDERS (Bounded query, real data)
    recent_orders_q = db.query(Order).order_by(Order.created_at.desc()).limit(8).all()
    recent_orders = [
        RecentOrderItem(
            id=o.id,
            order_number=o.order_number,
            customer_name=o.user.full_name if o.user else "Customer",
            customer_email=o.user.email if o.user else "N/A",
            total_amount=round(o.total_amount, 2),
            status=o.status,
            payment_status=o.payment_status,
            created_at=o.created_at.strftime("%Y-%m-%d %H:%M")
        )
        for o in recent_orders_q
    ]

    # 12. TOP PRODUCTS (Calculated from actual OrderItems)
    top_items = (
        db.query(
            OrderItem.product_id,
            OrderItem.product_name,
            OrderItem.sku,
            OrderItem.image_url,
            func.sum(OrderItem.quantity).label("units_sold"),
            func.sum(OrderItem.total_price).label("revenue"),
            func.count(distinct(OrderItem.order_id)).label("order_count")
        )
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.status != "cancelled")
        .group_by(OrderItem.product_id, OrderItem.product_name, OrderItem.sku, OrderItem.image_url)
        .order_by(desc("revenue"))
        .limit(5)
        .all()
    )

    top_products = [
        TopProductItem(
            product_id=ti.product_id,
            product_name=ti.product_name,
            sku=ti.sku,
            image_url=ti.image_url,
            units_sold=int(ti.units_sold or 0),
            revenue=round(float(ti.revenue or 0.0), 2),
            order_count=int(ti.order_count or 0)
        )
        for ti in top_items
    ]

    # 13. CATEGORY PERFORMANCE (Real product & sales distribution)
    categories = db.query(Category).filter(Category.is_active == True).all()
    category_perf: List[CategoryPerformanceItem] = []
    for cat in categories:
        cat_prod_count = len(cat.products) if cat.products else 0
        cat_items = (
            db.query(
                func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
                func.coalesce(func.sum(OrderItem.total_price), 0.0).label("revenue")
            )
            .join(Product, OrderItem.product_id == Product.id)
            .filter(Product.category_id == cat.id)
            .first()
        )
        category_perf.append(
            CategoryPerformanceItem(
                category_id=cat.id,
                category_name=cat.name,
                product_count=cat_prod_count,
                units_sold=int(cat_items.units_sold) if cat_items else 0,
                revenue=round(float(cat_items.revenue), 2) if cat_items else 0.0
            )
        )

    # 14. DYNAMIC OPERATIONAL ALERTS
    alerts: List[OperationalAlert] = []
    if out_of_stock_products > 0:
        alerts.append(
            OperationalAlert(
                id="alert-oos",
                type="danger",
                category="inventory",
                title="Critical Stock Depletion",
                message=f"{out_of_stock_products} product(s) are completely out of stock and unavailable for customers.",
                count=out_of_stock_products,
                action_label="Restock Inventory",
                action_tab="inventory"
            )
        )
    if low_stock_products > 0:
        alerts.append(
            OperationalAlert(
                id="alert-low-stock",
                type="warning",
                category="inventory",
                title="Low Stock Warning",
                message=f"{low_stock_products} product(s) have fallen below safety threshold (5 units).",
                count=low_stock_products,
                action_label="Manage Inventory",
                action_tab="inventory"
            )
        )
    if returns_summary.pending_returns > 0:
        alerts.append(
            OperationalAlert(
                id="alert-pending-returns",
                type="info",
                category="returns",
                title="Pending Customer Returns",
                message=f"{returns_summary.pending_returns} return request(s) await dispatch or inspection approval.",
                count=returns_summary.pending_returns,
                action_label="Review Returns",
                action_tab="returns"
            )
        )
    if moderation_summary.urgent_support_tickets > 0:
        alerts.append(
            OperationalAlert(
                id="alert-urgent-tickets",
                type="danger",
                category="support",
                title="High-Priority Support Escalations",
                message=f"{moderation_summary.urgent_support_tickets} urgent customer support ticket(s) require intervention.",
                count=moderation_summary.urgent_support_tickets,
                action_label="Open Support Queue",
                action_tab="support"
            )
        )
    if moderation_summary.pending_reviews > 0:
        alerts.append(
            OperationalAlert(
                id="alert-pending-reviews",
                type="info",
                category="reviews",
                title="Reviews Awaiting Moderation",
                message=f"{moderation_summary.pending_reviews} submitted customer review(s) require moderation.",
                count=moderation_summary.pending_reviews,
                action_label="Moderate Reviews",
                action_tab="reviews"
            )
        )
    if payment_summary.failed_count > 0:
        alerts.append(
            OperationalAlert(
                id="alert-failed-payments",
                type="warning",
                category="payments",
                title="Failed Payment Transactions",
                message=f"{payment_summary.failed_count} customer payment(s) failed during checkout in this period.",
                count=payment_summary.failed_count,
                action_label="View Orders",
                action_tab="orders"
            )
        )

    return APIResponse(
        success=True,
        message="Comprehensive admin overview calculated successfully",
        data=DashboardOverviewResponse(
            period=period,
            sales=sales_summary,
            orders=orders_summary,
            customers=customers_summary,
            products=products_summary,
            inventory_alerts=inventory_alert_items,
            payments=payment_summary,
            shipments=shipping_summary,
            returns=returns_summary,
            marketing=marketing_summary,
            moderation=moderation_summary,
            chart=chart_data,
            recent_orders=recent_orders,
            top_products=top_products,
            category_performance=category_perf,
            alerts=alerts
        )
    )

# Retain backward compatible route
@router.get("", response_model=APIResponse[DashboardMetrics])
def get_admin_dashboard(
    current_admin: User = Depends(require_permission("dashboard.read")),
    db: Session = Depends(get_db)
):
    total_revenue = db.query(func.coalesce(func.sum(Order.total_amount), 0.0)).filter(
        Order.payment_status == "paid"
    ).scalar() or 0.0
    
    total_orders = db.query(Order).count()
    total_products = db.query(Product).count()
    total_customers = db.query(User).filter(User.role == "customer").count()
    low_stock_products = db.query(Product).filter(Product.stock <= 5).count()
    
    recent_orders_query = db.query(Order).order_by(Order.created_at.desc()).limit(5).all()
    recent_orders = [
        {
            "id": o.id,
            "order_number": o.order_number,
            "customer_name": o.user.full_name if o.user else "Customer",
            "total_amount": o.total_amount,
            "status": o.status,
            "payment_status": o.payment_status,
            "created_at": o.created_at.strftime("%Y-%m-%d %H:%M")
        }
        for o in recent_orders_query
    ]
    
    # 7-day actual sales trend
    now = datetime.utcnow()
    sales_trend = []
    for i in range(6, -1, -1):
        target_day = now.date() - timedelta(days=i)
        d_start = datetime(target_day.year, target_day.month, target_day.day, 0, 0, 0)
        d_end = datetime(target_day.year, target_day.month, target_day.day, 23, 59, 59)
        day_sales = db.query(func.coalesce(func.sum(Order.total_amount), 0.0)).filter(
            Order.created_at >= d_start,
            Order.created_at <= d_end,
            Order.payment_status == "paid"
        ).scalar() or 0.0
        day_orders = db.query(Order).filter(
            Order.created_at >= d_start,
            Order.created_at <= d_end
        ).count()
        sales_trend.append({
            "day": target_day.strftime("%a"),
            "sales": round(float(day_sales), 2),
            "orders": day_orders
        })
    
    return APIResponse(
        success=True,
        message="Admin metrics retrieved successfully",
        data=DashboardMetrics(
            total_revenue=float(total_revenue),
            total_orders=total_orders,
            total_products=total_products,
            total_customers=total_customers,
            low_stock_products=low_stock_products,
            recent_orders=recent_orders,
            sales_trend=sales_trend
        )
    )

