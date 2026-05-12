"""Add background_image_url to slides

Revision ID: 007
Revises: 006
Create Date: 2026-05-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '34059e7db266'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'slides',
        sa.Column('background_image_url', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('slides', 'background_image_url')
