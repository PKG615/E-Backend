from datetime import datetime
from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, Float, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Review(BaseModel):
    __tablename__ = "reviews"

    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id", ondelete="SET NULL"), nullable=True, index=True)
    
    rating = Column(Integer, nullable=False, index=True) # 1 to 5
    title = Column(String(255), nullable=True)
    comment = Column(Text, nullable=True)
    body = Column(Text, nullable=False)
    is_approved = Column(Boolean, default=True, nullable=False)
    status = Column(String(20), default="approved", nullable=False, index=True) # pending, approved, rejected, hidden
    is_verified_purchase = Column(Boolean, default=False, nullable=False, index=True)

    # Relationships
    product = relationship("Product", back_populates="reviews")
    user = relationship("User", back_populates="reviews")
    variant = relationship("ProductVariant")
    order = relationship("Order")
    order_item = relationship("OrderItem")
    images = relationship("ReviewImage", back_populates="review", cascade="all, delete-orphan", order_by="asc(ReviewImage.sort_order), asc(ReviewImage.id)")
    helpful_votes = relationship("ReviewHelpfulVote", back_populates="review", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("product_id", "user_id", name="uq_product_user_review"),
    )


class ReviewImage(BaseModel):
    __tablename__ = "review_images"

    review_id = Column(Integer, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    image_url = Column(String(500), nullable=False)
    alt_text = Column(String(255), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)

    review = relationship("Review", back_populates="images")


class ReviewHelpfulVote(BaseModel):
    __tablename__ = "review_helpful_votes"

    review_id = Column(Integer, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    review = relationship("Review", back_populates="helpful_votes")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("review_id", "user_id", name="uq_review_helpful_vote"),
    )


class ProductQuestion(BaseModel):
    __tablename__ = "product_questions"

    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    question = Column(Text, nullable=False)
    status = Column(String(20), default="approved", nullable=False, index=True) # pending, approved, rejected, hidden

    # Relationships
    product = relationship("Product", back_populates="questions")
    variant = relationship("ProductVariant")
    user = relationship("User")
    answers = relationship("ProductAnswer", back_populates="question", cascade="all, delete-orphan", order_by="desc(ProductAnswer.is_seller_answer), asc(ProductAnswer.created_at)")


class ProductAnswer(BaseModel):
    __tablename__ = "product_answers"

    question_id = Column(Integer, ForeignKey("product_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    answer = Column(Text, nullable=False)
    is_seller_answer = Column(Boolean, default=False, nullable=False)
    status = Column(String(20), default="approved", nullable=False, index=True) # pending, approved, rejected, hidden

    # Relationships
    question = relationship("ProductQuestion", back_populates="answers")
    user = relationship("User")
