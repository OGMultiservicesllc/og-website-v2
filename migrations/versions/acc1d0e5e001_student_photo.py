"""My Account redesign: customer profile photo

Revision ID: acc1d0e5e001
Revises: tx25a1c0de01
Create Date: 2026-09-21 10:00:00

Additive only: one nullable column. No existing table, row, application, case or person is changed.
"""
from alembic import op
import sqlalchemy as sa

revision = "acc1d0e5e001"
down_revision = "tx25a1c0de01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("students", sa.Column("photo_filename", sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column("students", "photo_filename")
