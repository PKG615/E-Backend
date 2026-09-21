"""add_inventory_and_transactions_management

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-16 10:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column, select, insert


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create inventory table
    op.create_table(
        'inventory',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('variant_id', sa.Integer(), nullable=True),
        sa.Column('sku', sa.String(length=100), nullable=False),
        sa.Column('on_hand_quantity', sa.Integer(), server_default='0', nullable=False),
        sa.Column('reserved_quantity', sa.Integer(), server_default='0', nullable=False),
        sa.Column('available_quantity', sa.Integer(), server_default='0', nullable=False),
        sa.Column('low_stock_threshold', sa.Integer(), server_default='5', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_id'), 'inventory', ['id'], unique=False)
    op.create_index(op.f('ix_inventory_product_id'), 'inventory', ['product_id'], unique=False)
    op.create_index(op.f('ix_inventory_variant_id'), 'inventory', ['variant_id'], unique=False)
    op.create_index(op.f('ix_inventory_sku'), 'inventory', ['sku'], unique=False)

    # Partial unique indexes for 1:1 inventory record per sellable item
    # Note: SQLite supports CREATE UNIQUE INDEX with WHERE clause
    op.create_index(
        'uq_inventory_product_null_variant',
        'inventory',
        ['product_id'],
        unique=True,
        sqlite_where=sa.text('variant_id IS NULL'),
        postgresql_where=sa.text('variant_id IS NULL')
    )
    op.create_index(
        'uq_inventory_variant',
        'inventory',
        ['variant_id'],
        unique=True,
        sqlite_where=sa.text('variant_id IS NOT NULL'),
        postgresql_where=sa.text('variant_id IS NOT NULL')
    )

    # 2. Create inventory_transactions table
    op.create_table(
        'inventory_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('inventory_id', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(length=50), nullable=False),
        sa.Column('quantity_change', sa.Integer(), nullable=False),
        sa.Column('quantity_before', sa.Integer(), nullable=False),
        sa.Column('quantity_after', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=False),
        sa.Column('reference_type', sa.String(length=50), nullable=True),
        sa.Column('reference_id', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=100), server_default='system', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['inventory_id'], ['inventory.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_transactions_id'), 'inventory_transactions', ['id'], unique=False)
    op.create_index(op.f('ix_inventory_transactions_inventory_id'), 'inventory_transactions', ['inventory_id'], unique=False)
    op.create_index(op.f('ix_inventory_transactions_transaction_type'), 'inventory_transactions', ['transaction_type'], unique=False)
    op.create_index(op.f('ix_inventory_transactions_created_at'), 'inventory_transactions', ['created_at'], unique=False)

    # 3. Data Migration: Seed inventory from existing products & variants
    conn = op.get_bind()
    
    # Query products
    products_res = conn.execute(sa.text("SELECT id, sku, stock, is_active FROM products")).fetchall()
    variants_res = conn.execute(sa.text("SELECT id, product_id, sku, stock, is_active FROM product_variants")).fetchall()
    
    variants_by_product = {}
    for v in variants_res:
        pid = v[1]
        if pid not in variants_by_product:
            variants_by_product[pid] = []
        variants_by_product[pid].append(v)
        
    for p in products_res:
        pid, psku, pstock, pis_active = p[0], p[1], p[2] or 0, bool(p[3])
        p_variants = variants_by_product.get(pid, [])
        
        if p_variants:
            # Has variants: migrate each variant to inventory
            for v in p_variants:
                vid, v_pid, vsku, vstock, vis_active = v[0], v[1], v[2], v[3] or 0, bool(v[4])
                inv_res = conn.execute(
                    sa.text(
                        "INSERT INTO inventory (product_id, variant_id, sku, on_hand_quantity, reserved_quantity, available_quantity, low_stock_threshold, is_active) "
                        "VALUES (:product_id, :variant_id, :sku, :on_hand, 0, :on_hand, 5, :is_active)"
                    ),
                    {
                        "product_id": pid,
                        "variant_id": vid,
                        "sku": vsku or f"SKU-{pid}-{vid}",
                        "on_hand": max(0, int(vstock)),
                        "is_active": vis_active
                    }
                )
                inv_id = inv_res.lastrowid
                conn.execute(
                    sa.text(
                        "INSERT INTO inventory_transactions (inventory_id, transaction_type, quantity_change, quantity_before, quantity_after, reason, created_by) "
                        "VALUES (:inventory_id, 'RECEIVE', :qty, 0, :qty, 'Initial migration from variant stock', 'system')"
                    ),
                    {
                        "inventory_id": inv_id,
                        "qty": max(0, int(vstock))
                    }
                )
        else:
            # Non-variant product: migrate product to inventory
            inv_res = conn.execute(
                sa.text(
                    "INSERT INTO inventory (product_id, variant_id, sku, on_hand_quantity, reserved_quantity, available_quantity, low_stock_threshold, is_active) "
                    "VALUES (:product_id, NULL, :sku, :on_hand, 0, :on_hand, 5, :is_active)"
                ),
                {
                    "product_id": pid,
                    "sku": psku or f"SKU-PROD-{pid}",
                    "on_hand": max(0, int(pstock)),
                    "is_active": pis_active
                }
            )
            inv_id = inv_res.lastrowid
            conn.execute(
                sa.text(
                    "INSERT INTO inventory_transactions (inventory_id, transaction_type, quantity_change, quantity_before, quantity_after, reason, created_by) "
                    "VALUES (:inventory_id, 'RECEIVE', :qty, 0, :qty, 'Initial migration from product stock', 'system')"
                ),
                {
                    "inventory_id": inv_id,
                    "qty": max(0, int(pstock))
                }
            )


def downgrade() -> None:
    op.drop_table('inventory_transactions')
    op.drop_table('inventory')
