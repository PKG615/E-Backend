from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.common import APIResponse
from app.schemas.account import (
    UserProfileResponse,
    UserProfileUpdate,
    PasswordChangeRequest,
    AccountDashboardResponse,
    NotificationResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    SupportTicketResponse,
    SupportTicketDetailResponse,
    SupportTicketCreate,
    SupportMessageResponse,
    SupportMessageCreate
)
from app.services.account_service import AccountService

router = APIRouter()

# ----------------------------------------------------
# Profile & Dashboard
# ----------------------------------------------------

@router.get("/profile", response_model=APIResponse[UserProfileResponse])
def get_my_profile(current_user: User = Depends(get_current_user)):
    """
    Retrieve current customer profile details.
    """
    return APIResponse(
        success=True,
        message="Profile retrieved",
        data=UserProfileResponse.from_orm(current_user)
    )

@router.put("/profile", response_model=APIResponse[UserProfileResponse])
def update_my_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update customer personal details (full name, phone, avatar URL).
    """
    updated_user = AccountService.update_profile(db, current_user, payload)
    return APIResponse(
        success=True,
        message="Profile updated successfully",
        data=UserProfileResponse.from_orm(updated_user)
    )

@router.put("/password", response_model=APIResponse[Dict[str, Any]])
def change_my_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update account password after verifying current credentials.
    """
    result = AccountService.change_password(db, current_user, payload)
    return APIResponse(
        success=True,
        message="Password updated successfully",
        data=result
    )

@router.get("/dashboard", response_model=APIResponse[AccountDashboardResponse])
def get_account_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Aggregated Account Dashboard with real-time statistics, active shipments,
    pending returns, unread notifications, wishlist count, and recent orders.
    """
    dashboard_data = AccountService.get_dashboard_summary(db, current_user)
    return APIResponse(
        success=True,
        message="Account dashboard loaded",
        data=dashboard_data
    )

# ----------------------------------------------------
# Notifications
# ----------------------------------------------------

@router.get("/notifications", response_model=APIResponse[Dict[str, Any]])
def list_notifications(
    is_read: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get customer notifications with unread count and pagination.
    """
    items, total, unread_count = AccountService.list_notifications(
        db=db,
        user_id=current_user.id,
        is_read=is_read,
        page=page,
        page_size=page_size
    )
    return APIResponse(
        success=True,
        message="Notifications retrieved",
        data={
            "items": [NotificationResponse.from_orm(n).dict() for n in items],
            "total": total,
            "unread_count": unread_count,
            "page": page,
            "page_size": page_size
        }
    )

@router.get("/notifications/unread-count", response_model=APIResponse[Dict[str, int]])
def get_notifications_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Quick endpoint for header notification badge.
    """
    unread = AccountService.get_unread_count(db, current_user.id)
    return APIResponse(
        success=True,
        message="Unread count retrieved",
        data={"unread_count": unread}
    )

@router.put("/notifications/{notification_id}/read", response_model=APIResponse[NotificationResponse])
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a specific notification as read.
    """
    notif = AccountService.mark_notification_as_read(db, current_user.id, notification_id)
    return APIResponse(
        success=True,
        message="Notification marked as read",
        data=NotificationResponse.from_orm(notif)
    )

@router.put("/notifications/read-all", response_model=APIResponse[Dict[str, int]])
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark all unread notifications for this customer as read.
    """
    count = AccountService.mark_all_notifications_as_read(db, current_user.id)
    return APIResponse(
        success=True,
        message=f"{count} notifications marked as read",
        data={"updated_count": count}
    )

@router.delete("/notifications/{notification_id}", response_model=APIResponse[Dict[str, str]])
def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a notification from inbox.
    """
    AccountService.delete_notification(db, current_user.id, notification_id)
    return APIResponse(
        success=True,
        message="Notification deleted successfully",
        data={"message": "Deleted"}
    )

@router.get("/notifications/preferences", response_model=APIResponse[NotificationPreferencesResponse])
def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get customer notification channel & topic preferences.
    """
    pref = AccountService.get_or_create_preferences(db, current_user.id)
    return APIResponse(
        success=True,
        message="Preferences retrieved",
        data=NotificationPreferencesResponse.from_orm(pref)
    )

@router.put("/notifications/preferences", response_model=APIResponse[NotificationPreferencesResponse])
def update_notification_preferences(
    payload: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update customer notification preferences.
    """
    pref = AccountService.update_preferences(db, current_user.id, payload)
    return APIResponse(
        success=True,
        message="Preferences updated successfully",
        data=NotificationPreferencesResponse.from_orm(pref)
    )

