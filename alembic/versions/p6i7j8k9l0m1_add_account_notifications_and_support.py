"""Add account profile avatar, notifications, notification preferences, and support tickets

Revision ID: p6i7j8k9l0m1
Revises: o5h6i7j8k9l0
Create Date: 2026-09-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'p6i7j8k9l0m1'
down_revision = 'o5h6i7j8k9l0'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = insp.get_table_names()

    # 1. Add avatar_url to users table if missing
    if 'users' in table_names:
        cols = [c['name'] for c in insp.get_columns('users')]
        if 'avatar_url' not in cols:
            with op.batch_alter_table('users') as batch_op:
                batch_op.add_column(sa.Column('avatar_url', sa.String(length=500), nullable=True))

    # 2. Create notifications table
    if 'notifications' not in table_names:
        op.create_table(
            'notifications',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('type', sa.String(length=50), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('reference_type', sa.String(length=50), nullable=True),
            sa.Column('reference_id', sa.String(length=100), nullable=True),
            sa.Column('is_read', sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column('read_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_notifications_user_id', 'notifications', ['user_id'], unique=False)
        op.create_index('ix_notifications_is_read', 'notifications', ['is_read'], unique=False)
        op.create_index('ix_notifications_created_at', 'notifications', ['created_at'], unique=False)

    # 3. Create notification_preferences table
    if 'notification_preferences' not in table_names:
        op.create_table(
            'notification_preferences',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('order_updates', sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column('shipment_updates', sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column('return_refund_updates', sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column('promotional_updates', sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column('email_notifications', sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column('in_app_notifications', sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', name='uq_notification_preference_user')
        )
        op.create_index('ix_notification_preferences_user_id', 'notification_preferences', ['user_id'], unique=True)

    # 4. Create support_tickets table
    if 'support_tickets' not in table_names:
        op.create_table(
            'support_tickets',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('ticket_number', sa.String(length=50), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('subject', sa.String(length=255), nullable=False),
            sa.Column('category', sa.String(length=100), server_default='general', nullable=False),
            sa.Column('priority', sa.String(length=50), server_default='medium', nullable=False),
            sa.Column('status', sa.String(length=50), server_default='open', nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('ticket_number', name='uq_support_tickets_ticket_number')
        )
        op.create_index('ix_support_tickets_ticket_number', 'support_tickets', ['ticket_number'], unique=True)
        op.create_index('ix_support_tickets_user_id', 'support_tickets', ['user_id'], unique=False)
        op.create_index('ix_support_tickets_status', 'support_tickets', ['status'], unique=False)
        op.create_index('ix_support_tickets_created_at', 'support_tickets', ['created_at'], unique=False)

    # 5. Create support_messages table
    if 'support_messages' not in table_names:
        op.create_table(
            'support_messages',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('ticket_id', sa.Integer(), sa.ForeignKey('support_tickets.id', ondelete='CASCADE'), nullable=False),
            sa.Column('sender_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('sender_role', sa.String(length=50), server_default='customer', nullable=False),
            sa.Column('sender_name', sa.String(length=255), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('is_internal', sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_support_messages_ticket_id', 'support_messages', ['ticket_id'], unique=False)
        op.create_index('ix_support_messages_created_at', 'support_messages', ['created_at'], unique=False)

def downgrade():
    op.drop_table('support_messages')
    op.drop_table('support_tickets')
    op.drop_table('notification_preferences')
    op.drop_table('notifications')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('avatar_url')
