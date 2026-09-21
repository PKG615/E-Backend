"""Add returns, refunds, and replacements tables

Revision ID: m3f4g5h6i7j8
Revises: l2e3f4g5h6i7
Create Date: 2026-09-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'm3f4g5h6i7j8'
down_revision = 'l2e3f4g5h6i7'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = insp.get_table_names()

    # 1. Create returns table
    if 'returns' not in table_names:
        op.create_table(
            'returns',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('return_number', sa.String(length=50), nullable=False),
            sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('status', sa.String(length=50), server_default='requested', nullable=False),
            sa.Column('resolution_type', sa.String(length=50), server_default='refund', nullable=False),
            sa.Column('reason', sa.String(length=100), nullable=False),
            sa.Column('customer_note', sa.Text(), nullable=True),
            sa.Column('admin_note', sa.Text(), nullable=True),
            sa.Column('rejection_reason', sa.Text(), nullable=True),
            sa.Column('inspection_condition', sa.String(length=50), nullable=True),
            sa.Column('inspection_note', sa.Text(), nullable=True),
            sa.Column('inspected_by', sa.String(length=100), nullable=True),
            sa.Column('inspected_at', sa.DateTime(), nullable=True),
            sa.Column('requested_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('approved_at', sa.DateTime(), nullable=True),
            sa.Column('rejected_at', sa.DateTime(), nullable=True),
            sa.Column('received_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('return_number')
        )
        op.create_index('ix_returns_return_number', 'returns', ['return_number'], unique=True)
        op.create_index('ix_returns_order_id', 'returns', ['order_id'], unique=False)
        op.create_index('ix_returns_user_id', 'returns', ['user_id'], unique=False)
        op.create_index('ix_returns_status', 'returns', ['status'], unique=False)
        op.create_index('ix_returns_created_at', 'returns', ['created_at'], unique=False)

    # 2. Create return_items table
    if 'return_items' not in table_names:
        op.create_table(
            'return_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('return_id', sa.Integer(), sa.ForeignKey('returns.id', ondelete='CASCADE'), nullable=False),
            sa.Column('order_item_id', sa.Integer(), sa.ForeignKey('order_items.id', ondelete='RESTRICT'), nullable=False),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='RESTRICT'), nullable=False),
            sa.Column('variant_id', sa.Integer(), sa.ForeignKey('product_variants.id', ondelete='SET NULL'), nullable=True),
            sa.Column('quantity', sa.Integer(), server_default='1', nullable=False),
            sa.Column('reason', sa.String(length=100), nullable=True),
            sa.Column('condition', sa.String(length=50), nullable=True),
            sa.Column('resolution', sa.String(length=50), server_default='refund', nullable=False),
            sa.Column('refund_amount', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('restocked', sa.Boolean(), server_default=sa.text('false'), nullable=False),
            sa.Column('restocked_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_return_items_return_id', 'return_items', ['return_id'], unique=False)
        op.create_index('ix_return_items_order_item_id', 'return_items', ['order_item_id'], unique=False)
        op.create_index('ix_return_items_product_id', 'return_items', ['product_id'], unique=False)
        op.create_index('ix_return_items_variant_id', 'return_items', ['variant_id'], unique=False)

    # 3. Create return_status_history table
    if 'return_status_history' not in table_names:
        op.create_table(
            'return_status_history',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('return_id', sa.Integer(), sa.ForeignKey('returns.id', ondelete='CASCADE'), nullable=False),
            sa.Column('old_status', sa.String(length=50), nullable=True),
            sa.Column('new_status', sa.String(length=50), nullable=False),
            sa.Column('changed_by', sa.String(length=100), server_default='system', nullable=False),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_return_status_history_return_id', 'return_status_history', ['return_id'], unique=False)
        op.create_index('ix_return_status_history_created_at', 'return_status_history', ['created_at'], unique=False)

    # 4. Create refunds table
    if 'refunds' not in table_names:
        op.create_table(
            'refunds',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('refund_number', sa.String(length=50), nullable=False),
            sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
            sa.Column('return_id', sa.Integer(), sa.ForeignKey('returns.id', ondelete='SET NULL'), nullable=True),
            sa.Column('payment_id', sa.Integer(), sa.ForeignKey('payments.id', ondelete='SET NULL'), nullable=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('amount', sa.Float(), nullable=False),
            sa.Column('currency', sa.String(length=10), server_default='INR', nullable=False),
            sa.Column('status', sa.String(length=50), server_default='requested', nullable=False),
            sa.Column('reason', sa.String(length=255), nullable=True),
            sa.Column('provider', sa.String(length=50), server_default='standard', nullable=False),
            sa.Column('provider_refund_id', sa.String(length=150), nullable=True),
            sa.Column('idempotency_key', sa.String(length=100), nullable=True),
            sa.Column('requested_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('processed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('refund_number')
        )
        op.create_index('ix_refunds_refund_number', 'refunds', ['refund_number'], unique=True)
        op.create_index('ix_refunds_order_id', 'refunds', ['order_id'], unique=False)
        op.create_index('ix_refunds_return_id', 'refunds', ['return_id'], unique=False)
        op.create_index('ix_refunds_payment_id', 'refunds', ['payment_id'], unique=False)
        op.create_index('ix_refunds_user_id', 'refunds', ['user_id'], unique=False)
        op.create_index('ix_refunds_status', 'refunds', ['status'], unique=False)
        op.create_index('ix_refunds_provider_refund_id', 'refunds', ['provider_refund_id'], unique=True)
        op.create_index('ix_refunds_idempotency_key', 'refunds', ['idempotency_key'], unique=True)

    # 5. Create refund_transactions table
    if 'refund_transactions' not in table_names:
        op.create_table(
            'refund_transactions',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('refund_id', sa.Integer(), sa.ForeignKey('refunds.id', ondelete='CASCADE'), nullable=False),
            sa.Column('provider', sa.String(length=50), nullable=False),
            sa.Column('provider_transaction_id', sa.String(length=150), nullable=True),
            sa.Column('amount', sa.Float(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('response_reference', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_refund_transactions_refund_id', 'refund_transactions', ['refund_id'], unique=False)
        op.create_index('ix_refund_transactions_provider_transaction_id', 'refund_transactions', ['provider_transaction_id'], unique=True)

    # 6. Create replacements table
    if 'replacements' not in table_names:
        op.create_table(
            'replacements',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('replacement_number', sa.String(length=50), nullable=False),
            sa.Column('return_id', sa.Integer(), sa.ForeignKey('returns.id', ondelete='CASCADE'), nullable=False),
            sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('shipment_id', sa.Integer(), sa.ForeignKey('shipments.id', ondelete='SET NULL'), nullable=True),
            sa.Column('status', sa.String(length=50), server_default='requested', nullable=False),
            sa.Column('reason', sa.String(length=255), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('replacement_number')
        )
        op.create_index('ix_replacements_replacement_number', 'replacements', ['replacement_number'], unique=True)
        op.create_index('ix_replacements_return_id', 'replacements', ['return_id'], unique=False)
        op.create_index('ix_replacements_order_id', 'replacements', ['order_id'], unique=False)
        op.create_index('ix_replacements_user_id', 'replacements', ['user_id'], unique=False)
        op.create_index('ix_replacements_shipment_id', 'replacements', ['shipment_id'], unique=False)
        op.create_index('ix_replacements_status', 'replacements', ['status'], unique=False)

    # 7. Create replacement_items table
    if 'replacement_items' not in table_names:
        op.create_table(
            'replacement_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('replacement_id', sa.Integer(), sa.ForeignKey('replacements.id', ondelete='CASCADE'), nullable=False),
            sa.Column('original_order_item_id', sa.Integer(), sa.ForeignKey('order_items.id', ondelete='RESTRICT'), nullable=False),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='RESTRICT'), nullable=False),
            sa.Column('variant_id', sa.Integer(), sa.ForeignKey('product_variants.id', ondelete='SET NULL'), nullable=True),
            sa.Column('quantity', sa.Integer(), server_default='1', nullable=False),
            sa.Column('allocated', sa.Boolean(), server_default=sa.text('false'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_replacement_items_replacement_id', 'replacement_items', ['replacement_id'], unique=False)
        op.create_index('ix_replacement_items_original_order_item_id', 'replacement_items', ['original_order_item_id'], unique=False)
        op.create_index('ix_replacement_items_product_id', 'replacement_items', ['product_id'], unique=False)
        op.create_index('ix_replacement_items_variant_id', 'replacement_items', ['variant_id'], unique=False)

    # 8. Create replacement_status_history table
    if 'replacement_status_history' not in table_names:
        op.create_table(
            'replacement_status_history',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('replacement_id', sa.Integer(), sa.ForeignKey('replacements.id', ondelete='CASCADE'), nullable=False),
            sa.Column('old_status', sa.String(length=50), nullable=True),
            sa.Column('new_status', sa.String(length=50), nullable=False),
            sa.Column('changed_by', sa.String(length=100), server_default='system', nullable=False),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_replacement_status_history_replacement_id', 'replacement_status_history', ['replacement_id'], unique=False)
        op.create_index('ix_replacement_status_history_created_at', 'replacement_status_history', ['created_at'], unique=False)


def downgrade():
    op.drop_table('replacement_status_history')
    op.drop_table('replacement_items')
    op.drop_table('replacements')
    op.drop_table('refund_transactions')
    op.drop_table('refunds')
    op.drop_table('return_status_history')
    op.drop_table('return_items')
    op.drop_table('returns')
