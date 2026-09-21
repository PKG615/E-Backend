"""Add cart checkout and address management fields

Revision ID: j0c1d2e3f4g5
Revises: i9b0c1d2e3f4
Create Date: 2026-09-16 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'j0c1d2e3f4g5'
down_revision = 'i9b0c1d2e3f4'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    
    # 1. Update carts table
    cart_cols = [c['name'] for c in insp.get_columns('carts')]
    with op.batch_alter_table('carts') as batch_op:
        if 'status' not in cart_cols:
            batch_op.add_column(sa.Column('status', sa.String(length=50), server_default='active', nullable=False))
        existing_indexes = [i['name'] for i in insp.get_indexes('carts')]
        if 'ix_carts_user_id_status' not in existing_indexes:
            batch_op.create_index('ix_carts_user_id_status', ['user_id', 'status'], unique=False)

    # 2. Update cart_items indexes
    item_indexes = [i['name'] for i in insp.get_indexes('cart_items')]
    with op.batch_alter_table('cart_items') as batch_op:
        if 'ix_cart_items_cart_id' not in item_indexes:
            batch_op.create_index('ix_cart_items_cart_id', ['cart_id'], unique=False)
        if 'ix_cart_items_product_id' not in item_indexes:
            batch_op.create_index('ix_cart_items_product_id', ['product_id'], unique=False)
        if 'ix_cart_items_variant_id' not in item_indexes:
            batch_op.create_index('ix_cart_items_variant_id', ['variant_id'], unique=False)
        if 'ix_cart_items_lookup' not in item_indexes:
            batch_op.create_index('ix_cart_items_lookup', ['cart_id', 'product_id', 'variant_id'], unique=False)

    # 3. Update addresses table
    addr_cols = [c['name'] for c in insp.get_columns('addresses')]
    with op.batch_alter_table('addresses') as batch_op:
        if 'address_line1' not in addr_cols:
            batch_op.add_column(sa.Column('address_line1', sa.String(length=255), nullable=True))
        if 'address_line2' not in addr_cols:
            batch_op.add_column(sa.Column('address_line2', sa.String(length=255), nullable=True))
        if 'landmark' not in addr_cols:
            batch_op.add_column(sa.Column('landmark', sa.String(length=255), nullable=True))
        if 'address_type' not in addr_cols:
            batch_op.add_column(sa.Column('address_type', sa.String(length=50), server_default='home', nullable=False))
        addr_indexes = [i['name'] for i in insp.get_indexes('addresses')]
        if 'ix_addresses_user_id' not in addr_indexes:
            batch_op.create_index('ix_addresses_user_id', ['user_id'], unique=False)
        if 'ix_addresses_user_is_default' not in addr_indexes:
            batch_op.create_index('ix_addresses_user_is_default', ['user_id', 'is_default'], unique=False)

    # Copy street to address_line1 if existing
    op.execute("UPDATE addresses SET address_line1 = street WHERE address_line1 IS NULL AND street IS NOT NULL")
    op.execute("UPDATE addresses SET address_line1 = 'Main Street' WHERE address_line1 IS NULL")

def downgrade():
    with op.batch_alter_table('addresses') as batch_op:
        batch_op.drop_index('ix_addresses_user_is_default')
        batch_op.drop_index('ix_addresses_user_id')
        batch_op.drop_column('address_type')
        batch_op.drop_column('landmark')
        batch_op.drop_column('address_line2')
        batch_op.drop_column('address_line1')

    with op.batch_alter_table('cart_items') as batch_op:
        batch_op.drop_index('ix_cart_items_lookup')
        batch_op.drop_index('ix_cart_items_variant_id')
        batch_op.drop_index('ix_cart_items_product_id')
        batch_op.drop_index('ix_cart_items_cart_id')

    with op.batch_alter_table('carts') as batch_op:
        batch_op.drop_index('ix_carts_user_id_status')
        batch_op.drop_column('status')
