from typing import Optional, List, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user, get_current_user_optional
from app.models.user import User
from app.schemas.common import APIResponse, PaginatedData
from app.schemas.reviews import (
    ReviewCreate, ReviewUpdate, ReviewResponse, ReviewAggregateResponse,
    ReviewEligibilityResponse, HelpfulVoteResponse,
    QuestionCreate, QuestionUpdate, AnswerCreate, AnswerResponse, QuestionResponse
)
from app.services.review_service import ReviewService

router = APIRouter()

# ==========================================
# PUBLIC & AUTHENTICATED PRODUCT REVIEWS
# ==========================================

@router.get("/products/{slug_or_id}/reviews", response_model=APIResponse[PaginatedData[ReviewResponse]])
def get_product_reviews(
    slug_or_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    sort: str = Query("newest", pattern="^(newest|oldest|highest_rating|lowest_rating|most_helpful)$"),
    rating: Optional[int] = Query(None, ge=1, le=5),
    verified_only: bool = Query(False),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    current_user_id = current_user.id if current_user else None
    reviews, total = ReviewService.get_product_reviews(
        db=db,
        product_id_or_slug=slug_or_id,
        page=page,
        limit=limit,
        sort=sort,
        rating_filter=rating,
        verified_only=verified_only,
        current_user_id=current_user_id
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


@router.get("/products/{slug_or_id}/reviews/aggregate", response_model=APIResponse[ReviewAggregateResponse])
def get_product_review_aggregate(
    slug_or_id: str,
    db: Session = Depends(get_db)
):
    aggregate = ReviewService.get_product_aggregate(db=db, product_id_or_slug=slug_or_id)
    return APIResponse(success=True, data=aggregate)


@router.get("/products/{slug_or_id}/reviews/eligibility", response_model=APIResponse[ReviewEligibilityResponse])
def check_review_eligibility(
    slug_or_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    eligibility = ReviewService.get_review_eligibility(
        db=db,
        user_id=current_user.id,
        product_id_or_slug=slug_or_id
    )
    return APIResponse(success=True, data=eligibility)


@router.post("/products/{slug_or_id}/reviews", response_model=APIResponse[ReviewResponse], status_code=status.HTTP_201_CREATED)
def submit_product_review(
    slug_or_id: str,
    data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    review = ReviewService.create_review(
        db=db,
        user=current_user,
        product_id_or_slug=slug_or_id,
        data=data
    )
    return APIResponse(success=True, message="Review submitted successfully", data=review)


# ==========================================
# HELPFUL VOTES
# ==========================================

@router.post("/products/reviews/{review_id}/helpful", response_model=APIResponse[HelpfulVoteResponse])
def vote_review_helpful(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    result = ReviewService.vote_helpful(db=db, user=current_user, review_id=review_id)
    return APIResponse(success=True, message=result.message, data=result)


@router.delete("/products/reviews/{review_id}/helpful", response_model=APIResponse[HelpfulVoteResponse])
def remove_helpful_vote(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    result = ReviewService.vote_helpful(db=db, user=current_user, review_id=review_id)
    return APIResponse(success=True, message=result.message, data=result)


# ==========================================
# PRODUCT QUESTIONS & ANSWERS (Q&A)
# ==========================================

@router.get("/products/{slug_or_id}/questions", response_model=APIResponse[PaginatedData[QuestionResponse]])
def get_product_questions(
    slug_or_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    current_user_id = current_user.id if current_user else None
    questions, total = ReviewService.get_product_questions(
        db=db,
        product_id_or_slug=slug_or_id,
        page=page,
        limit=limit,
        current_user_id=current_user_id
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


@router.post("/products/{slug_or_id}/questions", response_model=APIResponse[QuestionResponse], status_code=status.HTTP_201_CREATED)
def ask_product_question(
    slug_or_id: str,
    data: QuestionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    question = ReviewService.create_question(
        db=db,
        user=current_user,
        product_id_or_slug=slug_or_id,
        data=data
    )
    return APIResponse(success=True, message="Question submitted successfully", data=question)


@router.post("/products/questions/{question_id}/answers", response_model=APIResponse[AnswerResponse], status_code=status.HTTP_201_CREATED)
def answer_product_question(
    question_id: int,
    data: AnswerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    answer = ReviewService.create_answer(
        db=db,
        user=current_user,
        question_id=question_id,
        data=data
    )
    return APIResponse(success=True, message="Answer posted successfully", data=answer)


# ==========================================
# CUSTOMER ME REVIEWS (ACCOUNT / DASHBOARD)
# ==========================================

@router.get("/me/reviews", response_model=APIResponse[PaginatedData[ReviewResponse]])
def get_my_reviews(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    reviews, total = ReviewService.get_user_reviews(
        db=db,
        user_id=current_user.id,
        page=page,
        limit=limit
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


@router.put("/me/reviews/{review_id}", response_model=APIResponse[ReviewResponse])
def update_my_review(
    review_id: int,
    data: ReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    updated = ReviewService.update_review(
        db=db,
        user=current_user,
        review_id=review_id,
        data=data
    )
    return APIResponse(success=True, message="Review updated successfully", data=updated)


@router.delete("/me/reviews/{review_id}", response_model=APIResponse[dict])
def delete_my_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    result = ReviewService.delete_review(
        db=db,
        user=current_user,
        review_id=review_id
    )
    return APIResponse(success=True, message=result["message"], data=result)
