"""ds260 source snapshots keep the frozen question registry

Revision ID: d260c0a51e02
Revises: d260c0a51e01
Create Date: 2026-09-19 20:00:00

Additive only: one nullable column on ds260_sources.
"""
from alembic import op
import sqlalchemy as sa

revision = "d260c0a51e02"
down_revision = "d260c0a51e01"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ds260_sources", schema=None) as batch_op:
        batch_op.add_column(sa.Column("registry_json", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("ds260_sources", schema=None) as batch_op:
        batch_op.drop_column("registry_json")
