"""Add catalog search and filter indexes

Revision ID: h8a9b0c1d2e3
Revises: g7a8b9c0d1e2
Create Date: 2026-09-16 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'h8a9b0c1d2e3'
down_revision = 'g7a8b9c0d1e2'
branch_labels = None
depends_on = None

def upgrade():
    # Create indexes for optimized catalog filtering and sorting
    with op.batch_alter_table('products') as batch_op:
        batch_op.create_index('ix_products_price', ['price'], unique=False)
        batch_op.create_index('ix_products_is_active', ['is_active'], unique=False)
        batch_op.create_index('ix_products_created_at', ['created_at'], unique=False)
        batch_op.create_index('ix_products_discount_percent', ['discount_percent'], unique=False)

def downgrade():
    with op.batch_alter_table('products') as batch_op:
        batch_op.drop_index('ix_products_discount_percent')
        batch_op.drop_index('ix_products_created_at')
        batch_op.drop_index('ix_products_is_active')
        batch_op.drop_index('ix_products_price')
