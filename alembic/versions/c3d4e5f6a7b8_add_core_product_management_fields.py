"""add_core_product_management_fields

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-15 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to support full Core Product Management fields and indexes."""
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=50), nullable=False, server_default='active'))
        batch_op.add_column(sa.Column('is_new_arrival', sa.Boolean(), nullable=False, server_default=sa.text('false')))
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('weight', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('length', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('width', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('height', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('warranty', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('seo_title', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('seo_description', sa.Text(), nullable=True))
        
        # Indexes for optimized querying and foreign keys
        batch_op.create_index('ix_products_category_id', ['category_id'], unique=False)
        batch_op.create_index('ix_products_brand_id', ['brand_id'], unique=False)
        batch_op.create_index('ix_products_status', ['status'], unique=False)
        batch_op.create_index('ix_products_sort_order', ['sort_order'], unique=False)
        batch_op.create_index('ix_products_is_featured', ['is_featured'], unique=False)
        batch_op.create_index('ix_products_is_new_arrival', ['is_new_arrival'], unique=False)

    # Backfill initial synchronized data for existing records
    op.execute("""
        UPDATE products 
        SET 
            status = CASE WHEN is_active = true THEN 'active' ELSE 'inactive' END,
            warranty = warranty_info,
            seo_title = meta_title,
            seo_description = meta_description
    """)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_index('ix_products_is_new_arrival')
        batch_op.drop_index('ix_products_is_featured')
        batch_op.drop_index('ix_products_sort_order')
        batch_op.drop_index('ix_products_status')
        batch_op.drop_index('ix_products_brand_id')
        batch_op.drop_index('ix_products_category_id')
        
        batch_op.drop_column('seo_description')
        batch_op.drop_column('seo_title')
        batch_op.drop_column('warranty')
        batch_op.drop_column('height')
        batch_op.drop_column('width')
        batch_op.drop_column('length')
        batch_op.drop_column('weight')
        batch_op.drop_column('sort_order')
        batch_op.drop_column('is_new_arrival')
        batch_op.drop_column('status')
