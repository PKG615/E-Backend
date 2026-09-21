"""add_product_images_management_fields

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-15 18:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema for product images management with sort_order and performance indexes."""
    with op.batch_alter_table('product_images', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
        batch_op.create_index('ix_product_images_product_id', ['product_id'], unique=False)
        batch_op.create_index('ix_product_images_product_id_sort_order', ['product_id', 'sort_order'], unique=False)
        batch_op.create_index('ix_product_images_product_id_is_primary', ['product_id', 'is_primary'], unique=False)
    
    # Synchronize sort_order from existing display_order
    op.execute("UPDATE product_images SET sort_order = display_order WHERE display_order IS NOT NULL")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('product_images', schema=None) as batch_op:
        batch_op.drop_index('ix_product_images_product_id_is_primary')
        batch_op.drop_index('ix_product_images_product_id_sort_order')
        batch_op.drop_index('ix_product_images_product_id')
        batch_op.drop_column('sort_order')
