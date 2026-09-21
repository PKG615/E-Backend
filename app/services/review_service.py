from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, asc, and_, or_
from fastapi import HTTPException, status

from app.models.reviews import Review, ReviewImage, ReviewHelpfulVote, ProductQuestion, ProductAnswer
from app.models.product import Product, ProductVariant
from app.models.order import Order, OrderItem
from app.models.user import User
from app.schemas.reviews import (
    ReviewCreate, ReviewUpdate, ReviewResponse, ReviewImageResponse,
    ReviewAggregateResponse, ReviewEligibilityResponse, HelpfulVoteResponse,
    QuestionCreate, QuestionUpdate, AnswerCreate, AnswerResponse, QuestionResponse
)

class ReviewService:

    @staticmethod
    def check_purchase_eligibility(db: Session, user_id: int, product_id: int, variant_id: Optional[int] = None) -> Tuple[bool, Optional[int], Optional[int]]:
        """
        Check whether the given user has purchased the specified product in a valid completed/delivered/paid order.
        Returns: (is_eligible, order_id, order_item_id)
        """
        query = (
            db.query(OrderItem)
            .join(Order, OrderItem.order_id == Order.id)
            .filter(
                Order.user_id == user_id,
                OrderItem.product_id == product_id,
                or_(
                    Order.status.in_(["delivered", "completed", "shipped", "confirmed", "processing"]),
                    Order.payment_status == "paid"
                )
            )
        )
        if variant_id:
            variant_match = query.filter(OrderItem.variant_id == variant_id).first()
            if variant_match:
                return True, variant_match.order_id, variant_match.id

        order_item = query.order_by(desc(Order.created_at)).first()
        if order_item:
            return True, order_item.order_id, order_item.id
        return False, None, None

    @classmethod
    def get_review_eligibility(cls, db: Session, user_id: int, product_id_or_slug: Any) -> ReviewEligibilityResponse:
        # Resolve product
        product = cls._resolve_product(db, product_id_or_slug)
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        # Check existing review
        existing_review = db.query(Review).filter(
            Review.product_id == product.id,
            Review.user_id == user_id
        ).first()

        has_purchased, order_id, _ = cls.check_purchase_eligibility(db, user_id, product.id)

        if existing_review:
            return ReviewEligibilityResponse(
                can_review=False,
                has_purchased=has_purchased,
                is_verified_eligible=has_purchased,
                existing_review_id=existing_review.id,
                reason="You have already submitted a review for this product."
            )

        return ReviewEligibilityResponse(
            can_review=True,
            has_purchased=has_purchased,
            is_verified_eligible=has_purchased,
            existing_review_id=None,
            reason=None if has_purchased else "You have not purchased this item. Your review will be unverified."
        )

    @classmethod
    def create_review(cls, db: Session, user: User, product_id_or_slug: Any, data: ReviewCreate) -> ReviewResponse:
        product = cls._resolve_product(db, product_id_or_slug)
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        # Prevent duplicate reviews per user per product
        existing = db.query(Review).filter(
            Review.product_id == product.id,
            Review.user_id == user.id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already reviewed this product. Please update your existing review."
            )

        # Backend-enforced Verified Purchase check
        is_verified, order_id, order_item_id = cls.check_purchase_eligibility(
            db, user.id, product.id, data.variant_id
        )

        # Clean text
        clean_title = data.title.strip() if data.title else None
        clean_body = data.body.strip()

        # By default, reviews are 'approved' so users can see feedback, or can be moderated by admin
        review = Review(
            product_id=product.id,
            variant_id=data.variant_id,
            user_id=user.id,
            order_id=order_id,
            order_item_id=order_item_id,
            rating=data.rating,
            title=clean_title,
            comment=clean_body,
            body=clean_body,
            is_approved=True,
            status="approved",
            is_verified_purchase=is_verified
        )
        db.add(review)
        db.flush()

        # Handle review images
        if data.images:
            for idx, img_url in enumerate(data.images[:5]): # cap at 5 images
                if img_url and img_url.strip():
                    img = ReviewImage(
                        review_id=review.id,
                        image_url=img_url.strip(),
                        sort_order=idx
                    )
                    db.add(img)

        db.commit()
        db.refresh(review)
        return cls._format_review_response(review, current_user_id=user.id)

    @classmethod
    def update_review(cls, db: Session, user: User, review_id: int, data: ReviewUpdate) -> ReviewResponse:
        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

        # Authorization: user must own review unless admin
        if review.user_id != user.id and user.role not in ["admin", "manager"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit this review")

        if data.rating is not None:
            review.rating = data.rating
        if data.title is not None:
            review.title = data.title.strip() if data.title else None
        if data.body is not None:
            review.body = data.body.strip()
            review.comment = data.body.strip()

        if data.images is not None:
            # Replace images
            db.query(ReviewImage).filter(ReviewImage.review_id == review.id).delete()
            for idx, img_url in enumerate(data.images[:5]):
                if img_url and img_url.strip():
                    img = ReviewImage(
                        review_id=review.id,
                        image_url=img_url.strip(),
                        sort_order=idx
                    )
                    db.add(img)

        db.commit()
        db.refresh(review)
        return cls._format_review_response(review, current_user_id=user.id)

    @classmethod
    def delete_review(cls, db: Session, user: User, review_id: int) -> Dict[str, str]:
        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

        if review.user_id != user.id and user.role not in ["admin", "manager"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this review")

        db.delete(review)
        db.commit()
        return {"message": "Review deleted successfully"}

    @classmethod
    def get_product_reviews(
        cls,
        db: Session,
        product_id_or_slug: Any,
        page: int = 1,
        limit: int = 10,
        sort: str = "newest",
        rating_filter: Optional[int] = None,
        verified_only: bool = False,
        current_user_id: Optional[int] = None
    ) -> Tuple[List[ReviewResponse], int]:
        product = cls._resolve_product(db, product_id_or_slug)
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        # Base query for approved reviews
        query = db.query(Review).filter(
            Review.product_id == product.id,
            or_(
                Review.status == "approved",
                Review.user_id == current_user_id if current_user_id else False
            )
        )

        if rating_filter and 1 <= rating_filter <= 5:
            query = query.filter(Review.rating == rating_filter)

        if verified_only:
            query = query.filter(Review.is_verified_purchase == True)

        total = query.count()

        # Sorting
        if sort == "oldest":
            query = query.order_by(asc(Review.created_at))
        elif sort == "highest_rating":
            query = query.order_by(desc(Review.rating), desc(Review.created_at))
        elif sort == "lowest_rating":
            query = query.order_by(asc(Review.rating), desc(Review.created_at))
        elif sort == "most_helpful":
            # Count helpful votes subquery
            helpful_sub = (
                db.query(
                    ReviewHelpfulVote.review_id,
                    func.count(ReviewHelpfulVote.id).label("vote_cnt")
                )
                .group_by(ReviewHelpfulVote.review_id)
                .subquery()
            )
            query = query.outerjoin(helpful_sub, Review.id == helpful_sub.c.review_id).order_by(
                desc(func.coalesce(helpful_sub.c.vote_cnt, 0)),
                desc(Review.created_at)
            )
        else: # default: newest
            query = query.order_by(desc(Review.created_at))

        offset = (page - 1) * limit
        reviews = query.offset(offset).limit(limit).all()

        formatted = [
            cls._format_review_response(r, current_user_id=current_user_id)
            for r in reviews
        ]
        return formatted, total

    @classmethod
    def get_product_aggregate(cls, db: Session, product_id_or_slug: Any) -> ReviewAggregateResponse:
        product = cls._resolve_product(db, product_id_or_slug)
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        # Aggregate only approved reviews
        agg_result = (
            db.query(
                func.count(Review.id).label("total_count"),
                func.avg(Review.rating).label("avg_rating")
            )
            .filter(
                Review.product_id == product.id,
                Review.status == "approved"
            )
            .first()
        )

        total_count = agg_result.total_count if agg_result else 0
        avg_rating = round(float(agg_result.avg_rating), 1) if agg_result and agg_result.avg_rating else 0.0

        # Rating distribution
        distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
        dist_rows = (
            db.query(Review.rating, func.count(Review.id))
            .filter(Review.product_id == product.id, Review.status == "approved")
            .group_by(Review.rating)
            .all()
        )
        for r_val, r_cnt in dist_rows:
            distribution[str(r_val)] = r_cnt

        verified_cnt = (
            db.query(func.count(Review.id))
            .filter(
                Review.product_id == product.id,
                Review.status == "approved",
                Review.is_verified_purchase == True
            )
            .scalar() or 0
        )

        with_images_cnt = (
            db.query(func.count(func.distinct(Review.id)))
            .join(ReviewImage, Review.id == ReviewImage.review_id)
            .filter(
                Review.product_id == product.id,
                Review.status == "approved"
            )
            .scalar() or 0
        )

        return ReviewAggregateResponse(
            average_rating=avg_rating,
            review_count=total_count,
            rating_distribution=distribution,
            verified_purchases_count=verified_cnt,
            with_images_count=with_images_cnt
        )

    @classmethod
    def vote_helpful(cls, db: Session, user: User, review_id: int) -> HelpfulVoteResponse:
        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

        if review.user_id == user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot vote for your own review")

        existing = db.query(ReviewHelpfulVote).filter(
            ReviewHelpfulVote.review_id == review_id,
            ReviewHelpfulVote.user_id == user.id
        ).first()

        if existing:
            # Toggle off
            db.delete(existing)
            db.commit()
            count = db.query(func.count(ReviewHelpfulVote.id)).filter(ReviewHelpfulVote.review_id == review_id).scalar() or 0
            return HelpfulVoteResponse(review_id=review_id, helpful_count=count, voted=False, message="Vote removed")
        else:
            vote = ReviewHelpfulVote(review_id=review_id, user_id=user.id)
            db.add(vote)
            db.commit()
            count = db.query(func.count(ReviewHelpfulVote.id)).filter(ReviewHelpfulVote.review_id == review_id).scalar() or 0
            return HelpfulVoteResponse(review_id=review_id, helpful_count=count, voted=True, message="Marked as helpful")

    @classmethod
    def get_user_reviews(cls, db: Session, user_id: int, page: int = 1, limit: int = 20) -> Tuple[List[ReviewResponse], int]:
        query = db.query(Review).filter(Review.user_id == user_id).order_by(desc(Review.created_at))
        total = query.count()
        offset = (page - 1) * limit
        reviews = query.offset(offset).limit(limit).all()
        return [cls._format_review_response(r, current_user_id=user_id) for r in reviews], total

    @classmethod
    def admin_list_reviews(
        cls,
        db: Session,
        page: int = 1,
        limit: int = 20,
        status_filter: Optional[str] = None,
        product_id: Optional[int] = None,
        rating_filter: Optional[int] = None,
        search: Optional[str] = None
    ) -> Tuple[List[ReviewResponse], int]:
        query = db.query(Review)

        if status_filter:
            query = query.filter(Review.status == status_filter)
        if product_id:
            query = query.filter(Review.product_id == product_id)
        if rating_filter:
            query = query.filter(Review.rating == rating_filter)
        if search:
            query = query.filter(
                or_(
                    Review.title.ilike(f"%{search}%"),
                    Review.body.ilike(f"%{search}%")
                )
            )

        total = query.count()
        offset = (page - 1) * limit
        reviews = query.order_by(desc(Review.created_at)).offset(offset).limit(limit).all()
        return [cls._format_review_response(r) for r in reviews], total

    @classmethod
    def admin_update_review_status(cls, db: Session, review_id: int, new_status: str) -> ReviewResponse:
        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

        review.status = new_status
        review.is_approved = (new_status == "approved")
        db.commit()
        db.refresh(review)
        return cls._format_review_response(review)

    # ------------------------------------------------------------------
    # PRODUCT Q&A SERVICE METHODS
    # ------------------------------------------------------------------

    @classmethod
    def create_question(cls, db: Session, user: User, product_id_or_slug: Any, data: QuestionCreate) -> QuestionResponse:
        product = cls._resolve_product(db, product_id_or_slug)
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        question = ProductQuestion(
            product_id=product.id,
            variant_id=data.variant_id,
            user_id=user.id,
            question=data.question.strip(),
            status="approved" # approved by default
        )
        db.add(question)
        db.commit()
        db.refresh(question)
        return cls._format_question_response(question)

    @classmethod
    def create_answer(cls, db: Session, user: User, question_id: int, data: AnswerCreate) -> AnswerResponse:
        question = db.query(ProductQuestion).filter(ProductQuestion.id == question_id).first()
        if not question:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

        is_seller = user.role in ["admin", "manager", "seller"]
        answer = ProductAnswer(
            question_id=question.id,
            user_id=user.id,
            answer=data.answer.strip(),
            is_seller_answer=is_seller,
            status="approved"
        )
        db.add(answer)
        db.commit()
        db.refresh(answer)
        return cls._format_answer_response(answer)

    @classmethod
    def get_product_questions(
        cls,
        db: Session,
        product_id_or_slug: Any,
        page: int = 1,
        limit: int = 10,
        current_user_id: Optional[int] = None
    ) -> Tuple[List[QuestionResponse], int]:
        product = cls._resolve_product(db, product_id_or_slug)
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        query = db.query(ProductQuestion).filter(
            ProductQuestion.product_id == product.id,
            or_(
                ProductQuestion.status == "approved",
                ProductQuestion.user_id == current_user_id if current_user_id else False
            )
        )

        total = query.count()
        offset = (page - 1) * limit
        questions = query.order_by(desc(ProductQuestion.created_at)).offset(offset).limit(limit).all()

        formatted = [cls._format_question_response(q) for q in questions]
        return formatted, total

    @classmethod
    def admin_list_questions(
        cls,
        db: Session,
        page: int = 1,
        limit: int = 20,
        status_filter: Optional[str] = None,
        product_id: Optional[int] = None
    ) -> Tuple[List[QuestionResponse], int]:
        query = db.query(ProductQuestion)
        if status_filter:
            query = query.filter(ProductQuestion.status == status_filter)
        if product_id:
            query = query.filter(ProductQuestion.product_id == product_id)

        total = query.count()
        offset = (page - 1) * limit
        questions = query.order_by(desc(ProductQuestion.created_at)).offset(offset).limit(limit).all()
        return [cls._format_question_response(q, include_all_answers=True) for q in questions], total

    @classmethod
    def admin_update_question_status(cls, db: Session, question_id: int, new_status: str) -> QuestionResponse:
        q = db.query(ProductQuestion).filter(ProductQuestion.id == question_id).first()
        if not q:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
        q.status = new_status
        db.commit()
        db.refresh(q)
        return cls._format_question_response(q, include_all_answers=True)

    @classmethod
    def admin_delete_question(cls, db: Session, question_id: int) -> Dict[str, str]:
        q = db.query(ProductQuestion).filter(ProductQuestion.id == question_id).first()
        if not q:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
        db.delete(q)
        db.commit()
        return {"message": "Question deleted successfully"}

    @classmethod
    def admin_delete_answer(cls, db: Session, answer_id: int) -> Dict[str, str]:
        a = db.query(ProductAnswer).filter(ProductAnswer.id == answer_id).first()
        if not a:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")
        db.delete(a)
        db.commit()
        return {"message": "Answer deleted successfully"}

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_product(db: Session, product_id_or_slug: Any) -> Optional[Product]:
        if isinstance(product_id_or_slug, int) or (isinstance(product_id_or_slug, str) and product_id_or_slug.isdigit()):
            return db.query(Product).filter(Product.id == int(product_id_or_slug)).first()
        return db.query(Product).filter(Product.slug == str(product_id_or_slug)).first()

    @staticmethod
    def _format_review_response(review: Review, current_user_id: Optional[int] = None) -> ReviewResponse:
        helpful_count = len(review.helpful_votes) if review.helpful_votes else 0
        user_voted = False
        if current_user_id and review.helpful_votes:
            user_voted = any(v.user_id == current_user_id for v in review.helpful_votes)

        images = [
            ReviewImageResponse(
                id=img.id,
                image_url=img.image_url,
                alt_text=img.alt_text,
                sort_order=img.sort_order
            )
            for img in (review.images or [])
        ]

        user_name = review.user.full_name if review.user else "Verified Customer"

        # Product summary info
        p_name = review.product.name if review.product else None
        p_slug = review.product.slug if review.product else None
        p_image = None
        if review.product and review.product.images:
            p_image = review.product.images[0].image_url

        variant_title = review.variant.title if review.variant else None

        return ReviewResponse(
            id=review.id,
            product_id=review.product_id,
            product_name=p_name,
            product_slug=p_slug,
            product_image=p_image,
            variant_id=review.variant_id,
            variant_title=variant_title,
            user_id=review.user_id,
            user_name=user_name,
            rating=review.rating,
            title=review.title,
            body=review.body or review.comment or "",
            status=review.status,
            is_verified_purchase=review.is_verified_purchase,
            order_id=review.order_id,
            helpful_count=helpful_count,
            user_has_voted_helpful=user_voted,
            images=images,
            created_at=review.created_at,
            updated_at=review.updated_at
        )

    @classmethod
    def _format_question_response(cls, q: ProductQuestion, include_all_answers: bool = False) -> QuestionResponse:
        user_name = q.user.full_name if q.user else "Customer"
        answers = []
        if q.answers:
            for ans in q.answers:
                if include_all_answers or ans.status == "approved":
                    answers.append(cls._format_answer_response(ans))

        p_name = q.product.name if q.product else None
        p_slug = q.product.slug if q.product else None
        v_title = q.variant.title if q.variant else None

        return QuestionResponse(
            id=q.id,
            product_id=q.product_id,
            product_name=p_name,
            product_slug=p_slug,
            variant_id=q.variant_id,
            variant_title=v_title,
            user_id=q.user_id,
            user_name=user_name,
            question=q.question,
            status=q.status,
            answer_count=len(answers),
            answers=answers,
            created_at=q.created_at,
            updated_at=q.updated_at
        )

    @staticmethod
    def _format_answer_response(a: ProductAnswer) -> AnswerResponse:
        u_name = "Store Team" if a.is_seller_answer else (a.user.full_name if a.user else "Customer")
        return AnswerResponse(
            id=a.id,
            question_id=a.question_id,
            user_id=a.user_id,
            user_name=u_name,
            answer=a.answer,
            is_seller_answer=a.is_seller_answer,
            status=a.status,
            created_at=a.created_at,
            updated_at=a.updated_at
        )
