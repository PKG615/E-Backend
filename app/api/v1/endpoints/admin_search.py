from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from app.core.database import get_db

from app.api.v1.endpoints.auth import get_current_admin

from app.models.user import User

from app.models.product import Product

from app.models.order import Order

from app.models.promotions import Coupon

from app.models.support import SupportTicket

from app.schemas.common import APIResponse

router = APIRouter()

@router.get("", response_model=APIResponse[Dict[str, List[Dict[str, Any]]]])
def admin_global_search(
    q: str = Query(..., min_length=2, description="Search term across entities"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    query_str = q.strip()
    like_pattern = f"%{query_str}%"

    # 1. Products search
    products = db.query(Product).filter(
        or_(
            Product.name.ilike(like_pattern),
            Product.sku.ilike(like_pattern),
            Product.slug.ilike(like_pattern)
        )
    ).limit(6).all()
    product_results = [
        {
            "id": p.id,
            "title": p.name,
            "subtitle": f"SKU: {p.sku} • ₹{p.price} • Stock: {p.stock}",
            "type": "product",
            "link": f"/admin/products"
        }
        for p in products
    ]

    # 2. Orders search
    orders = db.query(Order).join(User, Order.user_id == User.id, isouter=True).filter(
        or_(
            Order.order_number.ilike(like_pattern),
            User.email.ilike(like_pattern),
            User.full_name.ilike(like_pattern)
        )
    ).order_by(desc(Order.created_at)).limit(6).all()
    order_results = [
        {
            "id": o.id,
            "title": f"Order #{o.order_number}",
            "subtitle": f"{o.user.full_name if o.user else 'Customer'} • ₹{o.total_amount} • {o.status.upper()}",
            "type": "order",
            "link": f"/admin/orders"
        }
        for o in orders
    ]

    # 3. Customers search
    customers = db.query(User).filter(
        User.role == "customer",
        or_(
            User.full_name.ilike(like_pattern),
            User.email.ilike(like_pattern),
            User.phone.ilike(like_pattern)
        )
    ).limit(6).all()
    customer_results = [
        {
            "id": c.id,
            "title": c.full_name,
            "subtitle": f"{c.email} • {c.phone or 'No phone'}",
            "type": "customer",
            "link": f"/admin/customers?search={c.email}"
        }
        for c in customers
    ]

    # 4. Coupons search
    coupons = db.query(Coupon).filter(
        or_(
            Coupon.code.ilike(like_pattern),
            Coupon.name.ilike(like_pattern)
        )
    ).limit(5).all()
    coupon_results = [
        {
            "id": cp.id,
            "title": cp.code,
            "subtitle": f"{cp.name} • {'Active' if cp.is_active else 'Inactive'}",
            "type": "coupon",
            "link": f"/admin/marketing"
        }
        for cp in coupons
    ]

    # 5. Support Tickets search
    tickets = db.query(SupportTicket).filter(
        or_(
            SupportTicket.ticket_number.ilike(like_pattern),
            SupportTicket.subject.ilike(like_pattern)
        )
    ).order_by(desc(SupportTicket.created_at)).limit(5).all()
    ticket_results = [
        {
            "id": t.id,
            "title": f"Ticket #{t.ticket_number}",
            "subtitle": f"{t.subject} • {t.status.upper()}",
            "type": "ticket",
            "link": f"/admin/support"
        }
        for t in tickets
    ]

    return APIResponse(
        success=True,
        message=f"Global search executed for '{q}'",
        data={
            "products": product_results,
            "orders": order_results,
            "customers": customer_results,
            "coupons": coupon_results,
            "tickets": ticket_results
        }
    )
