"""Add payment and order management tables and columns

Revision ID: k1d2e3f4g5h6
Revises: j0c1d2e3f4g5
Create Date: 2026-09-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'k1d2e3f4g5h6'
down_revision = 'j0c1d2e3f4g5'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    
    # 1. Update orders table
    order_cols = [c['name'] for c in insp.get_columns('orders')]
    with op.batch_alter_table('orders') as batch_op:
        if 'address_id' not in order_cols:
            batch_op.add_column(sa.Column('address_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key('fk_orders_address_id', 'addresses', ['address_id'], ['id'], ondelete='SET NULL')
        if 'currency' not in order_cols:
            batch_op.add_column(sa.Column('currency', sa.String(length=10), server_default='INR', nullable=False))
        if 'placed_at' not in order_cols:
            batch_op.add_column(sa.Column('placed_at', sa.DateTime(), nullable=True))
        if 'idempotency_key' not in order_cols:
            batch_op.add_column(sa.Column('idempotency_key', sa.String(length=100), nullable=True))
            batch_op.create_unique_constraint('uq_orders_idempotency_key', ['idempotency_key'])
        if 'payment_provider' not in order_cols:
            batch_op.add_column(sa.Column('payment_provider', sa.String(length=50), server_default='standard', nullable=False))
            
        existing_indexes = [i['name'] for i in insp.get_indexes('orders')]
        if 'ix_orders_user_id' not in existing_indexes:
            batch_op.create_index('ix_orders_user_id', ['user_id'], unique=False)
        if 'ix_orders_status' not in existing_indexes:
            batch_op.create_index('ix_orders_status', ['status'], unique=False)
        if 'ix_orders_payment_status' not in existing_indexes:
            batch_op.create_index('ix_orders_payment_status', ['payment_status'], unique=False)
        if 'ix_orders_created_at' not in existing_indexes:
            batch_op.create_index('ix_orders_created_at', ['created_at'], unique=False)

    # 2. Update order_items table
    item_cols = [c['name'] for c in insp.get_columns('order_items')]
    with op.batch_alter_table('order_items') as batch_op:
        if 'mrp' not in item_cols:
            batch_op.add_column(sa.Column('mrp', sa.Float(), server_default='0.0', nullable=False))
        if 'discount_amount' not in item_cols:
            batch_op.add_column(sa.Column('discount_amount', sa.Float(), server_default='0.0', nullable=False))
        if 'tax_amount' not in item_cols:
            batch_op.add_column(sa.Column('tax_amount', sa.Float(), server_default='0.0', nullable=False))
        if 'line_total' not in item_cols:
            batch_op.add_column(sa.Column('line_total', sa.Float(), server_default='0.0', nullable=False))
        if 'image_url' not in item_cols:
            batch_op.add_column(sa.Column('image_url', sa.String(length=500), nullable=True))

        item_indexes = [i['name'] for i in insp.get_indexes('order_items')]
        if 'ix_order_items_order_id' not in item_indexes:
            batch_op.create_index('ix_order_items_order_id', ['order_id'], unique=False)
        if 'ix_order_items_product_id' not in item_indexes:
            batch_op.create_index('ix_order_items_product_id', ['product_id'], unique=False)
        if 'ix_order_items_variant_id' not in item_indexes:
            batch_op.create_index('ix_order_items_variant_id', ['variant_id'], unique=False)

    # 3. Create order_status_history table
    table_names = insp.get_table_names()
    if 'order_status_history' not in table_names:
        op.create_table(
            'order_status_history',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
            sa.Column('old_status', sa.String(length=50), nullable=True),
            sa.Column('new_status', sa.String(length=50), nullable=False),
            sa.Column('changed_by', sa.String(length=100), server_default='system', nullable=False),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_order_status_history_order_id', 'order_status_history', ['order_id'], unique=False)
        op.create_index('ix_order_status_history_created_at', 'order_status_history', ['created_at'], unique=False)

    # 4. Create payments table
    if 'payments' not in table_names:
        op.create_table(
            'payments',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('provider', sa.String(length=50), server_default='standard', nullable=False),
            sa.Column('method', sa.String(length=50), nullable=False),
            sa.Column('amount', sa.Float(), nullable=False),
            sa.Column('currency', sa.String(length=10), server_default='INR', nullable=False),
            sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
            sa.Column('provider_payment_id', sa.String(length=150), nullable=True),
            sa.Column('idempotency_key', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_payments_order_id', 'payments', ['order_id'], unique=False)
        op.create_index('ix_payments_user_id', 'payments', ['user_id'], unique=False)
        op.create_index('ix_payments_status', 'payments', ['status'], unique=False)
        op.create_index('ix_payments_provider_payment_id', 'payments', ['provider_payment_id'], unique=True)
        op.create_index('ix_payments_idempotency_key', 'payments', ['idempotency_key'], unique=True)

    # 5. Create payment_transactions table
    if 'payment_transactions' not in table_names:
        op.create_table(
            'payment_transactions',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('payment_id', sa.Integer(), sa.ForeignKey('payments.id', ondelete='CASCADE'), nullable=False),
            sa.Column('transaction_type', sa.String(length=50), nullable=False),
            sa.Column('provider_transaction_id', sa.String(length=150), nullable=True),
            sa.Column('amount', sa.Float(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('response_reference', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_payment_transactions_payment_id', 'payment_transactions', ['payment_id'], unique=False)
        op.create_index('ix_payment_transactions_provider_transaction_id', 'payment_transactions', ['provider_transaction_id'], unique=True)

    # Sync line_total with total_price for existing order_items if any
    op.execute("UPDATE order_items SET line_total = total_price WHERE (line_total IS NULL OR line_total = 0.0) AND total_price IS NOT NULL")


def downgrade():
    op.drop_table('payment_transactions')
    op.drop_table('payments')
    op.drop_table('order_status_history')
