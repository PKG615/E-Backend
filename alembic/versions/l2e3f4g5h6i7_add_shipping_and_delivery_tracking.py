"""Add shipping and delivery tracking tables

Revision ID: l2e3f4g5h6i7
Revises: k1d2e3f4g5h6
Create Date: 2026-09-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'l2e3f4g5h6i7'
down_revision = 'k1d2e3f4g5h6'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = insp.get_table_names()

    # 1. Create shipments table if not exists
    if 'shipments' not in table_names:
        op.create_table(
            'shipments',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
            sa.Column('shipment_number', sa.String(length=50), nullable=False),
            sa.Column('carrier', sa.String(length=100), nullable=True),
            sa.Column('shipping_method', sa.String(length=50), server_default='standard', nullable=False),
            sa.Column('tracking_number', sa.String(length=100), nullable=True),
            sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
            sa.Column('shipping_cost', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('estimated_delivery_date', sa.DateTime(), nullable=True),
            sa.Column('shipped_at', sa.DateTime(), nullable=True),
            sa.Column('delivered_at', sa.DateTime(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('shipment_number')
        )
        op.create_index('ix_shipments_order_id', 'shipments', ['order_id'], unique=False)
        op.create_index('ix_shipments_shipment_number', 'shipments', ['shipment_number'], unique=True)
        op.create_index('ix_shipments_tracking_number', 'shipments', ['tracking_number'], unique=False)
        op.create_index('ix_shipments_status', 'shipments', ['status'], unique=False)
        op.create_index('ix_shipments_created_at', 'shipments', ['created_at'], unique=False)

    # 2. Create shipment_tracking_events table if not exists
    if 'shipment_tracking_events' not in table_names:
        op.create_table(
            'shipment_tracking_events',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('shipment_id', sa.Integer(), sa.ForeignKey('shipments.id', ondelete='CASCADE'), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('location', sa.String(length=255), nullable=True),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('event_time', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('source', sa.String(length=50), server_default='system', nullable=False),
            sa.Column('provider_event_id', sa.String(length=150), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_shipment_tracking_events_shipment_id', 'shipment_tracking_events', ['shipment_id'], unique=False)
        op.create_index('ix_shipment_tracking_events_event_time', 'shipment_tracking_events', ['event_time'], unique=False)
        op.create_index('ix_shipment_tracking_events_provider_event_id', 'shipment_tracking_events', ['provider_event_id'], unique=False)


def downgrade():
    op.drop_table('shipment_tracking_events')
    op.drop_table('shipments')
