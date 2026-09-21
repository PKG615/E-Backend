"""add_category_management_fields

Revision ID: a1b2c3d4e5f6
Revises: 3456024e091e
Create Date: 2026-09-15 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '3456024e091e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to support full Category Management fields."""
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('banner', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('seo_title', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('seo_description', sa.Text(), nullable=True))

    # Synchronize initial values from image_url and display_order where applicable
    op.execute("UPDATE categories SET image = image_url WHERE image IS NULL AND image_url IS NOT NULL")
    op.execute("UPDATE categories SET sort_order = display_order WHERE sort_order = 0 AND display_order IS NOT NULL")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.drop_column('seo_description')
        batch_op.drop_column('seo_title')
        batch_op.drop_column('sort_order')
        batch_op.drop_column('banner')
        batch_op.drop_column('image')
