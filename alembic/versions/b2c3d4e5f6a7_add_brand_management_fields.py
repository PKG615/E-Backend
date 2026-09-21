"""add_brand_management_fields

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-15 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to support full Brand Management fields."""
    with op.batch_alter_table('brands', schema=None) as batch_op:
        batch_op.add_column(sa.Column('website_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('seo_title', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('seo_description', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('brands', schema=None) as batch_op:
        batch_op.drop_column('seo_description')
        batch_op.drop_column('seo_title')
        batch_op.drop_column('sort_order')
        batch_op.drop_column('website_url')
