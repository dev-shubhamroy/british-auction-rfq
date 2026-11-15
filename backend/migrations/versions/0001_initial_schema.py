"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-15 14:16:52.237957

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('rfqs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reference_id', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('pickup_date', sa.Date(), nullable=False),
    sa.Column('bid_start_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('bid_close_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('current_close_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('forced_close_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('british_auction_enabled', sa.Boolean(), nullable=False),
    sa.Column('trigger_window_minutes', sa.Integer(), nullable=True),
    sa.Column('extension_minutes', sa.Integer(), nullable=True),
    sa.Column('trigger_type', sa.Enum('BID_RECEIVED', 'ANY_RANK_CHANGE', 'L1_CHANGE', name='triggertype', native_enum=False, create_constraint=True, length=20), nullable=True),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('reference_id')
    )
    op.create_index(op.f('ix_rfqs_closed_at'), 'rfqs', ['closed_at'], unique=False)
    op.create_table('suppliers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('activity_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('rfq_id', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.Enum('RFQ_CREATED', 'BID_SUBMITTED', 'RANK_CHANGED', 'L1_CHANGED', 'AUCTION_EXTENDED', 'AUCTION_CLOSED', 'AUCTION_FORCE_CLOSED', name='eventtype', native_enum=False, create_constraint=True, length=30), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('previous_close_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('new_close_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['rfq_id'], ['rfqs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_activity_logs_rfq_id'), 'activity_logs', ['rfq_id'], unique=False)
    op.create_table('bids',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('rfq_id', sa.Integer(), nullable=False),
    sa.Column('supplier_id', sa.Integer(), nullable=False),
    sa.Column('carrier_name', sa.String(length=200), nullable=False),
    sa.Column('freight_charges', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('origin_charges', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('destination_charges', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('transit_time_days', sa.Integer(), nullable=False),
    sa.Column('quote_validity_date', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['rfq_id'], ['rfqs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bids_rfq_supplier', 'bids', ['rfq_id', 'supplier_id'], unique=False)
    op.create_index('ix_bids_rfq_total', 'bids', ['rfq_id', 'total_amount', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_bids_rfq_total', table_name='bids')
    op.drop_index('ix_bids_rfq_supplier', table_name='bids')
    op.drop_table('bids')
    op.drop_index(op.f('ix_activity_logs_rfq_id'), table_name='activity_logs')
    op.drop_table('activity_logs')
    op.drop_table('suppliers')
    op.drop_index(op.f('ix_rfqs_closed_at'), table_name='rfqs')
    op.drop_table('rfqs')
