"""Add color_scheme and shape_style to slides

Revision ID: 003
Revises: 002
Create Date: 2024-01-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('slides', sa.Column('color_scheme', sa.String(20), nullable=False, server_default='default'))
    op.add_column('slides', sa.Column('shape_style', sa.String(20), nullable=False, server_default='square'))


def downgrade() -> None:
    op.drop_column('slides', 'shape_style')
    op.drop_column('slides', 'color_scheme')
