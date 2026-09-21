"""Add coupons, offers, and flash sales tables and columns

Revision ID: n4g5h6i7j8k9
Revises: m3f4g5h6i7j8
Create Date: 2026-09-18 07:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'n4g5h6i7j8k9'
down_revision = 'm3f4g5h6i7j8'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = insp.get_table_names()

    # 1. Create coupons table
    if 'coupons' not in table_names:
        op.create_table(
            'coupons',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('code', sa.String(length=50), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('discount_type', sa.String(length=50), nullable=False), # percentage, fixed_amount
            sa.Column('discount_value', sa.Float(), nullable=False),
            sa.Column('max_discount_amount', sa.Float(), nullable=True),
            sa.Column('minimum_cart_value', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('maximum_cart_value', sa.Float(), nullable=True),
            sa.Column('usage_limit', sa.Integer(), nullable=True),
            sa.Column('per_customer_limit', sa.Integer(), server_default='1', nullable=False),
            sa.Column('used_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('starts_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('code')
        )
        op.create_index('ix_coupons_code', 'coupons', ['code'], unique=True)
        op.create_index('ix_coupons_is_active', 'coupons', ['is_active'], unique=False)
        op.create_index('ix_coupons_expires_at', 'coupons', ['expires_at'], unique=False)

    # 2. Create coupon_products table
    if 'coupon_products' not in table_names:
        op.create_table(
            'coupon_products',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('coupon_id', sa.Integer(), sa.ForeignKey('coupons.id', ondelete='CASCADE'), nullable=False),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('coupon_id', 'product_id', name='uq_coupon_product')
        )
        op.create_index('ix_coupon_products_coupon_id', 'coupon_products', ['coupon_id'], unique=False)
        op.create_index('ix_coupon_products_product_id', 'coupon_products', ['product_id'], unique=False)

    # 3. Create coupon_categories table
    if 'coupon_categories' not in table_names:
        op.create_table(
            'coupon_categories',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('coupon_id', sa.Integer(), sa.ForeignKey('coupons.id', ondelete='CASCADE'), nullable=False),
            sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('coupon_id', 'category_id', name='uq_coupon_category')
        )
        op.create_index('ix_coupon_categories_coupon_id', 'coupon_categories', ['coupon_id'], unique=False)
        op.create_index('ix_coupon_categories_category_id', 'coupon_categories', ['category_id'], unique=False)

    # 4. Create coupon_brands table
    if 'coupon_brands' not in table_names:
        op.create_table(
            'coupon_brands',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('coupon_id', sa.Integer(), sa.ForeignKey('coupons.id', ondelete='CASCADE'), nullable=False),
            sa.Column('brand_id', sa.Integer(), sa.ForeignKey('brands.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('coupon_id', 'brand_id', name='uq_coupon_brand')
        )
        op.create_index('ix_coupon_brands_coupon_id', 'coupon_brands', ['coupon_id'], unique=False)
        op.create_index('ix_coupon_brands_brand_id', 'coupon_brands', ['brand_id'], unique=False)

    # 5. Create coupon_exclusions table
    if 'coupon_exclusions' not in table_names:
        op.create_table(
            'coupon_exclusions',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('coupon_id', sa.Integer(), sa.ForeignKey('coupons.id', ondelete='CASCADE'), nullable=False),
            sa.Column('exclusion_type', sa.String(length=50), nullable=False), # product, category, brand
            sa.Column('target_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_coupon_exclusions_coupon_id', 'coupon_exclusions', ['coupon_id'], unique=False)

    # 6. Create coupon_usages table
    if 'coupon_usages' not in table_names:
        op.create_table(
            'coupon_usages',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('coupon_id', sa.Integer(), sa.ForeignKey('coupons.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id', ondelete='SET NULL'), nullable=True),
            sa.Column('discount_amount', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('status', sa.String(length=50), server_default='consumed', nullable=False), # reserved, consumed, cancelled
            sa.Column('used_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_coupon_usages_coupon_id', 'coupon_usages', ['coupon_id'], unique=False)
        op.create_index('ix_coupon_usages_user_id', 'coupon_usages', ['user_id'], unique=False)
        op.create_index('ix_coupon_usages_order_id', 'coupon_usages', ['order_id'], unique=False)
        op.create_index('ix_coupon_usages_status', 'coupon_usages', ['status'], unique=False)

    # 7. Create offers table
    if 'offers' not in table_names:
        op.create_table(
            'offers',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('offer_type', sa.String(length=50), nullable=False), # product_discount, category_discount, brand_discount, cart_discount
            sa.Column('discount_type', sa.String(length=50), nullable=False), # percentage, fixed_amount
            sa.Column('discount_value', sa.Float(), nullable=False),
            sa.Column('max_discount_amount', sa.Float(), nullable=True),
            sa.Column('minimum_cart_value', sa.Float(), nullable=True),
            sa.Column('starts_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column('priority', sa.Integer(), server_default='0', nullable=False),
            sa.Column('stackable', sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_offers_is_active', 'offers', ['is_active'], unique=False)
        op.create_index('ix_offers_priority', 'offers', ['priority'], unique=False)
        op.create_index('ix_offers_expires_at', 'offers', ['expires_at'], unique=False)

    # 8. Create offer_products table
    if 'offer_products' not in table_names:
        op.create_table(
            'offer_products',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('offer_id', sa.Integer(), sa.ForeignKey('offers.id', ondelete='CASCADE'), nullable=False),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('offer_id', 'product_id', name='uq_offer_product')
        )
        op.create_index('ix_offer_products_offer_id', 'offer_products', ['offer_id'], unique=False)
        op.create_index('ix_offer_products_product_id', 'offer_products', ['product_id'], unique=False)

    # 9. Create offer_categories table
    if 'offer_categories' not in table_names:
        op.create_table(
            'offer_categories',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('offer_id', sa.Integer(), sa.ForeignKey('offers.id', ondelete='CASCADE'), nullable=False),
            sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('offer_id', 'category_id', name='uq_offer_category')
        )
        op.create_index('ix_offer_categories_offer_id', 'offer_categories', ['offer_id'], unique=False)
        op.create_index('ix_offer_categories_category_id', 'offer_categories', ['category_id'], unique=False)

    # 10. Create offer_brands table
    if 'offer_brands' not in table_names:
        op.create_table(
            'offer_brands',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('offer_id', sa.Integer(), sa.ForeignKey('offers.id', ondelete='CASCADE'), nullable=False),
            sa.Column('brand_id', sa.Integer(), sa.ForeignKey('brands.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('offer_id', 'brand_id', name='uq_offer_brand')
        )
        op.create_index('ix_offer_brands_offer_id', 'offer_brands', ['offer_id'], unique=False)
        op.create_index('ix_offer_brands_brand_id', 'offer_brands', ['brand_id'], unique=False)

    # 11. Create flash_sales table
    if 'flash_sales' not in table_names:
        op.create_table(
            'flash_sales',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('banner_image', sa.String(length=500), nullable=True),
            sa.Column('starts_at', sa.DateTime(), nullable=False),
            sa.Column('ends_at', sa.DateTime(), nullable=False),
            sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column('priority', sa.Integer(), server_default='0', nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_flash_sales_is_active', 'flash_sales', ['is_active'], unique=False)
        op.create_index('ix_flash_sales_starts_at', 'flash_sales', ['starts_at'], unique=False)
        op.create_index('ix_flash_sales_ends_at', 'flash_sales', ['ends_at'], unique=False)

    # 12. Create flash_sale_items table
    if 'flash_sale_items' not in table_names:
        op.create_table(
            'flash_sale_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('flash_sale_id', sa.Integer(), sa.ForeignKey('flash_sales.id', ondelete='CASCADE'), nullable=False),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
            sa.Column('variant_id', sa.Integer(), sa.ForeignKey('product_variants.id', ondelete='SET NULL'), nullable=True),
            sa.Column('sale_price', sa.Float(), nullable=False),
            sa.Column('quantity_limit', sa.Integer(), nullable=True),
            sa.Column('sold_quantity', sa.Integer(), server_default='0', nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_flash_sale_items_flash_sale_id', 'flash_sale_items', ['flash_sale_id'], unique=False)
        op.create_index('ix_flash_sale_items_product_id', 'flash_sale_items', ['product_id'], unique=False)
        op.create_index('ix_flash_sale_items_variant_id', 'flash_sale_items', ['variant_id'], unique=False)

    # 13. Update carts table
    cart_cols = [c['name'] for c in insp.get_columns('carts')]
    with op.batch_alter_table('carts') as batch_op:
        if 'coupon_code' not in cart_cols:
            batch_op.add_column(sa.Column('coupon_code', sa.String(length=50), nullable=True))
        if 'applied_coupon_id' not in cart_cols:
            batch_op.add_column(sa.Column('applied_coupon_id', sa.Integer(), nullable=True))

    # 14. Update orders table
    order_cols = [c['name'] for c in insp.get_columns('orders')]
    with op.batch_alter_table('orders') as batch_op:
        if 'coupon_code' not in order_cols:
            batch_op.add_column(sa.Column('coupon_code', sa.String(length=50), nullable=True))
        if 'coupon_discount' not in order_cols:
            batch_op.add_column(sa.Column('coupon_discount', sa.Float(), server_default='0.0', nullable=False))
        if 'offer_discount' not in order_cols:
            batch_op.add_column(sa.Column('offer_discount', sa.Float(), server_default='0.0', nullable=False))
        if 'flash_sale_discount' not in order_cols:
            batch_op.add_column(sa.Column('flash_sale_discount', sa.Float(), server_default='0.0', nullable=False))

    # 15. Update order_items table
    item_cols = [c['name'] for c in insp.get_columns('order_items')]
    with op.batch_alter_table('order_items') as batch_op:
        if 'offer_discount' not in item_cols:
            batch_op.add_column(sa.Column('offer_discount', sa.Float(), server_default='0.0', nullable=False))
        if 'flash_sale_discount' not in item_cols:
            batch_op.add_column(sa.Column('flash_sale_discount', sa.Float(), server_default='0.0', nullable=False))
        if 'coupon_discount' not in item_cols:
            batch_op.add_column(sa.Column('coupon_discount', sa.Float(), server_default='0.0', nullable=False))
        if 'final_price' not in item_cols:
            batch_op.add_column(sa.Column('final_price', sa.Float(), server_default='0.0', nullable=False))

def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = insp.get_table_names()

    with op.batch_alter_table('order_items') as batch_op:
        batch_op.drop_column('final_price')
        batch_op.drop_column('coupon_discount')
        batch_op.drop_column('flash_sale_discount')
        batch_op.drop_column('offer_discount')

    with op.batch_alter_table('orders') as batch_op:
        batch_op.drop_column('flash_sale_discount')
        batch_op.drop_column('offer_discount')
        batch_op.drop_column('coupon_discount')
        batch_op.drop_column('coupon_code')

    with op.batch_alter_table('carts') as batch_op:
        batch_op.drop_column('applied_coupon_id')
        batch_op.drop_column('coupon_code')

    if 'flash_sale_items' in table_names:
        op.drop_table('flash_sale_items')
    if 'flash_sales' in table_names:
        op.drop_table('flash_sales')
    if 'offer_brands' in table_names:
        op.drop_table('offer_brands')
    if 'offer_categories' in table_names:
        op.drop_table('offer_categories')
    if 'offer_products' in table_names:
        op.drop_table('offer_products')
    if 'offers' in table_names:
        op.drop_table('offers')
    if 'coupon_usages' in table_names:
        op.drop_table('coupon_usages')
    if 'coupon_exclusions' in table_names:
        op.drop_table('coupon_exclusions')
    if 'coupon_brands' in table_names:
        op.drop_table('coupon_brands')
    if 'coupon_categories' in table_names:
        op.drop_table('coupon_categories')
    if 'coupon_products' in table_names:
        op.drop_table('coupon_products')
    if 'coupons' in table_names:
        op.drop_table('coupons')
