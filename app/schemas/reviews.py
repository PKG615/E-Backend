from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# ==========================================
# REVIEW IMAGES & VOTES
# ==========================================

class ReviewImageResponse(BaseModel):
    id: int
    image_url: str
    alt_text: Optional[str] = None
    sort_order: int = 0

    model_config = ConfigDict(from_attributes=True)


class HelpfulVoteResponse(BaseModel):
    review_id: int
    helpful_count: int
    voted: bool
    message: str


# ==========================================
# REVIEW CREATE / UPDATE / RESPONSE
# ==========================================

class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Rating score from 1 to 5 stars")
    title: Optional[str] = Field(None, max_length=255, description="Review headline")
    body: str = Field(..., min_length=3, max_length=5000, description="Review text content")
    variant_id: Optional[int] = None
    images: Optional[List[str]] = Field(default_factory=list, description="Optional array of image URLs")


class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = Field(None, max_length=255)
    body: Optional[str] = Field(None, min_length=3, max_length=5000)
    images: Optional[List[str]] = None


class ReviewResponse(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    product_slug: Optional[str] = None
    product_image: Optional[str] = None
    variant_id: Optional[int] = None
    variant_title: Optional[str] = None
    user_id: int
    user_name: str
    rating: int
    title: Optional[str] = None
    body: str
    status: str
    is_verified_purchase: bool
    order_id: Optional[int] = None
    helpful_count: int = 0
    user_has_voted_helpful: bool = False
    images: List[ReviewImageResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewAggregateResponse(BaseModel):
    average_rating: float = 0.0
    review_count: int = 0
    rating_distribution: Dict[str, int] = {
        "5": 0,
        "4": 0,
        "3": 0,
        "2": 0,
        "1": 0
    }
    verified_purchases_count: int = 0
    with_images_count: int = 0


class ReviewEligibilityResponse(BaseModel):
    can_review: bool
    has_purchased: bool
    is_verified_eligible: bool
    existing_review_id: Optional[int] = None
    reason: Optional[str] = None


# ==========================================
# PRODUCT Q&A SCHEMAS
# ==========================================

class QuestionCreate(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000, description="Customer question")
    variant_id: Optional[int] = None


class QuestionUpdate(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000)


class AnswerCreate(BaseModel):
    answer: str = Field(..., min_length=2, max_length=2000, description="Answer text")


class AnswerResponse(BaseModel):
    id: int
    question_id: int
    user_id: Optional[int] = None
    user_name: str
    answer: str
    is_seller_answer: bool
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuestionResponse(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    product_slug: Optional[str] = None
    variant_id: Optional[int] = None
    variant_title: Optional[str] = None
    user_id: int
    user_name: str
    question: str
    status: str
    answer_count: int = 0
    answers: List[AnswerResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# ADMIN MODERATION SCHEMAS
# ==========================================

class AdminReviewStatusUpdate(BaseModel):
    status: str = Field(..., description="'approved', 'rejected', 'hidden', or 'pending'")
    moderation_note: Optional[str] = None


class AdminQuestionStatusUpdate(BaseModel):
    status: str = Field(..., description="'approved', 'rejected', 'hidden', or 'pending'")


class AdminAnswerStatusUpdate(BaseModel):
    status: str = Field(..., description="'approved', 'rejected', 'hidden', or 'pending'")
