from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
import random
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from fastapi import HTTPException, status

from app.models.user import User, Address
from app.models.order import Order, OrderItem
from app.models.shipment import Shipment
from app.models.returns import Return, Replacement
from app.models.wishlist import WishlistItem
from app.models.reviews import Review, ProductQuestion, ProductAnswer
from app.models.promotions import Coupon, CouponUsage
from app.models.notifications import Notification, NotificationPreference
from app.models.support import SupportTicket, SupportMessage
from app.core.security import verify_password, get_password_hash
from app.schemas.account import (
    UserProfileUpdate,
    PasswordChangeRequest,
    AccountDashboardResponse,
    NotificationPreferencesUpdate,
    SupportTicketCreate,
    SupportMessageCreate
)

class AccountService:

    # ----------------------------------------------------
    # Profile & Security Management
    # ----------------------------------------------------
    @staticmethod
    def get_profile(user: User) -> User:
        return user

    @staticmethod
    def update_profile(db: Session, user: User, data: UserProfileUpdate) -> User:
        if data.full_name is not None:
            user.full_name = data.full_name.strip()
        if data.phone is not None:
            user.phone = data.phone.strip()
        if data.avatar_url is not None:
            user.avatar_url = data.avatar_url.strip()
        
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def change_password(db: Session, user: User, data: PasswordChangeRequest) -> Dict[str, Any]:
        if not verify_password(data.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password verification failed. Please enter your correct current password."
            )
        
        if len(data.new_password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be at least 6 characters long."
            )

        if data.new_password != data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password and confirmation do not match."
            )

        user.hashed_password = get_password_hash(data.new_password)
        db.commit()

        # Send an in-app security notification
        AccountService.create_notification(
            db=db,
            user_id=user.id,
            type="security",
            title="Password Changed Successfully",
            message="The password for your account was updated. If this wasn't you, contact support immediately.",
            reference_type="account"
        )

        return {"message": "Password updated successfully"}

    # ----------------------------------------------------
    # Customer Account Dashboard Aggregation
    # ----------------------------------------------------
    @staticmethod
    def get_dashboard_summary(db: Session, user: User) -> AccountDashboardResponse:
        # Profile completion checklist
        has_name = bool(user.full_name and len(user.full_name.strip()) > 0)
        has_phone = bool(user.phone and len(user.phone.strip()) > 0)
        has_avatar = bool(user.avatar_url and len(user.avatar_url.strip()) > 0)
        is_verified = bool(user.is_verified)
        
        address_count = db.query(Address).filter(Address.user_id == user.id).count()
        has_address = address_count > 0

        completion_items = [
            {"key": "name", "label": "Full Name", "completed": has_name, "weight": 20},
            {"key": "email", "label": "Email Address", "completed": True, "weight": 20},
            {"key": "verified", "label": "Account Verified", "completed": is_verified, "weight": 20},
            {"key": "phone", "label": "Phone Number", "completed": has_phone, "weight": 15},
            {"key": "address", "label": "Delivery Address", "completed": has_address, "weight": 15},
            {"key": "avatar", "label": "Profile Picture", "completed": has_avatar, "weight": 10},
        ]
        completion_percent = sum(item["weight"] for item in completion_items if item["completed"])

        # Real PostgreSQL Query counts
        orders_count = db.query(Order).filter(Order.user_id == user.id).count()
        
        # Active shipments (orders with shipments in non-final status)
        active_shipments_count = (
            db.query(Order)
            .join(Shipment, Shipment.order_id == Order.id)
            .filter(
                Order.user_id == user.id,
                Shipment.status.in_(["pending", "manifested", "picked_up", "in_transit", "out_for_delivery"])
            )
            .count()
        )

        pending_returns_count = (
            db.query(Return)
            .filter(
                Return.user_id == user.id,
                Return.status.in_(["requested", "approved", "pickup_pending", "in_transit"])
            )
            .count()
        )

        wishlist_count = db.query(WishlistItem).filter(WishlistItem.user_id == user.id).count()
        reviews_count = db.query(Review).filter(Review.user_id == user.id).count()
        questions_count = db.query(ProductQuestion).filter(ProductQuestion.user_id == user.id).count()
        
        unread_notifications_count = (
            db.query(Notification)
            .filter(Notification.user_id == user.id, Notification.is_read == False)
            .count()
        )

        now = datetime.utcnow()
        available_coupons_count = (
            db.query(Coupon)
            .filter(
                Coupon.is_active == True,
                (Coupon.expires_at == None) | (Coupon.expires_at > now)
            )
            .count()
        )

        open_tickets_count = (
            db.query(SupportTicket)
            .filter(
                SupportTicket.user_id == user.id,
                SupportTicket.status.in_(["open", "in_progress", "waiting_for_customer"])
            )
            .count()
        )

        # Recent Orders
        recent_orders_raw = (
            db.query(Order)
            .filter(Order.user_id == user.id)
            .order_by(desc(Order.created_at))
            .limit(3)
            .all()
        )
        recent_orders = []
        for o in recent_orders_raw:
            items_preview = [
                {"id": item.id, "product_name": item.product_name, "quantity": item.quantity, "total_price": item.total_price}
                for item in o.items[:2]
            ]
            recent_orders.append({
                "id": o.id,
                "order_number": o.order_number,
                "total_amount": o.total_amount,
                "status": o.status,
                "created_at": o.created_at.isoformat(),
                "items_count": len(o.items),
                "items_preview": items_preview
            })

        # Recent Notifications
        recent_notifs_raw = (
            db.query(Notification)
            .filter(Notification.user_id == user.id)
            .order_by(desc(Notification.created_at))
            .limit(3)
            .all()
        )
        recent_notifications = [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
                "reference_type": n.reference_type,
                "reference_id": n.reference_id
            }
            for n in recent_notifs_raw
        ]

        # Open Tickets
        open_tickets_raw = (
            db.query(SupportTicket)
            .filter(SupportTicket.user_id == user.id)
            .order_by(desc(SupportTicket.updated_at))
            .limit(3)
            .all()
        )
        open_tickets = [
            {
                "id": t.id,
                "ticket_number": t.ticket_number,
                "subject": t.subject,
                "category": t.category,
                "priority": t.priority,
                "status": t.status,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
                "message_count": len(t.messages)
            }
            for t in open_tickets_raw
        ]

        return AccountDashboardResponse(
            customer_name=user.full_name or user.email.split("@")[0],
            email=user.email,
            phone=user.phone,
            avatar_url=user.avatar_url,
            role=user.role,
            member_since=user.created_at,
            profile_completion_percent=completion_percent,
            profile_completion_items=completion_items,
            stats={
                "orders_count": orders_count,
                "active_shipments_count": active_shipments_count,
                "pending_returns_count": pending_returns_count,
                "wishlist_count": wishlist_count,
                "reviews_count": reviews_count,
                "questions_count": questions_count,
                "unread_notifications_count": unread_notifications_count,
                "available_coupons_count": available_coupons_count,
                "addresses_count": address_count,
                "open_tickets_count": open_tickets_count
            },
            recent_orders=recent_orders,
            recent_notifications=recent_notifications,
            open_tickets=open_tickets
        )

    # ----------------------------------------------------
    # Notifications Management
    # ----------------------------------------------------
    @staticmethod
    def create_notification(
        db: Session,
        user_id: int,
        type: str,
        title: str,
        message: str,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None
    ) -> Notification:
        # Check customer preferences if present
        pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
        if pref and not pref.in_app_notifications:
            # Customer disabled in-app notifications
            pass

        notif = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            reference_type=reference_type,
            reference_id=reference_id,
            is_read=False
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        return notif

    @staticmethod
    def list_notifications(
        db: Session,
        user_id: int,
        is_read: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Notification], int, int]:
        query = db.query(Notification).filter(Notification.user_id == user_id)
        if is_read is not None:
            query = query.filter(Notification.is_read == is_read)
        
        total = query.count()
        unread_count = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).count()

        items = (
            query.order_by(desc(Notification.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total, unread_count

    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        return db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).count()

    @staticmethod
    def mark_notification_as_read(db: Session, user_id: int, notification_id: int) -> Notification:
        notif = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        if not notif:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
        
        if not notif.is_read:
            notif.is_read = True
            notif.read_at = datetime.utcnow()
            db.commit()
            db.refresh(notif)
        return notif

    @staticmethod
    def mark_all_notifications_as_read(db: Session, user_id: int) -> int:
        now = datetime.utcnow()
        updated_count = (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.is_read == False)
            .update({"is_read": True, "read_at": now}, synchronize_session=False)
        )
        db.commit()
        return updated_count

    @staticmethod
    def delete_notification(db: Session, user_id: int, notification_id: int) -> bool:
        notif = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        if not notif:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
        
        db.delete(notif)
        db.commit()
        return True

    @staticmethod
    def get_or_create_preferences(db: Session, user_id: int) -> NotificationPreference:
        pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
        if not pref:
            pref = NotificationPreference(
                user_id=user_id,
                order_updates=True,
                shipment_updates=True,
                return_refund_updates=True,
                promotional_updates=True,
                email_notifications=True,
                in_app_notifications=True
            )
            db.add(pref)
            db.commit()
            db.refresh(pref)
        return pref

    @staticmethod
    def update_preferences(db: Session, user_id: int, data: NotificationPreferencesUpdate) -> NotificationPreference:
        pref = AccountService.get_or_create_preferences(db, user_id)
        if data.order_updates is not None:
            pref.order_updates = data.order_updates
        if data.shipment_updates is not None:
            pref.shipment_updates = data.shipment_updates
        if data.return_refund_updates is not None:
            pref.return_refund_updates = data.return_refund_updates
        if data.promotional_updates is not None:
            pref.promotional_updates = data.promotional_updates
        if data.email_notifications is not None:
            pref.email_notifications = data.email_notifications
        if data.in_app_notifications is not None:
            pref.in_app_notifications = data.in_app_notifications

        db.commit()
        db.refresh(pref)
        return pref

    # ----------------------------------------------------
    # Support Tickets & Messages Management
    # ----------------------------------------------------
    @staticmethod
    def create_support_ticket(db: Session, user: User, data: SupportTicketCreate) -> SupportTicket:
        year = datetime.utcnow().year
        rand_suffix = random.randint(1000, 9999)
        ticket_number = f"TKT-{year}-{rand_suffix}"

        # Ensure unique ticket number
        while db.query(SupportTicket).filter(SupportTicket.ticket_number == ticket_number).first():
            rand_suffix = random.randint(1000, 9999)
            ticket_number = f"TKT-{year}-{rand_suffix}"

        ticket = SupportTicket(
            ticket_number=ticket_number,
            user_id=user.id,
            subject=data.subject.strip(),
            category=data.category,
            priority=data.priority,
            status="open",
            description=data.description.strip()
        )
        db.add(ticket)
        db.flush()

        # Add initial conversation message
        initial_msg = SupportMessage(
            ticket_id=ticket.id,
            sender_user_id=user.id,
            sender_role="customer",
            sender_name=user.full_name or user.email,
            message=data.description.strip(),
            is_internal=False
        )
        db.add(initial_msg)
        db.commit()
        db.refresh(ticket)

        # Notify customer
        AccountService.create_notification(
            db=db,
            user_id=user.id,
            type="support",
            title=f"Support Ticket Created: {ticket.ticket_number}",
            message=f"Your ticket '{ticket.subject}' has been submitted. Our support team will assist you shortly.",
            reference_type="ticket",
            reference_id=str(ticket.id)
        )

        return ticket

    @staticmethod
    def list_user_tickets(
        db: Session,
        user_id: int,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[SupportTicket], int]:
        query = db.query(SupportTicket).filter(SupportTicket.user_id == user_id)
        if status_filter and status_filter != "all":
            query = query.filter(SupportTicket.status == status_filter)
        
        total = query.count()
        tickets = (
            query.order_by(desc(SupportTicket.updated_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return tickets, total

    @staticmethod
    def get_user_ticket(db: Session, user_id: int, ticket_id: int) -> SupportTicket:
        ticket = db.query(SupportTicket).filter(
            SupportTicket.id == ticket_id,
            SupportTicket.user_id == user_id
        ).first()
        if not ticket:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found")
        return ticket

    @staticmethod
    def add_user_message(db: Session, user: User, ticket_id: int, message_text: str) -> SupportMessage:
        ticket = AccountService.get_user_ticket(db, user.id, ticket_id)
        if ticket.status == "closed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This ticket has been closed. Please create a new support ticket if you need further help."
            )

        msg = SupportMessage(
            ticket_id=ticket.id,
            sender_user_id=user.id,
            sender_role="customer",
            sender_name=user.full_name or user.email,
            message=message_text.strip(),
            is_internal=False
        )
        db.add(msg)
        
        # If it was waiting for customer or resolved, update to open or in_progress
        if ticket.status in ["waiting_for_customer", "resolved"]:
            ticket.status = "in_progress"
        ticket.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def close_user_ticket(db: Session, user: User, ticket_id: int) -> SupportTicket:
        ticket = AccountService.get_user_ticket(db, user.id, ticket_id)
        ticket.status = "closed"
        ticket.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(ticket)
        return ticket

    # ----------------------------------------------------
    # Admin Support Management
    # ----------------------------------------------------
    @staticmethod
    def list_admin_tickets(
        db: Session,
        status_filter: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[SupportTicket], int]:
        query = db.query(SupportTicket)
        if status_filter and status_filter != "all":
            query = query.filter(SupportTicket.status == status_filter)
        if category and category != "all":
            query = query.filter(SupportTicket.category == category)
        if priority and priority != "all":
            query = query.filter(SupportTicket.priority == priority)

        total = query.count()
        tickets = (
            query.order_by(desc(SupportTicket.updated_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return tickets, total

    @staticmethod
    def get_admin_ticket(db: Session, ticket_id: int) -> SupportTicket:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found")
        return ticket

    @staticmethod
    def update_admin_ticket_status(db: Session, ticket_id: int, new_status: str) -> SupportTicket:
        ticket = AccountService.get_admin_ticket(db, ticket_id)
        ticket.status = new_status
        ticket.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(ticket)

        # Notify customer of status change
        AccountService.create_notification(
            db=db,
            user_id=ticket.user_id,
            type="support",
            title=f"Ticket #{ticket.ticket_number} status updated to {new_status.replace('_', ' ').title()}",
            message=f"Your support ticket has been updated to '{new_status.replace('_', ' ').title()}'.",
            reference_type="ticket",
            reference_id=str(ticket.id)
        )
        return ticket

    @staticmethod
    def add_admin_message(
        db: Session,
        admin_user: User,
        ticket_id: int,
        message_text: str,
        is_internal: bool = False
    ) -> SupportMessage:
        ticket = AccountService.get_admin_ticket(db, ticket_id)

        msg = SupportMessage(
            ticket_id=ticket.id,
            sender_user_id=admin_user.id,
            sender_role="support",
            sender_name=f"Support ({admin_user.full_name or 'Agent'})",
            message=message_text.strip(),
            is_internal=is_internal
        )
        db.add(msg)

        if not is_internal:
            ticket.status = "waiting_for_customer"
            ticket.updated_at = datetime.utcnow()
            
            # Notify customer
            AccountService.create_notification(
                db=db,
                user_id=ticket.user_id,
                type="support",
                title=f"New response on Ticket #{ticket.ticket_number}",
                message=f"Our support team responded: \"{message_text[:80]}...\"",
                reference_type="ticket",
                reference_id=str(ticket.id)
            )

        db.commit()
        db.refresh(msg)
        return msg

    # ----------------------------------------------------
    # Customer Questions & Answers Listing
    # ----------------------------------------------------
    @staticmethod
    def list_user_questions(
        db: Session,
        user_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        query = db.query(ProductQuestion).filter(ProductQuestion.user_id == user_id)
        total = query.count()
        questions = (
            query.order_by(desc(ProductQuestion.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        
        result = []
        for q in questions:
            product = q.product
            primary_img = None
            if product and product.images:
                primary_img = product.images[0].image_url

            answers = [
                {
                    "id": a.id,
                    "answer": a.answer,
                    "is_seller_answer": a.is_seller_answer,
                    "created_at": a.created_at.isoformat(),
                    "status": a.status
                }
                for a in q.answers
                if a.status == "approved" or a.user_id == user_id
            ]

            result.append({
                "id": q.id,
                "product_id": q.product_id,
                "product_name": product.name if product else "Product",
                "product_slug": product.slug if product else "",
                "product_image": primary_img,
                "question": q.question,
                "status": q.status,
                "created_at": q.created_at.isoformat(),
                "answers": answers
            })

        return result, total

    @staticmethod
    def delete_user_question(db: Session, user_id: int, question_id: int) -> bool:
        q = db.query(ProductQuestion).filter(
            ProductQuestion.id == question_id,
            ProductQuestion.user_id == user_id
        ).first()
        if not q:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
        db.delete(q)
        db.commit()
        return True

    # ----------------------------------------------------
    # Available Coupons Listing for Customer
    # ----------------------------------------------------
    @staticmethod
    def list_available_coupons(db: Session, user_id: int) -> List[Dict[str, Any]]:
        now = datetime.utcnow()
        coupons = (
            db.query(Coupon)
            .filter(
                Coupon.is_active == True,
                (Coupon.expires_at == None) | (Coupon.expires_at > now)
            )
            .order_by(Coupon.id.asc())
            .all()
        )

        result = []
        for c in coupons:
            # Check user usage
            usage_count = (
                db.query(CouponUsage)
                .filter(CouponUsage.coupon_id == c.id, CouponUsage.user_id == user_id)
                .count()
            )
            is_usable = True
            if c.usage_limit and c.used_count >= c.usage_limit:
                is_usable = False
            if usage_count >= c.per_customer_limit:
                is_usable = False

            result.append({
                "id": c.id,
                "code": c.code,
                "name": c.name,
                "description": c.description,
                "discount_type": c.discount_type,
                "discount_value": c.discount_value,
                "max_discount_amount": c.max_discount_amount,
                "minimum_cart_value": c.minimum_cart_value,
                "maximum_cart_value": c.maximum_cart_value,
                "per_customer_limit": c.per_customer_limit,
                "user_used_count": usage_count,
                "is_usable": is_usable,
                "expires_at": c.expires_at.isoformat() if c.expires_at else None
            })

        return result
