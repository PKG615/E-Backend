from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_admin as get_current_admin_user
from app.models.user import User
from app.schemas.common import APIResponse, PaginatedData
from app.schemas.reviews import (
    ReviewResponse, AdminReviewStatusUpdate,
    QuestionResponse, AdminQuestionStatusUpdate,
    AnswerCreate, AnswerResponse, AdminAnswerStatusUpdate
)
from app.services.review_service import ReviewService

router = APIRouter()

# ==========================================
# ADMIN REVIEWS MODERATION
# ==========================================

@router.get("", response_model=APIResponse[PaginatedData[ReviewResponse]])
def admin_list_reviews(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, pattern="^(all|pending|approved|rejected|hidden)$"),
    product_id: Optional[int] = None,
    rating: Optional[int] = Query(None, ge=1, le=5),
    search: Optional[str] = None,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    status_filter = None if (not status or status == "all") else status
    reviews, total = ReviewService.admin_list_reviews(
        db=db,
        page=page,
        limit=limit,
        status_filter=status_filter,
        product_id=product_id,
        rating_filter=rating,
        search=search
    )
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    return APIResponse(
        success=True,
        data=PaginatedData(
            items=reviews,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages
        )
    )


@router.put("/{review_id}/approve", response_model=APIResponse[ReviewResponse])
def admin_approve_review(
    review_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    review = ReviewService.admin_update_review_status(db=db, review_id=review_id, new_status="approved")
    return APIResponse(success=True, message="Review approved successfully", data=review)


@router.put("/{review_id}/reject", response_model=APIResponse[ReviewResponse])
def admin_reject_review(
    review_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    review = ReviewService.admin_update_review_status(db=db, review_id=review_id, new_status="rejected")
    return APIResponse(success=True, message="Review rejected", data=review)


@router.put("/{review_id}/hide", response_model=APIResponse[ReviewResponse])
def admin_hide_review(
    review_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    review = ReviewService.admin_update_review_status(db=db, review_id=review_id, new_status="hidden")
    return APIResponse(success=True, message="Review hidden from public view", data=review)


@router.put("/{review_id}/status", response_model=APIResponse[ReviewResponse])
def admin_change_review_status(
    review_id: int,
    data: AdminReviewStatusUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    if data.status not in ["pending", "approved", "rejected", "hidden"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    review = ReviewService.admin_update_review_status(db=db, review_id=review_id, new_status=data.status)
    return APIResponse(success=True, message=f"Review status updated to {data.status}", data=review)


@router.delete("/{review_id}", response_model=APIResponse[dict])
def admin_delete_review(
    review_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    result = ReviewService.delete_review(db=db, user=current_admin, review_id=review_id)
    return APIResponse(success=True, message="Review deleted successfully", data=result)


# ==========================================
# ADMIN PRODUCT Q&A MANAGEMENT
# ==========================================

questions_router = APIRouter()

@questions_router.get("", response_model=APIResponse[PaginatedData[QuestionResponse]])
def admin_list_questions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, pattern="^(all|pending|approved|rejected|hidden)$"),
    product_id: Optional[int] = None,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    status_filter = None if (not status or status == "all") else status
    questions, total = ReviewService.admin_list_questions(
        db=db,
        page=page,
        limit=limit,
        status_filter=status_filter,
        product_id=product_id
    )
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    return APIResponse(
        success=True,
        data=PaginatedData(
            items=questions,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages
        )
    )


@questions_router.put("/{question_id}/approve", response_model=APIResponse[QuestionResponse])
def admin_approve_question(
    question_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    q = ReviewService.admin_update_question_status(db=db, question_id=question_id, new_status="approved")
    return APIResponse(success=True, message="Question approved successfully", data=q)


@questions_router.put("/{question_id}/reject", response_model=APIResponse[QuestionResponse])
def admin_reject_question(
    question_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    q = ReviewService.admin_update_question_status(db=db, question_id=question_id, new_status="rejected")
    return APIResponse(success=True, message="Question rejected", data=q)


@questions_router.post("/{question_id}/answers", response_model=APIResponse[AnswerResponse], status_code=status.HTTP_201_CREATED)
def admin_answer_question(
    question_id: int,
    data: AnswerCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    answer = ReviewService.create_answer(
        db=db,
        user=current_admin,
        question_id=question_id,
        data=data
    )
    return APIResponse(success=True, message="Official seller answer posted", data=answer)


@questions_router.delete("/{question_id}", response_model=APIResponse[dict])
def admin_delete_question(
    question_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    result = ReviewService.admin_delete_question(db=db, question_id=question_id)
    return APIResponse(success=True, message=result["message"], data=result)


@questions_router.delete("/answers/{answer_id}", response_model=APIResponse[dict])
def admin_delete_answer(
    answer_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    result = ReviewService.admin_delete_answer(db=db, answer_id=answer_id)
    return APIResponse(success=True, message=result["message"], data=result)
