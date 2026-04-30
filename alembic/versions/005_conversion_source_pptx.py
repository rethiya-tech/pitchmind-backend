"""Add source_pptx_key to conversions

Revision ID: 005
Revises: 004
Create Date: 2024-01-05 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('conversions', sa.Column('source_pptx_key', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('conversions', 'source_pptx_key')
