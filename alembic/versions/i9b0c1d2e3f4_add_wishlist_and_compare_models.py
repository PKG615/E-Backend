"""Add wishlist and compare models

Revision ID: i9b0c1d2e3f4
Revises: h8a9b0c1d2e3
Create Date: 2026-09-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'i9b0c1d2e3f4'
down_revision = 'h8a9b0c1d2e3'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    # 1. Create wishlist_items table if not exists
    if 'wishlist_items' not in tables:
        op.create_table(
            'wishlist_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('product_id', sa.Integer(), nullable=False),
            sa.Column('variant_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'product_id', name='uq_user_product_wishlist')
        )
        with op.batch_alter_table('wishlist_items') as batch_op:
            batch_op.create_index('ix_wishlist_items_id', ['id'], unique=False)
            batch_op.create_index('ix_wishlist_items_user_id', ['user_id'], unique=False)
            batch_op.create_index('ix_wishlist_items_product_id', ['product_id'], unique=False)
            batch_op.create_index('ix_wishlist_items_variant_id', ['variant_id'], unique=False)

    # 2. Create compare_items table if not exists
    if 'compare_items' not in tables:
        op.create_table(
            'compare_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('session_id', sa.String(length=100), nullable=True),
            sa.Column('product_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'product_id', name='uq_user_product_compare')
        )
        with op.batch_alter_table('compare_items') as batch_op:
            batch_op.create_index('ix_compare_items_id', ['id'], unique=False)
            batch_op.create_index('ix_compare_items_user_id', ['user_id'], unique=False)
            batch_op.create_index('ix_compare_items_session_id', ['session_id'], unique=False)
            batch_op.create_index('ix_compare_items_product_id', ['product_id'], unique=False)

def downgrade():
    op.drop_table('compare_items')
    op.drop_table('wishlist_items')
