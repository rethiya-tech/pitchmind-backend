"""add name to conversions

Revision ID: 003
Revises: 002
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversions", sa.Column("name", sa.String(300), nullable=True))


def downgrade() -> None:
    op.drop_column("conversions", "name")
