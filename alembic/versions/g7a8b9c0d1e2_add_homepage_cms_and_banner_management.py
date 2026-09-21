"""add_homepage_cms_and_banner_management

Revision ID: g7a8b9c0d1e2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-16 11:30:00.000000

"""
from datetime import datetime
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column, select, insert


# revision identifiers, used by Alembic.
revision: str = 'g7a8b9c0d1e2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    now = datetime.utcnow()

    # 1. Extend banners table with CMS scheduling and CTA fields
    if 'banners' in existing_tables:
        banner_cols = [c['name'] for c in inspector.get_columns('banners')]
        with op.batch_alter_table('banners', schema=None) as batch_op:
            if 'description' not in banner_cols:
                batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
            if 'cta_label' not in banner_cols:
                batch_op.add_column(sa.Column('cta_label', sa.String(length=100), server_default='Explore Now', nullable=True))
            if 'cta_url' not in banner_cols:
                batch_op.add_column(sa.Column('cta_url', sa.String(length=500), nullable=True))
            if 'mobile_image_url' not in banner_cols:
                batch_op.add_column(sa.Column('mobile_image_url', sa.String(length=500), nullable=True))
            if 'start_at' not in banner_cols:
                batch_op.add_column(sa.Column('start_at', sa.DateTime(), nullable=True))
            if 'end_at' not in banner_cols:
                batch_op.add_column(sa.Column('end_at', sa.DateTime(), nullable=True))

    # 2. Create homepage_sections table
    if 'homepage_sections' not in existing_tables:
        op.create_table(
            'homepage_sections',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('section_key', sa.String(length=100), nullable=False),
            sa.Column('section_type', sa.String(length=50), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('subtitle', sa.String(length=255), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
            sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
            sa.Column('configuration', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_homepage_sections_id'), 'homepage_sections', ['id'], unique=False)
        op.create_index(op.f('ix_homepage_sections_section_key'), 'homepage_sections', ['section_key'], unique=True)
        op.create_index(op.f('ix_homepage_sections_section_type'), 'homepage_sections', ['section_type'], unique=False)
        op.create_index(op.f('ix_homepage_sections_sort_order'), 'homepage_sections', ['sort_order'], unique=False)
        op.create_index(op.f('ix_homepage_sections_is_active'), 'homepage_sections', ['is_active'], unique=False)

    # 3. Create homepage_section_items table
    if 'homepage_section_items' not in existing_tables:
        op.create_table(
            'homepage_section_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('section_id', sa.Integer(), nullable=False),
            sa.Column('item_type', sa.String(length=50), nullable=False),
            sa.Column('item_id', sa.Integer(), nullable=True),
            sa.Column('custom_title', sa.String(length=255), nullable=True),
            sa.Column('custom_content', sa.Text(), nullable=True),
            sa.Column('custom_icon', sa.String(length=100), nullable=True),
            sa.Column('custom_url', sa.String(length=500), nullable=True),
            sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
            sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['section_id'], ['homepage_sections.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_homepage_section_items_id'), 'homepage_section_items', ['id'], unique=False)
        op.create_index(op.f('ix_homepage_section_items_section_id'), 'homepage_section_items', ['section_id'], unique=False)
        op.create_index(op.f('ix_homepage_section_items_item_id'), 'homepage_section_items', ['item_id'], unique=False)

    # 4. Create collections table
    if 'collections' not in existing_tables:
        op.create_table(
            'collections',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('slug', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('image_url', sa.String(length=500), nullable=True),
            sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
            sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_collections_id'), 'collections', ['id'], unique=False)
        op.create_index(op.f('ix_collections_slug'), 'collections', ['slug'], unique=True)

    # 5. Create collection_products table
    if 'collection_products' not in existing_tables:
        op.create_table(
            'collection_products',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('collection_id', sa.Integer(), nullable=False),
            sa.Column('product_id', sa.Integer(), nullable=False),
            sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_collection_products_collection_id'), 'collection_products', ['collection_id'], unique=False)
        op.create_index(op.f('ix_collection_products_product_id'), 'collection_products', ['product_id'], unique=False)

    # 6. Create newsletter_subscriptions table
    if 'newsletter_subscriptions' not in existing_tables:
        op.create_table(
            'newsletter_subscriptions',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_newsletter_subscriptions_email'), 'newsletter_subscriptions', ['email'], unique=True)

    # 7. Seed standard initial homepage sections if empty
    sections_tbl = sa.table(
        'homepage_sections',
        sa.column('id', sa.Integer),
        sa.column('section_key', sa.String),
        sa.column('section_type', sa.String),
        sa.column('title', sa.String),
        sa.column('subtitle', sa.String),
        sa.column('description', sa.Text),
        sa.column('sort_order', sa.Integer),
        sa.column('is_active', sa.Boolean),
        sa.column('configuration', sa.JSON),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime)
    )

    items_tbl = sa.table(
        'homepage_section_items',
        sa.column('id', sa.Integer),
        sa.column('section_id', sa.Integer),
        sa.column('item_type', sa.String),
        sa.column('item_id', sa.Integer),
        sa.column('custom_title', sa.String),
        sa.column('custom_content', sa.Text),
        sa.column('custom_icon', sa.String),
        sa.column('custom_url', sa.String),
        sa.column('sort_order', sa.Integer),
        sa.column('is_active', sa.Boolean),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime)
    )

    count_result = conn.execute(sa.text("SELECT count(*) FROM homepage_sections")).scalar()
    if count_result == 0:
        conn.execute(
            insert(sections_tbl).values([
                {
                    'id': 1,
                    'section_key': 'hero_showcase',
                    'section_type': 'HERO_BANNER',
                    'title': 'Special Flagship Showcase',
                    'subtitle': 'Engineered for seamless productivity, refined ergonomics, and top-tier build standards.',
                    'description': 'Hero banner carousel linking to flagship promotions and store collections.',
                    'sort_order': 1,
                    'is_active': True,
                    'configuration': {'autoplay': True, 'interval_seconds': 5},
                    'created_at': now,
                    'updated_at': now
                },
                {
                    'id': 2,
                    'section_key': 'categories_grid',
                    'section_type': 'CATEGORY_GRID',
                    'title': 'Explore Top Categories',
                    'subtitle': 'Handpicked curated collections backed by real database records',
                    'description': 'Hierarchy-aware category grid linked to catalog filters.',
                    'sort_order': 2,
                    'is_active': True,
                    'configuration': {'limit': 6, 'columns': 3},
                    'created_at': now,
                    'updated_at': now
                },
                {
                    'id': 3,
                    'section_key': 'featured_products',
                    'section_type': 'FEATURED_PRODUCTS',
                    'title': 'Featured Flagship Picks',
                    'subtitle': 'High-performance devices handpicked by engineering specialists',
                    'description': 'Showcase of active featured flagship products with real-time inventory.',
                    'sort_order': 3,
                    'is_active': True,
                    'configuration': {'limit': 4, 'columns': 4},
                    'created_at': now,
                    'updated_at': now
                },
                {
                    'id': 4,
                    'section_key': 'new_arrivals',
                    'section_type': 'NEW_ARRIVALS',
                    'title': 'Fresh New Arrivals',
                    'subtitle': 'Latest innovations added to our official inventory',
                    'description': 'Dynamic new arrival products ordered by release date.',
                    'sort_order': 4,
                    'is_active': True,
                    'configuration': {'limit': 4, 'columns': 4},
                    'created_at': now,
                    'updated_at': now
                },
                {
                    'id': 5,
                    'section_key': 'promotional_banner',
                    'section_type': 'PROMOTIONAL_BANNER',
                    'title': 'Enterprise Productivity Strip',
                    'subtitle': 'Explore commercial workgroup packages with extended on-site warranties',
                    'description': 'Promotional banner callout with direct action CTA.',
                    'sort_order': 5,
                    'is_active': True,
                    'configuration': {'banner_id': 2},
                    'created_at': now,
                    'updated_at': now
                },
                {
                    'id': 6,
                    'section_key': 'best_sellers',
                    'section_type': 'BEST_SELLERS',
                    'title': 'Best Sellers & Customer Favorites',
                    'subtitle': 'Highest customer satisfaction and top-tier durability ratings',
                    'description': 'Top merchandising picks from verified customer feedback.',
                    'sort_order': 6,
                    'is_active': True,
                    'configuration': {'limit': 4, 'columns': 4},
                    'created_at': now,
                    'updated_at': now
                },
                {
                    'id': 7,
                    'section_key': 'top_brands',
                    'section_type': 'BRANDS',
                    'title': 'Authorized Brand Partners',
                    'subtitle': '100% genuine products directly sourced from verified manufacturers',
                    'description': 'Brand portfolio strip with links to filtered brand catalogs.',
                    'sort_order': 7,
                    'is_active': True,
                    'configuration': {'layout': 'strip'},
                    'created_at': now,
                    'updated_at': now
                },
                {
                    'id': 8,
                    'section_key': 'trust_info',
                    'section_type': 'TRUST_INFO',
                    'title': 'The Enterprise Guarantee',
                    'subtitle': 'Built with integrity, verified inventory, and dedicated support',
                    'description': 'Four-pillar customer trust information cards.',
                    'sort_order': 8,
                    'is_active': True,
                    'configuration': {'columns': 4},
                    'created_at': now,
                    'updated_at': now
                },
                {
                    'id': 9,
                    'section_key': 'homepage_faq',
                    'section_type': 'FAQ',
                    'title': 'Frequently Asked Questions',
                    'subtitle': 'Everything you need to know about purchasing, warranty, and returns',
                    'description': 'Expandable accordion FAQ section.',
                    'sort_order': 9,
                    'is_active': True,
                    'configuration': {'collapsible': True},
                    'created_at': now,
                    'updated_at': now
                },
                {
                    'id': 10,
                    'section_key': 'newsletter_signup',
                    'section_type': 'NEWSLETTER',
                    'title': 'Subscribe for Exclusive Technical Briefs',
                    'subtitle': 'Receive early hardware dispatch notices, firmware advisories, and member-only promotions.',
                    'description': 'Interactive customer newsletter subscription form.',
                    'sort_order': 10,
                    'is_active': True,
                    'configuration': {'button_text': 'Subscribe'},
                    'created_at': now,
                    'updated_at': now
                }
            ])
        )

        # Seed Trust Info section items (Section 8)
        conn.execute(
            insert(items_tbl).values([
                {
                    'id': 1,
                    'section_id': 8,
                    'item_type': 'trust_item',
                    'custom_icon': 'Truck',
                    'custom_title': 'Free Express Delivery',
                    'custom_content': 'Complimentary ground shipping on qualifying orders with end-to-end GPS dispatch tracking.',
                    'sort_order': 1,
                    'is_active': True,
                    'created_at': now,
                    'updated_at': now
                },
                {
                    'id': 2,
                    'section_id': 8,
                    'item_type': 'trust_item',
                    'custom_icon': 'ShieldCheck',
                    'custom_title': '100% Genuine Authenticity',
                    'custom_content': 'Direct authorized OEM partnerships with official manufacturer warranty coverage.',
                    'sort_order': 2,
                    'is_active': True,
                    'created_at': now,
                    'updated_at': now
                },
                {
                    'id': 3,
                    'section_id': 8,
                    'item_type': 'trust_item',
                    'custom_icon': 'RotateCcw',
                    'custom_title': '7-Day Return Assurance',
                    'custom_content': 'Seamless replacement support for damaged or non-conforming electronics upon delivery.',
                    'sort_order': 3,
                    'is_active': True,
                    'created_at': now,
                    'updated_at': now
                },
                {
                    'id': 4,
                    'section_id': 8,
                    'item_type': 'trust_item',
                    'custom_icon': 'Headphones',
                    'custom_title': 'Specialist Tech Support',
                    'custom_content': 'Dedicated enterprise specialists ready to assist with deployment and compatibility.',
                    'sort_order': 4,
                    'is_active': True,
                    'created_at': now,
                    'updated_at': now
                }
            ])
        )

        # Seed FAQ section items (Section 9)
        conn.execute(
            insert(items_tbl).values([
                {
                    'id': 5,
                    'section_id': 9,
                    'item_type': 'faq',
                    'custom_title': 'How are products sourced and verified?',
                    'custom_content': 'All electronics and components are sourced directly from authorized brand distributors with genuine manufacturer seals and warranty documentation.',
                    'sort_order': 1,
                    'is_active': True,
                    'created_at': now,
                    'updated_at': now
                },
                {
                    'id': 6,
                    'section_id': 9,
                    'item_type': 'faq',
                    'custom_title': 'How accurate is the inventory stock shown on the storefront?',
                    'custom_content': 'Inventory availability is authoritative and synchronized in real time via our PostgreSQL ledger. Items marked "In Stock" are physically on-hand.',
                    'sort_order': 2,
                    'is_active': True,
                    'created_at': now,
                    'updated_at': now
                },
                {
                    'id': 7,
                    'section_id': 9,
                    'item_type': 'faq',
                    'custom_title': 'What payment methods are supported at checkout?',
                    'custom_content': 'We support UPI, Major Credit/Debit Cards, Net Banking, and Cash on Delivery for eligible delivery pincodes.',
                    'sort_order': 3,
                    'is_active': True,
                    'created_at': now,
                    'updated_at': now
                },
                {
                    'id': 8,
                    'section_id': 9,
                    'item_type': 'faq',
                    'custom_title': 'What happens if a received product is damaged?',
                    'custom_content': 'Notify our support team within 7 days of delivery. We arrange free return pickup and dispatch a replacement unit immediately upon receipt verification.',
                    'sort_order': 4,
                    'is_active': True,
                    'created_at': now,
                    'updated_at': now
                }
            ])
        )


def downgrade() -> None:
    op.drop_table('newsletter_subscriptions')
    op.drop_table('collection_products')
    op.drop_table('collections')
    op.drop_table('homepage_section_items')
    op.drop_table('homepage_sections')
    with op.batch_alter_table('banners', schema=None) as batch_op:
        batch_op.drop_column('end_at')
        batch_op.drop_column('start_at')
        batch_op.drop_column('mobile_image_url')
        batch_op.drop_column('cta_url')
        batch_op.drop_column('cta_label')
        batch_op.drop_column('description')