# ----------------------------------------------------
# Support Tickets & Messages
# ----------------------------------------------------

@router.get("/support/tickets", response_model=APIResponse[Dict[str, Any]])
def list_support_tickets(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List support tickets created by the authenticated customer.
    """
    tickets, total = AccountService.list_user_tickets(
        db=db,
        user_id=current_user.id,
        status_filter=status,
        page=page,
        page_size=page_size
    )
    formatted = []
    for t in tickets:
        item = SupportTicketResponse.from_orm(t).dict()
        item["message_count"] = len(t.messages)
        formatted.append(item)

    return APIResponse(
        success=True,
        message="Support tickets retrieved",
        data={
            "items": formatted,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )

@router.post("/support/tickets", response_model=APIResponse[SupportTicketResponse], status_code=status.HTTP_201_CREATED)
def create_support_ticket(
    payload: SupportTicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new support ticket with subject, category, priority, and description.
    """
    ticket = AccountService.create_support_ticket(db, current_user, payload)
    resp = SupportTicketResponse.from_orm(ticket).dict()
    resp["message_count"] = len(ticket.messages)
    return APIResponse(
        success=True,
        message="Support ticket created successfully",
        data=SupportTicketResponse(**resp)
    )

@router.get("/support/tickets/{ticket_id}", response_model=APIResponse[SupportTicketDetailResponse])
def get_support_ticket_detail(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get support ticket details and conversation message thread.
    """
    ticket = AccountService.get_user_ticket(db, current_user.id, ticket_id)
    detail = SupportTicketDetailResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        user_id=ticket.user_id,
        customer_name=ticket.user.full_name or ticket.user.email,
        customer_email=ticket.user.email,
        subject=ticket.subject,
        category=ticket.category,
        priority=ticket.priority,
        status=ticket.status,
        description=ticket.description,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        messages=[
            SupportMessageResponse.from_orm(m)
            for m in ticket.messages
            if not m.is_internal
        ]
    )
    return APIResponse(
        success=True,
        message="Ticket details retrieved",
        data=detail
    )

@router.post("/support/tickets/{ticket_id}/messages", response_model=APIResponse[SupportMessageResponse])
def reply_to_support_ticket(
    ticket_id: int,
    payload: SupportMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a message/reply to an active customer support ticket.
    """
    msg = AccountService.add_user_message(db, current_user, ticket_id, payload.message)
    return APIResponse(
        success=True,
        message="Message sent successfully",
        data=SupportMessageResponse.from_orm(msg)
    )

@router.put("/support/tickets/{ticket_id}/close", response_model=APIResponse[SupportTicketResponse])
def close_support_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Close support ticket when resolved.
    """
    ticket = AccountService.close_user_ticket(db, current_user, ticket_id)
    resp = SupportTicketResponse.from_orm(ticket).dict()
    resp["message_count"] = len(ticket.messages)
    return APIResponse(
        success=True,
        message="Support ticket closed",
        data=SupportTicketResponse(**resp)
    )

# ----------------------------------------------------
# Customer Questions & Answers
# ----------------------------------------------------

@router.get("/questions", response_model=APIResponse[Dict[str, Any]])
def list_my_questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List product questions submitted by this customer with their seller/community answers.
    """
    items, total = AccountService.list_user_questions(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size
    )
    return APIResponse(
        success=True,
        message="Customer questions retrieved",
        data={
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )

@router.delete("/questions/{question_id}", response_model=APIResponse[Dict[str, str]])
def delete_my_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a question asked by this customer.
    """
    AccountService.delete_user_question(db, current_user.id, question_id)
    return APIResponse(
        success=True,
        message="Question deleted successfully",
        data={"message": "Deleted"}
    )

# ----------------------------------------------------
# Customer Coupons & Offers
# ----------------------------------------------------

@router.get("/coupons", response_model=APIResponse[List[Dict[str, Any]]])
def list_available_coupons(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List available active coupons with customer usage eligibility.
    """
    coupons = AccountService.list_available_coupons(db, current_user.id)
    return APIResponse(
        success=True,
        message=f"{len(coupons)} coupons retrieved",
        data=coupons
    )
