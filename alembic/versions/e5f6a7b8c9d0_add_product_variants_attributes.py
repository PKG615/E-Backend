"""add_product_variants_attributes

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-15 19:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create product_attributes table
    op.create_table(
        'product_attributes',
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_product_attributes_id'), 'product_attributes', ['id'], unique=False)
    op.create_index(op.f('ix_product_attributes_slug'), 'product_attributes', ['slug'], unique=True)

    # 2. Create product_attribute_values table
    op.create_table(
        'product_attribute_values',
        sa.Column('attribute_id', sa.Integer(), nullable=False),
        sa.Column('value', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['attribute_id'], ['product_attributes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('attribute_id', 'slug', name='uq_attribute_value_slug')
    )
    op.create_index(op.f('ix_product_attribute_values_id'), 'product_attribute_values', ['id'], unique=False)
    op.create_index(op.f('ix_product_attribute_values_attribute_id'), 'product_attribute_values', ['attribute_id'], unique=False)
    op.create_index(op.f('ix_product_attribute_values_slug'), 'product_attribute_values', ['slug'], unique=False)

    # 3. Add sort_order to product_variants and indexes
    with op.batch_alter_table('product_variants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
        batch_op.create_index('ix_product_variants_product_id', ['product_id'], unique=False)
        batch_op.create_index('ix_product_variants_product_id_is_active', ['product_id', 'is_active'], unique=False)
        batch_op.create_index('ix_product_variants_product_id_sort_order', ['product_id', 'sort_order'], unique=False)

    # 4. Create variant_attribute_values association table
    op.create_table(
        'variant_attribute_values',
        sa.Column('variant_id', sa.Integer(), nullable=False),
        sa.Column('attribute_value_id', sa.Integer(), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['attribute_value_id'], ['product_attribute_values.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('variant_id', 'attribute_value_id', name='uq_variant_attribute_value')
    )
    op.create_index(op.f('ix_variant_attribute_values_id'), 'variant_attribute_values', ['id'], unique=False)
    op.create_index(op.f('ix_variant_attribute_values_variant_id'), 'variant_attribute_values', ['variant_id'], unique=False)
    op.create_index(op.f('ix_variant_attribute_values_attribute_value_id'), 'variant_attribute_values', ['attribute_value_id'], unique=False)


def downgrade() -> None:
    op.drop_table('variant_attribute_values')
    
    with op.batch_alter_table('product_variants', schema=None) as batch_op:
        batch_op.drop_index('ix_product_variants_product_id_sort_order')
        batch_op.drop_index('ix_product_variants_product_id_is_active')
        batch_op.drop_index('ix_product_variants_product_id')
        batch_op.drop_column('sort_order')

    op.drop_table('product_attribute_values')
    op.drop_table('product_attributes')
