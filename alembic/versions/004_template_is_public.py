"""Add is_public to templates

Revision ID: 004
Revises: 003
Create Date: 2024-01-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('templates', sa.Column('is_public', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    op.drop_column('templates', 'is_public')
