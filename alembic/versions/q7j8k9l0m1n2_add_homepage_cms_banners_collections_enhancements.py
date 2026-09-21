"""add_homepage_cms_banners_collections_enhancements

Revision ID: q7j8k9l0m1n2
Revises: p6i7j8k9l0m1
Create Date: 2026-09-19 11:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'q7j8k9l0m1n2'
down_revision: Union[str, Sequence[str], None] = 'p6i7j8k9l0m1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # 1. Update homepage_sections with scheduling columns
    if 'homepage_sections' in existing_tables:
        sec_cols = [c['name'] for c in insp.get_columns('homepage_sections')]
        with op.batch_alter_table('homepage_sections', schema=None) as batch_op:
            if 'starts_at' not in sec_cols:
                batch_op.add_column(sa.Column('starts_at', sa.DateTime(), nullable=True))
            if 'ends_at' not in sec_cols:
                batch_op.add_column(sa.Column('ends_at', sa.DateTime(), nullable=True))

    # 2. Update banners with link_type, link_target, alt_text
    if 'banners' in existing_tables:
        ban_cols = [c['name'] for c in insp.get_columns('banners')]
        with op.batch_alter_table('banners', schema=None) as batch_op:
            if 'alt_text' not in ban_cols:
                batch_op.add_column(sa.Column('alt_text', sa.String(length=255), nullable=True))
            if 'link_type' not in ban_cols:
                batch_op.add_column(sa.Column('link_type', sa.String(length=50), server_default='custom', nullable=True))
            if 'link_target' not in ban_cols:
                batch_op.add_column(sa.Column('link_target', sa.String(length=255), nullable=True))

    # 3. Update collections with SEO columns
    if 'collections' in existing_tables:
        col_cols = [c['name'] for c in insp.get_columns('collections')]
        with op.batch_alter_table('collections', schema=None) as batch_op:
            if 'seo_title' not in col_cols:
                batch_op.add_column(sa.Column('seo_title', sa.String(length=255), nullable=True))
            if 'seo_description' not in col_cols:
                batch_op.add_column(sa.Column('seo_description', sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'collections' in existing_tables:
        with op.batch_alter_table('collections', schema=None) as batch_op:
            batch_op.drop_column('seo_description')
            batch_op.drop_column('seo_title')

    if 'banners' in existing_tables:
        with op.batch_alter_table('banners', schema=None) as batch_op:
            batch_op.drop_column('link_target')
            batch_op.drop_column('link_type')
            batch_op.drop_column('alt_text')

    if 'homepage_sections' in existing_tables:
        with op.batch_alter_table('homepage_sections', schema=None) as batch_op:
            batch_op.drop_column('ends_at')
            batch_op.drop_column('starts_at')
