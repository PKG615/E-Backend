from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_
from app.core.database import get_db
from app.api.v1.endpoints.auth import require_permission
from app.models.user import User, Address
from app.models.order import Order, OrderItem
from app.models.wishlist import WishlistItem
from app.models.reviews import Review
from app.models.returns import Return, Refund
from app.models.support import SupportTicket
from app.schemas.user import AdminCustomerListItem, AdminCustomerDetail, AdminCustomerStatusUpdate
from app.schemas.common import APIResponse

router = APIRouter()

@router.get("", response_model=APIResponse[List[AdminCustomerListItem]])
def list_customers(
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    status_filter: Optional[str] = Query("all", description="all | active | inactive"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("created_at_desc", description="created_at_desc | created_at_asc | orders_desc | name_asc"),
    current_admin: User = Depends(require_permission("customers.read")),
    db: Session = Depends(get_db)
):
    query = db.query(User).filter(User.role == "customer")

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(or_(
            User.full_name.ilike(s),
            User.email.ilike(s),
            User.phone.ilike(s)
        ))

    if status_filter == "active":
        query = query.filter(User.is_active == True)
    elif status_filter == "inactive":
        query = query.filter(User.is_active == False)

    users = query.all()

    # Aggregate customer order stats directly from PostgreSQL
    items: List[AdminCustomerListItem] = []
    for u in users:
        user_orders = db.query(Order).filter(Order.user_id == u.id).all()
        order_count = len(user_orders)
        total_spent = sum(o.total_amount for o in user_orders if o.payment_status == "paid")
        last_order = max(user_orders, key=lambda o: o.created_at) if user_orders else None
        last_order_date = last_order.created_at.strftime("%Y-%m-%d %H:%M") if last_order else None

        items.append(
            AdminCustomerListItem(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                phone=u.phone,
                avatar_url=u.avatar_url,
                role=u.role,
                is_active=u.is_active,
                is_verified=u.is_verified,
                created_at=u.created_at,
                order_count=order_count,
                total_spent=round(float(total_spent), 2),
                last_order_date=last_order_date
            )
        )

    # Sort
    if sort_by == "orders_desc":
        items.sort(key=lambda x: x.order_count, reverse=True)
    elif sort_by == "created_at_asc":
        items.sort(key=lambda x: x.created_at)
    elif sort_by == "name_asc":
        items.sort(key=lambda x: x.full_name.lower())
    else:
        items.sort(key=lambda x: x.created_at, reverse=True)

    paginated_items = items[skip : skip + limit]

    return APIResponse(
        success=True,
        message=f"Retrieved {len(paginated_items)} customers",
        data=paginated_items
    )

@router.get("/{customer_id}", response_model=APIResponse[AdminCustomerDetail])
def get_customer_detail(
    customer_id: int,
    current_admin: User = Depends(require_permission("customers.read")),
    db: Session = Depends(get_db)
):
    customer = db.query(User).filter(User.id == customer_id, User.role == "customer").first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    # Aggregate real customer relations
    addresses = db.query(Address).filter(Address.user_id == customer.id).all()
    orders = db.query(Order).filter(Order.user_id == customer.id).order_by(desc(Order.created_at)).all()
    wishlist_count = db.query(WishlistItem).filter(WishlistItem.user_id == customer.id).count()
    reviews_count = db.query(Review).filter(Review.user_id == customer.id).count()
    returns_count = db.query(Return).filter(Return.user_id == customer.id).count()
    tickets = db.query(SupportTicket).filter(SupportTicket.user_id == customer.id).order_by(desc(SupportTicket.created_at)).all()

    total_spent = sum(o.total_amount for o in orders if o.payment_status == "paid")

    recent_orders = [
        {
            "id": o.id,
            "order_number": o.order_number,
            "total_amount": round(o.total_amount, 2),
            "status": o.status,
            "payment_status": o.payment_status,
            "created_at": o.created_at.strftime("%Y-%m-%d %H:%M"),
            "items_count": len(o.items) if o.items else 0
        }
        for o in orders[:10]
    ]

    addr_list = [
        {
            "id": a.id,
            "address_type": getattr(a, "address_type", "Home"),
            "full_name": a.full_name,
            "phone": a.phone,
            "address_line1": a.address_line1,
            "address_line2": a.address_line2,
            "city": a.city,
            "state": a.state,
            "postal_code": a.postal_code,
            "is_default": a.is_default
        }
        for a in addresses
    ]

    support_list = [
        {
            "id": t.id,
            "ticket_number": t.ticket_number,
            "subject": t.subject,
            "status": t.status,
            "priority": t.priority,
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M")
        }
        for t in tickets[:5]
    ]

    detail = AdminCustomerDetail(
        id=customer.id,
        email=customer.email,
        full_name=customer.full_name,
        phone=customer.phone,
        avatar_url=customer.avatar_url,
        role=customer.role,
        is_active=customer.is_active,
        is_verified=customer.is_verified,
        created_at=customer.created_at,
        order_count=len(orders),
        total_spent=round(float(total_spent), 2),
        addresses=addr_list,
        recent_orders=recent_orders,
        wishlist_count=wishlist_count,
        reviews_count=reviews_count,
        returns_count=returns_count,
        support_tickets=support_list
    )

    return APIResponse(
        success=True,
        message="Customer details retrieved successfully",
        data=detail
    )

@router.put("/{customer_id}/status", response_model=APIResponse[AdminCustomerListItem])
def update_customer_status(
    customer_id: int,
    payload: AdminCustomerStatusUpdate,
    current_admin: User = Depends(require_permission("customers.update")),
    db: Session = Depends(get_db)
):
    customer = db.query(User).filter(User.id == customer_id, User.role == "customer").first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    if payload.is_active is not None:
        customer.is_active = payload.is_active
    if payload.is_verified is not None:
        customer.is_verified = payload.is_verified
    if payload.role is not None and payload.role in ["customer", "manager"]:
        customer.role = payload.role

    db.commit()
    db.refresh(customer)

    user_orders = db.query(Order).filter(Order.user_id == customer.id).all()
    total_spent = sum(o.total_amount for o in user_orders if o.payment_status == "paid")

    return APIResponse(
        success=True,
        message="Customer status updated successfully",
        data=AdminCustomerListItem(
            id=customer.id,
            email=customer.email,
            full_name=customer.full_name,
            phone=customer.phone,
            avatar_url=customer.avatar_url,
            role=customer.role,
            is_active=customer.is_active,
            is_verified=customer.is_verified,
            created_at=customer.created_at,
            order_count=len(user_orders),
            total_spent=round(float(total_spent), 2),
            last_order_date=None
        )
    )
