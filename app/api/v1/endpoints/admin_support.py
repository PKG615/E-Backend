from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.models.user import User

from app.api.v1.endpoints.auth import get_current_admin

from app.schemas.common import APIResponse

from app.schemas.account import (
    SupportTicketResponse,
    SupportTicketDetailResponse,
    SupportStatusUpdate,
    SupportMessageCreate,
    SupportMessageResponse
)
from app.services.account_service import AccountService

router = APIRouter()

@router.get("/tickets", response_model=APIResponse[Dict[str, Any]])
def list_admin_support_tickets(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Admin: View all support tickets across the platform with filtering by status, category, priority.
    """
    tickets, total = AccountService.list_admin_tickets(
        db=db,
        status_filter=status,
        category=category,
        priority=priority,
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
        message="Admin support tickets retrieved",
        data={
            "items": formatted,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )

@router.get("/tickets/{ticket_id}", response_model=APIResponse[SupportTicketDetailResponse])
def get_admin_support_ticket(
    ticket_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Admin: Get full ticket conversation history including internal notes.
    """
    ticket = AccountService.get_admin_ticket(db, ticket_id)
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
        ]
    )
    return APIResponse(
        success=True,
        message="Ticket details retrieved",
        data=detail
    )

@router.put("/tickets/{ticket_id}/status", response_model=APIResponse[SupportTicketResponse])
def update_ticket_status(
    ticket_id: int,
    payload: SupportStatusUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Admin: Change ticket workflow status (open, in_progress, waiting_for_customer, resolved, closed).
    """
    ticket = AccountService.update_admin_ticket_status(db, ticket_id, payload.status)
    resp = SupportTicketResponse.from_orm(ticket).dict()
    resp["message_count"] = len(ticket.messages)
    return APIResponse(
        success=True,
        message=f"Ticket status updated to {payload.status}",
        data=SupportTicketResponse(**resp)
    )

@router.post("/tickets/{ticket_id}/messages", response_model=APIResponse[SupportMessageResponse])
def reply_to_ticket_as_admin(
    ticket_id: int,
    payload: SupportMessageCreate,
    is_internal: bool = Query(False),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Admin: Post a reply to customer or an internal support staff note.
    """
    msg = AccountService.add_admin_message(
        db=db,
        admin_user=current_admin,
        ticket_id=ticket_id,
        message_text=payload.message,
        is_internal=is_internal
    )
    return APIResponse(
        success=True,
        message="Admin reply sent successfully",
        data=SupportMessageResponse.from_orm(msg)
    )
