import unittest
from datetime import datetime
from fastapi.exceptions import HTTPException

from backend.app.core.database import SessionLocal
from backend.app.models.user import User
from backend.app.models.order import Order, OrderItem
from backend.app.models.product import Product
from backend.app.models.reviews import Review, ReviewHelpfulVote, ProductQuestion, ProductAnswer
from backend.app.schemas.reviews import ReviewCreate, ReviewUpdate, QuestionCreate, AnswerCreate
from backend.app.services.review_service import ReviewService


class TestReviewsRatingsAndQA(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        # Find customer and admin users
        self.customer = self.db.query(User).filter(User.role == "customer").first()
        self.admin = self.db.query(User).filter(User.role == "admin").first()
        if not self.customer:
            self.customer = self.db.query(User).first()
        if not self.admin:
            self.admin = self.db.query(User).first()
        self.product = self.db.query(Product).first()

    def tearDown(self):
        self.db.close()

    def test_review_creation_and_verified_check(self):
        """Test review creation and backend verification check."""
        self.assertIsNotNone(self.customer, "Customer user must exist")
        self.assertIsNotNone(self.product, "Product must exist")

        # Check eligibility before review
        elig = ReviewService.get_review_eligibility(self.db, self.customer.id, self.product.id)
        self.assertIsInstance(elig.can_review, bool)

        # Check existing review for this user/product
        existing = self.db.query(Review).filter(
            Review.product_id == self.product.id,
            Review.user_id == self.customer.id
        ).first()

        if existing:
            # Duplicate review should be rejected
            with self.assertRaises(HTTPException) as cm:
                ReviewService.create_review(
                    self.db,
                    self.customer,
                    self.product.id,
                    ReviewCreate(rating=5, title="Duplicate Test", body="Duplicate attempt")
                )
            self.assertEqual(cm.exception.status_code, 400)
        else:
            # Create a review
            rev = ReviewService.create_review(
                self.db,
                self.customer,
                self.product.id,
                ReviewCreate(
                    rating=5,
                    title="Amazing quality and sound",
                    body="Exceeded all my expectations. Highly recommended!",
                    images=["https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500"]
                )
            )
            self.assertEqual(rev.rating, 5)
            self.assertEqual(rev.title, "Amazing quality and sound")
            self.assertEqual(len(rev.images), 1)

    def test_rating_aggregate_calculation(self):
        """Test calculation of average rating and distribution."""
        agg = ReviewService.get_product_aggregate(self.db, self.product.id)
        self.assertGreaterEqual(agg.average_rating, 0.0)
        self.assertLessEqual(agg.average_rating, 5.0)
        self.assertIn("5", agg.rating_distribution)
        self.assertIn("1", agg.rating_distribution)
        total_dist = sum(agg.rating_distribution.values())
        self.assertEqual(total_dist, agg.review_count)

    def test_helpful_vote_toggle(self):
        """Test that helpful votes can be added and toggled off, and cannot self-vote."""
        # Find an existing review
        rev = self.db.query(Review).first()
        if not rev:
            return

        # Attempt self-vote
        author = self.db.query(User).filter(User.id == rev.user_id).first()
        if author:
            with self.assertRaises(HTTPException) as cm:
                ReviewService.vote_helpful(self.db, author, rev.id)
            self.assertEqual(cm.exception.status_code, 400)

        # Another user voting
        voter = self.db.query(User).filter(User.id != rev.user_id).first()
        if voter:
            # Clear any pre-existing vote from setup
            self.db.query(ReviewHelpfulVote).filter(
                ReviewHelpfulVote.review_id == rev.id,
                ReviewHelpfulVote.user_id == voter.id
            ).delete()
            self.db.commit()

            res1 = ReviewService.vote_helpful(self.db, voter, rev.id)
            self.assertTrue(res1.voted)
            
            # Toggle off
            res2 = ReviewService.vote_helpful(self.db, voter, rev.id)
            self.assertFalse(res2.voted)

    def test_qa_workflow_and_seller_badge(self):
        """Test customer asking question and admin answering with seller badge."""
        # Customer asks question
        q = ReviewService.create_question(
            self.db,
            self.customer,
            self.product.id,
            QuestionCreate(question="Does this package include warranty and cable?")
        )
        self.assertEqual(q.question, "Does this package include warranty and cable?")
        self.assertEqual(q.status, "approved")

        # Admin answers -> is_seller_answer must be True
        ans = ReviewService.create_answer(
            self.db,
            self.admin,
            q.id,
            AnswerCreate(answer="Yes, it includes a 1-year warranty and a fast USB-C cable.")
        )
        self.assertTrue(ans.is_seller_answer)
        self.assertEqual(ans.user_name, "Store Team")

        # Customer answers -> is_seller_answer must be False
        if self.customer.role == "customer":
            ans_cust = ReviewService.create_answer(
                self.db,
                self.customer,
                q.id,
                AnswerCreate(answer="I can confirm the cable is in the box.")
            )
            self.assertFalse(ans_cust.is_seller_answer)

        # Clean up test question
        ReviewService.admin_delete_question(self.db, q.id)

    def test_non_owner_cannot_edit_or_delete_review(self):
        """Test customer isolation: user cannot edit or delete another user's review."""
        rev = self.db.query(Review).first()
        if not rev:
            return

        other_user = self.db.query(User).filter(User.id != rev.user_id, User.role == "customer").first()
        if other_user:
            with self.assertRaises(HTTPException) as cm:
                ReviewService.update_review(
                    self.db,
                    other_user,
                    rev.id,
                    ReviewUpdate(title="Hacked Title", body="Hacked Body")
                )
            self.assertEqual(cm.exception.status_code, 403)

            with self.assertRaises(HTTPException) as cm_del:
                ReviewService.delete_review(self.db, other_user, rev.id)
            self.assertEqual(cm_del.exception.status_code, 403)

    def test_moderation_filtering_and_admin_actions(self):
        """Test review moderation status updates and public filtering."""
        rev = self.db.query(Review).first()
        if not rev:
            return

        original_status = rev.status

        # Admin rejects review
        rejected = ReviewService.admin_update_review_status(self.db, rev.id, "rejected")
        self.assertEqual(rejected.status, "rejected")

        # Public list shouldn't include rejected review for anonymous/other users
        reviews, _ = ReviewService.get_product_reviews(self.db, rev.product_id, current_user_id=None)
        self.assertFalse(any(r.id == rev.id for r in reviews))

        # Admin approves review back
        approved = ReviewService.admin_update_review_status(self.db, rev.id, original_status)
        self.assertEqual(approved.status, original_status)


if __name__ == "__main__":

    unittest.main()
