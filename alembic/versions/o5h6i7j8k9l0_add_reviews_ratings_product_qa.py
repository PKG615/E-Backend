"""Add reviews enhancements, helpful votes, review images, and product Q&A tables

Revision ID: o5h6i7j8k9l0
Revises: n4g5h6i7j8k9
Create Date: 2026-09-19 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'o5h6i7j8k9l0'
down_revision = 'n4g5h6i7j8k9'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = insp.get_table_names()

    # 1. Update existing reviews table with additional fields if missing
    if 'reviews' in table_names:
        cols = [c['name'] for c in insp.get_columns('reviews')]
        with op.batch_alter_table('reviews') as batch_op:
            if 'variant_id' not in cols:
                batch_op.add_column(sa.Column('variant_id', sa.Integer(), nullable=True))
            if 'order_id' not in cols:
                batch_op.add_column(sa.Column('order_id', sa.Integer(), nullable=True))
            if 'order_item_id' not in cols:
                batch_op.add_column(sa.Column('order_item_id', sa.Integer(), nullable=True))
            if 'status' not in cols:
                batch_op.add_column(sa.Column('status', sa.String(length=20), server_default='approved', nullable=False))
            if 'is_verified_purchase' not in cols:
                batch_op.add_column(sa.Column('is_verified_purchase', sa.Boolean(), server_default=sa.false(), nullable=False))
            if 'body' not in cols:
                batch_op.add_column(sa.Column('body', sa.Text(), nullable=True))

        # Backfill body from comment if comment exists
        if 'comment' in cols:
            op.execute("UPDATE reviews SET body = comment WHERE body IS NULL AND comment IS NOT NULL")
        
        # Create indexes on reviews
        idx_names = [idx['name'] for idx in insp.get_indexes('reviews')]
        if 'ix_reviews_product_id' not in idx_names:
            op.create_index('ix_reviews_product_id', 'reviews', ['product_id'], unique=False)
        if 'ix_reviews_user_id' not in idx_names:
            op.create_index('ix_reviews_user_id', 'reviews', ['user_id'], unique=False)
        if 'ix_reviews_status' not in idx_names:
            op.create_index('ix_reviews_status', 'reviews', ['status'], unique=False)
        if 'ix_reviews_rating' not in idx_names:
            op.create_index('ix_reviews_rating', 'reviews', ['rating'], unique=False)
        if 'ix_reviews_created_at' not in idx_names:
            op.create_index('ix_reviews_created_at', 'reviews', ['created_at'], unique=False)
    else:
        # Fallback create reviews table if somehow missing
        op.create_table(
            'reviews',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
            sa.Column('variant_id', sa.Integer(), sa.ForeignKey('product_variants.id', ondelete='SET NULL'), nullable=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id', ondelete='SET NULL'), nullable=True),
            sa.Column('order_item_id', sa.Integer(), sa.ForeignKey('order_items.id', ondelete='SET NULL'), nullable=True),
            sa.Column('rating', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=True),
            sa.Column('comment', sa.Text(), nullable=True),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('is_approved', sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column('status', sa.String(length=20), server_default='approved', nullable=False),
            sa.Column('is_verified_purchase', sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_reviews_product_id', 'reviews', ['product_id'], unique=False)
        op.create_index('ix_reviews_user_id', 'reviews', ['user_id'], unique=False)
        op.create_index('ix_reviews_status', 'reviews', ['status'], unique=False)
        op.create_index('ix_reviews_rating', 'reviews', ['rating'], unique=False)
        op.create_index('ix_reviews_created_at', 'reviews', ['created_at'], unique=False)

    # 2. Create review_images table
    if 'review_images' not in table_names:
        op.create_table(
            'review_images',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('review_id', sa.Integer(), sa.ForeignKey('reviews.id', ondelete='CASCADE'), nullable=False),
            sa.Column('image_url', sa.String(length=500), nullable=False),
            sa.Column('alt_text', sa.String(length=255), nullable=True),
            sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_review_images_review_id', 'review_images', ['review_id'], unique=False)

    # 3. Create review_helpful_votes table
    if 'review_helpful_votes' not in table_names:
        op.create_table(
            'review_helpful_votes',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('review_id', sa.Integer(), sa.ForeignKey('reviews.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('review_id', 'user_id', name='uq_review_helpful_vote')
        )
        op.create_index('ix_review_helpful_votes_review_id', 'review_helpful_votes', ['review_id'], unique=False)
        op.create_index('ix_review_helpful_votes_user_id', 'review_helpful_votes', ['user_id'], unique=False)

    # 4. Create product_questions table
    if 'product_questions' not in table_names:
        op.create_table(
            'product_questions',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
            sa.Column('variant_id', sa.Integer(), sa.ForeignKey('product_variants.id', ondelete='SET NULL'), nullable=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('question', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=20), server_default='approved', nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_product_questions_product_id', 'product_questions', ['product_id'], unique=False)
        op.create_index('ix_product_questions_user_id', 'product_questions', ['user_id'], unique=False)
        op.create_index('ix_product_questions_status', 'product_questions', ['status'], unique=False)
        op.create_index('ix_product_questions_created_at', 'product_questions', ['created_at'], unique=False)

    # 5. Create product_answers table
    if 'product_answers' not in table_names:
        op.create_table(
            'product_answers',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('question_id', sa.Integer(), sa.ForeignKey('product_questions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('answer', sa.Text(), nullable=False),
            sa.Column('is_seller_answer', sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column('status', sa.String(length=20), server_default='approved', nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_product_answers_question_id', 'product_answers', ['question_id'], unique=False)
        op.create_index('ix_product_answers_user_id', 'product_answers', ['user_id'], unique=False)
        op.create_index('ix_product_answers_status', 'product_answers', ['status'], unique=False)


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = insp.get_table_names()

    if 'product_answers' in table_names:
        op.drop_table('product_answers')
    if 'product_questions' in table_names:
        op.drop_table('product_questions')
    if 'review_helpful_votes' in table_names:
        op.drop_table('review_helpful_votes')
    if 'review_images' in table_names:
        op.drop_table('review_images')
